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


#---------------------------------------------------------------
#  DEFININDO FUNÇÕES DE CONEXÃO COM OS BANCOS
#---------------------------------------------------------------

def conectar_redis():
    try:
        r = redis.Redis(host = "localhost", port = 6379, decode_responses= True)
        r.ping()
        print("[REDIS] ✅")
        return r
    except Exception as e:
        print("[REDIS] ❌ ERRO: ", e)
        exit()

def conectar_mongo():
    try:
        mongo_client = MongoClient("mongodb://root:root@localhost:27017/")
        mongo_client.admin.command("ping")
        print("[MONGO] ✅!")

        db = mongo_client["mercado"]
        return db["cotações"]

    except Exception as e:
        print("[MONGO] ❌  ERRO: ", e)
        exit()

def conectar_scylla():
    try:
        print('[SCYLLA] Conectando...')
        cluster = Cluster(["localhost"])
        session = cluster.connect()
        

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

        print("[SCYLLA] ✅")
        return session
        

    except Exception as e:
        print("[SCYLLA] Erro ao conectar:", e)
        exit()

def conectar_neo4j():
    try:
        driver = GraphDatabase.driver(
            "bolt://localhost:7687",
            auth=("neo4j", "password")
        )
        print("[NEO4J] ✅")
        return driver
    except Exception as e:
        print("[NEO4J] Erro ao conectar:", e)
        exit()

#---------------------------------------------------------------
#  DEFININDO FUNÇÃO QUE FAZ O SETUP DO GRAFO NO NEO4J
#---------------------------------------------------------------

def setup_grafo(driver, moedas):
    with driver.session() as session:
        # Criar os nós das moedas
        for moeda in moedas:
            session.run("""
                MERGE (:Moeda {codigo: $codigo})
                """, codigo=moeda)

        # Criar os nós de invstidores    
        investidores = ["João",  "Ana", "Carlos"]

        for nome in investidores:
            session.run("MERGE (:Investidor {nome: $nome})", nome=nome)

        # Criar relacionamentos
        session.run("""
            MATCH (a:Investidor {nome:'João'}), (btc:Moeda {codigo: 'BTCUSDT'})
            MERGE (a)-[:ACOMPANHA]->(btc)
            """)
    
        session.run("""
            MATCH (b:Investidor {nome:'Ana'}), (eth:Moeda {codigo: 'ETHUSDT'})
            MERGE (b)-[:ACOMPANHA]->(eth)
            """)

        session.run("""
            MATCH (c:Investidor {nome:'Carlos'}),
                (btc:Moeda {codigo:'BTCUSDT'}),
                (eth: Moeda {codigo:'ETHUSDT'})
            MERGE (c)-[:ACOMPANHA]->(btc)
            MERGE (c)-[:ACOMPANHA]->(eth)
            """)
        
#---------------------------------------------------------------
#  DEFININDO FUNÇÕES DE PERSISTÊNCIA
#---------------------------------------------------------------

def salvar_mongo(collection, payload):
    try:
        payload["data_coleta"] = datetime.now()
        collection.insert_one(payload)
        print("[MONGO] Payload salvo no Data Lake.")
    except Exception as e:
        print("[MONGO] ERRO: ", e)

def salvar_scylla(session, symbol, preco):
    try:
        session.execute("""
            INSERT INTO historico_precos (moeda, data_coleta, valor)
            VALUES (%s, %s, %s)
                        
            """, (symbol, datetime.now(), preco))
        print("[SCYLLA] Preço gravado na série temporal.")
    except Exception as e:
        print("[SCYLLA] Erro ao inserir:", e)

#---------------------------------------------------------------
#  DEFININDO FUNÇÃO PARA A LÓGICA DE VOLATILIDADE
#--------------------------------------------------------------- 

def calcular_volatilidade(symbol, preco_atual, ultimos_precos):
    if symbol not in ultimos_precos:
        return "⚪ (Primeira coleta)", False
    
    preco_anterior = ultimos_precos[symbol]

    if preco_atual > preco_anterior:
        return "🟢 (Subiu)", True
    elif preco_atual < preco_anterior:
        return "🔴 (Caiu)", True
    else:
        return "⚪ (Estável)", False

#---------------------------------------------------------------------
#  DEFININDO FUNÇÃO DE QUE RETORNA OS INVESTIDORES A SEREM NOTIFICADOS
#--------------------------------------------------------------------- 

def investidores_para_notificar(driver, symbol):
    try:
        with driver.session() as session:
            result = session.run("""
             MATCH (i:Investidor)-[r:ACOMPANHA]-> (m:Moeda {codigo:$codigo})
             SET r.ultima_notificacao = datetime() 
             RETURN i.nome AS nome
            """, codigo=symbol) 

            return [registro["nome"] for registro in result]
        
    except Exception as e:
        print("[NEO4J] ERRRO ao localizar investidores:", e)
        # return [] # por que é preciso?
    
#---------------------------------------------------------------------
#  DEFININDO FUNÇÃO PARA O MONITORAMENTO 
#--------------------------------------------------------------------- 
def processar_moeda(symbol, r, collection, session, driver, ultimos_precos):
    print(f"Consultando preço do {symbol}...")

    preco_cache = r.get(symbol)

    # verifica o cache do Redis
    if preco_cache:
        print("[REDIS] Cache Hit!")
        print("-" * 50)
        return
    
    # Caso não haja um valor armazenado em cache, vamos consultar a API
    print("[REDIS] Cache Miss! Consultando API...")

    response = requests.get(
        f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}",
        timeout=5)
    
    payload = response.json()
    preco_atual = float(payload["price"])

    r.setex(symbol, TTL, preco_atual)

    salvar_mongo(collection, payload) #Mongo não precisa indicar o symbol?
    salvar_scylla(session, symbol, preco_atual)

    indicador, ocorreu_variacao = calcular_volatilidade(symbol, preco_atual, ultimos_precos)

    # print("\n VALOR DA VARIÁVEL ocorreu_variacao:")
    # print(ocorreu_variacao)

    ultimos_precos[symbol] = preco_atual

    print(f"{symbol}: $ {preco_atual:.2f} {indicador}")

    if ocorreu_variacao:
        investidores = investidores_para_notificar(driver, symbol)
        if investidores:
            print(f"[NEO4J] 🔔 Notificar: {','.join(investidores)}")

    print("-" * 50)

#---------------------------------------------------------------------
#                      FUNÇÃO PRINCIPAL
#--------------------------------------------------------------------- 

def main():
    r = conectar_redis()
    collection = conectar_mongo()
    session = conectar_scylla()
    driver = conectar_neo4j()

    setup_grafo(driver, MOEDAS)

    ultimos_precos = {}

    print('INICIANDO MONITORAMENTO... \n')

    try:
        while True:
            for symbol in MOEDAS:
                processar_moeda(
                    symbol, r, collection, session, driver, ultimos_precos
                )
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nMONITORAMENTO ENCERRADO!")


if __name__ == "__main__":
    main()