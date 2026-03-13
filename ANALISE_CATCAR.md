# Analise Completa do Site catcar.info

## 1. Visao Geral

O **catcar.info** e um catalogo online de pecas automotivas OEM (Original Equipment Manufacturer) fornecido pela empresa **Tradesoft**. O site permite buscar pecas originais por marca, modelo, ano, grupo de pecas e diagramas explodidos.

### Marcas Disponiveis
O site cobre as seguintes marcas:
- **Grupo VAG**: Audi, Volkswagen, Skoda, Seat
- **BMW Group**: BMW, Mini, Rolls-Royce
- **Mercedes Group**: Mercedes-Benz, Smart
- **Japonesas**: Toyota, Lexus, Nissan, Mazda, Mitsubishi, Subaru, Suzuki, Isuzu
- **Coreanas**: Hyundai, Kia
- **Francesas**: Renault, Dacia, Citroen
- **Americanas**: Chrysler, Ford
- **Outras**: Jaguar

---

## 2. Estrutura de URLs

### Padrao Base
```
https://www.catcar.info/{catalogo}/?lang=en
```

### Catalogos por Grupo de Marcas

| Catalogo (path) | Marcas Cobertas | URL |
|---|---|---|
| `/audivw/` | Audi, VW, Skoda, Seat | `catcar.info/audivw/?lang=en` |
| `/bmw/` | BMW, Mini, Rolls-Royce | `catcar.info/bmw/?lang=en` |
| `/mercedes/` | Mercedes-Benz, Smart | `catcar.info/mercedes/?lang=en` |
| `/toyota/` | Toyota, Lexus | `catcar.info/toyota/?lang=en` |
| `/renault/` | Renault, Dacia | `catcar.info/renault/?lang=en` |
| `/citroen/` | Citroen | `catcar.info/citroen/?lang=en` |
| `/hyundai/` | Hyundai | `catcar.info/hyundai/?lang=en` |
| `/kia/` | Kia | `catcar.info/kia/?lang=en` |
| `/nissan/` | Nissan | `catcar.info/nissan/?lang=en` |
| `/ford/` | Ford | `catcar.info/ford/?lang=en` |
| `/usa_oem/` | Pecas OEM USA | `catcar.info/usa_oem/?lang=en` |
| `/totalcatalog/` | Catalogo geral | `catcar.info/totalcatalog/?lang=en` |

### Parametro de Navegacao (l= Base64)

O site usa um parametro `l=` na URL que contem um **estado de navegacao codificado em Base64**. Quando decodificado, revela um JSON com a hierarquia de selecao:

```
Exemplo codificado:
l=c3RzPT17IjEwIjoiQnJhbmQiLCIyMCI6IlZXIn18fHN0PT0yMHx8YnJhbmQ9PXZ3

Decodificado:
sts==>{"10":"Brand","20":"VW"}||st==20||brand==vw
```

**Estrutura do estado decodificado:**
```
sts==>{ JSON com labels de navegacao }
||st=={ nivel atual }
||brand=={ marca selecionada }
||market=={ mercado }
||mdl=={ modelo }
||Epis=={ episodio/versao }
||Einsatz=={ ano }
||MainGroup=={ grupo principal }
||Bildtafel=={ numero do diagrama }
||Grafik=={ codigo do grafico }
```

---

## 3. Hierarquia de Navegacao

### Fluxo Geral (varia por marca)

```
Marca (Brand)
  └── Mercado/Regiao (Market)
        └── Modelo (Model)
              └── Ano/Faixa de Producao (Year/Production Range)
                    └── Grupo Principal (Main Group)
                          └── Subgrupo (Sub Group)
                                └── Diagrama de Pecas (Parts Diagram)
                                      └── Lista de Pecas (Parts List)
```

### Variacoes por Marca

