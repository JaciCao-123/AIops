#!/usr/bin/env python3
import json
from neo4j import GraphDatabase

NEO4J_URI = "bolt://8.136.226.231:30687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"

DATA_FILE = "/Users/jaci-j/AIops/knowledge_graph/neo4j_query_table_data_2026-3-20.json"

def create_constraints(tx):
    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Server) REQUIRE s.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (m:Middleware) REQUIRE m.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:NetworkDevice) REQUIRE n.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (st:Storage) REQUIRE st.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Database) REQUIRE d.name IS UNIQUE",
    ]
    for constraint in constraints:
        try:
            tx.run(constraint)
        except Exception as e:
            print(f"Constraint warning: {e}")

def create_node(tx, labels, properties):
    label_str = ":".join(labels)
    query = f"""
    MERGE (n:{label_str} {{name: $name}})
    SET n += $props
    """
    tx.run(query, name=properties.get("name"), props=properties)

def create_relationship(tx, start_name, start_labels, rel_type, rel_props, end_name, end_labels):
    start_label = start_labels[-1]
    end_label = end_labels[-1]
    query = f"""
    MATCH (a:{start_label} {{name: $start_name}})
    MATCH (b:{end_label} {{name: $end_name}})
    MERGE (a)-[r:{rel_type}]->(b)
    SET r += $props
    """
    tx.run(query, start_name=start_name, end_name=end_name, props=rel_props)

def import_data():
    print(f"Loading data from {DATA_FILE}...")
    with open(DATA_FILE, 'r') as f:
        data = json.load(f)
    
    print(f"Found {len(data)} records")
    
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    nodes_created = set()
    relationships_created = set()
    
    with driver.session() as session:
        print("Creating constraints...")
        session.execute_write(create_constraints)
        
        print("Importing nodes and relationships...")
        for record in data:
            n = record.get("n", {})
            r = record.get("r", {})
            m = record.get("m", {})
            
            n_labels = n.get("labels", [])
            n_props = n.get("properties", {})
            n_name = n_props.get("name")
            
            m_labels = m.get("labels", [])
            m_props = m.get("properties", {})
            m_name = m_props.get("name")
            
            rel_type = r.get("type")
            rel_props = r.get("properties", {})
            
            if n_name and n_labels:
                node_key = (tuple(n_labels), n_name)
                if node_key not in nodes_created:
                    session.execute_write(create_node, n_labels, n_props)
                    nodes_created.add(node_key)
            
            if m_name and m_labels:
                node_key = (tuple(m_labels), m_name)
                if node_key not in nodes_created:
                    session.execute_write(create_node, m_labels, m_props)
                    nodes_created.add(node_key)
            
            if n_name and m_name and rel_type:
                rel_key = (n_name, rel_type, m_name)
                if rel_key not in relationships_created:
                    session.execute_write(
                        create_relationship, 
                        n_name, n_labels, rel_type, rel_props, m_name, m_labels
                    )
                    relationships_created.add(rel_key)
    
    driver.close()
    
    print(f"\nImport completed!")
    print(f"  Nodes created: {len(nodes_created)}")
    print(f"  Relationships created: {len(relationships_created)}")

if __name__ == "__main__":
    import_data()
