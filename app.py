"""
Analisador Esportivo Pro 17
============================
Melhorias v17:
 - Força dinâmica via tabela real da ESPN (com fallback estático)
 - Correção Dixon-Coles para placares 0-0 / 1-0 / 0-1 / 1-1
 - Home advantage por liga (calibrado)
 - Sistema de aprendizado via regressão logística (scikit-learn opcional)
 - Backoff exponencial + rate-limit no retry
 - Cache @st.cache_data em todas as chamadas de API
 - Layout redesenhado: sidebar de navegação, abas, métricas visuais
 - Validação de inputs (times iguais, datas inválidas, etc.)
 - Backtesting automático com curva de acurácia
 - Normalização de força de tênis via ranking ATP/WTA ao vivo
"""

# ─── stdlib ───────────────────────────────────────────────────────────────────
import math
import os
import re
import sqlite3
import time
import unicodedata
from datetime import datetime, timedelta
from typing import Optional

# ─── third-party ──────────────────────────────────────────────────────────────
import pandas as pd
import requests
import streamlit as st

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    import numpy as np
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO GLOBAL
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Analisador Esportivo Pro 17",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

ESPN_BASE        = "https://site.api.espn.com/apis/site/v2/sports/soccer"
ESPN_SPORTS_BASE = "https://site.api.espn.com/apis/site/v2/sports"
HEADERS          = {"User-Agent": "AnalisadorEsportivoPro/17.0"}
DB_PATH          = "data/modelo_v17.db"

MAX_GOLS             = 10
RETRIES              = 3
DEFAULT_HOME_ADV     = 0.25
MIN_JOGOS_TREINO     = 20
DIXON_COLES_RHO      = -0.13   # correlação empírica Dixon-Coles

# ─── Vantagem em casa calibrada por liga ──────────────────────────────────────
HOME_ADV_LIGA: dict[str, float] = {
    "bra.1":                     0.28,
    "bra.2":                     0.27,
    "bra.copa_do_brazil":        0.22,
    "eng.1":                     0.22,
    "esp.1":                     0.24,
    "ita.1":                     0.25,
    "ger.1":                     0.26,
    "fra.1":                     0.24,
    "uefa.champions":            0.20,
    "uefa.europa":               0.18,
    "conmebol.libertadores":     0.30,
    "conmebol.sudamericana":     0.28,
}

# ─── Ligas disponíveis ────────────────────────────────────────────────────────
LIGAS: dict[str, str] = {
    "Brasileirão Série A":  "bra.1",
    "Brasileirão Série B":  "bra.2",
    "Copa do Brasil":       "bra.copa_do_brazil",
    "Premier League":       "eng.1",
    "La Liga":              "esp.1",
    "Serie A Itália":       "ita.1",
    "Bundesliga":           "ger.1",
    "Ligue 1":              "fra.1",
    "Champions League":     "uefa.champions",
    "Europa League":        "uefa.europa",
    "Libertadores":         "conmebol.libertadores",
    "Sul-Americana":        "conmebol.sudamericana",
}

TENIS_LIGAS:    dict[str, str] = {"ATP": "atp", "WTA": "wta"}
LIGAS_BASQUETE: dict[str, str] = {"NBA": "nba"}

# ─── Força base ESTÁTICA (fallback quando API não responde) ──────────────────
FORCA_BASE: dict[str, int] = {
    # Brasil
    "flamengo": 86, "palmeiras": 84, "botafogo": 79, "atletico-mg": 76,
    "sao paulo": 78, "fluminense": 77, "gremio": 74, "internacional": 75,
    "corinthians": 76, "cruzeiro": 73, "bahia": 74, "fortaleza": 73,
    "vasco": 70, "santos": 72, "ceara": 69, "sport": 68, "vitoria": 69,
    "coritiba": 68, "athletico-pr": 72, "atletico goianiense": 68,
    "goias": 68, "cuiaba": 67, "juventude": 67, "chapecoense": 65,
    "crb": 65, "csa": 64, "paysandu": 64, "remo": 64, "ponte preta": 65,
    "guarani": 64, "novorizontino": 67, "mirassol": 68, "operario pr": 64,
    "vila nova": 66, "amazonas": 64, "america mineiro": 68,
    "bragantino": 72, "red bull bragantino": 72,
    "sao bernardo": 63, "tombense": 62, "volta redonda": 62,
    "santa cruz": 61, "retro": 61,
    # Europa
    "manchester city": 91, "arsenal": 88, "liverpool": 88,
    "chelsea": 82, "tottenham hotspur": 80, "manchester united": 81,
    "real madrid": 90, "barcelona": 87, "atletico madrid": 84,
    "bayern munich": 88, "borussia dortmund": 82, "bayer leverkusen": 84,
    "inter milan": 86, "juventus": 82, "milan": 81,
    "paris saint-germain": 88,
}

