import math
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

import requests
import streamlit as st


# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

st.set_page_config(
    page_title="Analisador Esportivo Pro 11.0",
    page_icon="⚽",
    layout="wide",
)


# ============================================================
# CONSTANTES
# ============================================================

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
HEADERS = {"User-Agent": "AnalisadorEsportivoPro/11.0"}
MAX_GOLS = 10
RETRIES = 2

# Ajustes centrais do modelo
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


# ============================================================
# ESTILO
# ============================================================

st.markdown(
    """
<style>
    .main { background-color: #ffffff; color: #111827; }
    .block-container { padding-top: 1rem; max-width: 1500px; }
    section[data-testid="stSidebar"] { background: #f1f5f9; }

    .hero {
        border: 1px solid #d7dce2;
        background: #f8fafc;
        border-radius: 10px;
        padding: 18px 20px;
        margin-bottom: 16px;
    }

    .hero h1 {
        margin: 0;
        font-size: 2rem;
        color: #111827;
    }

    .hero p {
        margin: 6px 0 0;
        color: #475569;
    }

    .card {
        border: 1px solid #d7dce2;
        border-radius: 10px;
        padding: 14px 16px;
        margin: 10px 0;
        background: #ffffff;
    }

    .card.good { border-left: 7px solid #16a34a; }
    .card.medium { border-left: 7px solid #eab308; }
    .card.low { border-left: 7px solid #dc2626; }
    .card.live { border-left: 7px solid #2563eb; }

    .card-title {
        font-size: 1.15rem;
        font-weight: 800;
        margin-bottom: 6px;
    }

    .muted {
        color: #64748b;
        font-size: .88rem;
    }

    .pill {
        display: inline-block;
        padding: 4px 9px;
        margin: 4px 5px 0 0;
        border-radius: 7px;
        background: #eef2f7;
        border: 1px solid #d7dce2;
        font-size: .88rem;
    }

    .pill strong { color: #111827; }

    .decision {
        display: inline-block;
        padding: 6px 10px;
        margin: 8px 6px 0 0;
        border-radius: 7px;
        color: white;
        font-weight: 800;
    }

    .decision.green { background: #16a34a; }
    .decision.amber { background: #ca8a04; }
    .decision.red { background: #dc2626; }

    .form-badge {
        display: inline-block;
        width: 22px;
        height: 22px;
        line-height: 22px;
        text-align: center;
        border-radius: 5px;
        font-size: 0.8rem;
        font-weight: bold;
        margin-right: 2px;
    }

    .form-v { background: #16a34a; color: white; }
    .form-e { background: #eab308; color: white; }
    .form-d { background: #dc2626; color: white; }

    .live-badge {
        background: #dc2626;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.8rem;
        margin-left: 8px;
    }

    .team-info {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 6px;
        color: #475569;
    }
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# SESSÃO
# ============================================================

if "historico" not in st.session_state:
    st.session_state.historico = []

if "jogo_manual" not in st.session_state:
    st.session_state.jogo_manual = None


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


def valor_esperado(prob, odd):
    return prob * odd - 1 if odd > 1 else 0


def kelly_stake(prob, odd, banca, fracao=0.25):
    if odd <= 1 or banca <= 0:
        return 0.0

    b = odd - 1
    q = 1 - prob
    kelly = ((b * prob - q) / b)

    return max(0.0, kelly * fracao * banca)


def safe_log(x):
    return math.log(max(x, 1e-12))


# ============================================================
# API ESPN
# ============================================================

def fetch_with_retry(url, params=None, retries=RETRIES):
    ultimo_erro = ""

    for i in range(retries):
        try:
            resp = requests.get(url, params=params or {}, headers=HEADERS, timeout=12)
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

        home = next((c for c in competidores if c.get("homeAway") == "home"), competidores[0])
        away = next((c for c in competidores if c.get("homeAway") == "away"), competidores[1])

        # CORREÇÃO: status pode ser None
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
                "placar": f"{placar(home)} - {placar(away)}",
                "data": dt,
                "data_txt": dt.strftime("%d/%m/%Y %H:%M") if dt else "Sem data",
                "status": status_type.get("description") or status_type.get("detail") or "Scheduled",
                "state": status_type.get("state", ""),
                "completed": bool(status_type.get("completed", False)),
                "live": status_type.get("state", "") == "in",
            }
        )

    return jogos


@st.cache_data(ttl=900, show_spinner=False)
def buscar_periodo(liga_id, dias_passado, dias_futuro):
    jogos = []
    logs = []

    inicio = hoje() - timedelta(days=dias_passado)
    fim = hoje() + timedelta(days=dias_futuro)
    dia = inicio

    while dia <= fim:
        payload, erro = buscar_scoreboard(liga_id, dia.isoformat())

        if erro:
            logs.append(f"{dia.isoformat()}: {erro}")

        jogos.extend(extrair_jogos(payload, liga_id))
        dia += timedelta(days=1)

    vistos = {}

    for j in jogos:
        key = (j.get("id") or "", j["home"], j["away"], j["data_txt"])
        vistos[key] = j

    return sorted(vistos.values(), key=lambda x: x.get("data") or datetime.max), logs


# ============================================================
# MODELO
# ============================================================

def novo_stats():
    return {
        "jogos": 0,
        "gf": 0.0,
        "ga": 0.0,
        "home_gf": 0.0,
        "home_ga": 0.0,
        "home_j": 0,
        "away_gf": 0.0,
        "away_ga": 0.0,
        "away_j": 0,
    }


def obter_posicao(posicoes, time, padrao=10):
    if not posicoes:
        return padrao

    dados = posicoes.get(key_time(time))

    if not dados:
        return padrao

    return dados.get("posicao", padrao)


def forca_inicial(time, posicoes=None):
    nt = key_time(time)

    if posicoes:
        pos = obter_posicao(posicoes, time, padrao=None)

        if pos is not None:
            return 1850 - (pos - 1) * 22

    for nome, valor in FORCA_BASE.items():
        if key_time(nome) == nt:
            return 1650 + valor * 2

    seed = sum(ord(c) for c in nome_limpo(time))
    return ELO_BASE + (seed % 160) - 80


def media_time(stats, time, campo, padrao, prior=8):
    s = stats.get(key_time(time))

    if not s:
        return padrao

    if campo == "home_gf":
        n = s["home_j"]
        valor = s["home_gf"]
    elif campo == "home_ga":
        n = s["home_j"]
        valor = s["home_ga"]
    elif campo == "away_gf":
        n = s["away_j"]
        valor = s["away_gf"]
    elif campo == "away_ga":
        n = s["away_j"]
        valor = s["away_ga"]
    else:
        return padrao

    return (valor + prior * padrao) / max(1, n + prior)


def atualizar_contexto_com_jogo(ctx, jogo, posicoes=None, home_adv=DEFAULT_HOME_ADV):
    home, away = jogo["home"], jogo["away"]
    hk, ak = key_time(home), key_time(away)

    gh, ga = int(jogo["placar_home"]), int(jogo["placar_away"])

    ctx["ratings"].setdefault(hk, forca_inicial(home, posicoes))
    ctx["ratings"].setdefault(ak, forca_inicial(away, posicoes))
    ctx["stats"].setdefault(hk, novo_stats())
    ctx["stats"].setdefault(ak, novo_stats())

    jogos_h = ctx["stats"][hk]["jogos"]
    jogos_a = ctx["stats"][ak]["jogos"]
    experiencia_media = (jogos_h + jogos_a) / 2

    # K dinâmico: aprende mais no começo e estabiliza depois.
    k = clamp(22 - experiencia_media * 0.45, 10, 18)

    exp_home = 1 / (1 + 10 ** ((ctx["ratings"][ak] - (ctx["ratings"][hk] + home_adv)) / 400))
    real_home = 1.0 if gh > ga else 0.5 if gh == ga else 0.0

    delta = k * (real_home - exp_home)

    ctx["ratings"][hk] += delta
    ctx["ratings"][ak] -= delta

    for tk, gf, ga_val, is_home in [
        (hk, gh, ga, True),
        (ak, ga, gh, False),
    ]:
        st_team = ctx["stats"][tk]
        st_team["jogos"] += 1
        st_team["gf"] += gf
        st_team["ga"] += ga_val

        if is_home:
            st_team["home_j"] += 1
            st_team["home_gf"] += gf
            st_team["home_ga"] += ga_val
        else:
            st_team["away_j"] += 1
            st_team["away_gf"] += gf
            st_team["away_ga"] += ga_val

    ctx["jogos"] += 1
    ctx["total_home_gols"] += gh
    ctx["total_away_gols"] += ga
    ctx["empates"] += 1 if gh == ga else 0

    ctx["media_home"] = ctx["total_home_gols"] / max(1, ctx["jogos"])
    ctx["media_away"] = ctx["total_away_gols"] / max(1, ctx["jogos"])
    ctx["taxa_empate"] = ctx["empates"] / max(1, ctx["jogos"])

    return ctx


def novo_contexto():
    return {
        "ratings": {},
        "stats": {},
        "jogos": 0,
        "total_home_gols": 0.0,
        "total_away_gols": 0.0,
        "empates": 0,
        "media_home": 1.35,
        "media_away": 1.05,
        "taxa_empate": 0.26,
    }


def construir_contexto(jogos, posicoes=None, home_adv=DEFAULT_HOME_ADV):
    ctx = novo_contexto()
    encerrados = [j for j in jogos if j.get("completed")]

    for j in sorted(encerrados, key=lambda x: x.get("data") or datetime.min):
        atualizar_contexto_com_jogo(ctx, j, posicoes=posicoes, home_adv=home_adv)

    return ctx


def calcular_forma(jogos, time_normalizado, ate_data=None, n=5):
    jogos_time = []

    for j in jogos:
        if not j.get("completed"):
            continue

        if ate_data and j.get("data") and j["data"] >= ate_data:
            continue

        if key_time(j["home"]) == time_normalizado or key_time(j["away"]) == time_normalizado:
            jogos_time.append(j)

    jogos_time = sorted(jogos_time, key=lambda x: x.get("data") or datetime.min, reverse=True)[:n]

    forma = []

    for j in jogos_time:
        if key_time(j["home"]) == time_normalizado:
            gf, ga = int(j["placar_home"]), int(j["placar_away"])
        else:
            gf, ga = int(j["placar_away"]), int(j["placar_home"])

        forma.append("V" if gf > ga else ("E" if gf == ga else "D"))

    return forma


def calcular_pontos_forma(forma):
    pts = sum(3 if r == "V" else (1 if r == "E" else 0) for r in forma)
    return pts, " ".join(forma)


def matriz_poisson(m_h, m_a, rho=DEFAULT_RHO_DC):
    mat = [
        [
            poisson_pmf(i, m_h) * poisson_pmf(j, m_a)
            for j in range(MAX_GOLS + 1)
        ]
        for i in range(MAX_GOLS + 1)
    ]

    # Dixon-Coles simplificado: corrige correlação em placares baixos.
    if m_h > 0 and m_a > 0:
        ajustes = {
            (0, 0): 1 - (m_h * m_a * rho),
            (0, 1): 1 + (m_h * rho),
            (1, 0): 1 + (m_a * rho),
            (1, 1): 1 - rho,
        }

        for (i, j), fator in ajustes.items():
            mat[i][j] *= max(0.01, fator)

    total = sum(sum(row) for row in mat) or 1

    return [
        [
            max(0.0, p / total)
            for p in row
        ]
        for row in mat
    ]


def prob_over_poisson(media, linha):
    corte = int(math.floor(linha))
    return clamp(1 - sum(poisson_pmf(k, media) for k in range(corte + 1)), 0.0, 1.0)


def calcular_cartoes_escanteios(m_h, m_a, p_empate, riscos):
    total_gols = m_h + m_a
    equilibrio = 1 - abs(m_h - m_a) / max(0.2, total_gols)
    classico = 0.45 if "clássico" in riscos else 0.0

    cartoes_total = clamp(3.2 + 1.25 * equilibrio + 0.75 * p_empate + classico, 2.4, 7.2)
    cartoes_home = cartoes_total * clamp(0.49 + 0.06 * (m_a - m_h), 0.38, 0.62)

    escanteios_total = clamp(7.1 + 1.2 * total_gols + 0.75 * equilibrio, 6.0, 13.5)
    escanteios_home = escanteios_total * clamp(0.54 + 0.08 * (m_h - m_a), 0.40, 0.68)

    return {
        "cartoes_total": cartoes_total,
        "cartoes_home": cartoes_home,
        "cartoes_away": cartoes_total - cartoes_home,
        "over_25_cartoes": prob_over_poisson(cartoes_total, 2.5),
        "over_35_cartoes": prob_over_poisson(cartoes_total, 3.5),
        "over_45_cartoes": prob_over_poisson(cartoes_total, 4.5),
        "escanteios_total": escanteios_total,
        "escanteios_home": escanteios_home,
        "escanteios_away": escanteios_total - escanteios_home,
        "over_75_escanteios": prob_over_poisson(escanteios_total, 7.5),
        "over_85_escanteios": prob_over_poisson(escanteios_total, 8.5),
        "over_95_escanteios": prob_over_poisson(escanteios_total, 9.5),
        "over_105_escanteios": prob_over_poisson(escanteios_total, 10.5),
    }


def prever_jogo(
    jogo,
    contexto,
    posicoes=None,
    formas=None,
    desf_h=0,
    desf_a=0,
    ajuste_h=0,
    ajuste_a=0,
    home_adv=DEFAULT_HOME_ADV,
):
    """Calcula probabilidades e métricas para uma partida."""
    home, away = jogo["home"], jogo["away"]
    hk, ak = key_time(home), key_time(away)

    # 1. Ratings Elo
    rating_h = contexto["ratings"].get(hk, forca_inicial(home, posicoes))
    rating_a = contexto["ratings"].get(ak, forca_inicial(away, posicoes))
    diff = (rating_h + home_adv) - rating_a

    # 2. Médias base da liga
    media_h_liga = contexto.get("media_home", 1.35)
    media_a_liga = contexto.get("media_away", 1.05)

    # 3. Estatísticas específicas de cada time (com prior bayesiano)
    stats_h = contexto["stats"].get(hk, novo_stats())
    stats_a = contexto["stats"].get(ak, novo_stats())

    prior_jogos = 8
    atk_h = (stats_h["home_gf"] + prior_jogos * media_h_liga) / max(1, stats_h["home_j"] + prior_jogos)
    def_a = (stats_a["away_ga"] + prior_jogos * media_h_liga) / max(1, stats_a["away_j"] + prior_jogos)
    def_h = (stats_h["home_ga"] + prior_jogos * media_a_liga) / max(1, stats_h["home_j"] + prior_jogos)
    atk_a = (stats_a["away_gf"] + prior_jogos * media_a_liga) / max(1, stats_a["away_j"] + prior_jogos)

    # 4. Médias Poisson base (método de decomposição ataque/defesa)
    m_h_base = atk_h * def_a / media_h_liga
    m_a_base = atk_a * def_h / media_a_liga

    # 5. Ajuste por forma recente (últimos 5 jogos)
    fator_forma_h = 1.0
    fator_forma_a = 1.0
    if formas:
        pts_h, _ = calcular_pontos_forma(formas.get(hk, []))
        pts_a, _ = calcular_pontos_forma(formas.get(ak, []))
        fator_forma_h = 1 + (pts_h - 7.5) * 0.013
        fator_forma_a = 1 + (pts_a - 7.5) * 0.013

    # 6. Ajuste por força Elo (diferença afeta total de gols)
    fator_elo = 1 + diff * 0.0008

    # 7. Ajuste extra por clássicos
    riscos = []
    if tuple(sorted([hk, ak])) in CLASSICOS:
        riscos.append("clássico")
        fator_elo *= 0.7

    # 8. Aplicar ajustes
    m_h = m_h_base * fator_forma_h * fator_elo + ajuste_h + desf_h * 0.1
    m_a = m_a_base * fator_forma_a / fator_elo + ajuste_a + desf_a * 0.1

    # Garantir mínimo de gols esperados
    m_h = max(0.3, m_h)
    m_a = max(0.2, m_a)

    # 9. Matriz de probabilidades (Poisson + Dixon-Coles)
    mat = matriz_poisson(m_h, m_a)

    # Probabilidades 1X2
    prob_home = sum(mat[i][j] for i in range(MAX_GOLS+1) for j in range(MAX_GOLS+1) if i > j)
    prob_away = sum(mat[i][j] for i in range(MAX_GOLS+1) for j in range(MAX_GOLS+1) if i < j)
    prob_empate = sum(mat[i][j] for i in range(MAX_GOLS+1) for j in range(MAX_GOLS+1) if i == j)

    # Ambas marcam (BTTS)
    prob_btts_no = mat[0][0]
    prob_btts_yes = 1 - prob_btts_no

    # Over 2.5 gols
    prob_over25 = sum(mat[i][j] for i in range(MAX_GOLS+1) for j in range(MAX_GOLS+1) if i+j > 2)

    # Placar exato mais provável
    placares = [
        ((i, j), mat[i][j])
        for i in range(MAX_GOLS+1) for j in range(MAX_GOLS+1)
    ]
    placares.sort(key=lambda x: -x[1])
    placar_top = placares[0]

    # Cartões e escanteios
    extras = calcular_cartoes_escanteios(m_h, m_a, prob_empate, riscos)

    resultado = {
        "home": home,
        "away": away,
        "m_h": round(m_h, 3),
        "m_a": round(m_a, 3),
        "prob_home": prob_home,
        "prob_empate": prob_empate,
        "prob_away": prob_away,
        "prob_btts": prob_btts_yes,
        "prob_over25": prob_over25,
        "placar_provavel": placar_top,
        "forma_h": formas.get(hk, []) if formas else [],
        "forma_a": formas.get(ak, []) if formas else [],
        "cartoes": extras,
        "riscos": riscos,
        "fair_odd_home": odd_justa(prob_home),
        "fair_odd_empate": odd_justa(prob_empate),
        "fair_odd_away": odd_justa(prob_away),
        "fair_odd_over25": odd_justa(prob_over25),
        "fair_odd_btts": odd_justa(prob_btts_yes),
        "live": jogo.get("live", False),
        "status": jogo.get("status", ""),
        "data": jogo.get("data"),
    }
    return resultado


# ============================================================
# INTERFACE STREAMLIT
# ============================================================

def main():
    st.markdown('<div class="hero"><h1>⚽ Analisador Esportivo Pro 11.0</h1><p>Previsões inteligentes baseadas em dados reais.</p></div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        liga_nome = st.selectbox("🏆 Liga", list(LIGAS.keys()), index=0)
    with col2:
        dias_passado = st.slider("📅 Dias passados p/ contexto", 14, 90, 30)
    with col3:
        dias_futuro = st.slider("⏩ Dias futuros a prever", 1, 14, 7)

    liga_id = LIGAS[liga_nome]

    if st.button("🔍 Buscar e analisar"):
        with st.spinner("Obtendo dados da ESPN..."):
            jogos, logs = buscar_periodo(liga_id, dias_passado, dias_futuro)

        if not jogos:
            st.warning("Nenhum jogo encontrado no período.")
            return

        # Classificação (para força inicial)
        posicoes = buscar_classificacao(liga_id) if "cop" not in liga_id and "champions" not in liga_id else {}

        # Contexto (aprende com jogos já encerrados)
        contexto = construir_contexto(jogos, posicoes=posicoes)

        # Forma dos times para os últimos 5 jogos (apenas encerrados)
        formas = {}
        todos_times = set()
        for j in jogos:
            if j.get("completed"):
                todos_times.add(key_time(j["home"]))
                todos_times.add(key_time(j["away"]))
        for t in todos_times:
            formas[t] = calcular_forma(jogos, t)

        # Separa jogos futuros / ao vivo
        agora = datetime.now()
        futuros = [j for j in jogos if j.get("data") and j["data"] > agora and not j.get("completed")]

        if not futuros:
            st.info("Nenhum jogo futuro ou ao vivo encontrado.")
            return

        st.success(f"🔎 {len(futuros)} partidas a prever | Contexto com {contexto['jogos']} jogos")

        for jogo in sorted(futuros, key=lambda x: x["data"]):
            pred = prever_jogo(jogo, contexto, posicoes=posicoes, formas=formas)

            # Exibição visual (cards)
            with st.container():
                live_tag = '<span class="live-badge">AO VIVO</span>' if pred["live"] else ""
                st.markdown(
                    f"""
                    <div class="card {'live' if pred['live'] else ''}">
                        <div class="card-title">{pred['home']} vs {pred['away']} {live_tag}</div>
                        <div class="team-info">
                            📅 {jogo['data_txt']} | {jogo.get('status','')}
                        </div>
                    """,
                    unsafe_allow_html=True,
                )

                colA, colB, colC = st.columns(3)
                with colA:
                    st.metric("Prob. Casa", pct(pred["prob_home"]))
                    st.metric("Fair Odd Casa", f"{pred['fair_odd_home']:.2f}")
                with colB:
                    st.metric("Prob. Empate", pct(pred["prob_empate"]))
                    st.metric("Fair Odd Empate", f"{pred['fair_odd_empate']:.2f}")
                with colC:
                    st.metric("Prob. Fora", pct(pred["prob_away"]))
                    st.metric("Fair Odd Fora", f"{pred['fair_odd_away']:.2f}")

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Ambas Marcam (BTTS)", pct(pred["prob_btts"]))
                    st.metric("Fair Odd BTTS", f"{pred['fair_odd_btts']:.2f}")
                with col2:
                    st.metric("Over 2.5 gols", pct(pred["prob_over25"]))
                    st.metric("Fair Odd Over 2.5", f"{pred['fair_odd_over25']:.2f}")

                # Placar mais provável
                placar_str = f"{pred['placar_provavel'][0][0]} - {pred['placar_provavel'][0][1]}"
                prob_placar = pred['placar_provavel'][1]
                st.caption(f"🎯 Placar mais provável: **{placar_str}** ({pct(prob_placar)})")

                # Forma recente
                if pred["forma_h"]:
                    badges = "".join(f'<span class="form-badge form-{r.lower()}">{r}</span>' for r in pred["forma_h"])
                    st.markdown(f"🏠 Forma {pred['home']}: {badges}", unsafe_allow_html=True)
                if pred["forma_a"]:
                    badges = "".join(f'<span class="form-badge form-{r.lower()}">{r}</span>' for r in pred["forma_a"])
                    st.markdown(f"🚌 Forma {pred['away']}: {badges}", unsafe_allow_html=True)

                # Cartões e escanteios
                cart = pred["cartoes"]
                st.markdown(
                    f"""
                    <div style="margin-top:6px;">
                        <span class="pill">🟨 Cartões total: {cart['cartoes_total']:.1f}</span>
                        <span class="pill">Over 3.5 cartões: {pct(cart['over_35_cartoes'])}</span>
                        <span class="pill">⚽ Escanteios total: {cart['escanteios_total']:.1f}</span>
                        <span class="pill">Over 9.5: {pct(cart['over_95_escanteios'])}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Riscos especiais
                if pred["riscos"]:
                    st.markdown(f"⚠️ **Fatores especiais:** {', '.join(pred['riscos'])}")

                st.markdown("</div>", unsafe_allow_html=True)  # fecha card
                st.write("---")

        # Log de erros (se houver)
        if logs:
            with st.expander("⚠️ Log de erros da API"):
                for l in logs:
                    st.text(l)


if __name__ == "__main__":
    main()