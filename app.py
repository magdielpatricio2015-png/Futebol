
import math
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

import pandas as pd
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

        status_type = event.get("status", {}).get("type", {})

        def placar(c):
            try:
                return int(c.get("score", 0))
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
    rho=DEFAULT_RHO_DC,
    usar_posicao=True,
    usar_forma=True,
):
    home, away = jogo["home"], jogo["away"]
    hk, ak = key_time(home), key_time(away)

    ratings = contexto["ratings"]
    stats = contexto["stats"]

    rh = ratings.get(hk, forca_inicial(home, posicoes)) + ajuste_h - desf_h * 16
    ra = ratings.get(ak, forca_inicial(away, posicoes)) + ajuste_a - desf_a * 16

    liga_h = contexto.get("media_home") or 1.35
    liga_a = contexto.get("media_away") or 1.05

    ataque_h = media_time(stats, home, "home_gf", liga_h)
    defesa_a = media_time(stats, away, "away_ga", liga_h)
    ataque_a = media_time(stats, away, "away_gf", liga_a)
    defesa_h = media_time(stats, home, "home_ga", liga_a)

    fator_pos_h = fator_pos_a = 1.0

    if usar_posicao and posicoes:
        pos_h = obter_posicao(posicoes, home, 10)
        pos_a = obter_posicao(posicoes, away, 10)

        # Peso pequeno para evitar dupla contagem com Elo e gols.
        fator_pos_h = clamp(1 + (10 - pos_h) * 0.008, 0.94, 1.06)
        fator_pos_a = clamp(1 + (10 - pos_a) * 0.008, 0.94, 1.06)

        ataque_h *= fator_pos_h
        ataque_a *= fator_pos_a

    fator_forma_h = fator_forma_a = 1.0

    if usar_forma and formas:
        forma_h = formas.get(hk, [])
        forma_a = formas.get(ak, [])

        if forma_h:
            pts_h, _ = calcular_pontos_forma(forma_h)
            fator_forma_h = clamp(1 + (pts_h - 7.5) * 0.008, 0.94, 1.06)

        if forma_a:
            pts_a, _ = calcular_pontos_forma(forma_a)
            fator_forma_a = clamp(1 + (pts_a - 7.5) * 0.008, 0.94, 1.06)

        ataque_h *= fator_forma_h
        ataque_a *= fator_forma_a

    # Modelo multiplicativo ataque/defesa relativo à média da liga.
    forca_ataque_h = ataque_h / max(0.25, liga_h)
    forca_defesa_a = defesa_a / max(0.25, liga_h)

    forca_ataque_a = ataque_a / max(0.25, liga_a)
    forca_defesa_h = defesa_h / max(0.25, liga_a)

    # Clamps evitam explosões em ligas ou times com poucos jogos.
    forca_ataque_h = clamp(forca_ataque_h, 0.55, 1.75)
    forca_defesa_a = clamp(forca_defesa_a, 0.55, 1.75)
    forca_ataque_a = clamp(forca_ataque_a, 0.55, 1.75)
    forca_defesa_h = clamp(forca_defesa_h, 0.55, 1.75)

    base_lam_h = liga_h * forca_ataque_h * forca_defesa_a
    base_lam_a = liga_a * forca_ataque_a * forca_defesa_h

    # Elo entra como ajuste suave, não como motor principal dos gols.
    elo_gap = clamp((rh - ra + home_adv) / 400, -1.2, 1.2)

    lam_h = clamp(base_lam_h * (1 + 0.08 * elo_gap), 0.30, 3.40)
    lam_a = clamp(base_lam_a * (1 - 0.08 * elo_gap), 0.25, 3.10)

    mat = matriz_poisson(lam_h, lam_a, rho=rho)

    p_h = sum(mat[i][j] for i in range(MAX_GOLS + 1) for j in range(MAX_GOLS + 1) if i > j)
    p_d = sum(mat[i][i] for i in range(MAX_GOLS + 1))
    p_a = sum(mat[i][j] for i in range(MAX_GOLS + 1) for j in range(MAX_GOLS + 1) if i < j)

    total = p_h + p_d + p_a
    p_h, p_d, p_a = p_h / total, p_d / total, p_a / total

    over15 = 1 - sum(
        mat[i][j]
        for i in range(MAX_GOLS + 1)
        for j in range(MAX_GOLS + 1)
        if i + j <= 1
    )

    over25 = 1 - sum(
        mat[i][j]
        for i in range(MAX_GOLS + 1)
        for j in range(MAX_GOLS + 1)
        if i + j <= 2
    )

    under35 = sum(
        mat[i][j]
        for i in range(MAX_GOLS + 1)
        for j in range(MAX_GOLS + 1)
        if i + j <= 3
    )

    btts = sum(
        mat[i][j]
        for i in range(1, MAX_GOLS + 1)
        for j in range(1, MAX_GOLS + 1)
    )

    placares = sorted(
        [(mat[i][j], i, j) for i in range(MAX_GOLS + 1) for j in range(MAX_GOLS + 1)],
        reverse=True,
    )[:5]

    riscos = []

    if tuple(sorted([hk, ak])) in CLASSICOS:
        riscos.append("clássico")

    amostra = stats.get(hk, {}).get("jogos", 0) + stats.get(ak, {}).get("jogos", 0)

    if amostra < 18:
        riscos.append("baixa amostra")

    if abs(p_h - p_a) < 0.08:
        riscos.append("forças próximas")

    if desf_h or desf_a:
        riscos.append(f"desfalques {home}:{desf_h} {away}:{desf_a}")

    probs = {
        "Casa": p_h,
        "Empate": p_d,
        "Fora": p_a,
    }

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

    score = int(
        clamp(
            35
            + prob_palpite * 34
            + melhor_prob * 14
            + min(amostra, 50) * 0.35
            - len(riscos) * 8,
            0,
            94,
        )
    )

    if amostra < 18:
        decisao, cor, classe = "Evitar", "red", "low"
    elif prob_palpite < 0.46 and melhor_prob < 0.68:
        decisao, cor, classe = "Evitar", "red", "low"
    elif score >= 78 and melhor_prob >= 0.66:
        decisao, cor, classe = "Apostar", "green", "good"
    elif score >= 64:
        decisao, cor, classe = "Cuidado", "amber", "medium"
    else:
        decisao, cor, classe = "Evitar", "red", "low"

    extras = calcular_cartoes_escanteios(lam_h, lam_a, p_d, riscos)

    return {
        "p_h": p_h,
        "p_d": p_d,
        "p_a": p_a,
        "lam_h": lam_h,
        "lam_a": lam_a,
        "over15": over15,
        "over25": over25,
        "under35": under35,
        "btts": btts,
        "placares": placares,
        "palpite": palpite,
        "prob_palpite": prob_palpite,
        "melhor_mercado": melhor_mercado,
        "melhor_prob": melhor_prob,
        "score": score,
        "decisao": decisao,
        "cor": cor,
        "classe": classe,
        "riscos": riscos,
        "amostra": amostra,
        "rh": rh,
        "ra": ra,
        "fator_pos_h": fator_pos_h,
        "fator_pos_a": fator_pos_a,
        "fator_forma_h": fator_forma_h,
        "fator_forma_a": fator_forma_a,
        **extras,
    }


