"""
Analisador Esportivo Pro 17 – Versão Aprimorada (app.py)
========================================================
Principais melhorias:
- Geração automática de previsões para os próximos jogos.
- Aprendizado automático a cada acesso (sem clique).
- game_id confiável (sem "None").
- Recalculação única dos ajustes.
- Normalização robusta (fc/sc apenas no final).
- Uso correto do home_adv no modelo ML.
- Cache otimizado de jogos por dia.
"""

from __future__ import annotations

import math
import os
import re
import sqlite3
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional, Tuple

import pandas as pd
import streamlit as st

try:
    import requests
    REQUESTS_OK = True
except Exception:
    REQUESTS_OK = False

try:
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    SKLEARN_OK = True
except Exception:
    SKLEARN_OK = False


# ======================= CONFIGURAÇÃO =======================
st.set_page_config(
    page_title="Analisador Esportivo Pro 17",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
HEADERS = {"User-Agent": "AnalisadorEsportivoPro/17.0"}
DB_PATH = "data/modelo_v17.db"

MAX_GOLS = 10
RETRIES = 3
MIN_JOGOS_TREINO = 20
DIXON_COLES_RHO = -0.13

HOME_ADV_LIGA = {
    "bra.1": 0.28, "bra.2": 0.27, "bra.copa_do_brazil": 0.22,
    "eng.1": 0.22, "esp.1": 0.24, "ita.1": 0.25, "ger.1": 0.26,
    "fra.1": 0.24, "uefa.champions": 0.20, "uefa.europa": 0.18,
    "conmebol.libertadores": 0.30, "conmebol.sudamericana": 0.28,
}

LIGAS = {
    "Brasileirão Série A": "bra.1",
    "Brasileirão Série B": "bra.2",
    "Copa do Brasil": "bra.copa_do_brazil",
    "Premier League": "eng.1",
    "La Liga": "esp.1",
    "Série A Itália": "ita.1",
    "Bundesliga": "ger.1",
    "Ligue 1": "fra.1",
    "Champions League": "uefa.champions",
    "Europa League": "uefa.europa",
    "Libertadores": "conmebol.libertadores",
    "Sul-Americana": "conmebol.sudamericana",
}

# ---- forças e aliases (mantidos iguais, mas resumidos) ----
FORCA_BASE = {
    "flamengo": 86, "palmeiras": 84, "botafogo": 79, "atletico-mg": 76,
    "sao paulo": 78, "fluminense": 77, "gremio": 74, "internacional": 75,
    "corinthians": 76, "cruzeiro": 73, "bahia": 74, "fortaleza": 73,
    "vasco": 70, "santos": 72, "ceara": 69, "sport": 68, "vitoria": 69,
    "coritiba": 68, "athletico-pr": 72, "atletico goianiense": 68,
    "goias": 68, "cuiaba": 67, "juventude": 67, "chapecoense": 65,
    "crb": 65, "csa": 64, "paysandu": 64, "remo": 64,
    "ponte preta": 65, "guarani": 64, "novorizontino": 67,
    "mirassol": 68, "operario pr": 64, "vila nova": 66,
    "amazonas": 64, "america mineiro": 68, "bragantino": 72,
    "red bull bragantino": 72, "sao bernardo": 63, "tombense": 62,
    "volta redonda": 62, "santa cruz": 61, "retro": 61,
    "manchester city": 91, "arsenal": 88, "liverpool": 88,
    "chelsea": 82, "tottenham hotspur": 80, "manchester united": 81,
    "real madrid": 90, "barcelona": 87, "atletico madrid": 84,
    "bayern munich": 88, "borussia dortmund": 82, "bayer leverkusen": 84,
    "inter milan": 86, "juventus": 82, "milan": 81,
    "paris saint-germain": 88,
}

FORCA_TENIS = {
    "jannik sinner": 94, "carlos alcaraz": 93, "novak djokovic": 92,
    "daniil medvedev": 88, "alexander zverev": 88, "iga swiatek": 94,
    "aryna sabalenka": 93, "coco gauff": 90, "elena rybakina": 89,
    "jessica pegula": 86,
}

FORCA_BASQUETE = {
    "boston celtics": 92, "denver nuggets": 90, "oklahoma city thunder": 89,
    "milwaukee bucks": 87, "minnesota timberwolves": 86, "dallas mavericks": 85,
    "new york knicks": 84, "cleveland cavaliers": 83, "phoenix suns": 82,
    "la clippers": 82, "los angeles lakers": 80, "golden state warriors": 79,
    "miami heat": 78, "philadelphia 76ers": 78, "sacramento kings": 76,
    "indiana pacers": 76, "orlando magic": 75, "houston rockets": 74,
    "new orleans pelicans": 74, "atlanta hawks": 72, "chicago bulls": 71,
    "utah jazz": 70, "brooklyn nets": 69, "memphis grizzlies": 69,
    "toronto raptors": 68, "san antonio spurs": 68, "portland trail blazers": 66,
    "charlotte hornets": 65, "detroit pistons": 64, "washington wizards": 63,
}

ALIASES = {
    "man city": "manchester city", "man utd": "manchester united",
    "man united": "manchester united", "tottenham": "tottenham hotspur",
    "spurs": "tottenham hotspur", "psg": "paris saint-germain",
    "paris sg": "paris saint-germain", "inter": "inter milan",
    "internazionale": "inter milan", "atletico mineiro": "atletico-mg",
    "atletico mg": "atletico-mg", "vasco da gama": "vasco",
    "sao paulo fc": "sao paulo", "gremio fbpa": "gremio",
    "athletico paranaense": "athletico-pr", "atletico pr": "athletico-pr",
    "red bull bragantino": "bragantino", "operario": "operario pr",
    "operario-pr": "operario pr", "celtics": "boston celtics",
    "nuggets": "denver nuggets", "thunder": "oklahoma city thunder",
    "bucks": "milwaukee bucks", "timberwolves": "minnesota timberwolves",
    "mavs": "dallas mavericks", "mavericks": "dallas mavericks",
    "knicks": "new york knicks", "cavs": "cleveland cavaliers",
    "cavaliers": "cleveland cavaliers", "suns": "phoenix suns",
    "clippers": "la clippers", "lakers": "los angeles lakers",
    "warriors": "golden state warriors", "heat": "miami heat",
    "sixers": "philadelphia 76ers", "76ers": "philadelphia 76ers",
}

CLASSICOS = {
    ("flamengo", "vasco"), ("flamengo", "fluminense"), ("flamengo", "botafogo"),
    ("palmeiras", "corinthians"), ("sao paulo", "corinthians"),
    ("sao paulo", "palmeiras"), ("gremio", "internacional"),
    ("atletico-mg", "cruzeiro"), ("real madrid", "barcelona"),
    ("manchester united", "manchester city"), ("inter milan", "milan"),
}


# ======================= ESTILO =======================
def aplicar_estilo() -> None:
    st.markdown("""<style>
        html, body, [data-testid="stAppViewContainer"] { background: #f4f6fb; }
        .block-container { padding: 1.5rem 1.4rem 5rem 1.4rem; max-width: 1320px; }
        h1 { font-size: 1.55rem !important; margin-bottom: .2rem !important; font-weight: 750 !important; }
        section[data-testid="stSidebar"] { background: #172033 !important; }
        section[data-testid="stSidebar"] * { color: #e7edf7 !important; }
        div[data-testid="stMetric"] {
            background: #ffffff; border: 1px solid #dde5f0; border-radius: 8px;
            padding: .55rem .7rem; box-shadow: 0 1px 3px rgba(16,24,40,.06);
        }
        .pro-card {
            border: 1px solid #dde5f0; border-radius: 8px; padding: .85rem 1rem;
            background: #ffffff; margin: .45rem 0; box-shadow: 0 1px 4px rgba(16,24,40,.05);
        }
        .chip {
            display: inline-block; border-radius: 999px; padding: .12rem .55rem; margin: .08rem .12rem .08rem 0;
            font-size: .75rem; font-weight: 700;
        }
        .chip-green { background:#dcfce7; color:#166534; }
        .chip-red { background:#fee2e2; color:#991b1b; }
        .chip-blue { background:#dbeafe; color:#1e40af; }
        .chip-yellow { background:#fef3c7; color:#92400e; }
        .chip-gray { background:#f1f5f9; color:#475569; }
    </style>""", unsafe_allow_html=True)


# ======================= BANCO DE DADOS =======================
def conectar_db() -> sqlite3.Connection:
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db() -> None:
    conn = conectar_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS previsoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT UNIQUE,
            esporte TEXT, liga_id TEXT, liga_nome TEXT, data_jogo TEXT,
            home TEXT, away TEXT, forca_home REAL, forca_away REAL,
            home_adv REAL, contexto TEXT,
            mercado_base TEXT, codigo_base TEXT, prob_base REAL,
            mercado_aprendido TEXT, codigo_aprendido TEXT, prob_aprendido REAL,
            ajuste_aplicado REAL, placar_previsto TEXT,
            home_score INTEGER, away_score INTEGER,
            acertou_base INTEGER, acertou_aprendido INTEGER,
            finalizado INTEGER DEFAULT 0, criado_em TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback_rapido (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT, codigo TEXT, acertou INTEGER,
            registrado_em TEXT, UNIQUE(game_id, codigo)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ajustes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chave TEXT UNIQUE, fator REAL DEFAULT 0,
            jogos INTEGER DEFAULT 0, acertos INTEGER DEFAULT 0,
            taxa REAL DEFAULT 0, confianca REAL DEFAULT 0,
            atualizado_em TEXT
        )
    """)
    # Garantir colunas essenciais
    colunas = [
        ("previsoes", "esporte", "TEXT"),
        ("previsoes", "forca_home", "REAL"),
        ("previsoes", "forca_away", "REAL"),
        ("previsoes", "home_adv", "REAL DEFAULT 0.25"),
        ("previsoes", "contexto", "TEXT"),
    ]
    for tabela, coluna, tipo in colunas:
        cur.execute(f"PRAGMA table_info({tabela})")
        if coluna not in {row[1] for row in cur.fetchall()}:
            cur.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
    conn.commit()
    conn.close()

def ler_tabela(sql: str, params=()) -> pd.DataFrame:
    conn = conectar_db()
    try:
        return pd.read_sql_query(sql, conn, params=params)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()

def executar(sql: str, params=()) -> None:
    conn = conectar_db()
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


# ======================= UTILITÁRIOS =======================
def nome_limpo(nome: Any) -> str:
    return " ".join(str(nome or "").strip().split())

def normalizar(nome: str) -> str:
    nome = nome_limpo(nome).lower()
    nome = unicodedata.normalize("NFD", nome)
    nome = "".join(c for c in nome if unicodedata.category(c) != "Mn")
    nome = nome.replace("'", "").replace(".", "").replace(",", "")
    # Remove FC/SC apenas no final da string
    nome = re.sub(r"\b(fc|sc)\b$", "", nome).strip()
    nome = " ".join(nome.split())
    return ALIASES.get(nome, nome)

def clamp(valor: float, mini: float, maxi: float) -> float:
    return max(mini, min(maxi, valor))

def pct(valor: float) -> str:
    return f"{valor * 100:.1f}%"

def faixa_prob(prob: float) -> str:
    if prob >= 0.75: return "Muito alta"
    if prob >= 0.62: return "Alta"
    if prob >= 0.52: return "Média"
    return "Baixa"

def contexto_jogo(home: str, away: str, liga_id: str) -> str:
    h, a = normalizar(home), normalizar(away)
    partes = [liga_id]
    if tuple(sorted([h, a])) in CLASSICOS:
        partes.append("classico")
    if h in FORCA_BASE and a in FORCA_BASE:
        diff = abs(FORCA_BASE[h] - FORCA_BASE[a])
        if diff <= 4: partes.append("equilibrado")
        elif diff >= 12: partes.append("favorito_forte")
    return "|".join(partes)

def game_id_manual(esporte: str, liga_id: str, home: str, away: str, data_jogo: date) -> str:
    raw = f"{esporte}:{liga_id}:{data_jogo.isoformat()}:{normalizar(home)}:{normalizar(away)}"
    return raw.replace(" ", "_")

def parse_data_espn(valor: Any) -> Optional[datetime]:
    if not valor: return None
    texto = str(valor).replace("Z", "+00:00")
    try:
        data_hora = datetime.fromisoformat(texto)
        if data_hora.tzinfo is None:
            data_hora = data_hora.replace(tzinfo=timezone.utc)
        return data_hora.astimezone(timezone.utc)
    except ValueError:
        return None


# ======================= CHAMADAS À API =======================
@st.cache_data(ttl=60*30, show_spinner=False)
def api_get_json(url: str, params=None) -> Optional[dict]:
    if not REQUESTS_OK: return None
    params = params or {}
    for t in range(RETRIES):
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=12)
            if resp.status_code == 200: return resp.json()
            if resp.status_code in {404, 422}: return None
        except Exception:
            pass
        time.sleep(0.8 * (2**t))
    return None

@st.cache_data(ttl=60*60, show_spinner=False)
def buscar_tabela_espn(liga_id: str) -> pd.DataFrame:
    data = api_get_json(f"{ESPN_BASE}/{liga_id}/standings")
    rows = []
    if not data: return pd.DataFrame(rows)

    groups = data.get("children") or [{"standings": data.get("standings", [])}]
    for group in groups:
        entries = group.get("standings", {}).get("entries", [])
        if not entries: entries = group.get("entries", [])
        for pos, item in enumerate(entries, start=1):
            team = item.get("team", {})
            stats = {s.get("name"): s.get("value") for s in item.get("stats", [])}
            nome = team.get("displayName") or team.get("name") or ""
            if nome:
                rows.append({
                    "pos": pos, "time": nome, "normalizado": normalizar(nome),
                    "pontos": float(stats.get("points", stats.get("PTS", 0))),
                    "jogos": float(stats.get("gamesPlayed", stats.get("GP", 0))),
                    "vitorias": float(stats.get("wins", 0)),
                    "empates": float(stats.get("ties", stats.get("draws", 0))),
                    "derrotas": float(stats.get("losses", 0)),
                })
    return pd.DataFrame(rows)

# Cache por dia para evitar requisições repetidas
@st.cache_data(ttl=60*10, show_spinner=False)
def _buscar_jogos_dia(liga_id: str, dia_iso: str) -> pd.DataFrame:
    url = f"{ESPN_BASE}/{liga_id}/scoreboard"
    data = api_get_json(url, {"dates": dia_iso, "limit": 300})
    rows = []
    if not data: return pd.DataFrame(rows)

    for event in data.get("events", []):
        data_jogo = parse_data_espn(event.get("date"))
        if not data_jogo: continue
        competition = (event.get("competitions") or [{}])[0]
        competitors = competition.get("competitors") or []
        home = away = home_score = away_score = None
        for comp in competitors:
            team = comp.get("team", {})
            nome = team.get("displayName") or team.get("shortDisplayName") or team.get("name")
            if comp.get("homeAway") == "home":
                home, home_score = nome, comp.get("score")
            elif comp.get("homeAway") == "away":
                away, away_score = nome, comp.get("score")
        if not home or not away: continue

        status = event.get("status", {})
        tipo_status = status.get("type", {})
        completed = bool(tipo_status.get("completed"))
        game_id_raw = str(event.get("id") or competition.get("id") or "")
        # Garantir ID válido
        if not game_id_raw or game_id_raw.lower() == "none":
            game_id_raw = game_id_manual("futebol", liga_id, home, away, data_jogo.date())

        rows.append({
            "game_id": game_id_raw,
            "data_utc": data_jogo.isoformat(),
            "data_local": data_jogo.astimezone().strftime("%d/%m %H:%M"),
            "data_jogo": data_jogo.date().isoformat(),
            "home": nome_limpo(home),
            "away": nome_limpo(away),
            "home_score": int(home_score) if str(home_score).isdigit() else None,
            "away_score": int(away_score) if str(away_score).isdigit() else None,
            "status": tipo_status.get("shortDetail") or tipo_status.get("state", ""),
            "completed": completed,
        })
    return pd.DataFrame(rows)

def buscar_jogos_intervalo(liga_id: str, inicio: datetime, fim: datetime) -> pd.DataFrame:
    # Gera todos os dias do intervalo
    dias = []
    atual = inicio.date()
    fim_dia = fim.date()
    while atual <= fim_dia:
        dias.append(atual.strftime("%Y%m%d"))
        atual += timedelta(days=1)

    dfs = []
    for dia in dias:
        dfs.append(_buscar_jogos_dia(liga_id, dia))
    if not dfs:
        return pd.DataFrame()
    df = pd.concat(dfs, ignore_index=True)
    if df.empty:
        return df
    # Filtra exatamente pelo intervalo UTC
    df["data_utc_dt"] = pd.to_datetime(df["data_utc"]).dt.tz_localize(None)
    mask = (df["data_utc_dt"] >= inicio) & (df["data_utc_dt"] <= fim)
    df = df[mask].drop(columns=["data_utc_dt"])
    return df.drop_duplicates("game_id").sort_values("data_utc").reset_index(drop=True)


# ======================= FORÇAS =======================
def forca_dinamica_futebol(nome: str, liga_id: str) -> Tuple[float, str]:
    chave = normalizar(nome)
    tabela = buscar_tabela_espn(liga_id)
    if not tabela.empty and chave in set(tabela["normalizado"]):
        row = tabela[tabela["normalizado"] == chave].iloc[0]
        total = max(len(tabela), 1)
        rank_score = 92 - ((row["pos"] - 1) / max(total - 1, 1)) * 28
        ppg = row["pontos"] / max(row["jogos"], 1)
        pontos_score = 58 + clamp(ppg / 3, 0, 1) * 34
        forca = (rank_score * 0.58) + (pontos_score * 0.42)
        return round(clamp(forca, 50, 96), 1), "ESPN/tabela"
    if chave in FORCA_BASE:
        return float(FORCA_BASE[chave]), "fallback estático"
    return 68.0, "padrão neutro"

def forca_generica(nome: str, base: dict, padrao=72.0) -> Tuple[float, str]:
    chave = normalizar(nome)
    if chave in base: return float(base[chave]), "base interna"
    return padrao, "padrão neutro"


# ======================= MODELOS =======================
def poisson(k: int, lamb: float) -> float:
    lamb = max(lamb, 0.05)
    return math.exp(-lamb) * (lamb**k) / math.factorial(k)

def dixon_coles_factor(h, a, lh, la, rho):
    if h == 0 and a == 0: return 1 - (lh * la * rho)
    if h == 0 and a == 1: return 1 + (lh * rho)
    if h == 1 and a == 0: return 1 + (la * rho)
    if h == 1 and a == 1: return 1 - rho
    return 1.0

def matriz_placares(forca_home, forca_away, home_adv):
    diff = (forca_home + home_adv * 10) - forca_away
    lambda_h = clamp(1.28 + diff / 34, 0.25, 3.6)
    lambda_a = clamp(1.08 - diff / 40, 0.20, 3.2)
    linhas = []
    total = 0.0
    for h in range(MAX_GOLS + 1):
        for a in range(MAX_GOLS + 1):
            prob = poisson(h, lambda_h) * poisson(a, lambda_a)
            prob *= dixon_coles_factor(h, a, lambda_h, lambda_a, DIXON_COLES_RHO)
            prob = max(prob, 0)
            total += prob
            linhas.append({"home_gols": h, "away_gols": a, "prob": prob})
    df = pd.DataFrame(linhas)
    if total > 0: df["prob"] /= total
    return df.sort_values("prob", ascending=False).reset_index(drop=True)

def probabilidades_futebol(df):
    home_win = df[df["home_gols"] > df["away_gols"]]["prob"].sum()
    draw = df[df["home_gols"] == df["away_gols"]]["prob"].sum()
    away_win = df[df["home_gols"] < df["away_gols"]]["prob"].sum()
    over_15 = df[(df["home_gols"] + df["away_gols"]) > 1.5]["prob"].sum()
    over_25 = df[(df["home_gols"] + df["away_gols"]) > 2.5]["prob"].sum()
    under_35 = df[(df["home_gols"] + df["away_gols"]) < 3.5]["prob"].sum()
    btts = df[(df["home_gols"] > 0) & (df["away_gols"] > 0)]["prob"].sum()
    return {
        "Casa vence": home_win, "Empate": draw, "Fora vence": away_win,
        "Dupla 1X": home_win + draw, "Dupla X2": draw + away_win,
        "Dupla 12": home_win + away_win,
        "Over 1.5": over_15, "Over 2.5": over_25, "Under 3.5": under_35,
        "Ambos marcam": btts,
    }

def melhor_mercado(probs):
    ordenados = sorted(probs.items(), key=lambda x: x[1], reverse=True)
    mercado, prob = ordenados[0]
    codigo = mercado.lower().replace(" ", "_").replace(".", "")
    return mercado, codigo, prob

def ajuste_aprendido(codigo, contexto):
    chaves = [f"{contexto}:{codigo}", f"global:{codigo}"]
    df = ler_tabela("SELECT chave, fator, confianca FROM ajustes WHERE chave IN (?,?)", (chaves[0], chaves[1]))
    if df.empty: return 0.0
    df["peso"] = df["confianca"].fillna(0).clip(0, 1)
    if df["peso"].sum() <= 0:
        return float(df["fator"].mean())
    return float((df["fator"] * df["peso"]).sum() / df["peso"].sum())

def aplicar_ajuste(prob, codigo, contexto):
    ajuste = ajuste_aprendido(codigo, contexto)
    return clamp(prob + ajuste, 0.03, 0.97), ajuste

def prever_ml(forca_home, forca_away, home_adv):
    if not SKLEARN_OK: return None
    df = ler_tabela("""
        SELECT forca_home, forca_away, home_adv, home_score, away_score
        FROM previsoes
        WHERE finalizado = 1 AND home_score IS NOT NULL AND away_score IS NOT NULL
          AND forca_home IS NOT NULL AND forca_away IS NOT NULL AND home_adv IS NOT NULL
    """)
    if len(df) < MIN_JOGOS_TREINO: return None

    y = []
    for _, row in df.iterrows():
        if row["home_score"] > row["away_score"]: y.append(0)
        elif row["home_score"] == row["away_score"]: y.append(1)
        else: y.append(2)
    if len(set(y)) < 2: return None

    X = df[["forca_home", "forca_away", "home_adv"]].astype(float).copy()
    X["diff"] = X["forca_home"] - X["forca_away"]
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    model = LogisticRegression(max_iter=500)
    model.fit(Xs, y)
    atual = scaler.transform([[forca_home, forca_away, home_adv, forca_home - forca_away]])
    probs = model.predict_proba(atual)[0]
    classes = list(model.classes_)
    mapa = {0: "Casa vence", 1: "Empate", 2: "Fora vence"}
    return {mapa[c]: float(probs[i]) for i, c in enumerate(classes)}

def prob_tenis(fa, fb, superficie):
    bonus = {"Dura": 0.0, "Saibro": 0.8, "Grama": 0.5, "Indoor": 0.3}.get(superficie, 0.0)
    diff = (fa + bonus) - fb
    p1 = 1 / (1 + math.exp(-diff / 8))
    p1 = clamp(p1, 0.08, 0.92)
    return {"Jogador 1 vence": p1, "Jogador 2 vence": 1 - p1}

def prob_basquete(fh, fa):
    diff = (fh + 3.0) - fa
    p_home = 1 / (1 + math.exp(-diff / 7.5))
    total = 214 + (fh + fa - 150) * 0.9
    spread = -round(diff / 2.2, 1)
    return {
        "Casa vence": clamp(p_home, 0.05, 0.95),
        "Fora vence": clamp(1 - p_home, 0.05, 0.95),
        "Linha total projetada": float(round(total, 1)),
        "Handicap casa projetado": float(spread),
    }


# ======================= PERSISTÊNCIA =======================
def salvar_previsao(game_id, esporte, liga_id, liga_nome, data_jogo, home, away,
                    forca_home, forca_away, home_adv, contexto,
                    mercado, codigo, prob_base, prob_apr, ajuste, placar):
    executar("""
        INSERT OR REPLACE INTO previsoes (
            game_id, esporte, liga_id, liga_nome, data_jogo, home, away,
            forca_home, forca_away, home_adv, contexto,
            mercado_base, codigo_base, prob_base,
            mercado_aprendido, codigo_aprendido, prob_aprendido,
            ajuste_aplicado, placar_previsto, criado_em
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);
    """, (game_id, esporte, liga_id, liga_nome, data_jogo.isoformat(), home, away,
          forca_home, forca_away, home_adv, contexto,
          mercado, codigo, prob_base, mercado, codigo, prob_apr, ajuste, placar,
          datetime.now().isoformat(timespec="seconds")))

def registrar_feedback(game_id, codigo, acertou):
    executar("""
        INSERT OR REPLACE INTO feedback_rapido (game_id, codigo, acertou, registrado_em)
        VALUES (?,?,?,?)
    """, (game_id, codigo, int(acertou), datetime.now().isoformat(timespec="seconds")))

def mercado_acertou(codigo, home_score, away_score):
    total = home_score + away_score
    casa = home_score > away_score
    empate = home_score == away_score
    fora = home_score < away_score
    ambos = home_score > 0 and away_score > 0
    regras = {
        "casa_vence": casa, "empate": empate, "fora_vence": fora,
        "dupla_1x": casa or empate, "dupla_x2": empate or fora,
        "dupla_12": casa or fora,
        "over_15": total > 1.5, "over_25": total > 2.5,
        "under_35": total < 3.5, "ambos_marcam": ambos,
    }
    return int(bool(regras.get(codigo, False)))

def recalcular_ajustes():
    df = ler_tabela("""
        SELECT p.contexto, p.codigo_base AS codigo, f.acertou
        FROM feedback_rapido f
        JOIN previsoes p ON p.game_id = f.game_id AND p.codigo_base = f.codigo
        WHERE f.acertou IS NOT NULL
    """)
    if df.empty: return

    conn = conectar_db()
    cur = conn.cursor()
    for (contexto, codigo), grupo in df.groupby(["contexto", "codigo"]):
        jogos = int(len(grupo))
        acertos = int(grupo["acertou"].sum())
        taxa = acertos / max(jogos, 1)
        fator = clamp((taxa - 0.55) * 0.18, -0.08, 0.08)
        confianca = clamp(jogos / 50, 0, 1)
        chave = f"{contexto}:{codigo}"
        cur.execute("""
            INSERT OR REPLACE INTO ajustes (chave, fator, jogos, acertos, taxa, confianca, atualizado_em)
            VALUES (?,?,?,?,?,?,?)
        """, (chave, fator, jogos, acertos, taxa, confianca, datetime.now().isoformat(timespec="seconds")))

    for codigo, grupo in df.groupby("codigo"):
        jogos = int(len(grupo))
        acertos = int(grupo["acertou"].sum())
        taxa = acertos / max(jogos, 1)
        fator = clamp((taxa - 0.55) * 0.15, -0.06, 0.06)
        confianca = clamp(jogos / 80, 0, 1)
        cur.execute("""
            INSERT OR REPLACE INTO ajustes (chave, fator, jogos, acertos, taxa, confianca, atualizado_em)
            VALUES (?,?,?,?,?,?,?)
        """, (f"global:{codigo}", fator, jogos, acertos, taxa, confianca, datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()


# ======================= APRENDIZADO AUTOMÁTICO =======================
def aprender_ultimas_24h(liga_id: str) -> int:
    """Atualiza previsões finalizadas com resultados reais da ESPN. Retorna número de atualizações."""
    agora = datetime.now(timezone.utc)
    inicio = agora - timedelta(hours=24)
    jogos = buscar_jogos_intervalo(liga_id, inicio, agora)
    if jogos.empty:
        return 0
    finalizados = jogos[jogos["completed"] == True].copy()
    if finalizados.empty:
        return 0
    previsoes = ler_tabela("""
        SELECT * FROM previsoes
        WHERE esporte = 'futebol' AND liga_id = ? AND finalizado = 0
          AND data_jogo >= ? AND data_jogo <= ?
    """, (liga_id, (inicio - timedelta(days=2)).strftime("%Y-%m-%d"), agora.strftime("%Y-%m-%d")))
    if previsoes.empty:
        return 0

    atualizados = 0
    for _, jogo in finalizados.iterrows():
        if pd.isna(jogo["home_score"]) or pd.isna(jogo["away_score"]):
            continue
        jogo_id = str(jogo["game_id"])
        jogo_data = jogo["data_jogo"]
        jogo_home = normalizar(jogo["home"])
        jogo_away = normalizar(jogo["away"])
        match = previsoes[
            (previsoes["game_id"].astype(str) == jogo_id) |
            ((previsoes["data_jogo"].astype(str) == jogo_data) &
             (previsoes["home"].apply(normalizar) == jogo_home) &
             (previsoes["away"].apply(normalizar) == jogo_away))
        ]
        if match.empty:
            continue
        home_score = int(jogo["home_score"])
        away_score = int(jogo["away_score"])
        for _, prev in match.iterrows():
            codigo_base = str(prev.get("codigo_base", ""))
            codigo_apr = str(prev.get("codigo_aprendido", codigo_base))
            acertou_base = mercado_acertou(codigo_base, home_score, away_score)
            acertou_apr = mercado_acertou(codigo_apr, home_score, away_score)
            executar("""
                UPDATE previsoes SET
                    game_id = ?, home_score = ?, away_score = ?,
                    acertou_base = ?, acertou_aprendido = ?, finalizado = 1
                WHERE id = ?
            """, (jogo_id, home_score, away_score, acertou_base, acertou_apr, prev["id"]))
            registrar_feedback(jogo_id, codigo_apr, acertou_apr)
            atualizados += 1

    if atualizados > 0:
        recalcular_ajustes()
    return atualizados


# ======================= COMPONENTES VISUAIS =======================
def card(titulo, corpo, tipo="info"):
    cores = {"success": "pro-card-success", "warn": "pro-card-warn", "info": "pro-card-info", "danger": "pro-card-danger"}
    st.markdown(f"""
        <div class="pro-card {cores.get(tipo, 'pro-card-info')}">
            <strong>{titulo}</strong><br>{corpo}
        </div>
    """, unsafe_allow_html=True)

def chips_prob(probs):
    html = []
    for nome, prob in sorted(probs.items(), key=lambda x: x[1], reverse=True):
        if not isinstance(prob, (int, float)) or prob > 1: continue
        cls = "chip-green" if prob >= 0.62 else "chip-yellow" if prob >= 0.52 else "chip-gray"
        html.append(f'<span class="chip {cls}">{nome}: {pct(prob)}</span>')
    st.markdown("".join(html), unsafe_allow_html=True)

def tabela_placares(df, home, away, n=8):
    top = df.head(n).copy()
    top["placar"] = top["home_gols"].astype(str) + " x " + top["away_gols"].astype(str)
    top["probabilidade"] = top["prob"].apply(lambda x: pct(x))
    top["jogo"] = f"{home} x {away}"
    return top[["jogo", "placar", "probabilidade"]]


# ======================= TELAS =======================
def tela_futebol():
    st.header("Futebol")
    liga_nome = st.selectbox("Liga", list(LIGAS.keys()), key="futebol_liga")
    liga_id = LIGAS[liga_nome]

    # Aprendizado automático ao entrar
    if "aprendizado_" + liga_id not in st.session_state:
        with st.spinner("Buscando resultados recentes para aprendizado..."):
            atualizados = aprender_ultimas_24h(liga_id)
            st.session_state["aprendizado_" + liga_id] = time.time()
            st.session_state["atualizados_" + liga_id] = atualizados
    else:
        atualizados = st.session_state.get("atualizados_" + liga_id, 0)
    if atualizados:
        st.success(f"Aprendizado automático: {atualizados} previsões atualizadas com resultados reais.")

    # Botão forçar aprendizado
    col1, col2 = st.columns([0.8, 0.2])
    with col2:
        if st.button("Forçar aprendizado", use_container_width=True):
            with st.spinner("Aprendendo..."):
                novos = aprender_ultimas_24h(liga_id)
                st.session_state["atualizados_" + liga_id] = novos
                st.rerun()

    # Tabela atual
    tabela = buscar_tabela_espn(liga_id)
    agora = datetime.now(timezone.utc)
    proximas_24h = buscar_jogos_intervalo(liga_id, agora, agora + timedelta(hours=24))

    if proximas_24h.empty:
        st.warning("Nenhum jogo nas próximas 24h encontrado na ESPN.")
        return

    st.subheader(f"Jogos das próximas 24h ({len(proximas_24h)})")
    # Geração automática de previsões
    novas_previsoes = 0
    for _, jogo in proximas_24h.iterrows():
        home = str(jogo["home"])
        away = str(jogo["away"])
        data_jogo = datetime.fromisoformat(jogo["data_utc"]).date()
        game_id = jogo["game_id"]
        if normalizar(home) == normalizar(away):
            continue
        # Verificar se já existe previsão salva
        existente = ler_tabela("SELECT id FROM previsoes WHERE game_id = ?", (game_id,))
        if not existente.empty:
            continue
        # Gerar previsão
        forca_h, fonte_h = forca_dinamica_futebol(home, liga_id)
        forca_a, fonte_a = forca_dinamica_futebol(away, liga_id)
        adv = HOME_ADV_LIGA.get(liga_id, 0.25)
        contexto = contexto_jogo(home, away, liga_id)
        matriz = matriz_placares(forca_h, forca_a, adv)
        probs = probabilidades_futebol(matriz)
        mercado, codigo, prob_base = melhor_mercado(probs)
        prob_apr, ajuste = aplicar_ajuste(prob_base, codigo, contexto)
        placar = f"{int(matriz.iloc[0].home_gols)} x {int(matriz.iloc[0].away_gols)}"
        salvar_previsao(
            game_id, "futebol", liga_id, liga_nome, data_jogo, home, away,
            forca_h, forca_a, adv, contexto,
            mercado, codigo, prob_base, prob_apr, ajuste, placar
        )
        novas_previsoes += 1

    if novas_previsoes:
        st.info(f"{novas_previsoes} novas previsões foram geradas automaticamente.")

    # Exibir tabela de previsões
    previsoes_hoje = ler_tabela("""
        SELECT game_id, data_jogo, home, away, mercado_aprendido, prob_aprendido, placar_previsto, finalizado
        FROM previsoes
        WHERE esporte = 'futebol' AND liga_id = ? AND data_jogo = ?
    """, (liga_id, (agora.date()).isoformat()))
    if previsoes_hoje.empty:
        st.write("Nenhuma previsão para hoje.")
        return

    st.dataframe(
        previsoes_hoje[["data_jogo", "home", "away", "mercado_aprendido", "prob_aprendido", "placar_previsto"]],
        hide_index=True, use_container_width=True
    )

    # Detalhes de um jogo específico (para análise manual)
    with st.expander("🔍 Analisar um jogo específico"):
        jogo_selecionado = st.selectbox(
            "Escolha uma partida",
            [f"{row.home} x {row.away}" for _, row in previsoes_hoje.iterrows()]
        )
        if jogo_selecionado:
            idx = [f"{row.home} x {row.away}" for _, row in previsoes_hoje.iterrows()].index(jogo_selecionado)
            prev = previsoes_hoje.iloc[idx]
            st.write(f"**{prev['home']} x {prev['away']}**")
            st.write(f"Mercado: {prev['mercado_aprendido']} → {pct(prev['prob_aprendido'])}")
            st.write(f"Placar mais provável: {prev['placar_previsto']}")
            # Feedback manual
            col_fb1, col_fb2 = st.columns(2)
            if col_fb1.button("Acertou", key=f"acertou_{prev['game_id']}"):
                registrar_feedback(prev["game_id"], prev["mercado_aprendido"].lower().replace(" ", "_"), 1)
                st.success("Feedback registrado.")
                recalcular_ajustes()
            if col_fb2.button("Errou", key=f"errou_{prev['game_id']}"):
                registrar_feedback(prev["game_id"], prev["mercado_aprendido"].lower().replace(" ", "_"), 0)
                st.warning("Feedback registrado.")
                recalcular_ajustes()


def tela_tenis():
    st.header("Tênis")
    circuito = st.selectbox("Circuito", list({"ATP": "atp", "WTA": "wta"}.keys()))
    c1, c2, c3 = st.columns([1, 1, 0.8])
    with c1: jog1 = st.text_input("Jogador 1", "jannik sinner")
    with c2: jog2 = st.text_input("Jogador 2", "carlos alcaraz")
    with c3: superficie = st.selectbox("Superfície", ["Dura", "Saibro", "Grama", "Indoor"])
    if normalizar(jog1) == normalizar(jog2):
        st.error("Jogadores iguais.")
        return
    f1, src1 = forca_generica(jog1, FORCA_TENIS, 80)
    f2, src2 = forca_generica(jog2, FORCA_TENIS, 80)
    probs = prob_tenis(f1, f2, superficie)
    mercado, codigo, prob = melhor_mercado(probs)
    contexto = f"{'atp' if circuito=='ATP' else 'wta'}|{superficie.lower()}"
    prob_apr, ajuste = aplicar_ajuste(prob, codigo, contexto)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(f"Força {jog1}", f"{f1:.1f}", src1)
    m2.metric(f"Força {jog2}", f"{f2:.1f}", src2)
    m3.metric("Mercado", mercado)
    m4.metric("Probabilidade", pct(prob_apr), f"Ajuste {ajuste:+.1%}")
    chips_prob(probs)
    card("Leitura", f"Favorito: <b>{mercado}</b> em quadra de <b>{superficie}</b>.", "success")


def tela_basquete():
    st.header("Basquete")
    liga = st.selectbox("Liga", ["NBA"])
    c1, c2 = st.columns(2)
    with c1: home = st.text_input("Mandante", "boston celtics")
    with c2: away = st.text_input("Visitante", "denver nuggets")
    if normalizar(home) == normalizar(away):
        st.error("Times iguais.")
        return
    fh, sh = forca_generica(home, FORCA_BASQUETE, 74)
    fa, sa = forca_generica(away, FORCA_BASQUETE, 74)
    probs = prob_basquete(fh, fa)
    win_probs = {k: v for k, v in probs.items() if k.endswith("vence")}
    mercado, codigo, prob = melhor_mercado(win_probs)
    contexto = f"nba|regular"
    prob_apr, ajuste = aplicar_ajuste(prob, codigo, contexto)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Força casa", f"{fh:.1f}", sh)
    m2.metric("Força fora", f"{fa:.1f}", sa)
    m3.metric("Linha total", f"{probs['Linha total projetada']:.1f}")
    m4.metric("Handicap", f"{probs['Handicap casa projetado']:+.1f}")
    chips_prob(win_probs)
    card("Leitura", f"Mercado recomendado: <b>{mercado}</b> ({pct(prob_apr)}).", "success")


def tela_historico():
    st.header("Histórico")
    df = ler_tabela("SELECT * FROM previsoes ORDER BY id DESC LIMIT 300")
    if df.empty:
        st.info("Nenhuma previsão salva.")
        return
    c1, c2, c3 = st.columns(3)
    c1.metric("Total", len(df))
    c2.metric("Finalizadas", int(df["finalizado"].fillna(0).sum()))
    c3.metric("Prob. média", pct(df["prob_aprendido"].dropna().mean()) if not df["prob_aprendido"].dropna().empty else "N/A")
    cols = ["data_jogo", "home", "away", "mercado_aprendido", "prob_aprendido", "placar_previsto", "finalizado"]
    st.dataframe(df[cols], hide_index=True, use_container_width=True)


def tela_backtest():
    st.header("Backtesting")
    df = ler_tabela("""
        SELECT p.*, f.acertou
        FROM previsoes p
        LEFT JOIN feedback_rapido f ON f.game_id = p.game_id AND f.codigo = p.codigo_base
        ORDER BY p.id DESC
    """)
    if df.empty or df["acertou"].dropna().empty:
        st.info("Registre feedback para gerar backtest.")
        return
    bt = df.dropna(subset=["acertou"]).copy()
    bt["acertou"] = bt["acertou"].astype(int)
    acuracia = float(bt["acertou"].mean())
    media_prob = float(bt["prob_aprendido"].dropna().mean()) if not bt["prob_aprendido"].dropna().empty else 0
    c1, c2, c3 = st.columns(3)
    c1.metric("Amostra", len(bt))
    c2.metric("Acurácia", pct(acuracia))
    c3.metric("Prob média", pct(media_prob))
    bt = bt.sort_values("id")
    bt["acuracia_acumulada"] = bt["acertou"].expanding().mean()
    st.line_chart(bt.set_index("id")["acuracia_acumulada"])
    resumo = bt.groupby("codigo_base").agg(jogos=("acertou", "count"), acertos=("acertou", "sum"), taxa=("acertou", "mean")).reset_index()
    resumo["taxa"] = resumo["taxa"].apply(lambda x: pct(x))
    st.dataframe(resumo, hide_index=True, use_container_width=True)


def tela_diagnostico():
    st.header("Diagnóstico")
    checks = [
        ("Banco SQLite", os.path.exists(DB_PATH), DB_PATH),
        ("requests", REQUESTS_OK, "API ESPN"),
        ("scikit-learn", SKLEARN_OK, "Modelo aprendido"),
        ("Cache ativo", True, "Chamadas externas"),
        ("Pasta data", os.path.isdir("data"), os.path.abspath("data")),
    ]
    for nome, ok, detalhe in checks:
        card(nome, f"{'OK' if ok else 'Atenção'} - {detalhe}", "success" if ok else "warn")

    st.write("Últimas previsões:")
    df = ler_tabela("SELECT criado_em, esporte, home, away, mercado_aprendido, prob_aprendido FROM previsoes ORDER BY id DESC LIMIT 20")
    st.dataframe(df, hide_index=True, use_container_width=True)


# ======================= APP PRINCIPAL =======================
def main():
    aplicar_estilo()
    init_db()

    st.sidebar.title("Pro 17")
    st.sidebar.caption("Analisador automático com aprendizado contínuo")
    pagina = st.sidebar.radio("Navegação", ["Futebol", "Tênis", "Basquete", "Histórico", "Backtesting", "Diagnóstico"])

    st.title("Analisador Esportivo Pro 17")
    st.caption("Poisson, Dixon-Coles, forças dinâmicas e aprendizado automático.")

    if pagina == "Futebol":
        tela_futebol()
    elif pagina == "Tênis":
        tela_tenis()
    elif pagina == "Basquete":
        tela_basquete()
    elif pagina == "Histórico":
        tela_historico()
    elif pagina == "Backtesting":
        tela_backtest()
    else:
        tela_diagnostico()


if __name__ == "__main__":
    main()
