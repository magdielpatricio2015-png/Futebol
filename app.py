import math
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from collections import defaultdict

import pandas as pd
import requests
import streamlit as st

# ----------------------------------------------------------------------
# Configuração da página
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="Analisador Esportivo Pro 10.3",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------------
# Constantes
# ----------------------------------------------------------------------
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
HEADERS = {"User-Agent": "AnalisadorEsportivoPro/10.3"}
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
    "Flamengo": 86, "Palmeiras": 84, "Botafogo": 79, "Atletico-MG": 76,
    "Sao Paulo": 78, "Fluminense": 77, "Gremio": 74, "Internacional": 75,
    "Corinthians": 76, "Cruzeiro": 73, "Bahia": 74, "Fortaleza": 73,
    "Vasco": 70, "Santos": 72, "Ceara": 69, "Sport": 68, "Vitoria": 69,
    "Manchester City": 91, "Arsenal": 88, "Liverpool": 88, "Chelsea": 82,
    "Tottenham Hotspur": 80, "Real Madrid": 90, "Barcelona": 87,
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

JOGADORES = {
    "flamengo": [("Pedro", 0.35), ("Arrascaeta", 0.18), ("Bruno Henrique", 0.15)],
    "palmeiras": [("Raphael Veiga", 0.25), ("Flaco López", 0.30)],
    "corinthians": [("Yuri Alberto", 0.32), ("Wesley", 0.20)],
    "sao paulo": [("Calleri", 0.33), ("Lucas Moura", 0.22)],
    "atletico-mg": [("Paulinho", 0.28), ("Cadu", 0.16)],
    "fluminense": [("John Kennedy", 0.24), ("Jhon Arias", 0.20)],
    "botafogo": [("Igor Jesus", 0.28), ("Matheus Nascimento", 0.18)],
    "manchester city": [("Haaland", 0.45), ("Foden", 0.18)],
    "real madrid": [("Mbappé", 0.35), ("Vinicius Jr", 0.25)],
    "barcelona": [("Lewandowski", 0.33), ("Yamal", 0.17)],
    "inter milan": [("Lautaro Martínez", 0.35), ("Thuram", 0.20)],
    "gremio": [("Diego Costa", 0.26), ("Ferreira", 0.14)],
    "internacional": [("Enner Valencia", 0.30), ("Wanderson", 0.15)],
}