# ============================================================
# MÉTRICAS DE BACKTEST
# ============================================================

def resultado_real_1x2(jogo):
    gh = int(jogo["placar_home"])
    ga = int(jogo["placar_away"])

    if gh > ga:
        return "Casa"

    if gh < ga:
        return "Fora"

    return "Empate"


def brier_1x2(prev, real):
    y_casa = 1 if real == "Casa" else 0
    y_empate = 1 if real == "Empate" else 0
    y_fora = 1 if real == "Fora" else 0

    return (
        (prev["p_h"] - y_casa) ** 2
        + (prev["p_d"] - y_empate) ** 2
        + (prev["p_a"] - y_fora) ** 2
    )


def log_loss_1x2(prev, real):
    prob = {
        "Casa": prev["p_h"],
        "Empate": prev["p_d"],
        "Fora": prev["p_a"],
    }[real]

    return -safe_log(prob)


def lucro_aposta_unidade(acertou, odd):
    return odd - 1 if acertou else -1


def backtest_jogos(
    jogos,
    posicoes=None,
    warmup=25,
    home_adv=DEFAULT_HOME_ADV,
    rho=DEFAULT_RHO_DC,
    usar_posicao=True,
    usar_forma=True,
    filtro_decisao="Todos",
):
    encerrados = sorted(
        [j for j in jogos if j.get("completed") and j.get("data")],
        key=lambda x: x["data"],
    )

    ctx = novo_contexto()
    passados = []
    linhas = []

    for idx, jogo in enumerate(encerrados):
        if ctx["jogos"] >= warmup:
            formas = {}
            for time in [jogo["home"], jogo["away"]]:
                kt = key_time(time)
                formas[kt] = calcular_forma(passados, kt, ate_data=jogo["data"])

            prev = prever_jogo(
                jogo,
                ctx,
                posicoes=posicoes,
                formas=formas,
                home_adv=home_adv,
                rho=rho,
                usar_posicao=usar_posicao,
                usar_forma=usar_forma,
            )

            if filtro_decisao == "Todos" or prev["decisao"] == filtro_decisao:
                real = resultado_real_1x2(jogo)
                acertou_1x2 = real == prev["palpite"]

                gols = int(jogo["placar_home"]) + int(jogo["placar_away"])
                real_over25 = gols > 2.5
                pick_over25 = prev["over25"] >= 0.50
                acertou_over25 = real_over25 == pick_over25

                odd_justa_palpite = odd_justa(prev["prob_palpite"])
                odd_justa_melhor = odd_justa(prev["melhor_prob"])

                # Simulação teórica: apostando em odd justa + margem.
                # Se usar odd justa exatamente, EV esperado é zero. Por isso simulamos
                # uma odd de mercado 5% acima da odd justa para medir seletividade.
                odd_simulada = odd_justa_palpite * 1.05
                lucro_1u = lucro_aposta_unidade(acertou_1x2, odd_simulada)

                linhas.append(
                    {
                        "Data": jogo["data"].strftime("%d/%m/%Y"),
                        "Jogo": f"{jogo['home']} x {jogo['away']}",
                        "Placar": f"{jogo['placar_home']}x{jogo['placar_away']}",
                        "Real": real,
                        "Palpite": prev["palpite"],
                        "Acertou 1X2": acertou_1x2,
                        "Prob. palpite": prev["prob_palpite"],
                        "Casa %": prev["p_h"],
                        "Empate %": prev["p_d"],
                        "Fora %": prev["p_a"],
                        "Over 2.5 %": prev["over25"],
                        "Pick Over 2.5": pick_over25,
                        "Real Over 2.5": real_over25,
                        "Acertou Over 2.5": acertou_over25,
                        "Gols": gols,
                        "Gols esp. casa": prev["lam_h"],
                        "Gols esp. fora": prev["lam_a"],
                        "Melhor mercado": prev["melhor_mercado"],
                        "Prob. melhor mercado": prev["melhor_prob"],
                        "Score": prev["score"],
                        "Decisão": prev["decisao"],
                        "Amostra": prev["amostra"],
                        "Brier": brier_1x2(prev, real),
                        "Log loss": log_loss_1x2(prev, real),
                        "Odd justa palpite": odd_justa_palpite,
                        "Odd simulada +5%": odd_simulada,
                        "Lucro 1u simulado": lucro_1u,
                        "Alertas": ", ".join(prev["riscos"]) if prev["riscos"] else "baixo risco",
                    }
                )

        atualizar_contexto_com_jogo(ctx, jogo, posicoes=posicoes, home_adv=home_adv)
        passados.append(jogo)

    return pd.DataFrame(linhas)


