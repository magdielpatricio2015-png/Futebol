import html
import math
import re
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st


# ============================================================
# ANALISADOR ESPORTIVO PRO 9.1
# Futebol + Tenis
# App completo em um arquivo para Streamlit Cloud
# ============================================================

st.set_page_config(
    page_title="Analisador Esportivo Pro 9.1",
    page_icon="AE",
    layout="wide",
    initial_sidebar_state="expanded",
)

TZ_BR = ZoneInfo("America/Sao_Paulo")
ESPN_SOCCER_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
ODDS_API_BASE = "https://api.the-odds-api.com/v4/sports"
HEADERS = {"User-Agent": "AnalisadorEsportivoPro/7.0"}
MAX_GOLS = 10


FUTEBOL_COMPETICOES = {
    "Brasileirao Serie A": {"espn": "bra.1", "odds": "soccer_brazil_campeonato"},
    "Brasileirao Serie B": {"espn": "bra.2", "odds": "soccer_brazil_serie_b"},
    "Copa do Brasil": {"espn": "bra.copa_do_brasil", "odds": "soccer_brazil_copa_do_brasil"},
    "Libertadores": {"espn": "conmebol.libertadores", "odds": "soccer_conmebol_copa_libertadores"},
    "Sul-Americana": {"espn": "conmebol.sudamericana", "odds": "soccer_conmebol_copa_sudamericana"},
    "Premier League": {"espn": "eng.1", "odds": "soccer_epl"},
    "La Liga": {"espn": "esp.1", "odds": "soccer_spain_la_liga"},
    "Serie A Italia": {"espn": "ita.1", "odds": "soccer_italy_serie_a"},
    "Bundesliga": {"espn": "ger.1", "odds": "soccer_germany_bundesliga"},
    "Ligue 1": {"espn": "fra.1", "odds": "soccer_france_ligue_one"},
    "Champions League": {"espn": "uefa.champions", "odds": "soccer_uefa_champs_league"},
    "Europa League": {"espn": "uefa.europa", "odds": "soccer_uefa_europa_league"},
}

TENIS_TORNEIOS = {
    "ATP French Open": "tennis_atp_french_open",
    "WTA French Open": "tennis_wta_french_open",
    "ATP Wimbledon": "tennis_atp_wimbledon",
    "WTA Wimbledon": "tennis_wta_wimbledon",
    "ATP US Open": "tennis_atp_us_open",
    "WTA US Open": "tennis_wta_us_open",
    "ATP Australian Open": "tennis_atp_aus_open_singles",
    "WTA Australian Open": "tennis_wta_aus_open_singles",
    "ATP Italian Open": "tennis_atp_italian_open",
    "WTA Italian Open": "tennis_wta_italian_open",
    "ATP Madrid Open": "tennis_atp_madrid_open",
    "WTA Madrid Open": "tennis_wta_madrid_open",
    "ATP Miami Open": "tennis_atp_miami_open",
    "WTA Miami Open": "tennis_wta_miami_open",
    "ATP Indian Wells": "tennis_atp_indian_wells",
    "WTA Indian Wells": "tennis_wta_indian_wells",
    "ATP Cincinnati Open": "tennis_atp_cincinnati_open",
    "WTA Cincinnati Open": "tennis_wta_cincinnati_open",
    "ATP Canadian Open": "tennis_atp_canadian_open",
    "WTA Canadian Open": "tennis_wta_canadian_open",
    "ATP Shanghai Masters": "tennis_atp_shanghai_masters",
    "ATP Paris Masters": "tennis_atp_paris_masters",
    "ATP China Open": "tennis_atp_china_open",
    "WTA China Open": "tennis_wta_china_open",
}

FORCA_BASE = {
    "Flamengo": 86, "Palmeiras": 85, "Botafogo": 81, "Atletico-MG": 80,
    "Sao Paulo": 78, "Fluminense": 78, "Gremio": 77, "Internacional": 77,
    "Corinthians": 76, "Cruzeiro": 75, "Bahia": 74, "Fortaleza": 73,
    "Vasco": 72, "Santos": 72, "Sport": 68, "Ceara": 69, "Vitoria": 69,
    "Manchester City": 91, "Arsenal": 88, "Liverpool": 88, "Chelsea": 82,
    "Tottenham Hotspur": 80, "Real Madrid": 90, "Barcelona": 88,
    "Atletico Madrid": 84, "Bayern Munich": 88, "Borussia Dortmund": 82,
    "Bayer Leverkusen": 84, "Inter Milan": 86, "Juventus": 82, "PSG": 88,
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
    "ac milan": "milan",
    "atletico mineiro": "atletico-mg",
    "atletico mg": "atletico-mg",
    "vasco da gama": "vasco",
    "flamengo rj": "flamengo",
    "botafogo rj": "botafogo",
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
    tuple(sorted(["liverpool", "everton"])),
    tuple(sorted(["inter milan", "milan"])),
}


# ============================================================
# VISUAL
# ============================================================

