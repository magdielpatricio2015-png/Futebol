import math
import os
import re
import sqlite3
import unicodedata
from datetime import datetime, timedelta

import pandas as pd
import requests
import streamlit as st


st.set_page_config(
    page_title="Analisador Esportivo Pro 14.0",
    page_icon="⚽",
    layout="wide",
)

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
HEADERS = {"User-Agent": "AnalisadorEsportivoPro/14.0"}

MAX_GOLS = 10
RETRIES = 2
DEFAULT_HOME_ADV = 0.25
DB_PATH = "data/modelo.db"

MIN_JOGOS_PARA_APRENDER = 5


LIGAS = {
    "Brasileirão Série A": "bra.1",
    "Brasileirão Série B": "bra.2",
    "Copa do Brasil": "bra.copa_do_brasil",
    "Libertadores": "conmebol.libertadores",
    "Sul-Americana": "conmebol.sudamericana",
    "Premier League": "eng.1",
    "La Liga": "esp.1",
    "Serie A Itália": "ita.1",
    "Bundesliga": "ger.1",
    "Ligue 1": "fra.1",
    "Champions League": "uefa.champions",
    "Europa League": "uefa.europa",
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
}


CLASSICOS = {
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


# ============================================================
# BANCO
# ============================================================

def conectar_db():
    os.makedirs("data", exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = conectar_db()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS previsoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT UNIQUE,
            liga_id TEXT,
            liga_nome TEXT,
            data_jogo TEXT,
            home TEXT,
            away TEXT,
            mercado_base TEXT,
            prob_base REAL,
            mercado_aprendido TEXT,
            prob_aprendido REAL,
            ajuste REAL,
            confianca TEXT,
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
        CREATE TABLE IF NOT EXISTS ajustes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chave TEXT UNIQUE,
            fator REAL DEFAULT 0,
            jogos INTEGER DEFAULT 0,
            acertos INTEGER DEFAULT 0,
            atualizado_em TEXT
        )
        """
    )

    conn.commit()
    conn.close()


def salvar_previsao(jogo, liga_nome, base, aprendido, placar_previsto):
    mercado_base, codigo_base, prob_base = base
    mercado_ap, codigo_ap, prob_ap, fator, prob_original = aprendido

    conn = conectar_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR IGNORE INTO previsoes (
            game_id, liga_id, liga_nome, data_jogo, home, away,
            mercado_base, prob_base,
            mercado_aprendido, prob_aprendido, ajuste,
            confianca, placar_previsto, finalizado, criado_em
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            jogo["id"],
            jogo["liga"],
            liga_nome,
            jogo["data"].isoformat() if jogo["data"] else "",
            jogo["home"],
            jogo["away"],
            mercado_base,
            float(prob_base),
            mercado_ap,
            float(prob_ap),
            float(fator),
            nivel_confianca(prob_ap),
            placar_previsto,
            0,
            datetime.now().isoformat(),
        ),
    )

    conn.commit()
    conn.close()


def atualizar_resultado(jogo):
    conn = conectar_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT mercado_base, mercado_aprendido
        FROM previsoes
        WHERE game_id = ?
        """,
        (jogo["id"],),
    )

    row = cur.fetchone()

    if not row:
        conn.close()
        return

    mercado_base, mercado_ap = row

    acertou_base = int(verificar_acerto(mercado_base, jogo["home_score"], jogo["away_score"]))
    acertou_ap = int(verificar_acerto(mercado_ap, jogo["home_score"], jogo["away_score"]))

    cur.execute(
        """
        UPDATE previsoes
        SET home_score = ?,
            away_score = ?,
            acertou_base = ?,
            acertou_aprendido = ?,
            finalizado = 1
        WHERE game_id = ?
        """,
        (
            jogo["home_score"],
            jogo["away_score"],
            acertou_base,
            acertou_ap,
            jogo["id"],
        ),
    )

    conn.commit()
    conn.close()


def carregar_previsoes():
    conn = conectar_db()
    df = pd.read_sql_query("SELECT * FROM previsoes ORDER BY id DESC", conn)
    conn.close()
    return df


def carregar_ajustes():
    conn = conectar_db()
    df = pd.read_sql_query("SELECT * FROM ajustes ORDER BY jogos DESC", conn)
    conn.close()
    return df


