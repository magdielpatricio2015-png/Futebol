"""
Analisador Esportivo Pro 17 - app.py
====================================

Versao reescrita e corrigida para Streamlit.

Principais correcoes:
- Corrige normalizacao de nomes com unicodedata.normalize.
- Fecha funcoes que estavam incompletas no trecho original.
- Adiciona fallback seguro quando APIs externas falham.
- Evita que ausencia de scikit-learn quebre o app.
- Inicializa banco SQLite automaticamente.
- Adiciona validacao de entradas e mensagens claras.
"""

from __future__ import annotations

import math
import os
import sqlite3
import time
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any, Optional

import pandas as pd
import streamlit as st

try:
    import requests

    REQUESTS_OK = True
except Exception:
    requests = None
    REQUESTS_OK = False

try:
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    SKLEARN_OK = True
except Exception:
    np = None
    LogisticRegression = None
    StandardScaler = None
    SKLEARN_OK = False


# ============================================================================
# CONFIGURACAO
# ============================================================================

st.set_page_config(
    page_title="Analisador Esportivo Pro 17",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
ESPN_SPORTS_BASE = "https://site.api.espn.com/apis/site/v2/sports"
HEADERS = {"User-Agent": "AnalisadorEsportivoPro/17.0"}
DB_PATH = "data/modelo_v17.db"

MAX_GOLS = 10
RETRIES = 3
DEFAULT_HOME_ADV = 0.25
MIN_JOGOS_TREINO = 20
DIXON_COLES_RHO = -0.13

HOME_ADV_LIGA: dict[str, float] = {
    "bra.1": 0.28,
    "bra.2": 0.27,
    "bra.copa_do_brazil": 0.22,
    "eng.1": 0.22,
    "esp.1": 0.24,
    "ita.1": 0.25,
    "ger.1": 0.26,
    "fra.1": 0.24,
    "uefa.champions": 0.20,
    "uefa.europa": 0.18,
    "conmebol.libertadores": 0.30,
    "conmebol.sudamericana": 0.28,
}

LIGAS: dict[str, str] = {
    "Brasileirao Serie A": "bra.1",
    "Brasileirao Serie B": "bra.2",
    "Copa do Brasil": "bra.copa_do_brazil",
    "Premier League": "eng.1",
    "La Liga": "esp.1",
    "Serie A Italia": "ita.1",
    "Bundesliga": "ger.1",
    "Ligue 1": "fra.1",
    "Champions League": "uefa.champions",
    "Europa League": "uefa.europa",
    "Libertadores": "conmebol.libertadores",
    "Sul-Americana": "conmebol.sudamericana",
}

TENIS_LIGAS: dict[str, str] = {"ATP": "atp", "WTA": "wta"}
LIGAS_BASQUETE: dict[str, str] = {"NBA": "nba"}

TIMES_FALLBACK_LIGA: dict[str, list[str]] = {
    "bra.1": [
        "Flamengo", "Palmeiras", "Botafogo", "Atletico-MG", "Sao Paulo",
        "Fluminense", "Gremio", "Internacional", "Corinthians", "Cruzeiro",
        "Bahia", "Fortaleza", "Vasco", "Santos", "Ceara", "Sport",
        "Vitoria", "Bragantino",
    ],
    "bra.2": [
        "Amazonas", "America Mineiro", "Athletico-PR", "Atletico Goianiense",
        "Chapecoense", "Coritiba", "CRB", "Cuiaba", "Goias", "Guarani",
        "Novorizontino", "Operario PR", "Paysandu", "Ponte Preta", "Remo",
        "Vila Nova",
    ],
    "bra.copa_do_brazil": [
        "Flamengo", "Palmeiras", "Botafogo", "Atletico-MG", "Sao Paulo",
        "Fluminense", "Gremio", "Internacional", "Corinthians", "Cruzeiro",
        "Bahia", "Fortaleza", "Vasco", "Santos", "Athletico-PR",
        "America Mineiro",
    ],
    "eng.1": [
        "Manchester City", "Arsenal", "Liverpool", "Chelsea",
        "Tottenham Hotspur", "Manchester United",
    ],
    "esp.1": ["Real Madrid", "Barcelona", "Atletico Madrid"],
    "ita.1": ["Inter Milan", "Juventus", "Milan"],
    "ger.1": ["Bayern Munich", "Borussia Dortmund", "Bayer Leverkusen"],
    "fra.1": ["Paris Saint-Germain"],
    "uefa.champions": [
        "Real Madrid", "Barcelona", "Manchester City", "Arsenal", "Liverpool",
        "Bayern Munich", "Paris Saint-Germain", "Inter Milan",
    ],
    "uefa.europa": [
        "Manchester United", "Tottenham Hotspur", "Chelsea", "Milan",
        "Juventus", "Borussia Dortmund",
    ],
    "conmebol.libertadores": [
        "Flamengo", "Palmeiras", "Botafogo", "Atletico-MG", "Sao Paulo",
        "Fluminense", "Gremio", "Internacional",
    ],
    "conmebol.sudamericana": [
        "Fortaleza", "Bahia", "Cruzeiro", "Corinthians", "Vasco",
        "Bragantino", "Athletico-PR",
    ],
}

FORCA_BASE: dict[str, int] = {
    "flamengo": 86,
    "palmeiras": 84,
    "botafogo": 79,
    "atletico-mg": 76,
    "sao paulo": 78,
    "fluminense": 77,
    "gremio": 74,
    "internacional": 75,
    "corinthians": 76,
    "cruzeiro": 73,
    "bahia": 74,
    "fortaleza": 73,
    "vasco": 70,
    "santos": 72,
    "ceara": 69,
    "sport": 68,
    "vitoria": 69,
    "coritiba": 68,
    "athletico-pr": 72,
    "atletico goianiense": 68,
    "goias": 68,
    "cuiaba": 67,
    "juventude": 67,
    "chapecoense": 65,
    "crb": 65,
    "csa": 64,
    "paysandu": 64,
    "remo": 64,
    "ponte preta": 65,
    "guarani": 64,
    "novorizontino": 67,
    "mirassol": 68,
    "operario pr": 64,
    "vila nova": 66,
    "amazonas": 64,
    "america mineiro": 68,
    "bragantino": 72,
    "red bull bragantino": 72,
    "sao bernardo": 63,
    "tombense": 62,
    "volta redonda": 62,
    "santa cruz": 61,
    "retro": 61,
    "manchester city": 91,
    "arsenal": 88,
    "liverpool": 88,
    "chelsea": 82,
    "tottenham hotspur": 80,
    "manchester united": 81,
    "real madrid": 90,
    "barcelona": 87,
    "atletico madrid": 84,
    "bayern munich": 88,
    "borussia dortmund": 82,
    "bayer leverkusen": 84,
    "inter milan": 86,
    "juventus": 82,
    "milan": 81,
    "paris saint-germain": 88,
}

FORCA_TENIS: dict[str, int] = {
    "jannik sinner": 94,
    "carlos alcaraz": 93,
    "novak djokovic": 92,
    "daniil medvedev": 88,
    "alexander zverev": 88,
    "iga swiatek": 94,
    "aryna sabalenka": 93,
    "coco gauff": 90,
    "elena rybakina": 89,
    "jessica pegula": 86,
}

FORCA_BASQUETE: dict[str, int] = {
    "boston celtics": 92,
    "denver nuggets": 90,
    "oklahoma city thunder": 89,
    "milwaukee bucks": 87,
    "minnesota timberwolves": 86,
    "dallas mavericks": 85,
    "new york knicks": 84,
    "cleveland cavaliers": 83,
    "phoenix suns": 82,
    "la clippers": 82,
    "los angeles lakers": 80,
    "golden state warriors": 79,
    "miami heat": 78,
    "philadelphia 76ers": 78,
    "sacramento kings": 76,
    "indiana pacers": 76,
    "orlando magic": 75,
    "houston rockets": 74,
    "new orleans pelicans": 74,
    "atlanta hawks": 72,
    "chicago bulls": 71,
    "utah jazz": 70,
    "brooklyn nets": 69,
    "memphis grizzlies": 69,
    "toronto raptors": 68,
    "san antonio spurs": 68,
    "portland trail blazers": 66,
    "charlotte hornets": 65,
    "detroit pistons": 64,
    "washington wizards": 63,
}

ALIASES: dict[str, str] = {
    "man city": "manchester city",
    "man utd": "manchester united",
    "man united": "manchester united",
    "tottenham": "tottenham hotspur",
    "spurs": "tottenham hotspur",
    "psg": "paris saint-germain",
    "paris sg": "paris saint-germain",
    "inter": "inter milan",
    "internazionale": "inter milan",
    "atletico mineiro": "atletico-mg",
    "atletico mg": "atletico-mg",
    "vasco da gama": "vasco",
    "sao paulo fc": "sao paulo",
    "gremio fbpa": "gremio",
    "athletico paranaense": "athletico-pr",
    "atletico pr": "athletico-pr",
    "red bull bragantino": "bragantino",
    "operario": "operario pr",
    "operario-pr": "operario pr",
    "sao bernardo fc": "sao bernardo",
    "retro fc": "retro",
    "celtics": "boston celtics",
    "nuggets": "denver nuggets",
    "thunder": "oklahoma city thunder",
    "bucks": "milwaukee bucks",
    "timberwolves": "minnesota timberwolves",
    "mavs": "dallas mavericks",
    "mavericks": "dallas mavericks",
    "knicks": "new york knicks",
    "cavs": "cleveland cavaliers",
    "cavaliers": "cleveland cavaliers",
    "suns": "phoenix suns",
    "clippers": "la clippers",
    "lakers": "los angeles lakers",
    "warriors": "golden state warriors",
    "heat": "miami heat",
    "sixers": "philadelphia 76ers",
    "76ers": "philadelphia 76ers",
}

CLASSICOS: set[tuple[str, str]] = {
    tuple(sorted(["flamengo", "vasco"])),
    tuple(sorted(["flamengo", "fluminense"])),
    tuple(sorted(["flamengo", "botafogo"])),
    tuple(sorted(["palmeiras", "corinthians"])),
    tuple(sorted(["sao paulo", "corinthians"])),
    tuple(sorted(["sao paulo", "palmeiras"])),
    tuple(sorted(["gremio", "internacional"])),
    tuple(sorted(["atletico-mg", "cruzeiro"])),
    tuple(sorted(["real madrid", "barcelona"])),
    tuple(sorted(["manchester united", "manchester city"])),
    tuple(sorted(["inter milan", "milan"])),
}


# ============================================================================
# ESTILO
# ============================================================================


def aplicar_estilo() -> None:
    st.markdown(
        """
        <style>
        html, body, [data-testid="stAppViewContainer"] { overflow-y: auto !important; background: #f4f6fb; }
        .block-container { padding: 1.5rem 1.4rem 5rem 1.4rem; max-width: 1320px; }
        h1 { font-size: 1.55rem !important; margin-bottom: .2rem !important; font-weight: 750 !important; }
        h2 { font-size: 1.2rem !important; font-weight: 650 !important; }
        h3 { font-size: 1.02rem !important; font-weight: 650 !important; }
        section[data-testid="stSidebar"] { background: #172033 !important; }
        section[data-testid="stSidebar"] * { color: #e7edf7 !important; }
        div[data-testid="stMetric"] {
            background: #ffffff; border: 1px solid #dde5f0; border-radius: 8px;
            padding: .55rem .7rem; box-shadow: 0 1px 3px rgba(16,24,40,.06);
        }
        div[data-testid="stMetricValue"] { font-size: 1.08rem !important; }
        .pro-card {
            border: 1px solid #dde5f0; border-radius: 8px; padding: .85rem 1rem;
            background: #ffffff; margin: .45rem 0; box-shadow: 0 1px 4px rgba(16,24,40,.05);
        }
        .pro-card-success { border-left: 4px solid #16a34a; }
        .pro-card-warn { border-left: 4px solid #d97706; }
        .pro-card-info { border-left: 4px solid #2563eb; }
        .pro-card-danger { border-left: 4px solid #dc2626; }
        .chip {
            display: inline-block; border-radius: 999px; padding: .12rem .55rem; margin: .08rem .12rem .08rem 0;
            font-size: .75rem; font-weight: 700;
        }
        .chip-green { background:#dcfce7; color:#166534; }
        .chip-red { background:#fee2e2; color:#991b1b; }
        .chip-blue { background:#dbeafe; color:#1e40af; }
        .chip-yellow { background:#fef3c7; color:#92400e; }
        .chip-gray { background:#f1f5f9; color:#475569; }
        @media (max-width: 640px) {
            .block-container { padding: 1rem .55rem 5rem .55rem; }
            h1 { font-size: 1.14rem !important; }
            div[data-testid="stMetricValue"] { font-size: .92rem !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================================
# BANCO DE DADOS
# ============================================================================


def conectar_db() -> sqlite3.Connection:
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _garantir_coluna(cur: sqlite3.Cursor, tabela: str, coluna: str, tipo: str) -> None:
    cur.execute(f"PRAGMA table_info({tabela})")
    if coluna not in {row[1] for row in cur.fetchall()}:
        cur.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")


def init_db() -> None:
    conn = conectar_db()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS previsoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT UNIQUE,
            esporte TEXT,
            liga_id TEXT,
            liga_nome TEXT,
            data_jogo TEXT,
            home TEXT,
            away TEXT,
            forca_home REAL,
            forca_away REAL,
            contexto TEXT,
            mercado_base TEXT,
            codigo_base TEXT,
            prob_base REAL,
            mercado_aprendido TEXT,
            codigo_aprendido TEXT,
            prob_aprendido REAL,
            ajuste_aplicado REAL,
            placar_previsto TEXT,
            home_score INTEGER,
            away_score INTEGER,
            acertou_base INTEGER,
            acertou_aprendido INTEGER,
            finalizado INTEGER DEFAULT 0,
            criado_em TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS mercado_historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT,
            liga_id TEXT,
            liga_nome TEXT,
            data_jogo TEXT,
            home TEXT,
            away TEXT,
            contexto TEXT,
            faixa_prob TEXT,
            mercado TEXT,
            codigo TEXT,
            prob_base REAL,
            prob_aprendida REAL,
            ajuste_aplicado REAL,
            acertou INTEGER,
            finalizado INTEGER DEFAULT 0,
            criado_em TEXT,
            UNIQUE(game_id, codigo)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS placar_historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT UNIQUE,
            liga_id TEXT,
            liga_nome TEXT,
            data_jogo TEXT,
            home TEXT,
            away TEXT,
            contexto TEXT,
            placar_top1 TEXT,
            placar_top3 TEXT,
            placar_top5 TEXT,
            prob_top1 REAL,
            real_placar TEXT,
            home_score INTEGER,
            away_score INTEGER,
            acertou_exato INTEGER,
            acertou_top3 INTEGER,
            acertou_top5 INTEGER,
            acertou_vencedor INTEGER,
            acertou_total_gols INTEGER,
            erro_gols INTEGER,
            finalizado INTEGER DEFAULT 0,
            criado_em TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ajustes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chave TEXT UNIQUE,
            fator REAL DEFAULT 0,
            jogos INTEGER DEFAULT 0,
            acertos INTEGER DEFAULT 0,
            taxa REAL DEFAULT 0,
            confianca REAL DEFAULT 0,
            atualizado_em TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback_rapido (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT,
            codigo TEXT,
            acertou INTEGER,
            registrado_em TEXT,
            UNIQUE(game_id, codigo)
        )
        """
    )

    for tabela, coluna, tipo in [
        ("previsoes", "esporte", "TEXT"),
        ("previsoes", "forca_home", "REAL"),
        ("previsoes", "forca_away", "REAL"),
        ("previsoes", "contexto", "TEXT"),
        ("ajustes", "confianca", "REAL DEFAULT 0"),
    ]:
        _garantir_coluna(cur, tabela, coluna, tipo)

    conn.commit()
    conn.close()


def ler_tabela(sql: str, params: tuple = ()) -> pd.DataFrame:
    conn = conectar_db()
    try:
        return pd.read_sql_query(sql, conn, params=params)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


def executar(sql: str, params: tuple = ()) -> None:
    conn = conectar_db()
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


# ============================================================================
# UTILIDADES
# ============================================================================


def nome_limpo(nome: Any) -> str:
    return " ".join(str(nome or "").strip().split())


def normalizar(nome: str) -> str:
    nome = nome_limpo(nome).lower()
    nome = unicodedata.normalize("NFD", nome)
    nome = "".join(c for c in nome if unicodedata.category(c) != "Mn")
    nome = nome.replace("'", "").replace(".", "").replace(",", "")
    nome = nome.replace("fc", "").replace("sc", "")
    nome = " ".join(nome.split())
    return ALIASES.get(nome, nome)


def clamp(valor: float, minimo: float, maximo: float) -> float:
    return max(minimo, min(maximo, valor))


def pct(valor: float) -> str:
    return f"{valor * 100:.1f}%"


def faixa_prob(prob: float) -> str:
    if prob >= 0.75:
        return "Muito alta"
    if prob >= 0.62:
        return "Alta"
    if prob >= 0.52:
        return "Media"
    return "Baixa"


def contexto_jogo(home: str, away: str, liga_id: str) -> str:
    h = normalizar(home)
    a = normalizar(away)
    partes = [liga_id]
    if tuple(sorted([h, a])) in CLASSICOS:
        partes.append("classico")
    if h in FORCA_BASE and a in FORCA_BASE:
        diff = abs(FORCA_BASE[h] - FORCA_BASE[a])
        if diff <= 4:
            partes.append("equilibrado")
        elif diff >= 12:
            partes.append("favorito_forte")
    return "|".join(partes)


def game_id_manual(prefixo: str, liga_id: str, home: str, away: str, data_jogo: date) -> str:
    raw = f"{prefixo}:{liga_id}:{data_jogo.isoformat()}:{normalizar(home)}:{normalizar(away)}"
    return raw.replace(" ", "_")


def sugestoes_times_liga(liga_id: str, tabela: pd.DataFrame) -> list[str]:
    if not tabela.empty and "time" in tabela.columns:
        times = [nome_limpo(time) for time in tabela["time"].dropna().tolist()]
        times = [time for time in times if time]
        if len(times) >= 2:
            return sorted(set(times))

    fallback = TIMES_FALLBACK_LIGA.get(liga_id, [])
    if len(fallback) >= 2:
        return fallback

    return ["Flamengo", "Palmeiras"]


# ============================================================================
# API ESPN E FORCAS
# ============================================================================


@st.cache_data(ttl=60 * 30, show_spinner=False)
def api_get_json(url: str, params: Optional[dict[str, Any]] = None) -> Optional[dict[str, Any]]:
    if not REQUESTS_OK or requests is None:
        return None

    params = params or {}
    for tentativa in range(RETRIES):
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=12)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in {404, 422}:
                return None
        except Exception:
            pass
        time.sleep(0.6 * (2**tentativa))
    return None


