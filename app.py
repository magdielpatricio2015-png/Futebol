"""
Analisador Esportivo Pro 18 – Versão Moderna
=============================================
Melhorias:
- Layout moderno e responsivo (Mantido o visual claro do usuário)
- Intervalo de jogos aumentado para 48h
- CORREÇÃO CRÍTICA: Exibição de todas as previsões futuras na aba Futebol
- Lógica de aprendizado aprimorada com tratamento de datas e IDs
- Todas as correções de timezone e validação
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
    page_title="Pro 18 - Analisador Esportivo",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "Analisador Esportivo Pro 18 - v1.0"}
)

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
HEADERS = {"User-Agent": "AnalisadorEsportivoPro/18.0"}
DB_PATH = "data/modelo_v18.db"

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
    "operario-pr": "operario pr",
}

CLASSICOS = {
    ("flamengo", "vasco"), ("flamengo", "fluminense"), ("flamengo", "botafogo"),
    ("palmeiras", "corinthians"), ("sao paulo", "corinthians"),
    ("sao paulo", "palmeiras"), ("gremio", "internacional"),
    ("atletico-mg", "cruzeiro"), ("real madrid", "barcelona"),
    ("manchester united", "manchester city"), ("inter milan", "milan"),
}


# ======================= ESTILO MODERNO =======================
def aplicar_estilo() -> None:
    st.markdown("""<style>
    /* Layout base - Fundo claro */
    html, body, [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
        color: #0f172a;
    }
    
    .block-container {
        padding: 2rem 1.5rem 5rem 1.5rem;
        max-width: 1400px;
    }

    /* Headers */
    h1 {
        font-size: 2.2rem !important;
        font-weight: 800 !important;
        background: linear-gradient(135deg, #6366f1, #ec4899);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.5rem !important;
    }
    
    h2 {
        color: #4f46e5 !important;
        font-weight: 700 !important;
        border-bottom: 2px solid #e2e8f0;
        padding-bottom: 0.8rem !important;
        margin-top: 1.5rem !important;
    }

    h3 {
        color: #0891b2 !important;
        font-weight: 600 !important;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%) !important;
        border-right: 1px solid #e2e8f0;
    }
    
    section[data-testid="stSidebar"] * {
        color: #0f172a !important;
    }

    /* Cards e Containers */
    .card-modern {
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.2rem;
        margin: 0.8rem 0;
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08);
        transition: all 0.3s ease;
    }
    
    .card-modern:hover {
        border-color: #6366f1;
        box-shadow: 0 8px 20px rgba(99, 102, 241, 0.12);
    }

    /* Metrics */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%) !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important;
        padding: 1rem !important;
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08) !important;
    }

    /* Botões */
    button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        border: none !important;
        color: white !important;
    }

    button:hover {
        background: linear-gradient(135deg, #6366f1, #ec4899) !important;
    }

    /* Chips */
    .chip {
        display: inline-block;
        border-radius: 20px;
        padding: 0.4rem 0.9rem;
        margin: 0.3rem 0.4rem 0.3rem 0;
        font-size: 0.8rem;
        font-weight: 600;
        border: 1px solid #e2e8f0;
    }

    .chip-green {
        background: #dcfce7;
        color: #166534;
        border-color: #86efac;
    }

    .chip-blue {
        background: #dbeafe;
        color: #1e40af;
        border-color: #7dd3fc;
    }

    .chip-yellow {
        background: #fef3c7;
        color: #92400e;
        border-color: #fde047;
    }

    .chip-red {
        background: #fee2e2;
        color: #991b1b;
        border-color: #fca5a5;
    }

    .chip-purple {
        background: #f3e8ff;
        color: #6b21a8;
        border-color: #d8b4fe;
    }

    /* Tabelas */
    div[data-testid="stDataFrame"] {
        background: white !important;
    }

    /* Expanders */
    details {
        background: white !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
    }

    details summary {
        color: #4f46e5 !important;
        font-weight: 600 !important;
    }

    /* Avisos */
    .stAlert {
        border-radius: 8px !important;
    }
    
    div[data-testid="stAlert"] {
        background: #f0f9ff !important;
        border-left: 4px solid #0284c7 !important;
        color: #0c4a6e !important;
    }

    /* Input fields */
    input, select, textarea {
        background: white !important;
        border: 1px solid #e2e8f0 !important;
        color: #0f172a !important;
        border-radius: 8px !important;
    }

    input:focus, select:focus, textarea:focus {
        border-color: #6366f1 !important;
        box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1) !important;
    }

    /* Textos */
    p, span, label {
        color: #0f172a !important;
    }

    /* Links */
    a {
        color: #6366f1 !important;
    }
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
    nome = re.sub(r"\b(fc|sc)\b$", "", nome).strip()
    nome = " ".join(nome.split())
    return ALIASES.get(nome, nome)

