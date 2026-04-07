#!/usr/bin/env python3
"""
查询阿里云 ECS 实例和弹性公网 IP 的关联关系
"""
import sys
import os
import json

sys.path.insert(0, '/Users/jaci-j/AIops/aiops-platform/backend')

from app.core.config import settings

print("=" * 60)
print("查询 ECS 实例和 EIP 关联关系")
print("=" * 60)

try:
    from aliyunsdkcore.client import AcsClient
    from aliyunsdkecs.request.v20140526 import DescribeInstancesRequest
    from aliyunsdkecs.request.v20140526 import DescribeEipAddressesRequest
    
    client = AcsClient(
        settings.ALIYUN_ACCESS_KEY_ID,
        settings.ALIYUN_ACCESS_KEY_SECRET,
        settings.ALIYUN_REGION_ID
    )
    
    print("\n1. 查询 ECS 实例...")
    request = DescribeInstancesRequest.DescribeInstancesRequest()
    request.set_PageSize(100)
    response = client.do_action_with_exception(request)
    result = json.loads(response)
    
    instances = result.get("Instances", {}).get("Instance", [])
    print(f"   找到 {len(instances)} 个实例")
    
    instance_map = {}
    for instance in instances:
        instance_id = instance.get("InstanceId")
        instance_name = instance.get("InstanceName")
        status = instance.get("Status")
        private_ip_list = instance.get("VpcAttributes", {}).get("PrivateIpAddress", {}).get("IpAddress", [])
        private_ip = private_ip_list[0] if private_ip_list else "无"
        
        instance_map[instance_id] = {
            "name": instance_name,
            "status": status,
            "private_ip": private_ip
        }
        
        print(f"\n   实例: {instance_name}")
        print(f"     ID: {instance_id}")
        print(f"     状态: {status}")
        print(f"     私网 IP: {private_ip}")
    
    print("\n2. 查询弹性公网 IP (EIP)...")
    eip_request = DescribeEipAddressesRequest.DescribeEipAddressesRequest()
    eip_request.set_PageSize(100)
    eip_response = client.do_action_with_exception(eip_request)
    eip_result = json.loads(eip_response)
    
    eips = eip_result.get("EipAddresses", {}).get("EipAddress", [])
    print(f"   找到 {len(eips)} 个 EIP")
    
    target_ip = "8.136.226.230"
    found = False
    
    for eip in eips:
        eip_address = eip.get("IpAddress")
        eip_status = eip.get("Status")
        instance_id = eip.get("InstanceId")
        bandwidth = eip.get("Bandwidth")
        
        print(f"\n   EIP: {eip_address}")
        print(f"     状态: {eip_status}")
        print(f"     带宽: {bandwidth} Mbps")
        
        if instance_id and instance_id in instance_map:
            instance_info = instance_map[instance_id]
            print(f"     绑定实例: {instance_info['name']} ({instance_id})")
            print(f"     实例状态: {instance_info['status']}")
            print(f"     私网 IP: {instance_info['private_ip']}")
        else:
            print(f"     绑定实例: 未绑定")
        
        if eip_address == target_ip:
            found = True
            print(f"\n   ⭐ 找到目标 IP: {target_ip}")
            if instance_id and instance_id in instance_map:
                instance_info = instance_map[instance_id]
                print(f"\n   【分析结果】")
                print(f"   该 IP 绑定的实例: {instance_info['name']}")
                print(f"   实例 ID: {instance_id}")
                print(f"   实例状态: {instance_info['status']}")
                print(f"   私网 IP: {instance_info['private_ip']}")
                
                if instance_info['status'] == 'Stopped':
                    print(f"\n   ⚠️  实例已停止！")
                    print(f"   这就是 SSH 连接超时的原因：实例处于停止状态")
                    print(f"\n   【解决方案】")
                    print(f"   1. 登录阿里云控制台启动实例")
                    print(f"   2. 或使用 API 启动实例")
            else:
                print(f"\n   ⚠️  该 EIP 未绑定任何实例")
                print(f"   这就是 SSH 连接超时的原因：EIP 未绑定实例")
    
    if not found:
        print(f"\n   ❌ 未找到目标 IP: {target_ip}")
        print(f"   可能原因：")
        print(f"   1. 该 IP 已释放")
        print(f"   2. 该 IP 在其他区域")
        print(f"   3. 该 IP 不属于此账号")
    
    print("\n" + "=" * 60)
    print("✅ 查询完成")
    print("=" * 60)
    
except Exception as e:
    print(f"\n❌ 错误: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
