#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试渐进式披露 Skill 架构
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.agents.skill_manager import SkillManager


def test_progressive_disclosure():
    """测试渐进式披露架构"""
    print("\n" + "="*70)
    print("渐进式披露 Skill 架构测试")
    print("="*70)
    
    manager = SkillManager()
    
    print("\n" + "-"*70)
    print("Step 1: 加载主索引文件")
    print("-"*70)
    
    index = manager.get_index()
    if index:
        print(f"✅ 主索引文件加载成功 ({len(index)} 字符)")
        lines = index.split('\n')[:10]
        print("\n索引预览:")
        for line in lines:
            print(f"  {line}")
    else:
        print("❌ 主索引文件加载失败")
        return False
    
    print("\n" + "-"*70)
    print("Step 2: 列出可用 Skill")
    print("-"*70)
    
    skills = manager.list_available_skills()
    print(f"\n发现 {len(skills)} 个 Skill:\n")
    
    for skill in skills:
        status = "✅" if skill["exists"] else "❌"
        print(f"  {status} {skill['name']}")
        print(f"      类别: {skill['category_name']}")
        print(f"      描述: {skill['description']}")
        print(f"      路径: {skill['path']}")
        print(f"      关键词: {skill['keywords_count']} 个")
        print()
    
    print("-"*70)
    print("Step 3: 渐进式加载 Skill")
    print("-"*70)
    
    print("\n初始加载状态:")
    print(f"  已加载 Skill 数量: {len(manager.loaded_skills)}")
    
    print("\n按需加载 debug_skill...")
    debug_content = manager.get_skill("debug_skill")
    if debug_content:
        print(f"  ✅ debug_skill 加载成功 ({len(debug_content)} 字符)")
    else:
        print("  ❌ debug_skill 加载失败")
    
    print(f"\n当前加载状态:")
    print(f"  已加载 Skill 数量: {len(manager.loaded_skills)}")
    print(f"  已加载: {list(manager.loaded_skills.keys())}")
    
    print("\n按需加载 gnn_rca_skill...")
    gnn_content = manager.get_skill("gnn_rca_skill")
    if gnn_content:
        print(f"  ✅ gnn_rca_skill 加载成功 ({len(gnn_content)} 字符)")
    
    print(f"\n当前加载状态:")
    print(f"  已加载 Skill 数量: {len(manager.loaded_skills)}")
    print(f"  已加载: {list(manager.loaded_skills.keys())}")
    
    print("\n" + "-"*70)
    print("Step 4: 关键词匹配测试")
    print("-"*70)
    
    test_queries = [
        "服务器磁盘空间不足",
        "微服务根因分析",
        "SSH 连接远程服务器",
        "CPU 负载过高",
        "MySQL 死锁排查",
        "数据库事务阻塞",
    ]
    
    for query in test_queries:
        relevant = manager.search_relevant_skills(query, {})
        print(f"\n  查询: \"{query}\"")
        print(f"  匹配: {relevant}")
    
    print("\n" + "-"*70)
    print("Step 5: 按类别加载 Skill")
    print("-"*70)
    
    diagnosis_skills = manager.get_skills_by_category("diagnosis")
    print(f"\n诊断类 Skill ({len(diagnosis_skills)} 个):")
    for name, content in diagnosis_skills.items():
        print(f"  - {name}: {len(content)} 字符")
    
    connection_skills = manager.get_skills_by_category("connection")
    print(f"\n连接类 Skill ({len(connection_skills)} 个):")
    for name, content in connection_skills.items():
        print(f"  - {name}: {len(content)} 字符")
    
    print("\n" + "-"*70)
    print("Step 6: @reference 引用解析测试")
    print("-"*70)
    
    test_text = """
    根据用户问题，需要使用以下 Skill:
    @reference: diagnosis/debug_skill.md
    @reference: diagnosis/gnn_rca_skill.md
    """
    
    references = manager.parse_reference(test_text)
    print(f"\n解析结果:")
    for skill_name, path in references:
        print(f"  - {skill_name}: {path}")
    
    print("\n" + "-"*70)
    print("Step 7: Skill 摘要")
    print("-"*70)
    
    print("\n" + manager.get_skill_summary())
    
    print("\n" + "="*70)
    print("测试结果汇总")
    print("="*70)
    
    all_passed = True
    
    if not index:
        print("❌ 主索引文件加载失败")
        all_passed = False
    else:
        print("✅ 主索引文件加载")
    
    if len(skills) != 4:
        print(f"❌ Skill 数量不正确: {len(skills)}/4")
        all_passed = False
    else:
        print("✅ Skill 注册")
    
    if len(manager.loaded_skills) != 4:
        print(f"❌ Skill 加载不完整: {len(manager.loaded_skills)}/4")
        all_passed = False
    else:
        print("✅ 渐进式加载")
    
    if all_passed:
        print("\n🎉 所有测试通过！")
    else:
        print("\n❌ 部分测试失败")
    
    return all_passed


if __name__ == "__main__":
    success = test_progressive_disclosure()
    sys.exit(0 if success else 1)
