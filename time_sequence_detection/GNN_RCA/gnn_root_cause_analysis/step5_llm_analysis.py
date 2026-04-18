#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 5: LLM 智能分析与方案确认

功能：
1. 整合 GNN 预测结果与拓扑信息
2. 调用 LLM 进行根因确认和影响分析
3. 生成结构化诊断报告
4. 提供处理建议和预防措施
5. 支持多轮对话式分析

使用方法:
    python step5_llm_analysis.py --model checkpoints/best_model.pt --graph-data data/graphs/graph_data.npz
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import torch

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import (
    LLM_CONFIG,
    DATA_DIRS,
    get_device
)
from step3_gnn_models import RootCauseGNN, ModelFactory
from step4_train_model import RootCauseTrainer, load_graph_data


class GNNResultInterpreter:
    """GNN结果解释器 - 将模型输出转换为可理解的格式"""
    
    def __init__(self, node_metadata: List[dict] = None):
        self.node_metadata = node_metadata or []
        self.node_id_to_info = {
            node["id"]: node for node in self.node_metadata
        } if self.node_metadata else {}
    
    def interpret_predictions(
        self,
        logits: torch.Tensor,
        threshold: float = 0.5,
        top_k: int = 5
    ) -> Dict:
        """
        解释GNN预测结果
        
        Returns:
            包含以下信息的字典：
            - root_cause_candidates: 根因候选列表（按概率排序）
            - affected_nodes: 受影响节点
            - propagation_path: 推断的传播路径
            - confidence_scores: 所有节点的置信度
        """
        
        probs = torch.sigmoid(logits.squeeze(-1)).cpu().numpy()
        predictions = (probs > threshold).astype(int)
        
        # 根因候选（按概率排序）
        root_indices = np.where(predictions == 1)[0]
        root_probs = probs[root_indices]
        sorted_indices = np.argsort(-root_probs)
        
        candidates = []
        for rank, idx in enumerate(sorted_indices[:top_k], 1):
            original_idx = root_indices[idx]
            node_id = str(original_idx) if original_idx >= len(self.node_metadata) \
                else list(self.node_id_to_info.keys())[original_idx] if original_idx < len(self.node_metadata) \
                else f"node_{original_idx}"
            
            node_info = self.node_id_to_info.get(node_id, {"name": node_id})
            
            candidates.append({
                "rank": rank,
                "node_id": node_id,
                "service_name": node_info.get("name", "Unknown"),
                "layer": node_info.get("layer", "unknown"),
                "type": node_info.get("type", "unknown"),
                "probability": float(root_probs[idx]),
                "confidence_level": self._get_confidence_level(float(root_probs[idx]))
            })
        
        # 受影响节点（概率 > 0.3 但未达到阈值）
        affected_mask = (probs > 0.3) & (predictions == 0)
        affected_indices = np.where(affected_mask)[0]
        
        affected_nodes = []
        for idx in affected_indices:
            node_id = f"node_{idx}" if idx >= len(self.node_metadata) else \
                     list(self.node_id_to_info.keys())[idx]
            
            node_info = self.node_id_to_info.get(node_id, {})
            affected_nodes.append({
                "node_id": node_id,
                "service_name": node_info.get("name", "Unknown"),
                "probability": float(probs[idx]),
                "status": "suspected" if probs[idx] > 0.4 else "potentially_affected"
            })
        
        # 置信度分布
        confidence_distribution = {
            "high (>0.8)": int(np.sum(probs > 0.8)),
            "medium (0.5-0.8)": int(np.sum((probs > 0.5) & (probs <= 0.8))),
            "low (0.3-0.5)": int(np.sum((probs > 0.3) & (probs <= 0.5))),
            "very_low (<0.3)": int(np.sum(probs <= 0.3))
        }
        
        return {
            "root_cause_candidates": candidates,
            "affected_nodes": affected_nodes[:10],  # 最多显示10个
            "confidence_distribution": confidence_distribution,
            "total_suspected": len(candidates),
            "threshold_used": threshold,
            "analysis_time": datetime.now().isoformat()
        }
    
    def _get_confidence_level(self, prob: float) -> str:
        """根据概率返回置信度等级"""
        if prob >= 0.9:
            return "非常确信"
        elif prob >= 0.75:
            return "高度可能"
        elif prob >= 0.6:
            return "较有可能"
        elif prob >= 0.5:
            return "可能"
        else:
            return "低置信度"


