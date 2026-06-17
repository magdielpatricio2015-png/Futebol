import html
import math
import os
import re
import sqlite3
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import streamlit as st

# ======================= CONFIGURAÇÃO DE AMBIENTE =======================
try:
    from zoneinfo import ZoneInfo
    TZ_BR = ZoneInfo("America/Sao_Paulo")
except ImportError:
    from datetime import timedelta
    TZ_BR = timezone(timedelta(hours=-3))  # Fallback para Python < 3.9

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False


# ======================= CONFIGURAÇÃO GLOBAL =======================
st.set_page_config(
    page_title="Pro 18 - Analisador Esportivo",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "Analisador Esportivo Pro 18 - v2.4"}
)

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
HEADERS = {"User-Agent": "AnalisadorEsportivoPro/18.0"}
DB_PATH = "data/modelo_v18.db"

MAX_GOLS = 10
RETRIES = 3
MIN_JOGOS_TREINO = 30
AUTO_UPDATE_INTERVAL_SECONDS = 15 * 60  # 15 minutos

HOME_ADV_LIGA = {
    "bra.1": 0.28, "bra.2": 0.27, "bra.copa_do_brazil": 0.22,
    "eng.1": 0.22, "esp.1": 0.24, "ita.1": 0.25, "ger.1": 0.26, "fra.1": 0.24,
    "uefa.champions": 0.20, "uefa.europa": 0.18,
    "conmebol.libertadores": 0.30, "conmebol.sudamericana": 0.28,
    "fifa.world": 0.08
}

LIGAS = {
    "🌍 Copa do Mundo": "fifa.world",
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
    # Seleções
    "brasil": 88, "argentina": 91, "franca": 90, "england": 85, "espanha": 88,
    "alemanha": 85, "portugal": 86, "holanda": 84, "belgica": 82, "croacia": 82,
    "uruguai": 81, "colombia": 80, "mexico": 79, "estados unidos": 78, "canada": 77,
    "australia": 76, "japao": 79, "coreia do sul": 78, "marrocos": 80, "senegal": 79,
    "nigeria": 77, "egito": 76, "camaroes": 75, "ghana": 75, "tunisia": 74,
    "africa do sul": 73, "costa do marfim": 77, "mali": 74, "suica": 80,
    "austria": 79, "dinamarca": 81, "suecia": 79, "noruega": 80, "polonia": 78,
    "czechia": 77, "eslovaquia": 75, "hungria": 75, "escocia": 76, "gales": 75,
    "turquia": 78, "ukraine": 77, "serbia": 77, "albania": 74, "iran": 75,
    "arabia saudita": 73, "qatar": 71, "equador": 75, "chile": 76, "peru": 74,
    "venezuela": 72, "bolivia": 68, "paraguai": 71, "costa rica": 73, "panama": 70,
    "honduras": 69, "jamaica": 69, "nova zelandia": 68,
    # Clubes Brasil
    "flamengo": 86, "palmeiras": 84, "botafogo": 79, "atletico-mg": 76,
    "sao paulo": 78, "fluminense": 77, "gremio": 74, "internacional": 75,
    "corinthians": 76, "cruzeiro": 73, "bahia": 74, "fortaleza": 73, "vasco": 70,
    "santos": 72, "ceara": 69, "sport": 68, "vitoria": 69, "coritiba": 68,
    "athletico-pr": 72, "atletico goianiense": 68, "goias": 68, "cuiaba": 67,
    "juventude": 67, "chapecoense": 65, "crb": 65, "csa": 64, "paysandu": 64,
    "remo": 64, "ponte preta": 65, "guarani": 64, "novorizontino": 67,
    "mirassol": 68, "operario pr": 64, "vila nova": 66, "amazonas": 64,
    "america mineiro": 68, "bragantino": 72, "red bull bragantino": 72,
    "sao bernardo": 63, "tombense": 62, "volta redonda": 62, "santa cruz": 61,
    "retro": 61,
    # Clubes Europa
    "manchester city": 91, "arsenal": 88, "liverpool": 88, "chelsea": 82,
    "tottenham hotspur": 80, "manchester united": 81, "real madrid": 90,
    "barcelona": 87, "atletico madrid": 84, "bayern munich": 88,
    "borussia dortmund": 82, "bayer leverkusen": 84, "inter milan": 86,
    "juventus": 82, "milan": 81, "paris saint-germain": 88
}

