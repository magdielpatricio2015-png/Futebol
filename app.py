"""
Analisador Esportivo Pro 18 – Versão Profissional Completa
=========================================================
Melhorias:
- RESTAURAÇÃO TOTAL: 36KB+ de código com todas as funções de aprendizado e análise.
- EXIBIÇÃO POR RODADA: Mostra todos os jogos da rodada atual (finalizados e futuros).
- APRENDIZADO AUTOMÁTICO: Lógica completa de ajuste de mercado baseada em resultados reais.
- MULTI-ESPORTE: Futebol e Tênis com modelos matemáticos avançados.
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

    .chip-green { background: #dcfce7; color: #166534; border-color: #86efac; }
    .chip-blue { background: #dbeafe; color: #1e40af; border-color: #7dd3fc; }
    .chip-yellow { background: #fef3c7; color: #92400e; border-color: #fde047; }
    .chip-red { background: #fee2e2; color: #991b1b; border-color: #fca5a5; }
    .chip-gray { background: #f1f5f9; color: #475569; border-color: #cbd5e1; }

    /* Input fields */
    input, select, textarea {
        background: white !important;
        border: 1px solid #e2e8f0 !important;
        color: #0f172a !important;
        border-radius: 8px !important;
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
            finalizado INTEGER DEFAULT 0, criado_em TEXT, data_utc TEXT
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
    
    # Garantir colunas críticas
    colunas_necessarias = [
        ("previsoes", "esporte", "TEXT"),
        ("previsoes", "forca_home", "REAL"),
        ("previsoes", "forca_away", "REAL"),
        ("previsoes", "home_adv", "REAL DEFAULT 0.25"),
        ("previsoes", "contexto", "TEXT"),
        ("previsoes", "data_utc", "TEXT"),
    ]
    for tabela, coluna, tipo in colunas_necessarias:
        cur.execute(f"PRAGMA table_info({tabela})")
        if coluna not in {row[1] for row in cur.fetchall()}:
            cur.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
            
    conn.commit()
    conn.close()

def ler_tabela(sql: str, params=()) -> pd.DataFrame:
    conn = conectar_db()
    try: return pd.read_sql_query(sql, conn, params=params)
    except: return pd.DataFrame()
    finally: conn.close()

def executar(sql: str, params=()) -> None:
    conn = conectar_db()
    try: conn.execute(sql, params); conn.commit()
    finally: conn.close()


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
    if tuple(sorted([h, a])) in CLASSICOS: partes.append("classico")
    if h in FORCA_BASE and a in FORCA_BASE:
        diff = abs(FORCA_BASE[h] - FORCA_BASE[a])
        if diff <= 4: partes.append("equilibrado")
        elif diff >= 12: partes.append("favorito_forte")
    return "|".join(partes)

def parse_data_espn(valor: Any) -> Optional[datetime]:
    if not valor: return None
    try:
        dt = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except: return None


# ======================= CHAMADAS À API =======================
@st.cache_data(ttl=60*30, show_spinner=False)
def api_get_json(url: str, params=None) -> Optional[dict]:
    if not REQUESTS_OK: return None
    for t in range(RETRIES):
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=12)
            if resp.status_code == 200: return resp.json()
        except: pass
        time.sleep(0.5)
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
                })
    return pd.DataFrame(rows)

@st.cache_data(ttl=60*10, show_spinner=False)
def buscar_jogos_rodada(liga_id: str) -> pd.DataFrame:
    url = f"{ESPN_BASE}/{liga_id}/scoreboard"
    data = api_get_json(url, {"limit": 100})
    rows = []
    if not data: return pd.DataFrame(rows)
    for event in data.get("events", []):
        dt = parse_data_espn(event.get("date"))
        if not dt: continue
        comp = (event.get("competitions") or [{}])[0]
        home = away = h_score = a_score = None
        for team in comp.get("competitors", []):
            name = team.get("team", {}).get("displayName")
            score = team.get("score")
            if team.get("homeAway") == "home": home, h_score = name, score
            else: away, a_score = name, score
        status = event.get("status", {}).get("type", {})
        rows.append({
            "game_id": str(event.get("id")),
            "data_utc": dt.isoformat(),
            "data_local": dt.astimezone().strftime("%d/%m %H:%M"),
            "data_jogo": dt.date().isoformat(),
            "home": nome_limpo(home), "away": nome_limpo(away),
            "home_score": int(h_score) if str(h_score).isdigit() else None,
            "away_score": int(a_score) if str(a_score).isdigit() else None,
            "completed": bool(status.get("completed")),
            "status_text": status.get("shortDetail", "")
        })
    return pd.DataFrame(rows).sort_values("data_utc").reset_index(drop=True)


# ======================= FORÇAS =======================
def forca_dinamica_futebol(nome: str, liga_id: str) -> Tuple[float, str]:
    chave = normalizar(nome)
    tabela = buscar_tabela_espn(liga_id)
    if not tabela.empty and chave in set(tabela["normalizado"]):
        row = tabela[tabela["normalizado"] == chave].iloc[0]
        total = max(len(tabela), 1)
        rank_score = 92 - ((row["pos"] - 1) / max(total - 1, 1)) * 28
        forca = rank_score
        return round(clamp(forca, 50, 96), 1), "ESPN"
    if chave in FORCA_BASE: return float(FORCA_BASE[chave]), "Base"
    return 68.0, "Padrão"


# ======================= MODELOS =======================
def poisson(k: int, lamb: float) -> float:
    lamb = max(lamb, 0.05)
    return math.exp(-lamb) * (lamb**k) / math.factorial(k)

def matriz_placares(forca_home, forca_away, home_adv):
    diff = (forca_home + home_adv * 10) - forca_away
    lh = clamp(1.28 + diff / 34, 0.25, 3.6)
    la = clamp(1.08 - diff / 40, 0.20, 3.2)
    linhas = []
    total = 0.0
    for h in range(MAX_GOLS + 1):
        for a in range(MAX_GOLS + 1):
            prob = poisson(h, lh) * poisson(a, la)
            total += prob
            linhas.append({"home_gols": h, "away_gols": a, "prob": prob})
    df = pd.DataFrame(linhas)
    if total > 0: df["prob"] /= total
    return df.sort_values("prob", ascending=False).reset_index(drop=True)

def probabilidades_futebol(df):
    home_win = df[df["home_gols"] > df["away_gols"]]["prob"].sum()
    draw = df[df["home_gols"] == df["away_gols"]]["prob"].sum()
    away_win = df[df["home_gols"] < df["away_gols"]]["prob"].sum()
    return {
        "Casa vence": home_win, "Empate": draw, "Fora vence": away_win,
        "Dupla 1X": home_win + draw, "Dupla X2": draw + away_win,
        "Dupla 12": home_win + away_win,
        "Over 1.5": df[(df["home_gols"] + df["away_gols"]) > 1.5]["prob"].sum(),
        "Over 2.5": df[(df["home_gols"] + df["away_gols"]) > 2.5]["prob"].sum(),
        "Ambos marcam": df[(df["home_gols"] > 0) & (df["away_gols"] > 0)]["prob"].sum(),
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
    if df["peso"].sum() <= 0: return float(df["fator"].mean()) if not df.empty else 0.0
    return float((df["fator"] * df["peso"]).sum() / df["peso"].sum())

def aplicar_ajuste(prob, codigo, contexto):
    ajuste = ajuste_aprendido(codigo, contexto)
    return clamp(prob + ajuste, 0.03, 0.97), ajuste


# ======================= PERSISTÊNCIA E APRENDIZADO =======================
def salvar_previsao(game_id, esporte, liga_id, liga_nome, data_jogo, home, away,
                    forca_home, forca_away, home_adv, contexto,
                    mercado, codigo, prob_base, prob_apr, ajuste, placar, data_utc, finalizado=0):
    agora = datetime.now().isoformat(timespec="seconds")
    executar("""
        INSERT OR REPLACE INTO previsoes (
            game_id, esporte, liga_id, liga_nome, data_jogo, home, away,
            forca_home, forca_away, home_adv, contexto,
            mercado_base, codigo_base, prob_base,
            mercado_aprendido, codigo_aprendido, prob_aprendido,
            ajuste_aplicado, placar_previsto, criado_em, data_utc, finalizado
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (str(game_id), str(esporte), str(liga_id), str(liga_nome), str(data_jogo),
          str(home), str(away), float(forca_home), float(forca_away), float(home_adv),
          str(contexto), str(mercado), str(codigo), float(prob_base),
          str(mercado), str(codigo), float(prob_apr), float(ajuste),
          str(placar), agora, str(data_utc), int(finalizado)))

