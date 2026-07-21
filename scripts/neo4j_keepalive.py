"""每日 Ping Neo4j Aura，防止免费实例因 3 天无活动被暂停。"""
import os
import sys
from pathlib import Path
from datetime import datetime
from neo4j import GraphDatabase

# 从项目 .env 读取配置
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
if ENV_FILE.exists():
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

URI = os.getenv("NEO4J_URI", "neo4j+s://c60acc31.databases.neo4j.io")
USER = os.getenv("NEO4J_USER", "c60acc31")
PASSWORD = os.getenv("NEO4J_PASSWORD", "")
DATABASE = os.getenv("NEO4J_DATABASE", "c60acc31")

def ping():
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    try:
        with driver.session(database=DATABASE) as s:
            result = s.run("MATCH (n) RETURN count(n) as cnt").single()
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] OK — {result['cnt']} nodes")
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] FAIL — {e}", file=sys.stderr)
    finally:
        driver.close()

if __name__ == "__main__":
    ping()
