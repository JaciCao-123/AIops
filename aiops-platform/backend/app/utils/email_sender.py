import os
import smtplib
import json
import uuid
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

from ..core.config import settings


class ApprovalManager:
    """
    审批管理器
    管理待审批的操作和邮件回复
    """
    
    def __init__(self, data_dir: str = "data/approvals"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.pending_approvals: Dict[str, Dict] = {}
        self._load_pending_approvals()
    
    def _load_pending_approvals(self):
        """
        加载待审批的操作
        """
        for filepath in self.data_dir.glob("*.json"):
            with open(filepath, 'r', encoding='utf-8') as f:
                approval = json.load(f)
                if approval.get("status") == "pending":
                    self.pending_approvals[approval["approval_id"]] = approval
    
    def create_approval(
        self,
        operation: str,
        risk: str,
        impact: str,
        commands: List[str],
        target_host: str,
        email: str
    ) -> str:
        """
        创建待审批的操作
        """
        approval_id = str(uuid.uuid4())[:8]
        approval = {
            "approval_id": approval_id,
            "operation": operation,
            "risk": risk,
            "impact": impact,
            "commands": commands,
            "target_host": target_host,
            "email": email,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "approved_at": None,
            "approved_by": None
        }
        
        self.pending_approvals[approval_id] = approval
        
        filepath = self.data_dir / f"{approval_id}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(approval, f, ensure_ascii=False, indent=2)
        
        return approval_id
    
    def approve(self, approval_id: str, approved_by: str = "email") -> Optional[Dict]:
        """
        批准操作
        """
        if approval_id not in self.pending_approvals:
            return None
        
        approval = self.pending_approvals[approval_id]
        approval["status"] = "approved"
        approval["approved_at"] = datetime.now().isoformat()
        approval["approved_by"] = approved_by
        
        filepath = self.data_dir / f"{approval_id}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(approval, f, ensure_ascii=False, indent=2)
        
        del self.pending_approvals[approval_id]
        
        return approval
    
    def reject(self, approval_id: str, reason: str = "") -> Optional[Dict]:
        """
        拒绝操作
        """
        if approval_id not in self.pending_approvals:
            return None
        
        approval = self.pending_approvals[approval_id]
        approval["status"] = "rejected"
        approval["rejected_at"] = datetime.now().isoformat()
        approval["reject_reason"] = reason
        
        filepath = self.data_dir / f"{approval_id}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(approval, f, ensure_ascii=False, indent=2)
        
        del self.pending_approvals[approval_id]
        
        return approval
    
    def get_approval(self, approval_id: str) -> Optional[Dict]:
        """
        获取审批信息
        """
        if approval_id in self.pending_approvals:
            return self.pending_approvals[approval_id]
        
        filepath = self.data_dir / f"{approval_id}.json"
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        return None


class EmailSender:
    """
    邮件发送工具
    用于发送操作建议和审批请求
    """
    
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM_EMAIL or settings.SMTP_USER
        self.approval_manager = ApprovalManager()
    
    def _create_approval_email(
        self,
        to_email: str,
        operation: str,
        risk: str,
        impact: str,
        commands: List[str],
        target_host: str,
        approval_id: str
    ) -> MIMEMultipart:
        """
        创建审批请求邮件
        """
        msg = MIMEMultipart("alternative")
        msg["From"] = self.from_email
        msg["To"] = to_email
        msg["Subject"] = f"[AIOps] 操作审批请求 - {operation}"
        
        text_content = f"""
AIOps 智能运维平台 - 操作审批请求

尊敬的管理员：

系统检测到需要人工审批的操作，请确认是否执行。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 操作详情

操作类型: {operation}
目标服务器: {target_host}
风险等级: {risk}
影响范围: {impact}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔧 执行命令

{chr(10).join(f'{i+1}. {cmd}' for i, cmd in enumerate(commands))}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 审批方式

审批ID: {approval_id}

请回复此邮件，内容包含以下任一关键词：
- APPROVE 或 批准 或 同意 - 批准执行
- REJECT 或 拒绝 或 不同意 - 拒绝执行

例如回复: "APPROVE {approval_id}" 或 "批准执行"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ 发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

此邮件由 AIOps 智能运维平台自动发送，请勿直接回复。
"""
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9f9f9; padding: 20px; border: 1px solid #eee; }}
        .info-box {{ background: white; border-radius: 8px; padding: 15px; margin: 10px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .risk-high {{ background: #fff2f0; border-left: 4px solid #ff4d4f; }}
        .risk-medium {{ background: #fffbe6; border-left: 4px solid #faad14; }}
        .risk-low {{ background: #f6ffed; border-left: 4px solid #52c41a; }}
        .command {{ background: #282c34; color: #abb2bf; padding: 10px; border-radius: 4px; font-family: 'Monaco', 'Menlo', monospace; font-size: 13px; margin: 5px 0; }}
        .approval-id {{ font-size: 24px; font-weight: bold; color: #667eea; }}
        .footer {{ text-align: center; color: #999; font-size: 12px; padding: 20px; }}
        .btn {{ display: inline-block; padding: 10px 20px; margin: 5px; border-radius: 4px; text-decoration: none; color: white; }}
        .btn-approve {{ background: #52c41a; }}
        .btn-reject {{ background: #ff4d4f; }}
    </style>
</head>
<body>
    <div class="header">
        <h1 style="margin: 0;">🤖 AIOps 智能运维平台</h1>
        <p style="margin: 5px 0 0 0;">操作审批请求</p>
    </div>
    
    <div class="content">
        <p>尊敬的管理员：</p>
        <p>系统检测到需要人工审批的操作，请确认是否执行。</p>
        
        <div class="info-box risk-{risk.lower()}">
            <h3 style="margin-top: 0;">📋 操作详情</h3>
            <table style="width: 100%;">
                <tr><td style="width: 100px; color: #666;">操作类型:</td><td><strong>{operation}</strong></td></tr>
                <tr><td style="color: #666;">目标服务器:</td><td><code>{target_host}</code></td></tr>
                <tr><td style="color: #666;">风险等级:</td><td><strong style="color: {'#ff4d4f' if risk == 'high' else '#faad14' if risk == 'medium' else '#52c41a'}">{risk.upper()}</strong></td></tr>
                <tr><td style="color: #666;">影响范围:</td><td>{impact}</td></tr>
            </table>
        </div>
        
        <div class="info-box">
            <h3 style="margin-top: 0;">🔧 执行命令</h3>
            {chr(10).join(f'<div class="command">{cmd}</div>' for cmd in commands)}
        </div>
        
        <div class="info-box" style="text-align: center;">
            <h3 style="margin-top: 0;">✅ 审批方式</h3>
            <p>审批ID: <span class="approval-id">{approval_id}</span></p>
            <p style="color: #666; font-size: 14px;">请回复此邮件，内容包含以下任一关键词：</p>
            <p>
                <code style="background: #f6ffed; padding: 5px 10px; border-radius: 4px;">APPROVE {approval_id}</code>
                或
                <code style="background: #fff2f0; padding: 5px 10px; border-radius: 4px;">REJECT {approval_id}</code>
            </p>
        </div>
    </div>
    
    <div class="footer">
        <p>⏰ 发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>此邮件由 AIOps 智能运维平台自动发送</p>
    </div>
</body>
</html>
"""
        
        part1 = MIMEText(text_content, "plain", "utf-8")
        part2 = MIMEText(html_content, "html", "utf-8")
        
        msg.attach(part1)
        msg.attach(part2)
        
        return msg
    
    async def send_approval_request(
        self,
        to_email: str,
        operation: str,
        risk: str,
        impact: str,
        commands: List[str],
        target_host: str
    ) -> Dict[str, Any]:
        """
        发送审批请求邮件
        """
        if not self.smtp_user or not self.smtp_password:
            return {
                "success": False,
                "error": "SMTP 配置不完整，请设置 SMTP_USER 和 SMTP_PASSWORD 环境变量"
            }
        
        approval_id = self.approval_manager.create_approval(
            operation=operation,
            risk=risk,
            impact=impact,
            commands=commands,
            target_host=target_host,
            email=to_email
        )
        
        msg = self._create_approval_email(
            to_email=to_email,
            operation=operation,
            risk=risk,
            impact=impact,
            commands=commands,
            target_host=target_host,
            approval_id=approval_id
        )
        
        try:
            import ssl
            context = ssl.create_default_context()
            
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context) as server:
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_email, [to_email], msg.as_string())
            
            return {
                "success": True,
                "approval_id": approval_id,
                "to_email": to_email,
                "operation": operation,
                "message": f"审批请求已发送至 {to_email}，审批ID: {approval_id}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "approval_id": approval_id
            }
    
    async def check_approval(self, approval_id: str) -> Dict[str, Any]:
        """
        检查审批状态
        """
        approval = self.approval_manager.get_approval(approval_id)
        
        if not approval:
            return {
                "success": False,
                "error": f"未找到审批ID: {approval_id}"
            }
        
        return {
            "success": True,
            "approval": approval,
            "status": approval.get("status")
        }
    
    async def wait_for_approval(
        self,
        approval_id: str,
        timeout_seconds: int = 3600,
        poll_interval: int = 30
    ) -> Dict[str, Any]:
        """
        等待审批结果
        """
        start_time = datetime.now()
        
        while (datetime.now() - start_time).total_seconds() < timeout_seconds:
            approval = self.approval_manager.get_approval(approval_id)
            
            if not approval:
                return {
                    "success": False,
                    "error": "审批记录不存在"
                }
            
            status = approval.get("status")
            
            if status == "approved":
                return {
                    "success": True,
                    "approved": True,
                    "approval": approval
                }
            
            if status == "rejected":
                return {
                    "success": True,
                    "approved": False,
                    "approval": approval
                }
            
            await asyncio.sleep(poll_interval)
        
        return {
            "success": False,
            "error": "等待审批超时",
            "approval_id": approval_id
        }


email_sender = EmailSender()
