import time
import requests
import redis
from datetime import datetime
from pymongo import MongoClient
from cassandra.cluster import Cluster
from neo4j import GraphDatabase

#---------------------------------------
#  CONFIGURAÇÕES
#---------------------------------------

MOEDAS = ["BTCUSDT","ETHUSDT"] # lista que sera iterada no loop While para verificar as duas moedas
TTL = 10 # Fixa o TTL (Time to Live) em 10 segundos

#---------------------------------------
#  CONEXÃO REDIS
#---------------------------------------

try:
    r = redis.Redis(host = "localhost", port = 6379, decode_responses= True)
    r.ping()
    print("[REDIS] ✅")
except Exception as e:
    print("[REDIS] ❌ ERRO: ", e)
    exit()


#---------------------------------------
#  CONEXÃO MONGODB
#---------------------------------------

try:
    mongo_client = MongoClient("mongodb://root:root@localhost:27017/")
    mongo_client.admin.command("ping")
    print("[MONGO] ✅!")

    db = mongo_client["mercado"]
    collection = db["cotações"]

except Exception as e:
    print("[MONGO] ❌  ERRO: ", e)
    exit()

#---------------------------------------
#  CONEXÃO SCYLLA
#---------------------------------------

try:
    print('[SCYLLA] Conectando...')
    cluster = Cluster(["localhost"])
    session = cluster.connect()
    print("[SCYLLA] ✅")

    # Cria Keyspace se não existir
    session.execute("""
        CREATE KEYSPACE IF NOT EXISTS mercado
        WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1}
    """)

    session.set_keyspace("mercado")

    # Cria tabela se não existir
    session.execute("""
        CREATE TABLE IF NOT EXISTS historico_precos(
            moeda text,
            data_coleta timestamp,
            valor double,
            PRIMARY KEY (moeda, data_coleta)
            ) WITH CLUSTERING ORDER BY (data_coleta DESC)
     """)

except Exception as e:
    print("[SCYLLA] Erro ao conectar:", e)
    exit()

#---------------------------------------
#  CONEXÃO NEO4JAY
#---------------------------------------
try:
    driver = GraphDatabase.driver(
        "bolt://localhost:7687",
        auth=("neo4j", "password")
    )
    print("[NEO4J] ✅")
except Exception as e:
    print("[NEO4J] Erro ao conectar:", e)
    exit()


#---------------------------------------
#  FUNÇÃO PARA CONECTAR API
#---------------------------------------

def consultar_api():
    response = requests.get(API_URL, timeout=5)
    return response.json()

# ----------------------------
# DEFININDO VARIÁVEIS
# ----------------------------
ultimos_precos = {} # criando dicionário para armazenar valores dos preços em memória


#---------------------------------------
#  SETUP INICIAL DO GRAFO
#---------------------------------------

# investidores = ["João","Ana","Carlos"]

with driver.session() as session_neo:
    
    # Criar os nós das moedas
    for moeda in MOEDAS:
        session_neo.run("""
            MERGE (:Moeda {codigo: $codigo})
        """, codigo=moeda)

    # Criar investidores 
    session_neo.run(""" 
        MERGE (a:Investidor {nome: 'João'})
        MERGE (b:Investidor {nome:'Ana'})
        MERGE (c:Investidor {nome:'Carlos'})
        """)
    
    # Criar relacionamentos
    session_neo.run("""
        MATCH (a:Investidor {nome:'João'}), (btc:Moeda {codigo: 'BTCUSDT'})
        MERGE (a)-[:ACOMPANHA]->(btc)
        """)
    
    session_neo.run("""
        MATCH (b:Investidor {nome:'Ana'}), (eth:Moeda {codigo: 'ETHUSDT'})
        MERGE (b)-[:ACOMPANHA]->(eth)
        """)

    session_neo.run("""
        MATCH (c:Investidor {nome:'Carlos'}),
               (btc:Moeda {codigo:'BTCUSDT'}),
               (eth: Moeda {codigo:'ETHUSDT'})
        MERGE (c)-[:ACOMPANHA]->(btc)
        MERGE (c)-[:ACOMPANHA]->(eth)
        """)

