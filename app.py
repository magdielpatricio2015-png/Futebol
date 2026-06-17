from __future__ import annotations

import hashlib
import json
import math
import random
import re
import unicodedata
from datetime import datetime, timedelta
from difflib import get_close_matches
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import requests
import streamlit as st


# ============================================================
# CONFIGURAÇÃO
# ============================================================

APP_TITLE = "Previsor de Futebol"
APP_ICON = "⚽"
APP_TZ_NAME = "America/Sao_Paulo"
APP_TZ = ZoneInfo(APP_TZ_NAME)

API_BASE = "https://v3.football.api-sports.io"
CACHE_TTL_SECONDS = 30 * 60
REQUEST_TIMEOUT_SECONDS = 15

DEFAULT_RATING = 75.0
DEFAULT_SIMULATIONS = 20_000


st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# ESTILO
# ============================================================

st.markdown(
    """
    <style>
    .main-title {
        text-align: center;
        font-size: 2.8rem;
        font-weight: 900;
        margin: 0.8rem 0 0.2rem 0;
    }

    .main-subtitle {
        text-align: center;
        opacity: 0.75;
        font-size: 1.05rem;
        margin-bottom: 2rem;
    }

    .soft-card {
        padding: 1.1rem 1.25rem;
        border-radius: 1rem;
        border: 1px solid rgba(128, 128, 128, 0.18);
        background: var(--secondary-background-color);
        margin-bottom: 0.75rem;
    }

    .small-muted {
        opacity: 0.7;
        font-size: 0.88rem;
    }

    .team-line {
        font-size: 1.08rem;
        font-weight: 800;
    }

    .league-line {
        color: #3b82f6;
        font-weight: 700;
        margin-top: 0.25rem;
    }

    .danger-box {
        border-left: 5px solid #ef4444;
        padding: 0.8rem 1rem;
        background: rgba(239, 68, 68, 0.08);
        border-radius: 0.5rem;
    }

    .ok-box {
        border-left: 5px solid #22c55e;
        padding: 0.8rem 1rem;
        background: rgba(34, 197, 94, 0.08);
        border-radius: 0.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-title">⚽ Previsor de Futebol com API Real</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="main-subtitle">Jogos reais da API-Football + ratings locais + simulação Monte Carlo</div>',
    unsafe_allow_html=True,
)


# ============================================================
# ESTADO DA SESSÃO
# ============================================================

if "fixtures" not in st.session_state:
    st.session_state.fixtures = []

if "fixtures_error" not in st.session_state:
    st.session_state.fixtures_error = None

if "last_search_summary" not in st.session_state:
    st.session_state.last_search_summary = None

if "prediction_fixture_label" not in st.session_state:
    st.session_state.prediction_fixture_label = "Inserir manualmente"

if "custom_ratings" not in st.session_state:
    st.session_state.custom_ratings = {}


# ============================================================
# RATINGS BASE
# Ajuste livremente. O app também permite adicionar ratings
# customizados pela interface.
# ============================================================

BASE_TEAM_RATINGS: Dict[str, float] = {
    # Brasil
    "Flamengo": 87.5,
    "Palmeiras": 88.5,
    "Botafogo": 84.5,
    "Fluminense": 82.0,
    "São Paulo": 82.5,
    "Sao Paulo": 82.5,
    "Corinthians": 80.0,
    "Santos": 78.5,
    "Grêmio": 81.0,
    "Gremio": 81.0,
    "Internacional": 81.0,
    "Atlético Mineiro": 84.0,
    "Atletico-MG": 84.0,
    "Atletico Mineiro": 84.0,
    "Cruzeiro": 79.5,
    "Bahia": 79.0,
    "Vasco da Gama": 77.5,
    "Vasco DA Gama": 77.5,
    "Fortaleza": 80.0,
    "Fortaleza EC": 80.0,
    "Athletico-PR": 80.5,
    "Athletico Paranaense": 80.5,
    "RB Bragantino": 79.0,
    "Ceará": 76.0,
    "Ceara": 76.0,
    "Vitória": 75.5,
    "Vitoria": 75.5,
    "Juventude": 75.0,
    "Sport Recife": 74.0,
    "Mirassol": 74.5,

    # Argentina / América do Sul
    "River Plate": 84.0,
    "Boca Juniors": 83.0,
    "Racing Club": 80.0,
    "Independiente": 78.5,
    "Estudiantes L.P.": 79.5,
    "San Lorenzo": 78.5,
    "Nacional": 78.0,
    "Penarol": 78.0,
    "Colo Colo": 77.0,
    "LDU de Quito": 78.0,

    # Inglaterra
    "Manchester City": 94.0,
    "Arsenal": 91.0,
    "Liverpool": 91.5,
    "Chelsea": 86.0,
    "Manchester United": 84.5,
    "Tottenham": 85.5,
    "Newcastle": 84.0,
    "Aston Villa": 84.0,
    "Brighton": 82.0,
    "West Ham": 80.0,

    # Espanha
    "Real Madrid": 94.0,
    "Barcelona": 91.0,
    "Atletico Madrid": 88.0,
    "Atlético Madrid": 88.0,
    "Athletic Club": 84.0,
    "Real Sociedad": 84.0,
    "Villarreal": 82.0,
    "Sevilla": 80.0,
    "Real Betis": 81.0,

    # Itália
    "Inter": 90.5,
    "Inter Milan": 90.5,
    "AC Milan": 87.5,
    "Juventus": 87.5,
    "Napoli": 86.5,
    "Atalanta": 86.0,
    "Roma": 84.0,
    "Lazio": 83.0,
    "Fiorentina": 82.0,

    # Alemanha
    "Bayern München": 92.0,
    "Bayern Munich": 92.0,
    "Borussia Dortmund": 87.5,
    "Bayer Leverkusen": 90.0,
    "RB Leipzig": 86.5,
    "Eintracht Frankfurt": 82.0,
    "VfB Stuttgart": 82.0,

    # França / Portugal / Holanda
    "Paris Saint Germain": 91.0,
    "PSG": 91.0,
    "Marseille": 83.0,
    "Monaco": 84.0,
    "Lyon": 81.0,
    "Benfica": 85.0,
    "FC Porto": 84.0,
    "Sporting CP": 85.0,
    "Ajax": 81.0,
    "PSV Eindhoven": 84.0,
    "Feyenoord": 83.0,
}


TEAM_ALIASES: Dict[str, str] = {
    "PSG": "Paris Saint Germain",
    "Man City": "Manchester City",
    "Man United": "Manchester United",
    "Manchester Utd": "Manchester United",
    "Spurs": "Tottenham",
    "Bayern": "Bayern München",
    "Leverkusen": "Bayer Leverkusen",
    "Atleti": "Atletico Madrid",
    "Real": "Real Madrid",
    "Inter de Milão": "Inter",
    "Milan": "AC Milan",
    "Galo": "Atlético Mineiro",
    "Mengão": "Flamengo",
    "Mengo": "Flamengo",
    "Verdão": "Palmeiras",
    "Palmeiras SP": "Palmeiras",
    "Tricolor Paulista": "São Paulo",
    "Soberano": "São Paulo",
    "Timão": "Corinthians",
    "Peixe": "Santos",
    "Flu": "Fluminense",
    "Fogão": "Botafogo",
    "Vasco": "Vasco da Gama",
    "CAP": "Athletico-PR",
}


# ============================================================
# PRESETS DE LIGAS
# IDs úteis para API-Football. Você pode ajustar pela sidebar.
# ============================================================

def current_brazilian_season() -> int:
    return datetime.now(APP_TZ).year


def current_european_season() -> int:
    today = datetime.now(APP_TZ)
    return today.year if today.month >= 7 else today.year - 1


LEAGUE_PRESETS: Dict[str, Tuple[Optional[int], Optional[int]]] = {
    "Todas as ligas": (None, None),
    "Brasil - Série A": (71, current_brazilian_season()),
    "Brasil - Série B": (72, current_brazilian_season()),
    "CONMEBOL Libertadores": (13, current_brazilian_season()),
    "CONMEBOL Sul-Americana": (11, current_brazilian_season()),
    "Inglaterra - Premier League": (39, current_european_season()),
    "Espanha - La Liga": (140, current_european_season()),
    "Itália - Serie A": (135, current_european_season()),
    "Alemanha - Bundesliga": (78, current_european_season()),
    "França - Ligue 1": (61, current_european_season()),
    "Europa - Champions League": (2, current_european_season()),
    "Europa - Europa League": (3, current_european_season()),
}


# ============================================================
# UTILITÁRIOS
# ============================================================

def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def short_hash(value: str, size: int = 10) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:size]


def stable_seed(*parts: Any) -> int:
    raw = "|".join(map(str, parts))
    return int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:14], 16)


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def pct(value: float) -> str:
    return f"{value:.1f}%"


def safe_decimal_odds(probability_pct: float) -> str:
    if probability_pct <= 0:
        return "—"
    return f"{100 / probability_pct:.2f}"


def parse_api_datetime(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))

    return dt.astimezone(APP_TZ)


def get_fixture_datetime(match: Dict[str, Any]) -> Optional[datetime]:
    cached = match.get("_local_datetime")

    if isinstance(cached, datetime):
        return cached

    if isinstance(cached, str):
        try:
            return datetime.fromisoformat(cached)
        except ValueError:
            pass

    raw = match.get("fixture", {}).get("date")

    if not raw:
        return None

    try:
        return parse_api_datetime(raw)
    except Exception:
        return None


def current_ratings() -> Dict[str, float]:
    ratings = dict(BASE_TEAM_RATINGS)
    ratings.update(st.session_state.custom_ratings)
    return ratings


def build_rating_index(ratings: Dict[str, float]) -> Dict[str, Tuple[str, float]]:
    index: Dict[str, Tuple[str, float]] = {}

    for name, rating in ratings.items():
        index[normalize_text(name)] = (name, float(rating))

    for alias, canonical in TEAM_ALIASES.items():
        if canonical in ratings:
            index[normalize_text(alias)] = (canonical, float(ratings[canonical]))

    return index


def resolve_team_rating(
    team_name: str,
    ratings: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    ratings = ratings or current_ratings()
    index = build_rating_index(ratings)

    normalized = normalize_text(team_name)

    if not normalized:
        return {
            "rating": DEFAULT_RATING,
            "matched_name": "Padrão",
            "method": "padrão",
        }

    if normalized in index:
        matched_name, rating = index[normalized]
        return {
            "rating": rating,
            "matched_name": matched_name,
            "method": "exato",
        }

    for key, value in index.items():
        if len(key) >= 5 and (key in normalized or normalized in key):
            matched_name, rating = value
            return {
                "rating": rating,
                "matched_name": matched_name,
                "method": "aproximado",
            }

    possible_matches = get_close_matches(
        normalized,
        index.keys(),
        n=1,
        cutoff=0.78,
    )

    if possible_matches:
        matched_name, rating = index[possible_matches[0]]
        return {
            "rating": rating,
            "matched_name": matched_name,
            "method": "fuzzy",
        }

    return {
        "rating": DEFAULT_RATING,
        "matched_name": "Padrão",
        "method": "padrão",
    }


def api_errors_to_text(errors: Any) -> str:
    if not errors:
        return "Erro desconhecido retornado pela API."

    if isinstance(errors, dict):
        parts = []

        for key, value in errors.items():
            if value:
                parts.append(f"{key}: {value}")

        return " | ".join(parts) if parts else str(errors)

    if isinstance(errors, list):
        return " | ".join(map(str, errors))

    return str(errors)


# ============================================================
# CLIENTE DA API
# ============================================================

@st.cache_data(
    ttl=CACHE_TTL_SECONDS,
    max_entries=256,
    show_spinner=False,
)
def api_football_get(
    endpoint: str,
    params: Dict[str, Any],
    api_key: str,
) -> Dict[str, Any]:
    if not api_key.strip():
        return {
            "ok": False,
            "data": None,
            "message": "API Key não informada.",
            "status_code": None,
        }

    url = f"{API_BASE}{endpoint}"

    headers = {
        "x-apisports-key": api_key.strip(),
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

        status_code = response.status_code

        try:
            payload = response.json()
        except ValueError:
            payload = None

        if response.status_code == 401:
            return {
                "ok": False,
                "data": payload,
                "message": "API Key inválida ou não autorizada.",
                "status_code": status_code,
            }

        if response.status_code == 403:
            return {
                "ok": False,
                "data": payload,
                "message": "Acesso negado pela API. Verifique plano, chave e permissões.",
                "status_code": status_code,
            }

        if response.status_code == 429:
            return {
                "ok": False,
                "data": payload,
                "message": "Limite de requisições atingido. Tente novamente mais tarde.",
                "status_code": status_code,
            }

        response.raise_for_status()

        if payload is None:
            return {
                "ok": False,
                "data": None,
                "message": "A API retornou uma resposta inválida.",
                "status_code": status_code,
            }

        api_errors = payload.get("errors")

        if api_errors not in (None, [], {}):
            return {
                "ok": False,
                "data": payload,
                "message": api_errors_to_text(api_errors),
                "status_code": status_code,
            }

        return {
            "ok": True,
            "data": payload,
            "message": None,
            "status_code": status_code,
        }

    except requests.Timeout:
        return {
            "ok": False,
            "data": None,
            "message": "Tempo limite excedido ao consultar a API.",
            "status_code": None,
        }

    except requests.ConnectionError:
        return {
            "ok": False,
            "data": None,
            "message": "Erro de conexão. Verifique sua internet ou tente novamente.",
            "status_code": None,
        }

    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        text = exc.response.text[:250] if exc.response is not None else str(exc)

        return {
            "ok": False,
            "data": None,
            "message": f"Erro HTTP {status}: {text}",
            "status_code": status,
        }

    except requests.RequestException as exc:
        return {
            "ok": False,
            "data": None,
            "message": f"Erro inesperado de requisição: {exc}",
            "status_code": None,
        }


def fetch_fixtures_next_hours(
    api_key: str,
    hours: int,
    max_matches: int,
    league_id: Optional[int],
    season: Optional[int],
) -> Tuple[List[Dict[str, Any]], Optional[str], Dict[str, Any]]:
    now = datetime.now(APP_TZ)
    end = now + timedelta(hours=hours)

    params: Dict[str, Any] = {
        "from": now.date().isoformat(),
        "to": end.date().isoformat(),
        "timezone": APP_TZ_NAME,
    }

    if league_id is not None:
        params["league"] = int(league_id)

    if season is not None:
        params["season"] = int(season)

    result = api_football_get(
        endpoint="/fixtures",
        params=params,
        api_key=api_key,
    )

    metadata = {
        "started_at": now.isoformat(),
        "ended_at": end.isoformat(),
        "params": params,
        "status_code": result.get("status_code"),
    }

    if not result["ok"]:
        return [], result["message"], metadata

    payload = result["data"] or {}
    raw_matches = payload.get("response", [])

    matches: List[Dict[str, Any]] = []

    for match in raw_matches:
        dt = get_fixture_datetime(match)

        if dt is None:
            continue

        if now <= dt <= end:
            match["_local_datetime"] = dt.isoformat()
            matches.append(match)

    matches.sort(key=lambda item: get_fixture_datetime(item) or datetime.max.replace(tzinfo=APP_TZ))

    metadata["raw_count"] = len(raw_matches)
    metadata["filtered_count"] = len(matches)

    return matches[:max_matches], None, metadata


# ============================================================
# MODELO DE PREVISÃO
# ============================================================

def sample_poisson(lam: float, rng: random.Random) -> int:
    """
    Amostragem Poisson pelo algoritmo de Knuth.
    Para lambdas pequenas, funciona muito bem neste caso.
    """
    lam = max(lam, 0.01)

    limit = math.exp(-lam)
    product = 1.0
    k = 0

    while product > limit:
        k += 1
        product *= rng.random()

    return k - 1


def expected_goals(
    home_rating: float,
    away_rating: float,
    home_advantage: float,
    goal_aggressiveness: float,
) -> Tuple[float, float]:
    """
    Modelo simples e explicável.

    - Rating maior aumenta os gols esperados.
    - Mandante recebe bônus.
    - Agressividade ajusta o volume total de gols.
    """
    rating_diff = home_rating - away_rating

    home_xg = 1.35 + home_advantage + (0.028 * rating_diff)
    away_xg = 1.12 - (0.024 * rating_diff)

    home_xg *= goal_aggressiveness
    away_xg *= goal_aggressiveness

    return (
        clamp(home_xg, 0.15, 4.20),
        clamp(away_xg, 0.10, 4.00),
    )


def predict_match(
    home_team: str,
    away_team: str,
    home_rating: float,
    away_rating: float,
    simulations: int,
    home_advantage: float,
    goal_aggressiveness: float,
    deterministic: bool,
) -> Dict[str, Any]:
    home_xg, away_xg = expected_goals(
        home_rating=home_rating,
        away_rating=away_rating,
        home_advantage=home_advantage,
        goal_aggressiveness=goal_aggressiveness,
    )

    if deterministic:
        seed = stable_seed(
            home_team,
            away_team,
            home_rating,
            away_rating,
            simulations,
            home_advantage,
            goal_aggressiveness,
        )
    else:
        seed = random.randint(1, 10**12)

    rng = random.Random(seed)

    home_wins = 0
    draws = 0
    away_wins = 0

    over_05 = 0
    over_15 = 0
    over_25 = 0
    over_35 = 0
    both_score = 0

    total_home_goals = 0
    total_away_goals = 0

    scorelines: Dict[str, int] = {}

    for _ in range(simulations):
        hg = sample_poisson(home_xg, rng)
        ag = sample_poisson(away_xg, rng)

        total_home_goals += hg
        total_away_goals += ag

        total_goals = hg + ag

        if hg > ag:
            home_wins += 1
        elif hg == ag:
            draws += 1
        else:
            away_wins += 1

        if total_goals > 0.5:
            over_05 += 1

        if total_goals > 1.5:
            over_15 += 1

        if total_goals > 2.5:
            over_25 += 1

        if total_goals > 3.5:
            over_35 += 1

        if hg > 0 and ag > 0:
            both_score += 1

        score_key = f"{hg} x {ag}"
        scorelines[score_key] = scorelines.get(score_key, 0) + 1

    top_scorelines = sorted(
        scorelines.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:8]

    return {
        "home_team": home_team,
        "away_team": away_team,
        "home_rating": home_rating,
        "away_rating": away_rating,
        "home_xg": home_xg,
        "away_xg": away_xg,
        "avg_home_goals": total_home_goals / simulations,
        "avg_away_goals": total_away_goals / simulations,
        "home_win_pct": 100 * home_wins / simulations,
        "draw_pct": 100 * draws / simulations,
        "away_win_pct": 100 * away_wins / simulations,
        "over_05_pct": 100 * over_05 / simulations,
        "over_15_pct": 100 * over_15 / simulations,
        "over_25_pct": 100 * over_25 / simulations,
        "over_35_pct": 100 * over_35 / simulations,
        "both_score_pct": 100 * both_score / simulations,
        "top_scorelines": [
            {
                "Placar": score,
                "Probabilidade": pct(100 * count / simulations),
                "Odd justa": safe_decimal_odds(100 * count / simulations),
            }
            for score, count in top_scorelines
        ],
        "simulations": simulations,
        "seed": seed,
    }


# ============================================================
# COMPONENTES DE INTERFACE
# ============================================================

def fixture_label(match: Dict[str, Any]) -> str:
    fixture = match.get("fixture", {})
    teams = match.get("teams", {})
    league = match.get("league", {})

    fixture_id = fixture.get("id", "sem-id")

    dt = get_fixture_datetime(match)
    dt_text = dt.strftime("%d/%m %H:%M") if dt else "Data indefinida"

    home = teams.get("home", {}).get("name", "Mandante")
    away = teams.get("away", {}).get("name", "Visitante")
    league_name = league.get("name", "Liga")

    return f"{dt_text} — {home} x {away} • {league_name} • ID {fixture_id}"


def render_fixture_card(match: Dict[str, Any], index: int) -> None:
    fixture = match.get("fixture", {})
    teams = match.get("teams", {})
    league = match.get("league", {})

    dt = get_fixture_datetime(match)

    home = teams.get("home", {}).get("name", "Mandante")
    away = teams.get("away", {}).get("name", "Visitante")

    league_name = league.get("name", "Liga")
    country = league.get("country", "")
    round_name = league.get("round", "")

    venue = fixture.get("venue") or {}
    venue_name = venue.get("name") or "Estádio não informado"
    city = venue.get("city") or ""

    status = fixture.get("status", {})
    status_long = status.get("long", "Não iniciado")

    label = fixture_label(match)

    with st.container(border=True):
        col_time, col_match, col_action = st.columns([1.4, 4.5, 1.35])

        with col_time:
            if dt:
                st.markdown(f"**{dt.strftime('%d/%m')}**")
                st.markdown(f"### {dt.strftime('%H:%M')}")
            else:
                st.markdown("**Data indefinida**")

            st.caption(status_long)

        with col_match:
            st.markdown(f"### {home} x {away}")
            st.caption(f"{league_name} • {country}")

            location = venue_name

            if city:
                location += f" — {city}"

            st.caption(location)

            if round_name:
                st.caption(round_name)

        with col_action:
            if st.button(
                "Simular",
                key=f"use_fixture_{index}_{fixture.get('id', index)}",
                use_container_width=True,
            ):
                st.session_state.prediction_fixture_label = label
                st.success("Jogo enviado para a aba Previsor.")


def render_prediction(result: Dict[str, Any]) -> None:
    st.markdown("## 📊 Resultado da simulação")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            f"Vitória {result['home_team']}",
            pct(result["home_win_pct"]),
            help=f"Odd justa aproximada: {safe_decimal_odds(result['home_win_pct'])}",
        )
        st.progress(result["home_win_pct"] / 100)

    with col2:
        st.metric(
            "Empate",
            pct(result["draw_pct"]),
            help=f"Odd justa aproximada: {safe_decimal_odds(result['draw_pct'])}",
        )
        st.progress(result["draw_pct"] / 100)

    with col3:
        st.metric(
            f"Vitória {result['away_team']}",
            pct(result["away_win_pct"]),
            help=f"Odd justa aproximada: {safe_decimal_odds(result['away_win_pct'])}",
        )
        st.progress(result["away_win_pct"] / 100)

    st.markdown("### ⚽ Gols e mercados")

    col4, col5, col6, col7 = st.columns(4)

    col4.metric("xG mandante", f"{result['home_xg']:.2f}")
    col5.metric("xG visitante", f"{result['away_xg']:.2f}")
    col6.metric("Mais de 2.5 gols", pct(result["over_25_pct"]))
    col7.metric("Ambos marcam", pct(result["both_score_pct"]))

    market_rows = [
        {
            "Mercado": "Mais de 0.5 gols",
            "Probabilidade": pct(result["over_05_pct"]),
            "Odd justa": safe_decimal_odds(result["over_05_pct"]),
        },
        {
            "Mercado": "Mais de 1.5 gols",
            "Probabilidade": pct(result["over_15_pct"]),
            "Odd justa": safe_decimal_odds(result["over_15_pct"]),
        },
        {
            "Mercado": "Mais de 2.5 gols",
            "Probabilidade": pct(result["over_25_pct"]),
            "Odd justa": safe_decimal_odds(result["over_25_pct"]),
        },
        {
            "Mercado": "Mais de 3.5 gols",
            "Probabilidade": pct(result["over_35_pct"]),
            "Odd justa": safe_decimal_odds(result["over_35_pct"]),
        },
        {
            "Mercado": "Ambos marcam",
            "Probabilidade": pct(result["both_score_pct"]),
            "Odd justa": safe_decimal_odds(result["both_score_pct"]),
        },
    ]

    st.dataframe(
        market_rows,
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### 🎯 Placares mais prováveis")

    st.dataframe(
        result["top_scorelines"],
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("Detalhes técnicos da simulação"):
        st.write(
            {
                "Simulações": result["simulations"],
                "Seed": result["seed"],
                "Rating mandante": result["home_rating"],
                "Rating visitante": result["away_rating"],
                "Média de gols mandante": round(result["avg_home_goals"], 3),
                "Média de gols visitante": round(result["avg_away_goals"], 3),
            }
        )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("## 🔑 API-Football")

    default_secret = ""

    try:
        default_secret = st.secrets.get("API_FOOTBALL_KEY", "")
    except Exception:
        default_secret = ""

    api_key = st.text_input(
        "API Key",
        value=default_secret,
        type="password",
        help="Você pode digitar aqui ou salvar em .streamlit/secrets.toml como API_FOOTBALL_KEY.",
    )

    st.caption("No plano gratuito, evite muitas buscas seguidas para não gastar requisições.")

    st.markdown("---")
    st.markdown("## 📅 Busca de jogos")

    hours = st.slider(
        "Janela de busca",
        min_value=12,
        max_value=96,
        value=48,
        step=12,
    )

    max_matches = st.slider(
        "Máximo de jogos",
        min_value=5,
        max_value=100,
        value=30,
        step=5,
    )

    league_preset = st.selectbox(
        "Filtro de liga",
        options=list(LEAGUE_PRESETS.keys()),
        index=0,
    )

    preset_league_id, preset_season = LEAGUE_PRESETS[league_preset]

    advanced_league = st.checkbox("Editar liga/temporada manualmente")

    if advanced_league:
        league_id_input = st.number_input(
            "League ID",
            min_value=1,
            value=int(preset_league_id or 71),
        )

        season_input = st.number_input(
            "Temporada",
            min_value=2000,
            max_value=2100,
            value=int(preset_season or datetime.now(APP_TZ).year),
        )

        league_id = int(league_id_input)
        season = int(season_input)
    else:
        league_id = preset_league_id
        season = preset_season

    st.markdown("---")
    st.markdown("## 🧠 Modelo")

    home_advantage = st.slider(
        "Bônus de mando",
        min_value=0.00,
        max_value=0.45,
        value=0.20,
        step=0.01,
        help="Aumenta os gols esperados do mandante.",
    )

    goal_aggressiveness = st.slider(
        "Agressividade de gols",
        min_value=0.70,
        max_value=1.35,
        value=1.00,
        step=0.01,
        help="Controla se o modelo prevê jogos mais abertos ou fechados.",
    )

    deterministic = st.checkbox(
        "Resultado reprodutível",
        value=True,
        help="Ligado: a mesma partida gera o mesmo resultado. Desligado: cada simulação varia.",
    )

    st.markdown("---")

    if st.button("🧹 Limpar cache", use_container_width=True):
        st.cache_data.clear()
        st.success("Cache limpo.")


# ============================================================
# TABS
# ============================================================

tab_fixtures, tab_predictor, tab_ratings, tab_about = st.tabs(
    [
        "📅 Próximos Jogos",
        "🔮 Previsor",
        "📈 Ratings",
        "ℹ️ Sobre",
    ]
)


# ============================================================
# TAB 1 — PRÓXIMOS JOGOS
# ============================================================

with tab_fixtures:
    st.markdown("## 📅 Próximos jogos reais")

    col_info_1, col_info_2, col_info_3 = st.columns(3)

    col_info_1.metric("Janela", f"{hours}h")
    col_info_2.metric("Filtro", league_preset)
    col_info_3.metric("Máximo", max_matches)

    if not api_key:
        st.warning("Insira sua API Key na barra lateral para buscar jogos reais.")
    else:
        if st.button("🔄 Buscar jogos agora", type="primary", use_container_width=True):
            with st.spinner("Consultando API-Football..."):
                fixtures, error, metadata = fetch_fixtures_next_hours(
                    api_key=api_key,
                    hours=hours,
                    max_matches=max_matches,
                    league_id=league_id,
                    season=season,
                )

            st.session_state.fixtures = fixtures
            st.session_state.fixtures_error = error
            st.session_state.last_search_summary = metadata

    if st.session_state.fixtures_error:
        st.error(st.session_state.fixtures_error)

    fixtures = st.session_state.fixtures

    if fixtures:
        st.success(f"{len(fixtures)} jogo(s) encontrado(s).")

        search_text = st.text_input(
            "Filtrar resultados exibidos",
            placeholder="Ex.: Flamengo, Premier League, Libertadores...",
        )

        filtered_fixtures = fixtures

        if search_text.strip():
            needle = normalize_text(search_text)

            def match_contains_text(match: Dict[str, Any]) -> bool:
                teams = match.get("teams", {})
                league = match.get("league", {})

                haystack = " ".join(
                    [
                        teams.get("home", {}).get("name", ""),
                        teams.get("away", {}).get("name", ""),
                        league.get("name", ""),
                        league.get("country", ""),
                    ]
                )

                return needle in normalize_text(haystack)

            filtered_fixtures = [
                match
                for match in fixtures
                if match_contains_text(match)
            ]

        if not filtered_fixtures:
            st.info("Nenhum jogo corresponde ao filtro digitado.")
        else:
            for idx, match in enumerate(filtered_fixtures):
                render_fixture_card(match, idx)

        with st.expander("Resumo da última busca"):
            st.write(st.session_state.last_search_summary)

    elif not st.session_state.fixtures_error:
        st.info("Clique em **Buscar jogos agora** para carregar partidas.")


# ============================================================
# TAB 2 — PREVISOR
# ============================================================

with tab_predictor:
    st.markdown("## 🔮 Previsor de confronto")

    fixtures = st.session_state.fixtures

    labels = ["Inserir manualmente"]
    label_to_match: Dict[str, Dict[str, Any]] = {}

    for match in fixtures:
        label = fixture_label(match)
        labels.append(label)
        label_to_match[label] = match

    if st.session_state.prediction_fixture_label not in labels:
        st.session_state.prediction_fixture_label = "Inserir manualmente"

    selected_label = st.selectbox(
        "Partida",
        options=labels,
        key="prediction_fixture_label",
    )

    selected_match = label_to_match.get(selected_label)

    if selected_match:
        teams = selected_match.get("teams", {})
        default_home_team = teams.get("home", {}).get("name", "Mandante")
        default_away_team = teams.get("away", {}).get("name", "Visitante")
    else:
        default_home_team = "Flamengo"
        default_away_team = "Palmeiras"

    widget_scope = short_hash(selected_label)

    col_home, col_away = st.columns(2)

    with col_home:
        home_team = st.text_input(
            "Time mandante",
            value=default_home_team,
            key=f"home_team_{widget_scope}",
        )

        home_match = resolve_team_rating(home_team)
        home_default_rating = float(home_match["rating"])

        st.caption(
            f"Rating sugerido: {home_default_rating:.1f} "
            f"({home_match['matched_name']} · {home_match['method']})"
        )

        home_rating = st.slider(
            "Rating mandante",
            min_value=40.0,
            max_value=100.0,
            value=home_default_rating,
            step=0.5,
            key=f"home_rating_{widget_scope}_{short_hash(home_team)}",
        )

    with col_away:
        away_team = st.text_input(
            "Time visitante",
            value=default_away_team,
            key=f"away_team_{widget_scope}",
        )

        away_match = resolve_team_rating(away_team)
        away_default_rating = float(away_match["rating"])

        st.caption(
            f"Rating sugerido: {away_default_rating:.1f} "
            f"({away_match['matched_name']} · {away_match['method']})"
        )

        away_rating = st.slider(
            "Rating visitante",
            min_value=40.0,
            max_value=100.0,
            value=away_default_rating,
            step=0.5,
            key=f"away_rating_{widget_scope}_{short_hash(away_team)}",
        )

    simulations = st.slider(
        "Número de simulações",
        min_value=1_000,
        max_value=100_000,
        value=DEFAULT_SIMULATIONS,
        step=1_000,
    )

    run_prediction = st.button(
        "🎲 Simular partida",
        type="primary",
        use_container_width=True,
    )

    if run_prediction:
        if not home_team.strip() or not away_team.strip():
            st.error("Informe o nome dos dois times.")
        elif normalize_text(home_team) == normalize_text(away_team):
            st.error("Os times precisam ser diferentes.")
        else:
            with st.spinner("Rodando simulação Monte Carlo..."):
                result = predict_match(
                    home_team=home_team.strip(),
                    away_team=away_team.strip(),
                    home_rating=float(home_rating),
                    away_rating=float(away_rating),
                    simulations=int(simulations),
                    home_advantage=float(home_advantage),
                    goal_aggressiveness=float(goal_aggressiveness),
                    deterministic=bool(deterministic),
                )

            render_prediction(result)


# ============================================================
# TAB 3 — RATINGS
# ============================================================

with tab_ratings:
    st.markdown("## 📈 Ratings dos times")

    ratings = current_ratings()

    st.caption(
        "O rating é a força estimada do time. "
        "Quanto maior, mais forte o time no modelo."
    )

    rating_rows = [
        {
            "Time": team,
            "Rating": rating,
            "Tipo": "customizado" if team in st.session_state.custom_ratings else "base",
        }
        for team, rating in sorted(
            ratings.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    ]

    st.dataframe(
        rating_rows,
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### Adicionar ou atualizar rating")

    with st.form("rating_form", clear_on_submit=True):
        col_team, col_rating = st.columns([3, 1])

        with col_team:
            new_team = st.text_input("Time")

        with col_rating:
            new_rating = st.number_input(
                "Rating",
                min_value=40.0,
                max_value=100.0,
                value=75.0,
                step=0.5,
            )

        submitted_rating = st.form_submit_button(
            "Salvar rating customizado",
            use_container_width=True,
        )

        if submitted_rating:
            if not new_team.strip():
                st.error("Informe o nome do time.")
            else:
                st.session_state.custom_ratings[new_team.strip()] = float(new_rating)
                st.success(f"Rating salvo para {new_team.strip()}.")

    if st.session_state.custom_ratings:
        st.markdown("### Ratings customizados nesta sessão")

        custom_rows = [
            {"Time": team, "Rating": rating}
            for team, rating in sorted(st.session_state.custom_ratings.items())
        ]

        st.dataframe(
            custom_rows,
            use_container_width=True,
            hide_index=True,
        )

        custom_json = json.dumps(
            st.session_state.custom_ratings,
            ensure_ascii=False,
            indent=2,
        )

        st.download_button(
            "Baixar ratings customizados em JSON",
            data=custom_json,
            file_name="ratings_customizados.json",
            mime="application/json",
            use_container_width=True,
        )

        if st.button("Remover ratings customizados", use_container_width=True):
            st.session_state.custom_ratings = {}
            st.success("Ratings customizados removidos.")


# ============================================================
# TAB 4 — SOBRE
# ============================================================

with tab_about:
    st.markdown("## ℹ️ Sobre o app")

    st.markdown(
        """
        Este app combina duas camadas:

        **1. Dados reais da API-Football**  
        A aba de próximos jogos consulta partidas reais e filtra os jogos dentro da janela escolhida.

        **2. Modelo estatístico local**  
        A previsão usa ratings dos times, bônus de mando, volume esperado de gols e simulação Monte Carlo.

        O modelo calcula gols esperados para cada equipe e simula milhares de partidas usando uma distribuição de Poisson.
        A partir disso, estima probabilidades de vitória, empate, mercados de gols e placares mais prováveis.
        """
    )

    st.markdown("### Como salvar a API Key com segurança")

    st.code(
        """
# .streamlit/secrets.toml
API_FOOTBALL_KEY = "sua_chave_aqui"
        """.strip(),
        language="toml",
    )

    st.markdown("### Como rodar")

    st.code(
        """
pip install streamlit requests
streamlit run app.py
        """.strip(),
        language="bash",
    )

    st.warning(
        "As previsões são estimativas estatísticas. "
        "Não use este app como garantia de resultado esportivo."
    )


st.caption(
    "API-Football • Ratings locais • Monte Carlo • Streamlit"
)