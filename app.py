from __future__ import annotations

import hashlib
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
# APP CONFIG
# ============================================================

APP_TITLE = "Previsor de Futebol ESPN"
APP_ICON = "⚽"

APP_TZ_NAME = "America/Sao_Paulo"
APP_TZ = ZoneInfo(APP_TZ_NAME)

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

CACHE_TTL_SECONDS = 15 * 60
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
# CSS
# ============================================================

st.markdown(
    """
    <style>
    .main-title {
        text-align: center;
        font-size: 2.8rem;
        font-weight: 900;
        margin-top: 0.6rem;
        margin-bottom: 0.2rem;
    }

    .main-subtitle {
        text-align: center;
        opacity: 0.72;
        font-size: 1.05rem;
        margin-bottom: 2rem;
    }

    .tiny-muted {
        opacity: 0.68;
        font-size: 0.86rem;
    }

    .pill {
        display: inline-block;
        padding: 0.2rem 0.55rem;
        border-radius: 999px;
        background: rgba(59, 130, 246, 0.12);
        color: #3b82f6;
        font-weight: 700;
        font-size: 0.82rem;
        margin-right: 0.25rem;
    }

    .warning-soft {
        border-left: 4px solid #f59e0b;
        background: rgba(245, 158, 11, 0.10);
        border-radius: 0.6rem;
        padding: 0.85rem 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-title">⚽ Previsor de Futebol com ESPN</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-subtitle">Jogos reais via ESPN pública não oficial + ratings locais + Monte Carlo</div>',
    unsafe_allow_html=True,
)


# ============================================================
# SESSION STATE
# ============================================================

if "matches" not in st.session_state:
    st.session_state.matches = []

if "errors" not in st.session_state:
    st.session_state.errors = []

if "last_fetch_info" not in st.session_state:
    st.session_state.last_fetch_info = {}

if "selected_match_label" not in st.session_state:
    st.session_state.selected_match_label = "Inserir manualmente"

if "custom_ratings" not in st.session_state:
    st.session_state.custom_ratings = {}


# ============================================================
# ESPN LEAGUES
# ============================================================

ESPN_LEAGUE_GROUPS: Dict[str, Dict[str, str]] = {
    "🏆 Copas FIFA": {
        "Copa do Mundo FIFA": "fifa.world",
        "Copa do Mundo Feminina FIFA": "fifa.wwc",
        "Mundial de Clubes FIFA": "fifa.cwc",
        "Copa do Mundo Sub-20 FIFA": "fifa.world.u20",
        "Copa do Mundo Sub-17 FIFA": "fifa.world.u17",
        "Amistosos Internacionais": "fifa.friendly",
    },

    "🇧🇷 Brasil": {
        "Brasil - Série A": "bra.1",
        "Brasil - Série B": "bra.2",
    },

    "🌎 América do Sul": {
        "CONMEBOL Libertadores": "conmebol.libertadores",
        "CONMEBOL Sul-Americana": "conmebol.sudamericana",
    },

    "🇪🇺 Europa": {
        "UEFA Champions League": "uefa.champions",
        "UEFA Europa League": "uefa.europa",
        "UEFA Conference League": "uefa.europa.conf",
        "Inglaterra - Premier League": "eng.1",
        "Inglaterra - Championship": "eng.2",
        "Espanha - La Liga": "esp.1",
        "Itália - Serie A": "ita.1",
        "Alemanha - Bundesliga": "ger.1",
        "França - Ligue 1": "fra.1",
        "Portugal - Primeira Liga": "por.1",
        "Holanda - Eredivisie": "ned.1",
    },

    "🌍 Outras ligas": {
        "EUA - MLS": "usa.1",
        "EUA - NWSL Feminina": "usa.nwsl",
        "México - Liga MX": "mex.1",
        "Arábia Saudita - Pro League": "ksa.1",
    },
}


ESPN_LEAGUES: Dict[str, str] = {
    league_name: slug
    for group in ESPN_LEAGUE_GROUPS.values()
    for league_name, slug in group.items()
}


LEAGUE_PRESETS: Dict[str, List[str]] = {
    "Essencial": [
        "Copa do Mundo FIFA",
        "Brasil - Série A",
        "Brasil - Série B",
        "CONMEBOL Libertadores",
        "CONMEBOL Sul-Americana",
        "UEFA Champions League",
        "Inglaterra - Premier League",
        "Espanha - La Liga",
    ],

    "Copa do Mundo": [
        "Copa do Mundo FIFA",
    ],

    "Copas FIFA": [
        "Copa do Mundo FIFA",
        "Copa do Mundo Feminina FIFA",
        "Mundial de Clubes FIFA",
        "Copa do Mundo Sub-20 FIFA",
        "Copa do Mundo Sub-17 FIFA",
    ],

    "Só Brasil": [
        "Brasil - Série A",
        "Brasil - Série B",
    ],

    "América do Sul": [
        "Brasil - Série A",
        "Brasil - Série B",
        "CONMEBOL Libertadores",
        "CONMEBOL Sul-Americana",
    ],

    "Europa": [
        "UEFA Champions League",
        "UEFA Europa League",
        "UEFA Conference League",
        "Inglaterra - Premier League",
        "Espanha - La Liga",
        "Itália - Serie A",
        "Alemanha - Bundesliga",
        "França - Ligue 1",
        "Portugal - Primeira Liga",
    ],

    "Tudo": list(ESPN_LEAGUES.keys()),
}


PERIOD_PRESETS: Dict[str, int] = {
    "Próximas 48 horas": 48,
    "Próximos 7 dias": 24 * 7,
    "Próximos 30 dias": 24 * 30,
    "Próximos 60 dias": 24 * 60,
}


# ============================================================
# RATINGS
# ============================================================

BASE_TEAM_RATINGS: Dict[str, float] = {
    # Seleções
    "Brazil": 91.0,
    "Brasil": 91.0,
    "Argentina": 91.5,
    "France": 91.0,
    "França": 91.0,
    "England": 89.5,
    "Inglaterra": 89.5,
    "Spain": 89.0,
    "Espanha": 89.0,
    "Germany": 87.0,
    "Alemanha": 87.0,
    "Portugal": 88.5,
    "Netherlands": 87.5,
    "Holanda": 87.5,
    "Italy": 87.0,
    "Itália": 87.0,
    "Uruguay": 86.0,
    "Uruguai": 86.0,
    "Belgium": 86.0,
    "Bélgica": 86.0,
    "Croatia": 84.5,
    "Croácia": 84.5,
    "Colombia": 84.5,
    "Colômbia": 84.5,
    "Mexico": 81.0,
    "México": 81.0,
    "United States": 80.5,
    "Estados Unidos": 80.5,
    "USA": 80.5,
    "Japan": 80.0,
    "Japão": 80.0,
    "Morocco": 82.0,
    "Marrocos": 82.0,
    "Switzerland": 81.5,
    "Suíça": 81.5,
    "Denmark": 81.0,
    "Dinamarca": 81.0,
    "Senegal": 80.5,

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
    "Atletico Mineiro": 84.0,
    "Cruzeiro": 79.5,
    "Bahia": 79.0,
    "Vasco da Gama": 77.5,
    "Fortaleza": 80.0,
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

    # América do Sul
    "River Plate": 84.0,
    "Boca Juniors": 83.0,
    "Racing Club": 80.0,
    "Independiente": 78.5,
    "Estudiantes": 79.5,
    "San Lorenzo": 78.5,
    "Nacional": 78.0,
    "Peñarol": 78.0,
    "Penarol": 78.0,
    "Colo Colo": 77.0,
    "LDU Quito": 78.0,

    # Inglaterra
    "Manchester City": 94.0,
    "Arsenal": 91.0,
    "Liverpool": 91.5,
    "Chelsea": 86.0,
    "Manchester United": 84.5,
    "Tottenham Hotspur": 85.5,
    "Tottenham": 85.5,
    "Newcastle United": 84.0,
    "Aston Villa": 84.0,
    "Brighton & Hove Albion": 82.0,
    "West Ham United": 80.0,

    # Espanha
    "Real Madrid": 94.0,
    "Barcelona": 91.0,
    "Atlético Madrid": 88.0,
    "Atletico Madrid": 88.0,
    "Athletic Club": 84.0,
    "Real Sociedad": 84.0,
    "Villarreal": 82.0,
    "Sevilla": 80.0,
    "Real Betis": 81.0,

    # Itália
    "Internazionale": 90.5,
    "Inter": 90.5,
    "AC Milan": 87.5,
    "Juventus": 87.5,
    "Napoli": 86.5,
    "Atalanta": 86.0,
    "Roma": 84.0,
    "Lazio": 83.0,
    "Fiorentina": 82.0,

    # Alemanha
    "Bayern Munich": 92.0,
    "Bayern München": 92.0,
    "Borussia Dortmund": 87.5,
    "Bayer Leverkusen": 90.0,
    "RB Leipzig": 86.5,
    "Eintracht Frankfurt": 82.0,
    "VfB Stuttgart": 82.0,

    # França / Portugal / Holanda
    "Paris Saint-Germain": 91.0,
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
    "PSG": "Paris Saint-Germain",
    "Man City": "Manchester City",
    "Man United": "Manchester United",
    "Manchester Utd": "Manchester United",
    "Spurs": "Tottenham Hotspur",
    "Bayern": "Bayern Munich",
    "Leverkusen": "Bayer Leverkusen",
    "Atleti": "Atlético Madrid",
    "Milan": "AC Milan",
    "Inter de Milão": "Internazionale",
    "Galo": "Atlético Mineiro",
    "Mengão": "Flamengo",
    "Mengo": "Flamengo",
    "Verdão": "Palmeiras",
    "Timão": "Corinthians",
    "Peixe": "Santos",
    "Flu": "Fluminense",
    "Fogão": "Botafogo",
    "Vasco": "Vasco da Gama",
    "Seleção Brasileira": "Brasil",
    "Brazil National Team": "Brazil",
    "USMNT": "United States",
    "USA": "United States",
    "U.S.": "United States",
}


# ============================================================
# HELPERS
# ============================================================

def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def short_hash(value: str, size: int = 10) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:size]


def stable_seed(*parts: Any) -> int:
    raw = "|".join(map(str, parts)).encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:14], 16)


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def pct(value: float) -> str:
    return f"{value:.1f}%"


def decimal_odd(probability_pct: float) -> str:
    if probability_pct <= 0:
        return "—"
    return f"{100 / probability_pct:.2f}"


def parse_espn_datetime(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt.astimezone(APP_TZ)


def make_date_param(hours: int) -> str:
    now = datetime.now(APP_TZ)
    end = now + timedelta(hours=hours)

    start_text = now.strftime("%Y%m%d")
    end_text = end.strftime("%Y%m%d")

    if start_text == end_text:
        return start_text

    return f"{start_text}-{end_text}"


def current_ratings() -> Dict[str, float]:
    ratings = dict(BASE_TEAM_RATINGS)
    ratings.update(st.session_state.custom_ratings)
    return ratings


def resolve_rating(team_name: str) -> Dict[str, Any]:
    ratings = current_ratings()
    normalized = normalize_text(team_name)

    if not normalized:
        return {
            "rating": DEFAULT_RATING,
            "matched": "Padrão",
            "method": "padrão",
        }

    index: Dict[str, Tuple[str, float]] = {}

    for name, rating in ratings.items():
        index[normalize_text(name)] = (name, float(rating))

    for alias, canonical in TEAM_ALIASES.items():
        if canonical in ratings:
            index[normalize_text(alias)] = (canonical, float(ratings[canonical]))

    if normalized in index:
        name, rating = index[normalized]
        return {
            "rating": rating,
            "matched": name,
            "method": "exato",
        }

    for key, value in index.items():
        if len(key) >= 5 and (key in normalized or normalized in key):
            name, rating = value
            return {
                "rating": rating,
                "matched": name,
                "method": "aproximado",
            }

    close = get_close_matches(normalized, index.keys(), n=1, cutoff=0.78)

    if close:
        name, rating = index[close[0]]
        return {
            "rating": rating,
            "matched": name,
            "method": "fuzzy",
        }

    return {
        "rating": DEFAULT_RATING,
        "matched": "Padrão",
        "method": "padrão",
    }


def selected_leagues_from_categories(
    selected_groups: List[str],
    select_all: bool,
) -> Tuple[List[str], List[str]]:
    available: List[str] = []

    for group_name in selected_groups:
        available.extend(ESPN_LEAGUE_GROUPS.get(group_name, {}).keys())

    available = list(dict.fromkeys(available))

    default_selection = [
        league
        for league in LEAGUE_PRESETS["Essencial"]
        if league in available
    ]

    if select_all:
        default_selection = available

    return available, default_selection


# ============================================================
# ESPN CLIENT
# ============================================================

@st.cache_data(
    ttl=CACHE_TTL_SECONDS,
    max_entries=512,
    show_spinner=False,
)
def espn_scoreboard_request(
    league_slug: str,
    date_param: str,
    limit: int,
) -> Dict[str, Any]:
    url = f"{ESPN_BASE}/{league_slug}/scoreboard"

    params = {
        "dates": date_param,
        "limit": limit,
        "lang": "pt",
        "region": "br",
    }

    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 Streamlit Football Predictor",
    }

    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

        status_code = response.status_code
        final_url = response.url

        response.raise_for_status()

        return {
            "ok": True,
            "data": response.json(),
            "message": None,
            "status_code": status_code,
            "url": final_url,
        }

    except requests.Timeout:
        return {
            "ok": False,
            "data": None,
            "message": f"Tempo limite excedido ao consultar {league_slug}.",
            "status_code": None,
            "url": url,
        }

    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        return {
            "ok": False,
            "data": None,
            "message": f"Erro HTTP {status} ao consultar {league_slug}.",
            "status_code": status,
            "url": url,
        }

    except requests.RequestException as exc:
        return {
            "ok": False,
            "data": None,
            "message": f"Erro de conexão em {league_slug}: {exc}",
            "status_code": None,
            "url": url,
        }

    except ValueError:
        return {
            "ok": False,
            "data": None,
            "message": f"Resposta JSON inválida da ESPN para {league_slug}.",
            "status_code": None,
            "url": url,
        }


def extract_competitor(
    competitors: List[Dict[str, Any]],
    home_away: str,
) -> Dict[str, Any]:
    for competitor in competitors:
        if competitor.get("homeAway") == home_away:
            return competitor

    return {}


def normalize_espn_event(
    event: Dict[str, Any],
    league_label: str,
    league_slug: str,
) -> Optional[Dict[str, Any]]:
    competitions = event.get("competitions") or []

    if not competitions:
        return None

    competition = competitions[0]
    competitors = competition.get("competitors") or []

    home = extract_competitor(competitors, "home")
    away = extract_competitor(competitors, "away")

    if not home or not away:
        return None

    home_team = home.get("team") or {}
    away_team = away.get("team") or {}

    raw_date = competition.get("date") or event.get("date")

    if not raw_date:
        return None

    try:
        dt = parse_espn_datetime(raw_date)
    except Exception:
        return None

    venue = competition.get("venue") or {}
    venue_address = venue.get("address") or {}

    status = competition.get("status") or event.get("status") or {}
    status_type = status.get("type") or {}

    return {
        "event_id": str(event.get("id", "")),
        "date": dt.isoformat(),
        "timestamp": dt.timestamp(),
        "league_label": league_label,
        "league_slug": league_slug,
        "name": event.get("name") or "",
        "short_name": event.get("shortName") or "",
        "home_team": home_team.get("displayName") or home_team.get("name") or "Mandante",
        "away_team": away_team.get("displayName") or away_team.get("name") or "Visitante",
        "home_abbr": home_team.get("abbreviation") or "",
        "away_abbr": away_team.get("abbreviation") or "",
        "home_logo": home_team.get("logo") or "",
        "away_logo": away_team.get("logo") or "",
        "home_score": home.get("score"),
        "away_score": away.get("score"),
        "venue": venue.get("fullName") or venue.get("name") or "Local não informado",
        "city": venue_address.get("city") or "",
        "status": status_type.get("description") or status_type.get("detail") or "Status indisponível",
        "status_short": status_type.get("shortDetail") or "",
        "state": status_type.get("state") or "pre",
    }


def fetch_espn_matches(
    selected_leagues: List[str],
    hours: int,
    limit_per_league: int,
    include_live: bool,
    include_finished_today: bool,
) -> Tuple[List[Dict[str, Any]], List[str], Dict[str, Any]]:
    now = datetime.now(APP_TZ)
    end = now + timedelta(hours=hours)

    date_param = make_date_param(hours)

    matches: List[Dict[str, Any]] = []
    errors: List[str] = []

    request_log: List[Dict[str, Any]] = []

    for league_label in selected_leagues:
        league_slug = ESPN_LEAGUES.get(league_label)

        if not league_slug:
            errors.append(f"Liga sem slug configurado: {league_label}")
            continue

        result = espn_scoreboard_request(
            league_slug=league_slug,
            date_param=date_param,
            limit=limit_per_league,
        )

        request_log.append(
            {
                "league": league_label,
                "slug": league_slug,
                "ok": result["ok"],
                "status_code": result.get("status_code"),
                "url": result.get("url"),
            }
        )

        if not result["ok"]:
            errors.append(result["message"])
            continue

        payload = result["data"] or {}
        events = payload.get("events") or []

        for event in events:
            match = normalize_espn_event(
                event=event,
                league_label=league_label,
                league_slug=league_slug,
            )

            if not match:
                continue

            match_dt = datetime.fromisoformat(match["date"])
            state = match["state"]

            is_upcoming = now <= match_dt <= end
            is_live = state == "in"
            is_finished_today = (
                include_finished_today
                and state == "post"
                and match_dt.date() == now.date()
            )

            if is_upcoming or (include_live and is_live) or is_finished_today:
                matches.append(match)

    seen_ids = set()
    unique_matches: List[Dict[str, Any]] = []

    for match in sorted(matches, key=lambda item: item["timestamp"]):
        dedupe_key = (
            match.get("event_id"),
            match.get("league_slug"),
            match.get("home_team"),
            match.get("away_team"),
        )

        if dedupe_key in seen_ids:
            continue

        seen_ids.add(dedupe_key)
        unique_matches.append(match)

    fetch_info = {
        "generated_at": now.isoformat(),
        "window_start": now.isoformat(),
        "window_end": end.isoformat(),
        "date_param": date_param,
        "selected_leagues_count": len(selected_leagues),
        "matches_count": len(unique_matches),
        "requests": request_log,
    }

    return unique_matches, errors, fetch_info


# ============================================================
# PREDICTION MODEL
# ============================================================

def sample_poisson(lam: float, rng: random.Random) -> int:
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
    rating_diff = home_rating - away_rating

    home_xg = 1.35 + home_advantage + (0.028 * rating_diff)
    away_xg = 1.12 - (0.024 * rating_diff)

    home_xg *= goal_aggressiveness
    away_xg *= goal_aggressiveness

    return (
        clamp(home_xg, 0.15, 4.25),
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
        home_goals = sample_poisson(home_xg, rng)
        away_goals = sample_poisson(away_xg, rng)

        total_home_goals += home_goals
        total_away_goals += away_goals

        total_goals = home_goals + away_goals

        if home_goals > away_goals:
            home_wins += 1
        elif home_goals == away_goals:
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

        if home_goals > 0 and away_goals > 0:
            both_score += 1

        score_key = f"{home_goals} x {away_goals}"
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
        "home_win_pct": 100 * home_wins / simulations,
        "draw_pct": 100 * draws / simulations,
        "away_win_pct": 100 * away_wins / simulations,
        "over_05_pct": 100 * over_05 / simulations,
        "over_15_pct": 100 * over_15 / simulations,
        "over_25_pct": 100 * over_25 / simulations,
        "over_35_pct": 100 * over_35 / simulations,
        "both_score_pct": 100 * both_score / simulations,
        "avg_home_goals": total_home_goals / simulations,
        "avg_away_goals": total_away_goals / simulations,
        "top_scorelines": [
            {
                "Placar": score,
                "Probabilidade": pct(100 * count / simulations),
                "Odd justa": decimal_odd(100 * count / simulations),
            }
            for score, count in top_scorelines
        ],
        "simulations": simulations,
        "seed": seed,
    }


# ============================================================
# UI COMPONENTS
# ============================================================

def match_label(match: Dict[str, Any]) -> str:
    dt = datetime.fromisoformat(match["date"])

    return (
        f"{dt.strftime('%d/%m %H:%M')} — "
        f"{match['home_team']} x {match['away_team']} • "
        f"{match['league_label']}"
    )


def render_match_card(match: Dict[str, Any], index: int) -> None:
    dt = datetime.fromisoformat(match["date"])

    with st.container(border=True):
        col_time, col_game, col_action = st.columns([1.15, 4.95, 1.25])

        with col_time:
            st.markdown(f"**{dt.strftime('%d/%m')}**")
            st.markdown(f"### {dt.strftime('%H:%M')}")
            st.caption(match["status"])

        with col_game:
            st.markdown(f"### {match['home_team']} x {match['away_team']}")
            st.caption(f"{match['league_label']} • {match['venue']}")

            if match["city"]:
                st.caption(match["city"])

            if match["state"] in {"in", "post"}:
                score_home = match["home_score"] or "0"
                score_away = match["away_score"] or "0"
                st.markdown(f"**Placar ESPN:** {score_home} x {score_away}")

        with col_action:
            if st.button(
                "Usar",
                key=f"use_match_{match['event_id']}_{index}",
                use_container_width=True,
            ):
                st.session_state.selected_match_label = match_label(match)
                st.success("Partida enviada para a aba Previsor.")


def render_prediction(result: Dict[str, Any]) -> None:
    st.markdown("## 📊 Resultado da simulação")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            f"Vitória {result['home_team']}",
            pct(result["home_win_pct"]),
            help=f"Odd justa: {decimal_odd(result['home_win_pct'])}",
        )
        st.progress(result["home_win_pct"] / 100)

    with col2:
        st.metric(
            "Empate",
            pct(result["draw_pct"]),
            help=f"Odd justa: {decimal_odd(result['draw_pct'])}",
        )
        st.progress(result["draw_pct"] / 100)

    with col3:
        st.metric(
            f"Vitória {result['away_team']}",
            pct(result["away_win_pct"]),
            help=f"Odd justa: {decimal_odd(result['away_win_pct'])}",
        )
        st.progress(result["away_win_pct"] / 100)

    st.markdown("### ⚽ Gols esperados e mercados")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("xG mandante", f"{result['home_xg']:.2f}")
    c2.metric("xG visitante", f"{result['away_xg']:.2f}")
    c3.metric("Mais de 2.5 gols", pct(result["over_25_pct"]))
    c4.metric("Ambos marcam", pct(result["both_score_pct"]))

    markets = [
        {
            "Mercado": "Mais de 0.5 gols",
            "Probabilidade": pct(result["over_05_pct"]),
            "Odd justa": decimal_odd(result["over_05_pct"]),
        },
        {
            "Mercado": "Mais de 1.5 gols",
            "Probabilidade": pct(result["over_15_pct"]),
            "Odd justa": decimal_odd(result["over_15_pct"]),
        },
        {
            "Mercado": "Mais de 2.5 gols",
            "Probabilidade": pct(result["over_25_pct"]),
            "Odd justa": decimal_odd(result["over_25_pct"]),
        },
        {
            "Mercado": "Mais de 3.5 gols",
            "Probabilidade": pct(result["over_35_pct"]),
            "Odd justa": decimal_odd(result["over_35_pct"]),
        },
        {
            "Mercado": "Ambos marcam",
            "Probabilidade": pct(result["both_score_pct"]),
            "Odd justa": decimal_odd(result["both_score_pct"]),
        },
    ]

    st.dataframe(markets, use_container_width=True, hide_index=True)

    st.markdown("### 🎯 Placares mais prováveis")
    st.dataframe(result["top_scorelines"], use_container_width=True, hide_index=True)

    with st.expander("Detalhes técnicos"):
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
    st.markdown("## 🏆 Competições")

    selection_mode = st.selectbox(
        "Seleção rápida",
        options=list(LEAGUE_PRESETS.keys()) + ["Personalizado por categoria"],
        index=0,
        help="Use um pacote pronto ou monte sua seleção por categorias.",
    )

    if selection_mode != "Personalizado por categoria":
        selected_leagues = LEAGUE_PRESETS[selection_mode]

        st.success(f"{len(selected_leagues)} competição(ões) selecionada(s).")

        with st.expander("Ver seleção"):
            for league in selected_leagues:
                st.write(f"• {league}")

    else:
        selected_groups = st.multiselect(
            "Categorias",
            options=list(ESPN_LEAGUE_GROUPS.keys()),
            default=["🏆 Copas FIFA", "🇧🇷 Brasil", "🌎 América do Sul"],
            help="Primeiro escolha os grupos. Depois escolha as competições.",
        )

        select_all_in_categories = st.checkbox(
            "Selecionar todas das categorias escolhidas",
            value=False,
        )

        available_leagues, default_custom_leagues = selected_leagues_from_categories(
            selected_groups=selected_groups,
            select_all=select_all_in_categories,
        )

        selector_key = "custom_leagues_" + short_hash(
            "|".join(selected_groups) + str(select_all_in_categories)
        )

        selected_leagues = st.multiselect(
            "Competições",
            options=available_leagues,
            default=default_custom_leagues,
            key=selector_key,
        )

        st.info(f"{len(selected_leagues)} competição(ões) selecionada(s).")

    st.markdown("---")
    st.markdown("## 📅 Período")

    period_mode = st.selectbox(
        "Buscar jogos em",
        options=list(PERIOD_PRESETS.keys()) + ["Personalizado"],
        index=1,
        help="Para Copa do Mundo, 30 ou 60 dias costuma fazer mais sentido.",
    )

    if period_mode == "Personalizado":
        hours = st.slider(
            "Horas à frente",
            min_value=12,
            max_value=24 * 90,
            value=48,
            step=12,
        )
    else:
        hours = PERIOD_PRESETS[period_mode]

    limit_per_league = st.slider(
        "Limite por competição",
        min_value=5,
        max_value=150,
        value=75,
        step=5,
    )

    include_live = st.checkbox(
        "Incluir jogos ao vivo",
        value=True,
    )

    include_finished_today = st.checkbox(
        "Incluir jogos encerrados hoje",
        value=False,
    )

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
        help="Valores maiores deixam o jogo mais aberto.",
    )

    deterministic = st.checkbox(
        "Resultado reprodutível",
        value=True,
        help="Ligado: a mesma configuração gera o mesmo resultado.",
    )

    st.markdown("---")

    if st.button("🧹 Limpar cache", use_container_width=True):
        st.cache_data.clear()
        st.success("Cache limpo.")


# ============================================================
# TABS
# ============================================================

tab_matches, tab_predictor, tab_ratings, tab_about = st.tabs(
    [
        "📅 Jogos ESPN",
        "🔮 Previsor",
        "📈 Ratings",
        "ℹ️ Sobre",
    ]
)


# ============================================================
# TAB: JOGOS
# ============================================================

with tab_matches:
    st.markdown("## 📅 Jogos via ESPN")

    col_a, col_b, col_c = st.columns(3)

    col_a.metric("Competições", len(selected_leagues))
    col_b.metric("Período", f"{hours // 24} dias" if hours >= 24 else f"{hours}h")
    col_c.metric("Limite/competição", limit_per_league)

    if not selected_leagues:
        st.warning("Selecione pelo menos uma competição na barra lateral.")
    else:
        if st.button("🔄 Buscar jogos na ESPN", type="primary", use_container_width=True):
            with st.spinner("Consultando ESPN..."):
                matches, errors, fetch_info = fetch_espn_matches(
                    selected_leagues=selected_leagues,
                    hours=int(hours),
                    limit_per_league=int(limit_per_league),
                    include_live=bool(include_live),
                    include_finished_today=bool(include_finished_today),
                )

            st.session_state.matches = matches
            st.session_state.errors = errors
            st.session_state.last_fetch_info = fetch_info

    if st.session_state.errors:
        with st.expander("Avisos da ESPN"):
            for error in st.session_state.errors:
                st.warning(error)

    matches = st.session_state.matches

    if matches:
        st.success(f"{len(matches)} jogo(s) encontrado(s).")

        search = st.text_input(
            "Filtrar jogos exibidos",
            placeholder="Ex.: Brasil, Flamengo, Copa do Mundo, Champions...",
        )

        filtered_matches = matches

        if search.strip():
            needle = normalize_text(search)

            filtered_matches = [
                match
                for match in matches
                if needle in normalize_text(
                    " ".join(
                        [
                            match["home_team"],
                            match["away_team"],
                            match["league_label"],
                            match["venue"],
                            match["status"],
                        ]
                    )
                )
            ]

        if not filtered_matches:
            st.info("Nenhum jogo corresponde ao filtro.")
        else:
            for index, match in enumerate(filtered_matches):
                render_match_card(match, index)

        with st.expander("Resumo técnico da busca"):
            st.write(st.session_state.last_fetch_info)

    else:
        st.info("Clique em **Buscar jogos na ESPN** para carregar partidas.")


# ============================================================
# TAB: PREVISOR
# ============================================================

with tab_predictor:
    st.markdown("## 🔮 Previsor de confronto")

    matches = st.session_state.matches

    labels = ["Inserir manualmente"]
    label_to_match: Dict[str, Dict[str, Any]] = {}

    for match in matches:
        label = match_label(match)
        labels.append(label)
        label_to_match[label] = match

    if st.session_state.selected_match_label not in labels:
        st.session_state.selected_match_label = "Inserir manualmente"

    selected_label = st.selectbox(
        "Partida",
        options=labels,
        key="selected_match_label",
    )

    selected_match = label_to_match.get(selected_label)

    if selected_match:
        default_home = selected_match["home_team"]
        default_away = selected_match["away_team"]
    else:
        default_home = "Brasil"
        default_away = "Argentina"

    scope = short_hash(selected_label, 8)

    col_home, col_away = st.columns(2)

    with col_home:
        home_team = st.text_input(
            "Mandante",
            value=default_home,
            key=f"home_team_{scope}",
        )

        home_rating_info = resolve_rating(home_team)
        suggested_home_rating = float(home_rating_info["rating"])

        st.caption(
            f"Sugerido: {suggested_home_rating:.1f} "
            f"({home_rating_info['matched']} · {home_rating_info['method']})"
        )

        home_rating = st.slider(
            "Rating mandante",
            min_value=40.0,
            max_value=100.0,
            value=suggested_home_rating,
            step=0.5,
            key=f"home_rating_{scope}_{short_hash(home_team, 6)}",
        )

    with col_away:
        away_team = st.text_input(
            "Visitante",
            value=default_away,
            key=f"away_team_{scope}",
        )

        away_rating_info = resolve_rating(away_team)
        suggested_away_rating = float(away_rating_info["rating"])

        st.caption(
            f"Sugerido: {suggested_away_rating:.1f} "
            f"({away_rating_info['matched']} · {away_rating_info['method']})"
        )

        away_rating = st.slider(
            "Rating visitante",
            min_value=40.0,
            max_value=100.0,
            value=suggested_away_rating,
            step=0.5,
            key=f"away_rating_{scope}_{short_hash(away_team, 6)}",
        )

    simulations = st.slider(
        "Simulações",
        min_value=1_000,
        max_value=100_000,
        value=DEFAULT_SIMULATIONS,
        step=1_000,
    )

    if st.button("🎲 Simular partida", type="primary", use_container_width=True):
        if not home_team.strip() or not away_team.strip():
            st.error("Informe os dois times.")
        elif normalize_text(home_team) == normalize_text(away_team):
            st.error("Os times precisam ser diferentes.")
        else:
            with st.spinner("Rodando Monte Carlo..."):
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
# TAB: RATINGS
# ============================================================

with tab_ratings:
    st.markdown("## 📈 Ratings usados pelo modelo")

    st.caption(
        "Times/seleções não encontrados recebem rating padrão 75. "
        "Você pode editar ratings pela interface ou direto no dicionário BASE_TEAM_RATINGS."
    )

    ratings = current_ratings()

    rows = [
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

    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.markdown("### Adicionar ou ajustar rating nesta sessão")

    with st.form("rating_form", clear_on_submit=True):
        col_team, col_rating = st.columns([3, 1])

        with col_team:
            new_team = st.text_input("Time ou seleção")

        with col_rating:
            new_rating = st.number_input(
                "Rating",
                min_value=40.0,
                max_value=100.0,
                value=75.0,
                step=0.5,
            )

        submitted = st.form_submit_button(
            "Salvar rating",
            use_container_width=True,
        )

        if submitted:
            if not new_team.strip():
                st.error("Informe o nome.")
            else:
                st.session_state.custom_ratings[new_team.strip()] = float(new_rating)
                st.success(f"Rating salvo para {new_team.strip()}.")

    if st.session_state.custom_ratings:
        if st.button("Remover ratings customizados", use_container_width=True):
            st.session_state.custom_ratings = {}
            st.success("Ratings customizados removidos.")


# ============================================================
# TAB: SOBRE
# ============================================================

with tab_about:
    st.markdown("## ℹ️ Sobre o app")

    st.markdown(
        """
        Este app usa endpoints públicos não oficiais da ESPN para consultar partidas de futebol.

        **O que a ESPN fornece aqui:** lista de jogos, horários, competições, status e placar quando disponível.

        **O que o app calcula:** probabilidades de vitória, empate, gols e placares prováveis usando ratings locais,
        gols esperados e simulação Monte Carlo.

        Como a API pública da ESPN não é uma API oficial com contrato de estabilidade, alguma competição pode falhar
        ou mudar de formato sem aviso. O app trata essas falhas sem derrubar a busca inteira.
        """
    )

    st.markdown("### Como rodar")

    st.code(
        """
pip install streamlit requests
streamlit run app.py
        """.strip(),
        language="bash",
    )

    st.markdown("### Competições FIFA incluídas")

    st.write(
        [
            "Copa do Mundo FIFA",
            "Copa do Mundo Feminina FIFA",
            "Mundial de Clubes FIFA",
            "Copa do Mundo Sub-20 FIFA",
            "Copa do Mundo Sub-17 FIFA",
        ]
    )

    st.warning(
        "As previsões são estimativas estatísticas. "
        "Não use este app como garantia de resultado esportivo."
    )


st.caption("ESPN pública não oficial • Copa do Mundo • Streamlit • Monte Carlo • Ratings locais")