def resumo_backtest(df):
    if df.empty:
        return {}

    total = len(df)
    acertos_1x2 = int(df["Acertou 1X2"].sum())
    acertos_over = int(df["Acertou Over 2.5"].sum())

    return {
        "Jogos testados": total,
        "Acerto 1X2": acertos_1x2 / total,
        "Acerto Over 2.5": acertos_over / total,
        "Brier médio": df["Brier"].mean(),
        "Log loss médio": df["Log loss"].mean(),
        "ROI simulado 1u": df["Lucro 1u simulado"].sum() / total,
        "Lucro simulado": df["Lucro 1u simulado"].sum(),
        "Prob. média palpite": df["Prob. palpite"].mean(),
    }


def tabela_calibracao(df):
    if df.empty:
        return pd.DataFrame()

    tmp = df.copy()
    tmp["Faixa prob."] = pd.cut(
        tmp["Prob. palpite"],
        bins=[0, 0.40, 0.50, 0.60, 0.70, 0.80, 1.00],
        labels=["0-40%", "40-50%", "50-60%", "60-70%", "70-80%", "80-100%"],
        include_lowest=True,
    )

    cal = (
        tmp.groupby("Faixa prob.", observed=False)
        .agg(
            Jogos=("Jogo", "count"),
            Prob_media=("Prob. palpite", "mean"),
            Acerto_real=("Acertou 1X2", "mean"),
            Brier_medio=("Brier", "mean"),
            Lucro=("Lucro 1u simulado", "sum"),
        )
        .reset_index()
    )

    return cal


