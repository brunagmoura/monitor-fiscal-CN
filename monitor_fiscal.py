"""
Monitor Fiscal — MVP
--------------------
Coleta proposições recentes da Câmara dos Deputados e do Senado Federal
e as classifica por relevância fiscal em relação a:
  (1) Lei Complementar 200/2023 (arcabouço fiscal, limite de despesas)
  (2) Meta de resultado primário

A classificação é feita diretamente sobre o inteiro teor do texto.
A ementa serve apenas como fallback quando o inteiro teor não está disponível.

Saída: banco SQLite (monitor_fiscal.db) lido pelo painel.

Execução:
    python monitor_fiscal.py
"""

from __future__ import annotations

import re
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

# ===================================================================
# Configuração
# ===================================================================
DIAS_LOOKBACK = 2
TIPOS_CAMARA = "PL,PLP,PEC,MPV,PLN"
DB_PATH = Path(__file__).parent / "monitor_fiscal.db"
TIMEOUT = 30

# ===================================================================
# Padrões de triagem (regex, case-insensitive)
# ===================================================================

PADROES_LC200 = [
    r"limite\s+de\s+despesas",
    r"lei\s+complementar\s+n?[ºo°]?\s*200",
    r"arcabou[cç]o\s+fiscal",
    r"n[ãa]o\s+se\s+aplica[m]?\s+.{0,40}limite",
    r"excetua[m]?[-\s]?se?\s+.{0,30}limite",
    r"regra\s+fiscal",
    r"crescimento\s+real\s+(d[ao]s?\s+)?despesas?",
    r"teto\s+de\s+gastos?",
]

PADROES_META = [
    r"meta\s+de\s+resultado\s+prim[áa]rio",
    r"meta\s+fiscal",
    r"resultado\s+prim[áa]rio",
    r"n[ãa]o\s+(ser[áa]?\s+)?comput(ad[oa]s?|ar)\s+.{0,40}meta",
    r"exclus[ãa]o\s+da\s+meta",
    r"fora\s+da\s+meta",
    r"deduz(ido|ir|[-\s]se)\s+.{0,30}meta",
]

TERMOS_ALTO_RISCO = [
    r"precat[óo]rios?",
    r"fundeb",
    r"cr[ée]ditos?\s+extraordin[áa]rios?",
    r"transfer[êe]ncias?\s+constitucionais?",
    r"regime\s+especial\s+de\s+(execu[çc][ãa]o|pagamento)",
    r"fundos?\s+(especi(al|ais)|constituciona(l|is))",
    r"calamidade",
    r"estado\s+de\s+emerg[êe]ncia",
]

RE_LC200 = [re.compile(p, re.IGNORECASE) for p in PADROES_LC200]
RE_META  = [re.compile(p, re.IGNORECASE) for p in PADROES_META]
RE_RISCO = [re.compile(p, re.IGNORECASE) for p in TERMOS_ALTO_RISCO]


# ===================================================================
# Coleta — Câmara dos Deputados
# ===================================================================

def coletar_camara(dias: int = DIAS_LOOKBACK) -> pd.DataFrame:
    """Coleta proposicoes com tramitacao nos ultimos `dias`.

    Usa os parametros dataInicio/dataFim da API REST moderna, que
    filtram por intervalo de tramitacao (movimentacao). Aceita multiplos
    tipos separados por virgula no parametro siglaTipo.
    """
    data_inicio = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d")
    data_fim = datetime.now().strftime("%Y-%m-%d")

    base_url = "https://dadosabertos.camara.leg.br/api/v2/proposicoes"

    registros = []
    pagina = 1
    while pagina <= 200:
        params = {
            "dataInicio": data_inicio,
            "dataFim": data_fim,
            "siglaTipo": TIPOS_CAMARA,
            "ordem": "DESC",
            "ordenarPor": "id",
            "itens": 100,
            "pagina": pagina,
        }
        try:
            r = requests.get(base_url, params=params, timeout=TIMEOUT,
                             headers={"Accept": "application/json"})
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"  [Camara] Erro na pagina {pagina}: {e}")
            break

        dados = r.json().get("dados", [])
        if not dados:
            break

        for p in dados:
            registros.append({
                "casa": "Câmara",
                "id": p.get("id"),
                "tipo": p.get("siglaTipo"),
                "numero": p.get("numero"),
                "ano": p.get("ano"),
                "ementa": (p.get("ementa") or "").strip(),
                "data_apresentacao": p.get("dataApresentacao"),
                "data_ultima_movimentacao": p.get("dataUltimaAcao"),
                "url": (
                    "https://www.camara.leg.br/propostas-legislativas/"
                    + str(p.get("id"))
                ),
            })

        print(f"  pagina {pagina}: +{len(dados)} (total: {len(registros)})", end="\r")
        pagina += 1
        time.sleep(0.15)

    print()
    return pd.DataFrame(registros)