| Marca | Primeiro Nivel | Segundo Nivel | Terceiro Nivel |
|---|---|---|---|
| **Audi/VW/Skoda/Seat** | Brand | Market/Model | Year/Engine |
| **BMW/Mini/Rolls** | Brand/Marque | Series/Model | Type/Year |
| **Mercedes/Smart** | Assortment Class | Model | Group |
| **Toyota/Lexus** | Market | Region | Model |
| **Renault/Dacia** | Model | Type | Manual/Category |
| **Citroen** | Model (Private/Commercial) | Type | Group |
| **Hyundai/Kia** | Model | Year | Group |

---

## 4. Dados Extraiveis

### 4.1 Dados de Veiculos
- **Marca** (Brand)
- **Modelo** (Model)
- **Variante/Tipo** (Type/Variant)
- **Ano de producao** (Production Year)
- **Motor** (Engine)
- **Mercado/Regiao** (Market/Region)

### 4.2 Dados de Pecas
- **Numero da peca OEM** (OEM Part Number)
- **Descricao da peca** (Part Description)
- **Grupo principal** (Main Group - ex: Motor, Carroceria, Suspensao)
- **Subgrupo** (Sub Group)
- **Diagrama/Ilustracao** (Diagram/Illustration reference)
- **Posicao no diagrama** (Position in diagram)
- **Quantidade** (Quantity per vehicle)
- **Observacoes/Notas** (Notes/Remarks)

### 4.3 Imagens/Diagramas
- **Diagramas explodidos** (Exploded view diagrams)
- **Referencias visuais** das pecas

---

## 5. Aspectos Tecnicos do Site

- **Servidor**: Nginx
- **Conteudo**: Renderizado dinamicamente (provavelmente server-side com JavaScript para interacao)
- **Idiomas**: Suporta `lang=en` (ingles) e `lang=ru` (russo)
- **API publica**: NAO possui API REST publica documentada
- **Integracao**: Oferece servico de integracao para lojas online (via Tradesoft)
- **Busca por VIN**: Suporta busca por codigo VIN (e FRAME para carros japoneses)
- **Sessao**: 1 requisicao = busca de pecas para 1 carro, valida por 24 horas, ate 200 pecas

---

## 6. Proposta de Arquitetura - API FastAPI + PostgreSQL

### Stack Tecnologico
- **Python 3.11+**
- **FastAPI** - Framework web async
- **PostgreSQL** - Banco de dados relacional
- **SQLAlchemy** - ORM
- **Alembic** - Migracoes de banco
- **Playwright (Python)** - Web scraping
- **Pydantic** - Validacao de dados
- **Celery + Redis** - Tarefas assincronas de scraping
- **Docker** - Containerizacao

### Modelo de Dados Proposto

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   brands     │     │   models     │     │  variants    │
├──────────────┤     ├──────────────┤     ├──────────────┤
│ id (PK)      │────>│ id (PK)      │────>│ id (PK)      │
│ name         │     │ brand_id(FK) │     │ model_id(FK) │
│ catalog_path │     │ name         │     │ year_from    │
│ group_type   │     │ market       │     │ year_to      │
│ created_at   │     │ region       │     │ engine       │
│ updated_at   │     │ created_at   │     │ type_code    │
└──────────────┘     └──────────────┘     │ created_at   │
                                          └──────┬───────┘
                                                 │
                     ┌──────────────┐     ┌──────┴───────┐
                     │  sub_groups  │     │ main_groups  │
                     ├──────────────┤     ├──────────────┤
                     │ id (PK)      │<────│ id (PK)      │
                     │ main_grp(FK) │     │ variant_id   │
                     │ name         │     │ name         │
                     │ code         │     │ code         │
                     │ created_at   │     │ created_at   │
                     └──────┬───────┘     └──────────────┘
                            │
                     ┌──────┴───────┐     ┌──────────────┐
                     │  diagrams    │     │    parts     │
                     ├──────────────┤     ├──────────────┤
                     │ id (PK)      │────>│ id (PK)      │
                     │ sub_grp(FK)  │     │ diagram_id   │
                     │ code         │     │ oem_number   │
                     │ name         │     │ description  │
                     │ image_url    │     │ position     │
                     │ created_at   │     │ quantity     │
                     └──────────────┘     │ notes        │
                                          │ created_at   │
                                          └──────────────┘
