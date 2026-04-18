#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 2: Drain 日志解析层

功能：
1. 基于前缀树的日志模板提取
2. 自动识别静态部分和动态部分
3. 生成日志模板ID和参数值
4. 支持增量解析

核心算法：Drain (Log Parser with Fixed-depth Tree)
论文: "Drain: An Online Log Parsing Approach with Fixed Depth Tree"
"""

import re
import json
import sys
from collections import defaultdict, OrderedDict
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from config import DRAIN_CONFIG, DATA_DIRS


@dataclass
class LogTemplate:
    """日志模板数据结构"""
    template_id: str
    template_str: str
    occurrence_count: int = 0
    parameters: List[str] = None
    
    def __post_init__(self):
        if self.parameters is None:
            self.parameters = []


class LogNode:
    """前缀树节点"""
    
    def __init__(self, token: str = "", is_wildcard: bool = False):
        self.token = token
        self.is_wildcard = is_wildcard
        
        self.children: Dict[str, 'LogNode'] = {}
        
        self.template_clusters: List[Dict] = []
    
    def add_child(self, child_node: 'LogNode'):
        self.children[child_node.token] = child_node
    
    def get_child(self, token: str) -> Optional['LogNode']:
        return self.children.get(token)


class DrainParser:
    """
    Drain 日志解析器
    
    核心思想：
    1. 使用固定深度的前缀树组织日志消息
    2. 第一层按token数量分组
    3. 第二层按前N个token分组（快速定位）
    4. 后续层存储具体模板或通配符节点
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or DRAIN_CONFIG
        
        self.depth = self.config["depth"]
        self.sim_threshold = self.config["st"]
        self.max_children = self.config.get("max_children", 100)
        self.max_clusters = self.config.get("max_clusters", 50)
        
        self.root = LogNode()
        
        self.templates: Dict[str, LogTemplate] = {}
        self.template_counter = 0
        
        self.regex_patterns = [re.compile(p) for p in self.config.get("regex", [])]
        
        self.stats = {
            "total_logs_parsed": 0,
            "unique_templates_found": 0,
            "avg_tokens_per_log": 0
        }
    
    def parse_logs(self, log_df: pd.DataFrame) -> pd.DataFrame:
        """批量解析日志数据框"""
        print("\n" + "=" * 60)
        print("🔍 Step 2: Drain 日志解析")
        print("=" * 60)
        
        print(f"\n⚙️  Drain配置:")
        print(f"   • 前缀树深度: {self.depth}")
        print(f"   • 相似度阈值: {self.sim_threshold}")
        print(f"   • 最大子节点数: {self.max_children}")
        print(f"   • 最大聚类数: {self.max_clusters}")
        
        results = []
        
        total_logs = len(log_df)
        
        for idx, row in log_df.iterrows():
            raw_message = row['raw_message']
            
            parsed_result = self._parse_single_log(raw_message)
            
            result_entry = {
                **row.to_dict(),
                "template_id": parsed_result['template_id'],
                "template_str": parsed_result['template_str'],
                "parameters": parsed_result['parameters'],
                "token_count": len(parsed_result['tokens'])
            }
            
            results.append(result_entry)
            
            if (idx + 1) % 1000 == 0 or idx == total_logs - 1:
                progress = (idx + 1) / total_logs * 100
                print(f"\r   📝 处理进度: {idx+1:,}/{total_logs:,} ({progress:.1f}%)", end="", flush=True)
        
        print(f"\n\n✅ 日志解析完成!")
        
        result_df = pd.DataFrame(results)
        
        output_file = DATA_DIRS["parsed"] / "parsed_logs.csv"
        result_df.to_csv(output_file, index=False)
        
        template_summary = self._generate_template_summary()
        template_file = DATA_DIRS["parsed"] / "log_templates.json"
        with open(template_file, 'w', encoding='utf-8') as f:
            json.dump(template_summary, f, ensure_ascii=False, indent=2)
        
        self._print_statistics(result_df, template_summary)
        
        return result_df
    
    def _parse_single_log(self, raw_message: str) -> Dict:
        """解析单条日志"""
        tokens = self._tokenize(raw_message)
        
        matched_template_id, parameters = self._search_or_create(tokens, raw_message)
        
        if matched_template_id not in self.templates:
            self.template_counter += 1
            new_template = LogTemplate(
                template_id=f"TPL_{self.template_counter:04d}",
                template_str=" ".join(tokens),
                occurrence_count=1,
                parameters=parameters
            )
            self.templates[matched_template_id] = new_template
        else:
            self.templates[matched_template_id].occurrence_count += 1
        
        self.stats["total_logs_parsed"] += 1
        
        return {
            "template_id": matched_template_id,
            "template_str": " ".join(tokens),
            "parameters": parameters,
            "tokens": tokens
        }
    
    def _tokenize(self, message: str) -> List[str]:
        """将日志消息分词"""
        cleaned = re.sub(r'[\[\](){}]', '', message)
        tokens = cleaned.split()
        
        processed_tokens = []
        for token in tokens:
            if self._is_variable(token):
                processed_tokens.append("<*>")
            else:
                processed_tokens.append(token)
        
        return processed_tokens
    
    def _is_variable(self, token: str) -> bool:
        """判断是否为变量（动态部分）"""
        if not token or len(token) == 0:
            return False
        
        if len(token) <= 2 and not token.isdigit():
            return False
        
        if token.lower() in ['info', 'warn', 'error', 'debug', 'critical',
                            'get', 'post', 'put', 'delete', 'http', 'https']:
            return False
        
        variable_patterns = [
            r'^\d{13,}$',
            r'^\d+\.\d+$',
            r'^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$',
            r'^\d{4}[-/]\d{2}[-/]\d{2}$',
            r'^\d{2}:\d{2}:\d{2}$',
            r'^\d+ms$',
            r'^\d+s$',
            r'^\d+m$',
            r'^\d+[KBMG]$',
            r'^https?://[\w\.:/]+$', 
            r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$',
            r'^user_\d+$',
            r'^key-\d+$',
            r'^[a-fA-F0-9]{16,32}$'
        ]
        
        for pattern in variable_patterns:
            if re.match(pattern, token):
                return True
        
        if token.isdigit() and len(token) >= 3:
            return True
        
        return False
    
    def _search_or_create(self, tokens: List[str], original_message: str) -> Tuple[str, List[str]]:
        """在前缀树中搜索或创建模板"""
        num_tokens = len(tokens)
        
        level1_key = str(num_tokens)
        level1_node = self.root.get_child(level1_key)
        
        if not level1_node:
            level1_node = LogNode(token=level1_key)
            self.root.add_child(level1_node)
        
        depth_limit = min(self.depth - 1, num_tokens)
        
        if depth_limit <= 0:
            depth_limit = 1
        
        prefix_key = "_".join(tokens[:depth_limit])
        level2_node = level1_node.get_child(prefix_key)
        
        if not level2_node:
            level2_node = LogNode(token=prefix_key)
            level1_node.add_child(level2_node)
        
        best_match = self._find_best_match(level2_node, tokens)
        
        if best_match:
            template_str = best_match['template']
            parameters = self._extract_parameters(original_message, template_str)
            return (best_match['cluster_id'], parameters)
        else:
            new_cluster_id = f"C_{len(level2_node.template_clusters)}"
            new_template = {
                'cluster_id': new_cluster_id,
                'template': " ".join(tokens),
                'size': 1,
                'log_ids': [self.stats["total_logs_parsed"]]
            }
            level2_node.template_clusters.append(new_template)
            
            parameters = self._extract_parameters_from_tokens(tokens)
            return (new_cluster_id, parameters)
    
    def _find_best_match(self, node: LogNode, tokens: List[str]) -> Optional[Dict]:
        """在节点中查找最佳匹配的模板"""
        if not node.template_clusters:
            return None
        
        best_similarity = -1
        best_match = None
        
        for cluster in node.template_clusters:
            cluster_tokens = cluster['template'].split()
            
            similarity = self._calculate_similarity(tokens, cluster_tokens)
            
            if similarity > best_similarity and similarity >= self.sim_threshold:
                best_similarity = similarity
                best_match = cluster.copy()
                best_match['similarity'] = similarity
        
        if best_match:
            best_match['size'] += 1
        
        return best_match
    
    def _calculate_similarity(self, tokens1: List[str], tokens2: List[str]) -> float:
        """计算两个token序列的相似度"""
        if len(tokens1) != len(tokens2):
            return 0.0
        
        matches = sum(1 for t1, t2 in zip(tokens1, tokens2) 
                     if t1 == t2 or t1 == "<*>" or t2 == "<*>")
        
        return matches / len(tokens1) if tokens1 else 0.0
    
    def _extract_parameters(self, original_message: str, template_str: str) -> List[str]:
        """从原始消息中提取参数值"""
        parameters = []
        
        for pattern in self.regex_patterns:
            match = pattern.search(original_message)
            if match:
                try:
                    param_value = match.group()
                    parameters.append(param_value)
                except IndexError:
                    continue
        
        return parameters
    
    def _extract_parameters_from_tokens(self, tokens: List[str]) -> List[str]:
        """从token列表中提取参数"""
        parameters = []
        for i, token in enumerate(tokens):
            if token == "<*>":
                param_name = f"param_{i}"
                parameters.append(param_name)
        return parameters
    
    def _generate_template_summary(self) -> Dict:
        """生成模板摘要"""
        sorted_templates = sorted(
            self.templates.values(),
            key=lambda x: x.occurrence_count,
            reverse=True
        )
        
        summary = {
            "total_unique_templates": len(sorted_templates),
            "templates": [
                {
                    "id": tpl.template_id,
                    "template": tpl.template_str,
                    "count": tpl.occurrence_count,
                    "percentage": round(tpl.occurrence_count / max(self.stats["total_logs_parsed"], 1) * 100, 2),
                    "parameters": tpl.parameters
                }
                for tpl in sorted_templates[:50]
            ],
            "statistics": {
                "total_logs": self.stats["total_logs_parsed"],
                "unique_templates": len(sorted_templates),
                "coverage_ratio": round(len(sorted_templates) / max(self.stats["total_logs_parsed"], 1), 4)
            }
        }
        
        return summary
    
    def _print_statistics(self, parsed_df: pd.DataFrame, template_summary: Dict):
        """打印统计信息"""
        print(f"\n📊 Drain解析结果统计:")
        print(f"   总解析日志数: {len(parsed_df):,}")
        print(f"   发现唯一模板数: {template_summary['total_unique_templates']}")
        print(f"   平均每条日志Token数: {parsed_df['token_count'].mean():.1f}")
        
        print(f"\n🔝 Top 10 最频繁日志模板:")
        print("-" * 80)
        for i, tpl_info in enumerate(template_summary['templates'][:10], 1):
            template_preview = tpl_info['template'][:70] + "..." if len(tpl_info['template']) > 70 else tpl_info['template']
            print(f"{i:2d}. [{tpl_info['id']}] 出现次数: {tpl_info['count']:>5} ({tpl_info['percentage']:>5.1f}%)")
            print(f"     模板: {template_preview}")
        
        print(f"\n💾 解析结果已保存至: {DATA_DIRS['parsed']}")


def main():
    """主函数 - 用于测试"""
    from step1_log_generator import LogGenerator
    
    generator = LogGenerator()
    log_df = generator.generate_logs()
    
    parser = DrainParser()
    parsed_df = parser.parse_logs(log_df)
    
    return parsed_df


if __name__ == "__main__":
    main()