# ===================================================================
# Coleta — Senado Federal
# ===================================================================

def coletar_senado(dias: int = DIAS_LOOKBACK) -> pd.DataFrame:
    """Coleta processos do Senado usando o endpoint novo /processo.

    Duas estrategias combinadas (dedup por id):
    1. Processos ATUALIZADOS (movimentacao recente) - parametro numdias
       (limite maximo da API: 30 dias). Captura proposicoes antigas que
       voltaram a tramitar.
    2. Processos APRESENTADOS nos ultimos `dias` - parametros
       dataInicioApresentacao/dataFimApresentacao (limite maximo: 1 ano
       por requisicao). Captura proposicoes novas.

    Fonte: https://legis.senado.leg.br/dadosabertos/api-docs/swagger-ui/
    """
    base_url = "https://legis.senado.leg.br/dadosabertos/processo"
    headers = {"Accept": "application/json"}
    siglas = ["PL", "PLP", "PEC", "MPV", "PLN", "PLV"]

    registros = {}
    debug_count = 0  # para debugar apenas as primeiras 2 proposicoes

    # ---------- 1. Processos atualizados (movimentacao recente) ----------
    numdias = min(dias, 30)  # API limita a 30 dias
    print(f"  Buscando processos atualizados nos ultimos {numdias} dias...")
    for sigla in siglas:
        params = {"numdias": numdias, "sigla": sigla}
        try:
            r = requests.get(base_url, params=params, headers=headers, timeout=TIMEOUT)
            r.raise_for_status()
            dados = r.json() or []
            if isinstance(dados, dict):
                dados = [dados]
            print(f"    [{sigla}] {len(dados)} atualizados")
            for p in dados:
                _add_processo(registros, p, debug=(debug_count < 2))
                debug_count += 1
        except requests.RequestException as e:
            print(f"    [Senado/{sigla}] Erro atualizados: {e}")
        except ValueError:
            pass  # JSON invalido ou vazio
        time.sleep(0.2)

    # ---------- 2. Processos apresentados na janela ----------
    # A API aceita ate 1 ano por requisicao
    restante = dias
    fim = datetime.now()
    while restante > 0:
        bloco = min(restante, 365)
        inicio = fim - timedelta(days=bloco)
        print(f"  Buscando apresentados de {inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}...")
        for sigla in siglas:
            params = {
                "dataInicioApresentacao": inicio.strftime("%Y-%m-%d"),
                "dataFimApresentacao": fim.strftime("%Y-%m-%d"),
                "sigla": sigla,
            }
            try:
                r = requests.get(base_url, params=params, headers=headers, timeout=TIMEOUT)
                r.raise_for_status()
                dados = r.json() or []
                if isinstance(dados, dict):
                    dados = [dados]
                print(f"    [{sigla}] {len(dados)} apresentados")
                for p in dados:
                    _add_processo(registros, p, debug=(debug_count < 2))
                    debug_count += 1
            except requests.RequestException as e:
                print(f"    [Senado/{sigla}] Erro apresentados: {e}")
            except ValueError:
                pass
            time.sleep(0.2)

        restante -= bloco
        fim = inicio

    return pd.DataFrame(list(registros.values()))