def salvar_ajuste(chave, fator, jogos, acertos):
    conn = conectar_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO ajustes (chave, fator, jogos, acertos, atualizado_em)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(chave) DO UPDATE SET
            fator = excluded.fator,
            jogos = excluded.jogos,
            acertos = excluded.acertos,
            atualizado_em = excluded.atualizado_em
        """,
        (
            chave,
            float(fator),
            int(jogos),
            int(acertos),
            datetime.now().isoformat(),
        ),
    )

    conn.commit()
    conn.close()


# ============================================================
# UTILITÁRIOS
# ============================================================

def nome_limpo(nome):
    return " ".join(str(nome or "").strip().split())


def normalizar(nome):
    nome = nome_limpo(nome).lower()
    nome = unicodedata.normalize("NFKD", nome)
    nome = "".join(c for c in nome if not unicodedata.combining(c))
    nome = re.sub(r"\b(fc|cf|sc|afc|ec)\b", "", nome)
    nome = re.sub(r"[^a-z0-9\s\-]", "", nome)
    nome = re.sub(r"\s+", " ", nome).strip()
    return ALIASES.get(nome, nome)


def parse_dt(valor):
    if not valor:
        return None

    try:
        return datetime.fromisoformat(
            valor.replace("Z", "+00:00")
        ).astimezone().replace(tzinfo=None)
    except Exception:
        return None


def pct(x):
    return f"{100 * float(x):.1f}%"


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def poisson_pmf(k, media):
    media = max(0.03, float(media))
    return math.exp(-media) * (media ** k) / math.factorial(k)


def odd_justa(prob):
    return 1 / max(prob, 0.0001)


def forca_time(nome):
    return FORCA_BASE.get(normalizar(nome), 70)


def eh_classico(home, away):
    return tuple(sorted([normalizar(home), normalizar(away)])) in CLASSICOS


def nivel_confianca(prob):
    if prob >= 0.72:
        return "ALTA"
    if prob >= 0.58:
        return "MÉDIA"
    return "BAIXA"


def status_label(jogo):
    if jogo["em_jogo"]:
        return "🔴 Ao vivo"
    if jogo["finalizado"]:
        return "✅ Finalizado"
    if jogo["futuro"]:
        return "🕒 Futuro"
    return jogo["status"] or "Status não informado"


# ============================================================
# API ESPN
# ============================================================

def fetch_with_retry(url, params=None, retries=RETRIES):
    ultimo_erro = ""

    for _ in range(retries):
        try:
            resp = requests.get(
                url,
                params=params or {},
                headers=HEADERS,
                timeout=12,
            )
            resp.raise_for_status()
            return resp.json(), ""
        except requests.RequestException as exc:
            ultimo_erro = f"Erro ESPN: {exc}"

    return {}, ultimo_erro


@st.cache_data(ttl=240, show_spinner=False)
def buscar_scoreboard(liga_id, data_iso=None):
    params = {"limit": 300}

    if data_iso:
        params["dates"] = data_iso.replace("-", "")

    return fetch_with_retry(f"{ESPN_BASE}/{liga_id}/scoreboard", params)


def extrair_jogos(payload, liga_id):
    jogos = []

    for event in payload.get("events", []) or []:
        comps = event.get("competitions") or []

        if not comps:
            continue

        comp = comps[0]
        competidores = comp.get("competitors") or []

        if len(competidores) < 2:
            continue

        home = next(
            (c for c in competidores if c.get("homeAway") == "home"),
            competidores[0],
        )

        away = next(
            (c for c in competidores if c.get("homeAway") == "away"),
            competidores[1],
        )

        status_raw = event.get("status") or {}
        status_type = status_raw.get("type", {})

        def placar(c):
            try:
                return int(float(c.get("score", 0)))
            except Exception:
                return 0

        jogos.append(
            {
                "id": str(event.get("id", "")),
                "liga": liga_id,
                "home": nome_limpo(home.get("team", {}).get("displayName", "Casa")),
                "away": nome_limpo(away.get("team", {}).get("displayName", "Fora")),
                "home_score": placar(home),
                "away_score": placar(away),
                "data": parse_dt(event.get("date")),
                "status": status_type.get("description", ""),
                "estado": status_type.get("state", ""),
                "em_jogo": status_type.get("state") == "in",
                "finalizado": status_type.get("state") == "post",
                "futuro": status_type.get("state") == "pre",
            }
        )

    return jogos


def buscar_jogos_ultimas_24h():
    agora = datetime.now()
    datas = {
        (agora - timedelta(days=1)).date().isoformat(),
        agora.date().isoformat(),
    }

    todos = []

    for liga_nome, liga_id in LIGAS.items():
        for data_iso in datas:
            payload, erro = buscar_scoreboard(liga_id, data_iso)

            if erro:
                continue

            jogos = extrair_jogos(payload, liga_id)

            for jogo in jogos:
                jogo["liga_nome"] = liga_nome

                if jogo["data"] and agora - timedelta(hours=24) <= jogo["data"] <= agora:
                    todos.append(jogo)

    return todos


# ============================================================
# MODELO
# ============================================================

def calcular_probabilidades(home, away):
    fh = forca_time(home)
    fa = forca_time(away)
    diff = fh - fa

    media_home = 1.4 + (diff * 0.02) + DEFAULT_HOME_ADV
    media_away = 1.1 - (diff * 0.015)

    if eh_classico(home, away):
        media_home *= 0.95
        media_away *= 0.98

    media_home = clamp(media_home, 0.2, 4.0)
    media_away = clamp(media_away, 0.2, 4.0)

    p_home = p_draw = p_away = 0
    p_over15 = p_over25 = p_over35 = p_under25 = p_btts = 0

    placares = []

    for gh in range(MAX_GOLS + 1):
        for ga in range(MAX_GOLS + 1):
            p = poisson_pmf(gh, media_home) * poisson_pmf(ga, media_away)
            total = gh + ga

            placares.append((gh, ga, p))

            if gh > ga:
                p_home += p
            elif gh == ga:
                p_draw += p
            else:
                p_away += p

            if total >= 2:
                p_over15 += p
            if total >= 3:
                p_over25 += p
            if total >= 4:
                p_over35 += p
            if total <= 2:
                p_under25 += p
            if gh > 0 and ga > 0:
                p_btts += p

    placares = sorted(placares, key=lambda x: x[2], reverse=True)

    return {
        "home": clamp(p_home, 0, 1),
        "draw": clamp(p_draw, 0, 1),
        "away": clamp(p_away, 0, 1),
        "over15": clamp(p_over15, 0, 1),
        "over25": clamp(p_over25, 0, 1),
        "over35": clamp(p_over35, 0, 1),
        "under25": clamp(p_under25, 0, 1),
        "btts": clamp(p_btts, 0, 1),
        "dupla_1x": clamp(p_home + p_draw, 0, 1),
        "dupla_x2": clamp(p_draw + p_away, 0, 1),
        "dupla_12": clamp(p_home + p_away, 0, 1),
        "media_home": media_home,
        "media_away": media_away,
        "forca_home": fh,
        "forca_away": fa,
        "placares": placares[:5],
    }


def mercados_disponiveis(probs, home, away):
    return [
        (f"{home} vence", "home", probs["home"]),
        ("Empate", "draw", probs["draw"]),
        (f"{away} vence", "away", probs["away"]),
        ("Dupla chance 1X", "dupla_1x", probs["dupla_1x"]),
        ("Dupla chance X2", "dupla_x2", probs["dupla_x2"]),
        ("Dupla chance 12", "dupla_12", probs["dupla_12"]),
        ("Over 1.5 gols", "over15", probs["over15"]),
        ("Over 2.5 gols", "over25", probs["over25"]),
        ("Under 2.5 gols", "under25", probs["under25"]),
        ("Ambos marcam", "btts", probs["btts"]),
    ]


def melhor_mercado_base(probs, home, away):
    return sorted(
        mercados_disponiveis(probs, home, away),
        key=lambda x: x[2],
        reverse=True,
    )[0]


def obter_fator_aprendizado(liga_id, codigo):
    conn = conectar_db()
    cur = conn.cursor()

    fator = 0.0

    for chave in [f"mercado:{codigo}", f"liga:{liga_id}|mercado:{codigo}"]:
        cur.execute(
            "SELECT fator, jogos FROM ajustes WHERE chave = ?",
            (chave,),
        )

        row = cur.fetchone()

        if row:
            fator_row, jogos = row

            if int(jogos) >= MIN_JOGOS_PARA_APRENDER:
                fator += float(fator_row)

    conn.close()
    return clamp(fator, -0.12, 0.12)


def melhor_mercado_aprendido(probs, jogo):
    mercados = mercados_disponiveis(probs, jogo["home"], jogo["