# ============================================================
# RENDERIZAÇÃO
# ============================================================

def render_forma_bar(forma_lista):
    html = ""

    for r in forma_lista:
        cls = "form-v" if r == "V" else ("form-e" if r == "E" else "form-d")
        html += f"<span class='form-badge {cls}'>{r}</span>"

    return html


def factor_str(valor):
    if valor > 1:
        return f"⬆️ {valor:.2f}"

    if valor < 1:
        return f"⬇️ {valor:.2f}"

    return "1.00"


def mapa_palpite(jogo, pred):
    mp = {"Casa": jogo["home"], "Fora": jogo["away"], "Empate": "Empate"}
    return mp.get(pred["palpite"], pred["palpite"])


def obter_finalizadores(time_nome):
    return JOGADORES.get(key_time(time_nome), [])


def criar_jogo_manual(home, away):
    return {
        "id": "manual",
        "home": nome_limpo(home),
        "away": nome_limpo(away),
        "data_txt": "Manual",
        "status": "análise manual",
        "completed": False,
        "live": False,
        "placar_home": 0,
        "placar_away": 0,
    }


def render_card(jogo, r, posicoes, formas):
    home, away = jogo["home"], jogo["away"]
    hk, ak = key_time(home), key_time(away)

    pos_h = obter_posicao(posicoes, home, "?")
    pos_a = obter_posicao(posicoes, away, "?")

    forma_h = formas.get(hk, [])
    forma_a = formas.get(ak, [])

    pts_h, _ = calcular_pontos_forma(forma_h[:3])
    pts_a, _ = calcular_pontos_forma(forma_a[:3])

    tend_h = "⬆️" if pts_h >= 6 else ("⬇️" if pts_h <= 1 else "➡️")
    tend_a = "⬆️" if pts_a >= 6 else ("⬇️" if pts_a <= 1 else "➡️")

    live = jogo.get("live", False)
    card_class = f"{r['classe']} live" if live else r["classe"]

    placar_str = ""

    if live:
        placar_str = f" - {jogo['placar_home']} x {jogo['placar_away']} <span class='live-badge'>🔴 AO VIVO</span>"
    elif jogo.get("completed"):
        placar_str = f" - {jogo['placar_home']} x {jogo['placar_away']} (encerrado)"

    riscos = ", ".join(r["riscos"]) if r["riscos"] else "baixo risco"

    html_card = f"""
    <div class="card {card_class}">
        <div class="card-title">{home} x {away}{placar_str}</div>

        <div class="team-info">
            <span>🏠 {home}: {pos_h}º {tend_h}</span>
            <span>{render_forma_bar(forma_h)}</span>
        </div>

        <div class="team-info">
            <span>🏟️ {away}: {pos_a}º {tend_a}</span>
            <span>{render_forma_bar(forma_a)}</span>
        </div>

        <div class="muted">{jogo.get('data_txt', '')} | {jogo.get('status', '')}</div>

        <span class="pill">Vitória {home}: <strong>{pct(r['p_h'])}</strong></span>
        <span class="pill">Empate: <strong>{pct(r['p_d'])}</strong></span>
        <span class="pill">Vitória {away}: <strong>{pct(r['p_a'])}</strong></span>
        <br>

        <span class="pill">Palpite: <strong>{mapa_palpite(jogo, r)}</strong></span>
        <span class="pill">Probabilidade: <strong>{pct(r['prob_palpite'])}</strong></span>
        <span class="pill">Melhor mercado: <strong>{r['melhor_mercado']} {pct(r['melhor_prob'])}</strong></span>
        <span class="pill">Placar provável: <strong>{r['placares'][0][1]}x{r['placares'][0][2]}</strong></span>
        <span class="pill">Gols esp.: <strong>{r['lam_h']:.2f} x {r['lam_a']:.2f}</strong></span>
        <br>

        <span class="pill">Over 1.5 gols: <strong>{pct(r['over15'])}</strong></span>
        <span class="pill">Over 2.5 gols: <strong>{pct(r['over25'])}</strong></span>
        <span class="pill">Under 3.5 gols: <strong>{pct(r['under35'])}</strong></span>
        <span class="pill">Ambas marcam: <strong>{pct(r['btts'])}</strong></span>
        <br>

        <span class="pill">Cartões esp.: <strong>{r['cartoes_total']:.1f}</strong></span>
        <span class="pill">Over 3.5 cartões: <strong>{pct(r['over_35_cartoes'])}</strong></span>
        <span class="pill">Escanteios esp.: <strong>{r['escanteios_total']:.1f}</strong></span>
        <span class="pill">Over 8.5 esc.: <strong>{pct(r['over_85_escanteios'])}</strong></span>
        <br>

        <span class="decision {r['cor']}">{r['decisao']}</span>
        <span class="pill">Score: <strong>{r['score']}/100</strong></span>
        <span class="pill">Amostra: <strong>{r['amostra']}</strong></span>
        <span class="pill">Alertas: <strong>{riscos}</strong></span>
    </div>
    """

    st.markdown(html_card, unsafe_allow_html=True)

    with st.expander("🔍 Ver detalhes do modelo"):
        st.markdown(
            f"""
**Fatores aplicados**

- Posição: `{home}` {factor_str(r['fator_pos_h'])}, `{away}` {factor_str(r['fator_pos_a'])}
- Forma recente: `{home}` {factor_str(r['fator_forma_h'])}, `{away}` {factor_str(r['fator_forma_a'])}
- Elo ajustado: `{home}` {r['rh']:.1f}, `{away}` {r['ra']:.1f}
- Gols esperados: `{home}` {r['lam_h']:.2f} vs `{away}` {r['lam_a']:.2f}
- Top placares: {", ".join([f"{i}x{j} ({pct(p)})" for p, i, j in r["placares"][:5]])}
"""
        )

    if not jogo.get("completed"):
        finalizadores_home = obter_finalizadores(home)
        finalizadores_away = obter_finalizadores(away)

        if finalizadores_home or finalizadores_away:
            with st.expander(f"⚽ Prováveis finalizadores em {home} x {away}"):
                col1, col2 = st.columns(2)

                p_gol_home = 1 - poisson_pmf(0, r["lam_h"])
                p_gol_away = 1 - poisson_pmf(0, r["lam_a"])

                with col1:
                    st.markdown(f"**{home}** — prob. gol do time: {pct(p_gol_home)}")
                    for nome, peso in finalizadores_home:
                        st.markdown(f"- {nome}: {pct(p_gol_home * peso)}")

                with col2:
                    st.markdown(f"**{away}** — prob. gol do time: {pct(p_gol_away)}")
                    for nome, peso in finalizadores_away:
                        st.markdown(f"- {nome}: {pct(p_gol_away * peso)}")


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