def _add_processo(registros: dict, p: dict, debug: bool = False) -> None:
    """Extrai campos relevantes de um processo (endpoint /processo) e adiciona ao dict."""
    pid = p.get("id")
    if not pid or pid in registros:
        return

    if debug:
        print(f"    [DEBUG Senado] chaves disponiveis: {list(p.keys())}")
        print(f"    [DEBUG Senado] dataApresentacao: {p.get('dataApresentacao')!r}")
        print(f"    [DEBUG Senado] dataUltimaAtualizacao: {p.get('dataUltimaAtualizacao')!r}")

    # identificacao no formato "PL 21/2020" - extrai tipo/numero/ano
    ident = p.get("identificacao") or ""
    tipo, numero, ano = "", "", ""
    if " " in ident and "/" in ident:
        try:
            tipo = ident.split(" ")[0]
            resto = ident.split(" ")[1]
            numero, ano = resto.split("/")
        except (ValueError, IndexError):
            pass

    data_mov = p.get("dataUltimaAtualizacao") or p.get("dataApresentacao") or ""
    if isinstance(data_mov, str) and "T" in data_mov:
        data_mov = data_mov.split("T")[0]

    data_apres = p.get("dataApresentacao") or ""
    if isinstance(data_apres, str) and "T" in data_apres:
        data_apres = data_apres.split("T")[0]

    registros[pid] = {
        "casa": "Senado",
        "id": pid,
        "tipo": tipo,
        "numero": numero,
        "ano": ano,
        "ementa": (p.get("ementa") or "").strip(),
        "data_apresentacao": data_apres,
        "data_ultima_movimentacao": data_mov,
        "url": (
            "https://www25.senado.leg.br/web/atividade/materias/-/materia/"
            + str(p.get("codigoMateria") or pid)
        ),
    }



# ===================================================================
# Inteiro teor
# ===================================================================

def _texto_camara(id_prop, debug: bool = False) -> tuple[str, str]:
    """Baixa o inteiro teor de uma proposicao da Camara.
    Retorna (texto, data_ultima_acao).
    O link do texto esta no campo `urlInteiroTeor` dos detalhes da proposicao.
    """
    url = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{id_prop}"
    data_ultima = ""
    try:
        r = requests.get(url, timeout=TIMEOUT, headers={"Accept": "application/json"})
        r.raise_for_status()
        dados = r.json().get("dados") or {}
        doc_url = dados.get("urlInteiroTeor") or ""
        # Aproveita o request para pegar a data da ultima acao
        stat = dados.get("statusProposicao") or {}
        data_ultima = stat.get("dataHora", "") or ""
        if data_ultima and "T" in data_ultima:
            data_ultima = data_ultima.split("T")[0]
        if debug:
            print(f"\n    [DEBUG Camara {id_prop}] urlInteiroTeor: {doc_url or '(vazio)'}")
            print(f"    [DEBUG Camara {id_prop}] data_ultima_acao: {data_ultima or '(vazio)'}")
        if not doc_url:
            return "", data_ultima
        rd = requests.get(doc_url, timeout=TIMEOUT)
        rd.raise_for_status()
        content_type = rd.headers.get("Content-Type", "").lower()
        if "pdf" in content_type or doc_url.lower().endswith(".pdf"):
            try:
                from pypdf import PdfReader
                from io import BytesIO
                reader = PdfReader(BytesIO(rd.content))
                texto = " ".join(page.extract_text() or "" for page in reader.pages)
            except ImportError:
                if debug:
                    print(f"    [DEBUG Camara {id_prop}] pypdf nao instalado - pulando PDF")
                return "", data_ultima
            except Exception as e:
                if debug:
                    print(f"    [DEBUG Camara {id_prop}] erro ao ler PDF: {e}")
                return "", data_ultima
        else:
            texto = re.sub(r"<[^>]+>", " ", rd.text)
        texto = re.sub(r"\s+", " ", texto)
        return texto.strip(), data_ultima
    except Exception as e:
        if debug:
            print(f"    [DEBUG Camara {id_prop}] erro: {e}")
        return "", data_ultima