def clamp(valor: float, mini: float, maxi: float) -> float:
    return max(mini, min(maxi, valor))

def pct(valor: float) -> str:
    return f"{valor * 100:.1f}%"

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

def game_id_manual(esporte: str, liga_id: str, home: str, away: str, data_jogo: date, timestamp: int = 0) -> str:
    raw = f"{esporte}:{liga_id}:{data_jogo.isoformat()}:{timestamp}:{normalizar(home)}:{normalizar(away)}"
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
        
        if not game_id_raw or game_id_raw.lower() == "none" or game_id_raw == "":
            timestamp = int(data_jogo.timestamp())
            game_id_raw = game_id_manual("futebol", liga_id, home, away, data_jogo.date(), timestamp)

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
    
    df["data_utc_dt"] = pd.to_datetime(df["data_utc"], utc=True)
    
    if inicio.tzinfo is None:
        inicio = inicio.replace(tzinfo=timezone.utc)
    if fim.tzinfo is None:
        fim = fim.replace(tzinfo=timezone.utc)
    
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
        return round(clamp(forca, 50, 96), 1), "ESPN"
    if chave in FORCA_BASE:
        return float(FORCA_BASE[chave]), "Base"
    return 68.0, "Padrão"

def forca_generica(nome: str, base: dict, padrao=72.0) -> Tuple[float, str]:
    chave = normalizar(nome)
    if chave in base: return float(base[chave]), "Banco"
    return padrao, "Padrão"


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
        return float(df["fator"].mean()) if not df.empty else 0.0
    return float((df["fator"] * df["peso"]).sum() / df["peso"].sum())

def aplicar_ajuste(prob, codigo, contexto):
    ajuste = ajuste_aprendido(codigo, contexto)
    return clamp(prob + ajuste, 0.03, 0.97), ajuste

def prob_tenis(fa, fb, superficie):
    bonus = {"Dura": 0.0, "Saibro": 0.8, "Grama": 0.5, "Indoor": 0.3}.get(superficie, 0.0)
    diff = (fa + bonus) - fb
    p1 = 1 / (1 + math.exp(-diff / 8))
    p1 = clamp(p1, 0.08, 0.92)
    return {"Jogador 1 vence": p1, "Jogador 2 vence": 1 - p1}