ALIASES = {
    "brazil": "brasil", "brazil national team": "brasil", "selecao brasileira": "brasil",
    "argentina national team": "argentina", "france": "franca", "france national team": "franca",
    "england national team": "england", "spain": "espanha", "spain national team": "espanha",
    "germany": "alemanha", "germany national team": "alemanha", "portugal national team": "portugal",
    "netherlands": "holanda", "holland": "holanda", "nederland": "holanda", "belgium": "belgica",
    "croatia": "croacia", "uruguay": "uruguai", "colombia": "colombia", "japan": "japao",
    "south korea": "coreia do sul", "korea republic": "coreia do sul", "morocco": "marrocos",
    "switzerland": "suica", "denmark": "dinamarca", "sweden": "suecia", "norway": "noruega",
    "poland": "polonia", "czech republic": "czechia", "slovakia": "eslovaquia", "hungary": "hungria",
    "scotland": "escocia", "wales": "gales", "turkey": "turquia", "ukraine": "ukraine",
    "ecuador": "equador", "chile": "chile", "peru": "peru", "bolivia": "bolivia", "paraguay": "paraguai",
    "costa rica": "costa rica", "panama": "panama", "honduras": "honduras", "jamaica": "jamaica",
    "ivory coast": "costa do marfim", "cote d'ivoire": "costa do marfim", "iran": "iran",
    "saudi arabia": "arabia saudita", "south africa": "africa do sul", "ghana": "ghana",
    "man city": "manchester city", "man utd": "manchester united", "man united": "manchester united",
    "tottenham": "tottenham hotspur", "spurs": "tottenham hotspur", "psg": "paris saint-germain",
    "paris sg": "paris saint-germain", "inter": "inter milan", "internazionale": "inter milan",
    "atletico mineiro": "atletico-mg", "atletico mg": "atletico-mg", "vasco da gama": "vasco",
    "sao paulo fc": "sao paulo", "gremio fbpa": "gremio", "athletico paranaense": "athletico-pr",
    "atletico pr": "athletico-pr", "operario": "operario pr", "operario-pr": "operario pr"
}


# ======================= ESTILO =======================
def aplicar_estilo() -> None:
    st.markdown("""
        <style>
        html, body, [data-testid="stAppViewContainer"] {
            background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
            color: #0f172a;
        }
        .block-container {
            padding: 2rem 1.5rem 5rem 1.5rem;
            max-width: 1400px;
        }
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
        .chip-red { background: #fee2e2; color: #991b1b; border-color: #fecaca; }
        .chip-blue { background: #dbeafe; color: #1e40af; border-color: #7dd3fc; }
        .chip-gray { background: #f1f5f9; color: #475569; border-color: #cbd5e1; }
        .chip-gold { background: #fef9c3; color: #713f12; border-color: #fde047; }
        .chip-purple { background: #ede9fe; color: #4c1d95; border-color: #a78bfa; }
        .chip-orange { background: #fff7ed; color: #9a3412; border-color: #fdba74; }
        .chip-teal { background: #ccfbf1; color: #134e4a; border-color: #5eead4; }
        button { border-radius: 8px !important; font-weight: 600 !important; }
        </style>
    """, unsafe_allow_html=True)


# ======================= UTILITÁRIOS =======================
def agora_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def formatar_data_brasil(dt: datetime) -> str:
    try:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(TZ_BR).strftime("%d/%m %H:%M")
    except Exception:
        return "Data inválida"

def esc(valor: Any) -> str:
    return html.escape(str(valor)) if valor is not None else ""

def normalizar(nome: str) -> str:
    nome = str(nome or "").strip().lower()
    nome = unicodedata.normalize("NFD", nome)
    nome = "".join(c for c in nome if unicodedata.category(c) != "Mn")
    nome = re.sub(r"['.,]", "", nome)
    nome = re.sub(r"\b(fc|sc|ac)\b$", "", nome).strip()
    return ALIASES.get(nome, nome)

def pct(valor: Any) -> str:
    try:
        valor_num = float(valor)
        return f"{max(0.0, min(1.0, valor_num)) * 100:.1f}%"
    except (ValueError, TypeError):
        return "0.0%"

def traduzir_mercado(mercado: str) -> str:
    traducoes = {
        "casa_ou_empate": "Casa ou Empate", "empate_ou_fora": "Empate ou Fora",
        "casa_vence": "Casa vence", "fora_vence": "Fora vence", "empate": "Empate",
        "over_1.5": "Over 1.5 Gols", "over_2.5": "Over 2.5 Gols",
        "ambos_marcam": "Ambos marcam", "home_win": "Casa Vence (1)",
        "draw": "Empate (X)", "away_win": "Fora Vence (2)"
    }
    return traducoes.get(str(mercado or "").lower(), str(mercado or ""))