def _texto_senado(id_processo, debug: bool = False) -> str:
    """Baixa o inteiro teor de um processo do Senado via /processo/documento."""
    url = "https://legis.senado.leg.br/dadosabertos/processo/documento"
    try:
        r = requests.get(url, params={"idProcesso": id_processo},
                         timeout=TIMEOUT, headers={"Accept": "application/json"})
        r.raise_for_status()
        docs = r.json() or []
        if isinstance(docs, dict):
            docs = [docs]
        if debug:
            print(f"\n    [DEBUG Senado {id_processo}] {len(docs)} docs")
            if docs:
                print(f"    primeiro: {str(docs[0])[:300]}")
        if not docs:
            return ""
        doc_url = ""
        for d in docs:
            if d.get("urlDocumento"):
                doc_url = d["urlDocumento"]
                break
        if not doc_url:
            if debug:
                print(f"    [DEBUG Senado {id_processo}] sem urlDocumento")
            return ""
        rd = requests.get(doc_url, timeout=TIMEOUT)
        rd.raise_for_status()
        texto = re.sub(r"<[^>]+>", " ", rd.text)
        texto = re.sub(r"\s+", " ", texto)
        return texto.strip()
    except Exception as e:
        if debug:
            print(f"    [DEBUG Senado {id_processo}] erro: {e}")
        return ""


def baixar_inteiro_teor(df: pd.DataFrame) -> pd.DataFrame:
    """Baixa o inteiro teor de todas as proposicoes."""
    df = df.copy()
    total = len(df)
    print(f"  Baixando inteiro teor de {total} proposicoes...")

    textos = []
    datas_mov = []  # datas de ultima movimentacao coletadas no teor (Camara)
    com_teor = 0
    sem_teor = 0
    vistas_camara = 0
    vistas_senado = 0
    for i, (_, row) in enumerate(df.iterrows(), 1):
        if row["casa"] == "Câmara":
            debug = vistas_camara < 3
            vistas_camara += 1
            texto, data_ult = _texto_camara(row["id"], debug=debug)
            datas_mov.append(data_ult)
        else:
            debug = vistas_senado < 3
            vistas_senado += 1
            texto = _texto_senado(row["id"], debug=debug)
            datas_mov.append("")  # Senado ja preenche no momento da coleta
        textos.append(texto)

        if texto:
            com_teor += 1
        else:
            sem_teor += 1

        # Mostra progresso a cada 50 proposicoes (e na ultima)
        if i % 50 == 0 or i == total:
            pct = (i / total) * 100
            print(f"    [{i}/{total}] {pct:.1f}%  |  com teor: {com_teor}  |  sem teor: {sem_teor}")

        time.sleep(0.3)

    df["inteiro_teor"] = textos
    # Atualiza data_ultima_movimentacao para a Camara com o que veio do teor
    # Garante que a coluna seja string/object antes do update para evitar
    # conversões implícitas do pandas que podem virar NaT.
    if "data_ultima_movimentacao" not in df.columns:
        df["data_ultima_movimentacao"] = ""
    df["data_ultima_movimentacao"] = df["data_ultima_movimentacao"].astype("object")
    datas_preenchidas = 0
    for idx, data_ult in zip(df.index, datas_mov):
        if data_ult:
            df.at[idx, "data_ultima_movimentacao"] = str(data_ult)
            datas_preenchidas += 1
    print(f"  Datas de ultima movimentacao preenchidas (Camara): {datas_preenchidas}")
    df["texto_classificado"] = df.apply(
        lambda r: r["inteiro_teor"] if r["inteiro_teor"] else r["ementa"],
        axis=1,
    )
    df["fonte_classificacao"] = df["inteiro_teor"].apply(
        lambda t: "inteiro_teor" if t else "ementa"
    )
    return df


