
import math
import html
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, List, Tuple, Optional

import pandas as pd
import requests
import streamlit as st


# ============================================================
# ANÁLISE FUTEBOL PRO 6.0
# - ESPN scoreboard
# - Elo + Poisson normalizado
# - Ajuste de empate, clássico, odds, xG, desfalques
# - Live: minuto, placar, vermelhos e pressão manual
# - UI colorida + melhores palpites + jogos seguros + alertas
# ============================================================

st.set_page_config(
    page_title="Analisador Futebol Pro 6.0",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

TZ_BR = ZoneInfo("America/Sao_Paulo")
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
HEADERS = {"User-Agent": "Mozilla/5.0 AnalisadorFutebolPro/6.0"}

MAX_GOLS = 10


# ============================================================
# CONFIGURAÇÕES
# ============================================================

COMPETICOES = {
    "Brasileirão Série A": {"espn": "bra.1", "odds": "soccer_brazil_campeonato"},
    "Brasileirão Série B": {"espn": "bra.2", "odds": "soccer_brazil_serie_b"},
    "Copa do Brasil": {"espn": "bra.copa_do_brasil", "odds": "soccer_brazil_copa_do_brasil"},
    "Libertadores": {"espn": "conmebol.libertadores", "odds": "soccer_conmebol_copa_libertadores"},
    "Sul-Americana": {"espn": "conmebol.sudamericana", "odds": "soccer_conmebol_copa_sudamericana"},
    "Premier League": {"espn": "eng.1", "odds": "soccer_epl"},
    "La Liga": {"espn": "esp.1", "odds": "soccer_spain_la_liga"},
    "Serie A Itália": {"espn": "ita.1", "odds": "soccer_italy_serie_a"},
    "Bundesliga": {"espn": "ger.1", "odds": "soccer_germany_bundesliga"},
    "Ligue 1": {"espn": "fra.1", "odds": "soccer_france_ligue_one"},
    "Champions League": {"espn": "uefa.champions", "odds": "soccer_uefa_champs_league"},
    "Europa League": {"espn": "uefa.europa", "odds": "soccer_uefa_europa_league"},
}

FORCA_BASE = {
    "Flamengo": 86, "Palmeiras": 85, "Botafogo": 81, "Atlético-MG": 80, "Atletico-MG": 80,
    "São Paulo": 78, "Sao Paulo": 78, "Fluminense": 78, "Grêmio": 77, "Gremio": 77,
    "Internacional": 77, "Corinthians": 76, "Cruzeiro": 75, "Bahia": 74, "Fortaleza": 73,
    "Vasco": 72, "Santos": 72, "Sport": 68, "Ceará": 69, "Ceara": 69, "Vitória": 69,
    "Vitoria": 69, "Manchester City": 91, "Arsenal": 88, "Liverpool": 88, "Chelsea": 82,
    "Tottenham Hotspur": 80, "Real Madrid": 90, "Barcelona": 88, "Atlético Madrid": 84,
    "Atletico Madrid": 84, "Bayern Munich": 88, "Borussia Dortmund": 82,
    "Bayer Leverkusen": 84, "Inter Milan": 86, "Juventus": 82, "PSG": 88,
}

CLASSICOS = {
    tuple(sorted(map(lambda x: x.lower(), ["Flamengo", "Vasco"]))),
    tuple(sorted(map(lambda x: x.lower(), ["Flamengo", "Fluminense"]))),
    tuple(sorted(map(lambda x: x.lower(), ["Flamengo", "Botafogo"]))),
    tuple(sorted(map(lambda x: x.lower(), ["Palmeiras", "Corinthians"]))),
    tuple(sorted(map(lambda x: x.lower(), ["São Paulo", "Corinthians"]))),
    tuple(sorted(map(lambda x: x.lower(), ["São Paulo", "Palmeiras"]))),
    tuple(sorted(map(lambda x: x.lower(), ["Grêmio", "Internacional"]))),
    tuple(sorted(map(lambda x: x.lower(), ["Atlético-MG", "Cruzeiro"]))),
    tuple(sorted(map(lambda x: x.lower(), ["Real Madrid", "Barcelona"]))),
    tuple(sorted(map(lambda x: x.lower(), ["Manchester United", "Manchester City"]))),
    tuple(sorted(map(lambda x: x.lower(), ["Liverpool", "Everton"]))),
    tuple(sorted(map(lambda x: x.lower(), ["Inter Milan", "AC Milan"]))),
}

# Sinônimos usados para casar ESPN, odds e xG.
TIME_ALIASES = {
    "man city": "manchester city",
    "manchester city fc": "manchester city",
    "man united": "manchester united",
    "man utd": "manchester united",
    "tottenham": "tottenham hotspur",
    "spurs": "tottenham hotspur",
    "psg": "paris saint-germain",
    "paris sg": "paris saint-germain",
    "inter": "inter milan",
    "internazionale": "inter milan",
    "ac milan": "milan",
    "atletico mg": "atletico-mg",
    "atlético mineiro": "atletico-mg",
    "atletico mineiro": "atletico-mg",
    "sao paulo": "são paulo",
    "gremio": "grêmio",
    "vitoria": "vitória",
    "ceara": "ceará",
    "flamengo rj": "flamengo",
    "vasco da gama": "vasco",
    "botafogo rj": "botafogo",
}


# ============================================================
# CSS COLORIDO
# ============================================================

st.markdown(
    """
    <style>
        :root {
            --card-bg: rgba(255,255,255,.075);
            --border: rgba(255,255,255,.16);
            --green: #22c55e;
            --yellow: #f59e0b;
            --red: #ef4444;
            --blue: #38bdf8;
            --purple: #a78bfa;
        }
        .block-container { padding-top: 1rem; padding-bottom: 2rem; }
        .hero {
            border-radius: 26px;
            padding: 22px 24px;
            background: linear-gradient(135deg, rgba(34,197,94,.22), rgba(56,189,248,.16), rgba(167,139,250,.18));
            border: 1px solid var(--border);
            box-shadow: 0 16px 40px rgba(0,0,0,.18);
            margin-bottom: 18px;
        }
        .hero h1 {
            margin: 0;
            font-size: 2.15rem;
            letter-spacing: -0.04em;
        }
        .hero .sub { opacity: .82; margin-top: 5px; font-size: 1rem; }
        .game-card {
            border: 1px solid var(--border);
            border-radius: 22px;
            padding: 16px 18px;
            margin-bottom: 14px;
            background: var(--card-bg);
            box-shadow: 0 10px 30px rgba(0,0,0,.10);
        }
        .game-title { font-size: 1.08rem; font-weight: 800; margin-bottom: 5px; }
        .muted { opacity: .72; font-size: .88rem; }
        .pill {
            display: inline-block;
            padding: 5px 10px;
            border-radius: 999px;
            border: 1px solid rgba(255,255,255,.18);
            font-size: .82rem;
            margin-right: 5px;
            margin-top: 7px;
            background: rgba(255,255,255,.06);
        }
        .good { border-left: 7px solid var(--green); }
        .medium { border-left: 7px solid var(--yellow); }
        .low { border-left: 7px solid var(--red); }
        .live-box {
            border: 1px solid rgba(239,68,68,.42);
            border-left: 7px solid var(--red);
            border-radius: 22px;
            padding: 16px 18px;
            margin-bottom: 14px;
            background: linear-gradient(135deg, rgba(239,68,68,.17), rgba(245,158,11,.10));
            box-shadow: 0 10px 30px rgba(0,0,0,.12);
        }
        .safe-box {
            border: 1px solid rgba(34,197,94,.36);
            border-left: 7px solid var(--green);
            background: linear-gradient(135deg, rgba(34,197,94,.12), rgba(56,189,248,.08));
        }
        .risk {
            color: #fecaca;
            font-weight: 700;
        }
        .ok {
            color: #bbf7d0;
            font-weight: 700;
        }
        div[data-testid="stMetric"] {
            border-radius: 18px;
            padding: 10px;
            background: rgba(255,255,255,.06);
            border: 1px solid rgba(255,255,255,.10);
        }
        @media (max-width: 700px) {
            .block-container { padding-left: .7rem; padding-right: .7rem; }
            .hero h1 { font-size: 1.55rem; }
            div[data-testid="stMetricValue"] { font-size: 1.05rem; }
            .game-title { font-size: 1rem; }
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
    nome = nome.replace(" fc", "").replace(" cf", "").replace(" sc", "")
    nome = re.sub(r"[^a-z0-9\s\-]", "", nome)
    nome = re.sub(r"\s+", " ", nome).strip()
    return TIME_ALIASES.get(nome, nome)


def nomes_equivalentes(a, b):
    na = normalizar_nome(a)
    nb = normalizar_nome(b)
    return na == nb or na in nb or nb in na


def eh_classico(casa, fora):
    par = tuple(sorted([normalizar_nome(casa), normalizar_nome(fora)]))
    return par in CLASSICOS


def buscar_forca_base(nome):
    n = nome_limpo(nome)
    if n in FORCA_BASE:
        return FORCA_BASE[n]
    nn = normalizar_nome(n)
    for k, v in FORCA_BASE.items():
        if normalizar_nome(k) == nn:
            return v
    return None


def forca_inicial(nome):
    base = buscar_forca_base(nome)
    if base is not None:
        return 1300 + base * 6
    seed = sum(ord(c) for c in nome_limpo(nome))
    return 1720 + (seed % 120) - 60


def parse_dt_espn(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(TZ_BR)
    except Exception:
        return None


def poisson(k, lam):
    lam = max(0.03, float(lam))
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def status_legivel(jogo):
    state = jogo.get("state")
    detalhe = jogo.get("status", "")
    if state == "in":
        return f"🔴 Ao vivo — {detalhe}"
    if state == "post":
        return "✅ Encerrado"
    return "🕒 Futuro"


def resultado_real(jogo):
    gc = jogo.get("placar_casa")
    gf = jogo.get("placar_fora")
    if gc is None or gf is None:
        return None
    if gc > gf:
        return "Casa"
    if gc < gf:
        return "Fora"
    return "Empate"


def extrair_minuto(status):
    s = str(status or "")
    m = re.search(r"(\d+)\s*['’]", s)
    if m:
        return clamp(int(m.group(1)), 0, 120)
    m = re.search(r"(\d+):\d+", s)
    if m:
        return clamp(int(m.group(1)), 0, 120)
    if "half" in s.lower() or "intervalo" in s.lower():
        return 45
    return 0


# ============================================================
# ESPN API
# ============================================================

@st.cache_data(ttl=60, show_spinner=False)
def buscar_scoreboard_data(liga, data_yyyy_mm_dd):
    data_api = data_yyyy_mm_dd.replace("-", "")
    url = f"{ESPN_BASE}/{liga}/scoreboard"
    params = {"dates": data_api, "limit": 300}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.json(), ""
    except requests.RequestException as e:
        return {}, f"Erro ESPN {liga} em {data_yyyy_mm_dd}: {e}"


@st.cache_data(ttl=900, show_spinner=False)
def buscar_periodo(liga, inicio_iso, fim_iso):
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


@st.cache_data(ttl=18, show_spinner=False)
def buscar_ao_vivo_rapido(liga):
    hoje = hoje_br()
    jogos, logs = [], []
    for dia in [hoje - timedelta(days=1), hoje, hoje + timedelta(days=1)]:
        data, erro = buscar_scoreboard_data(liga, dia.isoformat())
        if erro:
            logs.append(erro)
        jogos.extend(extrair_jogos(data, liga))
    jogos = deduplicar(jogos)
    jogos.sort(key=lambda j: (0 if j.get("state") == "in" else 1 if j.get("state") == "pre" else 2, j.get("data") or agora_br()))
    return jogos, logs


def extrair_jogos(payload, liga):
    eventos = payload.get("events", []) or []
    jogos = []
    for ev in eventos:
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
        dt = parse_dt_espn(ev.get("date"))

        def score(c):
            try:
                s = c.get("score")
                return int(s) if s not in (None, "") else None
            except Exception:
                return None

        jogos.append({
            "id": str(ev.get("id") or ""),
            "liga": liga,
            "data": dt,
            "data_txt": dt.strftime("%d/%m %H:%M") if dt else "Sem data",
            "casa": nome_limpo(((casa.get("team") or {}).get("displayName"))),
            "fora": nome_limpo(((fora.get("team") or {}).get("displayName"))),
            "placar_casa": score(casa),
            "placar_fora": score(fora),
            "state": status.get("state", ""),
            "completed": bool(status.get("completed", False)),
            "status": status.get("detail") or status.get("shortDetail") or "",
        })
    return jogos


def chave_jogo(j):
    data = j.get("data")
    data_key = data.strftime("%Y-%m-%d") if data else ""
    return (data_key, normalizar_nome(j.get("casa")), normalizar_nome(j.get("fora")))


def deduplicar(jogos):
    vistos = {}
    for j in jogos:
        k = chave_jogo(j)
        antigo = vistos.get(k)
        if not antigo:
            vistos[k] = j
        elif j.get("state") == "in" or j.get("completed"):
            vistos[k] = j
    return sorted(vistos.values(), key=lambda x: x.get("data") or agora_br())


# ============================================================
# ODDS THEODDSAPI
# ============================================================

@st.cache_data(ttl=900, show_spinner=False)
def buscar_odds_theoddsapi(api_key, sport_key, regions="eu,us", markets="h2h"):
    if not api_key or not sport_key:
        return [], ""
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {
        "apiKey": api_key,
        "regions": regions,
        "markets": markets,
        "oddsFormat": "decimal",
        "dateFormat": "iso",
    }
    try:
        r = requests.get(url, params=params, timeout=18)
        r.raise_for_status()
        return r.json(), ""
    except requests.RequestException as e:
        return [], f"Erro TheOddsAPI ({sport_key}): {e}"


def odds_para_probabilidades(odd_event):
    # Usa primeira bookmaker com h2h disponível.
    for book in odd_event.get("bookmakers", []) or []:
        for market in book.get("markets", []) or []:
            if market.get("key") == "h2h":
                outcomes = market.get("outcomes", []) or []
                probs = {}
                for o in outcomes:
                    price = o.get("price")
                    name = o.get("name")
                    if price and price > 1:
                        probs[name] = 1 / float(price)
                soma = sum(probs.values())
                if soma > 0:
                    # remove margem da casa
                    probs = {k: v / soma for k, v in probs.items()}
                    return probs, book.get("title", "")
    return {}, ""


def encontrar_odds_jogo(jogo, odds_data):
    casa, fora = jogo["casa"], jogo["fora"]
    for ev in odds_data or []:
        home = ev.get("home_team", "")
        away = ev.get("away_team", "")
        if (nomes_equivalentes(casa, home) and nomes_equivalentes(fora, away)) or (
            nomes_equivalentes(casa, away) and nomes_equivalentes(fora, home)
        ):
            probs_raw, book = odds_para_probabilidades(ev)
            if not probs_raw:
                continue
            p_casa = p_fora = p_empate = None
            for name, p in probs_raw.items():
                if nomes_equivalentes(name, casa):
                    p_casa = p
                elif nomes_equivalentes(name, fora):
                    p_fora = p
                elif normalizar_nome(name) in ("draw", "empate"):
                    p_empate = p
            if p_casa is not None and p_fora is not None:
                return {
                    "p_casa": p_casa,
                    "p_empate": p_empate if p_empate is not None else 0.0,
                    "p_fora": p_fora,
                    "bookmaker": book,
                }
    return None


# ============================================================
# xG CSV OPCIONAL
# ============================================================

def carregar_xg_csv(uploaded_file):
    if uploaded_file is None:
        return {}
    try:
        df = pd.read_csv(uploaded_file)
    except Exception:
        return {}

    cols = {c.lower().strip(): c for c in df.columns}
    team_col = cols.get("time") or cols.get("team") or cols.get("squad")
    xg_col = cols.get("xg")
    xga_col = cols.get("xga") or cols.get("xg against") or cols.get("xg_contra")
    if not team_col or not xg_col or not xga_col:
        return {}

    out = {}
    for _, row in df.iterrows():
        team = normalizar_nome(row.get(team_col))
        try:
            out[team] = {"xg": float(row.get(xg_col)), "xga": float(row.get(xga_col))}
        except Exception:
            continue
    return out


# ============================================================
# MODELO BASE
# ============================================================

def novo_stats():
    return {
        "jogos": 0,
        "gf": 0.0,
        "ga": 0.0,
        "home_jogos": 0,
        "home_gf": 0.0,
        "home_ga": 0.0,
        "away_jogos": 0,
        "away_gf": 0.0,
        "away_ga": 0.0,
        "pontos_recent": [],
        "gols_recent": [],
        "peso_total": 0.0,
        "home_peso": 0.0,
        "away_peso": 0.0,
    }


def peso_recencia(data_jogo, ref_date, meia_vida=45):
    if not data_jogo:
        return 1.0
    dias = max(0, (ref_date.date() - data_jogo.date()).days)
    return 0.5 ** (dias / meia_vida)


def construir_contexto(jogos_encerrados, ref_dt=None):
    ref_dt = ref_dt or agora_br()
    jogos = [j for j in jogos_encerrados if j.get("completed") and j.get("placar_casa") is not None and j.get("data")]
    jogos = sorted(jogos, key=lambda x: x.get("data") or agora_br())

    ratings, stats = {}, {}
    total_home_gols = total_away_gols = total_peso = empates = 0.0

    for j in jogos:
        casa, fora = j["casa"], j["fora"]
        gc, gf = int(j["placar_casa"]), int(j["placar_fora"])
        w = peso_recencia(j.get("data"), ref_dt)

        ratings.setdefault(casa, forca_inicial(casa))
        ratings.setdefault(fora, forca_inicial(fora))
        stats.setdefault(casa, novo_stats())
        stats.setdefault(fora, novo_stats())

        rc, rf = ratings[casa], ratings[fora]
        exp_casa = 1 / (1 + 10 ** ((rf - (rc + 58)) / 400))

        if gc > gf:
            real_casa, pontos_casa, pontos_fora = 1.0, 3, 0
        elif gc == gf:
            real_casa, pontos_casa, pontos_fora = 0.5, 1, 1
            empates += w
        else:
            real_casa, pontos_casa, pontos_fora = 0.0, 0, 3

        margem = abs(gc - gf)
        k = (18 + min(16, margem * 5)) * (0.65 + 0.35 * w)
        delta = k * (real_casa - exp_casa)
        ratings[casa] = rc + delta
        ratings[fora] = rf - delta

        sc, sf = stats[casa], stats[fora]
        sc["jogos"] += 1; sc["gf"] += gc * w; sc["ga"] += gf * w
        sc["home_jogos"] += 1; sc["home_gf"] += gc * w; sc["home_ga"] += gf * w
        sc["peso_total"] += w; sc["home_peso"] += w
        sc["pontos_recent"].append(pontos_casa); sc["gols_recent"].append(gc)

        sf["jogos"] += 1; sf["gf"] += gf * w; sf["ga"] += gc * w
        sf["away_jogos"] += 1; sf["away_gf"] += gf * w; sf["away_ga"] += gc * w
        sf["peso_total"] += w; sf["away_peso"] += w
        sf["pontos_recent"].append(pontos_fora); sf["gols_recent"].append(gf)

        total_home_gols += gc * w
        total_away_gols += gf * w
        total_peso += w

    liga_home = total_home_gols / total_peso if total_peso else 1.35
    liga_away = total_away_gols / total_peso if total_peso else 1.05
    taxa_empate = empates / total_peso if total_peso else 0.27

    return {
        "ratings": ratings,
        "stats": stats,
        "jogos": len(jogos),
        "peso_jogos": total_peso,
        "liga_home": clamp(liga_home, 0.85, 2.25),
        "liga_away": clamp(liga_away, 0.60, 1.85),
        "taxa_empate": clamp(taxa_empate, 0.18, 0.34),
        "ref_dt": ref_dt,
    }


def media_suave(valor, peso, media_liga, peso_liga=6.5):
    return (valor + media_liga * peso_liga) / max(0.1, peso + peso_liga)


def regularizar_probs(p_casa, p_empate, p_fora, intensidade=0.08):
    # Puxa levemente para distribuição neutra, evitando overconfidence.
    p_casa = p_casa * (1 - intensidade) + (1 / 3) * intensidade
    p_empate = p_empate * (1 - intensidade) + (1 / 3) * intensidade
    p_fora = p_fora * (1 - intensidade) + (1 / 3) * intensidade
    s = p_casa + p_empate + p_fora
    return p_casa / s, p_empate / s, p_fora / s


def ajustar_empate(p_casa, p_empate, p_fora, taxa_empate_liga, diff_elo, classico=False):
    proximidade = max(0, 1 - abs(diff_elo) / 260)
    alvo_empate = clamp(taxa_empate_liga + 0.055 * proximidade + (0.035 if classico else 0), 0.18, 0.39)
    mistura = 0.24 if classico else 0.20
    novo_empate = p_empate * (1 - mistura) + alvo_empate * mistura
    restante_antigo = max(1e-9, p_casa + p_fora)
    restante_novo = 1 - novo_empate
    return p_casa / restante_antigo * restante_novo, novo_empate, p_fora / restante_antigo * restante_novo


def matriz_poisson_normalizada(lam_casa, lam_fora, max_gols=MAX_GOLS):
    matriz = []
    total = 0.0
    for i in range(max_gols + 1):
        for k in range(max_gols + 1):
            p = poisson(i, lam_casa) * poisson(k, lam_fora)
            matriz.append((p, i, k))
            total += p
    if total <= 0:
        return []
    return [(p / total, i, k) for p, i, k in matriz]


def calcular_mercados(lam_casa, lam_fora):
    p_casa = p_empate = p_fora = 0.0
    over15 = over25 = btts = under35 = 0.0
    placares = []
    for p, i, k in matriz_poisson_normalizada(lam_casa, lam_fora):
        placares.append((p, i, k))
        if i > k:
            p_casa += p
        elif i == k:
            p_empate += p
        else:
            p_fora += p
        if i + k >= 2:
            over15 += p
        if i + k >= 3:
            over25 += p
        if i + k <= 3:
            under35 += p
        if i > 0 and k > 0:
            btts += p
    return p_casa, p_empate, p_fora, over15, over25, under35, btts, sorted(placares, reverse=True)[:5]


def aplicar_xg(casa, fora, gols_casa, gols_fora, xg_data, liga_home, liga_away):
    nc, nf = normalizar_nome(casa), normalizar_nome(fora)
    xc, xf = xg_data.get(nc), xg_data.get(nf)
    if not xc or not xf:
        return gols_casa, gols_fora, False

    # Mistura conservadora para evitar que um CSV ruim domine o modelo.
    xg_casa = liga_home * (xc["xg"] / max(0.1, liga_home)) * (xf["xga"] / max(0.1, liga_home))
    xg_fora = liga_away * (xf["xg"] / max(0.1, liga_away)) * (xc["xga"] / max(0.1, liga_away))
    gols_casa = 0.72 * gols_casa + 0.28 * clamp(xg_casa, 0.25, 3.60)
    gols_fora = 0.72 * gols_fora + 0.28 * clamp(xg_fora, 0.20, 3.25)
    return gols_casa, gols_fora, True


def aplicar_desfalques(gols_time, gols_rival, impacto_time, impacto_rival):
    # impacto positivo fortalece, negativo enfraquece. Valor recomendado: -0.15 a +0.10.
    gols_time *= (1 + impacto_time)
    gols_rival *= (1 - min(0.18, impacto_time * 0.35)) if impacto_time > 0 else (1 + abs(impacto_time) * 0.20)
    gols_rival *= (1 + impacto_rival)
    gols_time *= (1 - min(0.18, impacto_rival * 0.35)) if impacto_rival > 0 else (1 + abs(impacto_rival) * 0.20)
    return clamp(gols_time, 0.25, 4.0), clamp(gols_rival, 0.20, 4.0)


def combinar_com_odds(p_casa, p_empate, p_fora, odds_info, peso=0.28):
    if not odds_info:
        return p_casa, p_empate, p_fora, False
    oc, oe, of = odds_info["p_casa"], odds_info.get("p_empate", 0.0), odds_info["p_fora"]
    # Se mercado não tem empate, usa só leve ajuste casa/fora.
    if oe <= 0.01:
        total_cf = max(1e-9, oc + of)
        oc, of = oc / total_cf, of / total_cf
        restante = p_casa + p_fora
        p_casa = (1 - peso) * p_casa + peso * oc * restante
        p_fora = (1 - peso) * p_fora + peso * of * restante
    else:
        p_casa = (1 - peso) * p_casa + peso * oc
        p_empate = (1 - peso) * p_empate + peso * oe
        p_fora = (1 - peso) * p_fora + peso * of
    s = p_casa + p_empate + p_fora
    return p_casa / s, p_empate / s, p_fora / s, True


def classificar_confianca(p_top, p_segundo, qualidade, riscos):
    margem = p_top - p_segundo
    risco_pesado = any(r in riscos for r in ["Clássico", "Baixa amostra", "Odds contra o modelo", "Desfalque relevante"])
    if not risco_pesado and qualidade >= 0.70 and p_top >= 0.61 and margem >= 0.14:
        return "Alta", "good", 82
    if qualidade >= 0.50 and p_top >= 0.54 and margem >= 0.075:
        return "Média", "medium", 65
    return "Baixa", "low", 42


def prever(casa, fora, contexto, odds_info=None, xg_data=None, impacto_casa=0.0, impacto_fora=0.0, usar_odds=True):
    xg_data = xg_data or {}
    ratings = contexto.get("ratings", {})
    stats = contexto.get("stats", {})
    jogos_modelo = contexto.get("jogos", 0)

    casa = nome_limpo(casa)
    fora = nome_limpo(fora)
    classico = eh_classico(casa, fora)

    elo_casa = ratings.get(casa, forca_inicial(casa))
    elo_fora = ratings.get(fora, forca_inicial(fora))
    liga_home = contexto.get("liga_home", 1.35)
    liga_away = contexto.get("liga_away", 1.05)

    sc = stats.get(casa, novo_stats())
    sf = stats.get(fora, novo_stats())

    home_gf = media_suave(sc["home_gf"], sc["home_peso"], liga_home)
    home_ga = media_suave(sc["home_ga"], sc["home_peso"], liga_away)
    away_gf = media_suave(sf["away_gf"], sf["away_peso"], liga_away)
    away_ga = media_suave(sf["away_ga"], sf["away_peso"], liga_home)

    atk_casa = home_gf / liga_home
    def_fora = away_ga / liga_home
    atk_fora = away_gf / liga_away
    def_casa = home_ga / liga_away

    diff_elo = (elo_casa + 58) - elo_fora
    fator_casa = clamp(1 + diff_elo / 980, 0.72, 1.35)
    fator_fora = clamp(1 - diff_elo / 1030, 0.72, 1.35)

    forma_casa = sum(sc["pontos_recent"][-5:]) / max(1, len(sc["pontos_recent"][-5:])) if sc["pontos_recent"] else 1.35
    forma_fora = sum(sf["pontos_recent"][-5:]) / max(1, len(sf["pontos_recent"][-5:])) if sf["pontos_recent"] else 1.20

    fator_forma_casa = clamp(1 + (forma_casa - 1.35) * 0.050, 0.90, 1.12)
    fator_forma_fora = clamp(1 + (forma_fora - 1.20) * 0.050, 0.90, 1.12)

    gols_casa = liga_home * atk_casa * def_fora * fator_casa * fator_forma_casa
    gols_fora = liga_away * atk_fora * def_casa * fator_fora * fator_forma_fora

    if jogos_modelo < 12:
        diff_base = forca_inicial(casa) - forca_inicial(fora)
        fallback_casa = 1.35 + (diff_base / 400) * 0.33
        fallback_fora = 1.05 - (diff_base / 400) * 0.26
        peso = jogos_modelo / 12
        gols_casa = gols_casa * peso + fallback_casa * (1 - peso)
        gols_fora = gols_fora * peso + fallback_fora * (1 - peso)

    # Clássicos: menos previsibilidade, empate maior, favoritismo menor.
    if classico:
        media = (gols_casa + gols_fora) / 2
        gols_casa = 0.88 * gols_casa + 0.12 * media
        gols_fora = 0.88 * gols_fora + 0.12 * media
        gols_casa *= 0.96
        gols_fora *= 0.96

    gols_casa, gols_fora, usou_xg = aplicar_xg(casa, fora, gols_casa, gols_fora, xg_data, liga_home, liga_away)
    gols_casa, gols_fora = aplicar_desfalques(gols_casa, gols_fora, impacto_casa, impacto_fora)

    gols_casa = clamp(gols_casa, 0.35, 3.60)
    gols_fora = clamp(gols_fora, 0.25, 3.25)

    p_casa, p_empate, p_fora, over15, over25, under35, btts, placares_top = calcular_mercados(gols_casa, gols_fora)
    p_casa, p_empate, p_fora = ajustar_empate(p_casa, p_empate, p_fora, contexto.get("taxa_empate", 0.27), diff_elo, classico)
    p_casa, p_empate, p_fora = regularizar_probs(p_casa, p_empate, p_fora, intensidade=0.10 if classico else 0.075)

    odds_aplicada = False
    if usar_odds and odds_info:
        p_casa, p_empate, p_fora, odds_aplicada = combinar_com_odds(p_casa, p_empate, p_fora, odds_info, peso=0.26)

    probs = {"Casa": p_casa, "Empate": p_empate, "Fora": p_fora}
    ordenadas = sorted(probs.items(), key=lambda x: x[1], reverse=True)
    palpite, p_top = ordenadas[0]
    p_segundo = ordenadas[1][1]

    jogos_times = sc["jogos"] + sf["jogos"]
    qualidade = clamp((jogos_modelo / 48) * 0.50 + (jogos_times / 18) * 0.40 + (0.10 if odds_aplicada else 0) + (0.08 if usou_xg else 0), 0, 1)

    riscos = []
    if classico:
        riscos.append("Clássico")
    if jogos_modelo < 20 or jogos_times < 8:
        riscos.append("Baixa amostra")
    if abs(impacto_casa) >= 0.12 or abs(impacto_fora) >= 0.12:
        riscos.append("Desfalque relevante")
    if odds_info:
        odds_top = max({"Casa": odds_info["p_casa"], "Empate": odds_info.get("p_empate", 0), "Fora": odds_info["p_fora"]}.items(), key=lambda x: x[1])[0]
        if odds_top != palpite:
            riscos.append("Odds contra o modelo")

    confianca, conf_class, score_base = classificar_confianca(p_top, p_segundo, qualidade, riscos)
    score_conf = int(clamp(score_base + (qualidade * 16) + ((p_top - p_segundo) * 45) - len(riscos) * 7, 15, 96))

    mercados = [
        ("+1.5 gols", over15),
        ("Under 3.5 gols", under35),
        ("Ambas marcam", btts),
        ("+2.5 gols", over25),
        ("1X2", p_top),
    ]
    mercados = sorted(mercados, key=lambda x: x[1], reverse=True)
    melhor_mercado, melhor_mercado_prob = mercados[0]

    # Evita indicar 1X2 em clássico/risco se um mercado de gols estiver próximo.
    if riscos and melhor_mercado == "1X2":
        alternativos = [m for m in mercados if m[0] != "1X2" and m[1] >= 0.57]
        if alternativos:
            melhor_mercado, melhor_mercado_prob = alternativos[0]

    return {
        "casa": casa, "fora": fora,
        "gols_casa": gols_casa, "gols_fora": gols_fora,
        "p_casa": p_casa, "p_empate": p_empate, "p_fora": p_fora,
        "over15": over15, "over25": over25, "under35": under35, "btts": btts,
        "elo_casa": elo_casa, "elo_fora": elo_fora, "diff_elo": diff_elo,
        "palpite": palpite, "prob_palpite": p_top,
        "confianca": confianca, "conf_class": conf_class, "score_conf": score_conf,
        "qualidade": qualidade, "placares_top": placares_top,
        "jogos_modelo": jogos_modelo, "amostra_times": jogos_times,
        "melhor_mercado": melhor_mercado, "melhor_mercado_prob": melhor_mercado_prob,
        "riscos": riscos, "classico": classico, "odds_aplicada": odds_aplicada, "usou_xg": usou_xg,
    }


# ============================================================
# LIVE
# ============================================================

def aplicar_vermelhos_live(lam_casa, lam_fora, vermelho_casa=0, vermelho_fora=0, minuto=0):
    # Quanto mais cedo o vermelho, maior o impacto.
    fator_tempo = clamp((95 - minuto) / 90, 0.15, 1.05)
    if vermelho_casa:
        lam_casa *= (1 - 0.30 * fator_tempo) ** vermelho_casa
        lam_fora *= (1 + 0.24 * fator_tempo) ** vermelho_casa
    if vermelho_fora:
        lam_fora *= (1 - 0.30 * fator_tempo) ** vermelho_fora
        lam_casa *= (1 + 0.24 * fator_tempo) ** vermelho_fora
    return clamp(lam_casa, 0.02, 3.2), clamp(lam_fora, 0.02, 3.2)


def ajustar_pressao_live(lam_casa, lam_fora, pressao_casa, pressao_fora):
    # pressão -5 a +5; valores positivos aumentam xG restante.
    lam_casa *= 1 + clamp(pressao_casa, -5, 5) * 0.035
    lam_fora *= 1 + clamp(pressao_fora, -5, 5) * 0.035
    return clamp(lam_casa, 0.02, 3.2), clamp(lam_fora, 0.02, 3.2)


def recalcular_live(gc_atual, gf_atual, lam_casa_restante, lam_fora_restante):
    p_casa = p_empate = p_fora = 0.0
    over15 = over25 = btts = under35 = 0.0
    placares = []

    for p, add_casa, add_fora in matriz_poisson_normalizada(lam_casa_restante, lam_fora_restante, max_gols=8):
        final_casa = gc_atual + add_casa
        final_fora = gf_atual + add_fora
        placares.append((p, final_casa, final_fora))
        if final_casa > final_fora:
            p_casa += p
        elif final_casa == final_fora:
            p_empate += p
        else:
            p_fora += p
        if final_casa + final_fora >= 2:
            over15 += p
        if final_casa + final_fora >= 3:
            over25 += p
        if final_casa + final_fora <= 3:
            under35 += p
        if final_casa > 0 and final_fora > 0:
            btts += p

    probs = {"Casa": p_casa, "Empate": p_empate, "Fora": p_fora}
    ordenadas = sorted(probs.items(), key=lambda x: x[1], reverse=True)
    return {
        "p_casa": p_casa, "p_empate": p_empate, "p_fora": p_fora,
        "palpite": ordenadas[0][0], "prob_palpite": ordenadas[0][1],
        "over15": over15, "over25": over25, "under35": under35, "btts": btts,
        "placares_top": sorted(placares, reverse=True)[:5],
    }


def ajustar_ao_vivo(jogo, r_pre, vermelho_casa=0, vermelho_fora=0, pressao_casa=0, pressao_fora=0):
    if jogo.get("state") != "in":
        return r_pre

    minuto = extrair_minuto(jogo.get("status", ""))
    gc = int(jogo.get("placar_casa") or 0)
    gf = int(jogo.get("placar_fora") or 0)

    # Tempo restante com acréscimos leves.
    duracao = 96 if minuto <= 90 else 120
    restante = clamp((duracao - minuto) / 90, 0.01, 1.0)

    lam_casa = r_pre["gols_casa"] * restante
    lam_fora = r_pre["gols_fora"] * restante

    lam_casa, lam_fora = aplicar_vermelhos_live(lam_casa, lam_fora, vermelho_casa, vermelho_fora, minuto)
    lam_casa, lam_fora = ajustar_pressao_live(lam_casa, lam_fora, pressao_casa, pressao_fora)

    live = recalcular_live(gc, gf, lam_casa, lam_fora)

    riscos = list(r_pre.get("riscos", []))
    if vermelho_casa or vermelho_fora:
        riscos.append("Cartão vermelho")
    if minuto >= 65 and r_pre["palpite"] == "Casa" and gc < gf:
        riscos.append("Favorito perdendo")
    if minuto >= 65 and r_pre["palpite"] == "Fora" and gf < gc:
        riscos.append("Favorito perdendo")

    probs = {"Casa": live["p_casa"], "Empate": live["p_empate"], "Fora": live["p_fora"]}
    ordenadas = sorted(probs.items(), key=lambda x: x[1], reverse=True)
    margem = ordenadas[0][1] - ordenadas[1][1]
    score_live = int(clamp(35 + ordenadas[0][1] * 50 + margem * 40 - len(riscos) * 5, 10, 96))

    return {
        **r_pre,
        **live,
        "gols_casa": lam_casa,
        "gols_fora": lam_fora,
        "confianca": "Ao vivo",
        "conf_class": "medium" if score_live < 78 else "good",
        "score_conf": score_live,
        "riscos": riscos,
        "minuto_live": minuto,
    }


# ============================================================
# DIAGNÓSTICO / BACKTEST
# ============================================================

def explicar_erro(jogo, r, real, acertou):
    if acertou:
        if r["confianca"] == "Alta":
            return "Acerto forte: havia margem, probabilidade e amostra suficientes."
        return "Acerto com cautela: havia vantagem, mas com risco estatístico."
    if r["confianca"] == "Baixa":
        return "Erro aceitável: o próprio modelo marcava baixa confiança."
    if real == "Empate":
        return "Erro por empate: 1X2 sofre muito quando forças são próximas."
    if r.get("classico"):
        return "Erro em clássico: esse tipo de jogo reduz o peso do favoritismo."
    return "Erro normal; revisar amostra, contexto, odds e desfalques."


def avaliar_jogo_com_contexto_anterior(jogo, historico_antes):
    real = resultado_real(jogo)
    if not real or not jogo.get("data"):
        return None
    contexto_pre = construir_contexto(historico_antes, ref_dt=jogo["data"] - timedelta(minutes=1))
    r = prever(jogo["casa"], jogo["fora"], contexto_pre, usar_odds=False)
    probs = {"Casa": r["p_casa"], "Empate": r["p_empate"], "Fora": r["p_fora"]}
    brier = sum((probs[k] - (1 if k == real else 0)) ** 2 for k in probs) / 3
    total_gols = jogo["placar_casa"] + jogo["placar_fora"]
    return {
        "jogo": jogo, "prev": r, "real": real, "acertou": r["palpite"] == real, "brier": brier,
        "over15_ok": (r["over15"] >= 0.56) == (total_gols >= 2),
        "over25_ok": (r["over25"] >= 0.54) == (total_gols >= 3),
        "under35_ok": (r["under35"] >= 0.58) == (total_gols <= 3),
        "btts_ok": (r["btts"] >= 0.54) == (jogo["placar_casa"] > 0 and jogo["placar_fora"] > 0),
        "explicacao": explicar_erro(jogo, r, real, r["palpite"] == real),
    }


def backtest_temporal(jogos_hist, limite=70, janela_treino=120):
    encerrados = [j for j in jogos_hist if j.get("completed") and j.get("placar_casa") is not None and j.get("data")]
    encerrados = sorted(encerrados, key=lambda x: x["data"])
    candidatos = encerrados[-limite:]
    avaliacoes = []
    for j in candidatos:
        inicio = j["data"] - timedelta(days=janela_treino)
        antes = [x for x in encerrados if inicio <= x["data"] < j["data"]]
        if len(antes) < 8:
            continue
        a = avaliar_jogo_com_contexto_anterior(j, antes)
        if a:
            avaliacoes.append(a)
    return avaliacoes


# ============================================================
# UI FUNCTIONS
# ============================================================

def riscos_html(riscos):
    if not riscos:
        return '<span class="ok">Baixo risco contextual</span>'
    return " • ".join([f'<span class="risk">{esc(r)}</span>' for r in riscos])


def palpite_nome(jogo, r):
    return {"Casa": jogo["casa"], "Fora": jogo["fora"], "Empate": "Empate"}[r["palpite"]]


def obter_previsao_jogo(jogo, contexto, odds_data, xg_data, usar_odds, impactos):
    odds_info = encontrar_odds_jogo(jogo, odds_data) if odds_data else None
    key_c = normalizar_nome(jogo["casa"])
    key_f = normalizar_nome(jogo["fora"])
    impacto_casa = impactos.get(key_c, 0.0)
    impacto_fora = impactos.get(key_f, 0.0)
    return prever(jogo["casa"], jogo["fora"], contexto, odds_info, xg_data, impacto_casa, impacto_fora, usar_odds=usar_odds)


def card_jogo(jogo, contexto, odds_data=None, xg_data=None, usar_odds=True, impactos=None):
    impactos = impactos or {}
    r_pre = obter_previsao_jogo(jogo, contexto, odds_data, xg_data, usar_odds, impactos)
    r = r_pre

    if jogo.get("state") == "in":
        with st.expander(f"🔴 Ajustes ao vivo: {jogo['casa']} x {jogo['fora']}", expanded=False):
            c1, c2, c3, c4 = st.columns(4)
            vc = c1.number_input("Vermelhos casa", 0, 3, 0, key=f"vc_{jogo['id']}")
            vf = c2.number_input("Vermelhos fora", 0, 3, 0, key=f"vf_{jogo['id']}")
            pc = c3.slider("Pressão casa", -5, 5, 0, key=f"pc_{jogo['id']}")
            pf = c4.slider("Pressão fora", -5, 5, 0, key=f"pf_{jogo['id']}")
            st.caption("Pressão é manual: use + se o time estiver dominando finalizações/ataques perigosos nos últimos minutos.")
        r = ajustar_ao_vivo(jogo, r_pre, vc, vf, pc, pf)

    nome = palpite_nome(jogo, r)
    placar = ""
    if jogo.get("placar_casa") is not None:
        placar = f" — {jogo['placar_casa']} x {jogo['placar_fora']}"

    css_extra = "live-box" if jogo.get("state") == "in" else f"game-card {r['conf_class']}"
    if r["score_conf"] >= 78 and not r.get("riscos"):
        css_extra += " safe-box"

    st.markdown(
        f"""
        <div class="{css_extra}">
            <div class="game-title">⚽ {esc(jogo['casa'])} x {esc(jogo['fora'])}{esc(placar)}</div>
            <div class="muted">{esc(jogo['data_txt'])} • {esc(status_legivel(jogo))}</div>
            <span class="pill">Palpite 1X2: <b>{esc(nome)}</b></span>
            <span class="pill">Prob.: <b>{esc(pct(r['prob_palpite']))}</b></span>
            <span class="pill">Confiança: <b>{esc(r['confianca'])} · {r['score_conf']}/100</b></span>
            <span class="pill">Melhor mercado: <b>{esc(r['melhor_mercado'])} {esc(pct(r['melhor_mercado_prob']))}</b></span>
            <span class="pill">Placar provável: <b>{esc(f"{r['placares_top'][0][1]}x{r['placares_top'][0][2]}")}</b></span>
            <span class="pill">Gols esp.: <b>{r['gols_casa']:.2f} x {r['gols_fora']:.2f}</b></span>
            <br><span class="muted">Alertas: {riscos_html(r.get('riscos', []))}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Ver análise detalhada"):
        c1, c2, c3 = st.columns(3)
        c1.metric(f"Vitória {jogo['casa']}", pct(r["p_casa"]))
        c2.metric("Empate", pct(r["p_empate"]))
        c3.metric(f"Vitória {jogo['fora']}", pct(r["p_fora"]))

        g1, g2, g3, g4 = st.columns(4)
        g1.metric("+1.5 gols", pct(r["over15"]))
        g2.metric("+2.5 gols", pct(r["over25"]))
        g3.metric("Under 3.5", pct(r["under35"]))
        g4.metric("Ambas marcam", pct(r["btts"]))

        ptxt = ", ".join([f"{i}x{k} ({pct(p)})" for p, i, k in r["placares_top"]])
        st.caption(f"Placares mais prováveis: {ptxt}")
        st.caption(
            f"Base: {r['jogos_modelo']} jogos. Amostra dos times: {r['amostra_times']} jogos. "
            f"Qualidade: {pct(r['qualidade'])}. Elo ajustado: {r['elo_casa']:.0f} x {r['elo_fora']:.0f}. "
            f"xG: {'sim' if r['usou_xg'] else 'não'} · Odds: {'sim' if r['odds_aplicada'] else 'não'}."
        )
    return r


def tabela_resumo(jogos, contexto, odds_data, xg_data, usar_odds, impactos):
    linhas = []
    for j in jogos:
        r = obter_previsao_jogo(j, contexto, odds_data, xg_data, usar_odds, impactos)
        linhas.append({
            "Data": j["data_txt"],
            "Jogo": f"{j['casa']} x {j['fora']}",
            "Status": status_legivel(j),
            "Palpite": {"Casa": j["casa"], "Fora": j["fora"], "Empate": "Empate"}[r["palpite"]],
            "Prob.": pct(r["prob_palpite"]),
            "Conf.": f"{r['confianca']} ({r['score_conf']}/100)",
            "Melhor mercado": r["melhor_mercado"],
            "Prob. mercado": pct(r["melhor_mercado_prob"]),
            "Placar provável": f"{r['placares_top'][0][1]}x{r['placares_top'][0][2]}",
            "Alertas": ", ".join(r["riscos"]) if r["riscos"] else "Baixo risco",
            "+1.5": pct(r["over15"]), "+2.5": pct(r["over25"]),
            "U3.5": pct(r["under35"]), "Ambas": pct(r["btts"]),
        })
    return pd.DataFrame(linhas)


def ranking_previsoes(jogos, contexto, odds_data, xg_data, usar_odds, impactos):
    items = []
    for j in jogos:
        r = obter_previsao_jogo(j, contexto, odds_data, xg_data, usar_odds, impactos)
        items.append((j, r))
    return sorted(items, key=lambda x: (x[1]["score_conf"], x[1]["melhor_mercado_prob"], -len(x[1]["riscos"])), reverse=True)


def render_cards_lista(items, contexto, odds_data, xg_data, usar_odds, impactos, limite=None):
    count = 0
    for jogo, _ in items:
        if limite and count >= limite:
            break
        card_jogo(jogo, contexto, odds_data, xg_data, usar_odds, impactos)
        count += 1


def render_ao_vivo(liga, contexto, busca, somente_confianca, odds_data, xg_data, usar_odds, impactos):
    jogos_live, logs = buscar_ao_vivo_rapido(liga)

    if busca.strip():
        b = normalizar_nome(busca)
        jogos_live = [j for j in jogos_live if b in normalizar_nome(j["casa"]) or b in normalizar_nome(j["fora"])]

    if somente_confianca:
        jogos_live = [j for j in jogos_live if obter_previsao_jogo(j, contexto, odds_data, xg_data, usar_odds, impactos)["score_conf"] >= 62]

    ao_vivo = [j for j in jogos_live if j.get("state") == "in"]
    futuros = [j for j in jogos_live if j.get("state") == "pre"]
    encerrados = [j for j in jogos_live if j.get("state") == "post"]

    st.caption(f"Última checagem ao vivo: {agora_br().strftime('%H:%M:%S')}")
    if logs:
        with st.expander("Avisos da API ao vivo"):
            for log in logs[:8]:
                st.write(log)

    st.subheader("🔴 Jogos ao vivo")
    if not ao_vivo:
        st.info("Nenhum jogo ao vivo encontrado agora.")
    else:
        for jogo in ao_vivo:
            card_jogo(jogo, contexto, odds_data, xg_data, usar_odds, impactos)

    st.subheader("🕒 Próximos jogos")
    if not futuros:
        st.caption("Nenhum próximo jogo encontrado na janela rápida.")
    else:
        items = ranking_previsoes(futuros, contexto, odds_data, xg_data, usar_odds, impactos)
        render_cards_lista(items[:14], contexto, odds_data, xg_data, usar_odds, impactos)

    with st.expander("✅ Encerrados recentes"):
        if not encerrados:
            st.caption("Nenhum encerrado recente.")
        else:
            for jogo in encerrados[:12]:
                card_jogo(jogo, contexto, odds_data, xg_data, usar_odds, impactos)


# ============================================================
# APP
# ============================================================

st.markdown(
    """
    <div class="hero">
        <h1>⚽ Analisador Futebol Pro 6.0</h1>
        <div class="sub">Elo + Poisson normalizado + odds por liga + xG + clássicos + desfalques + live inteligente.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("⚙️ Configurações")

    liga_nome = st.selectbox("Competição", list(COMPETICOES.keys()))
    liga = COMPETICOES[liga_nome]["espn"]
    sport_key = COMPETICOES[liga_nome]["odds"]

    modo = st.radio(
        "Jogos",
        ["Hoje e próximos", "Ao vivo + 48h", "Últimos resultados", "Período personalizado"],
        index=0,
    )

    dias_historico = st.slider("Histórico usado pelo modelo", 30, 240, 120, step=15)
    limite_backtest = st.slider("Jogos no diagnóstico temporal", 20, 120, 70, step=10)
    somente_confianca = st.checkbox("Mostrar só confiança média/alta", value=False)
    busca = st.text_input("Filtrar time", placeholder="Ex.: Flamengo")

    st.divider()
    st.subheader("📈 Odds")
    usar_odds = st.checkbox("Usar odds TheOddsAPI", value=False)
    odds_api_key = st.text_input("TheOddsAPI key", type="password", placeholder="opcional")
    st.caption(f"sport_key desta liga: `{sport_key}`")

    st.divider()
    st.subheader("🧪 xG opcional")
    xg_file = st.file_uploader("CSV com colunas: team/time, xg, xga", type=["csv"])

    st.divider()
    st.subheader("🚑 Contexto manual")
    st.caption("Impacto por time: negativo = desfalque/queda; positivo = reforço/momento. Ex.: Flamengo:-0.18")
    impactos_txt = st.text_area("Impactos", height=80, placeholder="Flamengo:-0.18\nPalmeiras:0.05")

    st.divider()
    if st.button("🔄 Atualizar dados"):
        st.cache_data.clear()
        st.rerun()

impactos = {}
for linha in impactos_txt.splitlines():
    if ":" in linha:
        nome, valor = linha.split(":", 1)
        try:
            impactos[normalizar_nome(nome)] = clamp(float(valor.replace(",", ".")), -0.40, 0.25)
        except Exception:
            pass

xg_data = carregar_xg_csv(xg_file)

hoje = hoje_br()
if modo == "Hoje e próximos":
    inicio, fim = hoje - timedelta(days=1), hoje + timedelta(days=7)
elif modo == "Ao vivo + 48h":
    inicio, fim = hoje - timedelta(days=1), hoje + timedelta(days=1)
elif modo == "Últimos resultados":
    inicio, fim = hoje - timedelta(days=7), hoje
else:
    c1, c2 = st.sidebar.columns(2)
    inicio = c1.date_input("Início", hoje - timedelta(days=3))
    fim = c2.date_input("Fim", hoje + timedelta(days=3))

hist_inicio = hoje - timedelta(days=dias_historico)
hist_fim = hoje - timedelta(days=1)

with st.spinner("Carregando dados, calibrando modelo e montando análise..."):
    jogos_hist, logs_hist = buscar_periodo(liga, hist_inicio.isoformat(), hist_fim.isoformat())
    contexto = construir_contexto(jogos_hist)
    jogos, logs_jogos = buscar_periodo(liga, inicio.isoformat(), fim.isoformat())
    odds_data, odds_log = buscar_odds_theoddsapi(odds_api_key, sport_key) if usar_odds and odds_api_key else ([], "")

if busca.strip():
    b = normalizar_nome(busca)
    jogos = [j for j in jogos if b in normalizar_nome(j["casa"]) or b in normalizar_nome(j["fora"])]

if somente_confianca:
    jogos = [j for j in jogos if obter_previsao_jogo(j, contexto, odds_data, xg_data, usar_odds, impactos)["score_conf"] >= 62]

aba_jogos, aba_melhores, aba_seguros, aba_diagnostico, aba_ranking = st.tabs([
    "📋 Jogos e previsões", "🔥 Melhores palpites", "🛡️ Só jogos seguros", "🧪 Diagnóstico real", "🏆 Ranking de mercados"
])

with aba_jogos:
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Jogos encontrados", len(jogos))
    m2.metric("Base do modelo", contexto["jogos"])
    m3.metric("Média casa", f"{contexto['liga_home']:.2f}")
    m4.metric("Média fora", f"{contexto['liga_away']:.2f}")
    m5.metric("Empate liga", pct(contexto["taxa_empate"]))
    m6.metric("xG carregado", len(xg_data))

    if logs_jogos or logs_hist or odds_log:
        with st.expander("Avisos de API"):
            for log in (logs_jogos + logs_hist + ([odds_log] if odds_log else []))[:14]:
                st.write(log)

    st.info(
        "Versão 6.0: prefira mercados com score alto, poucos alertas e boa amostra. "
        "Em clássicos, o app reduz confiança e tende a recomendar mercados menos arriscados que 1X2."
    )

    if modo == "Ao vivo + 48h":
        @st.fragment(run_every="20s")
        def bloco_ao_vivo():
            render_ao_vivo(liga, contexto, busca, somente_confianca, odds_data, xg_data, usar_odds, impactos)
        bloco_ao_vivo()
    else:
        if not jogos:
            st.warning("Nenhum jogo encontrado para os filtros.")
        else:
            df = tabela_resumo(jogos, contexto, odds_data, xg_data, usar_odds, impactos)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.subheader("Cards para celular")
            items = ranking_previsoes(jogos, contexto, odds_data, xg_data, usar_odds, impactos)
            render_cards_lista(items, contexto, odds_data, xg_data, usar_odds, impactos)

with aba_melhores:
    st.subheader("🔥 Melhores palpites do dia")
    st.caption("Ordenado por score de confiança, probabilidade do melhor mercado e quantidade de alertas.")
    if not jogos:
        st.warning("Sem jogos no período.")
    else:
        items = ranking_previsoes([j for j in jogos if j.get("state") != "post"], contexto, odds_data, xg_data, usar_odds, impactos)
        if not items:
            st.caption("Nenhum jogo futuro/ao vivo para ranquear.")
        else:
            render_cards_lista(items[:10], contexto, odds_data, xg_data, usar_odds, impactos)

with aba_seguros:
    st.subheader("🛡️ Só jogos seguros")
    st.caption("Filtro: score ≥ 72, melhor mercado ≥ 58% e no máximo 1 alerta contextual.")
    items = ranking_previsoes([j for j in jogos if j.get("state") != "post"], contexto, odds_data, xg_data, usar_odds, impactos)
    seguros = [(j, r) for j, r in items if r["score_conf"] >= 72 and r["melhor_mercado_prob"] >= 0.58 and len(r["riscos"]) <= 1]
    if not seguros:
        st.warning("Nenhum jogo passou no filtro de segurança. Isso também é uma boa análise: melhor evitar forçar palpite.")
    else:
        render_cards_lista(seguros, contexto, odds_data, xg_data, usar_odds, impactos)

with aba_diagnostico:
    st.subheader("🧪 Diagnóstico temporal dos últimos resultados")
    st.caption("Simula cada jogo usando apenas partidas anteriores a ele. Sem vazamento de dados.")
    avaliacoes = backtest_temporal(jogos_hist, limite=limite_backtest, janela_treino=dias_historico)
    if not avaliacoes:
        st.warning("Ainda não há jogos encerrados suficientes para diagnóstico temporal confiável.")
    else:
        total = len(avaliacoes)
        acertos = sum(a["acertou"] for a in avaliacoes)
        taxa = acertos / total if total else 0
        brier_medio = sum(a["brier"] for a in avaliacoes) / total
        altas_medias = [a for a in avaliacoes if a["prev"]["score_conf"] >= 62]
        taxa_filtrada = sum(a["acertou"] for a in altas_medias) / len(altas_medias) if altas_medias else 0

        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Jogos avaliados", total)
        d2.metric("Acertos 1X2", acertos, pct(taxa))
        d3.metric("Score ≥ 62", len(altas_medias), pct(taxa_filtrada))
        d4.metric("Brier médio", f"{brier_medio:.3f}")

        filtro = st.radio("Mostrar", ["Todos", "Só acertos", "Só erros", "Score ≥ 62"], horizontal=True)
        lista = avaliacoes
        if filtro == "Só acertos":
            lista = [a for a in avaliacoes if a["acertou"]]
        elif filtro == "Só erros":
            lista = [a for a in avaliacoes if not a["acertou"]]
        elif filtro == "Score ≥ 62":
            lista = altas_medias

        for a in reversed(lista):
            j, r = a["jogo"], a["prev"]
            sinal = "✅" if a["acertou"] else "❌"
            palpite_n = {"Casa": j["casa"], "Fora": j["fora"], "Empate": "Empate"}[r["palpite"]]
            real_n = {"Casa": j["casa"], "Fora": j["fora"], "Empate": "Empate"}[a["real"]]
            st.markdown(
                f"""
                <div class="game-card {'good' if a['acertou'] else 'low'}">
                    <div class="game-title">{sinal} {esc(j['casa'])} {j['placar_casa']} x {j['placar_fora']} {esc(j['fora'])}</div>
                    <div class="muted">{esc(j['data_txt'])}</div>
                    <span class="pill">Palpite: <b>{esc(palpite_n)}</b></span>
                    <span class="pill">Real: <b>{esc(real_n)}</b></span>
                    <span class="pill">Prob.: <b>{esc(pct(r['prob_palpite']))}</b></span>
                    <span class="pill">Score: <b>{r['score_conf']}/100</b></span>
                    <span class="pill">Brier: <b>{a['brier']:.3f}</b></span>
                    <br><span class="muted">{esc(a['explicacao'])}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

with aba_ranking:
    st.subheader("🏆 Ranking dos mercados")
    st.caption("Calculado com backtest temporal. Mostra onde o modelo está performando melhor no recorte.")
    avaliacoes = backtest_temporal(jogos_hist, limite=limite_backtest, janela_treino=dias_historico)
    if not avaliacoes:
        st.warning("Sem amostra suficiente.")
    else:
        total = len(avaliacoes)
        linhas = [
            {"Mercado": "Resultado 1X2", "Acertos": sum(a["acertou"] for a in avaliacoes), "Total": total},
            {"Mercado": "+1.5 gols", "Acertos": sum(a["over15_ok"] for a in avaliacoes), "Total": total},
            {"Mercado": "+2.5 gols", "Acertos": sum(a["over25_ok"] for a in avaliacoes), "Total": total},
            {"Mercado": "Under 3.5 gols", "Acertos": sum(a["under35_ok"] for a in avaliacoes), "Total": total},
            {"Mercado": "Ambas marcam", "Acertos": sum(a["btts_ok"] for a in avaliacoes), "Total": total},
        ]
        for linha in linhas:
            linha["Taxa_num"] = linha["Acertos"] / max(1, linha["Total"])
            if linha["Taxa_num"] >= 0.68:
                linha["Leitura"] = "Forte"
            elif linha["Taxa_num"] >= 0.58:
                linha["Leitura"] = "Boa"
            elif linha["Taxa_num"] >= 0.50:
                linha["Leitura"] = "Instável"
            else:
                linha["Leitura"] = "Fraca"
        df_rank = pd.DataFrame(linhas).sort_values("Taxa_num", ascending=False)
        melhor = df_rank.iloc[0].copy()
        pior = df_rank.iloc[-1].copy()
        df_rank["Taxa"] = df_rank["Taxa_num"].map(pct)
        df_rank = df_rank.drop(columns=["Taxa_num"])
        st.dataframe(df_rank, use_container_width=True, hide_index=True)
        st.success(f"Melhor mercado no recorte: {melhor['Mercado']} ({pct(melhor['Taxa_num'])}).")
        st.warning(f"Mercado mais fraco no recorte: {pior['Mercado']} ({pct(pior['Taxa_num'])}).")

st.caption(f"Atualizado em {agora_br().strftime('%d/%m/%Y %H:%M:%S')} — horário de Brasília.")
