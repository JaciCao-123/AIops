#!/usr/bin/env python3
"""
Step 2: Drain 日志解析
使用 Drain 算法将原始日志解析为结构化模板，
提取服务间调用关系和错误传播链路
"""
import json
import re
import os
import sys
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple


@dataclass
class LogEntry:
    timestamp: str
    level: str
    service: str
    trace_id: str
    span_id: str
    parent_span_id: str
    message: str


@dataclass
class ParsedTemplate:
    template_id: str
    template: str
    count: int = 0
    services: set = field(default_factory=set)
    levels: Counter = field(default_factory=Counter)
    sample_messages: List[str] = field(default_factory=list)


@dataclass
class ServiceCallEdge:
    source: str
    target: str
    trace_ids: set = field(default_factory=set)
    count: int = 0
    error_count: int = 0
    avg_latency_ms: float = 0.0


class SimpleDrainParser:
    """
    简化版 Drain 日志解析器
    
    将日志消息中的动态变量替换为通配符 <*>，
    提取日志模板（log template）
    """
    
    DYNAMIC_PATTERNS = [
        (r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '<IP>'),
        (r'\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', '<TIMESTAMP>'),
        (r'\bU\d{4,}\b', '<USER_ID>'),
        (r'\bORD-\d{8}-\d{4}\b', '<ORDER_ID>'),
        (r'\bPRD-\d{4}\b', '<PRODUCT_ID>'),
        (r'\bTXN-[A-F0-9]{8}\b', '<TXN_ID>'),
        (r'\bSES-[a-f0-9]{8}\b', '<SESSION_ID>'),
        (r'\bTX-\d{5,}\b', '<TXN_ID>'),
        (r'\b\d+ms\b', '<DURATION>'),
        (r'\b\d+\.?\d*%?\b', '<NUM>'),
        (r'\b0x[0-9a-fA-F]+\b', '<HEX>'),
        (r'/[\w/.-]+', '<PATH>'),
    ]
    
    def __init__(self, similarity_threshold: float = 0.5, max_children: int = 100):
        self.similarity_threshold = similarity_threshold
        self.max_children = max_children
        self._template_tree: Dict[int, List[ParsedTemplate]] = defaultdict(list)
        self._template_counter = 0
    
    def _tokenize(self, message: str) -> List[str]:
        tokens = message.split()
        return [t.strip(".,;:!?") for t in tokens if t.strip(".,;:!?")]
    
    def _replace_dynamic_vars(self, message: str) -> str:
        result = message
        for pattern, replacement in self.DYNAMIC_PATTERNS:
            result = re.sub(pattern, replacement, result)
        return result
    
    def _get_template(self, tokens: List[str]) -> str:
        template_tokens = []
        for token in tokens:
            is_dynamic = False
            for pattern, _ in self.DYNAMIC_PATTERNS:
                if re.fullmatch(pattern.replace(r'\b', '').replace(r'\\b', ''), token):
                    is_dynamic = True
                    break
            
            if re.match(r'^\d+\.?\d*%?$', token):
                is_dynamic = True
            elif re.match(r'^[0-9a-fA-F]{8,}$', token):
                is_dynamic = True
            elif re.match(r'^[A-Z]+-[0-9]+', token):
                is_dynamic = True
            
            template_tokens.append('<*>' if is_dynamic else token)
        
        return ' '.join(template_tokens)
    
    def _similarity(self, template1: str, template2: str) -> float:
        tokens1 = template1.split()
        tokens2 = template2.split()
        
        if len(tokens1) != len(tokens2):
            return 0.0
        
        match_count = 0
        for t1, t2 in zip(tokens1, tokens2):
            if t1 == t2:
                match_count += 1
            elif t1 == '<*>' and t2 == '<*>':
                match_count += 1
        
        return match_count / max(len(tokens1), 1)
    
    def parse(self, message: str) -> str:
        tokens = self._tokenize(message)
        if not tokens:
            return ""
        
        template = self._get_template(tokens)
        token_count = len(template.split())
        
        for existing in self._template_tree[token_count]:
            sim = self._similarity(template, existing.template)
            if sim >= self.similarity_threshold:
                return existing.template
        
        self._template_counter += 1
        new_template = ParsedTemplate(
            template_id=f"T{self._template_counter:04d}",
            template=template,
        )
        self._template_tree[token_count].append(new_template)
        
        return template
    
    def get_all_templates(self) -> List[ParsedTemplate]:
        templates = []
        for token_count, template_list in self._template_tree.items():
            templates.extend(template_list)
        return templates


