import math
import re
import unicodedata
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import streamlit as st


st.set_page_config(
    page_title="Analisador Esportivo Pro 10.2",
    page_icon="AE",
    layout="wide",
    initial_sidebar_state="expanded",
)


ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
HEADERS = {"User-Agent": "AnalisadorEsportivoPro/10.2"}
MAX_GOLS = 10

LIGAS = {
    "Brasileirao Serie A": "bra.1",
    "Brasileirao Serie B": "bra.2",
    "Copa do Brasil": "bra.copa_do_brasil",
    "Libertadores": "conmebol.libertadores",
    "Sul-Americana": "conmebol.sudamericana",
    "Premier League": "eng.1",
    "La Liga": "esp.1",
    "Serie A Italia": "ita.1",
    "Bundesliga": "ger.1",
    "Ligue 1": "fra.1",
    "Champions League": "uefa.champions",
    "Europa League": "uefa.europa",
}

FORCA_BASE = {
    "Flamengo": 86, "Palmeiras": 85, "Botafogo": 81, "Atletico-MG": 80,
    "Sao Paulo": 78, "Fluminense": 78, "Gremio": 77, "Internacional": 77,
    "Corinthians": 76, "Cruzeiro": 75, "Bahia": 74, "Fortaleza": 73,
    "Vasco": 72, "Santos": 72, "Ceara": 69, "Sport": 68, "Vitoria": 69,
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
    "atletico mineiro": "atletico-mg",
    "atletico mg": "atletico-mg",
    "vasco da gama": "vasco",
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


st.markdown(
    """
    <style>
    .main { background-color: #ffffff; color: #111827; }
    .block-container { padding-top: 1rem; max-width: 1450px; }
    section[data-testid="stSidebar"] { background: #f1f5f9; }
    div[data-testid="stMetric"] {
        background-color: #f8fafc;
        padding: 14px;
        border-radius: 8px;
        border: 1px solid #d7dce2;
    }
    .hero {
        border: 1px solid #d7dce2;
        background: #f8fafc;
        border-radius: 8px;
        padding: 18px 20px;
        margin-bottom: 16px;
    }
    .hero h1 { margin: 0; font-size: 2rem; letter-spacing: 0; color: #111827; }
    .hero p { margin: 6px 0 0; color: #475569; }
    .card {
        border: 1px solid #d7dce2;
        border-radius: 8px;
        padding: 14px 16px;
        margin: 10px 0;
        background: #ffffff;
    }
    .card.good { border-left: 6px solid #16a34a; }
    .card.medium { border-left: 6px solid #eab308; }
    .card.low { border-left: 6px solid #dc2626; }
    .card.live { border-left: 6px solid #2563eb; }
    .card-title { font-size: 1.08rem; font-weight: 800; margin-bottom: 6px; }
    .muted { color: #64748b; font-size: .88rem; }
    .pill {
        display: inline-block;
        padding: 5px 9px;
        margin: 5px 5px 0 0;
        border-radius: 6px;
        background: #eef2f7;
        border: 1px solid #d7dce2;
        font-size: .88rem;
    }
    .pill strong { color: #111827; }
    .decision {
        display: inline-block;
        padding: 6px 10px;
        margin: 8px 6px 0 0;
        border-radius: 6px;
        color: white;
        font-weight: 800;
    }
    .decision.green { background: #16a34a; }
    .decision.amber { background: #ca8a04; }
    .decision.red { background: #dc2626; }
    .green { color: #16883c; font-weight: 800; }
    .red { color: #c92a2a; font-weight: 800; }
    .stButton>button { background-color: #0d6efd; color: white; border-radius: 5px; }
    </style>
    """,
    unsafe_allow_html=True,
)


if "historico" not in st.session_state:
    st.session_state.historico = []


def hoje():
    return datetime.now().date()


def nome_limpo(nome):
    return " ".join(str(nome or "").strip().split())


def normalizar(nome):
    nome = nome_limpo(nome).lower()
    nome = unicodedata.normalize("NFKD", nome)
    nome = "".join(c for c in nome if not unicodedata.combining(c))
    nome = re.sub(r"\b(fc|cf|sc|afc)\b", "", nome)
    nome = re.sub(r"[^a-z0-9\s\-]", "", nome)
    nome = re.sub(r"\s+", " ", nome).strip()
    return ALIASES.get(nome, nome)


def parse_dt(valor):
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
    except ValueError:
        return None


def pct(x):
    return f"{100 * float(x):.1f}%"


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def poisson_pmf(k, media):
    media = max(0.03, float(media))
    return math.exp(-media) * (media ** k) / math.factorial(k)


def prob_over(media, linha):
    corte = int(math.floor(linha))
    return clamp(1 - sum(poisson_pmf(k, media) for k in range(corte + 1)), 0.0, 1.0)


def odd_justa(prob):
    prob = clamp(prob, 0.0001, 0.9999)
    return 1 / prob


def valor_esperado(prob, odd):
    return prob * odd - 1 if odd > 1 else 0


def kelly_stake(prob, odd, banca, fracao=0.25):
    if odd <= 1 or banca <= 0:
        return 0.0
    b = odd - 1
    q = 1 - prob
    kelly = (b * prob - q) / b
    return max(0.0, kelly * fracao * banca)


@st.cache_data(ttl=240, show_spinner=False)
def buscar_scoreboard(liga_id, data_iso=None):
    params = {"limit": 300}
    if data_iso:
        params["dates"] = data_iso.replace("-", "")
    try:
        resp = requests.get(f"{ESPN_BASE}/{liga_id}/scoreboard", params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.json(), ""
    except requests.RequestException as exc:
        return {}, f"Erro ESPN: {exc}"


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
        status_type = event.get("status", {}).get("type", {})

        def placar(c):
            try:
                return int(c.get("score", 0))
            except (TypeError, ValueError):
                return 0

        dt = parse_dt(event.get("date"))
        jogos.append({
            "id": str(event.get("id", "")),
            "liga": liga_id,
            "nome": event.get("name", ""),
            "home": nome_limpo(home.get("team", {}).get("displayName", "Casa")),
            "away": nome_limpo(away.get("team", {}).get("displayName", "Fora")),
            "placar_home": placar(home),
            "placar_away": placar(away),
            "placar": f"{placar(home)} - {placar(away)}",
            "data": dt,
            "data_txt": dt.strftime("%d/%m %H:%M") if dt else "Sem data",
            "status": status_type.get("description") or status_type.get("detail") or "Scheduled",
            "state": status_type.get("state", ""),
            "completed": bool(status_type.get("completed", False)),
            "live": status_type.get("state", "") == "in",
        })
    return jogos


@st.cache_data(ttl=900, show_spinner=False)
def buscar_periodo(liga_id, dias_passado, dias_futuro):
    jogos, logs = [], []
    inicio = hoje() - timedelta(days=dias_passado)
    fim = hoje() + timedelta(days=dias_futuro)
    dia = inicio
    while dia <= fim:
        payload, erro = buscar_scoreboard(liga_id, dia.isoformat())
        if erro:
            logs.append(erro)
        jogos.extend(extrair_jogos(payload, liga_id))
        dia += timedelta(days=1)
    vistos = {}
    for j in jogos:
        key = (j.get("id") or "", j["home"], j["away"], j["data_txt"])
        vistos[key] = j
    return sorted(vistos.values(), key=lambda x: x.get("data") or datetime.now()), logs


def forca_inicial(time):
    nt = normalizar(time)
    for nome, valor in FORCA_BASE.items():
        if normalizar(nome) == nt:
            return 1300 + valor * 6
    seed = sum(ord(c) for c in nome_limpo(time))
    return 1710 + (seed % 140) - 70


def novo_stats():
    return {"jogos": 0, "gf": 0.0, "ga": 0.0, "home_gf": 0.0, "home_ga": 0.0, "home_j": 0, "away_gf": 0.0, "away_ga": 0.0, "away_j": 0}


def construir_contexto(jogos):
    encerrados = [j for j in jogos if j.get("completed")]
    ratings, stats = {}, {}
    total_home = total_away = empates = n = 0
    for j in sorted(encerrados, key=lambda x: x.get("data") or datetime.min):
        home, away = j["home"], j["away"]
        gh, ga = int(j["placar_home"]), int(j["placar_away"])
        ratings.setdefault(home, forca_inicial(home))
        ratings.setdefault(away, forca_inicial(away))
        stats.setdefault(home, novo_stats())
        stats.setdefault(away, novo_stats())

        exp_home = 1 / (1 + 10 ** ((ratings[away] - (ratings[home] + 58)) / 400))
        real_home = 1.0 if gh > ga else 0.5 if gh == ga else 0.0
        delta = 22 * (real_home - exp_home)
        ratings[home] += delta
        ratings[away] -= delta

        stats[home]["jogos"] += 1
        stats[home]["gf"] += gh
        stats[home]["ga"] += ga
        stats[home]["home_j"] += 1
        stats[home]["home_gf"] += gh
        stats[home]["home_ga"] += ga

        stats[away]["jogos"] += 1
        stats[away]["gf"] += ga
        stats[away]["ga"] += gh
        stats[away]["away_j"] += 1
        stats[away]["away_gf"] += ga
        stats[away]["away_ga"] += gh

        total_home += gh
        total_away += ga
        empates += 1 if gh == ga else 0
        n += 1

    return {
        "ratings": ratings,
        "stats": stats,
        "jogos": n,
        "media_home": total_home / max(1, n),
        "media_away": total_away / max(1, n),
        "taxa_empate": empates / max(1, n),
    }


def media_time(stats, time, campo, padrao):
    s = stats.get(time)
    if not s:
        return padrao
    if campo == "home_gf":
        return s["home_gf"] / max(1, s["home_j"])
    if campo == "home_ga":
        return s["home_ga"] / max(1, s["home_j"])
    if campo == "away_gf":
        return s["away_gf"] / max(1, s["away_j"])
    if campo == "away_ga":
        return s["away_ga"] / max(1, s["away_j"])
    return padrao


def matriz_poisson(media_home, media_away):
    mat, total = [], 0.0
    for i in range(MAX_GOLS + 1):
        row = []
        for j in range(MAX_GOLS + 1):
            p = poisson_pmf(i, media_home) * poisson_pmf(j, media_away)
            row.append(p)
            total += p
        mat.append(row)
    return [[p / total for p in row] for row in mat]


def calcular_cartoes_escanteios(media_home, media_away, p_empate, riscos):
    total_gols = media_home + media_away
    equilibrio = 1 - abs(media_home - media_away) / max(0.2, total_gols)
    classico = 0.45 if "classico" in riscos else 0.0
    cartoes_total = clamp(3.2 + 1.25 * equilibrio + 0.75 * p_empate + classico, 2.4, 7.2)
    cartoes_home = cartoes_total * clamp(0.49 + 0.06 * (media_away - media_home), 0.38, 0.62)
    escanteios_total = clamp(7.1 + 1.2 * total_gols + 0.75 * equilibrio, 6.0, 13.5)
    escanteios_home = escanteios_total * clamp(0.54 + 0.08 * (media_home - media_away), 0.40, 0.68)
    return {
        "cartoes_total": cartoes_total,
        "cartoes_home": cartoes_home,
        "cartoes_away": cartoes_total - cartoes_home,
        "over_25_cartoes": prob_over(cartoes_total, 2.5),
        "over_35_cartoes": prob_over(cartoes_total, 3.5),
        "over_45_cartoes": prob_over(cartoes_total, 4.5),
        "escanteios_total": escanteios_total,
        "escanteios_home": escanteios_home,
        "escanteios_away": escanteios_total - escanteios_home,
        "over_75_escanteios": prob_over(escanteios_total, 7.5),
        "over_85_escanteios": prob_over(escanteios_total, 8.5),
        "over_95_escanteios": prob_over(escanteios_total, 9.5),
        "over_105_escanteios": prob_over(escanteios_total, 10.5),
    }


def prever_jogo(jogo, contexto, desfalques_home=0, desfalques_away=0, ajuste_home=0, ajuste_away=0):
    home, away = jogo["home"], jogo["away"]
    ratings, stats = contexto["ratings"], contexto["stats"]
    rh = ratings.get(home, forca_inicial(home)) + ajuste_home - desfalques_home * 18
    ra = ratings.get(away, forca_inicial(away)) + ajuste_away - desfalques_away * 18
    liga_h = contexto["media_home"] or 1.35
    liga_a = contexto["media_away"] or 1.05

    ataque_h = media_time(stats, home, "home_gf", liga_h)
    defesa_a = media_time(stats, away, "away_ga", liga_h)
    ataque_a = media_time(stats, away, "away_gf", liga_a)
    defesa_h = media_time(stats, home, "home_ga", liga_a)
    elo_gap = (rh - ra + 58) / 400

    lam_h = clamp((0.52 * ataque_h + 0.48 * defesa_a) * (1 + 0.16 * elo_gap), 0.25, 3.8)
    lam_a = clamp((0.52 * ataque_a + 0.48 * defesa_h) * (1 - 0.14 * elo_gap), 0.20, 3.4)
    mat = matriz_poisson(lam_h, lam_a)

    p_h = sum(mat[i][j] for i in range(MAX_GOLS + 1) for j in range(MAX_GOLS + 1) if i > j)
    p_d = sum(mat[i][i] for i in range(MAX_GOLS + 1))
    p_a = sum(mat[i][j] for i in range(MAX_GOLS + 1) for j in range(MAX_GOLS + 1) if i < j)
    p_d = 0.74 * p_d + 0.26 * contexto.get("taxa_empate", 0.26)
    total = p_h + p_d + p_a
    p_h, p_d, p_a = p_h / total, p_d / total, p_a / total

    over15 = 1 - sum(mat[i][j] for i in range(MAX_GOLS + 1) for j in range(MAX_GOLS + 1) if i + j <= 1)
    over25 = 1 - sum(mat[i][j] for i in range(MAX_GOLS + 1) for j in range(MAX_GOLS + 1) if i + j <= 2)
    under35 = sum(mat[i][j] for i in range(MAX_GOLS + 1) for j in range(MAX_GOLS + 1) if i + j <= 3)
    btts = sum(mat[i][j] for i in range(1, MAX_GOLS + 1) for j in range(1, MAX_GOLS + 1))
    placares = sorted([(mat[i][j], i, j) for i in range(MAX_GOLS + 1) for j in range(MAX_GOLS + 1)], reverse=True)[:3]

    riscos = []
    if tuple(sorted([normalizar(home), normalizar(away)])) in CLASSICOS:
        riscos.append("classico")
    amostra = stats.get(home, {}).get("jogos", 0) + stats.get(away, {}).get("jogos", 0)
    if amostra < 10:
        riscos.append("baixa amostra")
    if abs(p_h - p_a) < 0.08:
        riscos.append("forcas proximas")
    if desfalques_home or desfalques_away:
        riscos.append(f"desfalques {home}:{desfalques_home} {away}:{desfalques_away}")

    probs = {"Casa": p_h, "Empate": p_d, "Fora": p_a}
    palpite = max(probs, key=probs.get)
    prob_palpite = probs[palpite]
    mercados = {
        "Over 1.5 gols": over15,
        "Over 2.5 gols": over25,
        "Under 3.5 gols": under35,
        "Ambas marcam": btts,
        f"{home} ou empate": p_h + p_d,
        f"{away} ou empate": p_a + p_d,
    }
    melhor_mercado, melhor_prob = max(mercados.items(), key=lambda x: x[1])
    score = int(clamp(45 + prob_palpite * 38 + melhor_prob * 18 + min(amostra, 40) * 0.25 - len(riscos) * 6, 0, 96))
    if score >= 76:
        decisao, cor, classe = "Apostar", "green", "good"
    elif score >= 62:
        decisao, cor, classe = "Cuidado", "amber", "medium"
    else:
        decisao, cor, classe = "Evitar", "red", "low"

    extras = calcular_cartoes_escanteios(lam_h, lam_a, p_d, riscos)
    return {
        "p_h": p_h, "p_d": p_d, "p_a": p_a, "lam_h": lam_h, "lam_a": lam_a,
        "over15": over15, "over25": over25, "under35": under35, "btts": btts,
        "placares": placares, "palpite": palpite, "prob_palpite": prob_palpite,
        "melhor_mercado": melhor_mercado, "melhor_prob": melhor_prob,
        "score": score, "decisao": decisao, "cor": cor, "classe": classe,
        "riscos": riscos, **extras,
    }


def criar_jogo_manual(home, away):
    return {"id": "manual", "home": nome_limpo(home), "away": nome_limpo(away), "data_txt": "Manual", "status": "analise manual", "completed": False, "live": False, "placar_home": 0, "placar_away": 0}


def render_card(jogo, r):
    mapa = {"Casa": jogo["home"], "Fora": jogo["away"], "Empate": "Empate"}
    riscos = ", ".join(r["riscos"]) if r["riscos"] else "baixo risco"
    placar = f" - {jogo['placar_home']} x {jogo['placar_away']}" if jogo.get("completed") or jogo.get("live") else ""
    st.markdown(
        f"""
        <div class="card {r['classe']}">
            <div class="card-title">{jogo['home']} x {jogo['away']}{placar}</div>
            <div class="muted">{jogo.get('data_txt', '')} | {jogo.get('status', '')}</div>
            <span class="pill">Vitoria {jogo['home']}: <strong>{pct(r['p_h'])}</strong></span>
            <span class="pill">Empate: <strong>{pct(r['p_d'])}</strong></span>
            <span class="pill">Vitoria {jogo['away']}: <strong>{pct(r['p_a'])}</strong></span>
            <br>
            <span class="pill">Palpite: <strong>{mapa[r['palpite']]}</strong></span>
            <span class="pill">Probabilidade: <strong>{pct(r['prob_palpite'])}</strong></span>
            <span class="pill">Melhor mercado: <strong>{r['melhor_mercado']} {pct(r['melhor_prob'])}</strong></span>
            <span class="pill">Placar provavel: <strong>{r['placares'][0][1]}x{r['placares'][0][2]}</strong></span>
            <span class="pill">Gols esp.: <strong>{r['lam_h']:.2f} x {r['lam_a']:.2f}</strong></span>
            <br>
            <span class="pill">Cartoes esp.: <strong>{r['cartoes_total']:.1f}</strong></span>
            <span class="pill">Over 2.5 cartoes: <strong>{pct(r['over_25_cartoes'])}</strong></span>
            <span class="pill">Over 3.5 cartoes: <strong>{pct(r['over_35_cartoes'])}</strong></span>
            <span class="pill">Over 4.5 cartoes: <strong>{pct(r['over_45_cartoes'])}</strong></span>
            <br>
            <span class="pill">Escanteios esp.: <strong>{r['escanteios_total']:.1f}</strong></span>
            <span class="pill">Over 7.5 esc.: <strong>{pct(r['over_75_escanteios'])}</strong></span>
            <span class="pill">Over 8.5 esc.: <strong>{pct(r['over_85_escanteios'])}</strong></span>
            <span class="pill">Over 9.5 esc.: <strong>{pct(r['over_95_escanteios'])}</strong></span>
            <span class="pill">Over 10.5 esc.: <strong>{pct(r['over_105_escanteios'])}</strong></span>
            <br><span class="decision {r['cor']}">{r['decisao']}</span>
            <span class="pill">Score: <strong>{r['score']}/100</strong></span>
            <span class="pill">Alertas: <strong>{riscos}</strong></span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def tabela_cartoes_escanteios(previsoes):
    return pd.DataFrame([{
        "Jogo": f"{j['home']} x {j['away']}",
        "Cartoes esp.": round(r["cartoes_total"], 1),
        "Over 2.5 cartoes": pct(r["over_25_cartoes"]),
        "Over 3.5 cartoes": pct(r["over_35_cartoes"]),
        "Over 4.5 cartoes": pct(r["over_45_cartoes"]),
        "Escanteios esp.": round(r["escanteios_total"], 1),
        "Over 7.5 esc.": pct(r["over_75_escanteios"]),
        "Over 8.5 esc.": pct(r["over_85_escanteios"]),
        "Over 9.5 esc.": pct(r["over_95_escanteios"]),
        "Over 10.5 esc.": pct(r["over_105_escanteios"]),
    } for j, r in previsoes])


def render_value_box(titulo, prob, odd, banca):
    ev = valor_esperado(prob, odd)
    stake = kelly_stake(prob, odd, banca)
    color = "green" if ev > 0 else "red"
    st.markdown(f"**{titulo}**")
    st.write(f"Probabilidade: **{pct(prob)}**")
    st.write(f"Odd justa: **{odd_justa(prob):.2f}**")
    st.markdown(f"EV: <span class='{color}'>{ev:+.2%}</span>", unsafe_allow_html=True)
    st.write(f"Stake Kelly 25%: **R$ {stake:.2f}**")


def resultado_real(j):
    if int(j["placar_home"]) > int(j["placar_away"]):
        return "Casa"
    if int(j["placar_home"]) < int(j["placar_away"]):
        return "Fora"
    return "Empate"


def avaliar_ultimas_horas(jogos, horas=36):
    agora = datetime.now()
    limite = agora - timedelta(hours=horas)
    encerrados = [j for j in jogos if j.get("completed") and j.get("data")]
    encerrados = sorted(encerrados, key=lambda x: x["data"])
    recentes = [j for j in encerrados if limite <= j["data"] <= agora]
    rows = []
    for jogo in recentes:
        anteriores = [x for x in encerrados if x["data"] < jogo["data"]]
        if len(anteriores) < 8:
            continue
        ctx = construir_contexto(anteriores)
        prev = prever_jogo(jogo, ctx)
        real = resultado_real(jogo)
        gols = int(jogo["placar_home"]) + int(jogo["placar_away"])
        btts_real = int(jogo["placar_home"]) > 0 and int(jogo["placar_away"]) > 0
        rows.append({
            "Data": jogo["data_txt"],
            "Jogo": f"{jogo['home']} {jogo['placar_home']} x {jogo['placar_away']} {jogo['away']}",
            "Previsto 1X2": {"Casa": jogo["home"], "Fora": jogo["away"], "Empate": "Empate"}[prev["palpite"]],
            "Real 1X2": {"Casa": jogo["home"], "Fora": jogo["away"], "Empate": "Empate"}[real],
            "1X2": "acerto" if prev["palpite"] == real else "erro",
            "Over 1.5": "acerto" if (prev["over15"] >= 0.55) == (gols >= 2) else "erro",
            "Over 2.5": "acerto" if (prev["over25"] >= 0.55) == (gols >= 3) else "erro",
            "Ambas": "acerto" if (prev["btts"] >= 0.55) == btts_real else "erro",
            "Prob. casa": pct(prev["p_h"]),
            "Prob. empate": pct(prev["p_d"]),
            "Prob. fora": pct(prev["p_a"]),
        })
    return rows


def prob_tenis_manual(forma1, forma2, sup1, sup2, h2h1, h2h2, rating1, rating2):
    elo = 1 / (1 + 10 ** ((rating2 - rating1) / 400))
    forma_total = max(1, forma1 + forma2)
    sup_total = max(1, sup1 + sup2)
    h2h_total = max(1, h2h1 + h2h2)
    p1 = 0.42 * (forma1 / forma_total) + 0.28 * (sup1 / sup_total) + 0.20 * elo + 0.10 * (h2h1 / h2h_total)
    return clamp(p1, 0.05, 0.95), clamp(1 - p1, 0.05, 0.95)


st.markdown(
    """
    <div class="hero">
        <h1>AE Analisador Esportivo Pro 10.2</h1>
        <p>Futebol e tenis com ESPN gratis, Poisson, Elo, desfalques, cartoes, escanteios, Kelly e diagnostico.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    menu = st.radio("Navegacao", ["Analise por Liga", "Melhores oportunidades", "Jogos ao Vivo", "Tenis", "Performance 36h", "Gestao de Banca"])
    st.divider()
    banca_usuario = st.number_input("Banca para stake (R$)", min_value=0.0, value=1000.0, step=50.0)
    liga_sel = st.selectbox("Liga", list(LIGAS.keys()))
    dias_hist = st.slider("Historico do modelo", 30, 180, 90, step=15)
    dias_fut = st.slider("Proximos dias", 0, 14, 7)
    if st.button("Atualizar dados"):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    st.write("Versao 10.2 - gratis")

liga_id = LIGAS[liga_sel]
with st.spinner("Carregando dados gratis da ESPN..."):
    jogos_periodo, logs = buscar_periodo(liga_id, dias_hist, dias_fut)
contexto = construir_contexto(jogos_periodo)
previsoes = [(j, prever_jogo(j, contexto)) for j in jogos_periodo if not j.get("completed")]


if menu == "Analise por Liga":
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Jogos encontrados", len(jogos_periodo))
    c2.metric("Base do modelo", contexto["jogos"])
    c3.metric("Media casa", f"{contexto['media_home']:.2f}")
    c4.metric("Media fora", f"{contexto['media_away']:.2f}")
    if logs:
        with st.expander("Avisos"):
            for log in logs[:8]:
                st.write(log)

    jogos_futuros = [j for j in jogos_periodo if not j.get("completed")]
    if not jogos_futuros:
        st.warning("Nenhum jogo futuro encontrado. Use a analise manual abaixo.")
    else:
        escolhido = st.selectbox("Selecione o jogo", [f"{j['home']} x {j['away']} ({j['status']})" for j in jogos_futuros])
        jogo = next(j for j in jogos_futuros if f"{j['home']} x {j['away']} ({j['status']})" == escolhido)
        d1, d2, d3 = st.columns(3)
        with d1:
            des_h = st.slider(f"Desfalques importantes {jogo['home']}", 0, 6, 0)
            des_a = st.slider(f"Desfalques importantes {jogo['away']}", 0, 6, 0)
        with d2:
            odd_h = st.number_input(f"Odd {jogo['home']}", 1.01, 50.0, 2.0, step=0.05)
            odd_d = st.number_input("Odd Empate", 1.01, 50.0, 3.2, step=0.05)
            odd_a = st.number_input(f"Odd {jogo['away']}", 1.01, 50.0, 3.5, step=0.05)
        with d3:
            aj_h = st.slider(f"Ajuste tecnico {jogo['home']}", -30, 30, 0)
            aj_a = st.slider(f"Ajuste tecnico {jogo['away']}", -30, 30, 0)
        r = prever_jogo(jogo, contexto, des_h, des_a, aj_h, aj_a)
        render_card(jogo, r)
        st.subheader("Cartoes e escanteios - probabilidades")
        st.dataframe(tabela_cartoes_escanteios([(jogo, r)]), use_container_width=True, hide_index=True)
        v1, v2, v3 = st.columns(3)
        with v1:
            render_value_box(jogo["home"], r["p_h"], odd_h, banca_usuario)
        with v2:
            render_value_box("Empate", r["p_d"], odd_d, banca_usuario)
        with v3:
            render_value_box(jogo["away"], r["p_a"], odd_a, banca_usuario)

    with st.expander("Analise manual de futebol"):
        m1, m2, m3 = st.columns(3)
        with m1:
            mh = st.text_input("Time da casa", "Flamengo")
            ma = st.text_input("Time visitante", "Palmeiras")
        with m2:
            des_mh = st.slider("Desfalques casa", 0, 6, 0)
            des_ma = st.slider("Desfalques fora", 0, 6, 0)
        with m3:
            oh = st.number_input("Odd casa manual", 1.01, 50.0, 2.0, step=0.05)
            od = st.number_input("Odd empate manual", 1.01, 50.0, 3.2, step=0.05)
            oa = st.number_input("Odd fora manual", 1.01, 50.0, 3.5, step=0.05)
        jogo_m = criar_jogo_manual(mh, ma)
        rm = prever_jogo(jogo_m, contexto, des_mh, des_ma)
        render_card(jogo_m, rm)
        st.dataframe(tabela_cartoes_escanteios([(jogo_m, rm)]), use_container_width=True, hide_index=True)
        x1, x2, x3 = st.columns(3)
        with x1:
            render_value_box(jogo_m["home"], rm["p_h"], oh, banca_usuario)
        with x2:
            render_value_box("Empate", rm["p_d"], od, banca_usuario)
        with x3:
            render_value_box(jogo_m["away"], rm["p_a"], oa, banca_usuario)


elif menu == "Melhores oportunidades":
    st.subheader("Melhores oportunidades")
    itens = sorted(previsoes, key=lambda x: x[1]["score"], reverse=True)[:15]
    if not itens:
        st.warning("Sem jogos futuros para ranquear.")
    else:
        df = pd.DataFrame([{
            "Data": j["data_txt"], "Jogo": f"{j['home']} x {j['away']}",
            "Palpite": {"Casa": j["home"], "Fora": j["away"], "Empate": "Empate"}[r["palpite"]],
            "Prob.": pct(r["prob_palpite"]), "Mercado": r["melhor_mercado"],
            "Prob. mercado": pct(r["melhor_prob"]), "Score": r["score"], "Decisao": r["decisao"],
        } for j, r in itens])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.subheader("Cartoes e escanteios - todos os jogos")
        st.dataframe(tabela_cartoes_escanteios(itens), use_container_width=True, hide_index=True)
        for j, r in itens:
            render_card(j, r)


elif menu == "Jogos ao Vivo":
    st.subheader("Jogos ao vivo")
    ao_vivo = [(j, r) for j, r in previsoes if j.get("live")]
    if not ao_vivo:
        st.info("Nenhum jogo ao vivo encontrado agora nesta liga.")
    for j, r in ao_vivo:
        r = {**r, "classe": "live"}
        render_card(j, r)


elif menu == "Tenis":
    st.subheader("Analise manual de tenis")
    t1, t2, t3 = st.columns(3)
    with t1:
        jogador1 = st.text_input("Jogador 1", "Novak Djokovic")
        jogador2 = st.text_input("Jogador 2", "Carlos Alcaraz")
    with t2:
        forma1 = st.slider("Forma recente jogador 1 (%)", 0, 100, 78)
        forma2 = st.slider("Forma recente jogador 2 (%)", 0, 100, 74)
        sup1 = st.slider("Aderencia superficie jogador 1 (%)", 0, 100, 76)
        sup2 = st.slider("Aderencia superficie jogador 2 (%)", 0, 100, 80)
    with t3:
        h2h1 = st.number_input("Vitorias H2H jogador 1", 0, 50, 3)
        h2h2 = st.number_input("Vitorias H2H jogador 2", 0, 50, 2)
        odd1 = st.number_input("Odd jogador 1", 1.01, 50.0, 1.90, step=0.05)
        odd2 = st.number_input("Odd jogador 2", 1.01, 50.0, 1.95, step=0.05)
    rating1 = 1500 + (sum(ord(c) for c in jogador1) % 120) - 60
    rating2 = 1500 + (sum(ord(c) for c in jogador2) % 120) - 60
    p1, p2 = prob_tenis_manual(forma1, forma2, sup1, sup2, h2h1, h2h2, rating1, rating2)
    st.metric(jogador1, pct(p1), f"Odd justa {odd_justa(p1):.2f}")
    st.metric(jogador2, pct(p2), f"Odd justa {odd_justa(p2):.2f}")
    c1, c2 = st.columns(2)
    with c1:
        render_value_box(jogador1, p1, odd1, banca_usuario)
    with c2:
        render_value_box(jogador2, p2, odd2, banca_usuario)


elif menu == "Performance 36h":
    st.subheader("Acertos e erros das ultimas 36 horas")
    rows = avaliar_ultimas_horas(jogos_periodo, 36)
    if not rows:
        st.info("Ainda nao ha jogos encerrados nas ultimas 36 horas com amostra suficiente.")
    else:
        df = pd.DataFrame(rows)
        total = len(df)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("1X2", f"{(df['1X2'] == 'acerto').sum()}/{total}", pct((df["1X2"] == "acerto").mean()))
        c2.metric("Over 1.5", f"{(df['Over 1.5'] == 'acerto').sum()}/{total}", pct((df["Over 1.5"] == "acerto").mean()))
        c3.metric("Over 2.5", f"{(df['Over 2.5'] == 'acerto').sum()}/{total}", pct((df["Over 2.5"] == "acerto").mean()))
        c4.metric("Ambas", f"{(df['Ambas'] == 'acerto').sum()}/{total}", pct((df["Ambas"] == "acerto").mean()))
        st.dataframe(df, use_container_width=True, hide_index=True)


elif menu == "Gestao de Banca":
    st.subheader("Calculadora de stake")
    banca = st.number_input("Banca Total (R$)", value=1000.0)
    odd = st.number_input("Odd", value=2.0)
    prob = st.slider("Sua probabilidade (%)", 1, 100, 55) / 100
    st.success(f"Sugestao Kelly 25%: R$ {kelly_stake(prob, odd, banca):.2f}")
