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
    page_title="Analisador Esportivo Pro",
    page_icon="⚽",
    layout="wide",
)

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
HEADERS = {"User-Agent": "AnalisadorEsportivoPro/13.0"}

MAX_GOLS = 10
RETRIES = 2
DEFAULT_HOME_ADV = 0.25
DB_PATH = "data/modelo.db"


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
# BANCO DE DADOS
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
            mercado TEXT,
            prob_mercado REAL,
            odd_justa REAL,
            confianca TEXT,
            prob_home REAL,
            prob_draw REAL,
            prob_away REAL,
            prob_over15 REAL,
            prob_over25 REAL,
            prob_under25 REAL,
            prob_btts REAL,
            placar_previsto TEXT,
            home_score INTEGER,
            away_score INTEGER,
            resultado_real TEXT,
            acertou INTEGER,
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


def salvar_previsao(jogo, liga_nome, probs, mercado, prob_mercado, confianca, placar_previsto):
    conn = conectar_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR IGNORE INTO previsoes (
            game_id, liga_id, liga_nome, data_jogo, home, away,
            mercado, prob_mercado, odd_justa, confianca,
            prob_home, prob_draw, prob_away,
            prob_over15, prob_over25, prob_under25, prob_btts,
            placar_previsto, finalizado, criado_em
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            jogo["id"],
            jogo["liga"],
            liga_nome,
            jogo["data"].isoformat() if jogo["data"] else "",
            jogo["home"],
            jogo["away"],
            mercado,
            float(prob_mercado),
            float(odd_justa(prob_mercado)),
            confianca,
            float(probs["home"]),
            float(probs["draw"]),
            float(probs["away"]),
            float(probs["over15"]),
            float(probs["over25"]),
            float(probs["under25"]),
            float(probs["btts"]),
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

    resultado = resultado_real(jogo["home_score"], jogo["away_score"])
    mercado = obter_mercado_salvo(jogo["id"])
    acertou = int(verificar_acerto(mercado, jogo["home_score"], jogo["away_score"])) if mercado else 0

    cur.execute(
        """
        UPDATE previsoes
        SET home_score = ?,
            away_score = ?,
            resultado_real = ?,
            acertou = ?,
            finalizado = 1
        WHERE game_id = ?
        """,
        (
            jogo["home_score"],
            jogo["away_score"],
            resultado,
            acertou,
            jogo["id"],
        ),
    )

    conn.commit()
    conn.close()


def obter_mercado_salvo(game_id):
    conn = conectar_db()
    cur = conn.cursor()

    cur.execute("SELECT mercado FROM previsoes WHERE game_id = ?", (game_id,))
    row = cur.fetchone()

    conn.close()

    return row[0] if row else None


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
# FUNÇÕES GERAIS
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


def resultado_real(home_score, away_score):
    if home_score > away_score:
        return "home"
    if home_score < away_score:
        return "away"
    return "draw"


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

        dt = parse_dt(event.get("date"))

        jogos.append(
            {
                "id": str(event.get("id", "")),
                "liga": liga_id,
                "home": nome_limpo(home.get("team", {}).get("displayName", "Casa")),
                "away": nome_limpo(away.get("team", {}).get("displayName", "Fora")),
                "home_score": placar(home),
                "away_score": placar(away),
                "data": dt,
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

def obter_fator_aprendizado(liga_id, mercado, home, away):
    conn = conectar_db()
    cur = conn.cursor()

    chaves = [
        f"liga:{liga_id}|mercado:{mercado}",
        f"mercado:{mercado}",
    ]

    if eh_classico(home, away):
        chaves.append("contexto:classico")

    fator_total = 0.0

    for chave in chaves:
        cur.execute("SELECT fator FROM ajustes WHERE chave = ?", (chave,))
        row = cur.fetchone()
        if row:
            fator_total += float(row[0])

    conn.close()
    return clamp(fator_total, -0.12, 0.12)


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

    p_home = 0
    p_draw = 0
    p_away = 0
    p_over15 = 0
    p_over25 = 0
    p_over35 = 0
    p_under25 = 0
    p_btts = 0

    placares = []

    for gh in range(MAX_GOLS + 1):
        for ga in range(MAX_GOLS + 1):
            p = poisson_pmf(gh, media_home) * poisson_pmf(ga, media_away)

            placares.append((gh, ga, p))

            if gh > ga:
                p_home += p
            elif gh == ga:
                p_draw += p
            else:
                p_away += p

            total = gh + ga

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

    dupla_1x = p_home + p_draw
    dupla_x2 = p_draw + p_away
    dupla_12 = p_home + p_away

    return {
        "home": clamp(p_home, 0, 1),
        "draw": clamp(p_draw, 0, 1),
        "away": clamp(p_away, 0, 1),
        "over15": clamp(p_over15, 0, 1),
        "over25": clamp(p_over25, 0, 1),
        "over35": clamp(p_over35, 0, 1),
        "under25": clamp(p_under25, 0, 1),
        "btts": clamp(p_btts, 0, 1),
        "dupla_1x": clamp(dupla_1x, 0, 1),
        "dupla_x2": clamp(dupla_x2, 0, 1),
        "dupla_12": clamp(dupla_12, 0, 1),
        "media_home": media_home,
        "media_away": media_away,
        "forca_home": fh,
        "forca_away": fa,
        "placares": placares[:5],
    }


def melhor_mercado_base(probs, home, away):
    mercados = [
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

    return sorted(mercados, key=lambda x: x[2], reverse=True)


def melhor_mercado_aprendido(probs, jogo):
    mercados = melhor_mercado_base(probs, jogo["home"], jogo["away"])

    ajustados = []

    for nome, codigo, prob in mercados:
        fator = obter_fator_aprendizado(jogo["liga"], codigo, jogo["home"], jogo["away"])
        prob_ajustada = clamp(prob + fator, 0.01, 0.99)
        ajustados.append((nome, codigo, prob_ajustada, fator, prob))

    return sorted(ajustados, key=lambda x: x[2], reverse=True)[0]


def verificar_acerto(mercado, home_score, away_score):
    if not mercado:
        return False

    total = home_score + away_score
    ambos = home_score > 0 and away_score > 0

    if "vence" in mercado:
        if home_score > away_score and not mercado.startswith("Empate"):
            return True
        if away_score > home_score and not mercado.startswith("Empate"):
            return True

    if mercado == "Empate":
        return home_score == away_score

    if mercado == "Dupla chance 1X":
        return home_score >= away_score

    if mercado == "Dupla chance X2":
        return away_score >= home_score

    if mercado == "Dupla chance 12":
        return home_score != away_score

    if mercado == "Over 1.5 gols":
        return total >= 2

    if mercado == "Over 2.5 gols":
        return total >= 3

    if mercado == "Under 2.5 gols":
        return total <= 2

    if mercado == "Ambos marcam":
        return ambos

    return False


def treinar_modelo():
    df = carregar_previsoes()

    if df.empty:
        return 0

    df = df[df["finalizado"] == 1].copy()

    if df.empty:
        return 0

    treinados = 0

    for mercado_codigo, mercado_nome in [
        ("home", "vence"),
        ("draw", "Empate"),
        ("dupla_1x", "Dupla chance 1X"),
        ("dupla_x2", "Dupla chance X2"),
        ("dupla_12", "Dupla chance 12"),
        ("over15", "Over 1.5 gols"),
        ("over25", "Over 2.5 gols"),
        ("under25", "Under 2.5 gols"),
        ("btts", "Ambos marcam"),
    ]:
        if mercado_nome == "vence":
            sub = df[df["mercado"].str.contains("vence", na=False)]
        else:
            sub = df[df["mercado"] == mercado_nome]

        jogos = len(sub)

        if jogos >= 3:
            acertos = int(sub["acertou"].sum())
            taxa = acertos / jogos

            fator = clamp((taxa - 0.55) * 0.18, -0.08, 0.08)
            salvar_ajuste(f"mercado:{mercado_codigo}", fator, jogos, acertos)
            treinados += 1

    for liga_id in df["liga_id"].dropna().unique():
        df_liga = df[df["liga_id"] == liga_id]

        for mercado in df_liga["mercado"].dropna().unique():
            sub = df_liga[df_liga["mercado"] == mercado]
            jogos = len(sub)

            if jogos >= 3:
                acertos = int(sub["acertou"].sum())
                taxa = acertos / jogos
                codigo = mercado_para_codigo(mercado)

                fator = clamp((taxa - 0.55) * 0.14, -0.06, 0.06)
                salvar_ajuste(f"liga:{liga_id}|mercado:{codigo}", fator, jogos, acertos)
                treinados += 1

    return treinados


def mercado_para_codigo(mercado):
    if mercado == "Empate":
        return "draw"
    if mercado == "Dupla chance 1X":
        return "dupla_1x"
    if mercado == "Dupla chance X2":
        return "dupla_x2"
    if mercado == "Dupla chance 12":
        return "dupla_12"
    if mercado == "Over 1.5 gols":
        return "over15"
    if mercado == "Over 2.5 gols":
        return "over25"
    if mercado == "Under 2.5 gols":
        return "under25"
    if mercado == "Ambos marcam":
        return "btts"
    if "vence" in mercado:
        return "home"
    return "outro"


# ============================================================
# APP
# ============================================================

init_db()

st.title("⚽ Analisador Esportivo Pro 13.0")
st.caption("ESPN API + Poisson + odds justas + backtest 24h + aprendizado automático.")

aba_jogos, aba_backtest, aba_aprendizado = st.tabs(
    ["Jogos", "Backtest 24h", "Aprendizado"]
)


with st.sidebar:
    st.header("Filtros")

    liga_nome = st.selectbox("Liga", list(LIGAS.keys()))

    usar_data = st.checkbox("Filtrar por data")
    data_escolhida = None

    if usar_data:
        data_escolhida = st.date_input("Data").isoformat()

    filtro_status = st.selectbox(
        "Status",
        ["Todos", "Ao vivo", "Futuros", "Finalizados"],
    )

    if st.button("Atualizar dados"):
        st.cache_data.clear()
        st.rerun()


with aba_jogos:
    liga_id = LIGAS[liga_nome]

    with st.spinner("Buscando jogos na ESPN..."):
        payload, erro = buscar_scoreboard(liga_id, data_escolhida)

    if erro:
        st.error(erro)
        st.stop()

    jogos = extrair_jogos(payload, liga_id)

    if filtro_status == "Ao vivo":
        jogos = [j for j in jogos if j["em_jogo"]]
    elif filtro_status == "Futuros":
        jogos = [j for j in jogos if j["futuro"]]
    elif filtro_status == "Finalizados":
        jogos = [j for j in jogos if j["finalizado"]]

    if not jogos:
        st.warning("Nenhum jogo encontrado para os filtros escolhidos.")
    else:
        st.subheader(f"{liga_nome} — {len(jogos)} jogo(s) encontrado(s)")

        resumo = []

        for jogo in jogos:
            probs = calcular_probabilidades(jogo["home"], jogo["away"])
            mercado, codigo, prob_mercado, fator, prob_original = melhor_mercado_aprendido(probs, jogo)

            confianca = nivel_confianca(prob_mercado)

            placar_top = probs["placares"][0]
            placar_previsto = f"{placar_top[0]} x {placar_top[1]}"

            salvar_previsao(
                jogo,
                liga_nome,
                probs,
                mercado,
                prob_mercado,
                confianca,
                placar_previsto,
            )

            if jogo["finalizado"]:
                atualizar_resultado(jogo)

            placar_txt = ""
            if jogo["finalizado"] or jogo["em_jogo"]:
                placar_txt = f" — {jogo['home_score']} x {jogo['away_score']}"

            data_txt = "Data não informada"
            if jogo["data"]:
                data_txt = jogo["data"].strftime("%d/%m/%Y %H:%M")

            resumo.append(
                {
                    "Jogo": f"{jogo['home']} x {jogo['away']}",
                    "Status": status_label(jogo),
                    "Mercado": mercado,
                    "Prob. ajustada": pct(prob_mercado),
                    "Ajuste": f"{fator:+.1%}",
                    "Confiança": confianca,
                }
            )

            with st.container(border=True):
                st.markdown(f"### {jogo['home']} x {jogo['away']}{placar_txt}")
                st.write(f"**Status:** {status_label(jogo)}")
                st.write(f"**Data:** {data_txt}")

                if eh_classico(jogo["home"], jogo["away"]):
                    st.warning("Clássico detectado: modelo aplicou cautela.")

                st.info(
                    f"🎯 Melhor mercado: **{mercado}** — "
                    f"{pct(prob_mercado)} | Confiança: **{confianca}** | "
                    f"Ajuste aprendido: **{fator:+.1%}**"
                )

                c1, c2, c3 = st.columns(3)
                c1.metric("Força casa", probs["forca_home"])
                c2.metric("Força fora", probs["forca_away"])
                c3.metric("Placar provável", placar_previsto)

                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("Casa", pct(probs["home"]), f"Odd {odd_justa(probs['home']):.2f}")
                c2.metric("Empate", pct(probs["draw"]), f"Odd {odd_justa(probs['draw']):.2f}")
                c3.metric("Fora", pct(probs["away"]), f"Odd {odd_justa(probs['away']):.2f}")
                c4.metric("Over 2.5", pct(probs["over25"]), f"Odd {odd_justa(probs['over25']):.2f}")
                c5.metric("BTTS", pct(probs["btts"]), f"Odd {odd_justa(probs['btts']):.2f}")

                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("Over 1.5", pct(probs["over15"]))
                c2.metric("Over 3.5", pct(probs["over35"]))
                c3.metric("Under 2.5", pct(probs["under25"]))
                c4.metric("Dupla 1X", pct(probs["dupla_1x"]))
                c5.metric("Dupla X2", pct(probs["dupla_x2"]))

        st.subheader("Resumo")
        st.dataframe(pd.DataFrame(resumo), use_container_width=True, hide_index=True)


with aba_backtest:
    st.subheader("📊 Backtest — Últimas 24h")

    if st.button("Rodar backtest 24h"):
        with st.spinner("Buscando jogos finalizados das últimas 24h..."):
            jogos_24h = buscar_jogos_ultimas_24h()

        finalizados = [j for j in jogos_24h if j["finalizado"]]

        linhas = []

        for jogo in finalizados:
            probs = calcular_probabilidades(jogo["home"], jogo["away"])
            mercado, codigo, prob_mercado, fator, prob_original = melhor_mercado_aprendido(probs, jogo)

            acertou = verificar_acerto(mercado, jogo["home_score"], jogo["away_score"])

            salvar_previsao(
                jogo,
                jogo.get("liga_nome", jogo["liga"]),
                probs,
                mercado,
                prob_mercado,
                nivel_confianca(prob_mercado),
                f"{probs['placares'][0][0]} x {probs['placares'][0][1]}",
            )
            atualizar_resultado(jogo)

            linhas.append(
                {
                    "Liga": jogo.get("liga_nome", jogo["liga"]),
                    "Jogo": f"{jogo['home']} x {jogo['away']}",
                    "Placar": f"{jogo['home_score']} x {jogo['away_score']}",
                    "Mercado": mercado,
                    "Probabilidade": pct(prob_mercado),
                    "Confiança": nivel_confianca(prob_mercado),
                    "Resultado": "✅ Acerto" if acertou else "❌ Erro",
                }
            )

        if not linhas:
            st.warning("Nenhum jogo finalizado encontrado nas últimas 24h.")
        else:
            df_bt = pd.DataFrame(linhas)
            acertos = df_bt["Resultado"].str.contains("Acerto").sum()
            total = len(df_bt)
            taxa = acertos / total if total else 0

            c1, c2, c3 = st.columns(3)
            c1.metric("Jogos analisados", total)
            c2.metric("Acertos", acertos)
            c3.metric("Acurácia", pct(taxa))

            st.dataframe(df_bt, use_container_width=True, hide_index=True)

            por_mercado = (
                df_bt.assign(Acertou=df_bt["Resultado"].str.contains("Acerto"))
                .groupby("Mercado")
                .agg(Jogos=("Jogo", "count"), Acertos=("Acertou", "sum"))
                .reset_index()
            )
            por_mercado["Taxa"] = por_mercado["Acertos"] / por_mercado["Jogos"]
            por_mercado["Taxa"] = por_mercado["Taxa"].apply(pct)

            st.subheader("Desempenho por mercado")
            st.dataframe(por_mercado, use_container_width=True, hide_index=True)


with aba_aprendizado:
    st.subheader("🧠 Aprendizado do Modelo")

    df = carregar_previsoes()

    if df.empty:
        st.info("Ainda não há previsões salvas. Acesse a aba Jogos ou rode o Backtest 24h.")
    else:
        finalizados = df[df["finalizado"] == 1]

        c1, c2, c3 = st.columns(3)
        c1.metric("Previsões salvas", len(df))
        c2.metric("Jogos finalizados", len(finalizados))

        if len(finalizados) > 0:
            taxa = finalizados["acertou"].fillna(0).sum() / len(finalizados)
            c3.metric("Acurácia histórica", pct(taxa))
        else:
            c3.metric("Acurácia histórica", "0.0%")

        if st.button("Treinar com histórico salvo"):
            qtd = treinar_modelo()
            st.success(f"Treinamento concluído. Ajustes atualizados: {qtd}")
            st.rerun()

        st.subheader("Histórico de previsões")
        st.dataframe(df, use_container_width=True, hide_index=True)

        ajustes = carregar_ajustes()

        st.subheader("Ajustes aprendidos")
        if ajustes.empty:
            st.info("Nenhum ajuste aprendido ainda. Rode o treinamento após ter jogos finalizados.")
        else:
            st.dataframe(ajustes, use_container_width=True, hide_index=True)