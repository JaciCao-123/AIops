import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
from pathlib import Path
from bisect import bisect_left, bisect_right

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from base.config import config
from base.logger import get_logger


class CorrelationEngine:
    def __init__(self, events_dir: Optional[str] = None):
        self.logger = get_logger("CorrelationEngine")
        
        if events_dir is None:
            base_dir = Path(__file__).parent
            events_dir = base_dir / "events"
        
        self.events_dir = Path(events_dir)
        self.time_window_minutes = config.correlation.get("time_window_minutes", 15)
        self.severity_threshold = config.correlation.get("severity_threshold", "HIGH")
        self.rules = config.correlation.get("rules", [])
    
    def run(self) -> List[Dict[str, Any]]:
        self.logger.info("=" * 60)
        self.logger.info("中央关联引擎 - 开始运行")
        self.logger.info("=" * 60)
        
        events = self._load_all_events()
        
        if not events:
            self.logger.info("未发现任何初步告警事件")
            self.logger.info("=" * 60)
            self.logger.info("中央关联引擎 - 运行结束")
            self.logger.info("=" * 60)
            return []
        
        self.logger.info(f"已加载 {len(events)} 个初步告警事件")
        
        events_by_type = self._group_events_by_type(events)
        self.logger.info(f"事件类型分布: {dict((k, len(v)) for k, v in events_by_type.items())}")
        
        incidents = self._apply_correlation_rules(events, events_by_type)
        
        if not incidents:
            self.logger.info("未发现满足关联规则的高级攻击事件")
        else:
            self.logger.warning(f"发现 {len(incidents)} 个关联攻击事件")
        
        self.logger.info("=" * 60)
        self.logger.info("中央关联引擎 - 运行结束")
        self.logger.info("=" * 60)
        return incidents
    
    def _load_all_events(self) -> List[Dict[str, Any]]:
        events = []
        
        if not self.events_dir.exists():
            self.logger.warning(f"事件目录不存在: {self.events_dir}")
            return events
        
        for filename in sorted(self.events_dir.iterdir()):
            if filename.suffix == ".json":
                event = self._load_event_safely(filename)
                if event:
                    events.append(event)
        
        return events
    
    def _load_event_safely(self, filepath: Path) -> Optional[Dict[str, Any]]:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                event = json.load(f)
            
            if not isinstance(event, dict):
                self.logger.warning(f"无效事件格式: {filepath}")
                return None
            
            required_fields = ['alert_type', 'timestamp', 'severity']
            for field in required_fields:
                if field not in event:
                    self.logger.warning(f"事件缺少必需字段 {field}: {filepath}")
                    return None
            
            if isinstance(event['timestamp'], str):
                event['timestamp'] = datetime.fromisoformat(event['timestamp'])
            
            return event
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON 解析错误 {filepath}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"加载事件失败 {filepath}: {e}")
            return None
    
    def _group_events_by_type(self, events: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        grouped = defaultdict(list)
        for event in events:
            alert_type = event.get('alert_type', 'unknown')
            grouped[alert_type].append(event)
        return grouped
    
    def _apply_correlation_rules(
        self, 
        events: List[Dict[str, Any]], 
        events_by_type: Dict[str, List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        incidents = []
        
        incidents.extend(self._rule_coordinated_attack(events_by_type))
        incidents.extend(self._rule_cloud_breach(events_by_type))
        incidents.extend(self._rule_multi_vector_attack(events, events_by_type))
        incidents.extend(self._rule_lateral_movement(events_by_type))
        
        return incidents
    
    def _rule_coordinated_attack(self, events_by_type: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        incidents = []
        
        ssh_alerts = events_by_type.get('SSH_BruteForce_Detected', [])
        auth_alerts = events_by_type.get('Auth_CredentialStuffing_Detected', [])
        
        if not ssh_alerts or not auth_alerts:
            return incidents
        
        correlated = self._find_time_correlated_events(ssh_alerts, auth_alerts)
        
        for ssh_alert, auth_alert in correlated:
            incident = self._create_incident(
                incident_type="Coordinated_Attack_Detected",
                severity="CRITICAL",
                summary="检测到协同攻击：系统同时遭受SSH暴力破解和身份认证撞库攻击",
                events=[ssh_alert, auth_alert],
                recommendations=[
                    "立即封锁攻击源IP",
                    "强制重置目标用户密码",
                    "检查是否有账户已被入侵",
                    "加强认证系统的防护措施",
                    "启用多因素认证(MFA)"
                ]
            )
            incidents.append(incident)
            self._log_incident(incident)
        
        return incidents
    
    def _rule_cloud_breach(self, events_by_type: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        incidents = []
        
        cloud_alerts = events_by_type.get('Cloud_Anomaly_Detected', [])
        app_alerts = events_by_type.get('AppServer_ErrorSpike_Detected', [])
        
        if not cloud_alerts or not app_alerts:
            return incidents
        
        correlated = self._find_time_correlated_events(cloud_alerts, app_alerts)
        
        for cloud_alert, app_alert in correlated:
            cloud_entities = cloud_alert.get('entities', {})
            app_entities = app_alert.get('entities', {})
            
            incident = self._create_incident(
                incident_type="Cloud_Breach_Detected",
                severity="HIGH",
                summary=f"检测到云平台异常访问与应用错误激增的关联，可能存在云资源被攻击",
                events=[cloud_alert, app_alert],
                recommendations=[
                    "检查云平台IAM权限配置",
                    "审计云资源操作日志",
                    f"检查服务 {app_entities.get('service', 'unknown')} 的配置和依赖",
                    "评估是否需要隔离受影响的云资源"
                ],
                additional_info={
                    "cloud_user": cloud_entities.get('user'),
                    "affected_service": app_entities.get('service'),
                    "cloud_source_ip": cloud_entities.get('source_ip')
                }
            )
            incidents.append(incident)
            self._log_incident(incident)
        
        return incidents
    
    def _rule_multi_vector_attack(
        self, 
        events: List[Dict[str, Any]], 
        events_by_type: Dict[str, List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        incidents = []
        
        if len(events_by_type) < 3:
            return incidents
        
        time_clusters = self._cluster_events_by_time(events)
        
        for cluster in time_clusters:
            unique_types = set(e['alert_type'] for e in cluster)
            
            if len(unique_types) >= 3:
                incident = self._create_incident(
                    incident_type="Multi_Vector_Attack_Detected",
                    severity="CRITICAL",
                    summary=f"检测到多向量攻击：{len(unique_types)} 个系统同时出现异常",
                    events=cluster,
                    recommendations=[
                        "立即启动应急响应流程",
                        "隔离受影响的系统和网络",
                        "通知安全团队和管理层",
                        "收集并保全攻击证据",
                        "检查是否存在数据泄露"
                    ],
                    additional_info={
                        "attack_vectors": list(unique_types),
                        "total_events": len(cluster)
                    }
                )
                incidents.append(incident)
                self._log_incident(incident)
        
        return incidents
    
    def _rule_lateral_movement(self, events_by_type: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        incidents = []
        
        ssh_alerts = events_by_type.get('SSH_BruteForce_Detected', [])
        app_alerts = events_by_type.get('AppServer_ErrorSpike_Detected', [])
        
        if not ssh_alerts or not app_alerts:
            return incidents
        
        correlated = self._find_time_correlated_events(ssh_alerts, app_alerts)
        
        for ssh_alert, app_alert in correlated:
            ssh_entities = ssh_alert.get('entities', {})
            app_entities = app_alert.get('entities', {})
            
            ssh_host = ssh_entities.get('target_host', '')
            app_service = app_entities.get('service', '')
            
            if ssh_host and app_service:
                incident = self._create_incident(
                    incident_type="Lateral_Movement_Detected",
                    severity="HIGH",
                    summary=f"检测到横向移动迹象：SSH攻击后应用服务异常",
                    events=[ssh_alert, app_alert],
                    recommendations=[
                        "检查SSH登录后的操作记录",
                        "审计应用服务的访问日志",
                        "检查是否存在权限提升",
                        "隔离可疑账户和主机"
                    ],
                    additional_info={
                        "entry_point": ssh_host,
                        "target_service": app_service,
                        "attacker_ip": ssh_entities.get('source_ip')
                    }
                )
                incidents.append(incident)
                self._log_incident(incident)
        
        return incidents
    
    def _find_time_correlated_events(
        self, 
        events_a: List[Dict[str, Any]], 
        events_b: List[Dict[str, Any]]
    ) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
        if not events_a or not events_b:
            return []
        
        window = timedelta(minutes=self.time_window_minutes)
        
        events_b_sorted = sorted(events_b, key=lambda x: x['timestamp'])
        timestamps_b = [e['timestamp'] for e in events_b_sorted]
        
        correlated = []
        
        for event_a in events_a:
            time_a = event_a['timestamp']
            window_start = time_a - window
            window_end = time_a + window
            
            left_idx = bisect_left(timestamps_b, window_start)
            right_idx = bisect_right(timestamps_b, window_end)
            
            for idx in range(left_idx, right_idx):
                correlated.append((event_a, events_b_sorted[idx]))
        
        return correlated
    
    def _cluster_events_by_time(self, events: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        if not events:
            return []
        
        sorted_events = sorted(events, key=lambda x: x['timestamp'])
        window = timedelta(minutes=self.time_window_minutes)
        
        clusters = []
        current_cluster = [sorted_events[0]]
        
        for event in sorted_events[1:]:
            if event['timestamp'] - current_cluster[-1]['timestamp'] <= window:
                current_cluster.append(event)
            else:
                if len(current_cluster) >= 2:
                    clusters.append(current_cluster)
                current_cluster = [event]
        
        if len(current_cluster) >= 2:
            clusters.append(current_cluster)
        
        return clusters
    
    def _create_incident(
        self, 
        incident_type: str, 
        severity: str, 
        summary: str, 
        events: List[Dict[str, Any]],
        recommendations: List[str],
        additional_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        timestamps = [e['timestamp'] for e in events]
        start_time = min(timestamps)
        end_time = max(timestamps)
        
        events_serializable = []
        for e in events:
            e_copy = e.copy()
            if isinstance(e_copy.get('timestamp'), datetime):
                e_copy['timestamp'] = e_copy['timestamp'].isoformat()
            events_serializable.append(e_copy)
        
        incident = {
            "incident_type": incident_type,
            "severity": severity,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "summary": summary,
            "correlated_events": events_serializable,
            "recommendations": recommendations,
            "created_at": datetime.now().isoformat()
        }
        
        if additional_info:
            incident["additional_info"] = additional_info
        
        return incident
    
    def _log_incident(self, incident: Dict[str, Any]) -> None:
        self.logger.critical("=" * 60)
        self.logger.critical(f"🚨 [{incident['severity']}] {incident['incident_type']}")
        self.logger.critical(f"时间范围: {incident['start_time']} - {incident['end_time']}")
        self.logger.critical(f"摘要: {incident['summary']}")
        self.logger.critical(f"关联事件数: {len(incident['correlated_events'])}")
        self.logger.critical("=" * 60)


def run_correlation_engine(events_dir: str = "events") -> List[Dict[str, Any]]:
    engine = CorrelationEngine(events_dir)
    return engine.run()


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)
    incidents = run_correlation_engine()
    
    if incidents:
        output_path = Path(base_dir) / "incidents.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(incidents, f, indent=4, ensure_ascii=False, default=str)
        print(f"\n关联事件已保存至: {output_path}")
