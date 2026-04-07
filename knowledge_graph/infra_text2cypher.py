#!/usr/bin/env python3
"""
Infra Text2Cypher - 基础设施图谱自然语言查询工具
通过CLI接收自然语言问题，转换为Cypher查询并返回结果
"""

import os
import sys
import json

import openai
from dotenv import load_dotenv
from neo4j import GraphDatabase


class InfraText2Cypher:
    def __init__(self):
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        load_dotenv(env_path)

        api_key = os.getenv('QWEN_API_KEY') or os.getenv('LLM_API_KEY')
        if not api_key:
            raise ValueError('未找到API_KEY环境变量 (QWEN_API_KEY 或 LLM_API_KEY)')

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
1. 节点标签包括：Server, Middleware, NetworkDevice, Storage, Database, Infra
   - 所有节点都有Infra标签，如(Server:Infra)、(Middleware:Infra)等
2. 关系类型包括：PUBLISH_EVENT, CONSUME_EVENT, CONNECTED_TO, READS_FROM, WRITES_TO, DEPENDS_ON
3. 节点属性：
   - Server: name, ip, location, cpu_usage, owner, owner_email
   - Middleware: name, type(如Kafka), topic, version, status, lag, owner, owner_email
   - NetworkDevice: name, type(如Switch/Firewall), vendor, ip, bandwidth, status, owner, owner_email
   - Storage: name, type(如OSS), bucket_name, region, storage_class, size, owner, owner_email
   - Database: name, db_type(如MySQL/Redis/PostgreSQL), port, memory/volume, status, owner, owner_email
4. 关系属性如topic, port, speed, purpose, freq, latency, since等
5. 返回的Cypher查询应该直接可以在Neo4j中执行
6. 不要包含任何解释，只返回Cypher查询语句

示例转换：
问题：prod-server-01连接了哪些网络设备？
Cypher：MATCH (s:Server {name: 'prod-server-01'})-[:CONNECTED_TO]->(n:NetworkDevice) RETURN n.name AS 设备名称, n.type AS 类型, n.bandwidth AS 带宽

问题：哪些服务器往Kafka发布事件？
Cypher：MATCH (s:Server)-[:PUBLISH_EVENT]->(m:Middleware) RETURN s.name AS 服务器名称, m.name AS Kafka集群, m.topic AS 主题

问题：prod-server-03消费哪些Kafka主题？
Cypher：MATCH (s:Server {name: 'prod-server-03'})-[:CONSUME_EVENT]->(m:Middleware) RETURN m.name AS Kafka集群, m.topic AS 主题

问题：哪些Kafka集群正在运行？
Cypher：MATCH (m:Middleware) WHERE m.type = 'Kafka' AND m.status = 'Running' RETURN m.name AS Kafka集群, m.version AS 版本

问题：prod-server-01从哪个OSS读取数据？
Cypher：MATCH (s:Server {name: 'prod-server-01'})-[:READS_FROM]->(st:Storage) WHERE st.type = 'OSS' RETURN st.name AS OSS名称, st.bucket_name AS Bucket, st.region AS 区域

问题：prod-server-01依赖哪些数据库？
Cypher：MATCH (s:Server {name: 'prod-server-01'})-[:DEPENDS_ON]->(d:Database) RETURN d.name AS 数据库名称, d.db_type AS 类型, d.port AS 端口

问题：哪些服务器依赖Redis？
Cypher：MATCH (s:Server)-[:DEPENDS_ON]->(d:Database) WHERE d.db_type = 'Redis' RETURN s.name AS 服务器名称, d.name AS Redis名称

问题：prod-server-01的详细信息（包括IP、位置、CPU、负责人）
Cypher：MATCH (s:Server {name: 'prod-server-01'}) RETURN s.name AS 名称, s.ip AS IP, s.location AS 位置, s.cpu_usage AS CPU使用率, s.owner AS 负责人

问题：查看所有交换机及其带宽
Cypher：MATCH (n:NetworkDevice) WHERE n.type = 'Switch' RETURN n.name AS 交换机, n.vendor AS 厂商, n.bandwidth AS 带宽, n.ip AS IP

问题：查看所有服务器及其所在机房
Cypher：MATCH (s:Server) RETURN s.name AS 服务器, s.ip AS IP地址, s.location AS 机房位置, s.cpu_usage AS CPU使用率

问题：order-kafka-cluster的延迟是多少？
Cypher：MATCH (s:Server)-[:PUBLISH_EVENT|CONSUME_EVENT]->(m:Middleware {name: 'order-kafka-cluster'}) RETURN m.lag AS 延迟

现在请转换以下问题：
{question}

请直接返回Cypher查询语句，不要包含其他内容。'''

    def close(self):
        if hasattr(self, 'driver'):
            self.driver.close()

    def text_to_cypher(self, question: str) -> str:
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
        cypher = cypher.strip()
        cypher = cypher.strip('```cypher').strip('```').strip()
        return cypher

    def execute_cypher(self, cypher: str):
        try:
            with self.driver.session() as session:
                result = session.run(cypher)
                records = list(result)
                return records
        except Exception as e:
            print(f'执行失败: {e}')
            return None

    def query(self, question: str):
        print(f'\n问题: {question}')
        print('-' * 50)

        cypher = self.text_to_cypher(question)
        if not cypher:
            return

        print(f'生成的Cypher: {cypher}')
        print('-' * 50)

        records = self.execute_cypher(cypher)
        if records is None:
            return

        if not records:
            print('查询结果为空')
            return

        print('查询结果:')
        for i, record in enumerate(records, 1):
            print(f'  {i}. {dict(record)}')

        return records


def main():
    print('=' * 50)
    print('基础设施图谱 Text2Cypher')
    print('=' * 50)
    print('输入问题进行查询，输入 q 或 quit 退出')
    print()

    try:
        engine = InfraText2Cypher()
    except Exception as e:
        print(f'初始化失败: {e}')
        sys.exit(1)

    while True:
        try:
            question = input('\n请输入问题> ').strip()
        except (KeyboardInterrupt, EOFError):
            print('\n\n退出')
            break

        if question.lower() in ['q', 'quit', 'exit', '退出']:
            print('再见!')
            break

        if not question:
            continue

        engine.query(question)

    engine.close()


if __name__ == '__main__':
    main()