@st.cache_data(ttl=60 * 60, show_spinner=False)
def buscar_tabela_espn(liga_id: str) -> pd.DataFrame:
    url = f"{ESPN_BASE}/{liga_id}/standings"
    data = api_get_json(url)
    rows: list[dict[str, Any]] = []
    if not data:
        return pd.DataFrame(rows)

    children = data.get("children") or []
    standings = data.get("standings") or []
    groups = children if children else [{"standings": standings}]

    for group in groups:
        raw_standings = group.get("standings") if isinstance(group, dict) else {}
        if isinstance(raw_standings, dict):
            entries = raw_standings.get("entries") or []
        elif isinstance(raw_standings, list):
            entries = raw_standings
        else:
            entries = []
        if not entries and isinstance(group, dict):
            entries = group.get("entries") or []
        for pos, item in enumerate(entries, start=1):
            team = item.get("team") or {}
            stats = {s.get("name"): s.get("value") for s in item.get("stats", []) if isinstance(s, dict)}
            nome = team.get("displayName") or team.get("name") or ""
            if nome:
                rows.append(
                    {
                        "pos": pos,
                        "time": nome,
                        "normalizado": normalizar(nome),
                        "pontos": float(stats.get("points") or stats.get("PTS") or 0),
                        "jogos": float(stats.get("gamesPlayed") or stats.get("GP") or 0),
                        "vitorias": float(stats.get("wins") or 0),
                        "empates": float(stats.get("ties") or stats.get("draws") or 0),
                        "derrotas": float(stats.get("losses") or 0),
                    }
                )
    return pd.DataFrame(rows)


