import os
import json
from datetime import datetime
from typing import Dict, Any, Optional


class IntermediateFileManager:
    """
    中间文件管理器
    负责存储和管理所有中间文件（ansible yaml、output 等）
    """
    
    def __init__(self, base_dir: str = "data"):
        self.base_dir = base_dir
        self.diagnosis_dir = os.path.join(base_dir, "diagnosis")
        self.playbooks_dir = os.path.join(base_dir, "playbooks")
        self.outputs_dir = os.path.join(base_dir, "outputs")
        self.logs_dir = os.path.join(base_dir, "logs")
        
        self._ensure_directories()
    
    def _ensure_directories(self):
        """
        确保所有必要的目录都存在
        """
        for directory in [self.diagnosis_dir, self.playbooks_dir, self.outputs_dir, self.logs_dir]:
            os.makedirs(directory, exist_ok=True)
    
    def _generate_filename(self, prefix: str, extension: str = "json") -> str:
        """
        生成带时间戳的文件名
        
        Args:
            prefix: 文件名前缀
            extension: 文件扩展名
            
        Returns:
            文件名
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_{timestamp}.{extension}"
    
    def save_diagnosis_plan(
        self,
        diagnosis_plan: Dict[str, Any],
        query_id: Optional[str] = None
    ) -> str:
        """
        保存诊断计划
        
        Args:
            diagnosis_plan: 诊断计划
            query_id: 查询 ID
            
        Returns:
            文件路径
        """
        if query_id:
            filename = f"diagnosis_plan_{query_id}.json"
        else:
            filename = self._generate_filename("diagnosis_plan")
        
        filepath = os.path.join(self.diagnosis_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(diagnosis_plan, f, ensure_ascii=False, indent=2)
        
        return filepath
    
    def save_playbook(
        self,
        playbook: Dict[str, Any],
        target_host: str,
        query_id: Optional[str] = None
    ) -> str:
        """
        保存 Ansible Playbook
        
        Args:
            playbook: Playbook 内容
            target_host: 目标主机
            query_id: 查询 ID
            
        Returns:
            文件路径
        """
        if query_id:
            filename = f"playbook_{target_host}_{query_id}.yaml"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"playbook_{target_host}_{timestamp}.yaml"
        
        filepath = os.path.join(self.playbooks_dir, filename)
        
        import yaml
        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(playbook, f, allow_unicode=True, default_flow_style=False)
        
        return filepath
    
    def save_execution_output(
        self,
        output: str,
        target_host: str,
        query_id: Optional[str] = None
    ) -> str:
        """
        保存执行输出
        
        Args:
            output: 执行输出
            target_host: 目标主机
            query_id: 查询 ID
            
        Returns:
            文件路径
        """
        if query_id:
            filename = f"output_{target_host}_{query_id}.txt"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"output_{target_host}_{timestamp}.txt"
        
        filepath = os.path.join(self.outputs_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(output)
        
        return filepath
    
    def save_full_result(
        self,
        result: Dict[str, Any],
        query_id: Optional[str] = None
    ) -> str:
        """
        保存完整的处理结果
        
        Args:
            result: 完整结果
            query_id: 查询 ID
            
        Returns:
            文件路径
        """
        if query_id:
            filename = f"full_result_{query_id}.json"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"full_result_{timestamp}.json"
        
        filepath = os.path.join(self.logs_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        return filepath
    
    def load_diagnosis_plan(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        加载诊断计划
        
        Args:
            filename: 文件名
            
        Returns:
            诊断计划
        """
        filepath = os.path.join(self.diagnosis_dir, filename)
        
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        return None
    
    def list_diagnosis_plans(self) -> list:
        """
        列出所有诊断计划文件
        
        Returns:
            文件列表
        """
        if not os.path.exists(self.diagnosis_dir):
            return []
        
        return [f for f in os.listdir(self.diagnosis_dir) if f.endswith('.json')]
    
    def list_playbooks(self) -> list:
        """
        列出所有 Playbook 文件
        
        Returns:
            文件列表
        """
        if not os.path.exists(self.playbooks_dir):
            return []
        
        return [f for f in os.listdir(self.playbooks_dir) if f.endswith('.yaml')]
    
    def list_outputs(self) -> list:
        """
        列出所有输出文件
        
        Returns:
            文件列表
        """
        if not os.path.exists(self.outputs_dir):
            return []
        
        return [f for f in os.listdir(self.outputs_dir) if f.endswith('.txt')]
