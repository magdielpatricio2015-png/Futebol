import math
import re
import unicodedata
from datetime import datetime

import requests
import streamlit as st

# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

st.set_page_config(
    page_title="Analisador Esportivo Pro 12.2",
    page_icon="⚽",
    layout="wide",
)

# ============================================================
# CONSTANTES
# ============================================================

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

HEADERS = {
    "User-Agent": "AnalisadorEsportivoPro/12.2"
}

RETRIES = 2
MAX_GOLS = 10

DEFAULT_HOME_ADV = 0.25

LIGAS = {
    "Brasileirão Série A": "bra.1",
    "Premier League": "eng.1",
    "La Liga": "esp.1",
    "Serie A": "ita.1",
    "Bundesliga": "ger.1",
    "Ligue 1": "fra.1",
    "Champions League": "uefa.champions",
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
    "manchester city": 91,
    "arsenal": 88,
    "liverpool": 88,
    "chelsea": 82,
    "real madrid": 90,
    "barcelona": 87,
    "bayern munich": 88,
    "psg": 88,
}

ALIASES = {
    "man city": "manchester city",
    "man utd": "manchester united",
    "psg": "paris saint-germain",
    "inter": "inter milan",
    "atletico mineiro": "atletico-mg",
    "vasco da gama": "vasco",
}

# ============================================================
# CSS
# ============================================================

st.markdown(
    """
<style>

.main {
    background-color: #f8fafc;
}

.block-container {
    max-width: 1400px;
    padding-top: 1rem;
}

.hero {
    background: linear-gradient(135deg,#ffffff,#f1f5f9);
    border: 1px solid #dbe2ea;
    padding: 25px;
    border-radius: 18px;
    margin-bottom: 20px;
}

.hero h1 {
    margin: 0;
    font-size: 2rem;
}

.pro-card {
    background: white;
    border-radius: 18px;
    padding: 18px;
    margin-bottom: 18px;
    border: 1px solid #dbe2ea;
    box-shadow: 0 4px 18px rgba(0,0,0,.05);
}

.prob-grid {
    display: grid;
    grid-template-columns: repeat(5,1fr);
    gap: 10px;
    margin-top: 15px;
}

.prob-box {
    background: #f8fafc;
    border-radius: 12px;
    padding: 12px;
    border: 1px solid #e2e8f0;
}

.conf-green {
    color: #16a34a;
    font-weight: bold;
}

.conf-yellow {
    color: #ca8a04;
    font-weight: bold;
}

.conf-red {
    color: #dc2626;
    font-weight: bold;
}

</style>
""",
    unsafe_allow_html=True,
)

# ============================================================
# UTILITÁRIOS
# ============================================================


def nome_limpo(nome):
    return " ".join(str(nome or "").strip().split())


def normalizar(nome):
    nome = nome_limpo(nome).lower()

    nome = unicodedata.normalize("NFKD", nome)

    nome = "".join(
        c for c in nome
        if not unicodedata.combining(c)
    )

    nome = re.sub(r"\b(fc|sc|ec|afc)\b", "", nome)

    nome = re.sub(r"[^a-z0-9\s\-]", "", nome)

    nome = re.sub(r"\s+", " ", nome).strip()

    return ALIASES.get(nome, nome)


def key_time(nome):
    return normalizar(nome)


def parse_dt(valor):
    if not valor:
        return None

    try:
        return (
            datetime
            .fromisoformat(valor.replace("Z", "+00:00"))
            .astimezone()
            .replace(tzinfo=None)
        )
    except Exception:
        return None


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def pct(x):
    return f"{100 * x:.1f}%"


def poisson_pmf(k, media):
    media = max(0.01, media)

    return (
        math.exp(-media)
        * (media ** k)
        / math.factorial(k)
    )


def odd_justa(prob):
    return 1 / max(prob, 0.0001)


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
                timeout=15,
            )

            resp.raise_for_status()

            return resp.json(), ""

        except requests.RequestException as exc:
            ultimo_erro = str(exc)

    return {}, ultimo_erro


@st.cache_data(ttl=240)
def buscar_scoreboard(liga_id):

    url = f"{ESPN_BASE}/{liga_id}/scoreboard"

    payload, err = fetch_with_retry(
        url,
        params={"limit": 100}
    )

    return payload, err


# ============================================================
# EXTRAÇÃO DOS JOGOS
# ============================================================