```

### Endpoints da API (Proposta)

```
GET  /api/v1/brands                              - Listar marcas
GET  /api/v1/brands/{brand_id}/models             - Listar modelos
GET  /api/v1/models/{model_id}/variants           - Listar variantes
GET  /api/v1/variants/{variant_id}/groups          - Listar grupos de pecas
GET  /api/v1/groups/{group_id}/subgroups           - Listar subgrupos
GET  /api/v1/subgroups/{subgroup_id}/diagrams      - Listar diagramas
GET  /api/v1/diagrams/{diagram_id}/parts           - Listar pecas
GET  /api/v1/parts/search?q={query}                - Buscar pecas por numero/nome
GET  /api/v1/vin/{vin_code}                        - Buscar por VIN

POST /api/v1/scraper/brands                        - Iniciar scraping de marcas
POST /api/v1/scraper/brand/{brand_id}              - Iniciar scraping de uma marca
GET  /api/v1/scraper/status/{task_id}              - Status do scraping
```

### Estrutura de Pastas do Projeto

```
ApiCar/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app
│   ├── config.py               # Configuracoes
│   ├── database.py             # Conexao PostgreSQL
│   ├── models/                 # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── brand.py
│   │   ├── model.py
│   │   ├── variant.py
│   │   ├── main_group.py
│   │   ├── sub_group.py
│   │   ├── diagram.py
│   │   └── part.py
│   ├── schemas/                # Pydantic schemas
│   │   ├── __init__.py
│   │   ├── brand.py
│   │   ├── model.py
│   │   ├── part.py
│   │   └── scraper.py
│   ├── routers/                # API routes
│   │   ├── __init__.py
│   │   ├── brands.py
│   │   ├── models.py
│   │   ├── parts.py
│   │   └── scraper.py
│   ├── services/               # Business logic
│   │   ├── __init__.py
│   │   ├── catalog_service.py
│   │   └── search_service.py
│   └── scraper/                # Playwright scraper
│       ├── __init__.py
│       ├── base_scraper.py     # Classe base
│       ├── audivw_scraper.py   # Scraper Audi/VW/Skoda/Seat
│       ├── bmw_scraper.py      # Scraper BMW/Mini/RR
│       ├── mercedes_scraper.py # Scraper Mercedes/Smart
│       ├── toyota_scraper.py   # Scraper Toyota/Lexus
│       ├── renault_scraper.py  # Scraper Renault/Dacia
│       └── generic_scraper.py  # Scraper generico
├── alembic/                    # Migracoes DB
├── tests/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── alembic.ini
└── README.md
```

---

## 7. Desafios e Consideracoes

1. **Conteudo dinamico**: O site carrega dados via JavaScript, necessitando Playwright (nao apenas requests HTTP)
2. **Base64 encoding**: As URLs usam estado codificado em Base64, necessitando decode/encode para navegacao programatica
3. **Variacoes por marca**: Cada grupo de marcas tem uma hierarquia de navegacao diferente, exigindo scrapers especializados
4. **Rate limiting**: Necessidade de respeitar limites do servidor (delays entre requests)
5. **Volume de dados**: O catalogo e extenso - sera necessario scraping incremental e priorizado
6. **Atualizacoes**: Os catalogos sao atualizados periodicamente pelas marcas
7. **Imagens/Diagramas**: Download e armazenamento de diagramas explodidos

---

## 8. Estrategia de Scraping

### Fase 1 - Estrutura Base
- Coletar todas as marcas e seus paths de catalogo
- Mapear modelos disponiveis por marca
- Salvar hierarquia basica no banco

### Fase 2 - Detalhamento
- Para cada modelo, coletar variantes/anos
- Mapear grupos e subgrupos de pecas
- Indexar diagramas disponiveis

### Fase 3 - Pecas
- Extrair listas de pecas de cada diagrama
- Coletar numeros OEM, descricoes, quantidades
- Download de imagens de diagramas

### Fase 4 - Manutencao
- Scraping incremental para atualizacoes
- Verificacao periodica de novos modelos/pecas
