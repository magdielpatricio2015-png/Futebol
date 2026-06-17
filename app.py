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

try:
    from zoneinfo import ZoneInfo

    TZ_BR = ZoneInfo("America/Sao_Paulo")
except Exception:
    TZ_BR = None

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
    menu_items={"About": "Analisador Esportivo Pro 18 - v2.3"},
)

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
HEADERS = {"User-Agent": "AnalisadorEsportivoPro/18.0"}
DB_PATH = "data/modelo_v18.db"

MAX_GOLS = 10
RETRIES = 3
MIN_JOGOS_TREINO = 30
AUTO_UPDATE_INTERVAL_SECONDS = 60 * 15

HOME_ADV_LIGA = {
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
    # Copa do Mundo: sede neutra (exceto país-sede), vantagem mínima
    "fifa.world": 0.08,
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

# Placeholder para força dinâmica das equipes (ELO/Glicko)
# Em uma implementação real, esta força seria calculada dinamicamente
# com base nos resultados dos jogos e na força dos adversários.
# Por enquanto, mantemos a força base estática.
FORCA_BASE = {
    # ===== SELEÇÕES – Copa do Mundo =====
    "brasil": 88,
    "argentina": 91,
    "franca": 90,
    "england": 85,
    "espanha": 88,
    "alemanha": 85,
    "portugal": 86,
    "holanda": 84,
    "belgica": 82,
    "croacia": 82,
    "uruguai": 81,
    "colombia": 80,
    "mexico": 79,
    "estados unidos": 78,
    "canada": 77,
    "australia": 76,
    "japao": 79,
    "coreia do sul": 78,
    "marrocos": 80,
    "senegal": 79,
    "nigeria": 77,
    "egito": 76,
    "camaroes": 75,
    "ghana": 75,
    "tunisia": 74,
    "africa do sul": 73,
    "costa do marfim": 77,
    "mali": 74,
    "suica": 80,
    "austria": 79,
    "dinamarca": 81,
    "suecia": 79,
    "noruega": 80,
    "polonia": 78,
    "czechia": 77,
    "eslovaquia": 75,
    "hungria": 75,
    "escocia": 76,
    "gales": 75,
    "turquia": 78,
    "ukraine": 77,
    "serbia": 77,
    "albania": 74,
    "iran": 75,
    "arabia saudita": 73,
    "qatar": 71,
    "equador": 75,
    "chile": 76,
    "peru": 74,
    "venezuela": 72,
    "bolivia": 68,
    "paraguai": 71,
    "costa rica": 73,
    "panama": 70,
    "honduras": 69,
    "jamaica": 69,
    "nova zelandia": 68,
    # ===== CLUBES – Brasil =====
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
    # ===== CLUBES – Europa =====
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

ALIASES = {
    # ===== Seleções =====
    "brazil": "brasil",
    "brazil national team": "brasil",
    "brazil (w)": "brasil",
    "selecao brasileira": "brasil",
    "argentina national team": "argentina",
    "france": "franca",
    "france national team": "franca",
    "england": "england",
    "england national team": "england",
    "spain": "espanha",
    "spain national team": "espanha",
    "germany": "alemanha",
    "germany national team": "alemanha",
    "portugal national team": "portugal",
    "netherlands": "holanda",
    "holland": "holanda",
    "nederland": "holanda",
    "belgium": "belgica",
    "croatia": "croacia",
    "uruguay": "uruguai",
    "colombia": "colombia",
    "japan": "japao",
    "south korea": "coreia do sul",
    "korea republic": "coreia do sul",
    "morocco": "marrocos",
    "switzerland": "suica",
    "denmark": "dinamarca",
    "sweden": "suecia",
    "norway": "noruega",
    "poland": "polonia",
    "czech republic": "czechia",
    "slovakia": "eslovaquia",
    "hungary": "hungria",
    "scotland": "escocia",
    "wales": "gales",
    "turkey": "turquia",
    "ukraine": "ukraine",
    "ecuador": "equador",
    "chile": "chile",
    "peru": "peru",
    "bolivia": "bolivia",
    "paraguay": "paraguai",
    "costa rica": "costa rica",
    "panama": "panama",
    "honduras": "honduras",
    "jamaica": "jamaica",
    "nova zelandia": "nova zelandia",
    "ivory coast": "costa do marfim",
    "cote d\'ivoire": "costa do marfim",
    "iran (islamic republic)": "iran",
    "saudi arabia": "arabia saudita",
    "south africa": "africa do sul",
    "ghana": "ghana",
    # ===== Clubes =====
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
}


# ======================= ESTILO =======================
def aplicar_estilo() -> None:
    st.markdown(
        """
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
        .chip-green {
            background: #dcfce7;
            color: #166534;
            border-color: #86efac;
        }
        .chip-red {
            background: #fee2e2;
            color: #991b1b;
            border-color: #fecaca;
        }
        .chip-blue {
            background: #dbeafe;
            color: #1e40af;
            border-color: #7dd3fc;
        }
        .chip-gray {
            background: #f1f5f9;
            color: #475569;
            border-color: #cbd5e1;
        }
        .chip-gold {
            background: #fef9c3;
            color: #713f12;
            border-color: #fde047;
        }
        .chip-purple {
            background: #ede9fe;
            color: #4c1d95;
            border-color: #a78bfa;
        }
        .chip-orange {
            background: #fff7ed;
            color: #9a3412;
            border-color: #fdba74;
        }
        .chip-teal {
            background: #ccfbf1;
            color: #134e4a;
            border-color: #5eead4;
        }
        button {
            border-radius: 8px !important;
            font-weight: 600 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ======================= TEMPO E FORMATAÇÃO =======================
def agora_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def formatar_data_brasil(dt: datetime) -> str:
    if TZ_BR is not None:
        return dt.astimezone(TZ_BR).strftime("%d/%m %H:%M")
    return dt.astimezone().strftime("%d/%m %H:%M")


def esc(valor: Any) -> str:
    return html.escape(str(valor or ""))


# ======================= BANCO DE DADOS =======================
def conectar_db() -> sqlite3.Connection:
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


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
            home_adv REAL,
            contexto TEXT,
            mercado_base TEXT,
            codigo_base TEXT,
            prob_base REAL,
            mercado_aprendido TEXT,
            codigo_aprendido TEXT,
            prob_aprendido REAL,
            ajuste_aplicado REAL,
            placar_previsto TEXT,
            escanteios_previstos TEXT,
            cartoes_previstos TEXT,
            home_score INTEGER,
            away_score INTEGER,
            acertou_base INTEGER,
            acertou_aprendido INTEGER,
            finalizado INTEGER DEFAULT 0,
            status_resultado TEXT,
            criado_em TEXT,
            atualizado_em TEXT,
            data_utc TEXT,
            # Novas colunas para apostas de valor
            odds_home REAL,
            odds_draw REAL,
            odds_away REAL,
            prob_implicita_home REAL,
            prob_implicita_draw REAL,
            prob_implicita_away REAL,
            ev_home REAL,
            ev_draw REAL,
            ev_away REAL,
            mercado_valor TEXT,
            kelly_fracao REAL
        )
        """
    )

    colunas_necessarias = [
        ("forca_home", "REAL"),
        ("forca_away", "REAL"),
        ("home_adv", "REAL"),
        ("contexto", "TEXT"),
        ("mercado_base", "TEXT"),
        ("codigo_base", "TEXT"),
        ("prob_base", "REAL"),
        ("mercado_aprendido", "TEXT"),
        ("codigo_aprendido", "TEXT"),
        ("prob_aprendido", "REAL"),
        ("ajuste_aplicado", "REAL"),
        ("placar_previsto", "TEXT"),
        ("escanteios_previstos", "TEXT"),
        ("cartoes_previstos", "TEXT"),
        ("home_score", "INTEGER"),
        ("away_score", "INTEGER"),
        ("acertou_base", "INTEGER"),
        ("acertou_aprendido", "INTEGER"),
        ("finalizado", "INTEGER DEFAULT 0"),
        ("status_resultado", "TEXT"),
        ("criado_em", "TEXT"),
        ("atualizado_em", "TEXT"),
        ("data_utc", "TEXT"),
        ("odds_home", "REAL"),
        ("odds_draw", "REAL"),
        ("odds_away", "REAL"),
        ("prob_implicita_home", "REAL"),
        ("prob_implicita_draw", "REAL"),
        ("prob_implicita_away", "REAL"),
        ("ev_home", "REAL"),
        ("ev_draw", "REAL"),
        ("ev_away", "REAL"),
        ("mercado_valor", "TEXT"),
        ("kelly_fracao", "REAL"),
    ]

    cur.execute("PRAGMA table_info(previsoes)")
    existentes = {row[1] for row in cur.fetchall()}

    for coluna, tipo in colunas_necessarias:
        if coluna not in existentes:
            cur.execute(f"ALTER TABLE previsoes ADD COLUMN {coluna} {tipo}")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_previsoes_game_id ON previsoes(game_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_previsoes_liga ON previsoes(liga_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_previsoes_finalizado ON previsoes(finalizado)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_previsoes_data_utc ON previsoes(data_utc)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_previsoes_liga_finalizado ON previsoes(liga_id, finalizado)")
    conn.commit()
    conn.close()


def ler_tabela(sql: str, params: tuple = ()) -> pd.DataFrame:
    conn = conectar_db()
    try:
        return pd.read_sql_query(sql, conn, params=params)
    except Exception as exc:
        st.error(f"Erro ao ler banco de dados: {exc}")
        return pd.DataFrame()
    finally:
        conn.close()


def executar(sql: str, params: tuple = ()) -> None:
    conn = conectar_db()
    try:
        conn.execute(sql, params)
        conn.commit()
    except Exception as exc:
        st.error(f"Erro ao executar SQL: {exc}")
    finally:
        conn.close()


# ======================= UTILITÁRIOS =======================
def normalizar(nome: str) -> str:
    nome = str(nome or "").strip().lower()
    nome = unicodedata.normalize("NFD", nome)
    nome = "".join(c for c in nome if unicodedata.category(c) != "Mn")
    nome = nome.replace("'", "").replace(".", "").replace(",", "")
    nome = re.sub(r"\b(fc|sc)\b$", "", nome).strip()
    return ALIASES.get(nome, nome)


def pct(valor: Any) -> str:
    try:
        return f"{float(valor) * 100:.1f}%"
    except Exception:
        return "0.0%"


def traduzir_mercado(mercado: str) -> str:
    traducoes = {
        "casa_ou_empate": "Casa ou Empate",
        "empate_ou_fora": "Empate ou Fora",
        "casa_vence": "Casa vence",
        "fora_vence": "Fora vence",
        "empate": "Empate",
        "over_1.5": "Over 1.5 Gols",
        "over_2.5": "Over 2.5 Gols",
        "ambos_marcam": "Ambos marcam",
        "home_win": "Casa Vence (1)",
        "draw": "Empate (X)",
        "away_win": "Fora Vence (2)",
    }
    m_lower = str(mercado or "").lower()
    return traducoes.get(m_lower, str(mercado or ""))


def parse_data_espn(valor: Any) -> Optional[datetime]:
    if not valor:
        return None
    try:
        dt = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def safe_int(valor: Any) -> Optional[int]:
    try:
        if valor is None:
            return None
        texto = str(valor).strip()
        if texto == "":
            return None
        return int(float(texto))
    except Exception:
        return None


def eh_copa_do_mundo(liga_id: str) -> bool:
    return liga_id == "fifa.world"


def info_liga(liga_id: str) -> dict:
    """Retorna metadados visuais e textuais de cada competição."""
    mapa = {
        "fifa.world": {
            "emoji": "🏆",
            "nome": "COPA DO MUNDO FIFA",
            "subtitulo": "Análise por força das seleções · Sede neutra · Modelo Poisson + ML",
            "header": "🌍 COPA DO MUNDO",
            "banner_bg": "linear-gradient(135deg, #1a3a1a 0%, #2d6a2d 50%, #1a3a1a 100%)",
            "banner_border": "#fde047",
            "banner_titulo_cor": "#fde047",
            "banner_sub_cor": "#bbf7d0",
            "chip_classe": "chip-gold",
            "chip_label": "🌍 Copa do Mundo",
            "label_rodada": "🏆 Jogos da Copa do Mundo",
            "aviso_vazio": "⚠️ Nenhum jogo da Copa do Mundo encontrado. A ESPN pode não ter dados fora do período da competição.",
        },
        "conmebol.libertadores": {
            "emoji": "🏆",
            "nome": "LIBERTADORES DA AMÉRICA",
            "subtitulo": "Maior competição de clubes sul-americanos · Modelo Poisson + ML",
            "header": "🌎 LIBERTADORES DA AMÉRICA",
            "banner_bg": "linear-gradient(135deg, #1e1b4b 0%, #3730a3 50%, #1e1b4b 100%)",
            "banner_border": "#a5b4fc",
            "banner_titulo_cor": "#e0e7ff",
            "banner_sub_cor": "#c7d2fe",
            "chip_classe": "chip-purple",
            "chip_label": "🌎 Libertadores",
            "label_rodada": "🌎 Jogos da Libertadores",
            "aviso_vazio": "⚠️ Nenhum jogo da Libertadores encontrado no momento.",
        },
        "conmebol.sudamericana": {
            "emoji": "🥈",
            "nome": "SUL-AMERICANA",
            "subtitulo": "Segunda competição de clubes da CONMEBOL · Modelo Poisson + ML",
            "header": "🌎 SUL-AMERICANA",
            "banner_bg": "linear-gradient(135deg, #1c1917 0%, #b45309 50%, #1c1917 100%)",
            "banner_border": "#fdba74",
            "banner_titulo_cor": "#fed7aa",
            "banner_sub_cor": "#fef3c7",
            "chip_classe": "chip-orange",
            "chip_label": "🌎 Sul-Americana",
            "label_rodada": "🌎 Jogos da Sul-Americana",
            "aviso_vazio": "⚠️ Nenhum jogo da Sul-Americana encontrado no momento.",
        },
        "uefa.champions": {
            "emoji": "⭐",
            "nome": "UEFA CHAMPIONS LEAGUE",
            "subtitulo": "Elite do futebol europeu · Modelo Poisson + ML",
            "header": "⭐ CHAMPIONS LEAGUE",
            "banner_bg": "linear-gradient(135deg, #0c1445 0%, #1e3a8a 50%, #0c1445 100%)",
            "banner_border": "#60a5fa",
            "banner_titulo_cor": "#bfdbfe",
            "banner_sub_cor": "#93c5fd",
            "chip_classe": "chip-blue",
            "chip_label": "⭐ Champions League",
            "label_rodada": "⭐ Jogos da Champions",
            "aviso_vazio": "⚠️ Nenhum jogo da Champions League encontrado no momento.",
        },
        "uefa.europa": {
            "emoji": "🟠",
            "nome": "UEFA EUROPA LEAGUE",
            "subtitulo": "Segunda competição de clubes da UEFA · Modelo Poisson + ML",
            "header": "🟠 EUROPA LEAGUE",
            "banner_bg": "linear-gradient(135deg, #1c0a00 0%, #c2410c 50%, #1c0a00 100%)",
            "banner_border": "#fb923c",
            "banner_titulo_cor": "#fed7aa",
            "banner_sub_cor": "#fef3c7",
            "chip_classe": "chip-orange",
            "chip_label": "🟠 Europa League",
            "label_rodada": "🟠 Jogos da Europa League",
            "aviso_vazio": "⚠️ Nenhum jogo da Europa League encontrado no momento.",
        },
        "bra.1": {
            "emoji": "🇧🇷",
            "nome": "BRASILEIRÃO SÉRIE A",
            "subtitulo": "Primeira divisão do futebol brasileiro",
            "header": "🇧🇷 BRASILEIRÃO S