def forca_dinamica_futebol(nome: str, liga_id: str) -> tuple[float, str]:
    chave = normalizar(nome)
    tabela = buscar_tabela_espn(liga_id)

    if not tabela.empty and chave in set(tabela["normalizado"]):
        row = tabela[tabela["normalizado"] == chave].iloc[0]
        total = max(len(tabela), 1)
        rank_score = 92 - ((float(row["pos"]) - 1) / max(total - 1, 1)) * 28
        ppg = float(row["pontos"]) / max(float(row["jogos"]), 1)
        pontos_score = 58 + clamp(ppg / 3, 0, 1) * 34
        forca = (rank_score * 0.58) + (pontos_score * 0.42)
        return round(clamp(forca, 50, 96), 1), "ESPN/tabela"

    if chave in FORCA_BASE:
        return float(FORCA_BASE[chave]), "fallback estatico"

    return 68.0, "padrao neutro"


def forca_generica(nome: str, base: dict[str, int], padrao: float = 72.0) -> tuple[float, str]:
    chave = normalizar(nome)
    if chave in base:
        return float(base[chave]), "base interna"
    return padrao, "padrao neutro"


# ============================================================================
# MODELOS
# ============================================================================


def poisson(k: int, lamb: float) -> float:
    lamb = max(lamb, 0.05)
    return math.exp(-lamb) * (lamb**k) / math.factorial(k)


