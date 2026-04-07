#!/usr/bin/env python3
"""
查询Neo4j中的医疗知识图谱数据
"""

import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(env_path)


def query_medical_graph():
    """查询医疗知识图谱"""
    uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    user = os.getenv('NEO4J_USER', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD', 'password')

    driver = GraphDatabase.driver(uri, auth=(user, password))

    print('='*60)
    print('医疗知识图谱查询')
    print('='*60 + '\n')

    with driver.session() as session:
        node_count = session.run('''
            MATCH (n:MedicalNode)
            RETURN count(n) AS count
        ''').single()['count']

        print(f'📊 医疗节点总数: {node_count}\n')

        print('📦 所有医疗节点：')
        result = session.run('''
            MATCH (n:MedicalNode)
            RETURN n.name AS name, n.type AS type
            ORDER BY n.type, n.name
        ''')
        for record in result:
            print(f'   - {record["name"]} ({record["type"]})')

        print('\n🔗 医疗关系：')
        result = session.run('''
            MATCH (s:MedicalNode)-[r]->(t:MedicalNode)
            RETURN s.name AS source, type(r) AS relation, t.name AS target
            ORDER BY s.name, type(r), t.name
            LIMIT 50
        ''')
        for record in result:
            print(f'   - {record["source"]} -> {record["relation"]} -> {record["target"]}')

        print('\n📈 按类型统计：')
        result = session.run('''
            MATCH (n:MedicalNode)
            RETURN n.type AS type, count(n) AS count
            ORDER BY count DESC
        ''')
        for record in result:
            print(f'   - {record["type"]}: {record["count"]}')

        print('\n' + '='*60)
        print('💡 提示：在Neo4j Browser中执行以下查询查看图谱：')
        print('   MATCH (n:MedicalNode) RETURN n LIMIT 100')
        print('   MATCH (n:MedicalNode)-[r]->(m:MedicalNode) RETURN n, r, m LIMIT 50')
        print('='*60 + '\n')

    driver.close()


if __name__ == '__main__':
    query_medical_graph()
