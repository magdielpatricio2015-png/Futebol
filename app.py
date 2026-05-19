"""
Analisador Esportivo Pro 18 – app.py
====================================
Versão revisada com:
- Cache limpo antes de atualizar resultados manualmente.
- Timezone fixo America/Sao_Paulo.
- Consultas SQLite em lote para melhorar performance.
- Índices no banco para acelerar histórico e pendências.
- Métricas separadas: modelo base vs modelo aprendido.
- Modelo de Regressão Logística com mais features.
- Tratamento mais seguro de HTML vindo da API.
- Tratamento melhor de erros HTTP.
- Datas salvas em UTC.
- Persistência segura com UPSERT, sem apagar dados antigos.
"""

from __future__ import annotations

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
    menu_items={"About": "Analisador Esportivo Pro 18 - v2.1"},
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

ALIASES = {
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
            data_utc TEXT
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


# ======================= AVALIAÇÃO DE ACERTOS =======================
def avaliar_codigo(codigo: Any, home_score: Any, away_score: Any) -> Optional[int]:
    h = safe_int(home_score)
    a = safe_int(away_score)

    if h is None or a is None:
        return None

    codigo = str(codigo or "").strip().lower()
    total_gols = h + a

    regras = {
        "casa_ou_empate": h >= a,
        "empate_ou_fora": a >= h,
        "casa_vence": h > a,
        "fora_vence": a > h,
        "empate": h == a,
        "over_1.5": total_gols > 1.5,
        "over_2.5": total_gols > 2.5,
        "ambos_marcam": h > 0 and a > 0,
    }

    if codigo not in regras:
        return None

    return 1 if regras[codigo] else 0


def texto_status_acerto(acertou: Any) -> str:
    if pd.isna(acertou):
        return "Pendente"
    return "Acerto" if int(acertou) == 1 else "Erro"


def recalcular_acertos_banco() -> int:
    df = ler_tabela(
        """
        SELECT game_id, codigo_base, codigo_aprendido, home_score, away_score
        FROM previsoes
        WHERE finalizado = 1
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
        """
    )

    atualizados = 0

    for _, row in df.iterrows():
        acertou_base = avaliar_codigo(
            row.get("codigo_base"), row.get("home_score"), row.get("away_score")
        )
        acertou_aprendido = avaliar_codigo(
            row.get("codigo_aprendido"), row.get("home_score"), row.get("away_score")
        )

        if acertou_base is None and acertou_aprendido is None:
            continue

        status = texto_status_acerto(acertou_aprendido)
        executar(
            """
            UPDATE previsoes
            SET acertou_base = ?,
                acertou_aprendido = ?,
                status_resultado = ?,
                atualizado_em = ?
            WHERE game_id = ?
            """,
            (
                acertou_base,
                acertou_aprendido,
                status,
                agora_utc_iso(),
                str(row["game_id"]),
            ),
        )
        atualizados += 1

    return atualizados


# ======================= CHAMADAS À API =======================
@st.cache_data(ttl=60 * 10, show_spinner=False)
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

        except requests.RequestException:
            time.sleep(0.5 + tentativa * 0.5)
        except ValueError:
            return None
        except Exception:
            time.sleep(0.5 + tentativa * 0.5)

    return None


@st.cache_data(ttl=60 * 10, show_spinner=False)
def buscar_jogos_rodada(liga_id: str) -> pd.DataFrame:
    url = f"{ESPN_BASE}/{liga_id}/scoreboard"
    data = api_get_json(url, {"limit": 100})
    rows = []

    if not data:
        return pd.DataFrame(rows)

    for event in data.get("events", []):
        dt = parse_data_espn(event.get("date"))
        if not dt:
            continue

        comp = (event.get("competitions") or [{}])[0]

        home = None
        away = None
        h_score = None
        a_score = None

        for team in comp.get("competitors", []):
            name = team.get("team", {}).get("displayName")
            score = safe_int(team.get("score"))

            if team.get("homeAway") == "home":
                home = name
                h_score = score
            else:
                away = name
                a_score = score

        status = event.get("status", {}).get("type", {})
        completed = bool(status.get("completed"))

        rows.append(
            {
                "game_id": str(event.get("id")),
                "data_utc": dt.isoformat(),
                "data_local": formatar_data_brasil(dt),
                "home": str(home or ""),
                "away": str(away or ""),
                "home_score": h_score,
                "away_score": a_score,
                "completed": completed,
                "status_text": str(status.get("shortDetail", "")),
            }
        )

    if not rows:
        return pd.DataFrame(rows)

    return pd.DataFrame(rows).sort_values("data_utc").reset_index(drop=True)


# ======================= APRENDIZADO DE MÁQUINA =======================
def preparar_features_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["diff_forca"] = df["forca_home"].astype(float) - df["forca_away"].astype(float)
    df["soma_forca"] = df["forca_home"].astype(float) + df["forca_away"].astype(float)
    df["home_adv_x10"] = df["home_adv"].fillna(0.25).astype(float) * 10
    return df


def treinar_modelo_ml():
    if not SKLEARN_OK:
        return None, None, []

    df = ler_tabela(
        """
        SELECT forca_home, forca_away, home_adv, home_score, away_score
        FROM previsoes
        WHERE finalizado = 1
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
          AND forca_home IS NOT NULL
          AND forca_away IS NOT NULL
        """
    )

    if len(df) < MIN_JOGOS_TREINO:
        return None, None, []

    df = preparar_features_df(df)

    feature_cols = [
        "forca_home",
        "forca_away",
        "diff_forca",
        "soma_forca",
        "home_adv_x10",
    ]

    X = df[feature_cols].values

    # Mercado aprendido: casa não perde.
    y = (df["home_score"] >= df["away_score"]).astype(int).values

    if len(set(y)) < 2:
        return None, None, []

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = LogisticRegression(max_iter=1000)
    model.fit(X_scaled, y)

    return model, scaler, feature_cols


def poisson(k: int, lamb: float) -> float:
    lamb = max(float(lamb), 0.05)
    return math.exp(-lamb) * (lamb**k) / math.factorial(k)


def placar_mais_provavel(lh: float, la: float) -> str:
    melhor_h = 0
    melhor_a = 0
    melhor_prob = -1.0

    for h in range(MAX_GOLS + 1):
        for a in range(MAX_GOLS + 1):
            prob_placar = poisson(h, lh) * poisson(a, la)
            if prob_placar > melhor_prob:
                melhor_prob = prob_placar
                melhor_h = h
                melhor_a = a

    return f"{melhor_h} x {melhor_a}"


def montar_features_jogo(fh: float, fa: float, adv: float) -> list[float]:
    return [
        float(fh),
        float(fa),
        float(fh - fa),
        float(fh + fa),
        float(adv * 10),
    ]


def analisar_jogo(home: str, away: str, liga_id: str, model=None, scaler=None):
    nh = normalizar(home)
    na = normalizar(away)

    fh = float(FORCA_BASE.get(nh, 72.0))
    fa = float(FORCA_BASE.get(na, 70.0))

    adv = float(HOME_ADV_LIGA.get(liga_id, 0.25))
    diff = (fh + adv * 10) - fa

    lh = max(1.28 + diff / 34, 0.2)
    la = max(1.08 - diff / 40, 0.2)

    prob_h = sum(
        poisson(h, lh) * poisson(a, la)
        for h in range(MAX_GOLS + 1)
        for a in range(MAX_GOLS + 1)
        if h > a
    )
    prob_d = sum(
        poisson(h, lh) * poisson(a, la)
        for h in range(MAX_GOLS + 1)
        for a in range(MAX_GOLS + 1)
        if h == a
    )
    prob_a = sum(
        poisson(h, lh) * poisson(a, la)
        for h in range(MAX_GOLS + 1)
        for a in range(MAX_GOLS + 1)
        if h < a
    )

    total = prob_h + prob_d + prob_a

    if total > 0:
        prob_h = prob_h / total
        prob_d = prob_d / total
        prob_a = prob_a / total

    mercado_base = "casa_ou_empate" if prob_h >= prob_a else "empate_ou_fora"
    codigo_base = mercado_base
    prob_base = prob_h + prob_d if mercado_base == "casa_ou_empate" else prob_a + prob_d

    ajuste_ml = 0.0

    if model is not None and scaler is not None and SKLEARN_OK:
        features = np.array([montar_features_jogo(fh, fa, adv)])
        features_scaled = scaler.transform(features)
        prob_ml_casa_ou_empate = float(model.predict_proba(features_scaled)[0][1])

        prob_base_casa_ou_empate = prob_h + prob_d
        prob_final_casa_ou_empate = (prob_base_casa_ou_empate * 0.6) + (
            prob_ml_casa_ou_empate * 0.4
        )

        ajuste_ml = prob_final_casa_ou_empate - prob_base_casa_ou_empate

        if prob_final_casa_ou_empate >= 0.50:
            mercado_aprendido = "casa_ou_empate"
            codigo_aprendido = "casa_ou_empate"
            prob_aprendido = prob_final_casa_ou_empate
        else:
            mercado_aprendido = "empate_ou_fora"
            codigo_aprendido = "empate_ou_fora"
            prob_aprendido = 1 - prob_final_casa_ou_empate
    else:
        mercado_aprendido = mercado_base
        codigo_aprendido = codigo_base
        prob_aprendido = prob_base

    base_esc = 9.5
    base_cart = 4.2

    if "bra" in liga_id or "conmebol" in liga_id:
        base_cart += 1.2
        base_esc += 0.5

    escanteios = max(5.0, base_esc + (fh + fa - 140) / 20)
    cartoes = max(1.0, base_cart + (160 - fh - fa) / 30)

    placar = placar_mais_provavel(lh, la)

    return {
        "mercado_base": mercado_base,
        "codigo_base": codigo_base,
        "prob_base": float(prob_base),
        "mercado_aprendido": mercado_aprendido,
        "codigo_aprendido": codigo_aprendido,
        "prob_aprendido": float(prob_aprendido),
        "placar_previsto": placar,
        "escanteios_previstos": f"{escanteios:.1f}",
        "cartoes_previstos": f"{cartoes:.1f}",
        "forca_home": fh,
        "forca_away": fa,
        "home_adv": adv,
        "ajuste_aplicado": float(ajuste_ml),
    }


# ======================= PERSISTÊNCIA =======================
def salvar_previsao(
    game_id: Any,
    esporte: str,
    liga_id: str,
    liga_nome: str,
    data_jogo: str,
    home: str,
    away: str,
    analise: dict,
    data_utc: str,
    finalizado: int = 0,
    home_score: Optional[int] = None,
    away_score: Optional[int] = None,
) -> None:
    agora = agora_utc_iso()

    acertou_base = avaliar_codigo(
        analise.get("codigo_base"),
        home_score,
        away_score,
    )
    acertou_aprendido = avaliar_codigo(
        analise.get("codigo_aprendido"),
        home_score,
        away_score,
    )

    status_resultado = (
        texto_status_acerto(acertou_aprendido)
        if int(finalizado) == 1 and acertou_aprendido is not None
        else "Pendente"
    )

    executar(
        """
        INSERT INTO previsoes (
            game_id,
            esporte,
            liga_id,
            liga_nome,
            data_jogo,
            home,
            away,
            forca_home,
            forca_away,
            home_adv,
            mercado_base,
            codigo_base,
            prob_base,
            mercado_aprendido,
            codigo_aprendido,
            prob_aprendido,
            ajuste_aplicado,
            placar_previsto,
            escanteios_previstos,
            cartoes_previstos,
            home_score,
            away_score,
            acertou_base,
            acertou_aprendido,
            finalizado,
            status_resultado,
            criado_em,
            atualizado_em,
            data_utc
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(game_id) DO UPDATE SET
            esporte = excluded.esporte,
            liga_id = excluded.liga_id,
            liga_nome = excluded.liga_nome,
            data_jogo = excluded.data_jogo,
            home = excluded.home,
            away = excluded.away,
            forca_home = COALESCE(previsoes.forca_home, excluded.forca_home),
            forca_away = COALESCE(previsoes.forca_away, excluded.forca_away),
            home_adv = COALESCE(previsoes.home_adv, excluded.home_adv),
            mercado_base = COALESCE(previsoes.mercado_base, excluded.mercado_base),
            codigo_base = COALESCE(previsoes.codigo_base, excluded.codigo_base),
            prob_base = COALESCE(previsoes.prob_base, excluded.prob_base),
            mercado_aprendido = COALESCE(previsoes.mercado_aprendido, excluded.mercado_aprendido),
            codigo_aprendido = COALESCE(previsoes.codigo_aprendido, excluded.codigo_aprendido),
            prob_aprendido = COALESCE(previsoes.prob_aprendido, excluded.prob_aprendido),
            ajuste_aplicado = COALESCE(previsoes.ajuste_aplicado, excluded.ajuste_aplicado),
            placar_previsto = COALESCE(previsoes.placar_previsto, excluded.placar_previsto),
            escanteios_previstos = COALESCE(previsoes.escanteios_previstos, excluded.escanteios_previstos),
            cartoes_previstos = COALESCE(previsoes.cartoes_previstos, excluded.cartoes_previstos),
            home_score = COALESCE(excluded.home_score, previsoes.home_score),
            away_score = COALESCE(excluded.away_score, previsoes.away_score),
            acertou_base = COALESCE(excluded.acertou_base, previsoes.acertou_base),
            acertou_aprendido = COALESCE(excluded.acertou_aprendido, previsoes.acertou_aprendido),
            finalizado = CASE
                WHEN excluded.finalizado = 1 THEN 1
                ELSE previsoes.finalizado
            END,
            status_resultado = CASE
                WHEN excluded.finalizado = 1 THEN excluded.status_resultado
                ELSE COALESCE(previsoes.status_resultado, excluded.status_resultado)
            END,
            atualizado_em = excluded.atualizado_em,
            data_utc = excluded.data_utc
        """,
        (
            str(game_id),
            str(esporte),
            str(liga_id),
            str(liga_nome),
            str(data_jogo),
            str(home),
            str(away),
            float(analise["forca_home"]),
            float(analise["forca_away"]),
            float(analise["home_adv"]),
            str(analise["mercado_base"]),
            str(analise["codigo_base"]),
            float(analise["prob_base"]),
            str(analise["mercado_aprendido"]),
            str(analise["codigo_aprendido"]),
            float(analise["prob_aprendido"]),
            float(analise["ajuste_aplicado"]),
            str(analise["placar_previsto"]),
            str(analise["escanteios_previstos"]),
            str(analise["cartoes_previstos"]),
            home_score,
            away_score,
            acertou_base,
            acertou_aprendido,
            int(finalizado),
            status_resultado,
            agora,
            agora,
            str(data_utc),
        ),
    )


def atualizar_resultados_finalizados(liga_id_filtro: Optional[str] = None) -> int:
    if liga_id_filtro:
        pendentes = ler_tabela(
            """
            SELECT game_id, liga_id, codigo_base, codigo_aprendido
            FROM previsoes
            WHERE finalizado = 0 AND liga_id = ?
            """,
            (liga_id_filtro,),
        )
    else:
        pendentes = ler_tabela(
            """
            SELECT game_id, liga_id, codigo_base, codigo_aprendido
            FROM previsoes
            WHERE finalizado = 0
            """
        )

    if pendentes.empty:
        return 0

    atualizados = 0

    for liga_id in sorted(pendentes["liga_id"].dropna().unique()):
        url = f"{ESPN_BASE}/{liga_id}/scoreboard"
        data = api_get_json(url, {"limit": 100})

        if not data:
            continue

        eventos = {str(event.get("id")): event for event in data.get("events", [])}
        df_liga = pendentes[pendentes["liga_id"] == liga_id]

        for _, row in df_liga.iterrows():
            game_id = str(row["game_id"])
            event = eventos.get(game_id)

            if not event:
                continue

            status = event.get("status", {}).get("type", {})

            if not status.get("completed"):
                continue

            comp = (event.get("competitions") or [{}])[0]

            h_score = None
            a_score = None

            for team in comp.get("competitors", []):
                score = safe_int(team.get("score"))

                if team.get("homeAway") == "home":
                    h_score = score
                else:
                    a_score = score

            if h_score is None or a_score is None:
                continue

            acertou_base = avaliar_codigo(row.get("codigo_base"), h_score, a_score)
            acertou_aprendido = avaliar_codigo(
                row.get("codigo_aprendido"),
                h_score,
                a_score,
            )

            status_resultado = texto_status_acerto(acertou_aprendido)

            executar(
                """
                UPDATE previsoes
                SET finalizado = 1,
                    home_score = ?,
                    away_score = ?,
                    acertou_base = ?,
                    acertou_aprendido = ?,
                    status_resultado = ?,
                    atualizado_em = ?
                WHERE game_id = ?
                """,
                (
                    h_score,
                    a_score,
                    acertou_base,
                    acertou_aprendido,
                    status_resultado,
                    agora_utc_iso(),
                    game_id,
                ),
            )

            atualizados += 1

    return atualizados


def auto_atualizar_resultados(liga_id_filtro: Optional[str] = None) -> int:
    chave = f"ultima_atualizacao_resultados_{liga_id_filtro or 'todas'}"
    agora = time.time()
    ultima = st.session_state.get(chave, 0)

    if agora - ultima < AUTO_UPDATE_INTERVAL_SECONDS:
        return 0

    atualizados = atualizar_resultados_finalizados(liga_id_filtro)
    recalcular_acertos_banco()
    st.session_state[chave] = agora

    return atualizados


# ======================= MÉTRICAS =======================
def resumo_metricas() -> dict:
    df = ler_tabela(
        """
        SELECT *
        FROM previsoes
        WHERE finalizado = 1
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
        """
    )

    retorno_vazio = {
        "finalizados": 0,
        "acertos": 0,
        "erros": 0,
        "taxa": 0.0,
        "acertos_base": 0,
        "erros_base": 0,
        "taxa_base": 0.0,
    }

    if df.empty:
        return retorno_vazio

    validos_apr = df[df["acertou_aprendido"].notna()].copy()
    validos_base = df[df["acertou_base"].notna()].copy()

    acertos_apr = int((validos_apr["acertou_aprendido"].astype(int) == 1).sum()) if not validos_apr.empty else 0
    erros_apr = int((validos_apr["acertou_aprendido"].astype(int) == 0).sum()) if not validos_apr.empty else 0
    total_apr = acertos_apr + erros_apr

    acertos_base = int((validos_base["acertou_base"].astype(int) == 1).sum()) if not validos_base.empty else 0
    erros_base = int((validos_base["acertou_base"].astype(int) == 0).sum()) if not validos_base.empty else 0
    total_base = acertos_base + erros_base

    return {
        "finalizados": int(len(df)),
        "acertos": acertos_apr,
        "erros": erros_apr,
        "taxa": acertos_apr / total_apr if total_apr else 0.0,
        "acertos_base": acertos_base,
        "erros_base": erros_base,
        "taxa_base": acertos_base / total_base if total_base else 0.0,
    }


def resumo_por_mercado() -> pd.DataFrame:
    df = ler_tabela(
        """
        SELECT mercado_aprendido, acertou_aprendido
        FROM previsoes
        WHERE finalizado = 1
          AND acertou_aprendido IS NOT NULL
        """
    )

    if df.empty:
        return pd.DataFrame()

    df["mercado"] = df["mercado_aprendido"].apply(traduzir_mercado)
    agrupado = (
        df.groupby("mercado")
        .agg(
            jogos=("acertou_aprendido", "count"),
            acertos=("acertou_aprendido", "sum"),
        )
        .reset_index()
    )
    agrupado["erros"] = agrupado["jogos"] - agrupado["acertos"]
    agrupado["taxa"] = agrupado["acertos"] / agrupado["jogos"]
    agrupado["taxa"] = agrupado["taxa"].apply(pct)
    return agrupado.sort_values("jogos", ascending=False)


# ======================= HELPERS DE TELA =======================
def limpar_cache_e_atualizar(liga_id: Optional[str] = None) -> int:
    st.cache_data.clear()
    atualizados = atualizar_resultados_finalizados(liga_id)
    recalcular_acertos_banco()
    return atualizados


def carregar_previsoes_da_rodada(df_rodada: pd.DataFrame) -> dict[str, pd.Series]:
    if df_rodada.empty:
        return {}

    game_ids = tuple(df_rodada["game_id"].astype(str).tolist())
    placeholders = ",".join(["?"] * len(game_ids))

    df_prev_all = ler_tabela(
        f"SELECT * FROM previsoes WHERE game_id IN ({placeholders})",
        game_ids,
    )

    if df_prev_all.empty:
        return {}

    return {
        str(row["game_id"]): row
        for _, row in df_prev_all.iterrows()
    }


def salvar_e_ler_previsao(
    jogo: pd.Series,
    liga_id: str,
    liga_nome: str,
    model: Any,
    scaler: Any,
) -> Optional[pd.Series]:
    analise = analisar_jogo(
        str(jogo["home"]),
        str(jogo["away"]),
        liga_id,
        model,
        scaler,
    )

    salvar_previsao(
        game_id=str(jogo["game_id"]),
        esporte="futebol",
        liga_id=liga_id,
        liga_nome=liga_nome,
        data_jogo=str(jogo["data_utc"])[:10],
        home=str(jogo["home"]),
        away=str(jogo["away"]),
        analise=analise,
        data_utc=str(jogo["data_utc"]),
        finalizado=1 if bool(jogo["completed"]) else 0,
        home_score=jogo["home_score"],
        away_score=jogo["away_score"],
    )

    db_prev = ler_tabela("SELECT * FROM previsoes WHERE game_id = ?", (str(jogo["game_id"]),))
    if db_prev.empty:
        return None
    return db_prev.iloc[0]


# ======================= TELAS =======================
def tela_futebol() -> None:
    st.header("⚽ FUTEBOL COM APRENDIZADO")

    liga_nome = st.selectbox("Escolha a Liga", list(LIGAS.keys()))
    liga_id = LIGAS[liga_nome]

    atualizados_auto = auto_atualizar_resultados(liga_id)

    if atualizados_auto > 0:
        st.success(f"✅ {atualizados_auto} resultado(s) atualizado(s) automaticamente.")

    col_a, col_b = st.columns([1, 1])

    with col_a:
        if st.button("🔃 Atualizar Rodada e Resultados", use_container_width=True):
            atualizados = limpar_cache_e_atualizar(liga_id)

            if atualizados:
                st.success(f"✅ {atualizados} resultado(s) finalizado(s) salvo(s).")
            else:
                st.info("Nenhum novo resultado finalizado encontrado.")

            st.rerun()

    with col_b:
        if st.button("🧮 Recalcular Acertos/Erros", use_container_width=True):
            total = recalcular_acertos_banco()
            st.success(f"✅ Acertos/erros recalculados em {total} jogo(s).")
            st.rerun()

    with st.spinner("Carregando inteligência..."):
        model, scaler, feature_cols = treinar_modelo_ml()

    if model is not None:
        st.success("🤖 Modelo de Aprendizado Ativo treinado com seu histórico.")
        with st.expander("Detalhes do modelo"):
            st.write(f"Features usadas: {', '.join(feature_cols)}")
            st.caption("O modelo aprendido combina regressão logística com o modelo base Poisson.")
    else:
        st.info(
            f"📈 Sistema em fase de coleta: mínimo de {MIN_JOGOS_TREINO} jogos finalizados "
            "com placar e variedade suficiente de resultados."
        )

    metricas = resumo_metricas()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Jogos finalizados", metricas["finalizados"])
    c2.metric("Acertos aprendidos", metricas["acertos"])
    c3.metric("Erros aprendidos", metricas["erros"])
    c4.metric("Taxa aprendida", pct(metricas["taxa"]))
    c5.metric("Taxa base", pct(metricas["taxa_base"]))

    df_rodada = buscar_jogos_rodada(liga_id)

    if df_rodada.empty:
        st.warning("Nenhum jogo encontrado para esta liga no momento.")
        return

    st.markdown(f"### 📅 Jogos da Rodada ({len(df_rodada)})")

    prev_por_game = carregar_previsoes_da_rodada(df_rodada)

    for _, jogo in df_rodada.iterrows():
        game_id = str(jogo["game_id"])
        prev = prev_por_game.get(game_id)

        if prev is None:
            prev = salvar_e_ler_previsao(jogo, liga_id, liga_nome, model, scaler)
            if prev is None:
                continue

        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 2, 1.5])

            with col1:
                st.markdown(
                    f"**{esc(jogo['data_local'])}**<br>"
                    f"**{esc(jogo['home'])}** vs **{esc(jogo['away'])}**",
                    unsafe_allow_html=True,
                )

                if bool(jogo["completed"]):
                    st.markdown(
                        f"<span class='chip chip-gray'>Fim: {esc(jogo['home_score'])} x {esc(jogo['away_score'])}</span>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f"<span class='chip chip-blue'>{esc(jogo['status_text'])}</span>",
                        unsafe_allow_html=True,
                    )

            with col2:
                mercado_claro = traduzir_mercado(prev.get("mercado_aprendido", ""))
                mercado_base = traduzir_mercado(prev.get("mercado_base", ""))

                st.markdown(
                    f"<span style='color: #4f46e5; font-weight: 700; font-size: 1.1rem;'>"
                    f"{esc(mercado_claro)}</span>",
                    unsafe_allow_html=True,
                )
                st.caption(f"Base: {mercado_base} • {pct(prev.get('prob_base', 0))}")
                st.markdown(f"🎯 Placar provável: **{esc(prev.get('placar_previsto', '-'))}**")
                st.markdown(
                    f"🚩 Escanteios: **{esc(prev.get('escanteios_previstos', '-'))}** "
                    f"| 🟨 Cartões: **{esc(prev.get('cartoes_previstos', '-'))}**"
                )

                if int(prev.get("finalizado") or 0) == 1:
                    acertou = prev.get("acertou_aprendido")
                    if pd.notna(acertou) and int(acertou) == 1:
                        st.markdown(
                            "<span class='chip chip-green'>✅ Acerto salvo</span>",
                            unsafe_allow_html=True,
                        )
                    elif pd.notna(acertou) and int(acertou) == 0:
                        st.markdown(
                            "<span class='chip chip-red'>❌ Erro salvo</span>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            "<span class='chip chip-gray'>Resultado salvo, avaliação pendente</span>",
                            unsafe_allow_html=True,
                        )

            with col3:
                st.markdown(
                    f"<span style='color: #059669; font-weight: 800; font-size: 1.4rem;'>"
                    f"{pct(prev.get('prob_aprendido', 0))}</span>",
                    unsafe_allow_html=True,
                )

                ajuste = prev.get("ajuste_aplicado", 0)
                try:
                    ajuste = float(ajuste)
                except Exception:
                    ajuste = 0.0

                if ajuste != 0:
                    cor = "blue" if ajuste > 0 else "red"
                    st.caption(f"Ajuste ML: :{cor}[{ajuste * 100:+.1f}%]")
                else:
                    st.caption("Confiança base")

                try:
                    fh = float(prev.get("forca_home", 0))
                    fa = float(prev.get("forca_away", 0))
                    st.caption(f"Forças: casa {fh:.0f} | fora {fa:.0f}")
                except Exception:
                    pass