# ============================================================
# PÁGINAS
# ============================================================

def pagina_previsoes(
    liga_nome,
    liga_id,
    dias_passado,
    dias_futuro,
    home_adv,
    rho,
    usar_posicao,
    usar_forma,
    mostrar_ao_vivo,
    odd_input,
    banca,
):
    with st.spinner("Buscando dados e calculando previsões..."):
        jogos, logs = buscar_periodo(liga_id, dias_passado, dias_futuro)
        classif = buscar_classificacao(liga_id)

        contexto = construir_contexto(jogos, posicoes=classif, home_adv=home_adv)

        formas = {}
        for j in jogos:
            for time in [j["home"], j["away"]]:
                kt = key_time(time)
                if kt not in formas:
                    formas[kt] = calcular_forma(jogos, kt)

        todos_jogos = []

        for j in jogos:
            if not j.get("completed") or j.get("live"):
                prev = prever_jogo(
                    j,
                    contexto,
                    posicoes=classif,
                    formas=formas,
                    home_adv=home_adv,
                    rho=rho,
                    usar_posicao=usar_posicao,
                    usar_forma=usar_forma,
                )
                todos_jogos.append((j, prev))

        if st.session_state.jogo_manual:
            mj, mh, ma = st.session_state.jogo_manual
            prev_m = prever_jogo(
                mj,
                contexto,
                posicoes=classif,
                formas=formas,
                desf_h=mh,
                desf_a=ma,
                home_adv=home_adv,
                rho=rho,
                usar_posicao=usar_posicao,
                usar_forma=usar_forma,
            )
            todos_jogos.append((mj, prev_m))

        if mostrar_ao_vivo:
            todos_jogos = [(j, p) for j, p in todos_jogos if j.get("live")]

        todos_jogos.sort(key=lambda x: (not x[0].get("live"), x[0].get("data") or datetime.max))

    st.header(f"{'📺 Jogos ao vivo' if mostrar_ao_vivo else '📊 Previsões'} – {liga_nome} ({len(todos_jogos)} jogos)")

    if logs:
        with st.expander("Logs de erro"):
            for log in logs:
                st.warning(log)

    if not todos_jogos:
        st.info("Nenhum jogo encontrado para o filtro atual.")
        return

    for jogo, prev in todos_jogos:
        render_card(jogo, prev, classif, formas)

        try:
            odd = float(str(odd_input).replace(",", ".")) if odd_input else 0
        except Exception:
            odd = 0

        if odd > 0:
            prob = (
                prev["p_h"]
                if prev["palpite"] == "Casa"
                else (prev["p_a"] if prev["palpite"] == "Fora" else prev["p_d"])
            )

            mercado = (
                f"Vitória {jogo['home']}"
                if prev["palpite"] == "Casa"
                else (f"Vitória {jogo['away']}" if prev["palpite"] == "Fora" else "Empate")
            )

            render_value_box(f"{mercado} (Palpite)", prob, odd, banca)

    st.subheader("📋 Resumo dos mercados")

    df_resumo = pd.DataFrame(
        [
            {
                "Jogo": f"{j['home']} x {j['away']}",
                "Palpite": mapa_palpite(j, r),
                "Prob.": pct(r["prob_palpite"]),
                "Melhor mercado": r["melhor_mercado"],
                "Prob. mercado": pct(r["melhor_prob"]),
                "Over 2.5": pct(r["over25"]),
                "Ambas marcam": pct(r["btts"]),
                "Cartões esp.": round(r["cartoes_total"], 1),
                "Escanteios esp.": round(r["escanteios_total"], 1),
                "Score": r["score"],
                "Decisão": r["decisao"],
                "Amostra": r["amostra"],
            }
            for j, r in todos_jogos
        ]
    )

    st.dataframe(df_resumo, use_container_width=True)

    st.session_state.historico.extend(todos_jogos)

    st.subheader("📜 Histórico da sessão")

    hist_df = pd.DataFrame(
        [
            {
                "Data": j.get("data_txt"),
                "Jogo": f"{j['home']} x {j['away']}",
                "Palpite": mapa_palpite(j, r),
                "Prob.": pct(r["prob_palpite"]),
                "Score": r["score"],
                "Decisão": r["decisao"],
            }
            for j, r in st.session_state.historico
        ]
    )

    st.dataframe(hist_df.tail(30), use_container_width=True)