def dixon_coles_factor(home_goals: int, away_goals: int, lambda_h: float, lambda_a: float, rho: float) -> float:
    if home_goals == 0 and away_goals == 0:
        return 1 - (lambda_h * lambda_a * rho)
    if home_goals == 0 and away_goals == 1:
        return 1 + (lambda_h * rho)
    if home_goals == 1 and away_goals == 0:
        return 1 + (lambda_a * rho)
    if home_goals == 1 and away_goals == 1:
        return 1 - rho
    return 1.0


def matriz_placares(forca_home: float, forca_away: float, home_adv: float) -> pd.DataFrame:
    diff = (forca_home + home_adv * 10) - forca_away
    lambda_h = clamp(1.28 + diff / 34, 0.25, 3.6)
    lambda_a = clamp(1.08 - diff / 40, 0.20, 3.2)

    linhas: list[dict[str, Any]] = []
    total_prob = 0.0
    for h in range(MAX_GOLS + 1):
        for a in range(MAX_GOLS + 1):
            prob = poisson(h, lambda_h) * poisson(a, lambda_a)
            prob *= dixon_coles_factor(h, a, lambda_h, lambda_a, DIXON_COLES_RHO)
            prob = max(prob, 0)
            total_prob += prob
            linhas.append({"home_gols": h, "away_gols": a, "prob": prob})

    df = pd.DataFrame(linhas)
    if total_prob > 0:
        df["prob"] = df["prob"] / total_prob
    return df.sort_values("prob", ascending=False).reset_index(drop=True)


