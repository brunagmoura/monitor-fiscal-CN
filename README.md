# Monitor Fiscal de Proposições Legislativas

Sistema de acompanhamento automatizado de proposições da Câmara dos Deputados e do Senado Federal que podem criar exceções à **Lei Complementar nº 200/2023** (regime fiscal sustentável) ou alterar o cálculo da **meta de resultado primário**.

O projeto combina um coletor (Python puro, consumindo APIs oficiais) e um painel editorial (Streamlit) para apoiar a análise técnica prévia à discussão institucional dessas proposições.

---

## Por que monitorar exceções fiscais

O orçamento público federal é disciplinado por dois regimes que operam em paralelo e se reforçam: o **limite de despesas** estabelecido pela LC 200/2023 e a **meta de resultado primário** fixada anualmente pela LDO.

Quando uma proposição legislativa cria uma exceção a essas regras, excluindo determinada despesa do limite, retirando um tipo de gasto do cálculo da meta ou instituindo regime especial de execução , ela impacta o fiscal sem aparecer formalmente como descumprimento. O efeito cumulativo dessas exceções, muitas vezes introduzidas em substitutivos de última hora ou emendas de plenário, pode gerar dúvidas sobre a efetividade dos regimes fiscais.

Como exemplo, cita-se a **Emenda Constitucional nº 136/2025**, originária da PEC 66/2023, que retirou integralmente os precatórios do limite individualizado de despesas primárias do Poder Executivo a partir de 2026, migrando R$ 117,9 bilhões para fora do teto na LOA 2026. No mesmo movimento, a EC excluiu esses mesmos valores do cálculo da meta de resultado primário, com reincorporação gradual prevista apenas a partir de 2027 (mínimo de 10% ao ano, cumulativo). Esse tipo de mudança, de grande impacto material, pode ser identificada rapidamente enquanto ainda tramita por meio do sistema de base de dados do Congresso Nacional.

Daí o propósito deste monitor: **varrer sistematicamente o fluxo de proposições das duas Casas, extrair o inteiro teor, classificar por risco fiscal e oferecer a base para uma leitura tempestiva**.

---

## O regime fiscal sustentável (LC nº 200/2023)

A Lei Complementar nº 200/2023 instituiu o regime fiscal sustentável e substituiu o teto de gastos criado pela EC 95/2016. Sua lógica central é vincular o crescimento real da despesa primária federal à variação real da receita primária, dentro de bandas pré-definidas.

O crescimento real da despesa é limitado ao **intervalo entre 0,6% e 2,5% ao ano**, tomando como base 70% do crescimento real da receita dos 12 meses encerrados em junho do ano anterior. Se a receita cresceu bastante, a despesa pode crescer até 2,5%; se cresceu pouco ou caiu, o piso de 0,6% garante alguma expansão mínima. O teto da regra, portanto, é inferior ao crescimento da receita — é essa a mecânica de geração de superávit primário ao longo do tempo.

A regra prevê **limites individualizados por Poder e órgão autônomo** (Executivo, Legislativo, Judiciário, MPU, DPU), com correção anual. Quando há descumprimento, aplicam-se gatilhos de contenção: vedação de criação de cargos, reajustes, contratações, admissão de pessoal e ampliação de subsídios tributários.

As exceções legais ao limite são nominais e restritas. Incluem, entre outras, as transferências constitucionais a estados e municípios, complementação da União ao FUNDEB, créditos extraordinários por calamidade, despesas com eleições, entre outros. Qualquer **nova** exceção exige alteração de lei complementar ou emenda à Constituição.

---

## A meta de resultado primário

Enquanto a LC 200 disciplina o **fluxo de despesas**, a meta de resultado primário disciplina o **resultado fiscal** — a diferença entre receitas e despesas não-financeiras do governo. A meta é fixada anualmente pela Lei de Diretrizes Orçamentárias (LDO) como percentual do PIB, com banda de tolerância para mais e para menos.

A meta e o limite de despesas não são redundantes. Uma despesa pode estar dentro do limite e ainda assim comprometer a meta se a receita frustrar; inversamente, uma despesa pode estar excluída do cálculo da meta e, ainda assim, estar sujeita ao limite (ou vice-versa). A arquitetura completa exige olhar os dois regimes simultaneamente.

O raciocínio aqui não é de que essas exceções sejam necessariamente ilegítimas já que geralmente têm fundamento constitucional ou técnico. Porém, o efeito agregado delas pode ser monitorado e discutido institucionalmente.

---

## Como o sistema funciona

O fluxo deste Monitor se divide em dois scripts, desenhados para rodar em sequência:

**1. Coletor (`monitor_fiscal.py`)**

Consulta as APIs oficiais da Câmara dos Deputados (`dadosabertos.camara.leg.br`) e do Senado Federal (`legis.senado.leg.br`) em busca de proposições com movimentação recente. Para cada proposição encontrada, baixa o inteiro teor (PDF ou HTML), extrai o texto e aplica uma bateria de expressões regulares organizadas em três categorias:

- **Referências diretas à LC 200/2023** — "limite de despesas", "lei complementar nº 200", "arcabouço fiscal", "regra fiscal", "teto de gastos", "não se aplica o limite", "excetua-se o limite", "crescimento real das despesas".
- **Referências à meta de resultado primário** — "meta de resultado primário", "meta fiscal", "resultado primário", "não computar na meta", "exclusão da meta", "fora da meta", "deduzir da meta".
- **Termos de alto risco** — sinalizadores históricos de carve-out fiscal: precatórios, FUNDEB, créditos extraordinários, transferências constitucionais, regime especial de execução, fundos especiais.

