#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阿里云 SLB 远程诊断脚本 (Python SDK 版本)
用于排查 SLB 实例的服务状态
生成时间: 2026-04-06
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path

def load_env_file():
    """
    自动加载 .env 文件中的环境变量
    支持多种 .env 文件位置
    """
    env_paths = [
        Path(__file__).parent.parent.parent.parent / '.env',
        Path.cwd() / '.env',
        Path.home() / '.env',
    ]
    
    for env_path in env_paths:
        if env_path.exists():
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        if key and value and key not in os.environ:
                            os.environ[key] = value
            break

load_env_file()

try:
    from aliyunsdkcore.client import AcsClient
    from aliyunsdkcore.acs_exception.exceptions import ServerException, ClientException
    from aliyunsdkslb.request.v20140515.DescribeLoadBalancerAttributeRequest import DescribeLoadBalancerAttributeRequest
    from aliyunsdkslb.request.v20140515.DescribeHealthStatusRequest import DescribeHealthStatusRequest
    from aliyunsdkslb.request.v20140515.DescribeLoadBalancerListenersRequest import DescribeLoadBalancerListenersRequest
    from aliyunsdkecs.request.v20140526.DescribeInstanceAttributeRequest import DescribeInstanceAttributeRequest
    from aliyunsdkecs.request.v20140526.DescribeSecurityGroupAttributeRequest import DescribeSecurityGroupAttributeRequest
except ImportError as e:
    print(f"错误: 缺少必要的 Python 包: {e}")
    print("请安装: pip install aliyun-python-sdk-core aliyun-python-sdk-ecs aliyun-python-sdk-slb")
    sys.exit(1)


