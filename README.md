#  Monitoramento de criptomoedas em tempo real

##  Ecossistema NoSQL com Persistência Poliglota

Projeto desenvolvido para a disciplina **Banco de Dados NoSQL** com o objetivo de implementar uma arquitetura baseada em **Persistência Poliglota**, utilizando múltiplos bancos NoSQL para resolver diferentes tipos de problemas dentro do mesmo sistema.

---

#  Visão Geral do Projeto

O sistema monitora em tempo real os preços de:

* **Bitcoin (BTCUSDT)**
* **Ethereum (ETHUSDT)**

Utilizando a API pública da Binance.

Os dados são distribuídos entre **quatro bancos NoSQL**, cada um com responsabilidade específica:

| Banco        | Função                                          |
| ------------ | ----------------------------------------------- |
| **Redis**    | Cache de baixa latência com TTL                 |
| **MongoDB**  | Data Lake (armazenamento bruto do JSON da API)  |
| **ScyllaDB** | Série temporal por moeda                        |
| **Neo4j**    | Grafo de investidores e sistema de notificações |

---

# 🏗️ Arquitetura do Sistema

```
                ┌───────────────┐
                │  API Binance  │
                └───────┬───────┘
                        │
                ┌───────▼───────┐
                │     Redis     │  ← Cache (TTL 10s)
                └───────┬───────┘
                        │
        ┌───────────────┼────────────────┐
        │               │                │
 ┌──────▼──────┐ ┌──────▼──────┐ ┌───────▼───────┐
 │   MongoDB   │ │  ScyllaDB   │ │     Neo4j     │
 │  Data Lake  │ │ Série Temp  │ │ Grafo Alertas │
 └─────────────┘ └─────────────┘ └───────────────┘
```

---

#  Arquitetura do Código (Modular)

O sistema foi estruturado com **separação de responsabilidades**, utilizando funções isoladas:

###  Funções de Conexão

* `conectar_redis()`
* `conectar_mongo()`
* `conectar_scylla()`
* `conectar_neo4j()`

###  Setup do Grafo

* `setup_grafo(driver, moedas)`

###  Persistência

* `salvar_mongo(collection, payload)`
* `salvar_scylla(session, symbol, preco)`

###  Regra de Negócio

* `calcular_volatilidade(symbol, preco_atual, ultimos_precos)`
* `investidores_para_notificar(driver, symbol)`

###  Processamento

* `processar_moeda(...)`
* `main()`

---

#  API Utilizada

### Binance Public API

* Bitcoin:

  ```
  https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT
  ```

* Ethereum:

  ```
  https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT
  ```

TTL configurado no Redis: **10 segundos**

---

#  Modelagem dos Bancos

---

## 🔴 Redis (Cache)

* Chave: `BTCUSDT` ou `ETHUSDT`
* Valor: preço atual
* TTL: 10 segundos

Implementa lógica de:

* ✅ Cache Hit
* ❌ Cache Miss

Se houver Cache Hit, a API não é consultada.

---

## 🟢 MongoDB (Data Lake)

* Database: `mercado`
* Collection: `cotações`

Documento salvo:

```json
{
  "symbol": "BTCUSDT",
  "price": "65000.00",
  "data_coleta": "2026-03-03T18:00:00"
}
```

Armazena o JSON retornado pela API com timestamp adicional.

---

## 🔵 ScyllaDB (Série Temporal)

**Keyspace:** `mercado`

```sql
CREATE TABLE historico_precos(
    moeda text,
    data_coleta timestamp,
    valor double,
    PRIMARY KEY (moeda, data_coleta)
) WITH CLUSTERING ORDER BY (data_coleta DESC);
```

* Partition Key → `moeda`
* Clustering Key → `data_coleta`
* Otimizado para consultas por moeda ordenadas por data

---

## 🟡 Neo4j (Grafo de Investidores)

### Nós

* `:Investidor`
* `:Moeda`

### Relacionamento

```
(:Investidor)-[:ACOMPANHA]->(:Moeda)
```

### Atualização Automática

Quando ocorre variação de preço, o sistema:

* Consulta os investidores que acompanham a moeda
* Atualiza a propriedade `ultima_notificacao` no relacionamento

Consulta utilizada:

```cypher
MATCH (i:Investidor)-[r:ACOMPANHA]->(m:Moeda {codigo:$codigo})
SET r.ultima_notificacao = datetime()
RETURN i.nome AS nome
```

---

#  Investidores Simulados

Criados automaticamente no setup inicial:

* João → BTCUSDT
* Ana → ETHUSDT
* Carlos → BTCUSDT e ETHUSDT

---

#  Lógica de Volatilidade

O sistema compara o preço atual com o último preço armazenado em memória.

Retornos possíveis:

* 🟢 Subiu → Notifica investidores
* 🔴 Caiu → Notifica investidores
* ⚪ Estável → Não notifica
* ⚪ Primeira coleta → Não notifica

Exemplo:

```
BTCUSDT: $ 65000.00 🟢 (Subiu)
[NEO4J] 🔔 Notificar: João, Carlos
--------------------------------------------------
```

---

# 🐳 Como Executar o Projeto

## ⚠️ IMPORTANTE — Versão do Python

Este projeto deve ser executado com:

```
Python 3.11 ou inferior
```

### ❗ Motivo

O pacote `cassandra-driver` (utilizado pelo ScyllaDB) não é compatível com Python 3.12+, pois o módulo `asyncore` foi removido nessa versão.

Se utilizar Python 3.12+, ocorrerá erro:

```
cassandra.DependencyException:
Unable to import asyncore module
```

---

## 🔎 Verificar versão do Python

```bash
python --version
```

---

## 🧪 Criar ambiente virtual (recomendado)

```bash
python3.11 -m venv venv
```

Ativar:

**Windows**

```bash
venv_nosql\Scripts\activate
```

**Linux/Mac**

```bash
source venv_nosql/bin/activate
```

---

## 1️⃣ Subir containers

```bash
docker-compose up -d
```

Aguarde todos os serviços inicializarem.

---

## 2️⃣ Instalar dependências

```bash
pip install -r requirements.txt
```

---

## 3️⃣ Executar o monitor

```bash
python monitor.py
```

---

## ⛔ Encerrar o sistema

Pressione:

```
CTRL + C
```

---

# 📦 Estrutura do Repositório

```
📁 projeto-nosql/
│
├── monitor.py
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---