Com base nas correspondências, cada proposição recebe uma  **nota fiscal de 0 a 3**:

| Score | Critério | Leitura |
|:-:|---|---|
| **0** | Nenhum termo detectado | Sem indício fiscal |
| **1** | Apenas termos de alto risco | Vigilância — contexto fiscal sensível |
| **2** | LC 200 *ou* meta primária | Atenção — mencionada exceção específica |
| **3** | LC 200 *e* meta, ou um deles + alto risco | Alto risco — exceção potencial confirmada |

Todos os resultados são persistidos num banco SQLite (`monitor_fiscal.db`), incluindo ementa, inteiro teor, termos encontrados, fonte de classificação (ementa vs. inteiro teor) e datas de apresentação e última movimentação.

**2. Painel (`painel.py`)**

Dashboard Streamlit que consome o SQLite e apresenta:

- Leitura executiva — quatro cartões com os números que importam numa reunião (alto risco, movimentação recente, cruzamento LC 200 × meta, revelações do inteiro teor)
- KPIs agregados — total coletado, triadas, ocorrências por regime fiscal
- Análise visual em quatro abas — distribuição de risco por tipo de proposição (heatmap), ranking de termos, linha do tempo por nível de risco, velocidade de tramitação
- Tabela detalhada com filtros, ordenação e exportação para CSV
- Notas técnicas — metodologia, limitações do MVP e glossário

---

## Execução local

Pré-requisitos: Python 3.10 ou superior.

```bash
git clone https://github.com/brunagmoura/monitor-fiscal-CN.git
cd monitor-fiscal-CN
pip install -r requirements.txt

# Coleta dados (demora alguns minutos, depende da janela configurada)
python monitor_fiscal.py

# Abre o painel
streamlit run painel.py
```

A janela de coleta é configurável no topo de `monitor_fiscal.py` pela variável `DIAS_LOOKBACK`.

---

## Limitações do MVP

**Regex é primeira peneira.** A classificação identifica menção explícita aos termos catalogados. Exceções fiscais *indiretas* — regimes paralelos, fundos com fonte própria, antecipação de receita, desvinculação por fora — podem passar despercebidas.

**Substitutivos e emendas não são versionados.** O jabuti clássico aparece em substitutivo de última hora ou emenda de plenário, e não na ementa original. O sistema precisa passar a guardar todas as versões do texto e reclassificar a cada movimentação significativa — hoje, cada coleta sobrescreve a anterior.

**Não há quantificação de impacto.** Saber que uma PEC pode abrir exceção à LC 200 é diferente de saber quanto de espaço fiscal ela pode criar. 

Há também limitações menores herdadas das APIs: a janela de coleta do Senado por movimentação é limitada a 30 dias por requisição (compensamos com coleta adicional por data de apresentação, até 1 ano); o endpoint `/materia/pesquisa/lista` do Senado foi depreciado e substituído por `/processo`; o retorno do endpoint `/proposicoes` da Câmara não inclui a data da última ação, que precisa ser coletada em requisição adicional por proposição.

---

## Estrutura do repositório

```
monitor-fiscal-CN/
├── monitor_fiscal.py      # Coletor e classificador
├── painel.py              # Dashboard Streamlit
├── monitor_fiscal.db      # Base SQLite (gerada pelo coletor)
├── requirements.txt       # Dependências Python
├── README.md              # Este arquivo
└── .gitignore
```

---

## Glossário abreviado

- **LC 200/2023** — Lei Complementar que instituiu o regime fiscal sustentável.
- **Arcabouço fiscal** — Designação coloquial do regime da LC 200.
- **Meta de resultado primário** — Objetivo fiscal fixado pela LDO para o resultado das contas do governo antes dos juros da dívida.
- **EC 136/2025** — Emenda Constitucional que retirou precatórios do limite de despesas e do cálculo da meta primária, com reincorporação gradual a partir de 2027.
- **Precatórios** — Dívidas da Fazenda Pública reconhecidas por decisão judicial transitada em julgado.
- **FUNDEB** — Fundo de Manutenção e Desenvolvimento da Educação Básica, que concentra transferências constitucionais relevantes.
- **Crédito extraordinário** — Instrumento orçamentário para despesas urgentes e imprevisíveis, tradicionalmente excluído de limites de gasto.
- **Regime especial de execução** — Expressão que, em muitos casos, sinaliza contabilidade paralela ao fluxo orçamentário ordinário.

## Tipos de proposição monitorados

- **PL** — Projeto de Lei (ordinária)
- **PLP** — Projeto de Lei Complementar
- **PEC** — Proposta de Emenda à Constituição
- **MPV** — Medida Provisória
- **PLN** — Projeto de Lei do Congresso Nacional
- **PLV** — Projeto de Lei de Conversão (MPV convertida)

---

## Contribuições e uso

O código é publicado de boa-fé; os dados consumidos são integralmente públicos, oriundos das APIs oficiais da Câmara dos Deputados e do Senado Federal. As classificações produzidas pelo sistema são indicativas e não substituem a análise técnica humana.

---