st.markdown(
    """
    <style>
    :root {
        --bg: #0b1117;
        --panel: #111a24;
        --panel2: #162331;
        --border: #243447;
        --text: #e8eef5;
        --muted: #91a4b7;
        --green: #23c483;
        --amber: #e6b450;
        --red: #ef6461;
        --blue: #4da3ff;
    }
    .stApp { background: var(--bg); color: var(--text); }
    .block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 1450px; }
    section[data-testid="stSidebar"] { background: #0f1720; border-right: 1px solid var(--border); }
    .hero {
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 18px 20px;
        margin-bottom: 16px;
    }
    .hero h1 { margin: 0; font-size: 1.75rem; letter-spacing: 0; }
    .hero p { margin: 6px 0 0; color: var(--muted); }
    .pro-card {
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 14px 16px;
        margin-bottom: 10px;
    }
    .pro-card.good { border-left: 5px solid var(--green); }
    .pro-card.medium { border-left: 5px solid var(--amber); }
    .pro-card.low { border-left: 5px solid var(--red); }
    .pro-card.live { border-left: 5px solid var(--blue); }
    .card-title { font-size: 1.05rem; font-weight: 800; margin-bottom: 4px; }
    .muted { color: var(--muted); font-size: .86rem; }
    .tag {
        display: inline-block;
        margin: 8px 6px 0 0;
        padding: 4px 8px;
        border-radius: 6px;
        border: 1px solid var(--border);
        background: var(--panel2);
        font-size: .82rem;
    }
    .tag strong { color: #fff; }
    .decision {
        display: inline-block;
        margin-top: 8px;
        padding: 5px 9px;
        border-radius: 6px;
        font-weight: 800;
        font-size: .82rem;
    }
    .decision.green { color: #06110d; background: var(--green); }
    .decision.amber { color: #161006; background: var(--amber); }
    .decision.red { color: #fff; background: var(--red); }
    div[data-testid="stMetric"] {
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 10px;
    }
    @media (max-width: 760px) {
        .block-container { padding-left: .7rem; padding-right: .7rem; }
        .hero h1 { font-size: 1.35rem; }
        .tag { display: block; width: fit-content; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HELPERS
# ============================================================

def agora_br():
    return datetime.now(TZ_BR)


def hoje_br():
    return agora_br().date()


def esc(x):
    return html.escape(str(x or ""), quote=True)


def pct(x):
    try:
        return f"{100 * float(x):.1f}%"
    except Exception:
        return "-"


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def nome_limpo(nome):
    return " ".join(str(nome or "").strip().split())


def normalizar_nome(nome):
    nome = nome_limpo(nome).lower()
    nome = unicodedata.normalize("NFKD", nome)
    nome = "".join(c for c in nome if not unicodedata.combining(c))
    nome = re.sub(r"\b(fc|cf|sc|afc)\b", "", nome)
    nome = re.sub(r"[^a-z0-9\s\-]", "", nome)
    nome = re.sub(r"\s+", " ", nome).strip()
    return ALIASES.get(nome, nome)


def nomes_equivalentes(a, b):
    na, nb = normalizar_nome(a), normalizar_nome(b)
    if not na or not nb:
        return False
    return na == nb or (len(na) >= 7 and na in nb) or (len(nb) >= 7 and nb in na)


def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(TZ_BR)
    except ValueError:
        return None


def poisson(k, lam):
    lam = max(0.03, float(lam))
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def decisao(score, edge=0.0):
    if score >= 76 and edge >= 0.015:
        return "Apostar", "green"
    if score >= 62:
        return "Cuidado", "amber"
    return "Evitar", "red"


def odd_justa(prob):
    prob = clamp(float(prob or 0), 0.0001, 0.9999)
    return 1 / prob


def valor_esperado(prob, odd):
    if odd <= 1:
        return 0.0
    return prob * odd - 1


def kelly_stake(prob, odd, banca, fracao=0.25):
    if odd <= 1 or banca <= 0:
        return 0.0
    b = odd - 1
    q = 1 - prob
    kelly = (b * prob - q) / b
    return max(0.0, kelly * fracao * banca)


def criar_jogo_manual(casa, fora):
    return {
        "id": "manual",
        "liga": "manual",
        "data": agora_br(),
        "data_txt": "Manual",
        "casa": nome_limpo(casa) or "Time da casa",
        "fora": nome_limpo(fora) or "Time visitante",
        "placar_casa": None,
        "placar_fora": None,
        "state": "pre",
        "completed": False,
        "status": "analise manual",
    }


def classe_score(score):
    if score >= 76:
        return "good"
    if score >= 62:
        return "medium"
    return "low"


# ============================================================
# APIS
# ============================================================

@st.cache_data(ttl=60, show_spinner=False)
def buscar_scoreboard_data(liga, data_yyyy_mm_dd):
    url = f"{ESPN_SOCCER_BASE}/{liga}/scoreboard"
    params = {"dates": data_yyyy_mm_dd.replace("-", ""), "limit": 300}
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.json(), ""
    except requests.RequestException as exc:
        return {}, f"Erro ESPN {liga}: {exc}"


@st.cache_data(ttl=900, show_spinner=False)
def buscar_odds(api_key, sport_key, markets="h2h", regions="eu,us,uk"):
    if not api_key or not sport_key:
        return [], ""
    url = f"{ODDS_API_BASE}/{sport_key}/odds"
    params = {
        "apiKey": api_key,
        "regions": regions,
        "markets": markets,
        "oddsFormat": "decimal",
        "dateFormat": "iso",
    }
    try:
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        return resp.json(), ""
    except requests.RequestException as exc:
        return [], f"Erro The Odds API ({sport_key}): {exc}"


def extrair_jogos(payload, liga):
    jogos = []
    for ev in payload.get("events", []) or []:
        comps = ev.get("competitions") or []
        if not comps:
            continue
        comp = comps[0]
        competidores = comp.get("competitors") or []
        if len(competidores) < 2:
            continue

        casa = next((c for c in competidores if c.get("homeAway") == "home"), competidores[0])
        fora = next((c for c in competidores if c.get("homeAway") == "away"), competidores[1])
        status = (comp.get("status") or {}).get("type") or {}
        dt = parse_dt(ev.get("date"))

        def score(c):
            try:
                s = c.get("score")
                return int(s) if s not in (None, "") else None
            except (TypeError, ValueError):
                return None

        jogos.append({
            "id": str(ev.get("id") or ""),
            "liga": liga,
            "data": dt,
            "data_txt": dt.strftime("%d/%m %H:%M") if dt else "Sem data",
            "casa": nome_limpo((casa.get("team") or {}).get("displayName")),
            "fora": nome_limpo((fora.get("team") or {}).get("displayName")),
            "placar_casa": score(casa),
            "placar_fora": score(fora),
            "state": status.get("state", ""),
            "completed": bool(status.get("completed", False)),
            "status": status.get("detail") or status.get("shortDetail") or "",
        })
    return jogos


def deduplicar(jogos):
    vistos = {}
    for j in jogos:
        dt = j.get("data")
        key = (dt.strftime("%Y-%m-%d") if dt else "", normalizar_nome(j["casa"]), normalizar_nome(j["fora"]))
        if key not in vistos or j.get("state") == "in" or j.get("completed"):
            vistos[key] = j
    return sorted(vistos.values(), key=lambda x: x.get("data") or agora_br())


@st.cache_data(ttl=900, show_spinner=False)
def buscar_periodo_futebol(liga, inicio_iso, fim_iso):
    inicio = datetime.fromisoformat(inicio_iso).date()
    fim = datetime.fromisoformat(fim_iso).date()
    jogos, logs = [], []
    dia = inicio
    while dia <= fim:
        data, erro = buscar_scoreboard_data(liga, dia.isoformat())
        if erro:
            logs.append(erro)
        jogos.extend(extrair_jogos(data, liga))
        dia += timedelta(days=1)
    return deduplicar(jogos), logs


def probabilidades_h2h(odd_event):
    best_book, best_probs = "", {}
    for book in odd_event.get("bookmakers", []) or []:
        for market in book.get("markets", []) or []:
            if market.get("key") != "h2h":
                continue
            raw = {}
            for outcome in market.get("outcomes", []) or []:
                price = outcome.get("price")
                name = outcome.get("name")
                if name and price and price > 1:
                    raw[name] = 1 / float(price)
            total = sum(raw.values())
            if total > 0:
                probs = {k: v / total for k, v in raw.items()}
                if not best_probs or len(probs) > len(best_probs):
                    best_book = book.get("title", "")
                    best_probs = probs
    return best_probs, best_book


def odds_futebol_para_jogo(jogo, odds_data):
    for ev in odds_data or []:
        home = ev.get("home_team", "")
        away = ev.get("away_team", "")
        bate = (
            nomes_equivalentes(jogo["casa"], home) and nomes_equivalentes(jogo["fora"], away)
        ) or (
            nomes_equivalentes(jogo["casa"], away) and nomes_equivalentes(jogo["fora"], home)
        )
        if not bate:
            continue

        probs_raw, book = probabilidades_h2h(ev)
        p_casa = p_empate = p_fora = None
        for nome, p in probs_raw.items():
            if nomes_equivalentes(nome, jogo["casa"]):
                p_casa = p
            elif nomes_equivalentes(nome, jogo["fora"]):
                p_fora = p
            elif normalizar_nome(nome) in {"draw", "empate"}:
                p_empate = p

        if p_casa is not None and p_fora is not None:
            return {"p_casa": p_casa, "p_empate": p_empate or 0.0, "p_fora": p_fora, "bookmaker": book}
    return None


# ============================================================
# FUTEBOL MODELO
# ============================================================

def forca_inicial(time):
    nt = normalizar_nome(time)
    for nome, valor in FORCA_BASE.items():
        if normalizar_nome(nome) == nt:
            return 1300 + valor * 6
    seed = sum(ord(c) for c in nome_limpo(time))
    return 1710 + (seed % 140) - 70


def novo_stats():
    return {
        "jogos": 0, "peso": 0.0, "gf": 0.0, "ga": 0.0,
        "home_peso": 0.0, "home_gf": 0.0, "home_ga": 0.0,
        "away_peso": 0.0, "away_gf": 0.0, "away_ga": 0.0,
        "pontos": [], "gols": [],
    }


def peso_recencia(data_jogo, ref_dt, meia_vida=45):
    if not data_jogo:
        return 1.0
    dias = max(0, (ref_dt.date() - data_jogo.date()).days)
    return 0.5 ** (dias / meia_vida)


def construir_contexto(jogos_encerrados, ref_dt=None):
    ref_dt = ref_dt or agora_br()
    jogos = [j for j in jogos_encerrados if j.get("completed") and j.get("placar_casa") is not None and j.get("data")]
    jogos = sorted(jogos, key=lambda x: x["data"])

    ratings, stats = {}, {}
    total_home = total_away = peso_total = empates = 0.0

    for j in jogos:
        casa, fora = j["casa"], j["fora"]
        gc, gf = int(j["placar_casa"]), int(j["placar_fora"])
        w = peso_recencia(j["data"], ref_dt)

        ratings.setdefault(casa, forca_inicial(casa))
        ratings.setdefault(fora, forca_inicial(fora))
        stats.setdefault(casa, novo_stats())
        stats.setdefault(fora, novo_stats())

        rc, rf = ratings[casa], ratings[fora]
        exp_casa = 1 / (1 + 10 ** ((rf - (rc + 58)) / 400))
        real_casa = 1.0 if gc > gf else 0.5 if gc == gf else 0.0
        if gc == gf:
            empates += w

        k = (18 + min(16, abs(gc - gf) * 5)) * (0.65 + 0.35 * w)
        delta = k * (real_casa - exp_casa)
        ratings[casa] = rc + delta
        ratings[fora] = rf - delta

        for time, gf_time, ga_time, is_home, pontos in [
            (casa, gc, gf, True, 3 if gc > gf else 1 if gc == gf else 0),
            (fora, gf, gc, False, 3 if gf > gc else 1 if gc == gf else 0),
        ]:
            s = stats[time]
            s["jogos"] += 1
            s["peso"] += w
            s["gf"] += gf_time * w
            s["ga"] += ga_time * w
            s["pontos"].append(pontos)
            s["gols"].append(gf_time)
            if is_home:
                s["home_peso"] += w
                s["home_gf"] += gf_time * w
                s["home_ga"] += ga_time * w
            else:
                s["away_peso"] += w
                s["away_gf"] += gf_time * w
                s["away_ga"] += ga_time * w

        total_home += gc * w
        total_away += gf * w
        peso_total += w

    return {
        "ratings": ratings,
        "stats": stats,
        "jogos": len(jogos),
        "liga_home": total_home / max(1.0, peso_total),
        "liga_away": total_away / max(1.0, peso_total),
        "taxa_empate": empates / max(1.0, peso_total),
    }


def media_stat(stats, time, campo, padrao):
    s = stats.get(time)
    if not s:
        return padrao
    if campo == "home_gf":
        return s["home_gf"] / max(1.0, s["home_peso"])
    if campo == "home_ga":
        return s["home_ga"] / max(1.0, s["home_peso"])
    if campo == "away_gf":
        return s["away_gf"] / max(1.0, s["away_peso"])
    if campo == "away_ga":
        return s["away_ga"] / max(1.0, s["away_peso"])
    return padrao


def matriz_poisson(lam_casa, lam_fora):
    mat, total = [], 0.0
    for i in range(MAX_GOLS + 1):
        row = []
        for j in range(MAX_GOLS + 1):
            p = poisson(i, lam_casa) * poisson(j, lam_fora)
            row.append(p)
            total += p
        mat.append(row)
    return [[p / total for p in row] for row in mat]


def prever_futebol(jogo, contexto, odds_info=None, usar_odds=True):
    casa, fora = jogo["casa"], jogo["fora"]
    ratings, stats = contexto["ratings"], contexto["stats"]
    rc = ratings.get(casa, forca_inicial(casa))
    rf = ratings.get(fora, forca_inicial(fora))
    liga_home = contexto["liga_home"] or 1.35
    liga_away = contexto["liga_away"] or 1.05

    ataque_casa = media_stat(stats, casa, "home_gf", liga_home)
    defesa_fora = media_stat(stats, fora, "away_ga", liga_home)
    ataque_fora = media_stat(stats, fora, "away_gf", liga_away)
    defesa_casa = media_stat(stats, casa, "home_ga", liga_away)
    elo_gap = (rc - rf + 58) / 400

    lam_casa = clamp((0.52 * ataque_casa + 0.48 * defesa_fora) * (1 + 0.16 * elo_gap), 0.25, 3.8)
    lam_fora = clamp((0.52 * ataque_fora + 0.48 * defesa_casa) * (1 - 0.14 * elo_gap), 0.20, 3.4)
    mat = matriz_poisson(lam_casa, lam_fora)

    p_casa = sum(mat[i][j] for i in range(MAX_GOLS + 1) for j in range(MAX_GOLS + 1) if i > j)
    p_empate = sum(mat[i][i] for i in range(MAX_GOLS + 1))
    p_fora = sum(mat[i][j] for i in range(MAX_GOLS + 1) for j in range(MAX_GOLS + 1) if i < j)

    p_empate = 0.72 * p_empate + 0.28 * contexto.get("taxa_empate", 0.26)
    total = p_casa + p_empate + p_fora
    p_casa, p_empate, p_fora = p_casa / total, p_empate / total, p_fora / total

    if usar_odds and odds_info:
        p_casa = 0.62 * p_casa + 0.38 * odds_info["p_casa"]
        p_empate = 0.62 * p_empate + 0.38 * odds_info["p_empate"]
        p_fora = 0.62 * p_fora + 0.38 * odds_info["p_fora"]
        total = p_casa + p_empate + p_fora
        p_casa, p_empate, p_fora = p_casa / total, p_empate / total, p_fora / total

    over15 = 1 - sum(mat[i][j] for i in range(2) for j in range(2 - i))
    over25 = 1 - sum(mat[i][j] for i in range(MAX_GOLS + 1) for j in range(MAX_GOLS + 1) if i + j <= 2)
    under35 = sum(mat[i][j] for i in range(MAX_GOLS + 1) for j in range(MAX_GOLS + 1) if i + j <= 3)
    btts = sum(mat[i][j] for i in range(1, MAX_GOLS + 1) for j in range(1, MAX_GOLS + 1))
    placares = sorted([(mat[i][j], i, j) for i in range(MAX_GOLS + 1) for j in range(MAX_GOLS + 1)], reverse=True)[:3]

    probs = {"Casa": p_casa, "Empate": p_empate, "Fora": p_fora}
    palpite = max(probs, key=probs.get)
    prob_palpite = probs[palpite]
    mercados = {
        "Over 1.5 gols": over15,
        "Over 2.5 gols": over25,
        "Under 3.5 gols": under35,
        "Ambas marcam": btts,
        f"{casa} ou empate": p_casa + p_empate,
        f"{fora} ou empate": p_fora + p_empate,
    }
    melhor_mercado, melhor_prob = max(mercados.items(), key=lambda x: x[1])

    riscos = []
    par = tuple(sorted([normalizar_nome(casa), normalizar_nome(fora)]))
    if par in CLASSICOS:
        riscos.append("classico")
    amostra = stats.get(casa, {}).get("jogos", 0) + stats.get(fora, {}).get("jogos", 0)
    if amostra < 10:
        riscos.append("baixa amostra")
    if abs(p_casa - p_fora) < 0.08:
        riscos.append("forcas proximas")

    score = int(clamp(45 + prob_palpite * 38 + melhor_prob * 18 + min(amostra, 40) * 0.25 - len(riscos) * 8, 0, 96))
    edge = 0.02 if melhor_prob >= 0.62 else 0.0
    label, color = decisao(score, edge)

    return {
        "p_casa": p_casa, "p_empate": p_empate, "p_fora": p_fora,
        "palpite": palpite, "prob_palpite": prob_palpite,
        "lam_casa": lam_casa, "lam_fora": lam_fora,
        "over15": over15, "over25": over25, "under35": under35, "btts": btts,
        "placares_top": placares,
        "melhor_mercado": melhor_mercado, "melhor_mercado_prob": melhor_prob,
        "score": score, "decisao": label, "decisao_cor": color,
        "conf_class": classe_score(score),
        "riscos": riscos,
        "amostra": amostra,
        "odds_aplicada": bool(usar_odds and odds_info),
    }


def resultado_real(jogo):
    gc, gf = jogo.get("placar_casa"), jogo.get("placar_fora")
    if gc is None or gf is None:
        return None
    return "Casa" if gc > gf else "Fora" if gf > gc else "Empate"


def backtest_futebol(jogos_hist, limite=80):
    encerrados = [j for j in jogos_hist if j.get("completed") and j.get("placar_casa") is not None and j.get("data")]
    encerrados = sorted(encerrados, key=lambda x: x["data"])
    avaliacoes = []
    for jogo in encerrados[-limite:]:
        real = resultado_real(jogo)
        antes = [x for x in encerrados if x["data"] < jogo["data"]]
        if not real or len(antes) < 8:
            continue
        contexto = construir_contexto(antes, ref_dt=jogo["data"] - timedelta(minutes=1))
        prev = prever_futebol(jogo, contexto, usar_odds=False)
        probs = {"Casa": prev["p_casa"], "Empate": prev["p_empate"], "Fora": prev["p_fora"]}
        brier = sum((probs[k] - (1 if k == real else 0)) ** 2 for k in probs) / 3
        avaliacoes.append({"jogo": jogo, "prev": prev, "real": real, "acertou": prev["palpite"] == real, "brier": brier})
    return avaliacoes


# ============================================================
# TENIS MODELO
# ============================================================

def carregar_ratings_tenis(uploaded_file):
    if uploaded_file is None:
        return {}
    try:
        df = pd.read_csv(uploaded_file)
    except Exception:
        return {}
    cols = {c.lower().strip(): c for c in df.columns}
    player_col = cols.get("player") or cols.get("jogador") or cols.get("nome")
    rating_col = cols.get("rating") or cols.get("elo") or cols.get("forca")
    if not player_col or not rating_col:
        return {}

    ratings = {}
    for _, row in df.iterrows():
        try:
            ratings[normalizar_nome(row[player_col])] = float(row[rating_col])
        except Exception:
            continue
    return ratings


def player_rating(nome, ratings):
    key = normalizar_nome(nome)
    if key in ratings:
        return ratings[key]
    seed = sum(ord(c) for c in nome_limpo(nome))
    return 1500 + (seed % 120) - 60


def prob_elo(r1, r2):
    return 1 / (1 + 10 ** ((r2 - r1) / 400))


def extrair_linha_tenis(evento):
    probs, book = probabilidades_h2h(evento)
    nomes = list(probs.keys())
    if len(nomes) < 2:
        return None
    p1, p2 = nomes[0], nomes[1]
    return {
        "id": evento.get("id", ""),
        "torneio": evento.get("sport_title") or evento.get("sport_key", ""),
        "data": parse_dt(evento.get("commence_time")),
        "jogador1": p1,
        "jogador2": p2,
        "odd_prob_1": probs.get(p1, 0.5),
        "odd_prob_2": probs.get(p2, 0.5),
        "bookmaker": book,
    }


def mercado_tenis_info(evento):
    spreads, totals = [], []
    for book in evento.get("bookmakers", []) or []:
        for market in book.get("markets", []) or []:
            key = market.get("key")
            for o in market.get("outcomes", []) or []:
                if o.get("point") is None or not o.get("price"):
                    continue
                if key == "spreads":
                    spreads.append(f"{o.get('name')} {o.get('point'):+g} @ {o.get('price')}")
                elif key == "totals":
                    totals.append(f"{o.get('name')} {o.get('point'):g} @ {o.get('price')}")
    return spreads[:2], totals[:2]


def prever_tenis(linha, ratings):
    r1 = player_rating(linha["jogador1"], ratings)
    r2 = player_rating(linha["jogador2"], ratings)
    p_model_1 = prob_elo(r1, r2)
    p_model_2 = 1 - p_model_1

    tem_rating = normalizar_nome(linha["jogador1"]) in ratings or normalizar_nome(linha["jogador2"]) in ratings
    peso_modelo = 0.32 if tem_rating else 0.12
    p1 = (1 - peso_modelo) * linha["odd_prob_1"] + peso_modelo * p_model_1
    p2 = (1 - peso_modelo) * linha["odd_prob_2"] + peso_modelo * p_model_2
    total = p1 + p2
    p1, p2 = p1 / total, p2 / total

    vencedor = linha["jogador1"] if p1 >= p2 else linha["jogador2"]
    prob_vencedor = max(p1, p2)
    odd_prob = linha["odd_prob_1"] if vencedor == linha["jogador1"] else linha["odd_prob_2"]
    edge = prob_vencedor - odd_prob

    riscos = []
    if not tem_rating:
        riscos.append("sem rating proprio")
    if abs(p1 - p2) < 0.08:
        riscos.append("partida equilibrada")
    if edge < 0:
        riscos.append("sem valor contra odds")

    score = int(clamp(42 + prob_vencedor * 42 + max(edge, 0) * 180 + (10 if tem_rating else -2) - len(riscos) * 4, 0, 96))
    label, color = decisao(score, edge)

    return {
        "p1": p1, "p2": p2,
        "vencedor": vencedor,
        "prob_vencedor": prob_vencedor,
        "edge": edge,
        "score": score,
        "decisao": label,
        "decisao_cor": color,
        "conf_class": classe_score(score),
        "riscos": riscos,
        "rating1": r1,
        "rating2": r2,
        "tem_rating": tem_rating,
    }


# ============================================================
# RENDER
# ============================================================

def render_card_futebol(jogo, r):
    placar = ""
    if jogo.get("placar_casa") is not None:
        placar = f" - {jogo['placar_casa']} x {jogo['placar_fora']}"
    palpite_nome = {"Casa": jogo["casa"], "Fora": jogo["fora"], "Empate": "Empate"}[r["palpite"]]
    riscos = ", ".join(r["riscos"]) if r["riscos"] else "baixo risco contextual"
    st.markdown(
        f"""
        <div class="pro-card {r['conf_class']}">
            <div class="card-title">{esc(jogo['casa'])} x {esc(jogo['fora'])}{esc(placar)}</div>
            <div class="muted">{esc(jogo['data_txt'])} | {esc(jogo.get('status') or jogo.get('state') or 'programado')}</div>
            <span class="tag">Palpite 1X2: <strong>{esc(palpite_nome)}</strong></span>
            <span class="tag">Probabilidade: <strong>{pct(r['prob_palpite'])}</strong></span>
            <span class="tag">Melhor mercado: <strong>{esc(r['melhor_mercado'])} {pct(r['melhor_mercado_prob'])}</strong></span>
            <span class="tag">Placar provavel: <strong>{r['placares_top'][0][1]}x{r['placares_top'][0][2]}</strong></span>
            <span class="tag">Gols esp.: <strong>{r['lam_casa']:.2f} x {r['lam_fora']:.2f}</strong></span>
            <br><span class="decision {r['decisao_cor']}">{esc(r['decisao'])}</span>
            <span class="tag">Score: <strong>{r['score']}/100</strong></span>
            <span class="tag">Alertas: <strong>{esc(riscos)}</strong></span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_card_tenis(linha, r, spreads=None, totals=None):
    dt = linha["data"].strftime("%d/%m %H:%M") if linha.get("data") else "Sem data"
    riscos = ", ".join(r["riscos"]) if r["riscos"] else "baixo risco contextual"
    extras = []
    if spreads:
        extras.append("Handicap: " + " | ".join(spreads))
    if totals:
        extras.append("Games: " + " | ".join(totals))
    extras_txt = " | ".join(extras) if extras else "Mercados extras indisponiveis nesta casa"
    st.markdown(
        f"""
        <div class="pro-card {r['conf_class']}">
            <div class="card-title">{esc(linha['jogador1'])} x {esc(linha['jogador2'])}</div>
            <div class="muted">{esc(linha['torneio'])} | {esc(dt)} | {esc(linha.get('bookmaker') or 'bookmaker n/d')}</div>
            <span class="tag">Vencedor: <strong>{esc(r['vencedor'])}</strong></span>
            <span class="tag">Probabilidade: <strong>{pct(r['prob_vencedor'])}</strong></span>
            <span class="tag">Valor vs odds: <strong>{r['edge']*100:+.1f} p.p.</strong></span>
            <span class="tag">Rating: <strong>{r['rating1']:.0f} x {r['rating2']:.0f}</strong></span>
            <br><span class="decision {r['decisao_cor']}">{esc(r['decisao'])}</span>
            <span class="tag">Score: <strong>{r['score']}/100</strong></span>
            <span class="tag">Alertas: <strong>{esc(riscos)}</strong></span>
            <div class="muted" style="margin-top:8px">{esc(extras_txt)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_value_box(titulo, prob, odd, banca):
    ev = valor_esperado(prob, odd)
    stake = kelly_stake(prob, odd, banca)
    classe = "good" if ev > 0.04 else "medium" if ev > 0 else "low"
    decisao_txt = "Entrada com valor" if ev > 0 else "Sem valor"
    st.markdown(
        f"""
        <div class="pro-card {classe}">
            <div class="card-title">{esc(titulo)}</div>
            <span class="tag">Probabilidade modelo: <strong>{pct(prob)}</strong></span>
            <span class="tag">Odd justa: <strong>{odd_justa(prob):.2f}</strong></span>
            <span class="tag">Odd mercado: <strong>{odd:.2f}</strong></span>
            <span class="tag">EV: <strong>{ev * 100:+.1f}%</strong></span>
            <br><span class="decision {'green' if ev > 0 else 'red'}">{esc(decisao_txt)}</span>
            <span class="tag">Stake Kelly 25%: <strong>R$ {stake:.2f}</strong></span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# APP
# ============================================================

st.markdown(
    """
    <div class="hero">
        <h1>Analisador Esportivo Pro 9.1</h1>
        <p>Futebol e Tenis com jogos reais, simulador manual, valor esperado, Kelly, risco e diagnostico do modelo.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Configuracao")
    odds_key = st.text_input("The Odds API key", type="password", placeholder="opcional, recomendado para Tenis")
    usar_odds = st.checkbox("Usar odds quando disponiveis", value=True)
    banca_usuario = st.number_input("Banca para sugestao de stake (R$)", min_value=0.0, value=1000.0, step=50.0)

    st.divider()
    st.subheader("Futebol")
    liga_nome = st.selectbox("Competicao", list(FUTEBOL_COMPETICOES.keys()))
    dias_hist = st.slider("Historico usado pelo modelo", 30, 240, 120, step=15)
    janela_fut = st.slider("Proximos dias", 1, 14, 7)

    st.divider()
    st.subheader("Tenis")
    torneios_escolhidos = st.multiselect(
        "Torneios",
        list(TENIS_TORNEIOS.keys()),
        default=["ATP French Open", "WTA French Open", "ATP Italian Open", "WTA Italian Open"],
    )
    ratings_file = st.file_uploader("CSV de ratings: player/jogador + rating/elo", type=["csv"])

    st.divider()
    if st.button("Atualizar dados"):
        st.cache_data.clear()
        st.rerun()

ratings_tenis = carregar_ratings_tenis(ratings_file)
hoje = hoje_br()
liga_cfg = FUTEBOL_COMPETICOES[liga_nome]

with st.spinner("Carregando futebol..."):
    hist_fut, logs_hist = buscar_periodo_futebol(
        liga_cfg["espn"],
        (hoje - timedelta(days=dias_hist)).isoformat(),
        (hoje - timedelta(days=1)).isoformat(),
    )
    contexto_fut = construir_contexto(hist_fut)
    jogos_fut, logs_fut = buscar_periodo_futebol(
        liga_cfg["espn"],
        (hoje - timedelta(days=1)).isoformat(),
        (hoje + timedelta(days=janela_fut)).isoformat(),
    )
    odds_fut, odds_log_fut = buscar_odds(odds_key, liga_cfg["odds"], markets="h2h") if usar_odds and odds_key else ([], "")

with st.spinner("Carregando tenis..."):
    eventos_tenis, logs_tenis = [], []
    if odds_key:
        for nome_torneio in torneios_escolhidos:
            dados, erro = buscar_odds(odds_key, TENIS_TORNEIOS[nome_torneio], markets="h2h,spreads,totals")
            if erro:
                logs_tenis.append(erro)
            eventos_tenis.extend(dados)

previsoes_fut = []
for jogo in jogos_fut:
    odds_info = odds_futebol_para_jogo(jogo, odds_fut) if odds_fut else None
    previsoes_fut.append((jogo, prever_futebol(jogo, contexto_fut, odds_info, usar_odds=usar_odds)))

previsoes_tenis = []
for ev in eventos_tenis:
    linha = extrair_linha_tenis(ev)
    if not linha:
        continue
    spreads, totals = mercado_tenis_info(ev)
    previsoes_tenis.append((linha, prever_tenis(linha, ratings_tenis), spreads, totals))

aba_futebol, aba_tenis, aba_oportunidades, aba_ao_vivo, aba_diag = st.tabs(
    ["Futebol", "Tenis", "Melhores oportunidades", "Ao vivo", "Diagnostico do modelo"]
)

with aba_futebol:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Jogos encontrados", len(jogos_fut))
    c2.metric("Base do modelo", contexto_fut["jogos"])
    c3.metric("Media casa", f"{contexto_fut['liga_home']:.2f}")
    c4.metric("Media fora", f"{contexto_fut['liga_away']:.2f}")
    c5.metric("Empate liga", pct(contexto_fut["taxa_empate"]))

    if logs_fut or logs_hist or odds_log_fut:
        with st.expander("Avisos de dados"):
            for log in (logs_fut + logs_hist + ([odds_log_fut] if odds_log_fut else []))[:12]:
                st.write(log)

    futuros = [(j, r) for j, r in previsoes_fut if j.get("state") != "post"]
    if not futuros:
        st.warning("Nenhum jogo futuro encontrado para os filtros.")
    else:
        df = pd.DataFrame([{
            "Data": j["data_txt"],
            "Jogo": f"{j['casa']} x {j['fora']}",
            "Palpite": {"Casa": j["casa"], "Fora": j["fora"], "Empate": "Empate"}[r["palpite"]],
            "Prob.": pct(r["prob_palpite"]),
            "Melhor mercado": r["melhor_mercado"],
            "Prob. mercado": pct(r["melhor_mercado_prob"]),
            "Decisao": r["decisao"],
            "Score": r["score"],
            "Alertas": ", ".join(r["riscos"]) if r["riscos"] else "baixo risco",
        } for j, r in futuros])
        st.dataframe(df, use_container_width=True, hide_index=True)
        for jogo, r in sorted(futuros, key=lambda x: x[1]["score"], reverse=True):
            render_card_futebol(jogo, r)

    with st.expander("Analisar partida manual de futebol"):
        m1, m2, m3 = st.columns(3)
        with m1:
            casa_manual = st.text_input("Time da casa", "Flamengo")
            fora_manual = st.text_input("Time visitante", "Palmeiras")
        with m2:
            odd_casa_manual = st.number_input("Odd casa", min_value=1.01, max_value=50.0, value=2.10, step=0.05)
            odd_empate_manual = st.number_input("Odd empate", min_value=1.01, max_value=50.0, value=3.40, step=0.05)
            odd_fora_manual = st.number_input("Odd fora", min_value=1.01, max_value=50.0, value=3.60, step=0.05)
        with m3:
            ajuste_casa = st.slider("Ajuste casa", -30, 30, 0)
            ajuste_fora = st.slider("Ajuste fora", -30, 30, 0)

        jogo_manual = criar_jogo_manual(casa_manual, fora_manual)
        contexto_manual = {
            **contexto_fut,
            "ratings": {
                **contexto_fut["ratings"],
                jogo_manual["casa"]: forca_inicial(jogo_manual["casa"]) + ajuste_casa,
                jogo_manual["fora"]: forca_inicial(jogo_manual["fora"]) + ajuste_fora,
            },
        }
        r_manual = prever_futebol(jogo_manual, contexto_manual, usar_odds=False)
        render_card_futebol(jogo_manual, r_manual)

        v1, v2, v3 = st.columns(3)
        with v1:
            render_value_box(jogo_manual["casa"], r_manual["p_casa"], odd_casa_manual, banca_usuario)
        with v2:
            render_value_box("Empate", r_manual["p_empate"], odd_empate_manual, banca_usuario)
        with v3:
            render_value_box(jogo_manual["fora"], r_manual["p_fora"], odd_fora_manual, banca_usuario)

with aba_tenis:
    t1, t2, t3 = st.columns(3)
    t1.metric("Partidas de tenis", len(previsoes_tenis))
    t2.metric("Ratings carregados", len(ratings_tenis))
    t3.metric("Torneios consultados", len(torneios_escolhidos))

    if logs_tenis:
        with st.expander("Avisos do tenis"):
            for log in logs_tenis[:12]:
                st.write(log)

    if not odds_key:
        st.warning("Para listar partidas reais de tenis, informe uma chave da The Odds API na lateral.")
    elif not previsoes_tenis:
        st.warning("Nenhuma partida encontrada. Em tenis, a API retorna dados apenas para torneios ativos.")
    else:
        df_tenis = pd.DataFrame([{
            "Data": l["data"].strftime("%d/%m %H:%M") if l.get("data") else "Sem data",
            "Partida": f"{l['jogador1']} x {l['jogador2']}",
            "Vencedor": r["vencedor"],
            "Prob.": pct(r["prob_vencedor"]),
            "Valor vs odds": f"{r['edge']*100:+.1f} p.p.",
            "Decisao": r["decisao"],
            "Score": r["score"],
            "Alertas": ", ".join(r["riscos"]) if r["riscos"] else "baixo risco",
        } for l, r, _, _ in previsoes_tenis])
        st.dataframe(df_tenis, use_container_width=True, hide_index=True)
        for linha, r, spreads, totals in sorted(previsoes_tenis, key=lambda x: x[1]["score"], reverse=True):
            render_card_tenis(linha, r, spreads, totals)

    with st.expander("Analisar partida manual de tenis"):
        mt1, mt2, mt3 = st.columns(3)
        with mt1:
            tenista_1 = st.text_input("Tenista 1", "Novak Djokovic")
            tenista_2 = st.text_input("Tenista 2", "Carlos Alcaraz")
        with mt2:
            forma_1 = st.slider("Forma recente tenista 1 (%)", 0, 100, 78)
            forma_2 = st.slider("Forma recente tenista 2 (%)", 0, 100, 74)
            superficie_1 = st.slider("Aderencia a superficie tenista 1 (%)", 0, 100, 76)
            superficie_2 = st.slider("Aderencia a superficie tenista 2 (%)", 0, 100, 80)
        with mt3:
            h2h_1 = st.number_input("Vitorias H2H tenista 1", min_value=0, max_value=50, value=3)
            h2h_2 = st.number_input("Vitorias H2H tenista 2", min_value=0, max_value=50, value=2)
            odd_1 = st.number_input("Odd tenista 1", min_value=1.01, max_value=50.0, value=1.90, step=0.05)
            odd_2 = st.number_input("Odd tenista 2", min_value=1.01, max_value=50.0, value=1.95, step=0.05)

        rating_1 = player_rating(tenista_1, ratings_tenis)
        rating_2 = player_rating(tenista_2, ratings_tenis)
        elo_1 = prob_elo(rating_1, rating_2)
        forma_total = max(1, forma_1 + forma_2)
        sup_total = max(1, superficie_1 + superficie_2)
        h2h_total = max(1, h2h_1 + h2h_2)
        p_manual_1 = (
            0.42 * (forma_1 / forma_total)
            + 0.28 * (superficie_1 / sup_total)
            + 0.20 * elo_1
            + 0.10 * (h2h_1 / h2h_total)
        )
        p_manual_2 = 1 - p_manual_1
        vencedor_manual = tenista_1 if p_manual_1 >= p_manual_2 else tenista_2
        st.markdown(
            f"""
            <div class="pro-card {'good' if max(p_manual_1, p_manual_2) >= 0.58 else 'medium'}">
                <div class="card-title">{esc(tenista_1)} x {esc(tenista_2)}</div>
                <span class="tag">Favorito: <strong>{esc(vencedor_manual)}</strong></span>
                <span class="tag">{esc(tenista_1)}: <strong>{pct(p_manual_1)}</strong></span>
                <span class="tag">{esc(tenista_2)}: <strong>{pct(p_manual_2)}</strong></span>
                <span class="tag">Rating: <strong>{rating_1:.0f} x {rating_2:.0f}</strong></span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        tv1, tv2 = st.columns(2)
        with tv1:
            render_value_box(tenista_1, p_manual_1, odd_1, banca_usuario)
        with tv2:
            render_value_box(tenista_2, p_manual_2, odd_2, banca_usuario)

with aba_oportunidades:
    st.subheader("Melhores oportunidades")
    itens = []
    for jogo, r in previsoes_fut:
        if jogo.get("state") != "post":
            itens.append(("Futebol", r["score"], r, jogo, None, None))
    for linha, r, spreads, totals in previsoes_tenis:
        itens.append(("Tenis", r["score"], r, linha, spreads, totals))

    itens = sorted(itens, key=lambda x: x[1], reverse=True)[:15]
    if not itens:
        st.warning("Ainda nao ha oportunidades com os filtros atuais.")
    for tipo, _, r, obj, spreads, totals in itens:
        st.caption(tipo)
        if tipo == "Futebol":
            render_card_futebol(obj, r)
        else:
            render_card_tenis(obj, r, spreads, totals)

with aba_ao_vivo:
    st.subheader("Ao vivo")
    ao_vivo = [(j, r) for j, r in previsoes_fut if j.get("state") == "in"]
    if not ao_vivo:
        st.info("Nenhum jogo de futebol ao vivo encontrado agora. Para tenis ao vivo, use torneios ativos com odds atualizadas.")
    for jogo, r in ao_vivo:
        r = {**r, "conf_class": "live"}
        render_card_futebol(jogo, r)

with aba_diag:
    st.subheader("Diagnostico do modelo")
    avaliacoes = backtest_futebol(hist_fut, limite=80)
    if not avaliacoes:
        st.warning("Sem amostra suficiente para backtest temporal nesta competicao.")
    else:
        total = len(avaliacoes)
        acertos = sum(a["acertou"] for a in avaliacoes)
        brier = sum(a["brier"] for a in avaliacoes) / total
        fortes = [a for a in avaliacoes if a["prev"]["score"] >= 62]
        taxa_fortes = sum(a["acertou"] for a in fortes) / len(fortes) if fortes else 0

        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Jogos avaliados", total)
        d2.metric("Acertos 1X2", f"{acertos}/{total}", pct(acertos / total))
        d3.metric("Score >= 62", len(fortes), pct(taxa_fortes))
        d4.metric("Brier medio", f"{brier:.3f}")

        rows = []
        for a in reversed(avaliacoes[-30:]):
            j, r = a["jogo"], a["prev"]
            rows.append({
                "Jogo": f"{j['casa']} {j['placar_casa']} x {j['placar_fora']} {j['fora']}",
                "Palpite": {"Casa": j["casa"], "Fora": j["fora"], "Empate": "Empate"}[r["palpite"]],
                "Real": {"Casa": j["casa"], "Fora": j["fora"], "Empate": "Empate"}[a["real"]],
                "Acertou": "sim" if a["acertou"] else "nao",
                "Score": r["score"],
                "Brier": round(a["brier"], 3),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.caption(f"Atualizado em {agora_br().strftime('%d/%m/%Y %H:%M:%S')} | Horario de Brasilia")