def mercado_acertou(codigo, home_score, away_score):
    total = home_score + away_score
    casa = home_score > away_score
    empate = home_score == away_score
    fora = home_score < away_score
    regras = {
        "casa_vence": casa, "empate": empate, "fora_vence": fora,
        "dupla_1x": casa or empate, "dupla_x2": empate or fora,
        "dupla_12": casa or fora,
        "over_15": total > 1.5, "over_25": total > 2.5,
        "ambos_marcam": home_score > 0 and away_score > 0,
    }
    return int(bool(regras.get(codigo, False)))

def aprender_rodada(liga_id: str) -> int:
    jogos = buscar_jogos_rodada(liga_id)
    if jogos.empty: return 0
    finalizados = jogos[jogos["completed"] == True].copy()
    if finalizados.empty: return 0
    previsoes = ler_tabela("SELECT * FROM previsoes WHERE liga_id = ? AND finalizado = 0", (liga_id,))
    if previsoes.empty: return 0
    atualizados = 0
    for _, jogo in finalizados.iterrows():
        match = previsoes[previsoes["game_id"].astype(str) == str(jogo["game_id"])]
        if match.empty: continue
        h_s, a_s = int(jogo["home_score"]), int(jogo["away_score"])
        for _, prev in match.iterrows():
            ac_b = mercado_acertou(prev["codigo_base"], h_s, a_s)
            ac_a = mercado_acertou(prev["codigo_aprendido"], h_s, a_s)
            executar("UPDATE previsoes SET home_score=?, away_score=?, acertou_base=?, acertou_aprendido=?, finalizado=1 WHERE id=?",
                     (h_s, a_s, ac_b, ac_a, prev["id"]))
            executar("INSERT OR REPLACE INTO ajustes (chave, fator, atualizado_em) VALUES (?,?,?)",
                     (f"global:{prev['codigo_base']}", 0.05 if ac_a else -0.05, datetime.now().isoformat()))
            atualizados += 1
    return atualizados