class SLBDiagnosis:
    def __init__(self, load_balancer_id, region='cn-hangzhou'):
        self.load_balancer_id = load_balancer_id
        self.region = region
        self.client = None
        self.output_dir = "/Users/jaci-j/AIops/aiops-platform/backend/data/diagnosis"
        self.output_file = None
        
        os.makedirs(self.output_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.output_file = os.path.join(self.output_dir, f"slb_diagnosis_{timestamp}.txt")
        
    def log(self, message):
        print(message)
        with open(self.output_file, 'a', encoding='utf-8') as f:
            f.write(message + '\n')
    
    def check_cli_environment(self):
        self.log("\n=== Step 1: 检查阿里云 SDK 环境 ===")
        
        access_key = os.environ.get('ALICLOUD_ACCESS_KEY') or os.environ.get('ALIYUN_ACCESS_KEY_ID')
        secret_key = os.environ.get('ALICLOUD_SECRET_KEY') or os.environ.get('ALIYUN_ACCESS_KEY_SECRET')
        
        if not access_key or not secret_key:
            self.log("✗ 未找到阿里云认证信息")
            self.log("\n请设置环境变量:")
            self.log("  export ALICLOUD_ACCESS_KEY='your-access-key-id'")
            self.log("  export ALICLOUD_SECRET_KEY='your-access-key-secret'")
            self.log("  export ALICLOUD_REGION='cn-hangzhou'")
            self.log("\n或创建配置文件 ~/.aliyun/config.json")
            return False
        
        try:
            self.client = AcsClient(access_key, secret_key, self.region)
            self.log("✓ 阿里云 SDK 初始化成功")
            
            try:
                from aliyunsdksts.request.v20150401.GetCallerIdentityRequest import GetCallerIdentityRequest
                request = GetCallerIdentityRequest()
                response = self.client.do_action_with_exception(request)
                identity = json.loads(response.decode('utf-8'))
                
                self.log(f"✓ 认证成功")
                self.log(f"  账号 ID: {identity.get('AccountId', 'N/A')}")
                self.log(f"  用户 ID: {identity.get('UserId', 'N/A')}")
                self.log(f"  ARN: {identity.get('Arn', 'N/A')}")
                return True
            except Exception as e:
                self.log(f"✗ 认证失败: {str(e)}")
                return False
                
        except Exception as e:
            self.log(f"✗ 初始化失败: {str(e)}")
            return False
    
    def query_slb_status(self):
        self.log("\n=== Step 2: 查询 SLB 实例状态 ===")
        
        try:
            request = DescribeLoadBalancerAttributeRequest()
            request.set_LoadBalancerId(self.load_balancer_id)
            
            response = self.client.do_action_with_exception(request)
            slb_info = json.loads(response.decode('utf-8'))
            
            self.log("✓ SLB 实例存在")
            self.log(f"  实例 ID: {slb_info.get('LoadBalancerId', 'N/A')}")
            self.log(f"  实例名称: {slb_info.get('LoadBalancerName', 'N/A')}")
            self.log(f"  实例状态: {slb_info.get('LoadBalancerStatus', 'N/A')}")
            self.log(f"  IP 地址: {slb_info.get('Address', 'N/A')}")
            self.log(f"  地址类型: {slb_info.get('AddressType', 'N/A')}")
            self.log(f"  VPC ID: {slb_info.get('VpcId', 'N/A')}")
            self.log(f"  VSwitch ID: {slb_info.get('VSwitchId', 'N/A')}")
            self.log(f"  网络类型: {slb_info.get('NetworkType', 'N/A')}")
            
            return slb_info
            
        except ServerException as e:
            if e.get_error_code() == 'InvalidLoadBalancerId.NotFound':
                self.log(f"✗ SLB 实例不存在: {self.load_balancer_id}")
            else:
                self.log(f"✗ 查询失败: {e.get_error_msg()}")
            return None
        except Exception as e:
            self.log(f"✗ 查询失败: {str(e)}")
            return None
    
    def query_health_status(self):
        self.log("\n=== Step 3: 查询健康检查状态 ===")
        
        try:
            request = DescribeHealthStatusRequest()
            request.set_LoadBalancerId(self.load_balancer_id)
            
            response = self.client.do_action_with_exception(request)
            health_status = json.loads(response.decode('utf-8'))
            
            backend_servers = health_status.get('BackendServers', {}).get('BackendServer', [])
            
            if not backend_servers:
                self.log("⚠ 没有配置后端服务器")
                return [], 0, 0
            
            normal_count = 0
            abnormal_count = 0
            
            self.log(f"后端服务器数量: {len(backend_servers)}")
            self.log("\n健康状态:")
            
            for server in backend_servers:
                status = server.get('ServerHealthStatus', 'unknown')
                server_id = server.get('ServerId', 'N/A')
                port = server.get('Port', 'N/A')
                
                status_emoji = "✓" if status == "normal" else "✗"
                self.log(f"  {status_emoji} ServerId: {server_id}, Port: {port}, Status: {status}")
                
                if status == "normal":
                    normal_count += 1
                else:
                    abnormal_count += 1
            
            self.log(f"\n健康服务器: {normal_count}")
            self.log(f"异常服务器: {abnormal_count}")
            
            return backend_servers, normal_count, abnormal_count
            
        except Exception as e:
            self.log(f"✗ 查询失败: {str(e)}")
            return [], 0, 0
    
    def query_listeners(self):
        self.log("\n=== Step 4: 查询监听配置 ===")
        
        try:
            request = DescribeLoadBalancerListenersRequest()
            request.set_LoadBalancerIds([self.load_balancer_id])
            
            response = self.client.do_action_with_exception(request)
            listeners = json.loads(response.decode('utf-8'))
            
            listener_list = listeners.get('Listeners', [])
            
            if not listener_list:
                self.log("⚠ 没有配置监听")
                return []
            
            self.log(f"监听数量: {len(listener_list)}")
            self.log("\n监听配置:")
            
            for listener in listener_list:
                self.log(f"  - 监听端口: {listener.get('ListenerPort', 'N/A')}")
                self.log(f"    后端端口: {listener.get('BackendServerPort', 'N/A')}")
                self.log(f"    协议: {listener.get('ListenerProtocol', 'N/A')}")
                self.log(f"    状态: {listener.get('Status', 'N/A')}")
                self.log(f"    调度算法: {listener.get('Scheduler', 'N/A')}")
                
                http_config = listener.get('HTTPListenerConfig', {})
                if http_config:
                    self.log(f"    健康检查: {http_config.get('HealthCheck', 'N/A')}")
                    self.log(f"      健康检查 URI: {http_config.get('HealthCheckURI', 'N/A')}")
                    self.log(f"      健康检查方法: {http_config.get('HealthCheckMethod', 'N/A')}")
                    self.log(f"      健康检查间隔: {http_config.get('HealthCheckInterval', 'N/A')} 秒")
                    self.log(f"      健康阈值: {http_config.get('HealthyThreshold', 'N/A')}")
                    self.log(f"      不健康阈值: {http_config.get('UnhealthyThreshold', 'N/A')}")
                else:
                    self.log(f"    健康检查: 未配置")
                self.log("")
            
            return listener_list
            
        except Exception as e:
            self.log(f"✗ 查询失败: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
            return []
    
    def check_abnormal_servers(self, abnormal_servers):
        if not abnormal_servers:
            return
        
        self.log("\n=== Step 5: 检查异常服务器 ===")
        
        for server in abnormal_servers:
            server_id = server.get('ServerId')
            port = server.get('Port', 'N/A')
            self.log(f"\n--- 服务器: {server_id} ---")
            self.log(f"端口: {port}")
            self.log(f"健康状态: abnormal")
            
            try:
                request = DescribeInstanceAttributeRequest()
                request.set_InstanceId(server_id)
                
                response = self.client.do_action_with_exception(request)
                instance_info = json.loads(response.decode('utf-8'))
                
                instance_status = instance_info.get('Status', 'N/A')
                private_ip = instance_info.get('VpcAttributes', {}).get('PrivateIpAddress', {}).get('IpAddress', ['N/A'])[0]
                public_ip = instance_info.get('PublicIpAddress', {}).get('IpAddress', ['N/A'])[0]
                
                self.log(f"实例状态: {instance_status}")
                self.log(f"内网 IP: {private_ip}")
                self.log(f"公网 IP: {public_ip}")
                
                if instance_status != 'Running':
                    self.log(f"⚠ 警告: 实例状态异常，应为 Running")
                    self.log(f"  建议操作: 在阿里云控制台启动实例")
                
                security_group_ids = instance_info.get('SecurityGroupIds', {}).get('SecurityGroupId', [])
                if security_group_ids:
                    security_group_id = security_group_ids[0]
                    self.log(f"安全组 ID: {security_group_id}")
                    
                    try:
                        request = DescribeSecurityGroupAttributeRequest()
                        request.set_SecurityGroupId(security_group_id)
                        
                        response = self.client.do_action_with_exception(request)
                        sg_info = json.loads(response.decode('utf-8'))
                        
                        permissions = sg_info.get('Permissions', {}).get('Permission', [])
                        
                        slb_access_count = 0
                        port_allowed = False
                        
                        for perm in permissions:
                            if perm.get('SourceCidrIp') == '100.64.0.0/10':
                                slb_access_count += 1
                                port_range = perm.get('PortRange', 'N/A')
                                self.log(f"  允许 SLB 网段访问: {port_range}")
                                
                                if port_range == f"{port}/{port}" or port_range == "-1/-1":
                                    port_allowed = True
                        
                        self.log(f"允许 SLB 网段 (100.64.0.0/10) 访问的规则数: {slb_access_count}")
                        
                        if slb_access_count == 0:
                            self.log("⚠ 警告: 安全组未允许 SLB 健康检查网段 (100.64.0.0/10) 访问")
                            self.log("  这可能是健康检查失败的原因")
                            self.log("  建议添加安全组规则:")
                            self.log(f"    aliyun ecs AuthorizeSecurityGroup --SecurityGroupId {security_group_id} --IpProtocol tcp --PortRange {port}/{port} --SourceCidrIp 100.64.0.0/10")
                        elif not port_allowed:
                            self.log(f"⚠ 警告: 安全组未明确允许端口 {port}")
                            self.log("  建议检查端口配置是否正确")
                    except Exception as e:
                        self.log(f"✗ 查询安全组失败: {str(e)}")
                
                self.log("\n排查建议:")
                self.log("1. 登录服务器检查端口监听状态:")
                self.log(f"   ssh root@{public_ip if public_ip != 'N/A' else private_ip}")
                self.log(f"   ss -tuln | grep :{port}")
                self.log("\n2. 检查服务进程状态:")
                self.log("   systemctl status nginx")
                self.log("   systemctl status httpd")
                self.log("\n3. 检查服务日志:")
                self.log("   tail -100 /var/log/nginx/error.log")
                self.log("   journalctl -u nginx -n 100")
                self.log("\n4. 本地连接测试:")
                self.log(f"   curl -I http://127.0.0.1:{port}/")
                self.log(f"   nc -zv 127.0.0.1 {port}")
                
            except Exception as e:
                self.log(f"✗ 查询服务器信息失败: {str(e)}")
    
    def analyze_security_group_root_cause(self, abnormal_servers):
        if not abnormal_servers:
            return
        
        self.log("\n=== Step 6: 详细安全组排查和根本原因分析 ===")
        
        for server in abnormal_servers:
            server_id = server.get('ServerId')
            port = server.get('Port', 'N/A')
            self.log(f"\n--- 服务器: {server_id}, 端口: {port} ---")
            
            try:
                request = DescribeInstanceAttributeRequest()
                request.set_InstanceId(server_id)
                
                response = self.client.do_action_with_exception(request)
                instance_info = json.loads(response.decode('utf-8'))
                
                security_group_ids = instance_info.get('SecurityGroupIds', {}).get('SecurityGroupId', [])
                
                for sg_id in security_group_ids:
                    self.log(f"\n安全组: {sg_id}")
                    
                    try:
                        request = DescribeSecurityGroupAttributeRequest()
                        request.set_SecurityGroupId(sg_id)
                        
                        response = self.client.do_action_with_exception(request)
                        sg_info = json.loads(response.decode('utf-8'))
                        
                        sg_name = sg_info.get('SecurityGroupName', 'N/A')
                        self.log(f"  安全组名称: {sg_name}")
                        
                        permissions = sg_info.get('Permissions', {}).get('Permission', [])
                        
                        self.log("\n  入方向规则分析:")
                        
                        ingress_rules = [p for p in permissions if p.get('Direction') == 'ingress']
                        
                        if not ingress_rules:
                            self.log("    ⚠ 警告: 没有入方向规则")
                        else:
                            slb_rules = [p for p in ingress_rules if p.get('SourceCidrIp') == '100.64.0.0/10']
                            
                            if not slb_rules:
                                self.log("    ✗ 根本原因: 安全组未允许 SLB 健康检查网段 (100.64.0.0/10) 访问")
                                self.log("    影响: SLB 无法进行健康检查，导致服务器被标记为异常")
                                self.log("")
                                self.log("    修复命令:")
                                self.log(f"      aliyun ecs AuthorizeSecurityGroup \\")
                                self.log(f"        --SecurityGroupId {sg_id} \\")
                                self.log(f"        --IpProtocol tcp \\")
                                self.log(f"        --PortRange {port}/{port} \\")
                                self.log(f"        --SourceCidrIp 100.64.0.0/10 \\")
                                self.log(f"        --Description \"Allow SLB health check\"")
                            else:
                                port_matched = [p for p in slb_rules if p.get('PortRange') == f"{port}/{port}" or p.get('PortRange') == "-1/-1"]
                                
                                if not port_matched:
                                    self.log("    ✗ 根本原因: 安全组允许 SLB 网段访问，但端口不匹配")
                                    self.log("    当前允许的端口:")
                                    for rule in slb_rules:
                                        self.log(f"      - {rule.get('PortRange', 'N/A')}")
                                    self.log(f"    需要开放的端口: {port}")
                                    self.log("")
                                    self.log("    修复命令:")
                                    self.log(f"      aliyun ecs AuthorizeSecurityGroup \\")
                                    self.log(f"        --SecurityGroupId {sg_id} \\")
                                    self.log(f"        --IpProtocol tcp \\")
                                    self.log(f"        --PortRange {port}/{port} \\")
                                    self.log(f"        --SourceCidrIp 100.64.0.0/10 \\")
                                    self.log(f"        --Description \"Allow SLB health check for port {port}\"")
                                else:
                                    protocol = port_matched[0].get('IpProtocol', 'N/A')
                                    if protocol not in ['TCP', 'ALL']:
                                        self.log("    ✗ 根本原因: 协议类型不匹配")
                                        self.log(f"    当前协议: {protocol}")
                                        self.log("    需要协议: TCP")
                                        self.log("")
                                        self.log("    修复命令:")
                                        self.log(f"      aliyun ecs AuthorizeSecurityGroup \\")
                                        self.log(f"        --SecurityGroupId {sg_id} \\")
                                        self.log(f"        --IpProtocol tcp \\")
                                        self.log(f"        --PortRange {port}/{port} \\")
                                        self.log(f"        --SourceCidrIp 100.64.0.0/10 \\")
                                        self.log(f"        --Description \"Allow SLB health check via TCP\"")
                                    else:
                                        policy = port_matched[0].get('Policy', 'N/A')
                                        if policy != 'Accept':
                                            self.log("    ✗ 根本原因: 授权策略为拒绝")
                                            self.log(f"    当前策略: {policy}")
                                            self.log("    需要策略: Accept")
                                            self.log("")
                                            self.log("    修复命令:")
                                            self.log(f"      aliyun ecs AuthorizeSecurityGroup \\")
                                            self.log(f"        --SecurityGroupId {sg_id} \\")
                                            self.log(f"        --IpProtocol tcp \\")
                                            self.log(f"        --PortRange {port}/{port} \\")
                                            self.log(f"        --SourceCidrIp 100.64.0.0/10 \\")
                                            self.log(f"        --Policy Accept \\")
                                            self.log(f"        --Description \"Allow SLB health check\"")
                                        else:
                                            self.log("    ✓ 安全组规则正常")
                                            self.log(f"    允许 SLB 网段 (100.64.0.0/10) 访问端口 {port}")
                            
                            deny_rules = [p for p in ingress_rules if p.get('Policy') in ['Drop', 'Reject']]
                            if deny_rules:
                                self.log("\n    ⚠ 警告: 发现拒绝规则，可能影响访问")
                                for rule in deny_rules:
                                    self.log(f"      - 源: {rule.get('SourceCidrIp', 'N/A')}, 端口: {rule.get('PortRange', 'N/A')}, 策略: {rule.get('Policy', 'N/A')}")
                    
                    except Exception as e:
                        self.log(f"✗ 查询安全组失败: {str(e)}")
            
            except Exception as e:
                self.log(f"✗ 查询服务器信息失败: {str(e)}")
    
    def run_diagnosis(self):
        self.log("=" * 60)
        self.log("阿里云 SLB 远程诊断")
        self.log("=" * 60)
        self.log(f"SLB ID: {self.load_balancer_id}")
        self.log(f"区域: {self.region}")
        self.log(f"诊断时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if not self.check_cli_environment():
            self.log("\n" + "=" * 60)
            self.log("诊断失败: 环境检查未通过")
            self.log("=" * 60)
            return
        
        slb_info = self.query_slb_status()
        if not slb_info:
            self.log("\n" + "=" * 60)
            self.log("诊断失败: SLB 实例不存在或无权访问")
            self.log("=" * 60)
            return
        
        backend_servers, normal_count, abnormal_count = self.query_health_status()
        
        listeners = self.query_listeners()
        
        total_servers = normal_count + abnormal_count
        service_capacity = (normal_count / total_servers * 100) if total_servers > 0 else 0
        
        listener_count = len(listeners)
        
        should_trigger_detailed_analysis = False
        trigger_reasons = []
        
        if abnormal_count > 0:
            should_trigger_detailed_analysis = True
            trigger_reasons.append(f"检测到 {abnormal_count} 台异常服务器")
        
        if service_capacity < 100:
            should_trigger_detailed_analysis = True
            trigger_reasons.append(f"服务能力低于 100% (当前: {service_capacity:.1f}%)")
        
        if listener_count < normal_count:
            should_trigger_detailed_analysis = True
            trigger_reasons.append(f"监听数量 ({listener_count}) 小于健康实例数 ({normal_count})，存在健康后端服务器未被监听使用")
        
        if should_trigger_detailed_analysis:
            self.log("\n" + "=" * 60)
            self.log("触发详细分析")
            self.log("=" * 60)
            self.log("触发原因:")
            for reason in trigger_reasons:
                self.log(f"  - {reason}")
            self.log("")
            
            if service_capacity < 100:
                self.log("\n=== Step 4.5: 服务能力评估 ===")
                self.log(f"服务能力: {service_capacity:.1f}%")
                self.log(f"正常服务器: {normal_count}/{total_servers}")
                self.log(f"异常服务器: {abnormal_count}/{total_servers}")
                
                if service_capacity < 50:
                    self.log(f"⚠ 严重警告: 服务能力严重不足，请立即处理")
                elif service_capacity < 80:
                    self.log(f"⚠ 警告: 服务能力下降，建议尽快处理")
                else:
                    self.log(f"ℹ 提示: 服务能力轻微下降，建议及时处理")
                
                if abnormal_count > 0:
                    self.log(f"\n⚠ 服务能力低于 100%，以下服务器的端口出现问题：")
                    abnormal_servers = [s for s in backend_servers if s.get('ServerHealthStatus') != 'normal']
                    for server in abnormal_servers:
                        server_id = server.get('ServerId')
                        port = server.get('Port', 'N/A')
                        status = server.get('ServerHealthStatus', 'N/A')
                        self.log(f"  - 服务器 ID: {server_id}, 端口: {port}, 状态: {status}")
                    
                    self.log("\n建议操作：")
                    self.log("1. 登录异常服务器检查端口监听状态")
                    self.log("2. 检查服务进程是否运行")
                    self.log("3. 检查服务日志排查错误")
                    self.log("4. 检查防火墙和安全组配置")
                
                self.log("")
            
            self.log("\n=== Step 5.5: 检查所有后端服务器的端口状态 ===")
            for server in backend_servers:
                server_id = server.get('ServerId')
                port = server.get('Port', 'N/A')
                status = server.get('ServerHealthStatus', 'N/A')
                status_emoji = "✓" if status == "normal" else "✗"
                self.log(f"  {status_emoji} 服务器 ID: {server_id}, 端口: {port}, 健康状态: {status}")
            
            self.log(f"\n端口状态汇总：")
            self.log(f"  正常端口数: {normal_count}")
            self.log(f"  异常端口数: {abnormal_count}")
            
            if abnormal_count > 0:
                self.log(f"\n⚠ 以下端口出现异常：")
                abnormal_servers = [s for s in backend_servers if s.get('ServerHealthStatus') != 'normal']
                for server in abnormal_servers:
                    server_id = server.get('ServerId')
                    port = server.get('Port', 'N/A')
                    self.log(f"  - 服务器 {server_id} 的端口 {port}")
            self.log("")
            
            if abnormal_count > 0:
                abnormal_servers = [s for s in backend_servers if s.get('ServerHealthStatus') != 'normal']
                self.check_abnormal_servers(abnormal_servers)
                self.analyze_security_group_root_cause(abnormal_servers)
        
        self.log("\n" + "=" * 60)
        self.log("诊断完成")
        self.log("=" * 60)
        
        if abnormal_count == 0 and normal_count > 0 and service_capacity == 100:
            self.log("\n✓ SLB 服务状态正常")
        elif abnormal_count > 0:
            self.log(f"\n✗ 发现 {abnormal_count} 台异常服务器，请检查上述诊断信息")
        elif service_capacity < 100:
            self.log(f"\n⚠ 服务能力低于 100%，请检查上述诊断信息")
        else:
            self.log("\n⚠ 未检测到后端服务器")
        
        self.log(f"\n诊断报告已保存到: {self.output_file}")


def main():
    if len(sys.argv) < 2:
        print("使用方法: python slb_diagnosis.py <LOAD_BALANCER_ID> [REGION]")
        print("示例: python slb_diagnosis.py lb-bp1bxqgw0jflid09i6xnq cn-hangzhou")
        sys.exit(1)
    
    load_balancer_id = sys.argv[1]
    region = sys.argv[2] if len(sys.argv) > 2 else 'cn-hangzhou'
    
    diagnosis = SLBDiagnosis(load_balancer_id, region)
    diagnosis.run_diagnosis()


if __name__ == '__main__':
    main()
