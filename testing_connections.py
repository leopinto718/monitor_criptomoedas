import time
import redis
from pymongo import MongoClient
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from neo4j import GraphDatabase

print("\n=======================")
print(" TESTANDO CONEXÕES NOSQL ")
print("=========================\n")


#---------------------------------------
#  REDIS
#---------------------------------------

try:
    r = redis.Redis(host = "localhost", port = 6379, decode_responses= True)
    r.ping()
    print("[REDIS] ✅")
except Exception as e:
    print("[REDIS] ❌ ERRO: ", e)

#---------------------------------------
#  MONGODB
#---------------------------------------

try:
    mongo_client = MongoClient("mongodb://root:root@localhost:27017/")
    mongo_client.admin.command("ping")
    print("[MONGO] ✅!")
except Exception as e:
    print("[MONGO] ❌  ERRO: ", e)

#---------------------------------------
#  SCYLLADB
#---------------------------------------

try:
    print("[SCYLLA] Tentando conectar...")

    cluster = Cluster(["localhost"])
    session = cluster.connect()

    # Executa uma query simples para testar conexão
    row = session.execute("SELECT release_version FROM system.local").one()

    print(f"[SCYLLA] ✅! Versão: {row.release_version}")

except Exception as e:
    print("[SCYLLA] ❌ ERRO:", e)

#---------------------------------------
#  NEO4J
#---------------------------------------

try:
    driver = GraphDatabase.driver(
        "bolt://localhost:7687",
        auth=("neo4j", "password")
    )
    with driver.session() as session:
        result = session.run("RETURN 'Neo4j OK' AS status")
        print("[NEO4J] ✅!")
except Exception as e:
    print("[NEO4J] ❌ ERRO:", e)