# ===================================================================
# Classificação
# ===================================================================

def _hits(padroes, texto: str) -> list[str]:
    return [p.pattern for p in padroes if p.search(texto)]


def classificar_texto(texto: str) -> dict:
    texto = texto or ""
    hits_lc200 = _hits(RE_LC200, texto)
    hits_meta  = _hits(RE_META, texto)
    hits_risco = _hits(RE_RISCO, texto)

    atinge_lc200 = bool(hits_lc200)
    atinge_meta  = bool(hits_meta)

    if atinge_lc200 and atinge_meta:
        score = 3
    elif (atinge_lc200 or atinge_meta) and hits_risco:
        score = 3
    elif atinge_lc200 or atinge_meta:
        score = 2
    elif hits_risco:
        score = 1
    else:
        score = 0

    return {
        "atinge_lc200": atinge_lc200,
        "atinge_meta":  atinge_meta,
        "termos_lc200": " | ".join(hits_lc200),
        "termos_meta":  " | ".join(hits_meta),
        "termos_risco": " | ".join(hits_risco),
        "score_fiscal": score,
    }


def classificar_df(df: pd.DataFrame) -> pd.DataFrame:
    """Baixa inteiro teor e classifica diretamente sobre ele."""
    if df.empty:
        return df
    df = baixar_inteiro_teor(df)
    classif = df["texto_classificado"].apply(classificar_texto).apply(pd.Series)
    return pd.concat([df.reset_index(drop=True), classif], axis=1)


# ===================================================================
# Persistência
# ===================================================================

def salvar(df: pd.DataFrame, caminho: Path = DB_PATH) -> None:
    df = df.copy()
    df["coletado_em"] = datetime.now().isoformat(timespec="seconds")
    # Remove colunas de texto bruto antes de salvar - o inteiro teor pode
    # pesar mais de 1 GB para coletas grandes, e ele ja cumpriu sua funcao
    # (classificar). O painel nao usa esse campo.
    colunas_pesadas = ["inteiro_teor", "texto_classificado"]
    df = df.drop(columns=[c for c in colunas_pesadas if c in df.columns])
    with sqlite3.connect(caminho) as con:
        df.to_sql("proposicoes", con, if_exists="replace", index=False)


# ===================================================================
# Pipeline
# ===================================================================

def main() -> None:
    print(f"Janela de coleta: últimos {DIAS_LOOKBACK} dias (por movimentação)\n")

    print("Coletando Câmara...")
    df_cam = coletar_camara()
    print(f"  → {len(df_cam)} proposições\n")

    print("Coletando Senado...")
    df_sen = coletar_senado()
    print(f"  → {len(df_sen)} matérias\n")

    df = pd.concat([df_cam, df_sen], ignore_index=True)
    if df.empty:
        print("Nenhum dado coletado.")
        return

    df = classificar_df(df)
    salvar(df)

    print("=" * 55)
    print("Resumo da triagem")
    print("=" * 55)
    print(f"Total coletado                  : {len(df)}")
    print(f"Classificados pelo inteiro teor : {(df['fonte_classificacao'] == 'inteiro_teor').sum()}")
    print(f"Classificados pela ementa       : {(df['fonte_classificacao'] == 'ementa').sum()}")
    print(f"Score 3 (alto risco)            : {(df['score_fiscal'] == 3).sum()}")
    print(f"Score 2 (LC200 ou meta)         : {(df['score_fiscal'] == 2).sum()}")
    print(f"Score 1 (vigilância)            : {(df['score_fiscal'] == 1).sum()}")
    print(f"Score 0 (irrelevantes)          : {(df['score_fiscal'] == 0).sum()}")
    print(f"\nBase salva em: {DB_PATH}")
    print("Para abrir o painel:  streamlit run painel.py")


if __name__ == "__main__":
    main()