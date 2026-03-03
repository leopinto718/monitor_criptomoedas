# 📊 Plataforma de Inteligência de Mercado em Tempo Real

### 💾 Ecossistema NoSQL com Persistência Poliglota

Projeto desenvolvido para a disciplina **Banco de Dados NoSQL** com o objetivo de implementar uma arquitetura baseada em **Persistência Poliglota**, utilizando múltiplos bancos NoSQL para resolver diferentes tipos de problemas dentro do mesmo sistema.

---

## 🚀 Visão Geral do Projeto

Este sistema monitora preços de criptomoedas em tempo real (Bitcoin e Ethereum) utilizando a API pública da Binance e distribui os dados em **quatro bancos NoSQL**, cada um com uma finalidade específica:

| Banco        | Função                                    |
| ------------ | ----------------------------------------- |
| **Redis**    | Cache de baixa latência                   |
| **MongoDB**  | Data Lake (armazenamento bruto do JSON)   |
| **ScyllaDB** | Série temporal otimizada                  |
| **Neo4j**    | Rede de investidores e sistema de alertas |

O sistema roda continuamente e executa as seguintes etapas:

1. 🔎 Verifica se o preço está no cache (Redis)
2. 🌐 Se não estiver, consulta a API da Binance
3. 🗄️ Salva o JSON bruto no MongoDB
4. 📈 Insere o preço na série temporal (ScyllaDB)
5. 🔔 Consulta no Neo4j quais investidores acompanham a moeda
6. 📊 Exibe indicador visual de volatilidade

---

## 🏗️ Arquitetura do Sistema

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

## 💰 API Utilizada

### Binance Public API (Mercado Cripto)

* Bitcoin:
  `https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT`

* Ethereum:
  `https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT`

**TTL configurado no Redis:** `10 segundos`

---

## 🗃️ Modelagem dos Bancos

### 🔴 Redis (Cache)

* Chave: `BTCUSDT` ou `ETHUSDT`
* Valor: preço atual
* TTL: 10 segundos

Implementa lógica de:

* ✅ Cache Hit
* ❌ Cache Miss

---

### 🟢 MongoDB (Data Lake)

* Database: `mercado`
* Collection: `cotações`
* Documento salvo:

```json
{
  "symbol": "BTCUSDT",
  "price": "65000.00",
  "data_coleta": "2026-03-03T18:00:00"
}
```

Armazena o JSON bruto retornado pela API com timestamp adicional.

---

### 🔵 ScyllaDB (Série Temporal)

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
* Clustering Key → `data_coleta DESC`
* Otimizado para consultas por moeda ordenadas por data

---

### 🟡 Neo4j (Grafo de Investidores)

#### Nós:

* `:Investidor`
* `:Moeda`

#### Relacionamento:

* `(:Investidor)-[:ACOMPANHA]->(:Moeda)`

Exemplo de consulta usada para notificação:

```cypher
MATCH (i:Investidor)-[:ACOMPANHA]->(m:Moeda {codigo:$codigo})
RETURN i.nome AS nome
```

---

## 👥 Investidores Simulados

Criados automaticamente no setup inicial:

* João
* Ana
* Carlos

Relacionamentos:

* João → BTCUSDT
* Ana → ETHUSDT
* Carlos → BTCUSDT e ETHUSDT

---

## 📊 Lógica de Volatilidade (Bônus Implementado)

O sistema compara o preço atual com o último preço armazenado em memória e exibe:

* 🟢 Subiu
* 🔴 Caiu
* ⚪ Estável

Exemplo de log:

```
BTCUSDT: $ 65000.00 🟢 (Subiu)
[NEO4J] 🔔 Notificar: João, Carlos
--------------------------------------------------
```

---

## 🐳 Como Executar o Projeto

### 1️⃣ Subir os containers

```bash
docker-compose up -d
```

Aguarde todos os bancos inicializarem.

---

### 2️⃣ Instalar dependências

```bash
pip install -r requirements.txt
```

---

### 3️⃣ Executar o monitor

```bash
python monitor.py
```

Para encerrar:

```
CTRL + C
```

---

## 📦 Estrutura do Repositório

```
📁 projeto-nosql/
│
├── monitor.py
├── docker-compose.yml
├── requirements.txt
└── README.md
```