#---------------------------------------
#  LOOP PRINCIPAL
#---------------------------------------

print("INICIANDO MONITORAMENTO... \n")

try:
    while True:

        for SYMBOL in MOEDAS:
            investidores = []
            API_URL = f"https://api.binance.com/api/v3/ticker/price?symbol={SYMBOL}"
            print(f"Consultando preço do {SYMBOL}...")

            preco_cache = r.get(SYMBOL)# retorna valor armazenado na chave SYMBOL   

            if preco_cache:
                print("[REDIS] Cache Hit!")
                preco_atual = float(preco_cache)
            else:
                print("[REDIS] Cache Miss! Consultando API..")

                payload = consultar_api()

                preco_atual = float(payload["price"])

                #Atualiza REDIS
                r.setex(SYMBOL, TTL, preco_atual) #armazena o valor da variável preço atual na chave SYMBOL e define TTL de 10 segundos para essa chave

                # Salvando no Mongo (Data Lake)
                try:
                    payload["data_coleta"] = datetime.now()
                    collection.insert_one(payload)
                    print("[MONGO] Payload salvo no Data Lake.")
                except Exception as e:
                    print("[MONGO] Erro ao salvar:", e)

                # Salvando no Scylla (Série Temporal)
                try:
                    session.execute("""
                        INSERT INTO historico_precos (moeda, data_coleta, valor)
                        VALUES (%s, %s, %s)
                                    
                        """, (SYMBOL, datetime.now(), preco_atual))
                    print("[SCYLLA] Preço gravado na série temporal.")

                except Exception as e:
                    print("[SCYLLA] Erro ao inserir:", e)

            # try:
            #     with driver.session() as session_neo:
            #         result = session_neo.run("""
            #             MATCH (i:Investidor)-[:ACOMPANHA]->(m:Moeda {codigo:$codigo})
            #             RETURN i.nome AS nome
            #         """, codigo = SYMBOL)

            #         investidores = [r["nome"] for r in result]

            #         if investidores:
            #             print(f"[NEO4J] Notificar: {','.join(investidores)}")
            # except Exception as e:
            #     print("[NEO4J] Erro ao tentar localizar investidores:", e)

            # Lógica visual da volatilidade
            if SYMBOL not in ultimos_precos:
                indicador = "⚪ (Primeira coleta)"
                ocorreu_variacao = False
            else:
                if preco_atual > ultimos_precos[SYMBOL]:
                    indicador = "🟢 (Subiu)"
                    ocorreu_variacao = True
                elif preco_atual < ultimos_precos[SYMBOL]:
                    indicador = "🔴 (Caiu)"
                    ocorreu_variacao = True
                else:
                    indicador = "⚪ (Estável)"
                    ocorreu_variacao = False

            ultimos_precos[SYMBOL] = preco_atual

            

            # Notificação dos investidores

            if ocorreu_variacao:

                try:
                    with driver.session() as session_neo:
                        result = session_neo.run("""
                            MATCH (i:Investidor)-[:ACOMPANHA]->(m:Moeda {codigo:$codigo})
                            RETURN i.nome AS nome""", codigo=SYMBOL)
                        
                        investidores = [registro["nome"] for registro in result]


                except Exception as e:
                    print("[NEO4J] Erro ao localizar investidores:", e)

            # Exibindo logs
            print(f"{SYMBOL}: $ {preco_atual:.2f} {indicador}")

            if investidores: #checa se existem investidores a serem notificados
                print(f"[NEO4J] 🔔 Notificar: {','.join(investidores)}")
                investidores = None # esvaziando variável para a próxima iteração
            
            print("-" * 50)

        time.sleep(5)

except KeyboardInterrupt:
    print("\n MONITORAMENTO ENCERRADO!")

        