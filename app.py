import math
import re
import unicodedata
from datetime import datetime, timedelta

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
HEADERS = {"User-Agent": "AnalisadorEsportivoPro/12.2"}

MAX_GOLS = 10
RETRIES = 2

DEFAULT_HOME_ADV = 70
DEFAULT_RHO_DC = -0.08
ELO_BASE = 1700


LIGAS = {
    "Brasileirão Série A": "bra.1",
    "Brasileirão Série B": "bra.2",
    "Copa do Brasil": "bra.copa_do_brasil",
    "Libertadores": "conmebol.libertadores",
    "Sul-Americana": "conmebol.sudamericana",
    "Premier League": "eng.1",
    "La Liga": "esp.1",
    "Serie A (Itália)": "ita.1",
    "Bundesliga": "ger.1",
    "Ligue 1": "fra.1",
    "Champions League": "uefa.champions",
    "Europa League": "uefa.europa",
}


FORCA_BASE = {
    "Flamengo": 86,
    "Palmeiras": 84,
    "Botafogo": 79,
    "Atletico-MG": 76,
    "Sao Paulo": 78,
    "Fluminense": 77,
    "Gremio": 74,
    "Internacional": 75,
    "Corinthians": 76,
    "Cruzeiro": 73,
    "Bahia": 74,
    "Fortaleza": 73,
    "Vasco": 70,
    "Santos": 72,
    "Ceara": 69,
    "Sport": 68,
    "Vitoria": 69,
    "Manchester City": 91,
    "Arsenal": 88,
    "Liverpool": 88,
    "Chelsea": 82,
    "Tottenham Hotspur": 80,
    "Manchester United": 81,
    "Real Madrid": 90,
    "Barcelona": 87,
    "Atletico Madrid": 84,
    "Bayern Munich": 88,
    "Borussia Dortmund": 82,
    "Bayer Leverkusen": 84,
    "Inter Milan": 86,
    "Juventus": 82,
    "Milan": 81,
    "PSG": 88,
    "Paris Saint-Germain": 88,
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
# CSS
# ============================================================

st.markdown(
    """
<style>
    .main {
        background-color: #f8fafc;
        color: #111827;
    }

    .block-container {
        padding-top: 1.2rem;
        max-width: 1450px;
    }

    section[data-testid="stSidebar"] {
        background: #eef2f7;
        border-right: 1px solid #d7dce2;
    }

    .hero {
        border: 1px solid #d7dce2;
        background: linear-gradient(135deg, #ffffff 0%, #f1f5f9 100%);
        border-radius: 18px;
        padding: 24px 26px;
        margin-bottom: 20px;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
    }

    .hero h1 {
        margin: 0;
        font-size: 2.15rem;
        font-weight: 900;
        letter-spacing: -0.03em;
        color: #0f172a;
    }

    .hero p {
        margin: 8px 0 0;
        color: #475569;
        font-size: 1rem;
    }

    .section-title {
        font-size: 1.25rem;
        font-weight: 900;
        color: #0f172a;
        margin: 16px 0 8px;
    }

    .pro-card {
        border: 1px solid #d7dce2;
        border-radius: 16px;
        padding: 18px 20px;
        margin: 14px 0;
        background: #ffffff;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
    }

    .pro-card.live {
        border-left: 7px solid #2563eb;
    }

    .pro-card-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 16px;
        margin-bottom: 14px;
    }

    .match-title {
        font-size: 1.18rem;
        font-weight: 900;
        color: #0f172a;
    }

    .match-subtitle {
        color: #64748b;
        font-size: 0.88rem;
        margin-top: 4px;
    }

    .confidence {
        padding: 6px 12px;
        border-radius: 999px;
        color: white;
        font-size: 0.82rem;
        font-weight: 800;
        white-space: nowrap;
    }

    .confidence.green {
        background: #16a34a;
    }

    .confidence.amber {
        background: #ca8a04;
    }

    .confidence.red {
        background: #dc2626;
    }

    .market-highlight {
        border-radius: 12px;
        background: #f1f5f9;
        border: 1px solid #e2e8f0;
        padding: 10px 12px;
        margin-bottom: 14px;
        color: #334155;
    }

    .prob-grid {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 10px;
        margin-bottom: 12px;
    }

    .prob-grid div {
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 10px;
        background: #ffffff;
    }

    .prob-grid span {
        display: block;
        font-size: 0.78rem;
        color: #64748b;
        margin-bottom: 3px;
    }

    .prob-grid strong {
        font-size: 1rem;
        color: #0f172a;
    }

    .card-footer {
        font-size: 0.88rem;
        color: #475569;
        border-top: 1px solid #e2e8f0;
        padding-top: 10px;
        line-height: 1.6;
    }

    .live-badge {
        background: #dc2626;
        color: white;
        padding: 3px 8px;
        border-radius: 999px;
        font-weight: 800;
        font-size: 0.72rem;
        margin-left: 8px;
    }

    .pill {
        display: inline-block;
        padding: 4px 9px;
        margin: 4px 5px 0 0;
        border-radius: 999px;
        background: #eef2f7;
        border: 1px solid #d7dce2;
        font-size: .84rem;
        color: #334155;
    }

    .form-badge {
        display: inline-block;
        width: 22px;
        height: 22px;
        line-height: 22px;
        text-align: center;
        border-radius: 6px;
        font-size: 0.78rem;
        font-weight: 900;
        margin-right: 3px;
        color: white;
    }

    .form-v {
        background: #16a34a;
    }

    .form-e {
        background: #eab308;
    }

    .form-d {
        background: #dc2626;
    }

    @media (max-width: 900px) {
        .prob-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }

        .pro-card-header {
            flex-direction: column;
        }
    }
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# UTILITÁRIOS
# ============================================================

def hoje():
    return datetime.now().date()


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


def key_time(nome):
    return normalizar(nome)


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
    return 1 / max(prob, 0.0001)


def prob_over_poisson(media, linha):
    corte = int(math.floor(linha))
    return clamp(
        1 - sum(poisson_pmf(k, media) for k in range(corte + 1)),
        0.0,
        1.0,
    )


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


@st.cache_data(ttl=3600, show_spinner=False)
def buscar_classificacao(liga_id):
    url = f"{ESPN_BASE}/{liga_id}/standings"
    payload, err = fetch_with_retry(url)

    if err or not payload:
        return {}

    tabela = {}

    try:
        grupos = payload.get("children", []) or [payload]

        for group in grupos:
            standings = group.get("standings", {})
            entries = standings.get("entries", []) if isinstance(standings, dict) else []

            for entry in entries:
                time_nome = entry.get("team", {}).get("displayName", "")
                time_nome_limpo = nome_limpo(time_nome)
                pos = entry.get("rank", 99)

                if pos == 99:
                    stats_list = entry.get("stats", [{}])
                    if stats_list:
                        pos = int(stats_list[0].get("value", 99))

                tabela[key_time(time_nome_limpo)] = {
                    "posicao": pos,
                    "time_original": time_nome_limpo,
                }
    except Exception:
        pass

    return tabela


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
                "home": nome_limpo(home.get("team", {}).get("displayName", "Casa")),
                "away": nome_limpo(away.get("team", {}).get("displayName", "Fora")),
                "placar_home": placar(home),
                "placar_away": placar(away),
                "placar": f"{placar(home