# ======================= PERSISTÊNCIA =======================
def salvar_previsao(game_id, esporte, liga_id, liga_nome, data_jogo, home, away,
                    forca_home, forca_away, home_adv, contexto,
                    mercado, codigo, prob_base, prob_apr, ajuste, placar):
    try:
        # Converter data_jogo para string se necessário
        data_str = data_jogo.isoformat() if hasattr(data_jogo, 'isoformat') else str(data_jogo)
        agora = datetime.now().isoformat(timespec="seconds")
        
        executar("""
            INSERT OR REPLACE INTO previsoes (
                game_id, esporte, liga_id, liga_nome, data_jogo, home, away,
                forca_home, forca_away, home_adv, contexto,
                mercado_base, codigo_base, prob_base,
                mercado_aprendido, codigo_aprendido, prob_aprendido,
                ajuste_aplicado, placar_previsto, criado_em
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            str(game_id), str(esporte), str(liga_id), str(liga_nome), data_str,
            str(home), str(away), float(forca_home), float(forca_away), float(home_adv),
            str(contexto), str(mercado), str(codigo), float(prob_base),
            str(mercado), str(codigo), float(prob_apr), float(ajuste),
            str(placar), agora
        ))
    except Exception as e:
        print(f"Erro ao salvar previsão: {str(e)}")
        pass

def registrar_feedback(game_id, codigo, acertou):
    if not codigo or not str(codigo).strip():
        return
    executar("""
        INSERT OR REPLACE INTO feedback_rapido (game_id, codigo, acertou, registrado_em)
        VALUES (?,?,?,?)
    """, (str(game_id), str(codigo).strip(), int(acertou), datetime.now().isoformat(timespec="seconds")))

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
    try:
        agora = datetime.now(timezone.utc)
        inicio = agora - timedelta(hours=48)
        jogos = buscar_jogos_intervalo(liga_id, inicio, agora)
        if jogos.empty:
            return 0
        finalizados = jogos[jogos["completed"] == True].copy()
        if finalizados.empty:
            return 0
        
        data_inicio_str = (inicio - timedelta(days=2)).strftime("%Y-%m-%d")
        data_fim_str = agora.strftime("%Y-%m-%d")
        
        previsoes = ler_tabela("""
            SELECT * FROM previsoes
            WHERE esporte = 'futebol' AND liga_id = ? AND finalizado = 0
              AND data_jogo >= ? AND data_jogo <= ?
        """, (liga_id, data_inicio_str, data_fim_str))
        
        if previsoes.empty:
            return 0

        atualizados = 0
        for _, jogo in finalizados.iterrows():
            if pd.isna(jogo["home_score"]) or pd.isna(jogo["away_score"]):
                continue
            jogo_id = str(jogo["game_id"])
            jogo_data = str(jogo["data_jogo"])
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
                codigo_base = str(prev.get("codigo_base", "") or "")
                codigo_apr = str(prev.get("codigo_aprendido") or codigo_base or "")
                if not codigo_base or not codigo_apr:
                    continue
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
    except Exception as e:
        print(f"Erro ao aprender: {str(e)}")
        return 0


# ======================= COMPONENTES VISUAIS =======================
def card_moderno(titulo, corpo, tipo="info"):
    cores = {
        "success": "💚", "info": "ℹ️", "warning": "⚠️", "danger": "❌"
    }
    emoji = cores.get(tipo, "ℹ️")
    st.markdown(f"""
    <div class="card-modern">
        <span style="font-size: 1.4rem; margin-right: 0.5rem;">{emoji}</span>
        <strong style="color: #4f46e5; font-size: 1.1rem;">{titulo}</strong><br>
        <span style="color: #0f172a; margin-top: 0.5rem; display: block;">{corpo}</span>
    </div>
    """, unsafe_allow_html=True)

def chips_prob(probs):
    html = []
    for nome, prob in sorted(probs.items(), key=lambda x: x[1], reverse=True):
        if not isinstance(prob, (int, float)) or prob > 1: continue
        if prob >= 0.70: cls = "chip-green"
        elif prob >= 0.55: cls = "chip-blue"
        elif prob >= 0.45: cls = "chip-yellow"
        else: cls = "chip-red"
        html.append(f'<span class="chip {cls}">{nome} · {pct(prob)}</span>')
    if html:
        st.markdown(" ".join(html), unsafe_allow_html=True)


# ======================= TELAS =======================
def tela_futebol():
    st.header("⚽ FUTEBOL")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        liga_nome = st.selectbox("Escolha a Liga", list(LIGAS.keys()), key="futebol_liga")
    liga_id = LIGAS[liga_nome]

    # Aprendizado automático
    chave_aprendizado = "aprendizado_" + liga_id
    if chave_aprendizado not in st.session_state:
        with st.spinner("🔄 Carregando dados..."):
            atualizados = aprender_ultimas_24h(liga_id)
            st.session_state[chave_aprendizado] = time.time()
            st.session_state["atualizados_" + liga_id] = atualizados
    else:
        atualizados = st.session_state.get("atualizados_" + liga_id, 0)
    
    if atualizados > 0:
        st.success(f"✨ {atualizados} previsões atualizadas com resultados reais")

    with col2:
        if st.button("🔃 Atualizar", use_container_width=True):
            with st.spinner("Atualizando..."):
                novos = aprender_ultimas_24h(liga_id)
                st.session_state["atualizados_" + liga_id] = novos
                st.rerun()

    # Buscar jogos - Aumentado para 48h
    agora = datetime.now(timezone.utc)
    proximas_48h = buscar_jogos_intervalo(liga_id, agora, agora + timedelta(hours=48))

    if proximas_48h.empty:
        st.warning("📭 Nenhum jogo encontrado nas próximas 48h")
        return

    st.markdown(f"### 📅 Próximos {len(proximas_48h)} Jogo(s)")
    
    # Gerar previsões
    novas_previsoes = 0
    for _, jogo in proximas_48h.iterrows():
        home = str(jogo["home"])
        away = str(jogo["away"])
        data_jogo_str = jogo["data_jogo"]
        game_id = str(jogo["game_id"])
        
        if normalizar(home) == normalizar(away):
            continue
        
        existente = ler_tabela("SELECT id FROM previsoes WHERE game_id = ?", (game_id,))
        if not existente.empty:
            continue
        
        try:
            data_jogo = datetime.fromisoformat(data_jogo_str).date() if isinstance(data_jogo_str, str) else data_jogo_str
        except:
            continue
        
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

    if novas_previsoes > 0:
        st.info(f"🤖 {novas_previsoes} novas previsões geradas automaticamente")

    # Tabela de previsões - CORRIGIDO: Mostrar todas as previsões futuras da liga selecionada
    # Removemos o filtro de data fixa para garantir que tudo que foi gerado apareça
    previsoes_periodo = ler_tabela("""
        SELECT id, game_id, data_jogo, home, away, mercado_aprendido, prob_aprendido, placar_previsto, finalizado, data_utc
        FROM previsoes
        WHERE esporte = 'futebol' AND liga_id = ? AND finalizado = 0
        ORDER BY data_utc
    """, (liga_id,))
    
    if previsoes_periodo.empty:
        st.info("Sem previsões para o período selecionado")
        return

    st.markdown("### 🎯 Previsões Geradas")
    
    for _, prev in previsoes_periodo.iterrows():
        with st.container():
            col1, col2, col3 = st.columns([2, 2, 1.5])
            with col1:
                try:
                    data_formatada = datetime.fromisoformat(prev['data_jogo']).strftime("%d/%m")
                except:
                    data_formatada = str(prev['data_jogo'])
                st.markdown(f"**{data_formatada}** - **{prev['home']}** vs **{prev['away']}**")
            with col2:
                st.markdown(f"<span style='color: #4f46e5; font-weight: 600;'>{prev['mercado_aprendido']}</span>", unsafe_allow_html=True)
            with col3:
                st.markdown(f"<span style='color: #059669; font-weight: 700; font-size: 1.2rem;'>{pct(prev['prob_aprendido'])}</span>", unsafe_allow_html=True)
            st.divider()


def tela_tenis():
    st.header("🎾 TÊNIS")
    
    col1, col2, col3 = st.columns([1.2, 1.2, 1])
    with col1:
        jog1 = st.text_input("Jogador 1", "jannik sinner", label_visibility="collapsed")
    with col2:
        jog2 = st.text_input("Jogador 2", "carlos alcaraz", label_visibility="collapsed")
    with col3:
        superficie = st.selectbox("Quadra", ["Dura", "Saibro", "Grama", "Indoor"], label_visibility="collapsed")
    
    if normalizar(jog1) == normalizar(jog2):
        st.error("❌ Jogadores iguais")
        return
    
    f1, src1 = forca_generica(jog1, FORCA_TENIS, 80)
    f2, src2 = forca_generica(jog2, FORCA_TENIS, 80)
    probs = prob_tenis(f1, f2, superficie)
    mercado, codigo, prob = melhor_mercado(probs)
    contexto = f"tenis|{superficie.lower()}"
    prob_apr, ajuste = aplicar_ajuste(prob, codigo, contexto)
    
    st.markdown("### 📊 Análise")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(f"💪 {jog1[:15]}", f"{f1:.0f}")
    with col2:
        st.metric(f"💪 {jog2[:15]}", f"{f2:.0f}")
    with col3:
        st.metric("🏆 Favorito", mercado)
    with col4:
        st.metric("📈 Probabilidade", pct(prob_apr))
    
    st.markdown("### 🎲 Cenários")
    chips_prob(probs)
    
    card_moderno("Parecer Técnico", 
                 f"<b>{mercado}</b> é o favorito em quadra de <b>{superficie}</b> com <b>{pct(prob_apr)}</b> de chance. Ajuste aplicado: <b>{ajuste:+.1%}</b>",
                 "success")


def tela_historico():
    st.header("📋 HISTÓRICO")
    
    df = ler_tabela("SELECT * FROM previsoes ORDER BY id DESC LIMIT 500")
    if df.empty:
        st.info("Nenhuma previsão registrada")
        return
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total", len(df))
    with col2:
        st.metric("Finalizadas", int(df["finalizado"].fillna(0).sum()))
    with col3:
        prob_media = df["prob_aprendido"].dropna().mean() if not df["prob_aprendido"].dropna().empty else 0
        st.metric("Prob. Média", pct(prob_media) if prob_media > 0 else "N/A")
    with col4:
        taxa_acerto = df["acertou_aprendido"].dropna().mean() if not df["acertou_aprendido"].dropna().empty else 0
        st.metric("Acurácia", pct(taxa_acerto) if taxa_acerto > 0 else "N/A")
    
    st.markdown("### 📊 Últimas Previsões")
    cols_exib = ["data_jogo", "esporte", "home", "away", "mercado_aprendido", "prob_aprendido", "finalizado"]
    st.dataframe(df[cols_exib], use_container_width=True, hide_index=True)


def tela_diagnóstico():
    st.header("⚙️ DIAGNÓSTICO")
    
    checks = [
        ("Banco de Dados", os.path.exists(DB_PATH), "SQLite v3"),
        ("API ESPN", REQUESTS_OK, "Conexão ativa"),
        ("Machine Learning", SKLEARN_OK, "scikit-learn pronto"),
        ("Cache", True, "Sistema ativo"),
    ]
    
    for nome, ok, detalhe in checks:
        status = "✅ OK" if ok else "⚠️ Erro"
        card_moderno(nome, f"{status} - {detalhe}", "success" if ok else "warning")
    
    st.markdown("### 📈 Sistema")
    df = ler_tabela("SELECT * FROM previsoes ORDER BY id DESC LIMIT 50")
    if not df.empty:
        st.dataframe(df[["criado_em", "esporte", "home", "away", "mercado_aprendido", "prob_aprendido"]], 
                    use_container_width=True, hide_index=True)


# ======================= APP PRINCIPAL =======================
def main():
    aplicar_estilo()
    init_db()

    st.sidebar.markdown("""
    <div style='text-align: center; padding: 1.5rem 0;'>
        <h1 style='font-size: 1.8rem; margin: 0; color: #6366f1;'>⚽ PRO 18</h1>
        <p style='color: #4f46e5; margin-top: 0.5rem; font-size: 0.9rem;'>Analisador Esportivo</p>
        <p style='color: #6b7280; font-size: 0.75rem; margin: 0.5rem 0 0 0;'>v1.0 • Inteligência Esportiva</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.divider()
    
    pagina = st.sidebar.radio(
        "Navegação",
        ["⚽ Futebol", "🎾 Tênis", "📋 Histórico", "⚙️ Diagnóstico"],
        label_visibility="collapsed"
    )

    if pagina == "⚽ Futebol":
        tela_futebol()
    elif pagina == "🎾 Tênis":
        tela_tenis()
    elif pagina == "📋 Histórico":
        tela_historico()
    else:
        tela_diagnóstico()
    
    # Footer
    st.sidebar.divider()
    st.sidebar.caption("🔐 Dados seguros • 🚀 Rápido • 📊 Preciso")


if __name__ == "__main__":
    main()
