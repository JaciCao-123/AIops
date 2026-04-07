#!/usr/bin/env python3
"""
Text2Cypher测试脚本
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from text2cypher import Text2Cypher


def test_text2cypher():
    """测试Text2Cypher功能"""
    try:
        converter = Text2Cypher()
        print('✓ 成功连接到 Neo4j 数据库\n')

        test_questions = [
            '阿司匹林能治疗哪些疾病？',
            '有哪些药物属于非甾体抗炎药？',
            '高血压可以用哪些药物治疗？',
            '哮喘有哪些症状？',
            '列出所有的药物类别',
        ]

        for i, question in enumerate(test_questions, 1):
            print('='*70)
            print(f'测试 {i}/{len(test_questions)}')
            print('='*70)
            print(f'\n📝 问题：{question}\n')

            print('🔄 正在转换为Cypher查询...\n')

            cypher = converter.text_to_cypher(question)

            if cypher:
                print('📤 生成的Cypher查询：')
                print(f'   {cypher}\n')

                print('🔄 正在执行查询...\n')

                result = converter.execute_cypher(cypher)

                if result['success']:
                    print('✓ 查询执行成功\n')

                    if result['data']:
                        print('📊 查询结果：')
                        for j, row in enumerate(result['data'], 1):
                            print(f'   {j}. {row}')
                    else:
                        print('   (无结果)')
                else:
                    print(f'✗ 查询执行失败：{result.get("error", "未知错误")}')
            else:
                print('✗ 转换失败\n')

            print()

        converter.close()
        print('✓ 已关闭 Neo4j 连接')
        print('\n✅ 所有测试完成！')

    except Exception as e:
        print(f'\n❌ 测试失败：{e}')
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_text2cypher()
