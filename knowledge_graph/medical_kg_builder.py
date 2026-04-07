#!/usr/bin/env python3
"""
医疗知识图谱构建器
从医疗文本中提取实体、属性和关系，存储到Neo4j
"""

import os
import json
import re
from typing import List, Dict, Any
from datetime import datetime

import openai
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()


class MedicalKnowledgeGraphBuilder:
    """医疗知识图谱构建器"""

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
        self.prompt_template = '''你是一个医疗知识图谱专家。请从以下文本中提取实体、属性和关系。

实体类型定义：
- 药物：具有治疗作用的物质
- 疾病：疾病名称
- 症状：疾病表现
- 药物类别：药物的分类

关系类型：
- 治疗：药物用于治疗疾病
- 属于：药物属于某类别
- 常用于：药物通常用于某种情况
- 引发：疾病引发症状

请以JSON格式返回，格式如下：
{"entities": [{"name": "实体名称", "type": "实体类型", "properties": {"description": "描述"}}], "relations": [{"source": "头实体名称", "relation": "关系类型", "target": "尾实体名称"}]}

文本内容：
''' + '{text}' + '''

请直接返回JSON，不要包含其他内容。'''

    def close(self):
        """关闭连接"""
        if hasattr(self, 'driver'):
            self.driver.close()

    def _extract_entities_and_relations(self, text: str) -> Dict[str, Any]:
        """使用LLM提取实体和关系"""
        try:
            prompt = self.prompt_template.replace('{text}', text)

            response = self.client.chat.completions.create(
                model='qwen-plus',
                messages=[
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.1
            )
            content = response.choices[0].message.content

            content = self._clean_json(content)

            data = json.loads(content)
            return data

        except json.JSONDecodeError as e:
            print(f'JSON解析失败: {e}')
            print(f'原始内容: {content[:200]}')
            return {'entities': [], 'relations': []}
        except Exception as e:
            print(f'提取失败: {e}')
            import traceback
            traceback.print_exc()
            return {'entities': [], 'relations': []}

    def _clean_json(self, text: str) -> str:
        """清理JSON字符串"""
        text = re.sub(r'^```json\s*', '', text)
        text = re.sub(r'^```\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        text = text.strip()
        return text

    def _normalize_entity_id(self, name: str) -> str:
        """规范化实体ID"""
        return name.lower().replace(' ', '_').replace('-', '_')

    def _create_constraints(self):
        """创建约束条件"""
        with self.driver.session() as session:
            session.run('''
                CREATE CONSTRAINT IF NOT EXISTS FOR (n:MedicalNode)
                REQUIRE n.id IS UNIQUE
            ''')

    def _create_node(self, tx, entity: Dict[str, Any]):
        """创建或更新节点（幂等操作）"""
        entity_id = self._normalize_entity_id(entity['name'])
        entity_type = entity.get('type', 'Unknown')
        properties = entity.get('properties', {})

        query = '''
        MERGE (n:MedicalNode {id: $id})
        SET n.name = $name,
            n.type = $type,
            n.description = $description,
            n.updated_at = datetime()
        '''

        tx.run(query, id=entity_id, name=entity['name'], type=entity_type,
               description=properties.get('description', ''))

    def _create_relationship(self, tx, relation: Dict[str, Any]):
        """创建或更新关系（幂等操作）"""
        source_id = self._normalize_entity_id(relation['source'])
        target_id = self._normalize_entity_id(relation['target'])
        relation_type = relation['relation'].upper().replace(' ', '_')

        query = f'''
        MATCH (source:MedicalNode {{id: $source_id}})
        MATCH (target:MedicalNode {{id: $target_id}})
        MERGE (source)-[r:{relation_type}]->(target)
        SET r.updated_at = datetime()
        '''

        tx.run(query, source_id=source_id, target_id=target_id)

    def _save_to_neo4j(self, data: Dict[str, Any]):
        """将提取的数据保存到Neo4j"""
        with self.driver.session() as session:
            with session.begin_transaction() as tx:
                for entity in data.get('entities', []):
                    self._create_node(tx, entity)

                for relation in data.get('relations', []):
                    self._create_relationship(tx, relation)

                tx.commit()

            print('✓ 数据已保存到 Neo4j')

    def _query_graph_stats(self):
        """查询图谱统计信息"""
        with self.driver.session() as session:
            node_count = session.run('''
                MATCH (n:MedicalNode)
                RETURN count(n) AS count
            ''').single()['count']

            relation_count = session.run('''
                MATCH ()-[r]->()
                RETURN count(r) AS count
            ''').single()['count']

            print(f'\n📊 图谱统计：')
            print(f'   - 节点数: {node_count}')
            print(f'   - 关系数: {relation_count}')

    def build_from_text(self, text: str, batch_id: int = 1):
        """从文本构建知识图谱"""
        print('\n' + '='*50)
        print(f'开始构建医疗知识图谱 (批次 {batch_id})')
        print('='*50)

        try:
            self._create_constraints()

            print(f'\n📝 输入文本：')
            print(f'   {text}')

            data = self._extract_entities_and_relations(text)

            if not data.get('entities') and not data.get('relations'):
                print('⚠ 未提取到任何实体或关系')
                return None

            print(f'\n📦 提取结果：')
            for entity in data.get('entities', []):
                print(f'   实体: {entity["name"]} ({entity["type"]})')

            for relation in data.get('relations', []):
                print(f'   关系: {relation["source"]} -> {relation["relation"]} -> {relation["target"]}')

            self._save_to_neo4j(data)
            self._query_graph_stats()

            print('\n' + '='*50)
            print('✅ 图谱构建完成！')
            print('='*50 + '\n')

            return data

        except Exception as e:
            print(f'\n❌ 构建失败: {e}')
            raise

    def build_from_file(self, file_path: str):
        """从文件批量构建知识图谱"""
        print('\n' + '='*60)
        print('医疗知识图谱构建器 - 文件批量处理')
        print('='*60)

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            texts = [t.strip() for t in content.split('\n') if t.strip()]

            print(f'\n📦 待处理文本数量: {len(texts)}')

            all_entities = []
            all_relations = []
            success_count = 0
            fail_count = 0

            for i, text in enumerate(texts, 1):
                try:
                    print(f'\n🔄 处理批次 {i}/{len(texts)}...')
                    data = self.build_from_text(text, batch_id=i)

                    if data:
                        all_entities.extend(data.get('entities', []))
                        all_relations.extend(data.get('relations', []))
                        success_count += 1
                    else:
                        fail_count += 1

                except Exception as e:
                    print(f'❌ 批次 {i} 处理失败: {e}')
                    fail_count += 1

            print('\n' + '='*60)
            print('📊 批量处理总结')
            print('='*60)
            print(f'✓ 成功处理: {success_count}/{len(texts)}')
            print(f'✗ 失败: {fail_count}/{len(texts)}')
            print(f'\n📦 总计提取：')
            print(f'   - 实体总数: {len(all_entities)}')
            print(f'   - 关系总数: {len(all_relations)}')

            entity_types = {}
            for entity in all_entities:
                entity_type = entity.get('type', 'Unknown')
                entity_types[entity_type] = entity_types.get(entity_type, 0) + 1

            print(f'\n📈 按类型统计：')
            for entity_type, count in sorted(entity_types.items(), key=lambda x: x[1], reverse=True):
                print(f'   - {entity_type}: {count}')

            print('\n' + '='*60)
            print('✅ 批量处理完成！')
            print('='*60 + '\n')

            return {
                'entities': all_entities,
                'relations': all_relations,
                'success_count': success_count,
                'fail_count': fail_count
            }

        except FileNotFoundError:
            print(f'\n❌ 文件不存在: {file_path}')
            raise
        except Exception as e:
            print(f'\n❌ 批量处理失败: {e}')
            raise


def main():
    """主函数"""
    try:
        builder = MedicalKnowledgeGraphBuilder()
        print('✓ 成功连接到 Neo4j 数据库')

        file_path = os.path.join(os.path.dirname(__file__), 'medician.txt')
        result = builder.build_from_file(file_path)

        print(f'\n📊 最终统计：')
        print(f'   - 总实体数: {len(result["entities"])}')
        print(f'   - 总关系数: {len(result["relations"])}')
        print(f'   - 成功率: {result["success_count"]}/{result["success_count"] + result["fail_count"]}')

        builder.close()
        print('\n✓ 已关闭 Neo4j 连接')

    except Exception as e:
        print(f'\n❌ 程序执行失败: {e}')
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