class LogAnalyzer:
    """
    日志分析器
    
    1. 使用 Drain 解析日志模板
    2. 从 trace_id 链路中提取服务调用关系
    3. 从无 trace_id 日志中推断服务依赖
    """
    
    def __init__(self):
        self.drain = SimpleDrainParser(similarity_threshold=0.5)
        self._logs: List[LogEntry] = []
        self._templates: Dict[str, ParsedTemplate] = {}
        self._trace_groups: Dict[str, List[LogEntry]] = defaultdict(list)
        self._service_logs: Dict[str, List[LogEntry]] = defaultdict(list)
    
    def load_log_file(self, filepath: str) -> int:
        count = 0
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entry = LogEntry(
                        timestamp=data.get("timestamp", ""),
                        level=data.get("level", "INFO"),
                        service=data.get("service", "unknown"),
                        trace_id=data.get("trace_id", "-"),
                        span_id=data.get("span_id", "-"),
                        parent_span_id=data.get("parent_span_id", "-"),
                        message=data.get("message", ""),
                    )
                    self._logs.append(entry)
                    self._service_logs[entry.service].append(entry)
                    if entry.trace_id != "-":
                        self._trace_groups[entry.trace_id].append(entry)
                    count += 1
                except json.JSONDecodeError:
                    continue
        return count
    
    def parse_templates(self) -> Dict[str, ParsedTemplate]:
        for entry in self._logs:
            template_str = self.drain.parse(entry.message)
            
            if template_str not in self._templates:
                self._templates[template_str] = ParsedTemplate(
                    template_id=f"T{len(self._templates) + 1:04d}",
                    template=template_str,
                )
            
            t = self._templates[template_str]
            t.count += 1
            t.services.add(entry.service)
            t.levels[entry.level] += 1
            if len(t.sample_messages) < 3:
                t.sample_messages.append(entry.message)
        
        return self._templates
    
    def extract_call_edges_from_traces(self) -> List[ServiceCallEdge]:
        """
        从 trace_id 链路中提取服务调用关系
        通过 parent_span_id 推断调用链
        """
        edges: Dict[Tuple[str, str], ServiceCallEdge] = {}
        
        for trace_id, entries in self._trace_groups.items():
            if len(entries) < 2:
                continue
            
            span_to_service = {}
            for entry in entries:
                if entry.span_id != "-":
                    span_to_service[entry.span_id] = entry.service
            
            for entry in entries:
                if entry.parent_span_id != "-" and entry.parent_span_id in span_to_service:
                    parent_service = span_to_service[entry.parent_span_id]
                    child_service = entry.service
                    
                    if parent_service == child_service:
                        continue
                    
                    key = (parent_service, child_service)
                    if key not in edges:
                        edges[key] = ServiceCallEdge(
                            source=parent_service,
                            target=child_service,
                        )
                    
                    edges[key].trace_ids.add(trace_id)
                    edges[key].count += 1
                    if entry.level in ("ERROR", "WARN"):
                        edges[key].error_count += 1
        
        return list(edges.values())
    
    def extract_call_edges_from_templates(self) -> List[ServiceCallEdge]:
        """
        从日志模板中推断服务调用关系（无 trace_id 场景）
        
        策略：
        1. 日志中提到其他服务名 → 存在调用关系
        2. 错误传播模式：下游报错后上游也报错
        3. 时间窗口内同一 trace 的服务序列
        """
        KNOWN_SERVICES = set(self._service_logs.keys())
        edges: Dict[Tuple[str, str], ServiceCallEdge] = {}
        
        for service, entries in self._service_logs.items():
            for entry in entries:
                msg_lower = entry.message.lower()
                for known_svc in KNOWN_SERVICES:
                    if known_svc == service:
                        continue
                    svc_lower = known_svc.lower().replace("-", "").replace("_", "")
                    if svc_lower in msg_lower or known_svc in entry.message:
                        key = (service, known_svc)
                        if key not in edges:
                            edges[key] = ServiceCallEdge(
                                source=service,
                                target=known_svc,
                            )
                        edges[key].count += 1
                        if entry.level in ("ERROR", "WARN"):
                            edges[key].error_count += 1
        
        return list(edges.values())
    
    def extract_all_edges(self) -> List[ServiceCallEdge]:
        """
        合并 trace 和模板推断的调用关系
        """
        trace_edges = self.extract_call_edges_from_traces()
        template_edges = self.extract_call_edges_from_templates()
        
        merged: Dict[Tuple[str, str], ServiceCallEdge] = {}
        
        for edge in trace_edges:
            key = (edge.source, edge.target)
            merged[key] = edge
        
        for edge in template_edges:
            key = (edge.source, edge.target)
            if key in merged:
                merged[key].count += edge.count
                merged[key].error_count += edge.error_count
            else:
                merged[key] = edge
        
        return list(merged.values())
    
    def get_service_error_summary(self) -> Dict[str, Dict[str, Any]]:
        """
        获取每个服务的错误摘要
        """
        summary = {}
        for service, entries in self._service_logs.items():
            error_count = sum(1 for e in entries if e.level == "ERROR")
            warn_count = sum(1 for e in entries if e.level == "WARN")
            total = len(entries)
            
            error_templates = []
            for tmpl_str, tmpl in self._templates.items():
                if service in tmpl.services and tmpl.levels.get("ERROR", 0) > 0:
                    error_templates.append({
                        "template": tmpl.template,
                        "error_count": tmpl.levels.get("ERROR", 0),
                    })
            
            summary[service] = {
                "total_logs": total,
                "error_count": error_count,
                "warn_count": warn_count,
                "error_rate": round(error_count / max(total, 1) * 100, 2),
                "error_templates": sorted(error_templates, key=lambda x: -x["error_count"])[:5],
            }
        
        return summary