def probabilidades_futebol(df: pd.DataFrame) -> dict[str, float]:
    home_win = float(df[df["home_gols"] > df["away_gols"]]["prob"].sum())
    draw = float(df[df["home_gols"] == df["away_gols"]]["prob"].sum())
    away_win = float(df[df["home_gols"] < df["away_gols"]]["prob"].sum())
    over_15 = float(df[(df["home_gols"] + df["away_gols"]) > 1.5]["prob"].sum())
    over_25 = float(df[(df["home_gols"] + df["away_gols"]) > 2.5]["prob"].sum())
    under_35 = float(df[(df["home_gols"] + df["away_gols"]) < 3.5]["prob"].sum())
    btts = float(df[(df["home_gols"] > 0) & (df["away_gols"] > 0)]["prob"].sum())
    dupla_1x = home_win + draw
    dupla_x2 = draw + away_win
    dupla_12 = home_win + away_win
    return {
        "Casa vence": home_win,
        "Empate": draw,
        "Fora vence": away_win,
        "Dupla 1X": dupla_1x,
        "Dupla X2": dupla_x2,
        "Dupla 12": dupla_12,
        "Over 1.5": over_15,
        "Over 2.5": over_25,
        "Under 3.5": under_35,
        "Ambos marcam": btts,
    }


def melhor_mercado(probs: dict[str, float]) -> tuple[str, str, float]:
    ordenados = sorted(probs.items(), key=lambda item: item[1], reverse=True)
    mercado, prob = ordenados[0]
    codigo = mercado.lower().replace(" ", "_").replace(".", "")
    return mercado, codigo, prob


def ajuste_aprendido(codigo: str, contexto: str) -> float:
    chaves = [f"{contexto}:{codigo}", f"global:{codigo}"]
    df = ler_tabela(
        "SELECT chave, fator, confianca FROM ajustes WHERE chave IN (?, ?)",
        (chaves[0], chaves[1]),
    )
    if df.empty:
        return 0.0
    df["peso"] = df["confianca"].fillna(0).clip(0, 1)
    if df["peso"].sum() <= 0:
        return float(df["fator"].mean())
    return float((df["fator"] * df["peso"]).sum() / df["peso"].sum())


def aplicar_ajuste(prob: float, codigo: str, contexto: str) -> tuple[float, float]:
    ajuste = ajuste_aprendido(codigo, contexto)
    return clamp(prob + ajuste, 0.03, 0.97), ajuste


def prever_ml(forca_home: float, forca_away: float, home_adv: float) -> Optional[dict[str, float]]:
    if not SKLEARN_OK:
        return None
    df = ler_tabela(
        """
        SELECT forca_home, forca_away, home_score, away_score
        FROM previsoes
        WHERE finalizado = 1
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
          AND forca_home IS NOT NULL
          AND forca_away IS NOT NULL
        """
    )
    if len(df) < MIN_JOGOS_TREINO:
        return None

    y = []
    for _, row in df.iterrows():
        if row["home_score"] > row["away_score"]:
            y.append(0)
        elif row["home_score"] == row["away_score"]:
            y.append(1)
        else:
            y.append(2)

    if len(set(y)) < 2:
        return None

    x = pd.DataFrame(
        {
            "forca_home": df["forca_home"].astype(float),
            "forca_away": df["forca_away"].astype(float),
            "diff": df["forca_home"].astype(float) - df["forca_away"].astype(float),
            "home_adv": home_adv,
        }
    )
    scaler = StandardScaler()
    xs = scaler.fit_transform(x)
    model = LogisticRegression(max_iter=500)
    model.fit(xs, y)
    atual = scaler.transform([[forca_home, forca_away, forca_home - forca_away, home_adv]])
    probs = model.predict_proba(atual)[0]
    classes = list(model.classes_)
    mapa = {0: "Casa vence", 1: "Empate", 2: "Fora vence"}
    return {mapa[c]: float(probs[i]) for i, c in enumerate(classes)}


def prob_tenis(forca_a: float, forca_b: float, superficie: str) -> dict[str, float]:
    bonus = {"Dura": 0.0, "Saibro": 0.8, "Grama": 0.5, "Indoor": 0.3}.get(superficie, 0.0)
    diff = (forca_a + bonus) - forca_b
    p1 = 1 / (1 + math.exp(-diff / 8))
    p1 = clamp(p1, 0.08, 0.92)
    return {"Jogador 1 vence": p1, "Jogador 2 vence": 1 - p1}


