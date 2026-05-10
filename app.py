import math
import re
import unicodedata
from datetime import datetime

import requests
import streamlit as st


# ============================================================
# CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="Analisador Esportivo Pro",
    page_icon="⚽",
    layout="wide",
)

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
HEADERS = {"User-Agent": "AnalisadorEsportivoPro/12.2"}

MAX_GOLS = 10
RETRIES = 2
DEFAULT_HOME_ADV = 0.25


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


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
<style>
    .block-container {
        max-width: 1450px;
        padding-top: 1rem;
    }

    .hero {
        background: linear-gradient(135deg, #ffffff, #f1f5f9);
        border: 1px solid #d7dce2;
        border-radius: 18px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
    }

    .hero h1 {
        margin: 0;
        font-size: 2rem;
        font-weight: 900;
        color: #0f172a;
    }

    .hero p {
        color: #475569;
        margin-top: 8px;
    }

    .pro-card {
        border: 1px solid #d7dce2;
        border-radius: 16px;
        padding: 18px;
        margin: 14px 0;
        background: #ffffff;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
    }

    .match-title {
        font-size: 1.2rem;
        font-weight: 900;
        color: #0f172a;
        margin-bottom: 5px;
    }

    .match-status {
        color: #64748b;
        margin-bottom: 10px;
    }

    .confidence {
        display: inline-block;
        padding: 6px 12px;
        border-radius: 999px;
        color: white;
        font-weight: 800;
        font-size: 0.82rem;
        margin-bottom: 14px;
    }

    .green {
        background: #16a34a;
    }

    .amber {
        background: #ca8a04;
    }

    .red {
        background: #dc2626;
    }

    .prob-grid {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 10px;
        margin-top: 12px;
    }

    .prob-box {
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 12px;
        background: #f8fafc;
    }

    .prob-box span {
        display: block;
        color: #64748b;
        font-size: 0.82rem;
        margin-bottom: 4px;
    }

    .prob-box strong {
        font-size: 1.08rem;
        color: #0f172a;
    }

    @media (max-width: 900px) {
        .prob-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
    }
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# FUNÇÕES
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

    return fetch_with_retry(
        f"{ESPN_BASE}/{liga_id}/scoreboard",
        params,
    )


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
                "nome": event.get("name", ""),
                "home": nome_limpo(
                    home.get("team", {}).get("displayName", "Casa")
                ),
                "away": nome_limpo(
                    away.get("team", {}).get("displayName", "Fora")
                ),
                "home_score": placar(home),
                "away_score": placar(away),
                "data": dt,
                "status": status_type.get("description", ""),
                "status_nome": status_type.get("name", ""),
                "em_jogo": status_type.get("state") == "in",
                "finalizado": status_type.get("state") == "post",
            }
        )

    return jogos


def forca_time(nome):
    return FORCA_BASE.get(normalizar(nome), 70)


def calcular_probabilidades(home, away):
    fh = forca_time(home)
    fa = forca_time(away)

    diff = fh - fa

    media_home = 1.4 + (diff * 0.02) + DEFAULT_HOME_ADV
    media_away = 1.1 - (diff * 0.015)

    media_home = clamp(media_home, 0.2, 4.0)
    media_away = clamp(media_away, 0.2, 4.0)

    p_home = 0
    p_draw = 0
    p_away = 0
    p_over25 = 0
    p_btts = 0

    for gh in range(MAX_GOLS + 1):
        for ga in range(MAX_GOLS + 1):
            p = poisson_pmf(gh, media_home) * poisson_pmf(ga, media_away)

            if gh > ga:
                p_home += p
            elif gh == ga:
                p_draw += p
            else:
                p_away += p

            if gh + ga >= 3:
                p_over25 += p

            if gh > 0 and ga > 0:
                p_btts += p

    return {
        "home": clamp(p_home, 0, 1),
        "draw": clamp(p_draw, 0, 1),
        "away": clamp(p_away, 0, 1),
        "over25": clamp(p_over25, 0, 1),
        "btts": clamp(p_btts, 0, 1),
        "odd_home": odd_justa(p_home),
        "odd_draw": odd_justa(p_draw),
        "odd_away": odd_justa(p_away),
    }


# ============================================================
# INTERFACE
# ============================================================

st.markdown(
    """
<div class="hero">
    <h1>⚽ Analisador Esportivo Pro</h1>
    <p>Probabilidades com ESPN API + modelo Poisson simples.</p>
</div>
""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Filtros")

    liga_nome = st.selectbox(
        "Liga",
        list(LIGAS.keys()),
    )

    usar_data = st.checkbox("Filtrar por data")

    data_escolhida = None

    if usar_data:
        data_escolhida = st.date_input("Data").isoformat()

    st.info("Depois de alterar filtros, aguarde carregar os jogos.")


liga_id = LIGAS[liga_nome]

with st.spinner("Buscando jogos na ESPN..."):
    payload, erro = buscar_scoreboard(liga_id, data_escolhida)

if erro:
    st.error(erro)
    st.stop()

jogos = extrair_jogos(payload, liga_id)

if not jogos:
    st.warning("Nenhum jogo encontrado para essa liga/data.")
    st.stop()

st.subheader(f"{liga_nome} — {len(jogos)} jogo(s) encontrado(s)")

for jogo in jogos:
    probs = calcular_probabilidades(jogo["home"], jogo["away"])

    maior = max(probs["home"], probs["draw"], probs["away"])

    if maior >= 0.60:
        conf_class = "green"
        confianca = "ALTA"
    elif maior >= 0.45:
        conf_class = "amber"
        confianca = "MÉDIA"
    else:
        conf_class = "red"
        confianca = "BAIXA"

    data_txt = ""
    if jogo["data"]:
        data_txt = jogo["data"].strftime("%d/%m/%Y %H:%M")

    placar_txt = ""
    if jogo["finalizado"] or jogo["em_jogo"]:
        placar_txt = f" — {jogo['home_score']} x {jogo['away_score']}"

    st.markdown(
        f"""
<div class="pro-card">
    <div class="match-title">
        {jogo["home"]} x {jogo["away"]}{placar_txt}
    </div>

    <div class="match-status">
        Status: {jogo["status"]} &nbsp; | &nbsp; {data_txt}
    </div>

    <div class="confidence {conf_class}">
        Confiança: {confianca}
    </div>

    <div class="prob-grid">
        <div class="prob-box">
            <span>Casa</span>
            <strong>{pct(probs["home"])}</strong><br>
            Odd justa: {probs["odd_home"]:.2f}
        </div>

        <div class="prob-box">
            <span>Empate</span>
            <strong>{pct(probs["draw"])}</strong><br>
            Odd justa: {probs["odd_draw"]:.2f}
        </div>

        <div class="prob-box">
            <span>Fora</span>
            <strong>{pct(probs["away"])}</strong><br>
            Odd justa: {probs["odd_away"]:.2f}
        </div>

        <div class="prob-box">
            <span>Over 2.5</span>
            <strong>{pct(probs["over25"])}</strong>
        </div>

        <div class="prob-box">
            <span>Ambos Marcam</span>
            <strong>{pct(probs["btts"])}</strong>
        </div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

st.success("Aplicação carregada corretamente.")