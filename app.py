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
    page_title="Analisador Esportivo Pro 16",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
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
        html, body, [data-testid="stAppViewContainer"] {
            overflow-y: auto !important;
        }
        .block-container {
            padding-top: 2.2rem;
            padding-left: 1rem;
            padding-right: 1rem;
            padding-bottom: 5rem;
            max-width: 1280px;
        }
        h1 { font-size: 1.55rem !important; margin-bottom: .2rem !important; }
        h2, h3 { letter-spacing: 0 !important; }
        [data-testid="stHeader"] {
            background: rgba(255, 255, 255, .94);
        }
        [data-testid="stToolbar"] { visibility: visible; }
        div[data-testid="stMetric"] {
            background: #f8fafc;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: .45rem .55rem;
        }
        div[data-testid="stAlert"] {
            border-radius: 8px;
            padding: .55rem .75rem;
        }
        section[data-testid="stSidebar"] {
            background: #f8fafc;
        }
        .pro-card {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: .75rem .85rem;
            background: #ffffff;
            margin: .55rem 0 .35rem 0;
        }
        .pro-chip {
            display: inline-block;
            border: 1px solid #e5e7eb;
            border-radius: 999px;
            padding: .12rem .45rem;
            margin-right: .25rem;
            font-size: .78rem;
            background: #f8fafc;
        }
        div[data-testid="stMetricValue"] { font-size: 1rem !important; }
        div[data-testid="stMetricDelta"] { font-size: .72rem !important; }
        @media (max-width: 640px) {
            .block-container {
                padding: 1.35rem .45rem 5rem .45rem;
            }
            h1 { font-size: 1.12rem !important; line-height: 1.15 !important; }
            h2 { font-size: 1.05rem !important; }
            h3 { font-size: .98rem !important; }
            p, div, span { font-size: .9rem; }
            div[data-testid="stMetric"] { padding: .38rem .45rem; }
            div[data-testid="stMetricValue"] { font-size: .92rem !important; }
            .pro-card { padding: .55rem .6rem; }
            div[data-testid="column"] {
                min-width: 0 !important;
            }
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

def proxima_data_semana(dia_semana):
    hoje = datetime.now().date()
    dias = (dia_semana - hoje.weekday()) % 7
    if dias == 0:
        dias = 7
    return (hoje + timedelta(days=dias)).isoformat()

def datas_para_busca(modo_agenda, data_manual=None):
    if modo_agenda == "Data manual":
        return [data_manual] if data_manual else [None]
    if modo_agenda == "Próxima quarta":
        return [proxima_data_semana(2)]
    if modo_agenda == "Próximo domingo":
        return [proxima_data_semana(6)]
    if modo_agenda == "Quarta + Domingo":
        return [proxima_data_semana(2), proxima_data_semana(6)]
    return [None]

def rotulo_datas(datas):
    datas_validas = [d for d in datas or [] if d]
    if not datas_validas:
        return "agenda atual"
    return " + ".join(datas_validas)


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


def verificar_acerto_tenis(codigo, jogo):
    vencedor = jogo.get("vencedor", "")
    jogador1 = jogo.get("jogador1", "")
    jogador2 = jogo.get("jogador2", "")
    if not vencedor:
        return False
    if codigo == "j1":
        return vencedor == jogador1
    if codigo == "j2":
        return vencedor == jogador2
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
        INSERT OR IGNORE INTO tenis_historico (
            game_id, circuito, torneio, data_jogo, jogador1, jogador2,
            mercado, codigo, prob_base, prob_aprendida, ajuste_aplicado,
            placar, vencedor, acertou, finalizado, criado_em
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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


def render_jogos(liga_nome, datas_escolhidas, filtro_status):
    liga_id = LIGAS[liga_nome]
    jogos = []
    erros = []
    datas_escolhidas = datas_escolhidas or [None]

    with st.spinner("Carregando jogos..."):
        for data_iso in datas_escolhidas:
            payload, erro = buscar_scoreboard(liga_id, data_iso)
            if erro:
                erros.append(f"{data_iso or 'agenda atual'}: {erro}")
                continue
            jogos.extend(extrair_jogos(payload, liga_id))

    if erros and not jogos:
        st.error(" | ".join(erros))
        return

    jogos_unicos = {}
    for jogo in jogos:
        jogos_unicos[jogo["id"]] = jogo
    jogos = list(jogos_unicos.values())

    if filtro_status == "Ao vivo":
        jogos = [j for j in jogos if j["em_jogo"]]
    elif filtro_status == "Futuros":
        jogos = [j for j in jogos if j["futuro"]]
    elif filtro_status == "Finalizados":
        jogos = [j for j in jogos if j["finalizado"]]

    st.subheader(f"{liga_nome} - {len(jogos)} jogo(s)")
    st.caption(f"Datas carregadas: {rotulo_datas(datas_escolhidas)}")
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


def render_tenis(circuito_nome, datas_escolhidas, filtro_status):
    circuito = TENIS_LIGAS[circuito_nome]
    jogos = []
    erros = []
    datas_escolhidas = datas_escolhidas or [None]

    with st.spinner("Carregando jogos de tenis..."):
        for data_iso in datas_escolhidas:
            payload, erro = buscar_scoreboard_tenis(circuito, data_iso)
            if erro:
                erros.append(f"{data_iso or 'agenda atual'}: {erro}")
                continue
            jogos.extend(extrair_jogos_tenis(payload, circuito))

    if erros and not jogos:
        st.error(" | ".join(erros))
        return

    jogos_unicos = {}
    for jogo in jogos:
        jogos_unicos[jogo["id"]] = jogo
    jogos = list(jogos_unicos.values())

    if filtro_status == "Ao vivo":
        jogos = [j for j in jogos if j["em_jogo"]]
    elif filtro_status == "Futuros":
        jogos = [j for j in jogos if j["futuro"]]
    elif filtro_status == "Finalizados":
        jogos = [j for j in jogos if j["finalizado"]]

    st.subheader(f"Tenis {circuito_nome} - {len(jogos)} jogo(s)")
    st.caption(f"Datas carregadas: {rotulo_datas(datas_escolhidas)}")
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
    ajustes = ler_tabela("SELECT * FROM ajustes ORDER BY jogos DESC")

    if df.empty:
        st.info("Ainda nao ha historico salvo.")
        return

    finalizados = df[df["finalizado"] == 1].copy()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Previsoes", len(df))
    c2.metric("Mercados", len(mercados))
    if len(finalizados):
        base_acc = finalizados["acertou_base"].fillna(0).sum() / len(finalizados)
        ap_acc = finalizados["acertou_aprendido"].fillna(0).sum() / len(finalizados)
        ganho = int(finalizados["acertou_aprendido"].fillna(0).sum() - finalizados["acertou_base"].fillna(0).sum())
    else:
        base_acc = ap_acc = 0
        ganho = 0
    c3.metric("Base", pct(base_acc))
    c4.metric("Aprendido", pct(ap_acc), f"Ganho {ganho}")

    st.caption(f"Treino exige pelo menos {MIN_JOGOS_TREINO} jogos por grupo.")
    if st.button("Treinar modelo agora"):
        qtd = treinar_modelo()
        st.success(f"Treinamento concluido. Ajustes atualizados: {qtd}")

    st.subheader("Ajustes aprendidos")
    if ajustes.empty:
        st.info("Nenhum ajuste aprendido ainda.")
    else:
        st.dataframe(ajustes, use_container_width=True, hide_index=True)

    mercados_finalizados = mercados[mercados["finalizado"] == 1].copy() if not mercados.empty else pd.DataFrame()
    if not mercados_finalizados.empty:
        st.subheader("Desempenho por mercado")
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

        st.subheader("Aprendizado por contexto")
        contexto = (
            mercados_finalizados
            .groupby(["contexto", "codigo"], as_index=False)
            .agg(jogos=("id", "count"), acertos=("acertou", "sum"), prob_media=("prob_base", "mean"))
        )
        contexto["taxa"] = contexto["acertos"] / contexto["jogos"]
        contexto = contexto.sort_values(["jogos", "taxa"], ascending=[False, False])
        contexto["taxa"] = contexto["taxa"].map(pct)
        contexto["prob_media"] = contexto["prob_media"].map(pct)
        st.dataframe(contexto.head(30), use_container_width=True, hide_index=True)

        st.subheader("Calibragem por faixa de probabilidade")
        faixas = (
            mercados_finalizados
            .groupby(["faixa_prob", "codigo"], as_index=False)
            .agg(jogos=("id", "count"), acertos=("acertou", "sum"), prob_media=("prob_base", "mean"))
        )
        faixas["taxa_real"] = faixas["acertos"] / faixas["jogos"]
        faixas = faixas.sort_values(["faixa_prob", "jogos"], ascending=[True, False])
        faixas["taxa_real"] = faixas["taxa_real"].map(pct)
        faixas["prob_media"] = faixas["prob_media"].map(pct)
        st.dataframe(faixas, use_container_width=True, hide_index=True)

    st.subheader("Historico")
    st.dataframe(df, use_container_width=True, hide_index=True)


def main():
    aplicar_estilo()
    init_db()
    st.title("Pro 16 Super")
    st.caption("Futebol e tenis com aprendizado por erros/acertos.")

    c1, c2, c3, c4 = st.columns(4)
    esporte = c1.selectbox("Esporte", ["Futebol", "Tenis"])
    if esporte == "Futebol":
        pagina = c2.selectbox("Tela", ["Jogos", "Backtest 24h", "Aprendizado"])
        liga_nome = c3.selectbox("Liga", list(LIGAS.keys()))
        circuito_tenis = "ATP"
    else:
        pagina = "Tenis"
        liga_nome = "Brasileirão Série A"
        circuito_tenis = c2.selectbox("Circuito", list(TENIS_LIGAS.keys()))
        c3.info("Tenis")
    filtro_status = c4.selectbox("Status", ["Todos", "Ao vivo", "Futuros", "Finalizados"])

    c1, c2, c3 = st.columns(3)
    modo_agenda = c1.selectbox(
        "Agenda",
        ["Hoje/API", "Data manual", "Próxima quarta", "Próximo domingo", "Quarta + Domingo"],
        index=0,
    )
    data_manual = c2.date_input("Data").isoformat() if modo_agenda == "Data manual" else None
    carregar_auto = c3.checkbox("Carregar ao abrir", value=False)
    datas_escolhidas = datas_para_busca(modo_agenda, data_manual)

    c1, c2, c3 = st.columns(3)
    limpar_cache = c1.button("Limpar cache ESPN")
    carregar = c2.button("Carregar jogos")
    ao_vivo_agora = c3.button("Ao vivo agora")
    if limpar_cache:
        try:
            st.cache_data.clear()
            st.success("Cache limpo.")
        except Exception:
            st.info("Cache indisponivel nesta versao do Streamlit.")
    if ao_vivo_agora:
        filtro_status = "Ao vivo"
        carregar = True
        datas_escolhidas = [None]

    if esporte == "Tenis":
        st.info(f"Tenis {circuito_tenis} | {filtro_status} | {rotulo_datas(datas_escolhidas)}")
        if carregar_auto or carregar:
            render_tenis(circuito_tenis, datas_escolhidas, filtro_status)
    elif pagina == "Jogos":
        st.info(f"{liga_nome} | {filtro_status} | {rotulo_datas(datas_escolhidas)} | treino minimo: {MIN_JOGOS_TREINO} jogos")
        if carregar_auto or carregar:
            render_jogos(liga_nome, datas_escolhidas, filtro_status)
    elif pagina == "Backtest 24h":
        render_backtest()
    else:
        render_aprendizado()


try:
    main()
except Exception as exc:
    st.error("O app encontrou um erro ao iniciar.")
    st.exception(exc)
