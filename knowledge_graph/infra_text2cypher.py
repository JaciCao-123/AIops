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

        self.prompt_template = '''你是一个Neo4j图数据库查询专家，专注于iEngageProd生产环境基础设施图谱。请将用户的自然语言问题转换为Cypher查询语句。

注意：
1. 节点标签体系（所有节点都有iEngageProd标签，并组合其他标签）：
   - 网络层：VNET, EdgeNode, Public, External, Internal
   - 应用层：APIGateway, Microservice, WebServer, WebApp
   - 基础设施：LoadBalancer, NSG, AKS, Storage, Database, Email, MessageQueue
   - 示例：(n:iEngageProd:APIGateway:External), (n:iEngageProd:WebServer:Internal)

2. 关键属性：
   - name: 节点名称（如 "API Gateway 4", "HKAZEPLWB0003"）
   - ip: IP地址（如 "10.202.73.4"）
   - subnet: 子网（如 "subnet-p-infrasvc01-inttweba01-10.202.73.0-24"）
   - domain: 域名（如 "aiahk-apigw4-prd.aiaazure.biz"）
   - port: 端口号（如 8556, 443）
   - protocol: 协议（如 "HTTPS"）
   - type: 类型（如 "Identity Provider (IDP)", "Mobile Client"）
   - backend_pool: 后端池（负载均衡器属性）

3. 关系类型：
   - :CONTAINS - 包含关系（VNET包含资源）
   - :CONNECTS_TO - 连接关系（服务间调用）
   - :LOAD_BALANCES - 负载均衡关系
   - :SECURES - 安全保护关系（NSG保护资源）
   - :STORES_DATA_IN - 数据存储关系
   - :SENDS_EMAIL_VIA - 邮件发送关系
   - :CONSUMES_FROM - 消费关系（从消息队列消费）
   - :AUTHENTICATES_WITH - 认证关系
   - :INTEGRATES_WITH - 集成关系

4. 查询规则：
   - 使用 MATCH (n:iEngageProd) 查询所有iEngageProd节点
   - 使用 MATCH (n:iEngageProd:APIGateway) 查询特定类型的节点
   - 使用 WHERE 子句过滤属性（如 WHERE n.ip IS NOT NULL）
   - 返回有意义的列名（使用 AS 别名）

示例转换：

问题：查询所有API网关
Cypher：MATCH (n:iEngageProd:APIGateway) RETURN n.name AS 名称, n.ip AS IP地址, n.domain AS 域名, n.port AS 端口

问题：API Gateway 4连接到哪些服务？
Cypher：MATCH (gw:iEngageProd:APIGateway {name: 'API Gateway 4'})-[:CONNECTS_TO]->(target) RETURN target.name AS 目标服务, labels(target)[1] AS 类型, target.ip AS IP地址

问题：哪些Web服务器被负载均衡器保护？
Cypher：MATCH (lb:iEngageProd:LoadBalancer)-[:LOAD_BALANCES]->(ws:iEngageProd:WebServer) RETURN lb.name AS 负载均衡器, ws.name AS Web服务器, ws.ip AS IP地址

问题：显示从F5到内部服务的完整调用链路
Cypher：MATCH path = (f5:iEngageProd:EdgeNode {name: 'F5'})-[:CONNECTS_TO*1..5]->(target:iEngageProd:Internal) RETURN [node in nodes(path) | node.name] AS 调用链路, length(path) AS 跳数

问题：查询AIA Azure VNET包含哪些资源
Cypher：MATCH (vnet:iEngageProd:VNET {name: 'AIA Azure VNET'})-[:CONTAINS]->(resource) RETURN resource.name AS 资源名称, labels(resource)[1] AS 资源类型, resource.ip AS IP地址, resource.subnet AS 子网

问题：哪些服务通过Group SMTP发送邮件？
Cypher：MATCH (svc:iEngageProd)-[:SENDS_EMAIL_VIA]->(smtp:iEngageProd:Email {name: 'Group SMTP'}) RETURN svc.name AS 服务名称, svc.ip AS IP地址, labels(svc)[1] AS 类型

问题：查询HKAZEPLWB0004的详细信息
Cypher：MATCH (n:iEngageProd:WebServer {name: 'HKAZEPLWB0004'}) RETURN n.name AS 名称, n.ip AS IP地址, n.subnet AS 子网, labels(n) AS 标签

问题：哪些NSG在保护Web服务器？
Cypher：MATCH (nsg:iEngageProd:NSG)-[:SECURES]->(ws:iEngageProd:WebServer) RETURN nsg.name AS 安全组, ws.name AS Web服务器, ws.ip AS IP地址

问题：查询所有外部服务
Cypher：MATCH (n:iEngageProd:External) RETURN n.name AS 名称, labels(n) AS 标签, n.ip AS IP地址, n.domain AS 域名

问题：显示完整的网络拓扑
Cypher：MATCH (n:iEngageProd)-[r:CONNECTS_TO]->(m:iEngageProd) RETURN n.name AS 源节点, type(r) AS 关系, m.name AS 目标节点, labels(n)[1] AS 源类型, labels(m)[1] AS 目标类型

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