def parse_data_espn(valor: Any) -> Optional[datetime]:
    if not valor:
        return None
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None

def safe_int(valor: Any) -> Optional[int]:
    try:
        if valor is None or str(valor).strip() == "":
            return None
        return int(float(str(valor).strip()))
    except (ValueError, TypeError):
        return None

def eh_copa_do_mundo(liga_id: str) -> bool:
    return liga_id == "fifa.world"

def info_liga(liga_id: str) -> dict:
    mapa = {
        "fifa.world": {
            "emoji": "🏆", "nome": "COPA DO MUNDO FIFA",
            "subtitulo": "Análise por força das seleções · Sede neutra · Modelo Poisson + ML",
            "header": "🌍 COPA DO MUNDO",
            "banner_bg": "linear-gradient(135deg, #1a3a1a 0%, #2d6a2d 50%, #1a3a1a 100%)",
            "banner_border": "#fde047", "banner_titulo_cor": "#fde047",
            "banner_sub_cor": "#bbf7d0", "chip_classe": "chip-gold",
            "chip_label": "🌍 Copa do Mundo", "label_rodada": "🏆 Jogos da Copa do Mundo",
            "aviso_vazio": "⚠️ Nenhum jogo da Copa do Mundo encontrado."
        },
        "conmebol.libertadores": {
            "emoji": "🏆", "nome": "LIBERTADORES DA AMÉRICA",
            "subtitulo": "Maior competição sul-americana · Modelo Poisson + ML",
            "header": "🌎 LIBERTADORES DA AMÉRICA",
            "banner_bg": "linear-gradient(135deg, #1e1b4b 0%, #3730a3 50%, #1e1b4b 100%)",
            "banner_border": "#a5b4fc", "banner_titulo_cor": "#e0e7ff",
            "banner_sub_cor": "#c7d2fe", "chip_classe": "chip-purple",
            "chip_label": "🌎 Libertadores", "label_rodada": "🌎 Jogos da Libertadores",
            "aviso_vazio": "⚠️ Nenhum jogo da Libertadores encontrado."
        },
        "bra.1": {
            "emoji": "🇧🇷", "nome": "BRASILEIRÃO SÉRIE A",
            "subtitulo": "Primeira divisão do futebol brasileiro",
            "header": "🇧🇷 BRASILEIRÃO SÉRIE A",
            "banner_bg": "linear-gradient(135deg, #14532d 0%, #15803d 50%, #14532d 100%)",
            "banner_border": "#4ade80", "banner_titulo_cor": "#dcfce7",
            "banner_sub_cor": "#bbf7d0", "chip_classe": "chip-green",
            "chip_label": "🇧🇷 Brasileirão A", "label_rodada": "📅 Jogos da Rodada",
            "aviso_vazio": "⚠️ Nenhum jogo do Brasileirão Série A encontrado."
        }
    }
    return mapa.get(liga_id, {
        "emoji": "⚽", "nome": liga_id.upper(),
        "subtitulo": "Análise estatística Poisson + ML",
        "header": "⚽ FUTEBOL COM APRENDIZADO",
        "banner_bg": "linear-gradient(135deg, #1e293b 0%, #334155 50%, #1e293b 100%)",
        "banner_border": "#94a3b8", "banner_titulo_cor": "#e2e8f0",
        "banner_sub_cor": "#cbd5e1", "chip_classe": "chip-gray",
        "chip_label": "⚽ Futebol", "label_rodada": "📅 Jogos da Rodada",
        "aviso_vazio": "⚠️ Nenhum jogo encontrado para esta liga."
    })


# ======================= BANCO DE DADOS =======================
def conectar_db() -> sqlite3.Connection:
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn

def init_db() -> None:
    conn = conectar_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS previsoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT UNIQUE NOT NULL,
            esporte TEXT, liga_id TEXT, liga_nome TEXT, data_jogo TEXT,
            home TEXT, away TEXT, forca_home REAL, forca_away REAL, home_adv REAL,
            contexto TEXT, mercado_base TEXT, codigo_base TEXT, prob_base REAL,
            mercado_aprendido TEXT, codigo_aprendido TEXT, prob_aprendido REAL,
            ajuste_aplicado REAL, placar_previsto TEXT, escanteios_previstos TEXT,
            cartoes_previstos TEXT, home_score INTEGER, away_score INTEGER,
            acertou_base INTEGER, acertou_aprendido INTEGER, finalizado INTEGER DEFAULT 0,
            status_resultado TEXT, criado_em TEXT, atualizado_em TEXT, data_utc TEXT,
            odds_home REAL, odds_draw REAL, odds_away REAL, prob_implicita_home REAL,
            prob_implicita_draw REAL, prob_implicita_away REAL, ev_home REAL, ev_draw REAL,
            ev_away REAL, mercado_valor TEXT, kelly_fracao REAL
        )
    """)

    cur.execute("PRAGMA table_info(previsoes)")
    colunas_existentes = {row[1] for row in cur.fetchall()}

    colunas_necessarias = [
        ("forca_home", "REAL"), ("forca_away", "REAL"), ("home_adv", "REAL"),
        ("contexto", "TEXT"), ("mercado_base", "TEXT"), ("codigo_base", "TEXT"),
        ("prob_base", "REAL"), ("mercado_aprendido", "TEXT"), ("codigo_aprendido", "TEXT"),
        ("prob_aprendido", "REAL"), ("ajuste_aplicado", "REAL"), ("placar_previsto", "TEXT"),
        ("escanteios_previstos", "TEXT"), ("cartoes_previstos", "TEXT"), ("home_score", "INTEGER"),
        ("away_score", "INTEGER"), ("acertou_base", "INTEGER"), ("acertou_aprendido", "INTEGER"),
        ("finalizado", "INTEGER DEFAULT 0"), ("status_resultado", "TEXT"), ("criado_em", "TEXT"),
        ("atualizado_em", "TEXT"), ("data_utc", "TEXT"), ("odds_home", "REAL"),
        ("odds_draw", "REAL"), ("odds_away", "REAL"), ("prob_implicita_home", "REAL"),
        ("prob_implicita_draw", "REAL"), ("prob_implicita_away", "REAL"), ("ev_home", "REAL"),
        ("ev_draw", "REAL"), ("ev_away", "REAL"), ("mercado_valor", "TEXT"), ("kelly_fracao", "REAL")
    ]

    for coluna, tipo in colunas_necessarias:
        if coluna not in colunas_existentes:
            try:
                cur.execute(f"ALTER TABLE previsoes ADD COLUMN {coluna} {tipo}")
            except sqlite3.OperationalError:
                pass

    cur.execute("CREATE INDEX IF NOT EXISTS idx_game_id ON previsoes(game_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_liga_finalizado ON previsoes(liga_id, finalizado)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_data_utc ON previsoes(data_utc)")
    conn.commit()
    conn.close()

def ler_tabela(sql: str, params: tuple = ()) -> pd.DataFrame:
    try:
        with conectar_db() as conn:
            return pd.read_sql_query(sql, conn, params=params)
    except Exception as e:
        st.error(f"Erro ao ler banco: {str(e)}")
        return pd.DataFrame()

def executar(sql: str, params: tuple = ()) -> None:
    try:
        with conectar_db() as conn:
            conn.execute(sql, params)
            conn.commit()
    except Exception as e:
        st.error(f"Erro ao executar SQL: {str(e)}")


# ======================= AVALIAÇÃO =======================
def avaliar_codigo(codigo: Any, home_score: Any, away_score: Any) -> Optional[int]:
    h = safe_int(home_score)
    a = safe_int(away_score)
    if h is None or a is None:
        return None

    codigo = str(codigo or "").strip().lower()
    total = h + a

    regras = {
        "casa_ou_empate": h >= a, "empate_ou_fora": a >= h,
        "casa_vence": h > a, "fora_vence": a > h, "empate": h == a,
        "over_1.5": total > 1, "over_2.5": total > 2,
        "ambos_marcam": h > 0 and a > 0, "home_win": h > a,
        "draw": h == a, "away_win": a > h
    }

    return 1 if regras.get(codigo, False) else 0

def texto_status_acerto(acertou: Any) -> str:
    if pd.isna(acertou):
        return "Pendente"
    return "Acerto" if int(acertou) == 1 else "Erro"

def recalcular_acertos_banco() -> int:
    df = ler_tabela("""
        SELECT game_id, codigo_base, codigo_aprendido, home_score, away_score
        FROM previsoes WHERE finalizado = 1 AND home_score IS NOT NULL
    """)
    if df.empty:
        return 0

    atualizados = 0
    for _, row in df.iterrows():
        acertou_base = avaliar_codigo(row["codigo_base"], row["home_score"], row["away_score"])
        acertou_aprendido = avaliar_codigo(row["codigo_aprendido"], row["home_score"], row["away_score"])
        status = texto_status_acerto(acertou_aprendido)

        executar("""
            UPDATE previsoes SET acertou_base=?, acertou_aprendido=?, status_resultado=?, atualizado_em=?
            WHERE game_id=?
        """, (acertou_base, acertou_aprendido, status, agora_utc_iso(), row["game_id"]))
        atualizados += 1
    return atualizados


# ======================= API =======================
@st.cache_data(ttl=600, show_spinner=False)
def api_get_json(url: str, params: Optional[dict] = None) -> Optional[dict]:
    if not REQUESTS_OK:
        return None

    for tentativa in range(RETRIES):
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=12)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in {429, 500, 502, 503, 504}:
                time.sleep(1 + tentativa)
                continue
            return None
        except requests.exceptions.RequestException:
            time.sleep(0.5 + tentativa * 0.5)
    return None

@st.cache_data(ttl=600, show_spinner=False)
def buscar_jogos_rodada(liga_id: str) -> pd.DataFrame:
    dados = api_get_json(f"{ESPN_BASE}/{liga_id}/scoreboard", {"limit": 100})
    if not dados or "events" not in dados:
        return pd.DataFrame()

    linhas = []
    for evento in dados["events"]:
        data_utc = parse_data_espn(evento.get("date"))
        if not data_utc:
            continue

        competicao = evento.get("competitions", [{}])[0]
        home = away = None
        home_score = away_score = None

        for time in competicao.get("competitors", []):
            nome = time.get("team", {}).get("displayName")
            placar = safe_int(time.get("score"))
            if time.get("homeAway") == "home":
                home, home_score = nome, placar
            else:
                away, away_score = nome, placar

        status = evento.get("status", {}).get("type", {})
        linhas.append({
            "game_id": str(evento.get("id")),
            "data_utc": data_utc.isoformat(),
            "data_local": formatar_data_brasil(data_utc),
            "home": home, "away": away,
            "home_score": home_score, "away_score": away_score,
            "completed": bool(status.get("completed")),
            "status_text": status.get("shortDetail", "")
        })

    return pd.DataFrame(linhas).sort_values("data_utc").reset_index(drop=True)

@st.cache_data(ttl=300, show_spinner=False)
def buscar_odds(game_id: str, home_team: str, away_team: str) -> dict:
    # Substitua por API real de odds
    return {
        "home_win": 1.80, "draw": 3.50, "away_win": 4.20,
        "over_2.5": 1.90, "under_2.5": 1.80, "btts_yes": 1.75, "btts_no": 2.00
    }


# ======================= MODELAGEM =======================
def poisson(k: int, lamb: float) -> float:
    lamb = max(lamb, 0.1)
    try:
        return (lamb ** k * math.exp(-lamb)) / math.factorial(k)
    except OverflowError:
        return 0.0

def placar_mais_provavel(lambda_home: float, lambda_away: float) -> str:
    max_prob = -1.0
    melhor = "0x0"
    for h in range(MAX_GOLS + 1):
        for a in range(MAX_GOLS + 1):
            prob = poisson(h, lambda_home) * poisson(a, lambda_away)
            if prob > max_prob:
                max_prob = prob
                melhor = f"{h}x{a}"
    return melhor

def montar_features(fh: float, fa: float, adv: float) -> list[float]:
    return [fh, fa, adv, fh - fa, (fh + fa) / 2]

@st.cache_resource
def treinar_modelo_ml():
    df = ler_tabela("""
        SELECT forca_home, forca_away, home_adv, home_score, away_score
        FROM previsoes WHERE finalizado = 1 AND home_score IS NOT NULL
    """)
    if len(df) < MIN_JOGOS_TREINO:
        return None, None, []

    df["target"] = (df["home_score"] >= df["away_score"]).astype(int)
    df["diff_forca"] = df["forca_home"] - df["forca_away"]
    df["media_forca"] = (df["forca_home"] + df["forca_away"]) / 2

    colunas = ["forca_home", "forca_away", "home_adv", "diff_forca", "media_forca"]
    X = df[colunas].fillna(0)
    y = df["target"]

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    modelo = LogisticRegression(random_state=42, solver="liblinear", max_iter=1000)
    modelo.fit(X_scaled, y)
    return modelo, scaler, colunas

def analisar_jogo(home: str, away: str, liga_id: str, liga_nome: str, modelo, scaler, odds: dict) -> dict:
    nh = normalizar(home)
    na = normalizar(away)

    fh = FORCA_BASE.get(nh, 72.0)
    fa = FORCA_BASE.get(na, 70.0)
    adv = HOME_ADV_LIGA.get(liga_id, 0.25)

    diff = (fh + adv * 10) - fa
    lh = max(1.28 + diff / 34, 0.2)
    la = max(1.08 - diff / 40, 0.2)

    prob_h = prob_d = prob_a = 0.0
    for h in range(MAX_GOLS + 1):
        for a in range(MAX_GOLS + 1):
            p = poisson(h, lh) * poisson(a, la)
            if h > a:
                prob_h += p
            elif h == a:
                prob_d += p
            else:
                prob_a += p

    total = prob_h + prob_d + prob_a
    if total > 0:
        prob_h /= total
        prob_d /= total
        prob_a /= total

    mercado_base = "casa_ou_empate" if prob_h >= prob_a else "empate_ou_fora"
    prob_base = prob_h + prob_d if mercado_base == "casa_ou_empate" else prob_a + prob_d

    ajuste_ml = 0.0
    mercado_aprendido = mercado_base
    prob_aprendido = prob_base

    if modelo and scaler and SKLEARN_OK:
        features = np.array([montar_features(fh, fa, adv)])
        features_scaled = scaler.transform(features)
        prob_ml = modelo.predict_proba(features_scaled)[0][1]
        prob_final = (prob_base * 0.6) + (prob_ml * 0.4)
        ajuste_ml = prob_final - prob_base

        if prob_final >= 0.5:
            mercado_aprendido = "casa_ou_empate"
            prob_aprendido = prob_final
        else:
            mercado_aprendido = "empate_ou_fora"
            prob_aprendido = 1 - prob_final

    # Escanteios e cartões
    if eh_copa_do_mundo(liga_id):
        base_esc, base_cart = 9.8, 3.8
    elif "bra" in liga_id or "conmebol" in liga_id:
        base_esc, base_cart = 10.0, 5.4
    else:
        base_esc, base_cart = 9.5, 4.2

    escanteios = max(5.0, base_esc + (fh + fa - 140) / 20)
    cartoes = max(1.0, base_cart + (160 - fh - fa) / 30)
    placar = placar_mais_provavel(lh, la)

    # Cálculo de valor esperado e Kelly
    odds_home = max(odds.get("home_win", 0.0), 1.01)
    odds_draw = max(odds.get("draw", 0.0), 1.01)
    odds_away = max(odds.get("away_win", 0.0), 1.01)

    soma_inv = (1/odds_home) + (1/odds_draw) + (1/odds_away)
    soma_inv = max(soma_inv, 0.001)

    prob_impl_h = (1/odds_home) / soma_inv
    prob_impl_d = (1/odds_draw) / soma_inv
    prob_impl_a = (1/odds_away) / soma_inv

    ev_h = (prob_h * (odds_home - 1)) - (1 - prob_h)
    ev_d = (prob_d * (odds_draw - 1)) - (1 - prob_d)
    ev_a = (prob_a * (odds_away - 1)) - (1 - prob_a)

    melhor_ev = max(ev_h, ev_d, ev_a)
    mercado_valor = "Nenhum"
    kelly = 0.0

    if melhor_ev > 0:
        if melhor_ev == ev_h:
            mercado_valor = "home_win"
            b, p = odds_home - 1, prob_h
        elif melhor_ev == ev_d:
            mercado_valor = "draw"
            b, p = odds_draw - 1, prob_d
        else:
            mercado_valor = "away_win"
            b, p = odds_away - 1, prob_a

        if b > 0:
            kelly = (b * p - (1 - p)) / b
            kelly = max(0.0, min(kelly, 0.10))  # Limite de 10%

    return {
        "mercado_base": mercado_base, "codigo_base": mercado_base, "prob_base": prob_base,
        "mercado_aprendido": mercado_aprendido, "codigo_aprendido": mercado_aprendido,
        "prob_aprendido": prob_aprendido, "placar_previsto": placar,
        "escanteios_previstos": f"{escanteios:.1f}", "cartoes_previstos": f"{cartoes:.1f}",
        "forca_home": fh, "forca_away": fa, "home_adv": adv, "ajuste_aplicado": ajuste_ml,
        "odds_home": odds_home, "odds_draw": odds_draw, "odds_away": odds_away,
        "prob_implicita_home": prob_impl_h, "prob_implicita_draw": prob_impl_d,
        "prob_implicita_away": prob_impl_a, "ev_home": ev_h, "ev_draw": ev_d,
        "ev_away": ev_a, "mercado_valor": mercado_valor, "kelly_fracao": kelly
    }


# ======================= PERSISTÊNCIA =======================
def salvar_previsao(**dados):
    dados.setdefault("atualizado_em", agora_utc_iso())
    dados.setdefault("criado_em", agora_utc_iso())

    colunas = ", ".join(dados.keys())
    valores = ", ".join(["?"] * len(dados))
    atualizacoes = ", ".join([f"{k} = excluded.{k}" for k in dados.keys()])

    executar(f"""
        INSERT INTO previsoes ({colunas}) VALUES ({valores})
        ON CONFLICT(game_id) DO UPDATE SET {atualizacoes}
    """, tuple(dados.values()))

def salvar_e_ler_previsao(jogo: pd.Series, liga_id: str, liga_nome: str, modelo, scaler) -> Optional[dict]:
    odds = buscar_odds(jogo["game_id"], jogo["home"], jogo["away"])
    analise = analisar_jogo(jogo["home"], jogo["away"], liga_id, liga_nome, modelo, scaler, odds)

    salvar_previsao(
        game_id=jogo["game_id"], esporte="futebol", liga_id=liga_id, liga_nome=liga_nome,
        data_jogo=jogo["data_local"], home=jogo["home"], away=jogo["away"],
        data_utc=jogo["data_utc"], finalizado=int(jogo["completed"]),
        home_score=jogo["home_score"], away_score=jogo["away_score"], **analise
    )
    return analise

def atualizar_resultados_finalizados(liga_id_filtro: Optional[str] = None) -> int:
    sql = "SELECT game_id, liga_id FROM previsoes WHERE finalizado = 0"
    params = ()
    if liga_id_filtro:
        sql += " AND liga_id = ?"
        params = (liga_id_filtro,)

    pendentes = ler_tabela(sql, params)
    if pendentes.empty:
        return 0

    atualizados = 0
    for liga in pendentes["liga_id"].unique():
        dados = api_get_json(f"{ESPN_BASE}/{liga}/scoreboard", {"limit": 100})
        if not dados:
            continue

        eventos = {str(e["id"]): e for e in dados.get("events", [])}
        for _, row in pendentes[pendentes["liga_id"] == liga].iterrows():
            evento = eventos.get(row["game_id"])
            if not evento or not evento.get("status", {}).get("type", {}).get("completed"):
                continue

            comp = evento.get("competitions", [{}])[0]
            h = a = None
            for t in comp.get("competitors", []):
                if t["homeAway"] == "home":
                    h = safe_int(t.get("score"))
                else:
                    a = safe_int(t.get("score"))

            if h is None or a is None:
                continue

            acertou_base = avaliar_codigo(row.get("codigo_base"), h, a)
            acertou_aprendido = avaliar_codigo(row.get("codigo_aprendido"), h, a)
            status = texto_status_acerto(acertou_aprendido)

            executar("""
                UPDATE previsoes SET finalizado=1, home_score=?, away_score=?,
                acertou_base=?, acertou_aprendido=?, status_resultado=?, atualizado_em=?
                WHERE game_id=?
            """, (h, a, acertou_base, acertou_aprendido, status, agora_utc_iso(), row["game_id"]))
            atualizados += 1
    return atualizados

def auto_atualizar_resultados(liga_id_filtro: Optional[str] = None) -> int:
    chave = f"ultima_atualizacao_{liga_id_filtro or 'todas'}"
    agora = time.time()
    if agora - st.session_state.get(chave, 0) < AUTO_UPDATE_INTERVAL_SECONDS:
        return 0

    atualizados = atualizar_resultados_finalizados(liga_id_filtro)
    recalcular_acertos_banco()
    st.session_state[chave] = agora
    return atualizados


# ======================= MÉTRICAS E TELAS =======================
def resumo_metricas() -> dict:
    df = ler_tabela("SELECT * FROM previsoes WHERE finalizado = 1")
    if df.empty:
        return {
            "finalizados": 0, "acertos": 0, "erros": 0, "taxa": 0.0,
            "acertos_base": 0, "erros_base": 0, "taxa_base": 0.0,
            "ev_medio": 0.0, "kelly_total": 0.0
        }

    total = len(df)
    acertos_apr = df["acertou_aprendido"].sum()
    acertos_base = df["acertou_base"].sum()

    return {
        "finalizados": total, "acertos": int(acertos_apr), "erros": int(total - acertos_apr),
        "taxa": acertos_apr / total if total else 0.0, "acertos_base": int(acertos_base),
        "erros_base": int(total - acertos_base), "taxa_base": acertos_base / total if total else 0.0,
        "ev_medio": df[["ev_home", "ev_draw", "ev_away"]].max(axis=1).mean(),
        "kelly_total": df["kelly_fracao"].sum()
    }

def tela_futebol():
    st.title("⚽ Analisador Esportivo Pro 18")
    liga_selecionada = st.sidebar.selectbox("Selecione a Liga", list(LIGAS.keys()), index=1)
    liga_id = LIGAS[liga_selecionada]
    meta = info_liga(liga_id)

    st.markdown(f"""
        <div style="background: {meta['banner_bg']}; border-radius: 12px; padding: 1rem 1.5rem;
                    margin-bottom: 1rem; border: 2px solid {meta['banner_border']}; display: flex;
                    align-items: center; gap: 1rem;">
            <span style="font-size: 2.5rem;">{meta['emoji']}</span>
            <div>
                <span style="color: {meta['banner_titulo_cor']}; font-size: 1.3rem; font-weight: 800;">
                    {meta['nome']}
                </span><br>
                <span style="color: {meta['banner_sub_cor']}; font-size: 0.85rem;">{meta['subtitulo']}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    if auto_atualizar_resultados(liga_id):
        st.success("✅ Resultados atualizados automaticamente")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🔃 Atualizar Rodada", use_container_width=True):
            st.cache_data.clear()
            atualizados = atualizar_resultados_finalizados(liga_id)
            st.success(f"✅ {atualizados} resultados atualizados") if atualizados else st.info("Nenhuma novidade")
            st.rerun()

    with col_b:
        if st.button("🧮 Recalcular Acertos", use_container_width=True):
            total = recalcular_acertos_banco()
            st.success(f"✅ {total} registros recalculados")
            st.rerun()

    modelo, scaler, _ = treinar_modelo_ml()
    if modelo:
        st.success("🤖 Modelo de aprendizado ativo")
    else:
        st.info(f"📊 Coletando dados: mínimo de {MIN_JOGOS_TREINO} jogos finalizados")

    metricas = resumo_metricas()
    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    c1.metric("Finalizados", metricas["finalizados"])
    c2.metric("Acertos", metricas["acertos"])
    c3.metric("Erros", metricas["erros"])
    c4.metric("Taxa", pct(metricas["taxa"]))
    c5.metric("Taxa Base", pct(metricas["taxa_base"]))
    c6.metric("EV Médio", f"{metricas['ev_medio']:.2f}")
    c7.metric("Kelly Total", f"{metricas['kelly_total']:.1%}")

    df_rodada = buscar_jogos_rodada(liga_id)
    if df_rodada.empty:
        st.warning(meta["aviso_vazio"])
        return

    st.markdown(f"### {meta['label_rodada']} ({len(df_rodada)})")
    prev_existentes = ler_tabela("SELECT * FROM previsoes WHERE game_id IN ({})".format(
        ",".join(["?"] * len(df_rodada))
    ), tuple(df_rodada["game_id"]))
    prev_existentes = prev_existentes.set_index("game_id").to_dict("index") if not prev_existentes.empty else {}

    for _, jogo in df_rodada.iterrows():
        with st.container(border=True):
            prev = prev_existentes.get(jogo["game_id"]) or salvar_e_ler_previsao(jogo, liga_id, liga_selecionada, modelo, scaler)
            if not prev:
                continue

            col1, col2, col3, col4 = st.columns([2, 2, 1.5, 1.5])

            with col1:
                st.markdown(f"**{esc(jogo['data_local'])}**<br>"
                            f"<span class='chip {meta['chip_classe']}'>{meta['chip_label']}</span><br>"
                            f"🔵 **{esc(jogo['home'])}** vs 🔴 **{esc(jogo['away'])}**", unsafe_allow_html=True)
                if jogo["completed"]:
                    st.markdown(f"<span class='chip chip-gray'>Fim: {jogo['home_score']} x {jogo['away_score']}</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<span class='chip chip-blue
