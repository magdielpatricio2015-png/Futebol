import math
import re
import unicodedata
from datetime import datetime, timedelta
from textwrap import dedent

import requests
import streamlit as st


# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

st.set_page_config(
    page_title="Analisador Esportivo Pro 12.1",
    page_icon="⚽",
    layout="wide",
)


# ============================================================
# CONSTANTES
# ============================================================

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
HEADERS = {"User-Agent": "AnalisadorEsportivoPro/12.1"}

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
    dedent(
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
        """
    ),
    unsafe_allow_html=True,
)


# ============================================================
# SESSÃO
# ============================================================

if "historico" not in st.session_state:
    st.session_state.historico = []


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
                "placar": f"{placar(home)} - {placar(away)}",
                "data": dt,
                "data_txt": dt.strftime("%d/%m/%Y %H:%M") if dt else "Sem data",
                "status": status_type.get("description")
                or status_type.get("detail")
                or "Scheduled",
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

    return sorted(
        vistos.values(),
        key=lambda x: x.get("data") or datetime.max,
    ), logs


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

    return ELO_BASE - 200


def atualizar_contexto_com_jogo(ctx, jogo, posicoes=None, home_adv=DEFAULT_HOME_ADV):
    home, away = jogo["home"], jogo["away"]
    hk, ak = key_time(home), key_time(away)

    gh = int(jogo["placar_home"])
    ga = int(jogo["placar_away"])

    ctx["ratings"].setdefault(hk, forca_inicial(home, posicoes))
    ctx["ratings"].setdefault(ak, forca_inicial(away, posicoes))
    ctx["stats"].setdefault(hk, novo_stats())
    ctx["stats"].setdefault(ak, novo_stats())

    jogos_h = ctx["stats"][hk]["jogos"]
    jogos_a = ctx["stats"][ak]["jogos"]
    experiencia_media = (jogos_h + jogos_a) / 2

    k = clamp(22 - experiencia_media * 0.45, 10, 18)

    exp_home = 1 / (
        1 + 10 ** ((ctx["ratings"][ak] - (ctx["ratings"][hk] + home_adv)) / 400)
    )
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


def construir_contexto(jogos, posicoes=None, home_adv=DEFAULT_HOME_ADV):
    ctx = novo_contexto()
    encerrados = [j for j in jogos if j.get("completed")]

    for j in sorted(encerrados, key=lambda x: x.get("data") or datetime.min):
        atualizar_contexto_com_jogo(
            ctx,
            j,
            posicoes=posicoes,
            home_adv=home_adv,
        )

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

    jogos_time = sorted(
        jogos_time,
        key=lambda x: x.get("data") or datetime.min,
        reverse=True,
    )[:n]

    forma = []

    for j in jogos_time:
        if key_time(j["home"]) == time_normalizado:
            gf = int(j["placar_home"])
            ga = int(j["placar_away"])
        else:
            gf = int(j["placar_away"])
            ga = int(j["placar_home"])

        forma.append("V" if gf > ga else "E" if gf == ga else "D")

    return forma


def calcular_pontos_forma(forma):
    pts = sum(3 if r == "V" else 1 if r == "E" else 0 for r in forma)
    return pts, " ".join(forma)


def matriz_poisson(m_h, m_a, rho=DEFAULT_RHO_DC, diff_rating=0):
    mat = [
        [
            poisson_pmf(i, m_h) * poisson_pmf(j, m_a)
            for j in range(MAX_GOLS + 1)
        ]
        for i in range(MAX_GOLS + 1)
    ]

    if abs(diff_rating) < 150 and m_h > 0 and m_a > 0:
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


def calcular_cartoes_escanteios(m_h, m_a, p_empate, riscos):
    total_gols = m_h + m_a
    equilibrio = 1 - abs(m_h - m_a) / max(0.2, total_gols)
    classico = 0.45 if "clássico" in riscos else 0.0

    cartoes_total = clamp(
        3.2 + 1.25 * equilibrio + 0.75 * p_empate + classico,
        2.4,
        7.2,
    )

    cartoes_home = cartoes_total * clamp(
        0.49 + 0.06 * (m_a - m_h),
        0.38,
        0.62,
    )

    escanteios_total = clamp(
        7.1 + 1.2 * total_gols + 0.75 * equilibrio,
        6.0,
        13.5,
    )

    escanteios_home = escanteios_total * clamp(
        0.54 + 0.08 * (m_h - m_a),
        0.40,
        0.68,
    )

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
    home = jogo["home"]
    away = jogo["away"]

    hk = key_time(home)
    ak = key_time(away)

    rating_h = contexto["ratings"].get(hk, forca_inicial(home, posicoes))
    rating_a = contexto["ratings"].get(ak, forca_inicial(away, posicoes))

    if contexto["ratings"]:
        league_avg = sum(contexto["ratings"].values()) / len(contexto["ratings"])
    else:
        league_avg = ELO_BASE

    diff_rating = (rating_h + home_adv) - rating_a

    media_h_liga = contexto.get("media_home", 1.35)
    media_a_liga = contexto.get("media_away", 1.05)

    stats_h = contexto["stats"].get(hk, novo_stats())
    stats_a = contexto["stats"].get(ak, novo_stats())

    prior_jogos = 8

    fator_atk_h = clamp(rating_h / league_avg, 0.6, 1.6)
    fator_atk_a = clamp(rating_a / league_avg, 0.6, 1.6)
    fator_def_h = clamp(league_avg / rating_h, 0.6, 1.6)
    fator_def_a = clamp(league_avg / rating_a, 0.6, 1.6)

    atk_h = (
        stats_h["home_gf"] + prior_jogos * media_h_liga * fator_atk_h
    ) / max(1, stats_h["home_j"] + prior_jogos)

    def_a = (
        stats_a["away_ga"] + prior_jogos * media_h_liga * fator_def_a
    ) / max(1, stats_a["away_j"] + prior_jogos)

    def_h = (
        stats_h["home_ga"] + prior_jogos * media_a_liga * fator_def_h
    ) / max(1, stats_h["home_j"] + prior_jogos)

    atk_a = (
        stats_a["away_gf"] + prior_jogos * media_a_liga * fator_atk_a
    ) / max(1, stats_a["away_j"] + prior_jogos)

    m_h_base = atk_h * def_a / max(media_h_liga, 0.1)
    m_a_base = atk_a * def_h / max(media_a_liga, 0.1)

    fator_forma_h = 1.0
    fator_forma_a = 1.0

    if formas:
        pts_h, _ = calcular_pontos_forma(formas.get(hk, []))
        pts_a, _ = calcular_pontos_forma(formas.get(ak, []))

        fator_forma_h = 1 + (pts_h - 7.5) * 0.013
        fator_forma_a = 1 + (pts_a - 7.5) * 0.013

    fator_elo = 1 + diff_rating * 0.0008
    fator_elo = clamp(fator_elo, 0.65, 1.45)

    riscos = []

    if tuple(sorted([hk, ak])) in CLASSICOS:
        riscos.append("clássico")
        fator_elo = 1 + (fator_elo - 1) * 0.7

    m_h = m_h_base * fator_forma_h * fator_elo + ajuste_h + desf_h * 0.1
    m_a = m_a_base * fator_forma_a / fator_elo + ajuste_a + desf_a * 0.1

    m_h = max(0.3, m_h)
    m_a = max(0.2, m_a)

    mat = matriz_poisson(
        m_h,
        m_a,
        rho=DEFAULT_RHO_DC,
        diff_rating=diff_rating,
    )

    prob_home = sum(
        mat[i][j]
        for i in range(MAX_GOLS + 1)
        for j in range(MAX_GOLS + 1)
        if i > j
    )

    prob_away = sum(
        mat[i][j]
        for i in range(MAX_GOLS + 1)
        for j in range(MAX_GOLS + 1)
        if i < j
    )

    prob_empate = sum(
        mat[i][j]
        for i in range(MAX_GOLS + 1)
        for j in range(MAX_GOLS + 1)
        if i == j
    )

    prob_home_zero = sum(mat[0][j] for j in range(MAX_GOLS + 1))
    prob_away_zero = sum(mat[i][0] for i in range(MAX_GOLS + 1))
    prob_zero_zero = mat[0][0]

    prob_btts_yes = clamp(
        1 - prob_home_zero - prob_away_zero + prob_zero_zero,
        0.0,
        1.0,
    )

    prob_over25 = sum(
        mat[i][j]
        for i in range(MAX_GOLS + 1)
        for j in range(MAX_GOLS + 1)
        if i + j > 2
    )

    placares = [
        ((i, j), mat[i][j])
        for i in range(MAX_GOLS + 1)
        for j in range(MAX_GOLS + 1)
    ]
    placares.sort(key=lambda x: -x[1])
    placar_top = placares[0]

    extras = calcular_cartoes_escanteios(
        m_h,
        m_a,
        prob_empate,
        riscos,
    )

    return {
        "home": home,
        "away": away,
        "m_h": round(m_h, 3),
        "m_a": round(m_a, 3),
        "rating_h": round(rating_h, 1),
        "rating_a": round(rating_a, 1),
        "diff_rating": round(diff_rating, 1),
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


# ============================================================
# COMPONENTES DE LAYOUT
# ============================================================

def classificar_confianca(prob):
    if prob >= 0.62:
        return "Alta", "green"

    if prob >= 0.54:
        return "Média", "amber"

    return "Baixa", "red"


def melhor_mercado(pred):
    mercados = [
        ("Casa", pred["prob_home"], pred["fair_odd_home"]),
        ("Empate", pred["prob_empate"], pred["fair_odd_empate"]),
        ("Fora", pred["prob_away"], pred["fair_odd_away"]),
        ("BTTS", pred["prob_btts"], pred["fair_odd_btts"]),
        ("Over 2.5", pred["prob_over25"], pred["fair_odd_over25"]),
    ]

    return max(mercados, key=lambda x: x[1])


def render_forma(forma):
    if not forma:
        return "Sem dados"

    return "".join(
        f'<span class="form-badge form-{r.lower()}">{r}</span>'
        for r in forma
    )


def render_card_jogo(jogo, pred):
    mercado_nome, mercado_prob, mercado_odd = melhor_mercado(pred)
    confianca_txt, confianca_cor = classificar_confianca(mercado_prob)

    live_tag = '<span class="live-badge">AO VIVO</span>' if pred["live"] else ""
    live_class = "live" if pred["live"] else ""

    riscos = ", ".join(pred["riscos"]) if pred["riscos"] else "Sem alerta"

    placar_str = f"{pred['placar_provavel'][0][0]} - {pred['placar_provavel'][0][1]}"
    prob_placar = pred["placar_provavel"][1]

    forma_h = render_forma(pred["forma_h"])
    forma_a = render_forma(pred["forma_a"])

    cart = pred["cartoes"]

    html = f"""
<div class="pro-card {live_class}">
    <div class="pro-card-header">
        <div>
            <div class="match-title">
                {pred["home"]} vs {pred["away"]} {live_tag}
            </div>
            <div class="match-subtitle">
                📅 {jogo["data_txt"]} · {jogo.get("status", "")}
            </div>
        </div>

        <div class="confidence {confianca_cor}">
            Confiança {confianca_txt}
        </div>
    </div>

    <div class="market-highlight">
        Melhor mercado: <strong>{mercado_nome}</strong> ·
        Probabilidade {pct(mercado_prob)} ·
        Odd justa {mercado_odd:.2f}
    </div>

    <div class="prob-grid">
        <div>
            <span>Casa</span>
            <strong>{pct(pred["prob_home"])}</strong>
        </div>
        <div>
            <span>Empate</span>
            <strong>{pct(pred["prob_empate"])}</strong>
        </div>
        <div>
            <span>Fora</span>
            <strong>{pct(pred["prob_away"])}</strong>
        </div>
        <div>
            <span>BTTS</span>
            <strong>{pct(pred["prob_btts"])}</strong>
        </div>
        <div>
            <span>Over 2.5</span>
            <strong>{pct(pred["prob_over25"])}</strong>
        </div>
    </div>

    <div class="card-footer">
        🎯 Placar provável: <strong>{placar_str}</strong> ({pct(prob_placar)}) ·
        Gols esperados: <strong>{pred["m_h"]}</strong> x <strong>{pred["m_a"]}</strong>
        <br>
        🏠 Forma {pred["home"]}: {forma_h}
        <br>
        🚌 Forma {pred["away"]}: {forma_a}
        <br>
        <span class="pill">🟨 Cartões: {cart["cartoes_total"]:.1f}</span>
        <span class="pill">Over 3.5 cartões: {pct(cart["over_35_cartoes"])}</span>
        <span class="pill">⚽ Escanteios: {cart["escanteios_total"]:.1f}</span>
        <span class="pill">Over 9.5 escanteios: {pct(cart["over_95_escanteios"])}</span>
        <br>
        ⚠️ Risco: <strong>{riscos}</strong>
    </div>
</div>
"""

    st.markdown(dedent(html), unsafe_allow_html=True)


def montar_previsoes(futuros, contexto, posicoes, formas):
    previsoes = []

    for jogo in sorted(futuros, key=lambda x: x["data"]):
        pred = prever_jogo(
            jogo,
            contexto,
            posicoes=posicoes,
            formas=formas,
        )

        mercado_nome, mercado_prob, mercado_odd = melhor_mercado(pred)

        previsoes.append(
            {
                "jogo": jogo,
                "pred": pred,
                "mercado_nome": mercado_nome,
                "mercado_prob": mercado_prob,
                "mercado_odd": mercado_odd,
            }
        )

    return previsoes


# ============================================================
# INTERFACE PRINCIPAL
# ============================================================

def main():
    st.markdown(
        dedent(
            """
            <div class="hero">
                <h1>⚽ Analisador Esportivo Pro 12.1</h1>
                <p>Dashboard profissional de probabilidades, odds justas, risco e oportunidades.</p>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("⚙️ Configurações")

        liga_nome = st.selectbox(
            "🏆 Liga",
            list(LIGAS.keys()),
            index=0,
        )

        dias_passado = st.slider(
            "📅 Dias passados para contexto",
            14,
            90,
            30,
        )

        dias_futuro = st.slider(
            "⏩ Dias futuros para prever",
            1,
            14,
            7,
        )

        limite_oportunidade = st.slider(
            "🎯 Probabilidade mínima para oportunidade",
            0.50,
            0.75,
            0.55,
            0.01,
        )

        buscar = st.button(
            "🔍 Buscar e analisar",
            use_container_width=True,
        )

        st.caption("Fonte de dados: API pública da ESPN.")

    if not buscar:
        st.info("Configure a liga na lateral e clique em **Buscar e analisar**.")
        return

    liga_id = LIGAS[liga_nome]

    with st.spinner("Obtendo dados da ESPN e calculando previsões..."):
        jogos, logs = buscar_periodo(
            liga_id,
            dias_passado,
            dias_futuro,
        )

    if not jogos:
        st.warning("Nenhum jogo encontrado no período.")
        return

    torneio_sem_tabela = (
        "copa" in liga_id
        or "champions" in liga_id
        or "europa" in liga_id
        or "libertadores" in liga_id
        or "sudamericana" in liga_id
    )

    posicoes = {} if torneio_sem_tabela else buscar_classificacao(liga_id)

    contexto = construir_contexto(
        jogos,
        posicoes=posicoes,
    )

    formas = {}
    todos_times = set()

    for j in jogos:
        if j.get("completed"):
            todos_times.add(key_time(j["home"]))
            todos_times.add(key_time(j["away"]))

    for t in todos_times:
        formas[t] = calcular_forma(jogos, t)

    agora = datetime.now()

    futuros = [
        j for j in jogos
        if j.get("data")
        and j["data"] > agora
        and not j.get("completed")
    ]

    ao_vivo = [
        j for j in jogos
        if j.get("live")
    ]

    futuros = sorted(ao_vivo + futuros, key=lambda x: x["data"])

    if not futuros:
        st.info("Nenhum jogo futuro ou ao vivo encontrado.")
        return

    previsoes = montar_previsoes(
        futuros,
        contexto,
        posicoes,
        formas,
    )

    total_jogos = len(previsoes)
    total_ao_vivo = sum(1 for p in previsoes if p["pred"].get("live"))

    jogos_hoje = sum(
        1
        for p in previsoes
        if p["jogo"].get("data")
        and p["jogo"]["data"].date() == hoje()
    )

    oportunidades_qtd = sum(
        1
        for p in previsoes
        if p["mercado_prob"] >= limite_oportunidade
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Partidas analisadas", total_jogos)
    col2.metric("Jogos hoje", jogos_hoje)
    col3.metric("Ao vivo", total_ao_vivo)
    col4.metric("Oportunidades", oportunidades_qtd)

    st.success(
        f"Contexto calculado com {contexto['jogos']} jogos encerrados."
    )

    aba1, aba2, aba3 = st.tabs(
        [
            "📊 Painel",
            "🎯 Oportunidades",
            "⚙️ Modelo",
        ]
    )

    with aba1:
        st.markdown(
            dedent(
                """
                <div class="section-title">📊 Jogos analisados</div>
                """
            ),
            unsafe_allow_html=True,
        )

        for item in previsoes:
            render_card_jogo(
                item["jogo"],
                item["pred"],
            )

    with aba2:
        st.markdown(
            dedent(
                """
                <div class="section-title">🎯 Melhores oportunidades</div>
                """
            ),
            unsafe_allow_html=True,
        )

        oportunidades = [
            item for item in previsoes
            if item["mercado_prob"] >= limite_oportunidade
        ]

        oportunidades.sort(
            key=lambda x: x["mercado_prob"],
            reverse=True,
        )

        if not oportunidades:
            st.info("Nenhuma oportunidade acima do limite definido.")
        else:
            for item in oportunidades:
                render_card_jogo(
                    item["jogo"],
                    item["pred"],
                )

    with aba3:
        st.markdown(
            dedent(
                """
                <div class="section-title">⚙️ Diagnóstico do modelo</div>
                """
            ),
            unsafe_allow_html=True,
        )

        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Jogos no contexto", contexto["jogos"])
        c2.metric("Média gols casa", f"{contexto['media_home']:.2f}")
        c3.metric("Média gols fora", f"{contexto['media_away']:.2f}")
        c4.metric("Taxa de empate", pct(contexto["taxa_empate"]))

        st.write(
            {
                "Liga": liga_nome,
                "ID ESPN": liga_id,
                "Home advantage": DEFAULT_HOME_ADV,
                "Rho Dixon-Coles": DEFAULT_RHO_DC,
                "Máximo de gols na matriz": MAX_GOLS,
                "Times com rating calculado": len(contexto["ratings"]),
                "Times com estatísticas": len(contexto["stats"]),
            }
        )

        with st.expander("Ratings calculados"):
            if contexto["ratings"]:
                ratings_ordenados = sorted(
                    contexto["ratings"].items(),
                    key=lambda x: x[1],
                    reverse=True,
                )

                for time, rating in ratings_ordenados:
                    st.text(f"{time}: {rating:.1f}")
            else:
                st.info("Sem ratings calculados.")

        if logs:
            with st.expander("⚠️ Logs da API"):
                for log in logs:
                    st.text(log)


if __name__ == "__main__":
    main()