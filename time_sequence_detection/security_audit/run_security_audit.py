import os
import sys
import shutil
import subprocess
from typing import List, Tuple
from pathlib import Path

from base.config import config
from base.logger import get_logger


class SecurityAuditRunner:
    def __init__(self):
        self.logger = get_logger("SecurityAuditRunner")
        self.base_dir = Path(__file__).parent
        self.timeout = 600
    
    def run(self) -> bool:
        self.logger.info("=" * 60)
        self.logger.info("开始执行完整的安全与合规性审计流程")
        self.logger.info("=" * 60)
        
        if not self._clean_events_dir():
            return False
        
        detectors = [
            ("身份认证检测器", self.base_dir / "auth_logs" / "detector.py"),
            ("云平台日志检测器", self.base_dir / "cloud_logs" / "detector.py"),
            ("应用/服务器日志检测器", self.base_dir / "app_server_logs" / "detector.py"),
            ("堡垒机/SSH日志检测器", self.base_dir / "ssh_logs" / "detector.py"),
        ]
        
        failed_detectors = []
        
        for name, script_path in detectors:
            if not self._run_detector(name, script_path):
                failed_detectors.append(name)
                self.logger.warning(f"{name} 执行失败，继续执行其他检测器...")
        
        if failed_detectors:
            self.logger.warning(f"以下检测器执行失败: {', '.join(failed_detectors)}")
        
        if not self._run_correlation_engine():
            self.logger.error("关联引擎执行失败")
            return False
        
        self.logger.info("=" * 60)
        self.logger.info("安全与合规性审计流程执行完毕")
        self.logger.info("=" * 60)
        return True
    
    def _clean_events_dir(self) -> bool:
        events_dir = self.base_dir / "correlation_engine" / "events"
        
        if events_dir.exists():
            try:
                shutil.rmtree(events_dir)
                self.logger.info(f"已清理旧的告警事件目录: {events_dir}")
            except Exception as e:
                self.logger.error(f"清理事件目录失败: {e}")
                return False
        
        return True
    
    def _run_detector(self, name: str, script_path: Path) -> bool:
        self.logger.info("=" * 60)
        self.logger.info(f"正在执行: {name}")
        self.logger.info("=" * 60)
        
        if not script_path.exists():
            self.logger.error(f"脚本不存在: {script_path}")
            return False
        
        return self._execute_script(script_path)
    
    def _run_correlation_engine(self) -> bool:
        self.logger.info("=" * 60)
        self.logger.info("正在执行中央关联引擎")
        self.logger.info("=" * 60)
        
        script_path = self.base_dir / "correlation_engine" / "engine.py"
        
        if not script_path.exists():
            self.logger.error(f"关联引擎脚本不存在: {script_path}")
            return False
        
        return self._execute_script(script_path)
    
    def _execute_script(self, script_path: Path) -> bool:
        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=script_path.parent
            )
            
            if result.stdout:
                print(result.stdout)
            
            if result.returncode != 0:
                self.logger.error(f"脚本执行失败: {script_path}")
                if result.stderr:
                    self.logger.error(f"错误输出: {result.stderr}")
                return False
            
            return True
            
        except subprocess.TimeoutExpired:
            self.logger.error(f"脚本执行超时 ({self.timeout}秒): {script_path}")
            return False
        except Exception as e:
            self.logger.exception(f"执行脚本异常: {e}")
            return False


def main() -> int:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    runner = SecurityAuditRunner()
    success = runner.run()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
