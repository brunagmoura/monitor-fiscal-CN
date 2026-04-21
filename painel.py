"""
Painel BI — Monitor Fiscal de Proposições Legislativas
------------------------------------------------------
Dashboard institucional para acompanhamento de proposições que tratam
de exceções à LC 200/2023 e ao cálculo da meta de resultado primário.

Consome o SQLite gerado por monitor_fiscal.py.

Execução:
    streamlit run painel.py
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DB_PATH = Path(__file__).parent / "monitor_fiscal.db"


# ===================================================================
# Configuração da página
# ===================================================================
st.set_page_config(
    page_title="Monitor Fiscal de Proposições Legislativas",
    page_icon=":female_detective:"":file_folder:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ===================================================================
# Paleta e estilo
# ===================================================================
PALETA = {
    "papel":      "#F5F1EA",
    "papel_alt":  "#EDE6D9",
    "tinta":      "#1A1A1A",
    "tinta_mid":  "#4A4A47",
    "linha":      "#2E2E2B",
    "azeitona":   "#5F6B3C",
    "azeitona_c": "#8A9457",
    "ocre":       "#B8893F",
    "alerta":     "#A8291F",
    "alerta_bg":  "#F4E4E1",
    "score_0":    "#C9C3B4",
    "score_1":    "#B8893F",
    "score_2":    "#5F6B3C",
    "score_3":    "#A8291F",
}

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Crimson+Pro:ital,wght@0,400;0,600;0,700;1,400&family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

    :root {{
        --papel: {PALETA['papel']};
        --papel-alt: {PALETA['papel_alt']};
        --tinta: {PALETA['tinta']};
        --tinta-mid: {PALETA['tinta_mid']};
        --linha: {PALETA['linha']};
        --azeitona: {PALETA['azeitona']};
        --ocre: {PALETA['ocre']};
        --alerta: {PALETA['alerta']};
    }}

    html, body, [data-testid="stAppViewContainer"], .main {{
        background: var(--papel) !important;
        color: var(--tinta);
        font-family: 'IBM Plex Sans', -apple-system, sans-serif;
    }}

    .main .block-container {{
        padding-top: 1.5rem;
        padding-bottom: 3rem;
        max-width: 1400px;
    }}

    h1, h2, h3, h4 {{
        font-family: 'Crimson Pro', Georgia, serif;
        color: var(--tinta);
        letter-spacing: -0.01em;
    }}
    h1 {{
        font-weight: 700;
        font-size: 2.6rem;
        line-height: 1.05;
        margin-bottom: 0.3rem;
    }}
    h2 {{
        font-weight: 600;
        font-size: 1.5rem;
        border-bottom: 1px solid var(--linha);
        padding-bottom: 0.4rem;
        margin-top: 2rem;
    }}
    h3 {{
        font-weight: 600;
        font-size: 1.15rem;
    }}

    [data-testid="stMetricValue"] {{
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 2.1rem !important;
        font-weight: 500 !important;
        color: var(--tinta) !important;
    }}
    [data-testid="stMetricLabel"] {{
        font-family: 'IBM Plex Sans', sans-serif !important;
        font-size: 0.72rem !important;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        color: var(--tinta-mid) !important;
        font-weight: 500 !important;
    }}
    [data-testid="stMetricDelta"] {{
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.85rem !important;
    }}

    [data-testid="stSidebar"] {{
        background: var(--papel-alt);
        border-right: 1px solid var(--linha);
    }}
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {{
        font-family: 'Crimson Pro', serif;
    }}

    hr {{
        border: none;
        border-top: 1px solid var(--linha);
        margin: 1.5rem 0;
        opacity: 0.3;
    }}

    .stCaption, [data-testid="stCaptionContainer"] {{
        color: var(--tinta-mid) !important;
        font-style: italic;
    }}

    [data-testid="stDataFrame"] {{
        border: 1px solid var(--linha);
        border-radius: 2px;
    }}

    .stDownloadButton button, .stButton button {{
        background: var(--tinta) !important;
        color: var(--papel) !important;
        border: none !important;
        border-radius: 2px !important;
        font-family: 'IBM Plex Sans', sans-serif !important;
        font-weight: 500 !important;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        font-size: 0.75rem !important;
        padding: 0.6rem 1.4rem !important;
    }}

    .cartao {{
        background: var(--papel-alt);
        border-left: 3px solid var(--tinta);
        padding: 1.1rem 1.3rem;
        margin: 0.8rem 0;
        font-family: 'IBM Plex Sans', sans-serif;
    }}
    .cartao-alerta {{
        background: {PALETA['alerta_bg']};
        border-left: 3px solid var(--alerta);
    }}
    .cartao-azeitona {{
        border-left: 3px solid var(--azeitona);
    }}
    .cartao-ocre {{
        border-left: 3px solid var(--ocre);
    }}
    .cartao h4 {{
        margin: 0 0 0.4rem 0;
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.68rem;
        text-transform: uppercase;
        letter-spacing: 0.14em;
        color: var(--tinta-mid);
        font-weight: 600;
    }}
    .cartao .numero {{
        font-family: 'IBM Plex Mono', monospace;
        font-size: 2.4rem;
        font-weight: 500;
        line-height: 1;
        color: var(--tinta);
    }}
    .cartao .numero-alerta {{
        color: var(--alerta);
    }}
    .cartao .contexto {{
        font-size: 0.85rem;
        color: var(--tinta-mid);
        margin-top: 0.5rem;
        line-height: 1.45;
    }}

    .cabecalho-sistema {{
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.18em;
        color: var(--tinta-mid);
        border-top: 2px solid var(--tinta);
        border-bottom: 1px solid var(--linha);
        padding: 0.6rem 0;
        margin-bottom: 1rem;
        display: flex;
        justify-content: space-between;
    }}

    .stTabs [data-baseweb="tab-list"] {{
        gap: 0;
        border-bottom: 1px solid var(--linha);
    }}
    .stTabs [data-baseweb="tab"] {{
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        font-weight: 500;
        padding: 0.6rem 1.2rem;
        background: transparent;
        color: var(--tinta-mid);
    }}
    .stTabs [aria-selected="true"] {{
        color: var(--tinta);
        border-bottom: 2px solid var(--tinta) !important;
    }}

    .streamlit-expanderHeader {{
        font-family: 'IBM Plex Sans', sans-serif;
        font-weight: 500;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


PLOTLY_LAYOUT = dict(
    paper_bgcolor=PALETA["papel"],
    plot_bgcolor=PALETA["papel"],
    font=dict(family="IBM Plex Sans, sans-serif", color=PALETA["tinta"], size=12),
    title=dict(font=dict(family="Crimson Pro, serif", size=16, color=PALETA["tinta"])),
    xaxis=dict(
        gridcolor="rgba(46,46,43,0.08)",
        linecolor=PALETA["linha"],
        tickfont=dict(family="IBM Plex Mono, monospace", size=11),
    ),
    yaxis=dict(
        gridcolor="rgba(46,46,43,0.08)",
        linecolor=PALETA["linha"],
        tickfont=dict(family="IBM Plex Mono, monospace", size=11),
    ),
    margin=dict(l=40, r=20, t=50, b=40),
)

CORES_SCORE = {
    "0": PALETA["score_0"],
    "1": PALETA["score_1"],
    "2": PALETA["score_2"],
    "3": PALETA["score_3"],
}


# ===================================================================
# Carregamento
# ===================================================================
@st.cache_data(ttl=300)
def carregar() -> pd.DataFrame:
    if not DB_PATH.exists():
        return pd.DataFrame()
    with sqlite3.connect(DB_PATH) as con:
        df = pd.read_sql("SELECT * FROM proposicoes", con)
    for col in ["data_apresentacao", "data_ultima_movimentacao"]:
        if col in df.columns:
            # format="mixed" lida com valores heterogêneos no mesmo campo
            # (ex: "2019-02-19" do Senado e "2026-04-17T16:56" da Câmara)
            df[col] = pd.to_datetime(df[col], errors="coerce", format="mixed")
    return df


df = carregar()


# ===================================================================
# Cabeçalho
# ===================================================================
ultima_coleta = "—"
if not df.empty and "coletado_em" in df.columns:
    ultima_coleta = str(df["coletado_em"].max())[:16].replace("T", " ")

st.markdown(
    f"""
    <div class="cabecalho-sistema">
        <span>Monitor Fiscal · Acompanhamento de Proposições Legislativas</span>
        <span>Última coleta: {ultima_coleta}</span>
    </div>
    """,
    unsafe_allow_html=True,
)

col_titulo, col_sub = st.columns([3, 2])
with col_titulo:
    st.markdown("# Proposições legislativas com<br>impacto fiscal", unsafe_allow_html=True)
with col_sub:
    st.markdown(
        """
        <div style="padding-top: 1rem; line-height: 1.55;
                    color: var(--tinta-mid); font-family: 'Crimson Pro', serif;
                    font-style: italic; font-size: 1.05rem;">
        Acompanhamento automatizado de proposições legislativas da
        Câmara dos Deputados e do Senado Federal que podem criar
        exceções à Lei Complementar nº 200/2023 (Regime Fiscal Sustentável)
        ou inserir excecções ao cálculo da meta de resultado primário</strong>.
        </div>
        """,
        unsafe_allow_html=True,
    )

if df.empty:
    st.warning("Base vazia. Execute primeiro: `python monitor_fiscal.py`")
    st.stop()


# ===================================================================
# Sidebar
# ===================================================================
with st.sidebar:
    st.markdown("### Filtros")
    st.caption("Cartões e gráficos se ajustam aos filtros selecionados.")

    casas = st.multiselect(
        "Casa Legislativa",
        options=sorted(df["casa"].dropna().unique()),
        default=sorted(df["casa"].dropna().unique()),
    )

    tipos_disp = sorted([t for t in df["tipo"].dropna().unique() if t])
    tipos = st.multiselect(
        "Tipo de proposição",
        options=tipos_disp,
        help="PL (Projeto de Lei) · PLP (Projeto de Lei Complementar)"
             "PEC (Proposta de Emenda à Constituição) · MPV (Medida Provisória)"
             "PLN (Projeto de Lei do Congresso Nacional)",
    )

    score_min = st.slider(
        "Score fiscal mínimo",
        0, 3, 1,
        help="0 - irrelevante · 1 - menciona termos relacionados ao RFS ou meta de resultado primário"
             "2 - menciona RFS ou meta fiscal"
             "3 alto risco",
    )

    termo_busca = st.text_input(
        "Busca na ementa",
        "",
        placeholder="ex: precatórios",
    )

    st.divider()
    st.caption(
        "Monitor desenvolvido para apoiar a análise técnica prévia "
        "à discussão institucional das proposições."
    )


# ===================================================================
# Aplicação de filtros
# ===================================================================
mask = df["casa"].isin(casas) & (df["score_fiscal"] >= score_min)
if tipos:
    mask &= df["tipo"].isin(tipos)
if termo_busca:
    mask &= df["ementa"].str.contains(termo_busca, case=False, na=False)
filt = df[mask].copy()


# ===================================================================
# Cálculos
# ===================================================================
total = len(df)
score3 = int((df["score_fiscal"] == 3).sum())
score2 = int((df["score_fiscal"] == 2).sum())
score1 = int((df["score_fiscal"] == 1).sum())
triadas = score1 + score2 + score3
lc200 = int(df["atinge_lc200"].sum())
meta = int(df["atinge_meta"].sum())
ambos = int((df["atinge_lc200"] & df["atinge_meta"]).sum())

escape_teor = 0
if "fonte_classificacao" in df.columns:
    classif_por_teor = df[df["fonte_classificacao"] == "inteiro_teor"]
    escape_teor = int((classif_por_teor["score_fiscal"] >= 2).sum())

if "data_ultima_movimentacao" in df.columns:
    max_data = df["data_ultima_movimentacao"].max()
    corte_7d = max_data - timedelta(days=7) if pd.notna(max_data) else None
    if corte_7d is not None:
        movim_7d = int(
            ((df["data_ultima_movimentacao"] >= corte_7d) &
             (df["score_fiscal"] >= 2)).sum()
        )
    else:
        movim_7d = 0
else:
    movim_7d = 0

taxa_triagem = (triadas / total * 100) if total else 0
taxa_alto = (score3 / total * 100) if total else 0


# ===================================================================
# Seção 1 — Leitura executiva
# ===================================================================
st.markdown("## Resumo Executivo")
st.caption(
    "Principais achados do sistema de Monitoramento"
)

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown(
        f"""
        <div class="cartao cartao-alerta">
            <h4>Alto risco fiscal</h4>
            <div class="numero numero-alerta">{score3}</div>
            <div class="contexto">
                Proposições que mencionam LC 200/2023 <em>e</em> meta primária,
                ou combinam uma delas com termos relacionados à impacto fiscal.
                Representam {taxa_alto:.1f}% do total coletado.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c2:
    st.markdown(
        f"""
        <div class="cartao cartao-ocre">
            <h4>Movimentação em 7 dias</h4>
            <div class="numero">{movim_7d}</div>
            <div class="contexto">
                Proposições com score ≥ 2 que tiveram tramitação
                na última semana. Pode indicar votação em breve.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c3:
    st.markdown(
        f"""
        <div class="cartao cartao-azeitona">
            <h4>Cruzamento LC 200 × Meta</h4>
            <div class="numero">{ambos}</div>
            <div class="contexto">
                Proposições que mencionam simultaneamente LC 200/2023 e meta fiscal.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c4:
    st.markdown(
        f"""
        <div class="cartao">
            <h4>Textos apenas no inteiro teor</h4>
            <div class="numero">{escape_teor}</div>
            <div class="contexto">
                Proposições que a ementa não sinalizava como fiscais
                mas o inteiro teor revelou.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ===================================================================
# Seção 2 — KPIs
# ===================================================================
st.markdown("<br>", unsafe_allow_html=True)
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric(
    "Total coletado",
    f"{total:,}".replace(",", "."),
)
k2.metric(
    "Triadas",
    f"{triadas:,}".replace(",", "."),
    delta=f"{taxa_triagem:.1f}% do total",
    delta_color="off",
)
k3.metric(
    "LC nº 200/2023",
    f"{lc200:,}".replace(",", "."),
)
k4.metric(
    "Meta de resultado primário",
    f"{meta:,}".replace(",", "."),
)
k5.metric(
    "Selecionadas",
    f"{len(filt):,}".replace(",", "."),
    delta=f"{(len(filt)/total*100):.1f}% após filtros" if total else "—",
    delta_color="off",
)


# ===================================================================
# Seção 3 — Análise visual em tabs
# ===================================================================
st.markdown("## Análise")

tab1, tab2, tab3, tab4 = st.tabs([
    "Distribuição por risco",
    "Termos em destaque",
    "Linha do tempo",
    "Velocidade de tramitação",
])


# -------- TAB 1 — Heatmap tipo × score --------
with tab1:
    col_a, col_b = st.columns([3, 2])

    with col_a:
        pivot = (
            df.groupby(["tipo", "score_fiscal"])
              .size()
              .unstack(fill_value=0)
              .reindex(columns=[0, 1, 2, 3], fill_value=0)
        )
        if 3 in pivot.columns:
            pivot = pivot.sort_values(3, ascending=True)

        fig = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=["Score 0", "Score 1", "Score 2", "Score 3"],
            y=pivot.index,
            colorscale=[
                [0, PALETA["papel"]],
                [0.2, "#E8DFC8"],
                [0.5, PALETA["ocre"]],
                [1, PALETA["alerta"]],
            ],
            text=pivot.values,
            texttemplate="%{text}",
            textfont=dict(family="IBM Plex Mono", size=13, color=PALETA["tinta"]),
            colorbar=dict(
                title="",
                thickness=10,
                tickfont=dict(family="IBM Plex Mono", size=10),
            ),
            hovertemplate="<b>%{y}</b><br>%{x}: %{z} proposições<extra></extra>",
        ))
        fig.update_layout(
            PLOTLY_LAYOUT,
            title="Tipo de proposição × score fiscal",
            height=380,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.markdown("#### O que significa")
        st.markdown(
            """
            Cada linha é um tipo de proposição. As colunas vão do risco
            inexistente (score 0) ao alto risco (score 3). Quanto mais
            escura a célula, maior o volume.

            **Pontos de atenção:**

            - **PECs com score 3** têm peso maior porque alteram a
              Constituição.
            - **MPVs com score ≥ 2** exigem resposta rápida porque têm prazo
              de 60+60 dias.
            - **PLPs** geralmente são os veículos de alteração da
              própria LC nº 200/23.
            """
        )


# -------- TAB 2 — Ranking de termos --------
with tab2:
    col_a, col_b = st.columns([3, 2])

    def contar_termos(coluna: str) -> pd.Series:
        if coluna not in df.columns:
            return pd.Series(dtype=int)
        series = df[coluna].dropna().astype(str)
        series = series[series != ""]
        todos = []
        for s in series:
            todos.extend([t.strip() for t in s.split("|") if t.strip()])
        return pd.Series(todos).value_counts()

    def limpar(p: str) -> str:
        p = p.replace(r"\s+", " ")
        p = re.sub(r"\[.\]", "", p)
        p = re.sub(r"[\\?{}()|^$]", "", p)
        p = re.sub(r"\s+", " ", p).strip()
        return p

    def preparar_df_termos(serie, categoria):
        if serie.empty:
            return pd.DataFrame()
        s = serie.head(10)
        return pd.DataFrame({
            "termo": [limpar(p) for p in s.index],
            "qtd": s.values,
            "categoria": categoria,
        })

    df_termos = pd.concat([
        preparar_df_termos(contar_termos("termos_lc200"), "LC 200/2023"),
        preparar_df_termos(contar_termos("termos_meta"), "Meta primária"),
        preparar_df_termos(contar_termos("termos_risco"), "Termos relacionados à LC 200 ou meta primária"),
    ], ignore_index=True)

    with col_a:
        if not df_termos.empty:
            fig = px.bar(
                df_termos.sort_values("qtd"),
                y="termo", x="qtd",
                color="categoria",
                orientation="h",
                color_discrete_map={
                    "LC 200/2023": PALETA["score_2"],
                    "Meta primária": PALETA["ocre"],
                    "Termos fiscais": PALETA["alerta"],
                },
                labels={"qtd": "Ocorrências", "termo": "", "categoria": ""},
            )
            fig.update_layout(
                PLOTLY_LAYOUT,
                title="Termos mais frequentes por categoria",
                height=450,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Nenhum termo foi detectado nas proposições coletadas.")

    with col_b:
        st.markdown("#### O que os termos dizem")
        st.markdown(
            """
            Os termos destacados indicam qual foi a fonte que o Monitor identificou
             para identificar uma proposta como de risco fiscal no momento da coleta.

            A lista reflete apenas o que os padrões regex captaram.
            Efeitos fiscais indiretos (regimes paralelos, antecipação
            de receita) precisam de análise semântica adicional.
            """
        )


# -------- TAB 3 — Linha do tempo --------
with tab3:
    col_data = "data_ultima_movimentacao" if "data_ultima_movimentacao" in df.columns else "data_apresentacao"

    serie_base = (
        df.dropna(subset=[col_data])
          .assign(dia=lambda d: d[col_data].dt.date)
    )

    if serie_base.empty:
        st.info("Sem dados de data suficientes para construir a linha do tempo.")
    else:
        col_a, col_b = st.columns([3, 2])

        with col_a:
            serie_empilhada = (
                serie_base
                .groupby(["dia", "score_fiscal"])
                .size()
                .reset_index(name="qtd")
            )
            serie_empilhada["score_fiscal"] = serie_empilhada["score_fiscal"].astype(str)

            fig = px.area(
                serie_empilhada,
                x="dia", y="qtd",
                color="score_fiscal",
                color_discrete_map=CORES_SCORE,
                category_orders={"score_fiscal": ["0", "1", "2", "3"]},
                labels={"dia": "", "qtd": "Proposições", "score_fiscal": "Score"},
            )
            fig.update_layout(
                PLOTLY_LAYOUT,
                title="Movimentação diária por nível de risco",
                height=400,
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.02, x=0,
                    title=dict(text="Score: "),
                ),
                hovermode="x unified",
            )
            fig.update_traces(line=dict(width=0))
            st.plotly_chart(fig, use_container_width=True)

        with col_b:
            top_dias = (
                serie_base[serie_base["score_fiscal"] == 3]
                .groupby("dia")
                .size()
                .sort_values(ascending=False)
                .head(5)
            )
            st.markdown("#### Picos de alto risco")
            if top_dias.empty:
                st.caption("Nenhum dia com score 3 registrado.")
            else:
                linhas = []
                for dia, qtd in top_dias.items():
                    linhas.append(
                        f"<div style='font-family: IBM Plex Mono; "
                        f"padding: 0.4rem 0; border-bottom: 1px solid rgba(46,46,43,0.1);'>"
                        f"<strong>{dia.strftime('%d/%m/%Y')}</strong>"
                        f"<span style='float: right; color: var(--alerta);'>"
                        f"{qtd} proposições</span></div>"
                    )
                st.markdown("".join(linhas), unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.caption(
                " "
            )


# -------- TAB 4 — Velocidade --------
with tab4:
    if "data_apresentacao" in df.columns and "data_ultima_movimentacao" in df.columns:
        dft = df.dropna(subset=["data_apresentacao", "data_ultima_movimentacao"]).copy()
        dft["dias_tramitando"] = (
            dft["data_ultima_movimentacao"] - dft["data_apresentacao"]
        ).dt.days
        dft = dft[dft["dias_tramitando"] >= 0]

        col_a, col_b = st.columns([3, 2])

        with col_a:
            fig = go.Figure()
            for score in sorted(dft["score_fiscal"].unique()):
                sub = dft[dft["score_fiscal"] == score]
                fig.add_trace(go.Scatter(
                    x=sub["dias_tramitando"],
                    y=sub["score_fiscal"],
                    mode="markers",
                    marker=dict(
                        size=7,
                        color=CORES_SCORE[str(score)],
                        opacity=0.55,
                        line=dict(width=0.5, color=PALETA["papel"]),
                    ),
                    name=f"Score {score}",
                    hovertemplate=(
                        "<b>%{customdata[0]} %{customdata[1]}/%{customdata[2]}</b><br>"
                        "Tramitando há %{x} dias<br>"
                        "Score %{y}<extra></extra>"
                    ),
                    customdata=sub[["tipo", "numero", "ano"]].values,
                ))

            fig.update_layout(
                PLOTLY_LAYOUT,
                title="Idade de tramitação × score fiscal",
                height=400,
                xaxis_title="Dias desde a apresentação",
                yaxis_title="Score",
                yaxis=dict(
                    PLOTLY_LAYOUT["yaxis"],
                    tickmode="array",
                    tickvals=[0, 1, 2, 3],
                ),
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_b:
            mediana = dft["dias_tramitando"].median()
            antigas_alto = dft[
                (dft["score_fiscal"] == 3) &
                (dft["dias_tramitando"] > 365)
            ]
            recentes_alto = dft[
                (dft["score_fiscal"] == 3) &
                (dft["dias_tramitando"] <= 30)
            ]

            st.markdown("#### Sinais de velocidade")
            st.markdown(
                f"""
                <div class="cartao">
                    <h4>Mediana geral</h4>
                    <div class="numero">{mediana:.0f} dias</div>
                    <div class="contexto">tempo típico entre apresentação e última movimentação</div>
                </div>
                <div class="cartao cartao-alerta">
                    <h4>Reanimadas (≥ 1 ano + alto risco)</h4>
                    <div class="numero numero-alerta">{len(antigas_alto)}</div>
                    <div class="contexto">proposições antigas que voltaram a tramitar com score 3 — atenção</div>
                </div>
                <div class="cartao cartao-ocre">
                    <h4>Novas em alta velocidade</h4>
                    <div class="numero">{len(recentes_alto)}</div>
                    <div class="contexto">apresentadas nos últimos 30 dias e já com score 3</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("Dados de tramitação insuficientes.")


# ===================================================================
# Seção 4 — Tabela
# ===================================================================
st.markdown(f"## Proposições selecionadas · {len(filt)}")
st.caption(
    "Ordenadas por score descendente, depois por data de movimentação mais recente. "
    "Clique em qualquer cabeçalho para reordenar. Use o link para abrir a proposição "
    "no site da Casa Legislativa."
)

cols_show = [
    "casa", "tipo", "numero", "ano",
    "data_ultima_movimentacao", "data_apresentacao",
    "score_fiscal", "fonte_classificacao",
    "atinge_lc200", "atinge_meta",
    "ementa", "termos_lc200", "termos_meta", "termos_risco", "url",
]
cols_show = [c for c in cols_show if c in filt.columns]

df_tabela = filt[cols_show].copy()
if "score_fiscal" in df_tabela.columns:
    df_tabela = df_tabela.sort_values(
        ["score_fiscal", "data_ultima_movimentacao"],
        ascending=[False, False],
    )

st.dataframe(
    df_tabela,
    use_container_width=True,
    hide_index=True,
    height=450,
    column_config={
        "casa": st.column_config.TextColumn("Casa", width="small"),
        "tipo": st.column_config.TextColumn("Tipo", width="small"),
        "numero": st.column_config.TextColumn("Nº", width="small"),
        "ano": st.column_config.TextColumn("Ano", width="small"),
        "url": st.column_config.LinkColumn("Link", display_text="abrir", width="small"),
        "ementa": st.column_config.TextColumn("Ementa", width="large"),
        "score_fiscal": st.column_config.NumberColumn("Score", format="%d", width="small"),
        "fonte_classificacao": st.column_config.TextColumn("Fonte", width="small"),
        "data_ultima_movimentacao": st.column_config.DateColumn(
            "Últ. movim.", format="DD/MM/YYYY", width="small",
        ),
        "data_apresentacao": st.column_config.DateColumn(
            "Apresentação", format="DD/MM/YYYY", width="small",
        ),
        "atinge_lc200": st.column_config.CheckboxColumn("LC 200", width="small"),
        "atinge_meta":  st.column_config.CheckboxColumn("Meta", width="small"),
        "termos_lc200": st.column_config.TextColumn("Termos LC 200"),
        "termos_meta":  st.column_config.TextColumn("Termos meta"),
        "termos_risco": st.column_config.TextColumn("Termos de risco"),
    },
)

col_exp1, col_exp2, _ = st.columns([1, 1, 3])
with col_exp1:
    st.download_button(
        label="Exportar seleção (CSV)",
        data=df_tabela.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"monitor_fiscal_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )
with col_exp2:
    df_alto = df[df["score_fiscal"] == 3][cols_show]
    st.download_button(
        label="Exportar apenas alto risco",
        data=df_alto.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"monitor_fiscal_alto_risco_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )


# ===================================================================
# Seção 5 — Notas técnicas
# ===================================================================
st.markdown("## Notas técnicas")

tab_met, tab_lim, tab_gloss = st.tabs([
    "Metodologia",
    "Limitações do MVP",
    "Glossário",
])

with tab_met:
    st.markdown(
        """
        **Fluxo de classificação**

        1. Coleta diária de proposições via APIs oficiais da Câmara
           (`dadosabertos.camara.leg.br`) e do Senado (`legis.senado.leg.br`),
           filtrando por movimentação recente.
        2. Download do inteiro teor via campo `urlInteiroTeor` (Câmara)
           ou `/processo/documento` (Senado). PDFs são processados com
           extração de texto; HTMLs têm as tags limpas.
        3. Classificação por expressões regulares em três categorias:

           - Referência à **LC 200/2023** (limite de despesas, arcabouço
             fiscal, regra fiscal, teto de gastos)
           - Referência à **meta de resultado primário** (meta fiscal,
             resultado primário, exclusão da meta)
           - **Termos de risco** — termos relacionados a temas que costumam
            gerar impacto fiscal (precatórios, FUNDEB, crédito
             extraordinário, transferência constitucional, regime
             especial de execução, fundo especial).

        4. Atribuição de score de 0 a 3 conforme combinação das três
           dimensões (ver glossário).

        **Fallback:** quando o inteiro teor não está disponível, a
        classificação recai sobre a ementa. A coluna *Fonte* na tabela
        indica qual texto foi analisado em cada caso.
        """
    )

with tab_lim:
    st.markdown(
        """
        **Três limitações precisam ser ditas explicitamente:**

        **1. Regex é primeira peneira.** A classificação atual identifica
        menção explícita aos termos catalogados. Exceções fiscais
        *indiretas*, como regimes paralelos, fundos com fonte própria,
        antecipação de receita, desvinculação por fora, podem passar
        batido.

        **2. Substitutivos e emendas não são versionados.** O jabuti
        clássico aparece em substitutivo de última hora ou emenda de
        plenário. O sistema precisa guardar todas as versões do texto
        e reclassificar a cada movimentação significativa.

        **3. Não há quantificação de impacto.** Saber que uma PEC pode
        abrir exceção à LC 200 é diferente de saber quanto de espaço
        fiscal ela pode criar.

        **Outras limitações:**

        - A janela de coleta do Senado por movimentação é limitada a
          30 dias pela API. Para períodos maiores, combinamos com
          coleta por apresentação (máximo 1 ano por requisição).
        """
    )

with tab_gloss:
    st.markdown(
        """
        **LC 200/2023** — Lei Complementar que instituiu o regime fiscal
        sustentável (arcabouço fiscal). Estabelece limites para o
        crescimento real da despesa primária do governo federal,
        vinculados à variação da receita.

        **Meta de resultado primário** — objetivo fiscal fixado pela
        LDO para o resultado das contas do governo antes dos juros da
        dívida. Despesas excluídas do cálculo da meta abrem espaço
        fiscal sem aparecer como descumprimento.

        **Score fiscal** — escala de 0 a 3 atribuída automaticamente:

        - `0` — sem indício fiscal detectado
        - `1` — termos de contexto presentes (precatórios, FUNDEB
          etc.); vigilância
        - `2` — texto menciona LC 200 *ou* meta primária
        - `3` — menciona ambos, *ou* um deles combinado com termo de
          alto risco

        **Tipos de proposição monitorados:**

        - **PL** — Projeto de Lei (ordinária)
        - **PLP** — Projeto de Lei Complementar
        - **PEC** — Proposta de Emenda à Constituição
        - **MPV** — Medida Provisória
        - **PLN** — Projeto de Lei do Congresso Nacional
        - **PLV** — Projeto de Lei de Conversão (MPV convertida)
        """
    )


# ===================================================================
# Rodapé
# ===================================================================
st.markdown(
    """
    <div style="margin-top: 3rem; padding-top: 1rem;
                border-top: 1px solid var(--linha);
                font-family: 'IBM Plex Mono', monospace;
                font-size: 0.72rem; text-transform: uppercase;
                letter-spacing: 0.14em; color: var(--tinta-mid);
                display: flex; justify-content: space-between;">
        <span>Monitor Fiscal de Propostas Legislativas · Uso interno CGPEC/DE/SFC</span>
        <span>Dados públicos · Câmara + Senado</span>
    </div>
    """,
    unsafe_allow_html=True,
)