FORCA_TENIS: dict[str, int] = {
    "jannik sinner": 94, "carlos alcaraz": 93, "novak djokovic": 92,
    "daniil medvedev": 88, "alexander zverev": 88,
    "iga swiatek": 94, "aryna sabalenka": 93, "coco gauff": 90,
    "elena rybakina": 89, "jessica pegula": 86,
}

FORCA_BASQUETE: dict[str, int] = {
    "boston celtics": 92, "denver nuggets": 90,
    "oklahoma city thunder": 89, "milwaukee bucks": 87,
    "minnesota timberwolves": 86, "dallas mavericks": 85,
    "new york knicks": 84, "cleveland cavaliers": 83,
    "phoenix suns": 82, "la clippers": 82,
    "los angeles lakers": 80, "golden state warriors": 79,
    "miami heat": 78, "philadelphia 76ers": 78,
    "sacramento kings": 76, "indiana pacers": 76,
    "orlando magic": 75, "houston rockets": 74,
    "new orleans pelicans": 74, "atlanta hawks": 72,
    "chicago bulls": 71, "utah jazz": 70, "brooklyn nets": 69,
    "memphis grizzlies": 69, "toronto raptors": 68,
    "san antonio spurs": 68, "portland trail blazers": 66,
    "charlotte hornets": 65, "detroit pistons": 64,
    "washington wizards": 63,
}

ALIASES: dict[str, str] = {
    "man city": "manchester city", "man utd": "manchester united",
    "man united": "manchester united", "tottenham": "tottenham hotspur",
    "spurs": "tottenham hotspur", "psg": "paris saint-germain",
    "paris sg": "paris saint-germain", "inter": "inter milan",
    "internazionale": "inter milan", "atletico mineiro": "atletico-mg",
    "atletico mg": "atletico-mg", "vasco da gama": "vasco",
    "sao paulo fc": "sao paulo", "gremio fbpa": "gremio",
    "athletico paranaense": "athletico-pr", "athletico-pr": "athletico-pr",
    "atletico pr": "athletico-pr",
    "red bull bragantino": "bragantino", "operario": "operario pr",
    "operario-pr": "operario pr", "sao bernardo fc": "sao bernardo",
    "retró": "retro", "retrô": "retro",
    # Basquete
    "celtics": "boston celtics", "nuggets": "denver nuggets",
    "thunder": "oklahoma city thunder", "bucks": "milwaukee bucks",
    "timberwolves": "minnesota timberwolves", "mavs": "dallas mavericks",
    "mavericks": "dallas mavericks", "knicks": "new york knicks",
    "cavs": "cleveland cavaliers", "cavaliers": "cleveland cavaliers",
    "suns": "phoenix suns", "clippers": "la clippers",
    "lakers": "los angeles lakers", "warriors": "golden state warriors",
    "heat": "miami heat", "sixers": "philadelphia 76ers",
    "76ers": "philadelphia 76ers", "kings": "sacramento kings",
    "pacers": "indiana pacers", "magic": "orlando magic",
    "rockets": "houston rockets", "pelicans": "new orleans pelicans",
    "hawks": "atlanta hawks", "bulls": "chicago bulls",
    "jazz": "utah jazz", "nets": "brooklyn nets",
    "grizzlies": "memphis grizzlies", "raptors": "toronto raptors",
    "hornets": "charlotte hornets", "pistons": "detroit pistons",
    "wizards": "washington wizards",
}