# ----------------------------------------------------------------------
# CSS
# ----------------------------------------------------------------------
st.markdown(
    """
    <style>
    .main { background-color: #ffffff; color: #111827; }
    .block-container { padding-top: 1rem; max-width: 1450px; }
    section[data-testid="stSidebar"] { background: #f1f5f9; }
    div[data-testid="stMetric"] {
        background-color: #f8fafc; padding: 14px; border-radius: 8px; border: 1px solid #d7dce2;
    }
    .hero {
        border: 1px solid #d7dce2; background: #f8fafc; border-radius: 8px;
        padding: 18px 20px; margin-bottom: 16px;
    }
    .hero h1 { margin: 0; font-size: 2rem; color: #111827; }
    .hero p { margin: 6px 0 0; color: #475569; }
    .card {
        border: 1px solid #d7dce2; border-radius: 8px; padding: 14px 16px;
        margin: 10px 0; background: #ffffff;
    }
    .card.good { border-left: 6px solid #16a34a; }
    .card.medium { border-left: 6px solid #eab308; }
    .card.low { border-left: 6px solid #dc2626; }
    .card.live { border-left: 6px solid #2563eb; }
    .card-title { font-size: 1.08rem; font-weight: 800; margin-bottom: 6px; }
    .muted { color: #64748b; font-size: .88rem; }
    .pill {
        display: inline-block; padding: 5px 9px; margin: 5px 5px 0 0;
        border-radius: 6px; background: #eef2f7; border: 1px solid #d7dce2; font-size: .88rem;
    }
    .pill strong { color: #111827; }
    .decision {
        display: inline-block; padding: 6px 10px; margin: 8px 6px 0 0;
        border-radius: 6px; color: white; font-weight: 800;
    }
    .decision.green { background: #16a34a; }
    .decision.amber { background: #ca8a04; }
    .decision.red { background: #dc2626; }
    .green { color: #16883c; font-weight: 800; }
    .red { color: #c92a2a; font-weight: 800; }
    .stButton>button { background-color: #0d6efd; color: white; border-radius: 5px; }
    .live-badge {
        background: #dc2626; color: white; padding: 2px 8px; border-radius: 4px;
        font-weight: bold; font-size: 0.8rem; margin-left: 8px;
    }
    .finisher-name { font-weight: 700; font-size: 1rem; }
    .finisher-prob { color: #2563eb; font-weight: 700; margin-left: 8px; }
    .team-info {
        display: flex; align-items: center; gap: 12px; margin-bottom: 6px;
        font-size: 0.9rem; color: #475569;
    }
    .form-badge {
        display: inline-block; width: 22px; height: 22px; line-height: 22px;
        text-align: center; border-radius: 4px; font-size: 0.8rem; font-weight: bold;
        margin-right: 2px;
    }
    .form-v { background: #16a34a; color: white; }
    .form-e { background: #eab308; color: white; }
    .form-d { background: #dc2626; color: white; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------
# Inicialização da sessão
# ----------------------------------------------------------------------
if "historico" not in st.session_state:
    st.session_state.historico = []
if "jogo_manual" not in st.session_state:
    st.session_state.jogo_manual = None

# ----------------------------------------------------------------------
# Funções auxiliares
# ----------------------------------------------------------------------
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

# ----------------------------------------------------------------------
# API ESPN – placares e classificação
# ----------------------------------------------------------------------
def fetch_with_retry(url, params=None, retries=RETRIES):
    for i in range(retries):
        try:
            resp = requests.get(url, params=params or {}, headers=HEADERS, timeout=10)
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

@st.cache_data(ttl=3600, show_spinner=False)
def buscar_classificacao(liga_id):
    url = f"{ESPN_BASE}/{liga_id}/standings"
    payload, err = fetch_with_retry(url)
    if err or not payload:
        return {}
    tabela = {}
    try:
        for group in payload.get("children", []):
            for entry in group.get("standings", {}).get("entries", []):
                time_nome = entry.get("team", {}).get("displayName", "")
                time_nome_limpo = nome_limpo(time_nome)
                pos = entry.get("stats", [{}])[0].get("value", 99)  # posição normalmente no primeiro stat
                # A ESPN coloca a posição como valor inteiro
                if isinstance(pos, (int, float)):
                    pos = int(pos)
                else:
                    pos = 99
                # Às vezes a posição está no field "rank"
                if "rank" in entry:
                    pos = entry["rank"]
                tabela[time_nome_limpo] = {"posicao": pos, "time_original": time_nome}
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

# ----------------------------------------------------------------------
# Modelo de força e estatísticas (com ajuste de posição/forma)
# ----------------------------------------------------------------------
def forca_inicial(time):
    nt = normalizar(time)
    for nome, valor in FORCA_BASE.items():
        if normalizar(nome) == nt:
            return 1300 + valor * 6
    seed = sum(ord(c) for c in nome_limpo(time))
    return 1710 + (seed % 140) - 70

def novo_stats():
    return {"jogos": 0, "gf": 0.0, "ga": 0.0, "home_gf": 0.0, "home_ga": 0.0, "home_j": 0,
            "away_gf": 0.0, "away_ga": 0.0, "away_j": 0}

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

def calcular_forma(jogos, time_normalizado):
    """ Retorna lista de resultados ('V','E','D') dos últimos 5 jogos encerrados do time. """
    jogos_time = [j for j in jogos if j.get("completed") and
                  (normalizar(j["home"]) == time_normalizado or normalizar(j["away"]) == time_normalizado)]
    jogos_time = sorted(jogos_time, key=lambda x: x.get("data") or datetime.min, reverse=True)[:5]
    forma = []
    for j in jogos_time:
        if normalizar(j["home"]) == time_normalizado:
            gh, ga = int(j["placar_home"]), int(j["placar_away"])
        else:
            ga, gh = int(j["placar_home"]), int(j["placar_away"])
        if gh > ga:
            forma.append("V")
        elif gh == ga:
            forma.append("E")
        else:
            forma.append("D")
    return forma

def calcular_pontos_forma(forma):
    """ Pontuação simples: V=3, E=1, D=0. Retorna total e string. """
    pts = 0
    for r in forma:
        if r == "V": pts += 3
        elif r == "E": pts += 1
    return pts, " ".join(forma)

def prever_jogo(jogo, contexto, posicoes=None, formas=None, desfalques_home=0, desfalques_away=0, ajuste_home=0, ajuste_away=0):
    home, away = jogo["home"], jogo["away"]
    ratings, stats = contexto["ratings"], contexto["stats"]
    rh = ratings.get(home, forca_inicial(home)) + ajuste_home - desfalques_home * 18
    ra = ratings.get(away, forca_inicial(away)) + ajuste_away - desfalques_away * 18

    # Ajustes por posição e forma (opcional)
    if posicoes:
        pos_h = posicoes.get(home, {}).get("posicao", 10)
        pos_a = posicoes.get(away, {}).get("posicao", 10)
        # Times mais bem colocados ganham ligeiro bônus
        bonus_pos_h = max(0, (16 - pos_h)) * 1.5
        bonus_pos_a = max(0, (16 - pos_a)) * 1.5
        rh += bonus_pos_h
        ra += bonus_pos_a
    if formas:
        pts_h, _ = calcular_pontos_forma(formas.get(home, []))
        pts_a, _ = calcular_pontos_forma(formas.get(away, []))
        # Momento: +1.5 por ponto nos últimos 5 jogos, comparado com a média (7.5)
        bonus_forma_h = (pts_h - 7.5) * 1.2
        bonus_forma_a = (pts_a - 7.5) * 1.2
        rh += bonus_forma_h
        ra += bonus_forma_a

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

# ----------------------------------------------------------------------
# Balanço 24h
# ----------------------------------------------------------------------
def calcular_balanco_24h(jogos):
    agora = datetime.now()
    limite = agora - timedelta(hours=24)
    encerrados = [j for j in jogos if j.get("completed") and j.get("data") and limite <= j["data"] <= agora]
    if not encerrados:
        return []
    todos_encerrados = sorted([j for j in jogos if j.get("completed") and j.get("data")], key=lambda x: x["data"])
    resultados = []
    ctx = {"ratings": {}, "stats": {}, "jogos": 0, "media_home": 0.0, "media_away": 0.0, "taxa_empate": 0.0}
    encerrados_24h_set = {j["id"] for j in encerrados}
    for jogo in todos_encerrados:
        if jogo["id"] in encerrados_24h_set:
            previsao = prever_jogo(jogo, ctx)
            gols = jogo["placar_home"] + jogo["placar_away"]
            acertos, erros = [], []
            if previsao["over25"] >= 0.5:
                if gols > 2.5: acertos.append("Over 2.5 gols")
                else: erros.append("Over 2.5 gols")
            else:
                if gols <= 2.5: acertos.append("Under 2.5 gols")
                else: erros.append("Under 2.5 gols")
            resultados.append({
                "jogo": f"{jogo['home']} {jogo['placar_home']} x {jogo['placar_away']} {jogo['away']}",
                "gols": gols,
                "previsao_over25": previsao["over25"],
                "acertos": acertos,
                "erros": erros,
            })
        home, away = jogo["home"], jogo["away"]
        gh, ga = int(jogo["placar_home"]), int(jogo["placar_away"])
        ctx["ratings"].setdefault(home, forca_inicial(home))
        ctx["ratings"].setdefault(away, forca_inicial(away))
        ctx["stats"].setdefault(home, novo_stats())
        ctx["stats"].setdefault(away, novo_stats())
        exp_home = 1 / (1 + 10 ** ((ctx["ratings"][away] - (ctx["ratings"][home] + 58)) / 400))
        real_home = 1.0 if gh > ga else 0.5 if gh == ga else 0.0
        delta = 22 * (real_home - exp_home)
        ctx["ratings"][home] += delta
        ctx["ratings"][away] -= delta
        ctx["stats"][home]["jogos"] += 1
        ctx["stats"][home]["gf"] += gh
        ctx["stats"][home]["ga"] += ga
        ctx["stats"][home]["home_j"] += 1
        ctx["stats"][home]["home_gf"] += gh
        ctx["stats"][home]["home_ga"] += ga
        ctx["stats"][away]["jogos"] += 1
        ctx["stats"][away]["gf"] += ga
        ctx["stats"][away]["ga"] += gh
        ctx["stats"][away]["away_j"] += 1
        ctx["stats"][away]["away_gf"] += ga
        ctx["stats"][away]["away_ga"] += gh
        ctx["jogos"] += 1
        if ctx["jogos"] > 0:
            total_h = sum(s["home_gf"] for s in ctx["stats"].values())
            ctx["media_home"] = total_h / ctx["jogos"]
            ctx["media_away"] = sum(s["away_ga"] for s in ctx["stats"].values()) / ctx["jogos"]
            empates = sum(1 for j2 in todos_encerrados if j2["data"] <= jogo["data"] and j2["placar_home"] == j2["placar_away"])
            ctx["taxa_empate"] = empates / ctx["jogos"]
    return resultados

# ----------------------------------------------------------------------
# Renderização
# ----------------------------------------------------------------------
def obter_finalizadores(time_nome):
    nt = normalizar(time_nome)
    return JOGADORES.get(nt, [])

def criar_jogo_manual(home, away):
    return {"id": "manual", "home": nome_limpo(home), "away": nome_limpo(away), "data_txt": "Manual",
            "status": "análise manual", "completed": False, "live": False, "placar_home": 0, "placar_away": 0}

def render_forma_bar(forma_lista):
    html = ""
    for r in forma_lista:
        cls = "form-v" if r == "V" else ("form-e" if r == "E" else "form-d")
        html += f"<span class='form-badge {cls}'>{r}</span>"
    return html

def render_card(jogo, r, posicoes, formas):
    home, away = jogo["home"], jogo["away"]
    pos_h = posicoes.get(home, {}).get("posicao", "?")
    pos_a = posicoes.get(away, {}).get("posicao", "?")
    forma_h = formas.get(home, [])
    forma_a = formas.get(away, [])

    # Determinar tendência (últimos 3 jogos)
    pts_h, _ = calcular_pontos_forma(forma_h[:3])
    pts_a, _ = calcular_pontos_forma(forma_a[:3])
    tendencia_h = "⬆️" if pts_h >= 6 else ("⬇️" if pts_h <= 1 else "➡️")
    tendencia_a = "⬆️" if pts_a >= 6 else ("⬇️" if pts_a <= 1 else "➡️")

    info_extra = f"""
    <div class="team-info">
        <span>🏠 {home}: {pos_h}º {tendencia_h}</span>
        <span>{render_forma_bar(forma_h)}</span>
    </div>
    <div class="team-info">
        <span>🏟️ {away}: {pos_a}º {tendencia_a}</span>
        <span>{render_forma_bar(forma_a)}</span>
    </div>
    """

    live = jogo.get("live", False)
    card_class = f"{r['classe']} live" if live else r["classe"]
    if live:
        placar = f" - {jogo['placar_home']} x {jogo['placar_away']} <span class='live-badge'>🔴 AO VIVO</span>"
    elif jogo.get("completed"):
        placar = f" - {jogo['placar_home']} x {jogo['placar_away']} (encerrado)"
    else:
        placar = ""
    mapa = {"Casa": home, "Fora": away, "Empate": "Empate"}
    riscos = ", ".join(r["riscos"]) if r["riscos"] else "baixo risco"
    st.markdown(
        f"""
        <div class="card {card_class}">
            <div class="card-title">{home} x {away}{placar}</div>
            {info_extra}
            <div class="muted">{jogo.get('data_txt', '')} | {jogo.get('status', '')}</div>
            <span class="pill">Vitória {home}: <strong>{pct(r['p_h'])}</strong></span>
            <span class="pill">Empate: <strong>{pct(r['p_d'])}</strong></span>
            <span class="pill">Vitória {away}: <strong>{pct(r['p_a'])}</strong></span>
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
    # Finalizadores
    if not jogo.get("completed"):
        finalizadores_home = obter_finalizadores(home)
        finalizadores_away = obter_finalizadores(away)
        if finalizadores_home or finalizadores_away:
            with st.expander(f"⚽ Prováveis finalizadores em {home} x {away}"):
                col1, col2 = st.columns(2)
                p_gol_home = 1 - poisson_pmf(0, r["lam_h"])
                p_gol_away = 1 - poisson_pmf(0, r["lam_a"])
                with col1:
                    st.markdown(f"**{home}** (prob. de gol: {pct(p_gol_home)})")
                    if finalizadores_home:
                        for nome, peso in finalizadores_home:
                            prob_jogador = p_gol_home * peso
                            st.markdown(f"- <span class='finisher-name'>{nome}</span> <span class='finisher-prob'>{pct(prob_jogador)}</span>", unsafe_allow_html=True)
                    else:
                        st.write("Sem dados de finalizadores")
                with col2:
                    st.markdown(f"**{away}** (prob. de gol: {pct(p_gol_away)})")
                    if finalizadores_away:
                        for nome, peso in finalizadores_away:
                            prob_jogador = p_gol_away * peso
                            st.markdown(f"- <span class='finisher-name'>{nome}</span> <span class='finisher-prob'>{pct(prob_jogador)}</span>", unsafe_allow_html=True)
                    else:
                        st.write("Sem dados de finalizadores")

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

# ----------------------------------------------------------------------
# Interface principal
# ----------------------------------------------------------------------
def main():
    st.markdown('<div class="hero"><h1>⚽ Analisador Esportivo Pro 10.3</h1><p>Com odds manuais, posição na liga e forma recente (dados gratuitos ESPN).</p></div>', unsafe_allow_html=True)

    with st.sidebar:
        st.header("Configuração")
        liga_nome = st.selectbox("Liga", list(LIGAS.keys()))
        liga_id = LIGAS[liga_nome]

        col1, col2 = st.columns(2)
        with col1:
            dias_passado = st.slider("Dias passados", 0, 30, 10)
        with col2:
            dias_futuro = st.slider("Dias futuros", 0, 7, 3)

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
                    st.session_state.jogo_manual = (jogo_manual, desf_home, desf_away)

        st.markdown("---")
        st.subheader("Odds manuais (copie da casa de apostas)")
        odd_input = st.text_input("Odd do palpite (ex: 2.10)")
        banca = st.number_input("Banca (R$)", 0.0, 100000.0, 1000.0, step=100.0)

    # Carregar dados
    with st.spinner("Buscando jogos, classificação e calculando previsões..."):
        jogos, logs = buscar_periodo(liga_id, dias_passado, dias_futuro)
        contexto = construir_contexto(jogos)

        # Classificação
        classif = buscar_classificacao(liga_id)

        # Calcular forma de cada time (últimos 5 jogos)
        formas = {}
        for j in jogos:
            for time in [j["home"], j["away"]]:
                tn = normalizar(time)
                if tn not in formas:
                    formas[tn] = calcular_forma(jogos, tn)

        todos_jogos = []
        for j in jogos:
            if not j.get("completed") or j.get("live"):
                desf_h, desf_a = 0, 0
                previsao = prever_jogo(j, contexto, posicoes=classif, formas=formas,
                                       desfalques_home=desf_h, desfalques_away=desf_a)
                todos_jogos.append((j, previsao))

        if st.session_state.jogo_manual:
            mj, mh, ma = st.session_state.jogo_manual
            previsao_m = prever_jogo(mj, contexto, posicoes=classif, formas=formas,
                                     desfalques_home=mh, desfalques_away=ma)
            todos_jogos.append((mj, previsao_m))

        if mostrar_ao_vivo:
            todos_jogos = [(j, p) for j, p in todos_jogos if j.get("live")]

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
        render_card(jogo, prev, classif, formas)
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

    # Balanço 24h
    st.header("📈 Balanço das últimas 24h")
    resultados_balanco = calcular_balanco_24h(jogos)
    if not resultados_balanco:
        st.info("Nenhum jogo encerrado nas últimas 24h.")
    else:
        total_acertos = sum(len(r["acertos"]) for r in resultados_balanco)
        total_erros = sum(len(r["erros"]) for r in resultados_balanco)
        st.markdown(f"**Acertos:** {total_acertos} | **Erros:** {total_erros} | **Total de jogos:** {len(resultados_balanco)}")
        table = "| Jogo | Gols | Previsão O/U 2.5 | Resultado |\n|------|------|--------------------|------------|\n"
        for r in resultados_balanco:
            previsao = "Over" if r["previsao_over25"] >= 0.5 else "Under"
            resultado = "✔ Acertou" if (previsao == "Over" and r["gols"] > 2.5) or (previsao == "Under" and r["gols"] <= 2.5) else "✘ Errou"
            table += f"| {r['jogo']} | {r['gols']} | {previsao} ({pct(r['previsao_over25'])}) | {resultado} |\n"
        st.markdown(table)
        st.caption("Dados de escanteios e cartões indisponíveis gratuitamente.")

    # Tabela resumo
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