def prob_basquete(forca_home: float, forca_away: float) -> dict[str, float]:
    diff = (forca_home + 3.0) - forca_away
    p_home = 1 / (1 + math.exp(-diff / 7.5))
    total = 214 + (forca_home + forca_away - 150) * 0.9
    spread = -round(diff / 2.2, 1)
    return {
        "Casa vence": clamp(p_home, 0.05, 0.95),
        "Fora vence": clamp(1 - p_home, 0.05, 0.95),
        "Linha total projetada": float(round(total, 1)),
        "Handicap casa projetado": float(spread),
    }


# ============================================================================
# PERSISTENCIA DE PREVISAO E APRENDIZADO
# ============================================================================


def salvar_previsao(
    esporte: str,
    game_id: str,
    liga_id: str,
    liga_nome: str,
    data_jogo: date,
    home: str,
    away: str,
    forca_home: float,
    forca_away: float,
    contexto: str,
    mercado: str,
    codigo: str,
    prob_base: float,
    prob_aprendida: float,
    ajuste: float,
    placar: str,
) -> None:
    executar(
        """
        INSERT OR REPLACE INTO previsoes (
            game_id, esporte, liga_id, liga_nome, data_jogo, home, away,
            forca_home, forca_away, contexto, mercado_base, codigo_base,
            prob_base, mercado_aprendido, codigo_aprendido, prob_aprendido,
            ajuste_aplicado, placar_previsto, finalizado, criado_em
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """,
        (
            game_id,
            esporte,
            liga_id,
            liga_nome,
            data_jogo.isoformat(),
            home,
            away,
            forca_home,
            forca_away,
            contexto,
            mercado,
            codigo,
            prob_base,
            mercado,
            codigo,
            prob_aprendida,
            ajuste,
            placar,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )


def registrar_feedback(game_id: str, codigo: str, acertou: int) -> None:
    executar(
        """
        INSERT OR REPLACE INTO feedback_rapido (game_id, codigo, acertou, registrado_em)
        VALUES (?, ?, ?, ?)
        """,
        (game_id, codigo, int(acertou), datetime.now().isoformat(timespec="seconds")),
    )
    recalcular_ajustes()


def recalcular_ajustes() -> None:
    df = ler_tabela(
        """
        SELECT p.contexto, p.codigo_base AS codigo, f.acertou
        FROM feedback_rapido f
        JOIN previsoes p ON p.game_id = f.game_id AND p.codigo_base = f.codigo
        WHERE f.acertou IS NOT NULL
        """
    )
    if df.empty:
        return

    conn = conectar_db()
    cur = conn.cursor()
    for (contexto, codigo), grupo in df.groupby(["contexto", "codigo"]):
        jogos = int(len(grupo))
        acertos = int(grupo["acertou"].sum())
        taxa = acertos / max(jogos, 1)
        fator = clamp((taxa - 0.55) * 0.18, -0.08, 0.08)
        confianca = clamp(jogos / 50, 0, 1)
        chave = f"{contexto}:{codigo}"
        cur.execute(
            """
            INSERT OR REPLACE INTO ajustes (chave, fator, jogos, acertos, taxa, confianca, atualizado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (chave, fator, jogos, acertos, taxa, confianca, datetime.now().isoformat(timespec="seconds")),
        )

    for codigo, grupo in df.groupby("codigo"):
        jogos = int(len(grupo))
        acertos = int(grupo["acertou"].sum())
        taxa = acertos / max(jogos, 1)
        fator = clamp((taxa - 0.55) * 0.15, -0.06, 0.06)
        confianca = clamp(jogos / 80, 0, 1)
        cur.execute(
            """
            INSERT OR REPLACE INTO ajustes (chave, fator, jogos, acertos, taxa, confianca, atualizado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"global:{codigo}",
                fator,
                jogos,
                acertos,
                taxa,
                confianca,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
    conn.commit()
    conn.close()


# ============================================================================
# COMPONENTES VISUAIS
# ============================================================================


def card(titulo: str, corpo: str, tipo: str = "info") -> None:
    st.markdown(
        f"""
        <div class="pro-card pro-card-{tipo}">
            <strong>{titulo}</strong><br>{corpo}
        </div>
        """,
        unsafe_allow_html=True,
    )


def chips_prob(probs: dict[str, float]) -> None:
    html = []
    for nome, prob in sorted(probs.items(), key=lambda item: item[1], reverse=True):
        if not isinstance(prob, (float, int)) or prob > 1:
            continue
        cls = "chip-green" if prob >= 0.62 else "chip-yellow" if prob >= 0.52 else "chip-gray"
        html.append(f'<span class="chip {cls}">{nome}: {pct(float(prob))}</span>')
    st.markdown("".join(html), unsafe_allow_html=True)


def tabela_placares(df: pd.DataFrame, home: str, away: str, n: int = 8) -> pd.DataFrame:
    top = df.head(n).copy()
    top["placar"] = top["home_gols"].astype(str) + " x " + top["away_gols"].astype(str)
    top["probabilidade"] = top["prob"].map(lambda x: pct(float(x)))
    top["jogo"] = f"{home} x {away}"
    return top[["jogo", "placar", "probabilidade"]]


# ============================================================================
# TELAS
# ============================================================================


def tela_futebol() -> None:
    st.header("Futebol")
    liga_nome = st.selectbox("Liga", list(LIGAS.keys()), key="futebol_liga")
    liga_id = LIGAS[liga_nome]

    tabela = buscar_tabela_espn(liga_id)
    sugestoes = sugestoes_times_liga(liga_id, tabela)
    away_default = 1 if len(sugestoes) > 1 else 0

    c1, c2, c3 = st.columns([1, 1, 0.7])
    with c1:
        home = st.selectbox("Mandante", sugestoes, index=0, key=f"home_{liga_id}")
    with c2:
        away = st.selectbox("Visitante", sugestoes, index=away_default, key=f"away_{liga_id}")
    with c3:
        data_jogo = st.date_input("Data", value=date.today())

    if normalizar(home) == normalizar(away):
        st.error("Escolha dois times diferentes.")
        return

    forca_home, fonte_h = forca_dinamica_futebol(home, liga_id)
    forca_away, fonte_a = forca_dinamica_futebol(away, liga_id)

    adv = HOME_ADV_LIGA.get(liga_id, DEFAULT_HOME_ADV)
    contexto = contexto_jogo(home, away, liga_id)
    matriz = matriz_placares(forca_home, forca_away, adv)
    probs = probabilidades_futebol(matriz)
    mercado, codigo, prob_base = melhor_mercado(probs)
    prob_apr, ajuste = aplicar_ajuste(prob_base, codigo, contexto)
    placar_top = matriz.iloc[0]
    placar = f"{int(placar_top.home_gols)} x {int(placar_top.away_gols)}"
    game_id = game_id_manual("futebol", liga_id, home, away, data_jogo)

    st.subheader(f"{nome_limpo(home)} x {nome_limpo(away)}")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Forca mandante", f"{forca_home:.1f}", fonte_h)
    m2.metric("Forca visitante", f"{forca_away:.1f}", fonte_a)
    m3.metric("Melhor mercado", mercado, faixa_prob(prob_apr))
    m4.metric("Probabilidade", pct(prob_apr), f"Ajuste {ajuste:+.1%}")

    chips_prob(probs)

    col_a, col_b = st.columns([1.1, 0.9])
    with col_a:
        card(
            "Leitura principal",
            f"Mercado recomendado: <b>{mercado}</b> com probabilidade ajustada de <b>{pct(prob_apr)}</b>. "
            f"Contexto: <code>{contexto}</code>.",
            "success" if prob_apr >= 0.62 else "warn",
        )
        st.dataframe(tabela_placares(matriz, home, away), hide_index=True, use_container_width=True)
    with col_b:
        ml = prever_ml(forca_home, forca_away, adv)
        if ml:
            st.write("Modelo aprendido")
            chips_prob(ml)
        else:
            card(
                "Modelo aprendido",
                "Ainda sem jogos finalizados suficientes ou sem scikit-learn instalado. O app segue usando Poisson + Dixon-Coles.",
                "info",
            )

    if st.button("Salvar previsao", type="primary"):
        salvar_previsao(
            "futebol",
            game_id,
            liga_id,
            liga_nome,
            data_jogo,
            home,
            away,
            forca_home,
            forca_away,
            contexto,
            mercado,
            codigo,
            prob_base,
            prob_apr,
            ajuste,
            placar,
        )
        st.success("Previsao salva no historico.")

    with st.expander("Feedback rapido para aprendizado"):
        st.caption("Use depois do jogo para o app aprender com o resultado do mercado recomendado.")
        fb_col1, fb_col2 = st.columns(2)
        if fb_col1.button("Acertou", use_container_width=True):
            registrar_feedback(game_id, codigo, 1)
            st.success("Feedback registrado.")
        if fb_col2.button("Errou", use_container_width=True):
            registrar_feedback(game_id, codigo, 0)
            st.warning("Feedback registrado.")

    if not tabela.empty:
        with st.expander("Tabela ESPN usada na forca dinamica"):
            st.dataframe(tabela[["pos", "time", "pontos", "jogos", "vitorias", "empates", "derrotas"]], hide_index=True)


def tela_tenis() -> None:
    st.header("Tenis")
    circuito = st.selectbox("Circuito", list(TENIS_LIGAS.keys()))
    c1, c2, c3 = st.columns([1, 1, 0.8])
    with c1:
        jogador1 = st.text_input("Jogador 1", "jannik sinner")
    with c2:
        jogador2 = st.text_input("Jogador 2", "carlos alcaraz")
    with c3:
        superficie = st.selectbox("Superficie", ["Dura", "Saibro", "Grama", "Indoor"])

    if normalizar(jogador1) == normalizar(jogador2):
        st.error("Escolha jogadores diferentes.")
        return

    f1, fonte1 = forca_generica(jogador1, FORCA_TENIS, 80)
    f2, fonte2 = forca_generica(jogador2, FORCA_TENIS, 80)
    probs = prob_tenis(f1, f2, superficie)
    mercado, codigo, prob = melhor_mercado(probs)
    contexto = f"{TENIS_LIGAS[circuito]}|{superficie.lower()}"
    prob_apr, ajuste = aplicar_ajuste(prob, codigo, contexto)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Forca jogador 1", f"{f1:.1f}", fonte1)
    m2.metric("Forca jogador 2", f"{f2:.1f}", fonte2)
    m3.metric("Mercado", mercado)
    m4.metric("Probabilidade", pct(prob_apr), f"Ajuste {ajuste:+.1%}")
    chips_prob(probs)
    card("Leitura principal", f"Favorito do modelo: <b>{mercado}</b> em quadra de <b>{superficie}</b>.", "success")


def tela_basquete() -> None:
    st.header("Basquete")
    liga_nome = st.selectbox("Liga", list(LIGAS_BASQUETE.keys()))
    c1, c2 = st.columns(2)
    with c1:
        home = st.text_input("Mandante", "boston celtics")
    with c2:
        away = st.text_input("Visitante", "denver nuggets")

    if normalizar(home) == normalizar(away):
        st.error("Escolha dois times diferentes.")
        return

    f_home, fonte_h = forca_generica(home, FORCA_BASQUETE, 74)
    f_away, fonte_a = forca_generica(away, FORCA_BASQUETE, 74)
    probs = prob_basquete(f_home, f_away)
    win_probs = {k: v for k, v in probs.items() if k.endswith("vence")}
    mercado, codigo, prob = melhor_mercado(win_probs)
    contexto = f"{LIGAS_BASQUETE[liga_nome]}|regular"
    prob_apr, ajuste = aplicar_ajuste(prob, codigo, contexto)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Forca mandante", f"{f_home:.1f}", fonte_h)
    m2.metric("Forca visitante", f"{f_away:.1f}", fonte_a)
    m3.metric("Linha total", f"{probs['Linha total projetada']:.1f}")
    m4.metric("Handicap casa", f"{probs['Handicap casa projetado']:+.1f}")
    chips_prob(win_probs)
    card("Leitura principal", f"Mercado recomendado: <b>{mercado}</b> com probabilidade ajustada de <b>{pct(prob_apr)}</b>.", "success")


def tela_historico() -> None:
    st.header("Historico")
    df = ler_tabela("SELECT * FROM previsoes ORDER BY id DESC LIMIT 300")
    if df.empty:
        st.info("Ainda nao ha previsoes salvas.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Previsoes", len(df))
    c2.metric("Finalizadas", int(df["finalizado"].fillna(0).sum()) if "finalizado" in df else 0)
    c3.metric("Prob. media", pct(float(df["prob_aprendido"].dropna().mean())) if df["prob_aprendido"].notna().any() else "-")

    cols = [
        "criado_em",
        "esporte",
        "liga_nome",
        "data_jogo",
        "home",
        "away",
        "mercado_aprendido",
        "prob_aprendido",
        "placar_previsto",
    ]
    visiveis = [c for c in cols if c in df.columns]
    out = df[visiveis].copy()
    if "prob_aprendido" in out:
        out["prob_aprendido"] = out["prob_aprendido"].map(lambda x: pct(float(x)) if pd.notna(x) else "")
    st.dataframe(out, hide_index=True, use_container_width=True)

    with st.expander("Ajustes aprendidos"):
        ajustes = ler_tabela("SELECT * FROM ajustes ORDER BY atualizado_em DESC")
        if ajustes.empty:
            st.caption("Sem ajustes aprendidos ainda.")
        else:
            st.dataframe(ajustes, hide_index=True, use_container_width=True)


def tela_backtest() -> None:
    st.header("Backtesting")
    df = ler_tabela(
        """
        SELECT p.*, f.acertou
        FROM previsoes p
        LEFT JOIN feedback_rapido f ON f.game_id = p.game_id AND f.codigo = p.codigo_base
        ORDER BY p.id DESC
        """
    )
    if df.empty or df["acertou"].dropna().empty:
        st.info("Registre feedback em algumas previsoes para gerar o backtest.")
        return

    bt = df.dropna(subset=["acertou"]).copy()
    bt["acertou"] = bt["acertou"].astype(int)
    acuracia = float(bt["acertou"].mean())
    media_prob = float(bt["prob_aprendido"].dropna().mean()) if bt["prob_aprendido"].notna().any() else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Amostra", len(bt))
    c2.metric("Acuracia", pct(acuracia))
    c3.metric("Probabilidade media", pct(media_prob))

    bt = bt.sort_values("id")
    bt["acuracia_acumulada"] = bt["acertou"].expanding().mean()
    st.line_chart(bt.set_index("id")["acuracia_acumulada"])

    resumo = (
        bt.groupby("codigo_base")
        .agg(jogos=("acertou", "count"), acertos=("acertou", "sum"), taxa=("acertou", "mean"))
        .reset_index()
        .sort_values(["taxa", "jogos"], ascending=False)
    )
    resumo["taxa"] = resumo["taxa"].map(lambda x: pct(float(x)))
    st.dataframe(resumo, hide_index=True, use_container_width=True)


def tela_diagnostico() -> None:
    st.header("Diagnostico")
    checks = []
    checks.append(("Banco SQLite", os.path.exists(DB_PATH), DB_PATH))
    checks.append(("requests", REQUESTS_OK, "Opcional: usado para consultar ESPN"))
    checks.append(("scikit-learn", SKLEARN_OK, "Opcional: usado apenas no modelo aprendido"))
    checks.append(("Cache Streamlit", True, "Ativo em chamadas externas"))
    checks.append(("Pasta data", os.path.isdir("data"), os.path.abspath("data")))

    for nome, ok, detalhe in checks:
        tipo = "success" if ok else "warn"
        status = "OK" if ok else "Atencao"
        card(nome, f"{status} - {detalhe}", tipo)

    st.write("Ultimas previsoes")
    df = ler_tabela("SELECT id, criado_em, esporte, home, away, mercado_aprendido, prob_aprendido FROM previsoes ORDER BY id DESC LIMIT 20")
    if df.empty:
        st.caption("Nenhuma previsao registrada ainda.")
    else:
        st.dataframe(df, hide_index=True, use_container_width=True)


# ============================================================================
# APP
# ============================================================================


def main() -> None:
    aplicar_estilo()
    init_db()

    st.sidebar.title("Pro 17")
    st.sidebar.caption("Analisador esportivo com fallback seguro")
    pagina = st.sidebar.radio(
        "Navegacao",
        ["Futebol", "Tenis", "Basquete", "Historico", "Backtesting", "Diagnostico"],
    )

    st.title("Analisador Esportivo Pro 17")
    st.caption("Poisson, Dixon-Coles, forca dinamica, cache, aprendizado opcional e historico local.")

    if pagina == "Futebol":
        tela_futebol()
    elif pagina == "Tenis":
        tela_tenis()
    elif pagina == "Basquete":
        tela_basquete()
    elif pagina == "Historico":
        tela_historico()
    elif pagina == "Backtesting":
        tela_backtest()
    else:
        tela_diagnostico()


if __name__ == "__main__":
    main()