def pagina_backtest(
    liga_nome,
    liga_id,
    dias_backtest,
    warmup,
    home_adv,
    rho,
    usar_posicao,
    usar_forma,
    filtro_decisao,
):
    st.header(f"🧪 Backtest histórico – {liga_nome}")

    st.info(
        "O backtest percorre os jogos em ordem cronológica. Para cada jogo encerrado, "
        "o modelo só usa jogos anteriores àquela data. Depois prevê o jogo e atualiza o contexto com o resultado real."
    )

    with st.spinner("Buscando jogos históricos e rodando backtest..."):
        jogos, logs = buscar_periodo(liga_id, dias_backtest, 0)
        classif = buscar_classificacao(liga_id)

        df = backtest_jogos(
            jogos,
            posicoes=classif,
            warmup=warmup,
            home_adv=home_adv,
            rho=rho,
            usar_posicao=usar_posicao,
            usar_forma=usar_forma,
            filtro_decisao=filtro_decisao,
        )

    if logs:
        with st.expander("Logs de erro"):
            for log in logs:
                st.warning(log)

    if df.empty:
        st.warning("Não há jogos suficientes para backtest com esses filtros. Reduza o warmup ou aumente os dias.")
        return

    res = resumo_backtest(df)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Jogos testados", f"{res['Jogos testados']}")
    col2.metric("Acerto 1X2", pct(res["Acerto 1X2"]))
    col3.metric("Brier médio", f"{res['Brier médio']:.3f}")
    col4.metric("ROI simulado", pct(res["ROI simulado 1u"]))

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Acerto Over 2.5", pct(res["Acerto Over 2.5"]))
    col6.metric("Log loss médio", f"{res['Log loss médio']:.3f}")
    col7.metric("Lucro simulado", f"{res['Lucro simulado']:.2f}u")
    col8.metric("Prob. média", pct(res["Prob. média palpite"]))

    st.subheader("🎯 Calibração por faixa de probabilidade")

    cal = tabela_calibracao(df)

    if not cal.empty:
        cal_fmt = cal.copy()
        for c in ["Prob_media", "Acerto_real"]:
            cal_fmt[c] = cal_fmt[c].map(lambda x: pct(x) if pd.notna(x) else "")
        cal_fmt["Brier_medio"] = cal_fmt["Brier_medio"].map(lambda x: f"{x:.3f}" if pd.notna(x) else "")
        cal_fmt["Lucro"] = cal_fmt["Lucro"].map(lambda x: f"{x:.2f}u" if pd.notna(x) else "")
        st.dataframe(cal_fmt, use_container_width=True)

    st.subheader("📄 Jogos analisados")

    df_show = df.copy()

    percent_cols = [
        "Prob. palpite",
        "Casa %",
        "Empate %",
        "Fora %",
        "Over 2.5 %",
        "Prob. melhor mercado",
    ]

    for c in percent_cols:
        df_show[c] = df_show[c].map(pct)

    numeric_cols = [
        "Gols esp. casa",
        "Gols esp. fora",
        "Brier",
        "Log loss",
        "Odd justa palpite",
        "Odd simulada +5%",
        "Lucro 1u simulado",
    ]

    for c in numeric_cols:
        df_show[c] = df_show[c].map(lambda x: f"{x:.3f}")

    st.dataframe(df_show, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        "⬇️ Baixar backtest em CSV",
        data=csv,
        file_name=f"backtest_{liga_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
    )

    st.subheader("Como interpretar")

    st.markdown(
        """
- **Acerto 1X2** mostra quantas vezes o palpite principal venceu.
- **Brier Score** mede qualidade probabilística. Quanto menor, melhor.
- **Log loss** pune muito previsões confiantes que erram. Quanto menor, melhor.
- **Calibração** compara a probabilidade estimada com o acerto real. Exemplo: palpites de 60% deveriam acertar perto de 60%.
- **ROI simulado** não é lucro real. Ele simula uma aposta de 1 unidade usando uma odd 5% acima da odd justa do modelo.
"""
    )


