import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import httpx
from neo4j import GraphDatabase
from dotenv import load_dotenv
import openai

load_dotenv()

app = FastAPI(title="Knowledge Graph API", version="1.0.0")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_API_BASE = os.getenv("LLM_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen-plus")

class QueryRequest(BaseModel):
    query: str
    service: Optional[str] = None

class Text2CypherRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    query: str
    cypher: Optional[str] = None
    result: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None

def get_neo4j_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def get_llm_client():
    return openai.OpenAI(api_key=LLM_API_KEY, base_url=LLM_API_BASE)

PROMPT_TEMPLATE = '''你是一个Neo4j图数据库查询专家。请将用户的自然语言问题转换为Cypher查询语句。

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

现在请转换以下问题：
{question}

请直接返回Cypher查询语句，不要包含其他内容。'''

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "knowledge-graph-api"}

@app.get("/api/query")
async def query_knowledge_graph(service: str = None, query: str = None):
    try:
        driver = get_neo4j_driver()
        
        with driver.session() as session:
            if service:
                result = _query_service_info(session, service)
            elif query:
                result = _query_by_natural_language(session, query)
            else:
                return {"error": "请提供 service 或 query 参数"}
        
        driver.close()
        
        return {
            "query": query or f"查询 {service} 的详细信息",
            "result": result,
            "source": "neo4j_kg"
        }
        
    except Exception as e:
        return {"query": query or service, "error": str(e)}

@app.post("/api/text2cypher", response_model=QueryResponse)
async def text_to_cypher(request: Text2CypherRequest):
    try:
        client = get_llm_client()
        
        prompt = PROMPT_TEMPLATE.replace('{question}', request.question)
        
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        cypher = response.choices[0].message.content.strip()
        cypher = cypher.strip('```cypher').strip('```').strip()
        
        driver = get_neo4j_driver()
        with driver.session() as session:
            result = session.run(cypher)
            records = [dict(record) for record in result]
        driver.close()
        
        return QueryResponse(
            query=request.question,
            cypher=cypher,
            result=records
        )
        
    except Exception as e:
        return QueryResponse(
            query=request.question,
            error=str(e)
        )

@app.get("/api/topology")
async def get_topology(service: str = None, depth: int = 2):
    try:
        driver = get_neo4j_driver()
        
        with driver.session() as session:
            if service:
                result = session.run(f"""
                    MATCH path = (s {{name: $name}})-[*1..{depth}]-(related)
                    RETURN s, related, relationships(path) as rels
                """, name=service)
            else:
                result = session.run(f"""
                    MATCH path = (a)-[r:DEPENDS_ON|RUNS_ON|CONNECTED_TO*1..{depth}]-(b)
                    RETURN a, b, relationships(path) as rels
                    LIMIT 50
                """)
            
            nodes = {}
            edges = []
            
            for record in result:
                if record.get("s") or record.get("a"):
                    source = record.get("s") or record.get("a")
                    source_id = source.element_id
                    if source_id not in nodes:
                        nodes[source_id] = {
                            "id": source_id,
                            "label": dict(source).get("name", "unknown"),
                            "type": list(source.labels)[0] if source.labels else "Node",
                            "properties": dict(source)
                        }
                
                if record.get("related") or record.get("b"):
                    target = record.get("related") or record.get("b")
                    target_id = target.element_id
                    if target_id not in nodes:
                        nodes[target_id] = {
                            "id": target_id,
                            "label": dict(target).get("name", "unknown"),
                            "type": list(target.labels)[0] if target.labels else "Node",
                            "properties": dict(target)
                        }
        
        driver.close()
        
        return {
            "nodes": list(nodes.values()),
            "edges": edges,
            "source": "neo4j_kg"
        }
        
    except Exception as e:
        return {"nodes": [], "edges": [], "error": str(e)}

def _query_service_info(session, service_name: str) -> Dict:
    result = session.run("""
        MATCH (s {name: $name})
        OPTIONAL MATCH (s)-[r:DEPENDS_ON]->(dep)
        OPTIONAL MATCH (s)-[r2:RUNS_ON]->(run)
        OPTIONAL MATCH (s)-[r3:CONNECTED_TO]->(conn)
        RETURN s, 
               collect(DISTINCT {name: dep.name, type: labels(dep)[0]}) as dependencies,
               collect(DISTINCT {name: run.name, type: labels(run)[0]}) as runs_on,
               collect(DISTINCT {name: conn.name, type: labels(conn)[0]}) as connections
    """, name=service_name)
    
    record = result.single()
    if not record:
        return {"error": f"未找到服务: {service_name}"}
    
    node = dict(record["s"]) if record["s"] else {}
    
    return {
        "service": service_name,
        "properties": node,
        "dependencies": [d for d in record["dependencies"] if d["name"]],
        "runs_on": [r for r in record["runs_on"] if r["name"]],
        "connections": [c for c in record["connections"] if c["name"]]
    }

def _query_by_natural_language(session, query: str) -> Dict:
    query_lower = query.lower()
    
    if "依赖" in query or "depend" in query_lower:
        parts = query.split()
        for part in parts:
            if "service" in part.lower() or "-" in part:
                service_name = part.replace("的", "").replace("?", "").replace("？", "")
                result = session.run("""
                    MATCH (s {name: $name})-[r:DEPENDS_ON]->(dep)
                    RETURN s.name as service, collect({name: dep.name, type: labels(dep)[0]}) as deps
                """, name=service_name)
                record = result.single()
                if record:
                    return {"service": record["service"], "dependencies": record["deps"]}
    
    if "服务器" in query or "server" in query_lower:
        result = session.run("MATCH (s:Server) RETURN s.name as name, s.ip as ip LIMIT 10")
        servers = [{"name": r["name"], "ip": r["ip"]} for r in result]
        return {"servers": servers}
    
    if "数据库" in query or "database" in query_lower:
        result = session.run("MATCH (d:Database) RETURN d.name as name, d.type as type LIMIT 10")
        databases = [{"name": r["name"], "type": r["type"]} for r in result]
        return {"databases": databases}
    
    result = session.run("""
        MATCH (n) 
        WHERE n.name CONTAINS $keyword OR n.ip CONTAINS $keyword
        RETURN labels(n)[0] as type, n.name as name, n as properties 
        LIMIT 5
    """, keyword=query.split()[0] if query.split() else query)
    nodes = [{"type": r["type"], "name": r["name"], "properties": dict(r["properties"])} for r in result]
    
    return {"matched_nodes": nodes}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