def extrair_jogos(payload, liga_id):

    jogos = []

    for event in payload.get("events", []):

        comps = event.get("competitions", [])

        if not comps:
            continue

        comp = comps[0]

        competidores = comp.get("competitors", [])

        if len(competidores) < 2:
            continue

        home = next(
            (
                c for c in competidores
                if c.get("homeAway") == "home"
            ),
            competidores[0]
        )

        away = next(
            (
                c for c in competidores
                if c.get("homeAway") == "away"
            ),
            competidores[1]
        )

        status_raw = event.get("status", {})

        status_type = status_raw.get("type", {})

        def placar(c):

            try:
                return int(float(c.get("score", 0)))
            except Exception:
                return 0

        dt = parse_dt(event.get("date"))

        jogos.append({
            "id": str(event.get("id", "")),
            "liga": liga_id,
            "nome": event.get("name", ""),
            "home": nome_limpo(
                home.get("team", {}).get(
                    "displayName",
                    "Casa"
                )
            ),
            "away": nome_limpo(
                away.get("team", {}).get(
                    "displayName",
                    "Fora"
                )
            ),
            "home_score": placar(home),
            "away_score": placar(away),
            "data": dt,
            "status": status_type.get(
                "description",
                ""
            ),
            "status_nome": status_type.get(
                "name",
                ""
            ),
            "em_jogo": (
                status_type.get("state") == "in"
            ),
            "finalizado": (
                status_type.get("state") == "post"
            ),
        })

    return jogos


# ============================================================
# MODELO SIMPLES DE PROBABILIDADE
# ============================================================


def forca_time(nome):

    key = key_time(nome)

    return FORCA_BASE.get(key, 70)


def calcular_probabilidades(home, away):

    fh = forca_time(home)
    fa = forca_time(away)

    diff = fh - fa

    media_home = 1.4 + (diff * 0.02) + DEFAULT_HOME_ADV
    media_away = 1.1 - (diff * 0.015)

    media_home = clamp(media_home, 0.2, 4.0)
    media_away = clamp(media_away, 0.2, 4.0)

    matriz = {}

    p_home = 0
    p_draw = 0
    p_away = 0
    p_over25 = 0
    p_btts = 0

    for gh in range(MAX_GOLS + 1):

        for ga in range(MAX_GOLS + 1):

            p = (
                poisson_pmf(gh, media_home)
                * poisson_pmf(ga, media_away)
            )

            matriz[(gh, ga)] = p

            if gh > ga:
                p_home += p

            elif gh == ga:
                p_draw += p

            else:
                p_away += p

            if (gh + ga) >= 3:
                p_over25 += p

            if gh > 0 and ga > 0:
                p_btts += p

    return {
        "home": clamp(p_home, 0, 1),
        "draw": clamp(p_draw, 0, 1),
        "away": clamp(p_away, 0, 1),
        "over25": clamp(p_over25, 0, 1),
        "btts": clamp(p_btts, 0, 1),
    }


# ============================================================
# UI
# ============================================================

st.markdown(
    """
<div class="hero">
    <h1>⚽ Analisador Esportivo Pro 12.2</h1>
    <p>
        Probabilidades usando Poisson + Força Base + ESPN API
    </p>
</div>
""",
    unsafe_allow_html=True,
)

liga_nome = st.sidebar.selectbox(
    "Escolha a liga",
    list(LIGAS.keys())
)

liga_id = LIGAS[liga_nome]

payload, erro = buscar_scoreboard(liga_id)

if erro:
    st.error(erro)
    st.stop()

jogos = extrair_jogos(payload, liga_id)

if not jogos:
    st.warning("Nenhum jogo encontrado.")
    st.stop()

st.subheader(f"Jogos encontrados: {len(jogos)}")

for jogo in jogos:

    probs = calcular_probabilidades(
        jogo["home"],
        jogo["away"]
    )

    maior = max(
        probs["home"],
        probs["draw"],
        probs["away"]
    )

    if maior >= 0.60:
        conf_class = "conf-green"
        confianca = "ALTA"

    elif maior >= 0.45:
        conf_class = "conf-yellow"
        confianca = "MÉDIA"

    else:
        conf_class = "conf-red"
        confianca = "BAIXA"

    st.markdown(
        f"""
<div class="pro-card">

    <h3>
        {jogo["home"]} x {jogo["away"]}
    </h3>

    <p>
        Status: {jogo["status"]}
    </p>

    <p class="{conf_class}">
        Confiança: {confianca}
    </p>

    <div class="prob-grid">

        <div class="prob-box">
            <b>Casa</b><br>
            {pct(probs["home"])}
        </div>

        <div class="prob-box">
            <b>Empate</b><br>
            {pct(probs["draw"])}
        </div>

        <div class="prob-box">
            <b>Fora</b><br>
            {pct(probs["away"])}
        </div>

        <div class="prob-box">
            <b>Over 2.5</b><br>
            {pct(probs["over25"])}
        </div>

        <div class="prob-box">
            <b>Ambos Marcam</b><br>
            {pct(probs["btts"])}
        </div>

    </div>

</div>
""",
        unsafe_allow_html=True,
    )

st.success("Aplicação carregada com sucesso.")