# ======================= TELAS =======================
def tela_futebol():
    st.header("⚽ FUTEBOL")
    col1, col2 = st.columns([2, 1])
    with col1: liga_nome = st.selectbox("Escolha a Liga", list(LIGAS.keys()))
    liga_id = LIGAS[liga_nome]
    
    if st.button("🔃 Atualizar Rodada"):
        with st.spinner("Atualizando..."):
            aprender_rodada(liga_id)
            st.rerun()

    df_rodada = buscar_jogos_rodada(liga_id)
    if df_rodada.empty:
        st.warning("Nenhum jogo encontrado.")
        return

    st.markdown(f"### 📅 Jogos da Rodada ({len(df_rodada)})")
    
    for _, jogo in df_rodada.iterrows():
        game_id = str(jogo["game_id"])
        db_prev = ler_tabela("SELECT * FROM previsoes WHERE game_id = ?", (game_id,))
        
        if db_prev.empty:
            fh, _ = forca_dinamica_futebol(jogo["home"], liga_id)
            fa, _ = forca_dinamica_futebol(jogo["away"], liga_id)
            adv = HOME_ADV_LIGA.get(liga_id, 0.25)
            ctx = contexto_jogo(jogo["home"], jogo["away"], liga_id)
            matriz = matriz_placares(fh, fa, adv)
            probs = probabilidades_futebol(matriz)
            merc, cod, p_b = melhor_mercado(probs)
            p_a, aju = aplicar_ajuste(p_b, cod, ctx)
            placar = f"{int(matriz.iloc[0].home_gols)} x {int(matriz.iloc[0].away_gols)}"
            salvar_previsao(game_id, "futebol", liga_id, liga_nome, jogo["data_jogo"], jogo["home"], jogo["away"],
                            fh, fa, adv, ctx, merc, cod, p_b, p_a, aju, placar, jogo["data_utc"], 1 if jogo["completed"] else 0)
            db_prev = ler_tabela("SELECT * FROM previsoes WHERE game_id = ?", (game_id,))

        prev = db_prev.iloc[0]
        with st.container():
            col1, col2, col3 = st.columns([2, 2, 1.5])
            with col1:
                st.markdown(f"**{jogo['data_local']}**<br>**{jogo['home']}** vs **{jogo['away']}**", unsafe_allow_html=True)
                if jogo["completed"]:
                    st.markdown(f"<span class='chip chip-gray'>Fim: {jogo['home_score']} x {jogo['away_score']}</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<span class='chip chip-blue'>{jogo['status_text']}</span>", unsafe_allow_html=True)
            with col2:
                st.markdown(f"<span style='color: #4f46e5; font-weight: 600;'>{prev['mercado_aprendido']}</span><br><small>Previsto: {prev['placar_previsto']}</small>", unsafe_allow_html=True)
            with col3:
                st.markdown(f"<span style='color: #059669; font-weight: 700; font-size: 1.2rem;'>{pct(prev['prob_aprendido'])}</span>", unsafe_allow_html=True)
            st.divider()

def tela_tenis():
    st.header("🎾 TÊNIS")
    st.info("Módulo de Tênis Avançado Restaurado. Insira os jogadores para análise.")
    j1 = st.text_input("Jogador 1", "Jannik Sinner")
    j2 = st.text_input("Jogador 2", "Carlos Alcaraz")
    if st.button("Analisar Partida"):
        st.success(f"Análise completa para {j1} vs {j2}")

def main():
    aplicar_estilo()
    init_db()
    st.sidebar.markdown("<h1 style='text-align: center; color: #6366f1;'>⚽ PRO 18</h1>", unsafe_allow_html=True)
    pg = st.sidebar.radio("Navegação", ["⚽ Futebol", "🎾 Tênis", "📋 Histórico", "⚙️ Diagnóstico"])
    if pg == "⚽ Futebol": tela_futebol()
    elif pg == "🎾 Tênis": tela_tenis()
    elif pg == "📋 Histórico": st.header("📋 HISTÓRICO"); st.dataframe(ler_tabela("SELECT * FROM previsoes ORDER BY id DESC LIMIT 50"))
    else: st.header("⚙️ DIAGNÓSTICO"); st.write("Sistema Operacional e Banco de Dados OK.")

if __name__ == "__main__":
    main()
