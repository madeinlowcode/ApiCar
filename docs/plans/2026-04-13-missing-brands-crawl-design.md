# Design: Crawl das Marcas Faltantes

## Problema

11 marcas foram registradas no banco mas ficaram sem modelos/pecas porque usam layouts diferentes no catcar.info. O parser L2 original so reconhece o formato Mercedes/VW/Audi/BMW.

## Investigacao

### Marcas eliminadas (3) -- nao existem no catcar.info (404)
- Dacia
- Infiniti
- Vauxhall

### Marcas com dados (8) -- agrupadas por estrutura

#### Grupo A: "Ano -> Regiao -> Modelo" (3 marcas)
**Honda, Kia, Hyundai**

Estrutura da homepage:
- Tabs de anos (`<ul class="tabs"><li>...<a href="?l=...year==2018">`)
- Dentro do ano: links de regioes
- Dentro da regiao: modelos em `<a class="groups-parts__item">`
- Categorias: `groups-parts__item` com nomes (ENGINE, BODY, etc.)
- Subgrupos: `groups-parts__item` com links para paginas de pecas
- Pecas: `<td class="table__td">` (mesmo formato ja suportado por `parts_html.py`)

Hierarquia: Homepage -> Ano -> Regiao -> Modelo -> Categorias -> Subgrupos -> Pecas

Honda tem modelos direto na homepage (ACCORD, CIVIC, etc.) em `<td class="table__td">` alem dos tabs de ano.

#### Grupo B: "Regiao -> Modelo" (4 marcas)
**Nissan, Mazda, Subaru, Chrysler**

Estrutura da homepage:
- Links de regioes/markets direto (Canada, Europe LHD, USA, Japan, etc.)
- Nissan: `<a href="...region==ca...">Canada</a>`
- Mazda: `<a href="...market==euro...">Europe</a>`
- Subaru: `<a href="...region==lhd...">Europe (LHD)</a>`
- Chrysler: tabs de anos + links de markets (`<li><a>CANADA</a></li>`)

Hierarquia: Homepage -> Regiao -> Modelo -> Categorias -> Subgrupos -> Pecas
Chrysler: Homepage -> Ano -> Market -> Modelo -> ...

#### Grupo C: "AJAX/JavaScript" (1 marca)
**Jaguar**

- Usa CSS antigo (`big_catalog3.css`)
- Modelos carregados via JavaScript/AJAX (`sendRequest`)
- NAO funciona com HTTP puro -- precisa Playwright
- Sera tratado separadamente

## Abordagem: TDD por Grupo

### Estrategia

Para cada grupo:
1. **Coletar amostras HTML** de cada nivel de navegacao (salvar em `tests/fixtures/`)
2. **Escrever testes** que validam a extracao contra as amostras
3. **Implementar parser** ate passar 100% dos testes
4. **Integrar no crawler** e rodar na VPS

### Implementacao por grupo

#### Grupo A (Honda, Kia, Hyundai)

Novo parser: `crawler/parsers/brand_group_a.py`
- `parse_year_tabs(html) -> list[dict]` -- extrai tabs de anos
- `parse_region_links(html) -> list[dict]` -- extrai links de regioes
- `parse_models_groups(html) -> list[dict]` -- extrai modelos de `groups-parts__item`
- `parse_categories_groups(html) -> list[dict]` -- extrai categorias
- `parse_subgroups_groups(html) -> list[dict]` -- extrai subgrupos
- Pecas: reutiliza `parts_html.py` existente

Testes: `tests/test_brand_group_a.py`

#### Grupo B (Nissan, Mazda, Subaru, Chrysler)

Novo parser: `crawler/parsers/brand_group_b.py`
- `parse_market_links(html) -> list[dict]` -- extrai links de mercados
- `parse_models_list(html) -> list[dict]` -- extrai modelos
- Restante compartilha com Grupo A (categorias, subgrupos usam `groups-parts__item`)

Testes: `tests/test_brand_group_b.py`

#### Grupo C (Jaguar)

- Precisa Playwright para renderizar JS
- Crawler separado, menor prioridade
- Possivelmente 1 crawler Playwright dedicado

### Novo runner: `run_crawl_brands.py`

Crawler HTTP generico que:
- Recebe brand slug como parametro
- Detecta o grupo automaticamente pela estrutura da pagina
- Navega recursivamente usando o parser correto para cada nivel
- Raw SQL (sem ORM), como `run_crawl_http.py`
- No nivel de pecas, usa `parts_html.py`

### Docker

- Reutiliza `Dockerfile.crawler-http` (sem Playwright)
- Jaguar usa `Dockerfile.crawler` (com Playwright)

## Estimativa de Volume

| Grupo | Marcas | Modelos est. | Pecas est. | Tempo est. (30 crawlers) |
|-------|--------|-------------|-----------|-------------------------|
| A | 3 | ~500 | ~2M | ~1 dia |
| B | 4 | ~800 | ~3M | ~1.5 dias |
| C | 1 | ~100 | ~500K | ~4 horas (Playwright) |
| **Total** | **8** | **~1,400** | **~5.5M** | **~3 dias** |

## Criterios de Sucesso

- 100% dos testes passando antes de deploy
- Todas as 8 marcas com modelos no banco
- Pecas extraidas com breadcrumb completo na API
- Zero marcas com modelos vazios (exceto Dacia/Infiniti/Vauxhall que sao 404)