def tela_historico() -> None:
    st.header("📋 HISTÓRICO DE APRENDIZADO")

    atualizados_auto = auto_atualizar_resultados()

    if atualizados_auto > 0:
        st.success(f"✅ {atualizados_auto} resultado(s) atualizado(s) automaticamente.")

    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("🔃 Atualizar resultados pendentes", use_container_width=True):
            atualizados = limpar_cache_e_atualizar()

            if atualizados:
                st.success(f"✅ {atualizados} resultado(s) atualizado(s).")
            else:
                st.info("Nenhum novo resultado encontrado.")

            st.rerun()

    with col2:
        if st.button("🧮 Recalcular todos os acertos/erros", use_container_width=True):
            total = recalcular_acertos_banco()
            st.success(f"✅ {total} registro(s) recalculado(s).")
            st.rerun()

    metricas = resumo_metricas()

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Finalizados", metricas["finalizados"])
    m2.metric("Acertos aprendidos", metricas["acertos"])
    m3.metric("Erros aprendidos", metricas["erros"])
    m4.metric("Taxa aprendida", pct(metricas["taxa"]))
    m5.metric("Taxa base", pct(metricas["taxa_base"]))

    with st.expander("Resumo por mercado"):
        df_mercados = resumo_por_mercado()
        if df_mercados.empty:
            st.info("Ainda não há dados finalizados por mercado.")
        else:
            st.dataframe(df_mercados, use_container_width=True, hide_index=True)

    df_hist = ler_tabela("SELECT * FROM previsoes ORDER BY id DESC LIMIT 300")

    if df_hist.empty:
        st.info("O histórico aparecerá aqui conforme você visualizar os jogos.")
        return

    colunas_preferidas = [
        "id",
        "liga_nome",
        "data_jogo",
        "home",
        "away",
        "mercado_base",
        "prob_base",
        "mercado_aprendido",
        "prob_aprendido",
        "placar_previsto",
        "home_score",
        "away_score",
        "finalizado",
        "acertou_base",
        "acertou_aprendido",
        "status_resultado",
        "atualizado_em",
    ]

    colunas_existentes = [c for c in colunas_preferidas if c in df_hist.columns]
    df_view = df_hist[colunas_existentes].copy()

    for coluna in ["mercado_base", "mercado_aprendido"]:
        if coluna in df_view.columns:
            df_view[coluna] = df_view[coluna].apply(traduzir_mercado)

    for coluna in ["prob_base", "prob_aprendido"]:
        if coluna in df_view.columns:
            df_view[coluna] = df_view[coluna].apply(pct)

    for coluna in ["acertou_base", "acertou_aprendido"]:
        if coluna in df_view.columns:
            df_view[coluna] = df_view[coluna].apply(texto_status_acerto)

    st.dataframe(df_view, use_container_width=True, hide_index=True)


