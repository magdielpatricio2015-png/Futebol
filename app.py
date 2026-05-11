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
    page_title="Analisador Esportivo Pro Learning",
    page_icon="⚽",
    layout="wide",
)

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
HEADERS = {"User-Agent": "AnalisadorEsportivoPro/16.1"}
DB_PATH = "data/modelo_v15.db"

MAX_GOLS = 10
RETRIES = 2
DEFAULT_HOME_ADV = 0.25
MIN_JOGOS_TREINO = 20

try:
    cache_streamlit = st.cache_data
except AttributeError:
    def cache_streamlit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

LIGAS = {
    "Brasileirão Série A": "bra.1",
    "Brasileirão Série B": "bra.2",
    "Premier League": "eng.1",
    "La Liga": "esp.1",
    "Serie A Itália": "ita.1",
    "Bundesliga": "ger.1",
    "Ligue 1": "fra.1",
    "Champions League": "uefa.champions",
    "Europa League": "uefa.europa",
    "Libertadores": "conmebol.libertadores",
    "Sul-Americana": "conmebol.sudamericana",
}

TENIS_LIGAS = {
    "ATP": "atp",
    "WTA": "wta",
}

FORCA_TENIS = {
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


def aplicar_estilo():
    st.markdown(
        """
        <style>
        :root {
            --bg-soft: #f8fafc;
            --border: #e5e7eb;
            --text-muted: #64748b;
        }
        .block-container { padding-top: .7rem; max-width: 1220px; }
        h1 { font-size: 1.9rem !important; margin-bottom: .1rem !important; }
        h2, h3 { letter-spacing: -.01em !important; }
        [data-testid="stHeader"] { height: 2.4rem; }
        [data-testid="stToolbar"] { display: none; }
        section[data-testid="stSidebar"] { background: var(--bg-soft); }
        div[data-testid="stMetric"] {
            background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: .65rem .75rem;
            box-shadow: 0 1px 2px rgba(15, 23, 42, .04);
        }
        div[data-testid="stMetricValue"] { font-size: 1.08rem !important; }
        div[data-testid="stMetricDelta"] { font-size: .75rem !important; }
        div[data-testid="stAlert"] { border-radius: 12px; padding: .65rem .85rem; }

        .hero {
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 1rem 1.1rem;
            margin: .25rem 0 .8rem 0;
            background:
                radial-gradient(circle at top left, rgba(59, 130, 246, .14), transparent 28%),
                linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
            box-shadow: 0 10px 22px rgba(15, 23, 42, .06);
        }
        .hero-title { font-size: 1.05rem; font-weight: 800; margin-bottom: .25rem; }
        .hero-text { color: var(--text-muted); font-size: .92rem; }

        .pro-card {
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: .85rem .95rem;
            background: #ffffff;
            margin: .7rem 0 .45rem 0;
            box-shadow: 0 6px 16px rgba(15, 23, 42, .045);
        }
        .pro-card h3 { margin-bottom: .4rem !important; }
        .pro-chip {
            display: inline-block;
            border: 1px solid var(--border);
            border-radius: 999px;
            padding: .16rem .55rem;
            margin: .12rem .25rem .12rem 0;
            font-size: .78rem;
            background: var(--bg-soft);
            color: #334155;
        }
        .learn-box {
            border-left: 4px solid #3b82f6;
            border-radius: 12px;
            padding: .75rem .9rem;
            background: #eff6ff;
            margin: .6rem 0;
            color: #1e3a8a;
        }
        .mobile-filter { display: none; }

        @media (max-width: 640px) {
            .block-container { padding: .35rem .55rem .8rem .55rem; }
            [data-testid="stHeader"] { height: 1.6rem; }
            h1 { font-size: 1.25rem !important; line-height: 1.2 !important; }
            h2 { font-size: 1.08rem !important; }
            h3 { font-size: 1rem !important; }
            p, div, span { font-size: .9rem; }
            div[data-testid="stMetric"] { padding: .42rem .5rem; border-radius: 12px; }
            div[data-testid="stMetricValue"] { font-size: .95rem !important; }
            .pro-card { padding: .65rem .7rem; border-radius: 14px; }
            .hero { padding: .75rem .8rem; border-radius: 14px; }
            .mobile-filter {
                display: block;
                border: 1px solid var(--border);
                border-radius: 12px;
                padding: .6rem .7rem;
                background: #ffffff;
                margin: .35rem 0 .6rem 0;
            }
            section[data-testid="stSidebar"] { min-width: 15rem !important; }
            div[data-testid="column"] { min-width: 0 !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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
        CREATE TABLE IF NOT EXISTS ajustes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chave TEXT UNIQUE,
            fator REAL DEFAULT 0,
            jogos INTEGER DEFAULT 0,
            acertos INTEGER DEFAULT 0,
            taxa REAL DEFAULT 0,
            atualizado_em TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tenis_historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT UNIQUE,
            circuito TEXT,
            torneio TEXT,
            data_jogo TEXT,
            jogador1 TEXT,
            jogador2 TEXT,
            mercado TEXT,
            codigo TEXT,
            prob_base REAL,
            prob_aprendida REAL,
            ajuste_aplicado REAL,
            placar TEXT,
            vencedor TEXT,
            acertou INTEGER,
            finalizado INTEGER DEFAULT 0,
            criado_em TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def ler_tabela(sql):
    conn = conectar_db()
    try:
        return pd.read_sql_query(sql, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


def salvar_ajuste(chave, fator, jogos, acertos):
    taxa = acertos / jogos if jogos else 0
    conn = conectar_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO ajustes (chave, fator, jogos, acertos, taxa, atualizado_em)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(chave) DO UPDATE SET
            fator = excluded.fator,
            jogos = excluded.jogos,
            acertos = excluded.acertos,
            taxa = excluded.taxa,
            atualizado_em = excluded.atualizado_em
        """,
        (chave, float(fator), int(jogos), int(acertos), float(taxa), datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


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
        return datetime.fromisoformat(valor.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
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
    return 1 / max(float(prob), 0.0001)


def forca_time(nome):
    return FORCA_BASE.get(normalizar(nome), 70)


def forca_jogador(nome):
    return FORCA_TENIS.get(normalizar(nome), 70)


def eh_classico(home, away):
    return tuple(sorted([normalizar(home), normalizar(away)])) in CLASSICOS


def status_label(jogo):
    if jogo["em_jogo"]:
        return "Ao vivo"
    if jogo["finalizado"]:
        return "Finalizado"
    if jogo["futuro"]:
        return "Futuro"
    return jogo["status"] or "Status nao informado"


def faixa_probabilidade(prob):
    if prob >= 0.72:
        return "alta"
    if prob >= 0.58:
        return "media"
    return "baixa"


def contexto_jogo(home, away):
    fh = forca_time(home)
    fa = forca_time(away)
    diff = fh - fa
    if eh_classico(home, away):
        return "classico"
    if abs(diff) <= 4:
        return "equilibrado"
    if diff >= 10:
        return "favorito_casa_forte"
    if diff >= 5:
        return "favorito_casa"
    if diff <= -10:
        return "favorito_fora_forte"
    if diff <= -5:
        return "favorito_fora"
    return "leve_desequilibrio"


def fetch_with_retry(url, params=None):
    ultimo_erro = ""
    for _ in range(RETRIES):
        try:
            resp = requests.get(url, params=params or {}, headers=HEADERS, timeout=8)
            resp.raise_for_status()
            return resp.json(), ""
        except requests.RequestException as exc:
            ultimo_erro = str(exc)
    return {}, f"Erro ao buscar dados da ESPN: {ultimo_erro}"


@cache_streamlit(ttl=900, show_spinner=False)
def buscar_scoreboard(liga_id, data_iso=None):
    params = {"limit": 300}
    if data_iso:
        params["dates"] = data_iso.replace("-", "")
    return fetch_with_retry(f"{ESPN_BASE}/{liga_id}/scoreboard", params)


@cache_streamlit(ttl=900, show_spinner=False)
def buscar_scoreboard_tenis(circuito, data_iso=None):
    params = {"limit": 300}
    if data_iso:
        params["dates"] = data_iso.replace("-", "")
    url = f"https://site.api.espn.com/apis/site/v2/sports/tennis/{circuito}/scoreboard"
    return fetch_with_retry(url, params)


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

        home = next((c for c in competidores if c.get("homeAway") == "home"), competidores[0])
        away = next((c for c in competidores if c.get("homeAway") == "away"), competidores[1])
        status_type = (event.get("status") or {}).get("type", {})

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
                "em_jogo": status_type.get("state") == "in",
                "finalizado": status_type.get("state") == "post",
                "futuro": status_type.get("state") == "pre",
            }
        )
    return jogos


def extrair_jogos_tenis(payload, circuito):
    jogos = []
    for evento in payload.get("events", []) or []:
        torneio = evento.get("name", "Torneio")
        for grupo in evento.get("groupings", []) or []:
            for comp in grupo.get("competitions", []) or []:
                competidores = comp.get("competitors") or []
                if len(competidores) < 2:
                    continue

                p1 = competidores[0]
                p2 = competidores[1]
                status_type = (comp.get("status") or {}).get("type", {})

                def nome(c):
                    atleta = c.get("athlete") or {}
                    return nome_limpo(atleta.get("displayName") or atleta.get("shortName") or "Jogador")

                def sets_txt(c):
                    valores = []
                    for linha in c.get("linescores") or []:
                        valor = linha.get("value")
                        if valor is not None:
                            valores.append(str(int(float(valor))))
                    return " ".join(valores)

                score1 = sets_txt(p1)
                score2 = sets_txt(p2)
                placar = f"{score1} / {score2}" if score1 or score2 else ""
                vencedor = ""
                if p1.get("winner"):
                    vencedor = nome(p1)
                elif p2.get("winner"):
                    vencedor = nome(p2)

                jogos.append(
                    {
                        "id": str(comp.get("id", "")),
                        "circuito": circuito,
                        "torneio": torneio,
                        "fase": ((comp.get("round") or {}).get("displayName") or ""),
                        "jogador1": nome(p1),
                        "jogador2": nome(p2),
                        "placar": placar,
                        "vencedor": vencedor,
                        "data": parse_dt(comp.get("date") or comp.get("startDate")),
                        "status": status_type.get("description", ""),
                        "em_jogo": status_type.get("state") == "in",
                        "finalizado": status_type.get("state") == "post",
                        "futuro": status_type.get("state") == "pre",
                    }
                )
    return jogos


def buscar_jogos_ultimas_24h():
    agora = datetime.now()
    datas = {(agora - timedelta(days=1)).date().isoformat(), agora.date().isoformat()}
    todos = []
    for liga_nome, liga_id in LIGAS.items():
        for data_iso in datas:
            payload, erro = buscar_scoreboard(liga_id, data_iso)
            if erro:
                continue
            for jogo in extrair_jogos(payload, liga_id):
                jogo["liga_nome"] = liga_nome
                if jogo["data"] and agora - timedelta(hours=24) <= jogo["data"] <= agora:
                    todos.append(jogo)
    return todos


def calcular_probabilidades(home, away):
    fh = forca_time(home)
    fa = forca_time(away)
    diff = fh - fa
    media_home = clamp(1.4 + (diff * 0.02) + DEFAULT_HOME_ADV, 0.2, 4.0)
    media_away = clamp(1.1 - (diff * 0.015), 0.2, 4.0)

    if eh_classico(home, away):
        media_home *= 0.95
        media_away *= 0.98

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


def obter_fator_aprendizado(liga_id, codigo, contexto=None, faixa=None):
    conn = conectar_db()
    cur = conn.cursor()
    fator_total = 0.0
    chaves = [f"mercado:{codigo}", f"liga:{liga_id}|mercado:{codigo}"]
    if contexto:
        chaves.append(f"contexto:{contexto}|mercado:{codigo}")
    if faixa:
        chaves.append(f"faixa:{faixa}|mercado:{codigo}")

    for chave in chaves:
        cur.execute("SELECT fator, jogos FROM ajustes WHERE chave = ?", (chave,))
        row = cur.fetchone()
        if row:
            fator, jogos = row
            if int(jogos) >= MIN_JOGOS_TREINO:
                fator_total += float(fator)
    conn.close()
    return clamp(fator_total, -0.18, 0.18)


def candidatos_aprendidos(probs, jogo):
    contexto = contexto_jogo(jogo["home"], jogo["away"])
    candidatos = []
    for nome, codigo, prob in mercados_disponiveis(probs, jogo["home"], jogo["away"]):
        faixa = faixa_probabilidade(prob)
        fator = obter_fator_aprendizado(jogo["liga"], codigo, contexto, faixa)
        candidatos.append((nome, codigo, clamp(prob + fator, 0.01, 0.99), fator, prob))
    return candidatos, contexto


def melhor_mercado_base(probs, home, away):
    return sorted(mercados_disponiveis(probs, home, away), key=lambda x: x[2], reverse=True)[0]


def melhor_mercado_aprendido(probs, jogo):
    candidatos, contexto = candidatos_aprendidos(probs, jogo)
    return sorted(candidatos, key=lambda x: x[2], reverse=True)[0], candidatos, contexto


def verificar_acerto(codigo, home_score, away_score):
    total = home_score + away_score
    if codigo == "home":
        return home_score > away_score
    if codigo == "draw":
        return home_score == away_score
    if codigo == "away":
        return away_score > home_score
    if codigo == "dupla_1x":
        return home_score >= away_score
    if codigo == "dupla_x2":
        return away_score >= home_score
    if codigo == "dupla_12":
        return home_score != away_score
    if codigo == "over15":
        return total >= 2
    if codigo == "over25":
        return total >= 3
    if codigo == "over35":
        return total >= 4
    if codigo == "under25":
        return total <= 2
    if codigo == "btts":
        return home_score > 0 and away_score > 0
    return False


def calcular_probabilidades_tenis(jogador1, jogador2, circuito):
    f1 = forca_jogador(jogador1)
    f2 = forca_jogador(jogador2)
    diff = f1 - f2
    p1 = clamp(1 / (1 + math.exp(-(diff / 12))), 0.08, 0.92)

    if circuito == "wta":
        p_over = 0.46 + (0.10 if abs(diff) <= 4 else -0.04)
    else:
        p_over = 0.48 + (0.08 if abs(diff) <= 4 else -0.03)

    p_over = clamp(p_over, 0.25, 0.72)
    p2 = 1 - p1
    return {
        "j1": p1,
        "j2": p2,
        "over_games": p_over,
        "straight_sets": clamp(max(p1, p2) - 0.10, 0.35, 0.78),
        "forca_j1": f1,
        "forca_j2": f2,
    }


def mercado_tenis(probs, jogador1, jogador2, circuito):
    mercados = [
        (f"{jogador1} vence", "j1", probs["j1"]),
        (f"{jogador2} vence", "j2", probs["j2"]),
        ("Over games", "over_games", probs["over_games"]),
        ("Vitoria em sets diretos", "straight_sets", probs["straight_sets"]),
    ]

    candidatos = []
    for nome, codigo, prob in mercados:
        fator = obter_fator_aprendizado(f"tenis_{circuito}", f"tenis_{codigo}", "tenis", faixa_probabilidade(prob))
        candidatos.append((nome, codigo, clamp(prob + fator, 0.01, 0.99), fator, prob))

    return sorted(candidatos, key=lambda x: x[2], reverse=True)[0], candidatos


def total_games_tenis(placar):
    """Soma games a partir de placares simples no formato '6 4 7 / 4 6 5'."""
    numeros = [int(n) for n in re.findall(r"\d+", placar or "")]
    return sum(numeros)


def sets_vencidos_tenis(placar):
    """
    Calcula sets vencidos usando pares por posição:
    '6 4 7 / 4 6 5' -> jogador1 venceu 2 sets, jogador2 venceu 1.
    """
    if "/" not in (placar or ""):
        return 0, 0

    lado1, lado2 = placar.split("/", 1)
    games1 = [int(n) for n in re.findall(r"\d+", lado1)]
    games2 = [int(n) for n in re.findall(r"\d+", lado2)]
    s1 = s2 = 0

    for g1, g2 in zip(games1, games2):
        if g1 > g2:
            s1 += 1
        elif g2 > g1:
            s2 += 1

    return s1, s2


def verificar_acerto_tenis(codigo, jogo):
    vencedor = jogo.get("vencedor", "")
    jogador1 = jogo.get("jogador1", "")
    jogador2 = jogo.get("jogador2", "")
    placar = jogo.get("placar", "")

    if codigo == "j1":
        return bool(vencedor) and vencedor == jogador1
    if codigo == "j2":
        return bool(vencedor) and vencedor == jogador2
    if codigo == "straight_sets":
        s1, s2 = sets_vencidos_tenis(placar)
        return bool(vencedor) and (s1 == 0 or s2 == 0)
    if codigo == "over_games":
        # Linha didática fixa. Depois você pode substituir por linhas reais de odds.
        return total_games_tenis(placar) >= 22

    return False



def salvar_previsao_tenis(jogo, mercado):
    nome, codigo, prob_aprendida, fator, prob_base = mercado
    acertou = None
    finalizado = int(jogo["finalizado"])
    vencedor = jogo.get("vencedor", "")
    if finalizado:
        acertou = int(verificar_acerto_tenis(codigo, jogo))

    conn = conectar_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO tenis_historico (
            game_id, circuito, torneio, data_jogo, jogador1, jogador2,
            mercado, codigo, prob_base, prob_aprendida, ajuste_aplicado,
            placar, vencedor, acertou, finalizado, criado_em
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(game_id) DO UPDATE SET
            circuito = excluded.circuito,
            torneio = excluded.torneio,
            data_jogo = excluded.data_jogo,
            jogador1 = excluded.jogador1,
            jogador2 = excluded.jogador2,
            mercado = excluded.mercado,
            codigo = excluded.codigo,
            prob_base = excluded.prob_base,
            prob_aprendida = excluded.prob_aprendida,
            ajuste_aplicado = excluded.ajuste_aplicado,
            placar = excluded.placar,
            vencedor = excluded.vencedor,
            acertou = excluded.acertou,
            finalizado = excluded.finalizado
        """,
        (
            jogo["id"],
            jogo["circuito"],
            jogo["torneio"],
            jogo["data"].isoformat() if jogo["data"] else "",
            jogo["jogador1"],
            jogo["jogador2"],
            nome,
            codigo,
            float(prob_base),
            float(prob_aprendida),
            float(fator),
            jogo.get("placar", ""),
            vencedor,
            acertou,
            finalizado,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()



def salvar_previsao(jogo, liga_nome, base, aprendido, placar_previsto, candidatos, contexto):
    conn = conectar_db()
    cur = conn.cursor()
    mercado_base, codigo_base, prob_base = base
    mercado_ap, codigo_ap, prob_ap, fator, prob_original = aprendido
    cur.execute(
        """
        INSERT OR IGNORE INTO previsoes (
            game_id, liga_id, liga_nome, data_jogo, home, away,
            mercado_base, codigo_base, prob_base,
            mercado_aprendido, codigo_aprendido, prob_aprendido, ajuste_aplicado,
            placar_previsto, finalizado, criado_em
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            jogo["id"], jogo["liga"], liga_nome, jogo["data"].isoformat() if jogo["data"] else "",
            jogo["home"], jogo["away"], mercado_base, codigo_base, float(prob_base),
            mercado_ap, codigo_ap, float(prob_ap), float(fator), placar_previsto, 0,
            datetime.now().isoformat(),
        ),
    )
    for nome, codigo, prob_aprendida, fator_candidato, prob_base_candidato in candidatos:
        cur.execute(
            """
            INSERT OR IGNORE INTO mercado_historico (
                game_id, liga_id, liga_nome, data_jogo, home, away,
                contexto, faixa_prob, mercado, codigo, prob_base,
                prob_aprendida, ajuste_aplicado, finalizado, criado_em
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                jogo["id"], jogo["liga"], liga_nome, jogo["data"].isoformat() if jogo["data"] else "",
                jogo["home"], jogo["away"], contexto, faixa_probabilidade(prob_base_candidato),
                nome, codigo, float(prob_base_candidato), float(prob_aprendida),
                float(fator_candidato), 0, datetime.now().isoformat(),
            ),
        )
    conn.commit()
    conn.close()


def atualizar_resultado(jogo):
    conn = conectar_db()
    cur = conn.cursor()
    cur.execute("SELECT codigo_base, codigo_aprendido FROM previsoes WHERE game_id = ?", (jogo["id"],))
    row = cur.fetchone()
    if not row:
        conn.close()
        return

    codigo_base, codigo_ap = row
    acertou_base = int(verificar_acerto(codigo_base, jogo["home_score"], jogo["away_score"]))
    acertou_ap = int(verificar_acerto(codigo_ap, jogo["home_score"], jogo["away_score"]))
    cur.execute(
        """
        UPDATE previsoes
        SET home_score = ?, away_score = ?, acertou_base = ?,
            acertou_aprendido = ?, finalizado = 1
        WHERE game_id = ?
        """,
        (jogo["home_score"], jogo["away_score"], acertou_base, acertou_ap, jogo["id"]),
    )
    cur.execute("SELECT codigo FROM mercado_historico WHERE game_id = ?", (jogo["id"],))
    for (codigo,) in cur.fetchall():
        acertou = int(verificar_acerto(codigo, jogo["home_score"], jogo["away_score"]))
        cur.execute(
            "UPDATE mercado_historico SET acertou = ?, finalizado = 1 WHERE game_id = ? AND codigo = ?",
            (acertou, jogo["id"], codigo),
        )
    conn.commit()
    conn.close()


def treinar_grupo(df, coluna, peso, limite, prefixo):
    treinados = 0
    if coluna not in df.columns:
        return 0
    for valor in df[coluna].dropna().unique():
        df_grupo = df[df[coluna] == valor]
        for codigo in df_grupo["codigo"].dropna().unique():
            sub = df_grupo[df_grupo["codigo"] == codigo]
            jogos = len(sub)
            if jogos >= MIN_JOGOS_TREINO:
                acertos = int(sub["acertou"].fillna(0).sum())
                fator = clamp(((acertos / jogos) - 0.55) * peso, -limite, limite)
                salvar_ajuste(f"{prefixo}:{valor}|mercado:{codigo}", fator, jogos, acertos)
                treinados += 1
    return treinados


def treinar_modelo():
    df = ler_tabela("SELECT * FROM mercado_historico WHERE finalizado = 1")
    if df.empty:
        return 0

    treinados = 0
    for codigo in df["codigo"].dropna().unique():
        sub = df[df["codigo"] == codigo]
        jogos = len(sub)
        if jogos >= MIN_JOGOS_TREINO:
            acertos = int(sub["acertou"].fillna(0).sum())
            fator = clamp(((acertos / jogos) - 0.55) * 0.18, -0.07, 0.07)
            salvar_ajuste(f"mercado:{codigo}", fator, jogos, acertos)
            treinados += 1

    treinados += treinar_grupo(df, "liga_id", 0.13, 0.05, "liga")
    treinados += treinar_grupo(df, "contexto", 0.12, 0.045, "contexto")
    treinados += treinar_grupo(df, "faixa_prob", 0.10, 0.035, "faixa")
    return treinados



def treinar_modelo_tenis():
    df = ler_tabela("SELECT * FROM tenis_historico WHERE finalizado = 1")
    if df.empty:
        return 0

    treinados = 0

    for codigo in df["codigo"].dropna().unique():
        sub = df[df["codigo"] == codigo]
        jogos = len(sub)
        if jogos >= MIN_JOGOS_TREINO:
            acertos = int(sub["acertou"].fillna(0).sum())
            fator = clamp(((acertos / jogos) - 0.55) * 0.15, -0.06, 0.06)
            salvar_ajuste(f"mercado:tenis_{codigo}", fator, jogos, acertos)
            treinados += 1

    for circuito in df["circuito"].dropna().unique():
        df_circuito = df[df["circuito"] == circuito]
        for codigo in df_circuito["codigo"].dropna().unique():
            sub = df_circuito[df_circuito["codigo"] == codigo]
            jogos = len(sub)
            if jogos >= MIN_JOGOS_TREINO:
                acertos = int(sub["acertou"].fillna(0).sum())
                fator = clamp(((acertos / jogos) - 0.55) * 0.12, -0.05, 0.05)
                salvar_ajuste(f"liga:tenis_{circuito}|mercado:tenis_{codigo}", fator, jogos, acertos)
                treinados += 1

    if "prob_base" in df.columns:
        df["faixa_prob"] = df["prob_base"].map(faixa_probabilidade)
        treinados += treinar_grupo(df, "faixa_prob", 0.08, 0.03, "faixa")

    return treinados

def render_jogos(liga_nome, data_escolhida, filtro_status):
    liga_id = LIGAS[liga_nome]
    with st.spinner("Carregando jogos..."):
        payload, erro = buscar_scoreboard(liga_id, data_escolhida)
    if erro:
        st.error(erro)
        return

    jogos = extrair_jogos(payload, liga_id)
    if filtro_status == "Ao vivo":
        jogos = [j for j in jogos if j["em_jogo"]]
    elif filtro_status == "Futuros":
        jogos = [j for j in jogos if j["futuro"]]
    elif filtro_status == "Finalizados":
        jogos = [j for j in jogos if j["finalizado"]]

    st.subheader(f"{liga_nome} - {len(jogos)} jogo(s)")
    if not jogos:
        st.info("Nenhum jogo encontrado com estes filtros.")
        return

    jogos_futuros = sum(1 for j in jogos if j["futuro"])
    jogos_ao_vivo = sum(1 for j in jogos if j["em_jogo"])
    jogos_finalizados = sum(1 for j in jogos if j["finalizado"])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Jogos", len(jogos))
    c2.metric("Futuros", jogos_futuros)
    c3.metric("Ao vivo", jogos_ao_vivo)
    c4.metric("Finalizados", jogos_finalizados)

    resumo = []
    for jogo in jogos:
        probs = calcular_probabilidades(jogo["home"], jogo["away"])
        base = melhor_mercado_base(probs, jogo["home"], jogo["away"])
        aprendido, candidatos, contexto = melhor_mercado_aprendido(probs, jogo)
        placar_top = probs["placares"][0]
        placar_previsto = f"{placar_top[0]} x {placar_top[1]}"
        salvar_previsao(jogo, liga_nome, base, aprendido, placar_previsto, candidatos, contexto)
        if jogo["finalizado"]:
            atualizar_resultado(jogo)

        mercado_base, codigo_base, prob_base = base
        mercado_ap, codigo_ap, prob_ap, fator, prob_original = aprendido
        placar_txt = f" - {jogo['home_score']} x {jogo['away_score']}" if jogo["finalizado"] or jogo["em_jogo"] else ""

        resumo.append(
            {
                "Jogo": f"{jogo['home']} x {jogo['away']}",
                "Status": status_label(jogo),
                "Base": mercado_base,
                "Prob Base": pct(prob_base),
                "Aprendido": mercado_ap,
                "Prob Aprendida": pct(prob_ap),
                "Prob Valor": prob_ap,
                "Contexto": contexto,
                "Ajuste": f"{fator:+.1%}",
            }
        )

        st.markdown(
            f"""
            <div class="pro-card">
                <h3>{jogo['home']} x {jogo['away']}{placar_txt}</h3>
                <span class="pro-chip">{status_label(jogo)}</span>
                <span class="pro-chip">{contexto.replace('_', ' ')}</span>
                <span class="pro-chip">Placar provavel {placar_previsto}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2)
        c1.metric("Base", mercado_base, pct(prob_base))
        c2.metric("Aprendido", mercado_ap, f"{pct(prob_ap)} | {fator:+.1%}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Casa", pct(probs["home"]), f"Odd {odd_justa(probs['home']):.2f}")
        c2.metric("Empate", pct(probs["draw"]), f"Odd {odd_justa(probs['draw']):.2f}")
        c3.metric("Fora", pct(probs["away"]), f"Odd {odd_justa(probs['away']):.2f}")
        with st.expander("Ver todos os mercados"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Mercado": nome,
                            "Base": pct(prob_original),
                            "Aprendido": pct(prob_ajustada),
                            "Ajuste": f"{fator_candidato:+.1%}",
                            "Odd justa": f"{odd_justa(prob_ajustada):.2f}",
                        }
                        for nome, codigo, prob_ajustada, fator_candidato, prob_original in candidatos
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )
        st.markdown("---")

    if resumo:
        st.subheader("Resumo")
        df_resumo = pd.DataFrame(resumo)
        st.dataframe(df_resumo.drop(columns=["Prob Valor"]), use_container_width=True, hide_index=True)

        st.subheader("Melhores oportunidades aprendidas")
        destaques = df_resumo.sort_values("Prob Valor", ascending=False).head(8)
        destaques = destaques.drop(columns=["Prob Valor"])
        st.dataframe(destaques, use_container_width=True, hide_index=True)


def render_backtest():
    if not st.button("Rodar backtest 24h"):
        st.info("Clique para buscar jogos finalizados das ultimas 24h.")
        return

    with st.spinner("Rodando backtest..."):
        finalizados = [j for j in buscar_jogos_ultimas_24h() if j["finalizado"]]

    linhas = []
    for jogo in finalizados:
        probs = calcular_probabilidades(jogo["home"], jogo["away"])
        base = melhor_mercado_base(probs, jogo["home"], jogo["away"])
        aprendido, candidatos, contexto = melhor_mercado_aprendido(probs, jogo)
        placar_previsto = f"{probs['placares'][0][0]} x {probs['placares'][0][1]}"
        salvar_previsao(jogo, jogo.get("liga_nome", jogo["liga"]), base, aprendido, placar_previsto, candidatos, contexto)
        atualizar_resultado(jogo)
        mercado_base, codigo_base, prob_base = base
        mercado_ap, codigo_ap, prob_ap, fator, prob_original = aprendido
        acertou_base = verificar_acerto(codigo_base, jogo["home_score"], jogo["away_score"])
        acertou_ap = verificar_acerto(codigo_ap, jogo["home_score"], jogo["away_score"])
        linhas.append(
            {
                "Liga": jogo.get("liga_nome", jogo["liga"]),
                "Jogo": f"{jogo['home']} x {jogo['away']}",
                "Placar": f"{jogo['home_score']} x {jogo['away_score']}",
                "Base": mercado_base,
                "Base Resultado": "Acertou" if acertou_base else "Errou",
                "Aprendido": mercado_ap,
                "Aprendido Resultado": "Acertou" if acertou_ap else "Errou",
                "Contexto": contexto,
            }
        )

    if not linhas:
        st.warning("Nenhum jogo finalizado encontrado nas ultimas 24h.")
        return

    df_bt = pd.DataFrame(linhas)
    total = len(df_bt)
    acertos_base = (df_bt["Base Resultado"] == "Acertou").sum()
    acertos_ap = (df_bt["Aprendido Resultado"] == "Acertou").sum()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Jogos", total)
    c2.metric("Base", f"{acertos_base}/{total}", pct(acertos_base / total))
    c3.metric("Aprendido", f"{acertos_ap}/{total}", pct(acertos_ap / total))
    c4.metric("Ganho", acertos_ap - acertos_base)
    st.dataframe(df_bt, use_container_width=True, hide_index=True)


def render_tenis(circuito_nome, data_escolhida, filtro_status):
    circuito = TENIS_LIGAS[circuito_nome]
    with st.spinner("Carregando jogos de tenis..."):
        payload, erro = buscar_scoreboard_tenis(circuito, data_escolhida)
    if erro:
        st.error(erro)
        return

    jogos = extrair_jogos_tenis(payload, circuito)
    if filtro_status == "Ao vivo":
        jogos = [j for j in jogos if j["em_jogo"]]
    elif filtro_status == "Futuros":
        jogos = [j for j in jogos if j["futuro"]]
    elif filtro_status == "Finalizados":
        jogos = [j for j in jogos if j["finalizado"]]

    st.subheader(f"Tenis {circuito_nome} - {len(jogos)} jogo(s)")
    if not jogos:
        st.info("Nenhum jogo de tenis encontrado com estes filtros.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Circuito", circuito_nome)
    c2.metric("Jogos", len(jogos))
    c3.metric("Treino minimo", MIN_JOGOS_TREINO)

    linhas = []
    for jogo in jogos:
        probs = calcular_probabilidades_tenis(jogo["jogador1"], jogo["jogador2"], circuito)
        melhor, candidatos = mercado_tenis(probs, jogo["jogador1"], jogo["jogador2"], circuito)
        salvar_previsao_tenis(jogo, melhor)

        mercado, codigo, prob_aprendida, fator, prob_base = melhor
        placar_txt = f" - {jogo['placar']}" if jogo.get("placar") else ""
        st.markdown(
            f"""
            <div class="pro-card">
                <h3>{jogo['jogador1']} x {jogo['jogador2']}{placar_txt}</h3>
                <span class="pro-chip">{status_label(jogo)}</span>
                <span class="pro-chip">{jogo.get('torneio', '')}</span>
                <span class="pro-chip">{jogo.get('fase', '')}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2, c3 = st.columns(3)
        c1.metric("Previsao", mercado, pct(prob_aprendida))
        c2.metric(jogo["jogador1"], pct(probs["j1"]), f"Forca {probs['forca_j1']}")
        c3.metric(jogo["jogador2"], pct(probs["j2"]), f"Forca {probs['forca_j2']}")

        with st.expander("Ver mercados do tenis"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Mercado": nome,
                            "Base": pct(prob_original),
                            "Aprendido": pct(prob_ajustada),
                            "Ajuste": f"{fator_candidato:+.1%}",
                            "Odd justa": f"{odd_justa(prob_ajustada):.2f}",
                        }
                        for nome, codigo_item, prob_ajustada, fator_candidato, prob_original in candidatos
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )

        linhas.append(
            {
                "Jogo": f"{jogo['jogador1']} x {jogo['jogador2']}",
                "Torneio": jogo["torneio"],
                "Status": status_label(jogo),
                "Previsao": mercado,
                "Prob": pct(prob_aprendida),
                "Ajuste": f"{fator:+.1%}",
                "Placar": jogo.get("placar", ""),
                "Vencedor": jogo.get("vencedor", ""),
            }
        )
        st.markdown("---")

    st.subheader("Resumo tenis")
    st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True)


def render_aprendizado():
    df = ler_tabela("SELECT * FROM previsoes ORDER BY id DESC")
    mercados = ler_tabela("SELECT * FROM mercado_historico ORDER BY id DESC")
    tenis = ler_tabela("SELECT * FROM tenis_historico ORDER BY id DESC")
    ajustes = ler_tabela("SELECT * FROM ajustes ORDER BY jogos DESC")

    st.markdown(
        """
        <div class="learn-box">
            <b>Como o aprendizado funciona:</b> o app mede acerto por mercado, liga/circuito e faixa de probabilidade.
            Quando existe amostra suficiente, ele aplica pequenos ajustes controlados. Isso é propositalmente simples,
            interpretável e bom para estudar antes de partir para Machine Learning real.
        </div>
        """,
        unsafe_allow_html=True,
    )

    finalizados = df[df["finalizado"] == 1].copy() if not df.empty else pd.DataFrame()
    tenis_finalizados = tenis[tenis["finalizado"] == 1].copy() if not tenis.empty else pd.DataFrame()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Previsões futebol", len(df))
    c2.metric("Previsões tênis", len(tenis))
    if len(finalizados):
        ap_acc = finalizados["acertou_aprendido"].fillna(0).sum() / len(finalizados)
    else:
        ap_acc = 0
    if len(tenis_finalizados):
        tenis_acc = tenis_finalizados["acertou"].fillna(0).sum() / len(tenis_finalizados)
    else:
        tenis_acc = 0
    c3.metric("Acurácia futebol", pct(ap_acc))
    c4.metric("Acurácia tênis", pct(tenis_acc))

    st.caption(f"Treino exige pelo menos {MIN_JOGOS_TREINO} jogos por grupo.")
    if st.button("Treinar futebol + tênis agora"):
        qtd_futebol = treinar_modelo()
        qtd_tenis = treinar_modelo_tenis()
        st.success(f"Treinamento concluído. Futebol: {qtd_futebol} ajuste(s). Tênis: {qtd_tenis} ajuste(s).")

    st.subheader("Ajustes aprendidos")
    if ajustes.empty:
        st.info("Nenhum ajuste aprendido ainda.")
    else:
        st.dataframe(ajustes, use_container_width=True, hide_index=True)

    tab1, tab2, tab3 = st.tabs(["Futebol", "Tênis", "Histórico bruto"])

    with tab1:
        if mercados.empty:
            st.info("Ainda não há mercados de futebol salvos.")
        else:
            mercados_finalizados = mercados[mercados["finalizado"] == 1].copy()
            if mercados_finalizados.empty:
                st.info("Ainda não há mercados de futebol finalizados.")
            else:
                desempenho = (
                    mercados_finalizados
                    .groupby(["codigo", "mercado"], as_index=False)
                    .agg(jogos=("id", "count"), acertos=("acertou", "sum"), prob_media=("prob_base", "mean"))
                )
                desempenho["taxa"] = desempenho["acertos"] / desempenho["jogos"]
                desempenho = desempenho.sort_values(["jogos", "taxa"], ascending=[False, False])
                desempenho["taxa"] = desempenho["taxa"].map(pct)
                desempenho["prob_media"] = desempenho["prob_media"].map(pct)
                st.dataframe(desempenho, use_container_width=True, hide_index=True)

    with tab2:
        if tenis.empty:
            st.info("Ainda não há histórico de tênis salvo.")
        elif tenis_finalizados.empty:
            st.info("Ainda não há jogos de tênis finalizados.")
        else:
            desempenho_tenis = (
                tenis_finalizados
                .groupby(["circuito", "codigo", "mercado"], as_index=False)
                .agg(jogos=("id", "count"), acertos=("acertou", "sum"), prob_media=("prob_base", "mean"))
            )
            desempenho_tenis["taxa"] = desempenho_tenis["acertos"] / desempenho_tenis["jogos"]
            desempenho_tenis = desempenho_tenis.sort_values(["jogos", "taxa"], ascending=[False, False])
            desempenho_tenis["taxa"] = desempenho_tenis["taxa"].map(pct)
            desempenho_tenis["prob_media"] = desempenho_tenis["prob_media"].map(pct)
            st.dataframe(desempenho_tenis, use_container_width=True, hide_index=True)

    with tab3:
        st.write("Futebol")
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.write("Tênis")
        st.dataframe(tenis, use_container_width=True, hide_index=True)



def main():
    aplicar_estilo()
    init_db()
    st.title("Analisador Esportivo Learning")
    st.caption("Futebol com Poisson, tênis com força relativa e aprendizado por erros/acertos.")
    st.markdown(
        """
        <div class="hero">
            <div class="hero-title">Laboratório de previsão esportiva</div>
            <div class="hero-text">
                Compare modelo base vs. modelo aprendido, acompanhe acertos e use cada erro como dado de treino.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("Menu")
        esporte = st.selectbox("Esporte", ["Futebol", "Tenis"])
        if esporte == "Futebol":
            pagina = st.selectbox("Tela", ["Jogos", "Backtest 24h", "Aprendizado"])
        else:
            pagina = "Tenis"
        st.header("Filtros")
        liga_nome = st.selectbox("Liga", list(LIGAS.keys()))
        circuito_tenis = st.selectbox("Circuito tenis", list(TENIS_LIGAS.keys()))
        usar_data = st.checkbox("Filtrar por data")
        data_escolhida = st.date_input("Data").isoformat() if usar_data else None
        filtro_status = st.selectbox("Status", ["Todos", "Ao vivo", "Futuros", "Finalizados"])
        carregar_auto = st.checkbox("Carregar jogos ao abrir", value=False)
        if st.button("Limpar cache ESPN"):
            try:
                st.cache_data.clear()
                st.success("Cache limpo.")
            except Exception:
                st.info("Cache indisponivel nesta versao do Streamlit.")

    st.markdown(
        f"""
        <div class="mobile-filter">
            <b>Esporte:</b> {esporte}<br>
            <b>Tela:</b> {pagina}<br>
            <b>Liga/Circuito:</b> {liga_nome if esporte == 'Futebol' else circuito_tenis}<br>
            <b>Status:</b> {filtro_status}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if esporte == "Tenis":
        st.info(f"Tenis {circuito_tenis} | {filtro_status} | previsao por forca do jogador e aprendizado.")
        if carregar_auto or st.button("Carregar jogos de tenis"):
            render_tenis(circuito_tenis, data_escolhida, filtro_status)
    elif pagina == "Jogos":
        st.info(f"{liga_nome} | {filtro_status} | treino minimo: {MIN_JOGOS_TREINO} jogos")
        if carregar_auto or st.button("Carregar jogos"):
            render_jogos(liga_nome, data_escolhida, filtro_status)
    elif pagina == "Backtest 24h":
        render_backtest()
    else:
        render_aprendizado()


try:
    main()
except Exception as exc:
    st.error("O app encontrou um erro ao iniciar.")
    st.exception(exc)