CLASSICOS: set[tuple] = {
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


# ══════════════════════════════════════════════════════════════════════════════
# ESTILO / LAYOUT
# ══════════════════════════════════════════════════════════════════════════════

def aplicar_estilo() -> None:
    st.markdown(
        """
        <style>
        /* ── base ───────────────────────────────── */
        html, body, [data-testid="stAppViewContainer"] {
            overflow-y: auto !important;
            background: #f0f2f6;
        }
        .block-container {
            padding: 1.8rem 1.5rem 5rem 1.5rem;
            max-width: 1300px;
        }

        /* ── tipografia ──────────────────────────── */
        h1 { font-size: 1.55rem !important; margin-bottom: .15rem !important;
             font-weight: 700 !important; }
        h2 { font-size: 1.2rem  !important; font-weight: 600 !important; }
        h3 { font-size: 1.05rem !important; font-weight: 600 !important; }

        /* ── sidebar ─────────────────────────────── */
        section[data-testid="stSidebar"] {
            background: #1e293b !important;
        }
        section[data-testid="stSidebar"] * {
            color: #e2e8f0 !important;
        }
        section[data-testid="stSidebar"] .stRadio label {
            font-size: .93rem;
        }

        /* ── métricas ────────────────────────────── */
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: .55rem .7rem;
            box-shadow: 0 1px 3px rgba(0,0,0,.06);
        }
        div[data-testid="stMetricValue"] { font-size: 1.05rem !important; }
        div[data-testid="stMetricDelta"] { font-size: .72rem  !important; }

        /* ── cards ───────────────────────────────── */
        .pro-card {
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: .85rem 1rem;
            background: #ffffff;
            margin: .5rem 0;
            box-shadow: 0 1px 4px rgba(0,0,0,.05);
        }
        .pro-card-danger  { border-left: 4px solid #ef4444; }
        .pro-card-success { border-left: 4px solid #22c55e; }
        .pro-card-warn    { border-left: 4px solid #f59e0b; }
        .pro-card-info    { border-left: 4px solid #3b82f6; }

        /* ── chips / badges ──────────────────────── */
        .chip {
            display: inline-block;
            border-radius: 999px;
            padding: .12rem .55rem;
            margin: .1rem .15rem .1rem 0;
            font-size: .75rem;
            font-weight: 600;
        }
        .chip-green  { background:#dcfce7; color:#15803d; }
        .chip-red    { background:#fee2e2; color:#b91c1c; }
        .chip-blue   { background:#dbeafe; color:#1d4ed8; }
        .chip-yellow { background:#fef9c3; color:#92400e; }
        .chip-gray   { background:#f1f5f9; color:#475569; }

        /* ── tabelas ─────────────────────────────── */
        .dataframe tbody tr:nth-child(even) { background:#f8fafc; }
        .dataframe thead th {
            background:#1e293b !important;
            color:#e2e8f0 !important;
            font-weight: 600;
        }

        /* ── alertas ─────────────────────────────── */
        div[data-testid="stAlert"] {
            border-radius: 8px;
            padding: .55rem .75rem;
        }

        /* ── mobile ──────────────────────────────── */
        @media (max-width: 640px) {
            .block-container { padding: 1.2rem .5rem 5rem .5rem; }
            h1 { font-size: 1.1rem  !important; }
            h2 { font-size: 1rem    !important; }
            div[data-testid="stMetricValue"] { font-size: .88rem !important; }
            .pro-card { padding: .6rem .7rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# BANCO DE DADOS
# ══════════════════════════════════════════════════════════════════════════════

def conectar_db() -> sqlite3.Connection:
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _garantir_coluna(cur: sqlite3.Cursor, tabela: str,
                     coluna: str, tipo: str) -> None:
    cur.execute(f"PRAGMA table_info({tabela})")
    if coluna not in {row[1] for row in cur.fetchall()}:
        cur.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")


def init_db() -> None:
    """Cria / migra todas as tabelas necessárias."""
    conn = conectar_db()
    cur  = conn.cursor()

    ddls = [
        # Previsões de futebol
        """
        CREATE TABLE IF NOT EXISTS previsoes (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id           TEXT UNIQUE,
            liga_id           TEXT,
            liga_nome         TEXT,
            data_jogo         TEXT,
            home              TEXT,
            away              TEXT,
            forca_home        REAL,
            forca_away        REAL,
            contexto          TEXT,
            mercado_base      TEXT,
            codigo_base       TEXT,
            prob_base         REAL,
            mercado_aprendido TEXT,
            codigo_aprendido  TEXT,
            prob_aprendido    REAL,
            ajuste_aplicado   REAL,
            placar_previsto   TEXT,
            home_score        INTEGER,
            away_score        INTEGER,
            acertou_base      INTEGER,
            acertou_aprendido INTEGER,
            finalizado        INTEGER DEFAULT 0,
            criado_em         TEXT
        )""",
        # Histórico de mercados
        """
        CREATE TABLE IF NOT EXISTS mercado_historico (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id        TEXT,
            liga_id        TEXT,
            liga_nome      TEXT,
            data_jogo      TEXT,
            home           TEXT,
            away           TEXT,
            contexto       TEXT,
            faixa_prob     TEXT,
            mercado        TEXT,
            codigo         TEXT,
            prob_base      REAL,
            prob_aprendida REAL,
            ajuste_aplicado REAL,
            acertou        INTEGER,
            finalizado     INTEGER DEFAULT 0,
            criado_em      TEXT,
            UNIQUE(game_id, codigo)
        )""",
        # Histórico de placares
        """
        CREATE TABLE IF NOT EXISTS placar_historico (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id            TEXT UNIQUE,
            liga_id            TEXT,
            liga_nome          TEXT,
            data_jogo          TEXT,
            home               TEXT,
            away               TEXT,
            contexto           TEXT,
            placar_top1        TEXT,
            placar_top3        TEXT,
            placar_top5        TEXT,
            prob_top1          REAL,
            real_placar        TEXT,
            home_score         INTEGER,
            away_score         INTEGER,
            acertou_exato      INTEGER,
            acertou_top3       INTEGER,
            acertou_top5       INTEGER,
            acertou_vencedor   INTEGER,
            acertou_total_gols INTEGER,
            erro_gols          INTEGER,
            finalizado         INTEGER DEFAULT 0,
            criado_em          TEXT
        )""",
        # Confrontos diretos
        """
        CREATE TABLE IF NOT EXISTS confronto_historico (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id        TEXT UNIQUE,
            liga_id        TEXT,
            liga_nome      TEXT,
            data_jogo      TEXT,
            time_a         TEXT,
            time_b         TEXT,
            chave_confronto TEXT,
            home           TEXT,
            away           TEXT,
            home_score     INTEGER,
            away_score     INTEGER,
            real_placar    TEXT,
            total_gols     INTEGER,
            ambos_marcam   INTEGER,
            vencedor       TEXT,
            contexto       TEXT,
            criado_em      TEXT
        )""",
        # Ajustes aprendidos (por contexto/mercado)
        """
        CREATE TABLE IF NOT EXISTS ajustes (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            chave        TEXT UNIQUE,
            fator        REAL    DEFAULT 0,
            jogos        INTEGER DEFAULT 0,
            acertos      INTEGER DEFAULT 0,
            taxa         REAL    DEFAULT 0,
            confianca    REAL    DEFAULT 0,
            atualizado_em TEXT
        )""",
        # Histórico de tênis
        """
        CREATE TABLE IF NOT EXISTS tenis_historico (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id         TEXT UNIQUE,
            circuito        TEXT,
            torneio         TEXT,
            data_jogo       TEXT,
            jogador1        TEXT,
            jogador2        TEXT,
            superficie      TEXT,
            mercado         TEXT,
            codigo          TEXT,
            prob_base       REAL,
            prob_aprendida  REAL,
            ajuste_aplicado REAL,
            placar          TEXT,
            vencedor        TEXT,
            acertou         INTEGER,
            finalizado      INTEGER DEFAULT 0,
            criado_em       TEXT
        )""",
        # Histórico de basquete
        """
        CREATE TABLE IF NOT EXISTS basquete_historico (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id           TEXT UNIQUE,
            liga_id           TEXT,
            liga_nome         TEXT,
            data_jogo         TEXT,
            home              TEXT,
            away              TEXT,
            mercado_base      TEXT,
            codigo_base       TEXT,
            prob_base         REAL,
            mercado_aprendido TEXT,
            codigo_aprendido  TEXT,
            prob_aprendido    REAL,
            ajuste_aplicado   REAL,
            linha_total       REAL,
            handicap_casa     REAL,
            pontos_previstos  TEXT,
            home_score        INTEGER,
            away_score        INTEGER,
            acertou_base      INTEGER,
            acertou_aprendido INTEGER,
            finalizado        INTEGER DEFAULT 0,
            criado_em         TEXT
        )""",
        # Sessões de feedback rápido
        """
        CREATE TABLE IF NOT EXISTS feedback_rapido (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id    TEXT,
            codigo     TEXT,
            acertou    INTEGER,
            registrado_em TEXT,
            UNIQUE(game_id, codigo)
        )""",
    ]

    for ddl in ddls:
        cur.execute(ddl)

    # Migrações não-destrutivas
    migrações = [
        ("previsoes",  "forca_home",   "REAL"),
        ("previsoes",  "forca_away",   "REAL"),
        ("previsoes",  "contexto",     "TEXT"),
        ("ajustes",    "confianca",    "REAL DEFAULT 0"),
        ("tenis_historico", "superficie", "TEXT"),
    ]
    for tabela, coluna, tipo in migrações:
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


# ══════════════════════════════════════════════════════════════════════════════
# UTILIDADES GERAIS
# ══════════════════════════════════════════════════════════════════════════════

def nome_limpo(nome) -> str:
    return " ".join(str(nome or "").strip().split())


def normalizar(nome: str) -> str:
    nome = nome_limpo(nome).lower()
    nome = unicodedata.normal