def tela_download() -> None:
    st.header("💾 ÁREA DE DOWNLOAD")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 Dados do Modelo")
        df_full = ler_tabela("SELECT * FROM previsoes ORDER BY id DESC")

        if not df_full.empty:
            csv = df_full.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Baixar Histórico CSV",
                csv,
                "historico_analisador.csv",
                "text/csv",
                use_container_width=True,
            )
        else:
            st.warning("Sem dados para baixar.")

    with col2:
        st.subheader("💻 Código Fonte")
        try:
            codigo = Path(__file__).read_text(encoding="utf-8")

            st.download_button(
                "Baixar app.py",
                codigo,
                "app.py",
                "text/plain",
                use_container_width=True,
            )
        except Exception as exc:
            st.error(f"Não foi possível ler o arquivo do código: {exc}")


def main() -> None:
    aplicar_estilo()
    init_db()

    st.sidebar.markdown(
        "<h1 style='text-align: center; color: #6366f1;'>⚽ PRO 18</h1>",
        unsafe_allow_html=True,
    )

    st.sidebar.caption("v2.1 • Métricas base vs aprendida")

    pg = st.sidebar.radio(
        "Navegação",
        ["⚽ Futebol", "📋 Histórico", "💾 Download"],
    )

    st.sidebar.divider()
    st.sidebar.caption(
        "Uso recomendado: trate as previsões como apoio estatístico experimental, "
        "não como garantia de resultado."
    )

    if pg == "⚽ Futebol":
        tela_futebol()
    elif pg == "📋 Histórico":
        tela_historico()
    else:
        tela_download()


if __name__ == "__main__":
    main()