def parse_logs(input_dir: str = None, output_dir: str = None) -> Dict[str, str]:
    """
    执行完整的日志解析流程
    """
    if input_dir is None:
        input_dir = str(Path(__file__).parent / "data" / "raw")
    if output_dir is None:
        output_dir = str(Path(__file__).parent / "data" / "parsed")
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    analyzer = LogAnalyzer()
    
    log_files = list(Path(input_dir).glob("*.log"))
    total_logs = 0
    for log_file in log_files:
        count = analyzer.load_log_file(str(log_file))
        total_logs += count
        print(f"  加载: {log_file.name} ({count} 条)")
    
    print(f"\n共加载 {total_logs} 条日志")
    
    # 1. 模板解析
    print("\n[1/3] Drain 模板解析...")
    templates = analyzer.parse_templates()
    print(f"  提取到 {len(templates)} 个日志模板")
    
    templates_file = output_path / "templates.json"
    templates_data = {}
    for tmpl_str, tmpl in templates.items():
        templates_data[tmpl.template_id] = {
            "template": tmpl.template,
            "count": tmpl.count,
            "services": list(tmpl.services),
            "levels": dict(tmpl.levels),
            "sample_messages": tmpl.sample_messages[:3],
        }
    with open(templates_file, "w", encoding="utf-8") as f:
        json.dump(templates_data, f, ensure_ascii=False, indent=2)
    print(f"  模板保存到: {templates_file}")
    
    # 2. 调用关系提取
    print("\n[2/3] 调用关系提取...")
    edges = analyzer.extract_all_edges()
    print(f"  提取到 {len(edges)} 条服务调用关系")
    
    edges_file = output_path / "call_edges.json"
    edges_data = []
    for edge in edges:
        edges_data.append({
            "source": edge.source,
            "target": edge.target,
            "call_count": edge.count,
            "error_count": edge.error_count,
            "trace_count": len(edge.trace_ids),
        })
    with open(edges_file, "w", encoding="utf-8") as f:
        json.dump(edges_data, f, ensure_ascii=False, indent=2)
    print(f"  调用关系保存到: {edges_file}")
    
    # 3. 错误摘要
    print("\n[3/3] 服务错误摘要...")
    error_summary = analyzer.get_service_error_summary()
    
    summary_file = output_path / "error_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(error_summary, f, ensure_ascii=False, indent=2)
    print(f"  错误摘要保存到: {summary_file}")
    
    return {
        "templates": str(templates_file),
        "edges": str(edges_file),
        "error_summary": str(summary_file),
    }


if __name__ == "__main__":
    parse_logs()
