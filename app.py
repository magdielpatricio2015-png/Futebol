import math
import re
import unicodedata
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import streamlit as st

# --- Configuração da página ---
st.set_page_config(
    page_title="Analisador Esportivo Pro 10.2",
    page_icon="AE",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Constantes ---
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
HEADERS = {"User-Agent": "AnalisadorEsportivoPro/10.2"}
MAX_GOLS = 10
RETRIES = 2

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

# --- CSS personalizado ---
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
    .live-badge {
        background: #dc2626;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.8rem;
        margin-left: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Sessão ---
if "historico" not in st.session_state:
    st.session_state.historico = []

# --- Funções auxiliares ---
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
    except:
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

# --- API ESPN ---
def fetch_with_retry(url, params, retries=RETRIES):
    for i in range(retries):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            return resp.json(), ""
        except requests.RequestException as exc:
            if i == retries - 1:
                return {}, f"Erro ESPN: {exc}"
    return {}, ""

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
        home = next((c for c in competidores if c.get("homeAway") == "home"), competidores[0])
        away = next((c for c in competidores if c.get("homeAway") == "away"), competidores[1])
        status_type = event.get("status", {}).get("type", {})

        def placar(c):
            try:
                return int(c.get("score", 0))
            except:
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

# --- Modelo de força / estatísticas ---
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
        riscos.append("forças próximas")
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

# --- Renderização (com suporte a live) ---
def criar_jogo_manual(home, away):
    return {"id": "manual", "home": nome_limpo(home), "away": nome_limpo(away), "data_txt": "Manual", "status": "análise manual", "completed": False, "live": False, "placar_home": 0, "placar_away": 0}

def render_card(jogo, r):
    mapa = {"Casa": jogo["home"], "Fora": jogo["away"], "Empate": "Empate"}
    riscos = ", ".join(r["riscos"]) if r["riscos"] else "baixo risco"
    live = jogo.get("live", False)

    # Define a classe do card combinando decisão e status ao vivo
    if live:
        card_class = f"{r['classe']} live"
    else:
        card_class = r["classe"]

    # Exibe placar atual e badge de AO VIVO
    if live:
        placar = f" - {jogo['placar_home']} x {jogo['placar_away']} <span class='live-badge'>🔴 AO VIVO</span>"
    elif jogo.get("completed"):
        placar = f" - {jogo['placar_home']} x {jogo['placar_away']} (encerrado)"
    else:
        placar = ""

    st.markdown(
        f"""
        <div class="card {card_class}">
            <div class="card-title">{jogo['home']} x {jogo['away']}{placar}</div>
            <div class="muted">{jogo.get('data_txt', '')} | {jogo.get('status', '')}</div>
            <span class="pill">Vitória {jogo['home']}: <strong>{pct(r['p_h'])}</strong></span>
            <span class="pill">Empate: <strong>{pct(r['p_d'])}</strong></span>
            <span class="pill">Vitória {jogo['away']}: <strong>{pct(r['p_a'])}</strong></span>
            <br>
            <span class="pill">Palpite: <strong>{mapa[r['palpite']]}</strong></span>
            <span class="pill">Probabilidade: <strong>{pct(r['prob_palpite'])}</strong></span>
            <span class="pill">Melhor mercado: <strong>{r['melhor_mercado']} {pct(r['melhor_prob'])}</strong></span>
            <span class="pill">Placar provável: <strong>{r['placares'][0][1]}x{r['placares'][0][2]}</strong></span>
            <span class="pill">Gols esp.: <strong>{r['lam_h']:.2f} x {r['lam_a']:.2f}</strong></span>
            <br>
            <span class="pill">Cartões esp.: <strong>{r['cartoes_total']:.1f}</strong></span>
            <span class="pill">Over 2.5 cartões: <strong>{pct(r['over_25_cartoes'])}</strong></span>
            <span class="pill">Over 3.5 cartões: <strong>{pct(r['over_35_cartoes'])}</strong></span>
            <span class="pill">Over 4.5 cartões: <strong>{pct(r['over_45_cartoes'])}</strong></span>
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

def render_value_box(titulo, prob, odd, banca):
    ev = valor_esperado(prob, odd)
    stake = kelly_stake(prob, odd, banca)
    color = "#16a34a" if ev > 0 else "#dc2626"
    st.markdown(
        f"""
        <div style="border:1px solid #d7dce2; border-radius:8px; padding:10px; margin:5px 0; background:#f8fafc;">
            <strong>{titulo}</strong><br>
            <span>Probabilidade: {pct(prob)} | Odd informada: {odd:.2f} | Odd justa: {odd_justa(prob):.2f}</span><br>
            <span style="color:{color}; font-weight:bold;">EV: {ev:+.2f}</span> |
            <span>Stake sugerido (Kelly 25%): R$ {stake:.2f}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

# --- Interface principal ---
def main():
    st.markdown('<div class="hero"><h1>⚽ Analisador Esportivo Pro 10.2</h1><p>Probabilidades, mercados de gols, cartões e escanteios com inteligência estatística.</p></div>', unsafe_allow_html=True)

    with st.sidebar:
        st.header("Configuração")
        liga_nome = st.selectbox("Liga", list(LIGAS.keys()))
        liga_id = LIGAS[liga_nome]

        col1, col2 = st.columns(2)
        with col1:
            dias_passado = st.slider("Dias passados", 0, 30, 10)
        with col2:
            dias_futuro = st.slider("Dias futuros", 0, 7, 3)

        # --- Opção de jogos ao vivo ---
        mostrar_ao_vivo = st.checkbox("🔴 Mostrar apenas jogos ao vivo")

        modo_manual = st.checkbox("Adicionar jogo manual")
        if modo_manual:
            with st.form("manual_form"):
                home = st.text_input("Time da casa")
                away = st.text_input("Time visitante")
                desf_home = st.number_input("Desfalques casa", 0, 5, 0)
                desf_away = st.number_input("Desfalques fora", 0, 5, 0)
                submitted = st.form_submit_button("Adicionar")
                if submitted and home and away:
                    jogo_manual = criar_jogo_manual(home, away)
                    st.session_state["jogo_manual"] = (jogo_manual, desf_home, desf_away)

        st.markdown("---")
        st.subheader("Avaliação de valor (odds reais)")
        odd_input = st.text_input("Odd do palpite (ex: 2.10)")
        banca = st.number_input("Banca (R$)", 0.0, 100000.0, 1000.0, step=100.0)

    # Carregar jogos
    with st.spinner("Buscando jogos e calculando previsões..."):
        jogos, logs = buscar_periodo(liga_id, dias_passado, dias_futuro)
        contexto = construir_contexto(jogos)

        todos_jogos = []
        for j in jogos:
            if not j.get("completed") or j.get("live"):
                desf_h, desf_a = 0, 0
                previsao = prever_jogo(j, contexto, desf_h, desf_a)
                todos_jogos.append((j, previsao))

        if "jogo_manual" in st.session_state:
            mj, mh, ma = st.session_state["jogo_manual"]
            previsao_m = prever_jogo(mj, contexto, mh, ma)
            todos_jogos.append((mj, previsao_m))

        # Filtra apenas jogos ao vivo, se checkbox marcado
        if mostrar_ao_vivo:
            todos_jogos = [(j, p) for j, p in todos_jogos if j.get("live")]

        # Ordenar: live first, then by date
        todos_jogos.sort(key=lambda x: (not x[0].get("live"), x[0].get("data") or datetime.max))

    if mostrar_ao_vivo:
        st.header(f"📺 Jogos ao vivo – {liga_nome} ({len(todos_jogos)} jogo(s))")
    else:
        st.header(f"📊 Análises – {liga_nome} ({len(todos_jogos)} jogos)")

    if logs:
        with st.expander("Logs de erros na API"):
            for log in logs:
                st.warning(log)

    if not todos_jogos:
        st.info("Nenhum jogo ao vivo no momento." if mostrar_ao_vivo else "Nenhum jogo encontrado no período selecionado.")
        return

    for jogo, prev in todos_jogos:
        render_card(jogo, prev)
        try:
            odd = float(odd_input) if odd_input else 0
        except:
            odd = 0
        if odd > 0:
            if prev["palpite"] == "Casa":
                prob = prev["p_h"]
                mercado = f"Vitória {jogo['home']}"
            elif prev["palpite"] == "Fora":
                prob = prev["p_a"]
                mercado = f"Vitória {jogo['away']}"
            else:
                prob = prev["p_d"]
                mercado = "Empate"
            render_value_box(f"{mercado} (Palpite)", prob, odd, banca)

    # Tabela resumo (caso não seja apenas ao vivo, ou sempre? Mostramos se houver jogos)
    st.subheader("📋 Resumo – Cartões e Escanteios")
    df = pd.DataFrame([{
        "Jogo": f"{j['home']} x {j['away']}",
        "Cartões esp.": round(r["cartoes_total"], 1),
        "Over 2.5 cartões": pct(r["over_25_cartoes"]),
        "Over 3.5 cartões": pct(r["over_35_cartoes"]),
        "Over 4.5 cartões": pct(r["over_45_cartoes"]),
        "Escanteios esp.": round(r["escanteios_total"], 1),
        "Over 7.5 esc.": pct(r["over_75_escanteios"]),
        "Over 8.5 esc.": pct(r["over_85_escanteios"]),
        "Over 9.5 esc.": pct(r["over_95_escanteios"]),
        "Over 10.5 esc.": pct(r["over_105_escanteios"]),
    } for j, r in todos_jogos])
    st.dataframe(df, use_container_width=True)

    # Histórico
    st.session_state.historico.extend(todos_jogos)
    st.subheader("📜 Histórico da sessão")
    hist_df = pd.DataFrame([{
        "Data": j.get("data_txt"),
        "Jogo": f"{j['home']} x {j['away']}",
        "Palpite": mapa_palpite(j, r),
        "Prob.": pct(r["prob_palpite"]),
        "Score": r["score"],
        "Decisão": r["decisao"],
    } for j, r in st.session_state.historico])
    st.dataframe(hist_df.tail(20), use_container_width=True)

def mapa_palpite(jogo, pred):
    mp = {"Casa": jogo["home"], "Fora": jogo["away"], "Empate": "Empate"}
    return mp.get(pred["palpite"], pred["palpite"])

if __name__ == "__main__":
    main()