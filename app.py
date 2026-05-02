import html
import json
import math
import hashlib
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
import streamlit as st


# ============================================================
# CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="Analisador de Futebol Pro",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)

APP_TITLE = "⚽ Analisador de Futebol Pro"
TZ_BR = ZoneInfo("America/Sao_Paulo")

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
OPENLIGADB_BASE = "https://api.openligadb.de"

APP_USER = "Aposta"
APP_PASSWORD = "12345678senha"


# ============================================================
# ESTILO MOBILE
# ============================================================

st.markdown(
    """
    <style>
        .main .block-container {
            padding-top: 0.85rem;
            padding-left: 0.7rem;
            padding-right: 0.7rem;
            max-width: 1180px;
        }

        h1 {
            font-size: 1.7rem !important;
            margin-bottom: 0.4rem !important;
        }

        h2, h3 {
            margin-top: 0.5rem !important;
        }

        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 10px;
            box-shadow: 0 1px 6px rgba(15, 23, 42, 0.04);
        }

        div[data-testid="stMetricValue"] {
            font-size: 1.18rem;
        }

        div[data-testid="stMetricLabel"] {
            font-size: 0.78rem;
        }

        .top-box {
            border: 1px solid #dbeafe;
            background: #eff6ff;
            color: #0f172a;
            border-radius: 14px;
            padding: 12px;
            margin-bottom: 12px;
        }

        .match-card {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 14px;
            padding: 13px;
            margin-bottom: 10px;
            box-shadow: 0 2px 10px rgba(15, 23, 42, 0.06);
        }

        .match-title {
            font-size: 1.02rem;
            font-weight: 800;
            color: #0f172a;
            margin-top: 6px;
            line-height: 1.25;
        }

        .muted {
            color: #64748b;
            font-size: 0.84rem;
            line-height: 1.35;
        }

        .pill {
            display: inline-block;
            padding: 3px 9px;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 800;
            margin-right: 5px;
            background: #e0f2fe;
            color: #075985;
            vertical-align: middle;
        }

        .pill-live {
            background: #dcfce7;
            color: #166534;
        }

        .pill-post {
            background: #fee2e2;
            color: #991b1b;
        }

        .pill-warn {
            background: #fef3c7;
            color: #92400e;
        }

        .pill-ok {
            background: #dcfce7;
            color: #166534;
        }

        .pill-bad {
            background: #fee2e2;
            color: #991b1b;
        }

        .source {
            display: inline-block;
            padding: 2px 7px;
            border-radius: 999px;
            font-size: 0.68rem;
            font-weight: 700;
            background: #f1f5f9;
            color: #334155;
            margin-left: 3px;
        }

        .summary-box {
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 12px;
            background: #f8fafc;
            margin-bottom: 12px;
        }

        .diag-card {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 14px;
            padding: 12px;
            margin-bottom: 10px;
            box-shadow: 0 2px 10px rgba(15, 23, 42, 0.05);
        }

        .diag-title {
            font-weight: 800;
            color: #0f172a;
            font-size: 0.98rem;
            line-height: 1.25;
            margin-top: 5px;
        }

        @media (max-width: 640px) {
            .main .block-container {
                padding-left: 0.45rem;
                padding-right: 0.45rem;
            }

            h1 {
                font-size: 1.35rem !important;
            }

            .match-card,
            .diag-card,
            .top-box {
                padding: 10px;
                border-radius: 12px;
            }

            .match-title,
            .diag-title {
                font-size: 0.95rem;
            }

            div[data-testid="stMetric"] {
                padding: 8px;
            }

            div[data-testid="stMetricValue"] {
                font-size: 1rem;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# DADOS BASE
# ============================================================

COMPETICOES = {
    "Brasileirão Série A": {
        "espn": "bra.1",
        "openligadb": None,
        "tipo": "liga",
    },
    "Brasileirão Série B": {
        "espn": "bra.2",
        "openligadb": None,
        "tipo": "liga",
    },
    "Copa do Brasil": {
        "espn": "bra.copa_do_brasil",
        "openligadb": None,
        "tipo": "copa",
    },
    "Libertadores": {
        "espn": "conmebol.libertadores",
        "openligadb": None,
        "tipo": "copa",
    },
    "Premier League": {
        "espn": "eng.1",
        "openligadb": None,
        "tipo": "liga",
    },
    "La Liga": {
        "espn": "esp.1",
        "openligadb": None,
        "tipo": "liga",
    },
    "Bundesliga": {
        "espn": "ger.1",
        "openligadb": {
            "league": "bl1",
            "season": "2025",
        },
        "tipo": "liga",
    },
    "2. Bundesliga": {
        "espn": "ger.2",
        "openligadb": {
            "league": "bl2",
            "season": "2025",
        },
        "tipo": "liga",
    },
}

FORCA_TIMES = {
    "Flamengo": 86,
    "Palmeiras": 85,
    "Atlético-MG": 80,
    "Atletico Mineiro": 80,
    "Botafogo": 80,
    "São Paulo": 78,
    "Sao Paulo": 78,
    "Fluminense": 78,
    "Grêmio": 77,
    "Gremio": 77,
    "Internacional": 77,
    "Corinthians": 76,
    "Cruzeiro": 75,
    "Bahia": 74,
    "Athletico-PR": 74,
    "Vasco": 72,
    "Santos": 72,
    "Fortaleza": 72,
    "Ceará": 70,
    "Ceara": 70,
    "Vitória": 69,
    "Vitoria": 69,
    "Sport": 68,
    "Manchester City": 90,
    "Arsenal": 88,
    "Liverpool": 88,
    "Real Madrid": 89,
    "Barcelona": 87,
    "Atlético Madrid": 84,
    "Atletico Madrid": 84,
    "Bayern Munich": 88,
    "Bayern München": 88,
    "Borussia Dortmund": 82,
    "Bayer Leverkusen": 83,
    "RB Leipzig": 81,
}


# ============================================================
# HELPERS
# ============================================================

def br_now():
    return datetime.now(TZ_BR)


def br_today():
    return br_now().date()


def esc(value):
    return html.escape(str(value or ""), quote=True)


def fmt_data(data_iso):
    try:
        return datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return data_iso or "Sem data"


def pct(valor):
    return f"{valor * 100:.1f}%"


def normalizar_nome(nome):
    return " ".join(str(nome or "").strip().split())


def nivel_texto(prob):
    if prob >= 0.70:
        return "Alta"
    if prob >= 0.55:
        return "Boa"
    if prob >= 0.42:
        return "Média"
    return "Baixa"


def hash_forca_time(nome):
    nome = normalizar_nome(nome)

    if not nome:
        return 70

    if nome in FORCA_TIMES:
        return FORCA_TIMES[nome]

    nome_low = nome.lower()
    for chave, valor in FORCA_TIMES.items():
        chave_low = chave.lower()
        if chave_low in nome_low or nome_low in chave_low:
            return valor

    h = hashlib.sha256(nome.encode("utf-8")).hexdigest()
    n = int(h[:8], 16)
    return 64 + (n % 15)


def poisson_pmf(k, lam):
    if lam <= 0:
        return 0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def parse_data_hora_br(jogo):
    try:
        data = jogo.get("data") or ""
        hora = jogo.get("hora") or "00:00"
        return datetime.strptime(f"{data} {hora}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ_BR)
    except Exception:
        return None


# ============================================================
# LOGIN
# ============================================================

def check_login():
    if "logado" not in st.session_state:
        st.session_state.logado = False

    if st.session_state.logado:
        return

    st.title("🔐 Login")
    st.info("Entre para acessar o analisador.")

    user = st.text_input("Usuário", placeholder="Usuário")
    password = st.text_input("Senha", type="password", placeholder="Senha")
    entrar = st.button("Entrar", use_container_width=True)

    if entrar:
        if user.strip() == APP_USER and password.strip() == APP_PASSWORD:
            st.session_state.logado = True
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos.")

    st.stop()


# ============================================================
# ESPN
# ============================================================

def abrir_json(url, timeout=15):
    headers = {
        "User-Agent": "Mozilla/5.0 AnalisadorFutebolStreamlit/2.1",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw)


@st.cache_data(ttl=180, show_spinner=False)
def buscar_espn_scoreboard(slug, data_yyyymmdd):
    url = f"{ESPN_BASE}/{slug}/scoreboard?dates={data_yyyymmdd}&limit=300&region=br&lang=pt"

    try:
        return abrir_json(url), ""
    except urllib.error.HTTPError as e:
        return {}, f"ESPN HTTP {e.code}"
    except Exception as e:
        return {}, f"ESPN indisponível: {e}"


def extrair_jogos_espn(data):
    jogos = []
    eventos = data.get("events", []) if isinstance(data, dict) else []

    for ev in eventos:
        comp = (ev.get("competitions") or [{}])[0]
        status = comp.get("status") or ev.get("status") or {}
        status_type = status.get("type") or {}

        status_state = status_type.get("state", "")
        status_name = status_type.get("description") or status_type.get("shortDetail") or ""
        status_detail = status_type.get("detail") or ""

        dt_br = None
        try:
            dt_utc = datetime.fromisoformat(str(ev.get("date", "")).replace("Z", "+00:00"))
            dt_br = dt_utc.astimezone(TZ_BR)
        except Exception:
            pass

        casa = ""
        fora = ""
        placar_casa = None
        placar_fora = None

        for c in comp.get("competitors", []):
            team = c.get("team") or {}
            nome = (
                team.get("displayName")
                or team.get("shortDisplayName")
                or team.get("name")
                or "Time"
            )

            score = c.get("score")
            if score is not None:
                try:
                    score = int(score)
                except Exception:
                    pass

            if c.get("homeAway") == "home":
                casa = nome
                placar_casa = score
            elif c.get("homeAway") == "away":
                fora = nome
                placar_fora = score

        if not casa or not fora:
            continue

        jogos.append(
            {
                "id": str(ev.get("id", "")),
                "source": "ESPN",
                "nome": ev.get("name", f"{casa} x {fora}"),
                "casa": casa,
                "fora": fora,
                "placar_casa": placar_casa,
                "placar_fora": placar_fora,
                "data": dt_br.strftime("%Y-%m-%d") if dt_br else "",
                "hora": dt_br.strftime("%H:%M") if dt_br else "",
                "status_state": status_state,
                "status_name": status_name,
                "status_detail": status_detail,
            }
        )

    jogos.sort(key=lambda x: (x.get("data", ""), x.get("hora", "")))
    return jogos


def buscar_jogos_espn_periodo(slug, dias=3):
    todos = []
    logs = []
    hoje = br_today()

    for i in range(dias + 1):
        d = hoje + timedelta(days=i)
        data_key = d.strftime("%Y%m%d")
        data, erro = buscar_espn_scoreboard(slug, data_key)

        if erro:
            logs.append(f"{d.strftime('%d/%m')}: {erro}")
            continue

        todos.extend(extrair_jogos_espn(data))

    return deduplicar_jogos(todos), logs


def buscar_jogos_espn_ultimas_48h(slug):
    todos = []
    logs = []
    agora = br_now()
    inicio = agora - timedelta(hours=48)

    for offset in range(-2, 1):
        d = br_today() + timedelta(days=offset)
        data_key = d.strftime("%Y%m%d")
        data, erro = buscar_espn_scoreboard(slug, data_key)

        if erro:
            logs.append(f"{d.strftime('%d/%m')}: {erro}")
            continue

        for jogo in extrair_jogos_espn(data):
            dt = parse_data_hora_br(jogo)
            if not dt:
                continue
            if inicio <= dt <= agora and str(jogo.get("status_state", "")).lower() == "post":
                todos.append(jogo)

    return deduplicar_jogos(todos), logs


# ============================================================
# OPENLIGADB
# ============================================================

@st.cache_data(ttl=1800, show_spinner=False)
def openligadb_get_available_leagues():
    try:
        url = f"{OPENLIGADB_BASE}/getavailableleagues"
        response = requests.get(url, timeout=12)
        response.raise_for_status()
        return response.json()
    except Exception:
        return []


@st.cache_data(ttl=600, show_spinner=False)
def openligadb_get_matches(league, season):
    try:
        url = f"{OPENLIGADB_BASE}/getmatchdata/{league}/{season}"
        response = requests.get(url, timeout=12)
        response.raise_for_status()
        return response.json()
    except Exception:
        return []


def extrair_placar_openligadb(match):
    resultados = match.get("matchResults") or []

    if not resultados:
        return None, None

    preferidos = [
        "Endergebnis",
        "Ergebnis nach Verlängerung",
        "Nach Elfmeterschießen",
        "Halbzeitergebnis",
    ]

    for nome in preferidos:
        for r in resultados:
            if r.get("resultName") == nome:
                return r.get("pointsTeam1"), r.get("pointsTeam2")

    ordenados = sorted(
        resultados,
        key=lambda r: r.get("resultOrderID") or 0,
        reverse=True,
    )
    r = ordenados[0]
    return r.get("pointsTeam1"), r.get("pointsTeam2")


def processar_openligadb_matches(matches):
    jogos = []

    for match in matches:
        try:
            match_date = match.get("matchDateTime", "")
            dt_br = None

            if match_date:
                dt = datetime.fromisoformat(str(match_date).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=ZoneInfo("Europe/Berlin"))
                dt_br = dt.astimezone(TZ_BR)

            team1 = match.get("team1") or {}
            team2 = match.get("team2") or {}

            casa = team1.get("teamName", "Mandante")
            fora = team2.get("teamName", "Visitante")

            placar_casa, placar_fora = extrair_placar_openligadb(match)
            is_finished = bool(match.get("matchIsFinished", False))
            is_live = bool(match.get("matchIsLive", False))

            status_state = "pre"
            status_name = "Agendado"

            if is_live:
                status_state = "in"
                status_name = "Ao vivo"
            elif is_finished:
                status_state = "post"
                status_name = "Finalizado"

            jogos.append(
                {
                    "id": f"olg-{match.get('matchID', '')}",
                    "source": "OpenLigaDB",
                    "nome": f"{casa} x {fora}",
                    "casa": casa,
                    "fora": fora,
                    "placar_casa": int(placar_casa) if placar_casa is not None else None,
                    "placar_fora": int(placar_fora) if placar_fora is not None else None,
                    "data": dt_br.strftime("%Y-%m-%d") if dt_br else "",
                    "hora": dt_br.strftime("%H:%M") if dt_br else "",
                    "status_state": status_state,
                    "status_name": status_name,
                    "status_detail": match.get("group", {}).get("groupName", "") or status_name,
                    "league": match.get("leagueName", ""),
                    "season": match.get("leagueSeason", ""),
                }
            )
        except Exception:
            continue

    jogos.sort(key=lambda x: (x.get("data", ""), x.get("hora", "")))
    return jogos


def buscar_jogos_openligadb_periodo(config_openliga, dias=7):
    if not config_openliga:
        return [], "OpenLigaDB não configurada para esta competição."

    matches = openligadb_get_matches(
        config_openliga["league"],
        config_openliga["season"],
    )

    jogos = processar_openligadb_matches(matches)
    hoje = br_today()
    limite = hoje + timedelta(days=dias)

    filtrados = []
    for j in jogos:
        try:
            d = datetime.strptime(j["data"], "%Y-%m-%d").date()
            if hoje <= d <= limite or j.get("status_state") == "in":
                filtrados.append(j)
        except Exception:
            pass

    return filtrados, ""


def buscar_jogos_openligadb_ultimas_48h(config_openliga):
    if not config_openliga:
        return [], "OpenLigaDB não configurada para esta competição."

    matches = openligadb_get_matches(
        config_openliga["league"],
        config_openliga["season"],
    )

    jogos = processar_openligadb_matches(matches)
    agora = br_now()
    inicio = agora - timedelta(hours=48)

    filtrados = []
    for j in jogos:
        dt = parse_data_hora_br(j)
        if not dt:
            continue
        if inicio <= dt <= agora and str(j.get("status_state", "")).lower() == "post":
            filtrados.append(j)

    return filtrados, ""


# ============================================================
# DADOS UNIFICADOS
# ============================================================

def chave_jogo(jogo):
    casa = normalizar_nome(jogo.get("casa")).lower()
    fora = normalizar_nome(jogo.get("fora")).lower()
    data = jogo.get("data", "")
    return f"{data}|{casa}|{fora}"


def deduplicar_jogos(jogos):
    vistos = set()
    unicos = []

    for j in jogos:
        chave = j.get("id") or chave_jogo(j)
        if chave in vistos:
            continue
        vistos.add(chave)
        unicos.append(j)

    unicos.sort(key=lambda x: (x.get("data", ""), x.get("hora", "")))
    return unicos


def combinar_fontes(jogos_espn, jogos_openliga):
    por_chave = {}

    for j in jogos_openliga:
        por_chave[chave_jogo(j)] = j

    for j in jogos_espn:
        por_chave[chave_jogo(j)] = j

    return sorted(
        por_chave.values(),
        key=lambda x: (x.get("data", ""), x.get("hora", "")),
    )


def filtrar_jogos(jogos, filtro):
    hoje = br_today()
    amanha = hoje + timedelta(days=1)

    filtrados = []

    for j in jogos:
        data_txt = j.get("data", "")
        estado = str(j.get("status_state", "")).lower()

        try:
            data_jogo = datetime.strptime(data_txt, "%Y-%m-%d").date()
        except Exception:
            data_jogo = None

        if filtro == "Ao vivo" and estado == "in":
            filtrados.append(j)
        elif filtro == "Hoje" and data_jogo == hoje:
            filtrados.append(j)
        elif filtro == "Amanhã" and data_jogo == amanha:
            filtrados.append(j)
        elif filtro == "Próximos" and data_jogo and data_jogo >= hoje and estado != "post":
            filtrados.append(j)
        elif filtro == "Todos":
            filtrados.append(j)

    return filtrados


# ============================================================
# MODELO MATEMÁTICO
# ============================================================

def calcular_probabilidades(casa, fora, campo_neutro=False):
    casa = normalizar_nome(casa)
    fora = normalizar_nome(fora)

    forca_casa = hash_forca_time(casa)
    forca_fora = hash_forca_time(fora)

    vantagem_casa = 0 if campo_neutro else 4
    rating_casa = forca_casa + vantagem_casa
    rating_fora = forca_fora
    diferenca = rating_casa - rating_fora

    gols_casa = max(0.45, min(3.2, 1.35 + diferenca * 0.025))
    gols_fora = max(0.35, min(3.0, 1.08 - diferenca * 0.020))

    max_gols = 8
    p_casa = 0.0
    p_empate = 0.0
    p_fora = 0.0
    over_15 = 0.0
    over_25 = 0.0
    ambas_marcam = 0.0

    for i in range(max_gols + 1):
        for j in range(max_gols + 1):
            p = poisson_pmf(i, gols_casa) * poisson_pmf(j, gols_fora)

            if i > j:
                p_casa += p
            elif i == j:
                p_empate += p
            else:
                p_fora += p

            if i + j >= 2:
                over_15 += p
            if i + j >= 3:
                over_25 += p
            if i > 0 and j > 0:
                ambas_marcam += p

    total_1x2 = p_casa + p_empate + p_fora

    if total_1x2 > 0:
        p_casa /= total_1x2
        p_empate /= total_1x2
        p_fora /= total_1x2

    intensidade = (forca_casa + forca_fora) / 2
    equilibrio = max(0, 100 - abs(forca_casa - forca_fora) * 3)

    escanteios_total = max(
        6.0,
        min(13.0, 8.5 + (intensidade - 70) * 0.10 + (equilibrio - 60) * 0.02),
    )
    cartoes_total = max(
        2.5,
        min(7.5, 4.0 + (equilibrio - 60) * 0.015),
    )

    favorito = casa
    prob_favorito = p_casa

    if p_fora > p_casa:
        favorito = fora
        prob_favorito = p_fora
    elif p_empate > p_casa and p_empate > p_fora:
        favorito = "Empate"
        prob_favorito = p_empate

    return {
        "casa": casa,
        "fora": fora,
        "forca_casa": forca_casa,
        "forca_fora": forca_fora,
        "gols_casa": gols_casa,
        "gols_fora": gols_fora,
        "p_casa": p_casa,
        "p_empate": p_empate,
        "p_fora": p_fora,
        "over_15": over_15,
        "over_25": over_25,
        "ambas_marcam": ambas_marcam,
        "escanteios_total": escanteios_total,
        "cartoes_total": cartoes_total,
        "prob_mais_8_escanteios": min(0.88, max(0.25, (escanteios_total - 6.5) / 7.0)),
        "prob_mais_9_escanteios": min(0.82, max(0.20, (escanteios_total - 7.2) / 7.0)),
        "prob_mais_3_cartoes": min(0.90, max(0.25, (cartoes_total - 2.2) / 4.8)),
        "prob_mais_4_cartoes": min(0.82, max(0.18, (cartoes_total - 3.0) / 4.8)),
        "favorito": favorito,
        "prob_favorito": prob_favorito,
    }


# ============================================================
# DIAGNÓSTICO DE ACERTOS E ERROS
# ============================================================

def resultado_real(jogo):
    pc = jogo.get("placar_casa")
    pf = jogo.get("placar_fora")

    if pc is None or pf is None:
        return None

    try:
        pc = int(pc)
        pf = int(pf)
    except Exception:
        return None

    if pc > pf:
        return "casa"
    if pf > pc:
        return "fora"
    return "empate"


def palpite_resultado(r):
    if r["p_casa"] >= r["p_empate"] and r["p_casa"] >= r["p_fora"]:
        return "casa", r["casa"], r["p_casa"]
    if r["p_fora"] >= r["p_casa"] and r["p_fora"] >= r["p_empate"]:
        return "fora", r["fora"], r["p_fora"]
    return "empate", "Empate", r["p_empate"]


def diagnosticar_jogo(jogo):
    r = calcular_probabilidades(jogo.get("casa", ""), jogo.get("fora", ""))
    real = resultado_real(jogo)

    if real is None:
        return None

    palpite_key, palpite_label, prob = palpite_resultado(r)
    acertou_resultado = palpite_key == real

    pc = int(jogo.get("placar_casa"))
    pf = int(jogo.get("placar_fora"))
    total_gols = pc + pf
    ambas = pc > 0 and pf > 0

    palpite_over_15 = r["over_15"] >= 0.55
    palpite_over_25 = r["over_25"] >= 0.55
    palpite_ambas = r["ambas_marcam"] >= 0.55

    return {
        "jogo": jogo,
        "modelo": r,
        "real": real,
        "palpite_key": palpite_key,
        "palpite_label": palpite_label,
        "prob": prob,
        "acertou_resultado": acertou_resultado,
        "placar": f"{pc} x {pf}",
        "total_gols": total_gols,
        "acertou_over_15": palpite_over_15 == (total_gols >= 2),
        "acertou_over_25": palpite_over_25 == (total_gols >= 3),
        "acertou_ambas": palpite_ambas == ambas,
        "palpite_over_15": palpite_over_15,
        "palpite_over_25": palpite_over_25,
        "palpite_ambas": palpite_ambas,
    }


def classe_diagnostico(acertou):
    return "pill pill-ok" if acertou else "pill pill-bad"


def texto_diagnostico(acertou):
    return "ACERTO" if acertou else "ERRO"


# ============================================================
# HISTÓRICO OPENLIGADB
# ============================================================

def buscar_confrontos_openligadb(casa, fora, config_openliga):
    if not config_openliga:
        return None

    matches = openligadb_get_matches(
        config_openliga["league"],
        config_openliga["season"],
    )

    casa_norm = normalizar_nome(casa).lower()
    fora_norm = normalizar_nome(fora).lower()

    confrontos = []

    for match in matches:
        team1 = normalizar_nome((match.get("team1") or {}).get("teamName", ""))
        team2 = normalizar_nome((match.get("team2") or {}).get("teamName", ""))

        t1 = team1.lower()
        t2 = team2.lower()

        mesmo_jogo = (t1 == casa_norm and t2 == fora_norm) or (t1 == fora_norm and t2 == casa_norm)

        if not mesmo_jogo:
            continue

        score1, score2 = extrair_placar_openligadb(match)

        if score1 is None or score2 is None:
            continue

        try:
            dt = datetime.fromisoformat(str(match.get("matchDateTime", "")).replace("Z", "+00:00"))
            data = dt.strftime("%Y-%m-%d")
        except Exception:
            data = ""

        placar_casa = score1 if t1 == casa_norm else score2
        placar_fora = score2 if t1 == casa_norm else score1

        if placar_casa > placar_fora:
            vencedor = "casa"
        elif placar_fora > placar_casa:
            vencedor = "fora"
        else:
            vencedor = "empate"

        confrontos.append(
            {
                "data": data,
                "team1": team1,
                "team2": team2,
                "score1": score1,
                "score2": score2,
                "placar_casa": placar_casa,
                "placar_fora": placar_fora,
                "vencedor": vencedor,
            }
        )

    if not confrontos:
        return None

    confrontos.sort(key=lambda x: x.get("data", ""), reverse=True)

    total = len(confrontos)
    vitorias_casa = sum(1 for c in confrontos if c["vencedor"] == "casa")
    vitorias_fora = sum(1 for c in confrontos if c["vencedor"] == "fora")
    empates = sum(1 for c in confrontos if c["vencedor"] == "empate")

    return {
        "total": total,
        "vitorias_casa": vitorias_casa,
        "vitorias_fora": vitorias_fora,
        "empates": empates,
        "confrontos": confrontos[:8],
    }


# ============================================================
# UI
# ============================================================

def status_visual(jogo):
    estado = str(jogo.get("status_state", "")).lower()

    if estado == "in":
        return "pill pill-live", "AO VIVO"
    if estado == "post":
        return "pill pill-post", "ENCERRADO"
    if estado == "pre":
        return "pill", "PRÓXIMO"

    return "pill pill-warn", jogo.get("status_name") or "STATUS"


def mostrar_jogo_card(jogo, config_openliga):
    classe, texto_status = status_visual(jogo)

    placar = ""
    if jogo.get("placar_casa") is not None and jogo.get("placar_fora") is not None:
        placar = f" — {jogo.get('placar_casa')} x {jogo.get('placar_fora')}"

    data = fmt_data(jogo.get("data"))
    hora = jogo.get("hora") or "--:--"
    fonte = jogo.get("source", "Fonte")

    st.markdown(
        f"""
        <div class="match-card">
            <span class="{classe}">{esc(texto_status)}</span>
            <span class="source">{esc(fonte)}</span>
            <span class="muted">{esc(data)} • {esc(hora)}</span>
            <div class="match-title">{esc(jogo.get("casa"))} x {esc(jogo.get("fora"))}{esc(placar)}</div>
            <div class="muted">{esc(jogo.get("status_detail") or jogo.get("status_name") or "")}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("📊 Análise do jogo"):
        mostrar_analise_partida(
            jogo.get("casa", ""),
            jogo.get("fora", ""),
            config_openliga,
        )


def mostrar_analise_partida(casa, fora, config_openliga):
    r = calcular_probabilidades(casa, fora)

    st.markdown(
        f"""
        <div class="summary-box">
            <b>Resumo:</b> tendência principal para <b>{esc(r["favorito"])}</b>
            com {esc(pct(r["prob_favorito"]))} de probabilidade estimada.
            Gols esperados: {r["gols_casa"]:.2f} x {r["gols_fora"]:.2f}.
        </div>
        """,
        unsafe_allow_html=True,
    )

    aba_resultado, aba_gols, aba_escanteios, aba_cartoes, aba_historico = st.tabs(
        ["Resultado", "Gols", "Escanteios", "Cartões", "Histórico"]
    )

    with aba_resultado:
        col1, col2, col3 = st.columns(3)
        col1.metric(f"Vitória {r['casa']}", pct(r["p_casa"]))
        col2.metric("Empate", pct(r["p_empate"]))
        col3.metric(f"Vitória {r['fora']}", pct(r["p_fora"]))

        col4, col5 = st.columns(2)
        col4.metric(f"Força {r['casa']}", r["forca_casa"])
        col5.metric(f"Força {r['fora']}", r["forca_fora"])

    with aba_gols:
        col1, col2 = st.columns(2)
        col1.metric("Gols esperados mandante", f"{r['gols_casa']:.2f}")
        col2.metric("Gols esperados visitante", f"{r['gols_fora']:.2f}")

        col3, col4, col5 = st.columns(3)
        col3.metric("+1.5 gols", pct(r["over_15"]))
        col4.metric("+2.5 gols", pct(r["over_25"]))
        col5.metric("Ambas marcam", pct(r["ambas_marcam"]))

    with aba_escanteios:
        col1, col2, col3 = st.columns(3)
        col1.metric("Média estimada", f"{r['escanteios_total']:.1f}")
        col2.metric("+8 escanteios", pct(r["prob_mais_8_escanteios"]), nivel_texto(r["prob_mais_8_escanteios"]))
        col3.metric("+9 escanteios", pct(r["prob_mais_9_escanteios"]), nivel_texto(r["prob_mais_9_escanteios"]))

    with aba_cartoes:
        col1, col2, col3 = st.columns(3)
        col1.metric("Média estimada", f"{r['cartoes_total']:.1f}")
        col2.metric("+3 cartões", pct(r["prob_mais_3_cartoes"]), nivel_texto(r["prob_mais_3_cartoes"]))
        col3.metric("+4 cartões", pct(r["prob_mais_4_cartoes"]), nivel_texto(r["prob_mais_4_cartoes"]))

    with aba_historico:
        historico = buscar_confrontos_openligadb(casa, fora, config_openliga)

        if not config_openliga:
            st.info("Histórico OpenLigaDB não configurado para esta competição.")
        elif not historico:
            st.info("Nenhum confronto direto encontrado na OpenLigaDB para esta temporada.")
        else:
            col1, col2, col3 = st.columns(3)
            col1.metric(casa, f"{historico['vitorias_casa']} vitórias")
            col2.metric("Empates", historico["empates"])
            col3.metric(fora, f"{historico['vitorias_fora']} vitórias")

            for c in historico["confrontos"]:
                st.write(
                    f"{fmt_data(c['data'])}: {c['team1']} {c['score1']} x {c['score2']} {c['team2']}"
                )

    st.warning(
        "As probabilidades são estimativas matemáticas. Use como apoio estatístico, não como garantia de resultado."
    )


def mostrar_diagnostico_card(item):
    jogo = item["jogo"]
    classe = classe_diagnostico(item["acertou_resultado"])
    texto = texto_diagnostico(item["acertou_resultado"])

    data = fmt_data(jogo.get("data"))
    hora = jogo.get("hora") or "--:--"
    fonte = jogo.get("source", "Fonte")

    real_label = {
        "casa": jogo.get("casa"),
        "fora": jogo.get("fora"),
        "empate": "Empate",
    }.get(item["real"], "-")

    st.markdown(
        f"""
        <div class="diag-card">
            <span class="{classe}">{esc(texto)}</span>
            <span class="source">{esc(fonte)}</span>
            <span class="muted">{esc(data)} • {esc(hora)}</span>
            <div class="diag-title">{esc(jogo.get("casa"))} {esc(item["placar"])} {esc(jogo.get("fora"))}</div>
            <div class="muted">
                Palpite principal: <b>{esc(item["palpite_label"])}</b> ({esc(pct(item["prob"]))}) •
                Resultado real: <b>{esc(real_label)}</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Ver detalhes do diagnóstico"):
        c1, c2, c3 = st.columns(3)
        c1.metric("Resultado", "Acertou" if item["acertou_resultado"] else "Errou")
        c2.metric("+1.5 gols", "Acertou" if item["acertou_over_15"] else "Errou")
        c3.metric("+2.5 gols", "Acertou" if item["acertou_over_25"] else "Errou")

        c4, c5 = st.columns(2)
        c4.metric("Ambas marcam", "Acertou" if item["acertou_ambas"] else "Errou")
        c5.metric("Total de gols real", item["total_gols"])

        st.caption(
            f"Modelo: {pct(item['modelo']['p_casa'])} casa • "
            f"{pct(item['modelo']['p_empate'])} empate • "
            f"{pct(item['modelo']['p_fora'])} fora"
        )


# ============================================================
# APP
# ============================================================

check_login()

st.title(APP_TITLE)

with st.sidebar:
    st.header("Filtros")

    competicao_nome = st.selectbox(
        "Competição",
        list(COMPETICOES.keys()),
        index=0,
    )

    filtro_periodo = st.radio(
        "Jogos",
        ["Hoje", "Amanhã", "Ao vivo", "Próximos", "Todos"],
        horizontal=False,
    )

    dias_busca = st.slider(
        "Dias para buscar",
        min_value=1,
        max_value=14,
        value=3,
        help="Use menos dias para carregar mais rápido no celular.",
    )

    buscar_openliga = st.toggle(
        "Usar OpenLigaDB quando disponível",
        value=True,
    )

    if st.button("Atualizar dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    if st.button("Sair", use_container_width=True):
        st.session_state.logado = False
        st.rerun()


config = COMPETICOES[competicao_nome]
config_openliga = config.get("openligadb") if buscar_openliga else None

st.markdown(
    f"""
    <div class="top-box">
        <b>{esc(competicao_nome)}</b><br>
        <span class="muted">Atualizado em {esc(br_now().strftime('%d/%m/%Y %H:%M'))}</span>
    </div>
    """,
    unsafe_allow_html=True,
)

aba_jogos, aba_diagnostico = st.tabs(
    ["Jogos e análises", "Diagnóstico 48h"]
)


# ============================================================
# ABA JOGOS
# ============================================================

with aba_jogos:
    with st.spinner("Buscando jogos..."):
        jogos_espn, logs_espn = buscar_jogos_espn_periodo(config["espn"], dias=dias_busca)

        jogos_openliga = []
        erro_openliga = ""

        if config_openliga:
            jogos_openliga, erro_openliga = buscar_jogos_openligadb_periodo(
                config_openliga,
                dias=dias_busca,
            )

        jogos = combinar_fontes(jogos_espn, jogos_openliga)
        jogos_filtrados = filtrar_jogos(jogos, filtro_periodo)

    total = len(jogos_filtrados)
    ao_vivo = sum(1 for j in jogos_filtrados if str(j.get("status_state", "")).lower() == "in")
    fontes = sorted(set(j.get("source", "Fonte") for j in jogos_filtrados))

    m1, m2, m3 = st.columns(3)
    m1.metric("Jogos exibidos", total)
    m2.metric("Ao vivo", ao_vivo)
    m3.metric("Fontes", ", ".join(fontes) if fontes else "-")

    if config_openliga:
        st.success(
            f"OpenLigaDB ativa: {config_openliga['league']} / {config_openliga['season']}."
        )
    else:
        st.info(
            "OpenLigaDB não está configurada para esta competição. A ESPN será usada como fonte principal."
        )

    if logs_espn:
        with st.expander("Avisos da ESPN"):
            for log in logs_espn[:8]:
                st.write(log)

    if erro_openliga:
        st.caption(erro_openliga)

    st.divider()

    if not jogos_filtrados:
        st.warning("Nenhum jogo encontrado para os filtros selecionados.")
    else:
        busca = st.text_input(
            "Buscar time",
            placeholder="Digite parte do nome do time",
        ).strip().lower()

        if busca:
            jogos_filtrados = [
                j
                for j in jogos_filtrados
                if busca in normalizar_nome(j.get("casa")).lower()
                or busca in normalizar_nome(j.get("fora")).lower()
            ]

        if not jogos_filtrados:
            st.warning("Nenhum jogo encontrado para esse time.")
        else:
            for jogo in jogos_filtrados:
                mostrar_jogo_card(jogo, config_openliga)


# ============================================================
# ABA DIAGNÓSTICO
# ============================================================

with aba_diagnostico:
    st.subheader("Diagnóstico das últimas 48 horas")

    st.caption(
        "Compara o palpite matemático principal com os jogos encerrados nas últimas 48 horas."
    )

    with st.spinner("Buscando jogos encerrados..."):
        diag_espn, logs_diag_espn = buscar_jogos_espn_ultimas_48h(config["espn"])

        diag_openliga = []
        erro_diag_openliga = ""

        if config_openliga:
            diag_openliga, erro_diag_openliga = buscar_jogos_openligadb_ultimas_48h(config_openliga)

        jogos_diag = combinar_fontes(diag_espn, diag_openliga)
        diagnosticos = []

        for jogo in jogos_diag:
            item = diagnosticar_jogo(jogo)
            if item:
                diagnosticos.append(item)

    total_diag = len(diagnosticos)
    acertos_resultado = sum(1 for d in diagnosticos if d["acertou_resultado"])
    erros_resultado = total_diag - acertos_resultado

    acertos_over15 = sum(1 for d in diagnosticos if d["acertou_over_15"])
    acertos_over25 = sum(1 for d in diagnosticos if d["acertou_over_25"])
    acertos_ambas = sum(1 for d in diagnosticos if d["acertou_ambas"])

    taxa_resultado = (acertos_resultado / total_diag) if total_diag else 0
    taxa_over15 = (acertos_over15 / total_diag) if total_diag else 0
    taxa_over25 = (acertos_over25 / total_diag) if total_diag else 0
    taxa_ambas = (acertos_ambas / total_diag) if total_diag else 0

    d1, d2, d3 = st.columns(3)
    d1.metric("Jogos avaliados", total_diag)
    d2.metric("Acertos resultado", acertos_resultado, pct(taxa_resultado) if total_diag else "-")
    d3.metric("Erros resultado", erros_resultado)

    d4, d5, d6 = st.columns(3)
    d4.metric("Acerto +1.5 gols", pct(taxa_over15) if total_diag else "-")
    d5.metric("Acerto +2.5 gols", pct(taxa_over25) if total_diag else "-")
    d6.metric("Acerto ambas marcam", pct(taxa_ambas) if total_diag else "-")

    if logs_diag_espn:
        with st.expander("Avisos da ESPN no diagnóstico"):
            for log in logs_diag_espn[:8]:
                st.write(log)

    if erro_diag_openliga:
        st.caption(erro_diag_openliga)

    st.divider()

    if not diagnosticos:
        st.warning("Nenhum jogo encerrado encontrado nas últimas 48 horas para esta competição.")
    else:
        filtro_diag = st.radio(
            "Mostrar",
            ["Todos", "Só acertos", "Só erros"],
            horizontal=True,
        )

        filtrados_diag = diagnosticos
        if filtro_diag == "Só acertos":
            filtrados_diag = [d for d in diagnosticos if d["acertou_resultado"]]
        elif filtro_diag == "Só erros":
            filtrados_diag = [d for d in diagnosticos if not d["acertou_resultado"]]

        for item in filtrados_diag:
            mostrar_diagnostico_card(item)

    st.warning(
        "O diagnóstico mede apenas se o modelo acertou a tendência matemática. Não representa recomendação de aposta nem garantia futura."
    )
