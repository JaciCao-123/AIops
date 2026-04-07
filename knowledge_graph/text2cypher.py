#!/usr/bin/env python3
"""
Text2Cypher - 自然语言转Cypher查询工具
通过CLI接收自然语言问题，转换为Cypher查询并返回结果
"""

import os
import sys
import json

import openai
from dotenv import load_dotenv
from neo4j import GraphDatabase


class Text2Cypher:
    """Text2Cypher转换器"""

    def __init__(self):
        """初始化"""
        env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
        load_dotenv(env_path)

        api_key = os.getenv('QWEN_API_KEY')
        if not api_key:
            raise ValueError('未找到QWEN_API_KEY环境变量')

        self.client = openai.OpenAI(
            api_key=api_key,
            base_url='https://dashscope.aliyuncs.com/compatible-mode/v1'
        )

        self.driver = GraphDatabase.driver(
            os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
            auth=(os.getenv('NEO4J_USER', 'neo4j'), os.getenv('NEO4J_PASSWORD', 'password'))
        )

        self.prompt_template = '''你是一个Neo4j图数据库查询专家。请将用户的自然语言问题转换为Cypher查询语句。

注意：
1. 所有节点都是MedicalNode标签，不要使用其他标签
2. 节点属性包括：id, name, type, description
3. type属性的值包括：药物、疾病、症状、药物类别
4. 关系类型都是大写，包括：治疗、属于、常用于、引发
5. 返回的Cypher查询应该直接可以在Neo4j中执行
6. 不要包含任何解释，只返回Cypher查询语句
7. 使用MATCH匹配MedicalNode标签，通过节点属性和关系类型进行查询

示例转换：
问题：阿司匹林能治疗哪些疾病？
Cypher：MATCH (d:MedicalNode)-[:治疗]->(disease:MedicalNode) WHERE d.name = '阿司匹林' AND d.type = '药物' RETURN disease.name AS 疾病名称

问题：有哪些药物属于非甾体抗炎药？
Cypher：MATCH (drug:MedicalNode)-[:属于]->(c:MedicalNode) WHERE c.name = '非甾体抗炎药' AND drug.type = '药物' RETURN drug.name AS 药物名称

问题：高血压可以用哪些药物治疗？
Cypher：MATCH (drug:MedicalNode)-[:治疗]->(d:MedicalNode) WHERE d.name = '高血压' AND drug.type = '药物' RETURN drug.name AS 药物名称

问题：哮喘有哪些症状？
Cypher：MATCH (d:MedicalNode)-[:引发]->(s:MedicalNode) WHERE d.name = '哮喘' AND s.type = '症状' RETURN s.name AS 症状名称

问题：列出所有的药物类别
Cypher：MATCH (c:MedicalNode) WHERE c.type = '药物类别' RETURN c.name AS 药物类别名称

问题：阿司匹林属于什么类别？
Cypher：MATCH (d:MedicalNode)-[:属于]->(c:MedicalNode) WHERE d.name = '阿司匹林' AND d.type = '药物' RETURN c.name AS 药物类别

现在请转换以下问题：
{question}

请直接返回Cypher查询语句，不要包含其他内容。'''

    def close(self):
        """关闭连接"""
        if hasattr(self, 'driver'):
            self.driver.close()

    def text_to_cypher(self, question: str) -> str:
        """将自然语言问题转换为Cypher查询"""
        try:
            prompt = self.prompt_template.replace('{question}', question)

            response = self.client.chat.completions.create(
                model='qwen-plus',
                messages=[
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.1
            )

            cypher = response.choices[0].message.content.strip()

            cypher = self._clean_cypher(cypher)

            return cypher

        except Exception as e:
            print(f'转换失败: {e}')
            return None

    def _clean_cypher(self, cypher: str) -> str:
        """清理Cypher查询"""
        cypher = cypher.strip()
        cypher = cypher.replace('```cypher', '')
        cypher = cypher.replace('```', '')
        cypher = cypher.strip()
        return cypher

    def execute_cypher(self, cypher: str):
        """执行Cypher查询"""
        try:
            with self.driver.session() as session:
                result = session.run(cypher)
                records = list(result)

                if not records:
                    return {'success': True, 'data': [], 'message': '查询成功，但没有找到结果'}

                columns = result.keys()
                data = []
                for record in records:
                    row = {}
                    for col in columns:
                        value = record[col]
                        if hasattr(value, 'name'):
                            row[col] = value.name
                        elif hasattr(value, 'properties'):
                            row[col] = dict(value.properties)
                        else:
                            row[col] = value
                    data.append(row)

                return {'success': True, 'data': data, 'columns': list(columns)}

        except Exception as e:
            return {'success': False, 'error': str(e), 'message': '查询执行失败'}


def print_banner():
    """打印欢迎信息"""
    print('='*70)
    print('  Text2Cypher - 自然语言转Cypher查询工具')
    print('='*70)
    print()
    print('  输入自然语言问题，系统会自动转换为Cypher查询并执行')
    print()
    print('  示例问题：')
    print('    - 阿司匹林能治疗哪些疾病？')
    print('    - 有哪些药物属于非甾体抗炎药？')
    print('    - 高血压可以用哪些药物治疗？')
    print('    - 哮喘有哪些症状？')
    print('    - 列出所有的药物类别')
    print()
    print('  输入 "quit" 或 "exit" 退出程序')
    print('  输入 "help" 查看帮助信息')
    print('='*70)
    print()


def print_help():
    """打印帮助信息"""
    print()
    print('帮助信息：')
    print('-' * 70)
    print('  Text2Cypher会将您的自然语言问题转换为Cypher查询语句')
    print('  并在Neo4j数据库中执行，返回查询结果')
    print()
    print('  使用示例：')
    print('    - 阿司匹林能治疗哪些疾病？')
    print('    - 有哪些药物属于非甾体抗炎药？')
    print('    - 高血压可以用哪些药物治疗？')
    print('    - 哮喘有哪些症状？')
    print('    - 列出所有的药物类别')
    print()
    print('  特殊命令：')
    print('    - help: 显示帮助信息')
    print('    - quit/exit: 退出程序')
    print('    - cypher <query>: 直接执行Cypher查询')
    print('    - show schema: 显示数据库Schema')
    print('-' * 70)
    print()


def show_schema(driver):
    """显示数据库Schema"""
    print()
    print('数据库Schema信息：')
    print('-' * 70)

    with driver.session() as session:
        labels = session.run('CALL db.labels() YIELD label RETURN label')
        print('  标签（Labels）：')
        for record in labels:
            print(f'    - {record["label"]}')

        rel_types = session.run('CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType')
        print()
        print('  关系类型（Relationship Types）：')
        for record in rel_types:
            print(f'    - {record["relationshipType"]}')

        print()
        print('  节点属性示例：')
        result = session.run('MATCH (n:MedicalNode) RETURN keys(n) AS keys LIMIT 1')
        for record in result:
            print(f'    属性：{record["keys"]}')

    print('-' * 70)
    print()


def main():
    """主函数"""
    try:
        print_banner()

        converter = Text2Cypher()
        print('✓ 成功连接到 Neo4j 数据库\n')

        while True:
            try:
                question = input('❓ 请输入问题：').strip()

                if not question:
                    continue

                if question.lower() in ['quit', 'exit', 'q']:
                    print('\n👋 感谢使用Text2Cypher，再见！')
                    break

                if question.lower() == 'help':
                    print_help()
                    continue

                if question.lower() == 'show schema':
                    show_schema(converter.driver)
                    continue

                if question.lower().startswith('cypher '):
                    cypher = question[7:].strip()
                    print(f'\n📤 直接执行Cypher查询：')
                    print(f'   {cypher}\n')

                    result = converter.execute_cypher(cypher)

                    if result['success']:
                        print('✓ 查询执行成功\n')
                        if result['data']:
                            print('📊 查询结果：')
                            for i, row in enumerate(result['data'], 1):
                                print(f'   {i}. {row}')
                        else:
                            print('   (无结果)')
                    else:
                        print(f'✗ 查询执行失败：{result["error"]}')

                    print()
                    continue

                print(f'\n📝 您的问题是：{question}\n')

                print('🔄 正在转换为Cypher查询...\n')

                cypher = converter.text_to_cypher(question)

                if not cypher:
                    print('✗ 转换失败，请稍后重试\n')
                    continue

                print('📤 生成的Cypher查询：')
                print(f'   {cypher}\n')

                print('🔄 正在执行查询...\n')

                result = converter.execute_cypher(cypher)

                if result['success']:
                    print('✓ 查询执行成功\n')

                    if result['data']:
                        print('📊 查询结果：')
                        print()
                        for i, row in enumerate(result['data'], 1):
                            print(f'   {i}. {row}')
                    else:
                        print('   (无结果)')

                else:
                    print(f'✗ 查询执行失败：{result["error"]}')

                print()

            except KeyboardInterrupt:
                print('\n\n👋 感谢使用Text2Cypher，再见！')
                break
            except Exception as e:
                print(f'\n✗ 发生错误：{e}\n')

        converter.close()
        print('✓ 已关闭 Neo4j 连接')

    except Exception as e:
        print(f'\n❌ 程序启动失败：{e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