# ============================================================
# MAIN
# ============================================================

def main():
    st.markdown(
        """
<div class="hero">
    <h1>⚽ Analisador Esportivo Pro 11.0</h1>
    <p>Modelo com Elo dinâmico, lambda multiplicativo, suavização, Dixon-Coles simplificado e backtest histórico.</p>
</div>
""",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("Configuração")

        modo = st.radio(
            "Modo",
            ["Previsões futuras/ao vivo", "Backtest jogos passados"],
            index=0,
        )

        liga_nome = st.selectbox("Liga", list(LIGAS.keys()))
        liga_id = LIGAS[liga_nome]

        st.markdown("---")
        st.subheader("Parâmetros do modelo")

        home_adv = st.slider("Vantagem casa Elo", 40, 100, DEFAULT_HOME_ADV, 5)
        rho = st.slider("Rho Dixon-Coles", -0.20, 0.05, DEFAULT_RHO_DC, 0.01)
        usar_posicao = st.checkbox("Usar posição na tabela", True)
        usar_forma = st.checkbox("Usar forma recente", True)

        st.markdown("---")

        if modo == "Previsões futuras/ao vivo":
            col1, col2 = st.columns(2)

            with col1:
                dias_passado = st.slider("Dias passados", 30, 180, 90)

            with col2:
                dias_futuro = st.slider("Dias futuros", 0, 14, 5)

            mostrar_ao_vivo = st.checkbox("🔴 Mostrar apenas jogos ao vivo")

            modo_manual = st.checkbox("Adicionar jogo manual")

            if modo_manual:
                with st.form("manual_form"):
                    home = st.text_input("Time da casa")
                    away = st.text_input("Time visitante")
                    desf_h = st.number_input("Desfalques casa", 0, 8, 0)
                    desf_a = st.number_input("Desfalques fora", 0, 8, 0)

                    if st.form_submit_button("Adicionar") and home and away:
                        st.session_state.jogo_manual = (criar_jogo_manual(home, away), desf_h, desf_a)

            st.markdown("---")
            odd_input = st.text_input("Odd do palpite, ex: 2.10")
            banca = st.number_input("Banca (R$)", 0.0, 100000.0, 1000.0, step=100.0)

        else:
            dias_backtest = st.slider("Dias para backtest", 30, 365, 180)
            warmup = st.slider("Warmup mínimo de jogos", 5, 80, 25)
            filtro_decisao = st.selectbox("Filtrar por decisão", ["Todos", "Apostar", "Cuidado", "Evitar"])

    if modo == "Previsões futuras/ao vivo":
        pagina_previsoes(
            liga_nome=liga_nome,
            liga_id=liga_id,
            dias_passado=dias_passado,
            dias_futuro=dias_futuro,
            home_adv=home_adv,
            rho=rho,
            usar_posicao=usar_posicao,
            usar_forma=usar_forma,
            mostrar_ao_vivo=mostrar_ao_vivo,
            odd_input=odd_input,
            banca=banca,
        )
    else:
        pagina_backtest(
            liga_nome=liga_nome,
            liga_id=liga_id,
            dias_backtest=dias_backtest,
            warmup=warmup,
            home_adv=home_adv,
            rho=rho,
            usar_posicao=usar_posicao,
            usar_forma=usar_forma,
            filtro_decisao=filtro_decisao,
        )


if __name__ == "__main__":
    main()