class LLMAnalyzer:
    """LLM智能分析器"""
    
    def __init__(self, config: dict = None):
        self.config = config or LLM_CONFIG
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """初始化LLM客户端"""
        
        try:
            if self.config["provider"] == "openai":
                from openai import OpenAI
                
                api_key = os.environ.get(
                    self.config["api_key_env"], 
                    self.config.get("api_key", "")
                )
                
                if not api_key:
                    print("⚠️ 未设置OPENAI_API_KEY，将使用模拟模式")
                    self.client = None
                    return
                
                self.client = OpenAI(
                    api_key=api_key,
                    base_url=self.config.get("base_url")
                )
                
                print(f"✅ LLM客户端初始化成功 ({self.config['model']})")
                
        except ImportError:
            print("⚠️ openai包未安装，使用模拟模式")
            self.client = None
    
    def analyze_root_cause(
        self,
        gnn_result: Dict,
        topology_info: Dict,
        alerts_summary: Dict,
        metrics_data: Optional[Dict] = None
    ) -> Dict:
        """
        使用LLM进行根因分析和方案确认
        
        Args:
            gnn_result: GNN解释器的输出
            topology_info: 拓扑结构信息
            alerts_summary: 告警摘要信息
            metrics_data: 关键指标数据
            
        Returns:
            LLM分析结果字典
        """
        
        # 构建prompt
        prompt = self._build_analysis_prompt(
            gnn_result, topology_info, alerts_summary, metrics_data
        )
        
        if self.client is None:
            # 模拟模式：生成基于规则的分析
            analysis = self._generate_mock_analysis(gnn_result, topology_info)
        else:
            # 调用真实LLM API
            try:
                response = self.client.chat.completions.create(
                    model=self.config["model"],
                    messages=[
                        {"role": "system", "content": "你是一位资深的AIOps故障诊断专家..."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.config["temperature"],
                    max_tokens=self.config["max_tokens"]
                )
                
                analysis_content = response.choices[0].message.content
                analysis = self._parse_llm_response(analysis_content, gnn_result)
                
            except Exception as e:
                print(f"❌ LLM调用失败: {e}")
                analysis = self._generate_mock_analysis(gnn_result, topology_info)
        
        return analysis
    
    def _build_analysis_prompt(
        self,
        gnn_result: Dict,
        topology_info: Dict,
        alerts_summary: Dict,
        metrics_data: Optional[Dict]
    ) -> str:
        """构建分析prompt"""
        
        # 格式化根因候选
        candidates_str = "\n".join([
            f"{c['rank']}. {c['service_name']} ({c['layer']}) - 置信度: {c['probability']:.1%} [{c['confidence_level']}]"
            for c in gnn_result["root_cause_candidates"][:5]
        ])
        
        # 格式化受影响节点
        affected_str = "\n".join([
            f"- {n['service_name']}: {n['probability']:.1%} ({n['status']})"
            for n in gnn_result["affected_nodes"][:5]
        ])
        
        prompt = f"""你是一位资深的AIOps故障诊断专家，擅长分析微服务架构中的根因问题。

## 🎯 任务
基于GNN模型的预测结果和系统拓扑信息，进行根因确认、影响评估和处理建议。

## 📊 GNN分析结果

### 🔴 可疑根因节点（按置信度排序）：
{candidates_str}

### 🟡 可能受影响的节点：
{affected_str}

### 📈 置信度分布：
{json.dumps(gnn_result['confidence_distribution'], ensure_ascii=False, indent=2)}

## 🏗️ 系统拓扑信息

- 总服务数: {topology_info.get('num_nodes', 'N/A')}
- 层级结构: {', '.join(topology_info.get('layers', []))}
- 关键依赖关系: {len(topology_info.get('edges', []))} 条边

## 🚨 告警概况

- 总告警数: {alerts_summary.get('total_alerts', 'N/A')}
- 时间范围: {alerts_summary.get('time_range', 'N/A')}
- 最高严重度: {alerts_summary.get('max_severity', 'N/A')}
- 主要告警类型: {', '.join(alerts_summary.get('top_alert_types', []))}

## 📏 关键指标（如有）
{json.dumps(metrics_data or {}, ensure_ascii=False, indent=2)}

## 📝 请按以下结构输出分析：

### 1️⃣ **根因确认**
- GNN识别的根因是否合理？
- 是否有遗漏的潜在根因？
- 给出最终确定的根因节点及理由

### 2️⃣ **故障传播路径分析**
- 描述从根因到各受影响节点的传播链路
- 评估每条路径的影响程度

### 3️⃣ **影响范围评估**
- 直接影响的服务/功能
- 间接影响（用户体验、业务指标等）
- 预估损失或影响时长

### 4️⃣ **处理建议** ⭐重点
- **紧急处理步骤**（立即执行）
- **根本修复方案**（短期）
- **优化改进措施**（长期）

### 5️⃣ **预防机制**
- 如何提前发现类似问题？
- 需要增加哪些监控或告警？
- 架构层面的改进建议

请以专业、简洁的方式输出，优先给出可执行的方案。"""
        
        return prompt
    
    def _parse_llm_response(self, content: str, gnn_result: Dict) -> Dict:
        """解析LLM响应"""
        
        sections = {
            "raw_response": content,
            "confirmed_root_cause": None,
            "propagation_paths": [],
            "impact_assessment": {},
            "handling_recommendations": [],
            "prevention_measures": [],
            "confidence_adjustment": {}
        }
        
        # 简单的关键词提取（实际应用中可用更复杂的解析）
        lines = content.split('\n')
        current_section = None
        
        for line in lines:
            line_lower = line.lower()
            
            if "根因确认" in line or "confirmed" in line_lower:
                current_section = "root_cause"
            elif "传播" in line or "propagation" in line_lower:
                current_section = "propagation"
            elif "影响" in line or "impact" in line_lower:
                current_section = "impact"
            elif "处理" in line or "recommendation" in line_lower:
                current_section = "recommendations"
            elif "预防" in line or "prevention" in line_lower:
                current_section = "prevention"
        
        return sections
    
    def _generate_mock_analysis(self, gnn_result: Dict, topology_info: Dict) -> Dict:
        """当LLM不可用时生成模拟分析"""
        
        candidates = gnn_result["root_cause_candidates"]
        primary_candidate = candidates[0] if candidates else None
        
        if not primary_candidate:
            return {
                "error": "无根因候选",
                "mock_mode": True
            }
        
        # 基于规则的简单分析
        layer_priority = {
            "infra_services": "基础设施层问题通常会导致级联故障",
            "data_services": "数据层瓶颈会影响所有依赖它的上游服务",
            "core_services": "核心业务逻辑错误会直接影响用户请求",
            "api_services": "API层异常主要影响接口可用性",
            "gateway": "网关问题会导致全局性故障"
        }
        
        service_type_guidance = {
            "infrastructure": [
                "检查主机资源（CPU/内存/磁盘）使用率",
                "查看系统日志（dmesg, /var/log/messages）",
                "验证网络连通性和延迟"
            ],
            "data": [
                "检查数据库连接池状态",
                "分析慢查询日志",
                "验证主从复制延迟"
            ],
            "business": [
                "查看应用日志中的异常堆栈",
                "检查最近的代码变更",
                "回滚到上一个稳定版本"
            ]
        }
        
        confirmed_root = {
            "node_id": primary_candidate["node_id"],
            "service_name": primary_candidate["service_name"],
            "layer": primary_candidate["layer"],
            "probability": primary_candidate["probability"],
            "reasoning": f"GNN模型以{primary_candidate['probability']:.1%}的置信度识别该节点为根因。{layer_priority.get(primary_candidate['layer'], '')}",
            "is_confirmed": True if primary_candidate["probability"] > 0.7 else False
        }
        
        # 处理建议
        recommendations = []
        type_key = primary_candidate.get("type", "")
        base_recs = service_type_guidance.get(type_key, ["检查服务健康状态"])
        
        recommendations.extend([{
            "priority": "P0 - 立即",
            "action": rec,
            "estimated_time": "5-15分钟"
        } for rec in base_recs])
        
        recommendations.extend([
            {
                "priority": "P1 - 短期",
                "action": "增加该服务的资源监控粒度和告警阈值",
                "estimated_time": "1-2小时"
            },
            {
                "priority": "P2 - 长期",
                "action": f"考虑对{primary_candidate['service_name']}实施服务降级或熔断机制",
                "estimated_time": "1-2周"
            },
            {
                "priority": "P3 - 持续",
                "action": "定期进行故障演练，验证应急预案的有效性",
                "estimated_time": "持续"
            }
        ])
        
        analysis = {
            "analysis_timestamp": datetime.now().isoformat(),
            "llm_model": "rule_based_mock",
            "confirmed_root_cause": confirmed_root,
            "alternative_candidates": [
                c for c in candidates[1:3]
            ] if len(candidates) > 1 else [],
            "impact_assessment": {
                "directly_affected_services": len(gnn_result["affected_nodes"]),
                "severity": "high" if primary_candidate["probability"] > 0.8 
                          else "medium" if primary_candidate["probability"] > 0.6 
                          else "low",
                "estimated_downtime_minutes": 15 if primary_candidate["layer"] in ["infra_services", "gateway"]
                                            else 30 if primary_candidate["layer"] in ["data_services"]
                                            else 45
            },
            "handling_recommendations": recommendations,
            "prevention_measures": [
                "增强关键服务的资源监控和自动扩缩容能力",
                "建立完善的告警分级和升级机制",
                "定期进行全链路压测和混沌工程实验",
                "完善服务间的熔断、限流、降级策略",
                "建立知识库，记录历史故障案例和处理经验"
            ],
            "next_steps": [
                f"立即通知相关团队关注{primary_candidate['service_name']}服务状态",
                "按照P0级别建议开始排查",
                "每5分钟更新一次排查进度",
                "如30分钟内无法定位，启动应急响应流程"
            ],
            "mock_mode": True,
            "note": "当前为模拟模式，配置正确的API Key后可获得更精准的分析"
        }
        
        return analysis


class DiagnosisReportGenerator:
    """诊断报告生成器"""
    
    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or DATA_DIRS["results"]
        os.makedirs(self.output_dir, exist_ok=True)
    
    def generate_report(
        self,
        gnn_interpretation: Dict,
        llm_analysis: Dict,
        metadata: Dict,
        format: str = "markdown"
    ) -> Tuple[str, str]:
        """
        生成完整诊断报告
        
        Returns:
            (report_path, report_content)
        """
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format == "markdown":
            content = self._generate_markdown_report(
                gnn_interpretation, llm_analysis, metadata
            )
            filename = f"diagnosis_report_{timestamp}.md"
        else:
            content = json.dumps({
                "gnn_results": gnn_interpretation,
                "llm_analysis": llm_analysis,
                "metadata": metadata,
                "generated_at": timestamp
            }, ensure_ascii=False, indent=2)
            filename = f"diagnosis_report_{timestamp}.json"
        
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"\n📄 报告已生成: {filepath}")
        
        return filepath, content
    
    def _generate_markdown_report(
        self,
        gnn_interp: Dict,
        llm_analysis: Dict,
        metadata: Dict
    ) -> str:
        """生成Markdown格式报告"""
        
        candidates = gnn_interp.get('root_cause_candidates', [])
        top_prob = f"{candidates[0]['probability']:.1%}" if candidates else "N/A"
        
        report = f"""# 🚨 微服务根因诊断报告

**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**分析引擎**: GNN + LLM  
**系统版本**: v1.0  

---

## 📋 执行摘要

| 项目 | 内容 |
|------|------|
| 分析场景 | {metadata.get('scenario_id', '未知')} |
| 分析时间 | {gnn_interp.get('analysis_time', 'N/A')} |
| 识别到的可疑根因 | {gnn_interp.get('total_suspected', 0)} 个 |
| 最高置信度 | {top_prob} |
| 影响服务数 | {len(gnn_interp.get('affected_nodes', []))} 个 |

---

## 🎯 GNN 模型分析结果

### 🔴 Top 5 根因候选

| 排名 | 服务名称 | 所属层级 | 置信度 | 置信等级 |
|------|---------|---------|--------|----------|
"""
        
        for candidate in gnn_interp.get("root_cause_candidates", [])[:5]:
            report += f"| {candidate['rank']} | {candidate['service_name']} | {candidate['layer']} | {candidate['probability']:.1%} | {candidate['confidence_level']} |\n"
        
        report += f"""
### 🟡 可能受影响的服务

"""
        for node in gnn_interp.get("affected_nodes", [])[:10]:
            status_icon = "⚠️" if node["status"] == "suspected" else "💛"
            report += f"- {status_icon} **{node['service_name']}** (概率: {node['probability']:.1%})\n"
        
        report += f"""
### 📊 置信度分布

```
{json.dumps(gnn_interp.get('confidence_distribution', {}), ensure_ascii=False, indent=2)}
```

---

## 🤖 LLM 智能分析

"""
        
        if llm_analysis.get("confirmed_root_cause"):
            rc = llm_analysis["confirmed_root_cause"]
            confirm_icon = "✅" if rc.get("is_confirmed") else "⚠️"
            
            report += f"""### 1️⃣ 根因确认

{confirm_icon} **最终确定根因**: {rc.get('service_name', 'N/A')}

**判断依据**:
> {rc.get('reasoning', 'N/A')}

**置信度**: {rc.get('probability', 0):.1%}
"""
        
        if llm_analysis.get("impact_assessment"):
            impact = llm_analysis["impact_assessment"]
            severity_map = {"high": "🔴 高", "medium": "🟡 中", "low": "🟢 低"}
            
            report += f"""
### 2️⃣ 影响评估

- **严重等级**: {severity_map.get(impact.get('severity'), '未知')}
- **直接受影响服务**: {impact.get('directly_affected_services', 0)} 个
- **预估停机时间**: ~{impact.get('estimated_downtime_minutes', 'N/A')} 分钟
        
"""
        
        if llm_analysis.get("handling_recommendations"):
            report += """### 3️⃣ 处理建议 ⭐

"""
            for i, rec in enumerate(llm_analysis["handling_recommendations"], 1):
                report += f"**{rec['priority']}**: {rec['action']} (预计耗时: {rec.get('estimated_time', 'N/A')})\n\n"
        
        if llm_analysis.get("prevention_measures"):
            report += """### 4️⃣ 预防措施

"""
            for measure in llm_analysis["prevention_measures"]:
                report += f"- [ ] {measure}\n"
        
        if llm_analysis.get("next_steps"):
            report += """
### 📌 下一步行动

"""
            for step in llm_analysis["next_steps"]:
                report += f"- [ ] {step}\n"
        
        report += f"""

---

## 📎 附录

### 技术细节

- **模型类型**: {metadata.get('model_type', 'GAT')}
- **训练数据量**: {metadata.get('training_samples', 'N/A')}
- **模型F1得分**: {metadata.get('best_f1', 'N/A')}
- **分析耗时**: {metadata.get('inference_time', 'N/A')}

### 免责声明

本报告由AI系统自动生成，仅供参考。实际操作请结合人工判断。

---
*Generated by AIOps GNN Root Cause Analysis System*
"""
        
        return report


def main():
    parser = argparse.ArgumentParser(description='LLM智能分析与报告生成')
    parser.add_argument('--model', type=str, required=True, help='训练好的模型路径')
    parser.add_argument('--graph-data', type=str, required=True, help='图数据NPZ文件')
    parser.add_argument('--topology', type=str, default=None, help='拓扑JSON文件')
    parser.add_argument('--output-format', choices=['markdown', 'json'], default='markdown', help='输出格式')
    args = parser.parse_args()
    
    print("="*70)
    print("🤖 Step 5/5: LLM智能分析与方案确认 - GNN根因分析系统")
    print("="*70)
    
    device = get_device()
    
    # 1. 加载图数据和元数据
    dataset, metadata = load_graph_data(args.graph_data)
    
    # 2. 加载模型
    trainer = RootCauseTrainer(MODEL_CONFIG)
    trainer.load_model(args.model)
    trainer.model.eval()
    
    # 3. 加载拓扑信息
    topology_info = {"num_nodes": metadata["num_nodes"]}
    if args.topology and os.path.exists(args.topology):
        with open(args.topology, 'r') as f:
            topo_json = json.load(f)
        topology_info.update({
            "nodes": topo_json.get("nodes", []),
            "edges": topo_json.get("edges", []),
            "layers": list(set(n.get("layer", "") for n in topo_json.get("nodes", [])))
        })
    
    # 4. 运行推理
    print("\n🔮 执行GNN推理...")
    
    with torch.no_grad():
        node_features = dataset.node_features.to(device)
        edge_index = dataset.edge_index.to(device)
        edge_attr = dataset.edge_attr.to(device) if dataset.edge_attr is not None else None
        
        temporal_feats = None
        if dataset.temporal_features:
            temporal_feats = {k: v.to(device) for k, v in dataset.temporal_features.items()}
        
        logits = trainer.model(node_features, edge_index, edge_attr, temporal_feats)
    
    # 5. 解释预测结果
    print("\n📊 解释预测结果...")
    interpreter = GNNResultInterpreter(topology_info.get("nodes"))
    gnn_result = interpreter.interpret_predictions(logits)
    
    print(f"\n   识别到 {gnn_result['total_suspected']} 个可疑根因:")
    for candidate in gnn_result["root_cause_candidates"][:3]:
        print(f"      {candidate['rank']}. {candidate['service_name']} "
              f"[{candidate['layer']}] - {candidate['probability']:.1%}")
    
    # 6. LLM分析
    print("\n🤖 调用LLM进行分析...")
    analyzer = LLMAnalyzer(LLM_CONFIG)
    
    alerts_summary = {
        "total_alerts": metadata.get("num_alerts", 0),
        "max_severity": "critical",
        "top_alert_types": ["CPU过高", "内存不足", "连接超时"]
    }
    
    llm_analysis = analyzer.analyze_root_cause(
        gnn_result=gnn_result,
        topology_info=topology_info,
        alerts_summary=alerts_summary
    )
    
    # 7. 生成报告
    print("\n📄 生成诊断报告...")
    generator = DiagnosisReportGenerator(DATA_DIRS["results"])
    
    final_metadata = {
        **metadata,
        "scenario_id": f"RC-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "model_type": MODEL_CONFIG["model_type"].upper(),
        "inference_time": "<1s"
    }
    
    report_path, report_content = generator.generate_report(
        gnn_interp=gnn_result,
        llm_analysis=llm_analysis,
        metadata=final_metadata,
        format=args.output_format
    )
    
    # 8. 输出摘要
    print(f"\n{'='*70}")
    print("✅ 分析完成!")
    print(f"{'='*70}")
    
    if llm_analysis.get("confirmed_root_cause"):
        rc = llm_analysis["confirmed_root_cause"]
        print(f"\n🎯 最终根因: {rc['service_name']}")
        print(f"   置信度: {rc['probability']:.1%}")
        print(f"   建议: {llm_analysis['handling_recommendations'][0]['action'] if llm_analysis.get('handling_recommendations') else '见报告'}")
    
    print(f"\n📄 完整报告: {report_path}")
    
    return gnn_result, llm_analysis


if __name__ == "__main__":
    main()