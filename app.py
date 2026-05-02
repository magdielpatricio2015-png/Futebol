import math
import time
import html
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st


# ============================================================
# CONFIGURAÇÃO GERAL
# ============================================================

st.set_page_config(
    page_title="Analisador Futebol Pro 2.0",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)

TZ_BR = ZoneInfo("America/Sao_Paulo")
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

COMPETICOES = {
    "Brasileirão Série A": "bra.1",
    "Brasileirão Série B": "bra.2",
    "Copa do Brasil": "bra.copa_do_brasil",
    "Libertadores": "conmebol.libertadores",
    "Sul-Americana": "conmebol.sudamericana",
    "Premier League": "eng.1",
    "La Liga": "esp.1",
    "Serie A Itália": "ita.1",
    "Bundesliga": "ger.1",
    "Ligue 1": "fra.1",
    "Champions League": "uefa.champions",
    "Europa League": "uefa.europa",
}

FORCA_BASE = {
    "Flamengo": 86,
    "Palmeiras": 85,
    "Botafogo": 81,
    "Atlético-MG": 80,
    "Atletico-MG": 80,
    "São Paulo": 78,
    "Sao Paulo": 78,
    "Fluminense": 78,
    "Grêmio": 77,
    "Gremio": 77,
    "Internacional": 77,
    "Corinthians": 76,
    "Cruzeiro": 75,
    "Bahia": 74,
    "Fortaleza": 73,
    "Vasco": 72,
    "Santos": 72,
    "Sport": 68,
    "Ceará": 69,
    "Ceara": 69,
    "Vitória": 69,
    "Vitoria": 69,
    "Manchester City": 91,
    "Arsenal": 88,
    "Liverpool": 88,
    "Chelsea": 82,
    "Tottenham Hotspur": 80,
    "Real Madrid": 90,
    "Barcelona": 88,
    "Atlético Madrid": 84,
    "Atletico Madrid": 84,
    "Bayern Munich": 88,
    "Borussia Dortmund": 82,
    "Bayer Leverkusen": 84,
    "Inter Milan": 86,
    "Juventus": 82,
    "PSG": 88,
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 AnalisadorFutebolPro/2.0"
}


# ============================================================
# CSS RESPONSIVO
# ============================================================

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 0.8rem;
            padding-bottom: 2rem;
        }
        .game-card {
            border: 1px solid rgba(150,150,150,.25);
            border-radius: 16px;
            padding: 14px 16px;
            margin-bottom: 12px;
            background: rgba(255,255,255,.04);
        }
        .game-title {
            font-size: 1.05rem;
            font-weight: 750;
            margin-bottom: 4px;
        }
        .muted {
            opacity: .72;
            font-size: .88rem;
        }
        .pill {
            display: inline-block;
            padding: 3px 9px;
            border-radius: 999px;
            border: 1px solid rgba(150,150,150,.35);
            font-size: .82rem;
            margin-right: 4px;
            margin-top: 5px;
        }
        .good {
            border-left: 5px solid #16a34a;
        }
        .medium {
            border-left: 5px solid #ca8a04;
        }
        .low {
            border-left: 5px solid #dc2626;
        }
        @media (max-width: 700px) {
            .block-container {
                padding-left: .7rem;
                padding-right: .7rem;
            }
            div[data-testid="stMetricValue"] {
                font-size: 1.05rem;
            }
            .game-title {
                font-size: 1rem;
            }
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


def nome_limpo(nome):
    return " ".join(str(nome or "").strip().split())


def forca_inicial(nome):
    nome = nome_limpo(nome)
    if nome in FORCA_BASE:
        return 1300 + FORCA_BASE[nome] * 6

    # fallback estável, não aleatório
    seed = sum(ord(c) for c in nome)
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
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def media_suave(valor, n, media_liga, peso_liga=5):
    return (valor + media_liga * peso_liga) / max(1, n + peso_liga)


def nivel_confianca(p_top, p_segundo, qualidade):
    margem = p_top - p_segundo

    if qualidade < 0.35:
        return "Baixa", "low"

    if p_top >= 0.62 and margem >= 0.14 and qualidade >= 0.65:
        return "Alta", "good"

    if p_top >= 0.54 and margem >= 0.08 and qualidade >= 0.45:
        return "Média", "medium"

    return "Baixa", "low"


def status_legivel(jogo):
    state = jogo.get("state")
    detalhe = jogo.get("status", "")

    if state == "in":
        return f"🔴 Ao vivo — {detalhe}"
    if state == "post":
        return "✅ Encerrado"
    return "🕒 Futuro"


# ============================================================
# ESPN API
# ============================================================

@st.cache_data(ttl=60, show_spinner=False)
def buscar_scoreboard_data(liga, data_yyyy_mm_dd):
    data_api = data_yyyy_mm_dd.replace("-", "")
    url = f"{ESPN_BASE}/{liga}/scoreboard"
    params = {"dates": data_api, "limit": 200}

    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.json(), ""
    except requests.RequestException as e:
        return {}, f"Erro ESPN {liga} em {data_yyyy_mm_dd}: {e}"


@st.cache_data(ttl=240, show_spinner=False)
def buscar_periodo(liga, inicio_iso, fim_iso):
    inicio = datetime.fromisoformat(inicio_iso).date()
    fim = datetime.fromisoformat(fim_iso).date()

    jogos = []
    logs = []

    dia = inicio
    while dia <= fim:
        data, erro = buscar_scoreboard_data(liga, dia.isoformat())
        if erro:
            logs.append(erro)
        jogos.extend(extrair_jogos(data, liga))
        dia += timedelta(days=1)

    return deduplicar(jogos), logs


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

        casa = None
        fora = None

        for c in competidores:
            if c.get("homeAway") == "home":
                casa = c
            elif c.get("homeAway") == "away":
                fora = c

        # fallback caso a API venha em ordem diferente
        casa = casa or competidores[0]
        fora = fora or competidores[1]

        status = (comp.get("status") or {}).get("type") or {}
        state = status.get("state", "")
        completed = bool(status.get("completed", False))

        dt = parse_dt_espn(ev.get("date"))

        def score(c):
            try:
                return int(c.get("score"))
            except Exception:
                return None

        jogos.append(
            {
                "id": str(ev.get("id") or ""),
                "liga": liga,
                "data": dt,
                "data_txt": dt.strftime("%d/%m %H:%M") if dt else "Sem data",
                "casa": nome_limpo(((casa.get("team") or {}).get("displayName"))),
                "fora": nome_limpo(((fora.get("team") or {}).get("displayName"))),
                "placar_casa": score(casa),
                "placar_fora": score(fora),
                "state": state,
                "completed": completed,
                "status": status.get("detail") or status.get("shortDetail") or "",
            }
        )

    return jogos


def chave_jogo(j):
    data = j.get("data")
    data_key = data.strftime("%Y-%m-%d") if data else ""
    return (
        data_key,
        nome_limpo(j.get("casa")).lower(),
        nome_limpo(j.get("fora")).lower(),
    )


def deduplicar(jogos):
    vistos = {}
    for j in jogos:
        k = chave_jogo(j)
        # se duplicar, prefere o que tem placar/status mais completo
        antigo = vistos.get(k)
        if not antigo:
            vistos[k] = j
        elif j.get("completed") or j.get("state") == "in":
            vistos[k] = j
    return sorted(vistos.values(), key=lambda x: x.get("data") or agora_br())


# ============================================================
# MODELO
# ============================================================

def novo_stats():
    return {
        "jogos": 0,
        "gf": 0,
        "ga": 0,
        "home_jogos": 0,
        "home_gf": 0,
        "home_ga": 0,
        "away_jogos": 0,
        "away_gf": 0,
        "away_ga": 0,
        "pontos_recent": [],
        "gols_recent": [],
    }


def construir_contexto(jogos_encerrados):
    jogos = [j for j in jogos_encerrados if j.get("completed") and j.get("placar_casa") is not None]
    jogos = sorted(jogos, key=lambda x: x.get("data") or agora_br())

    ratings = {}
    stats = {}

    total_home_gols = 0
    total_away_gols = 0

    for j in jogos:
        casa = j["casa"]
        fora = j["fora"]
        gc = int(j["placar_casa"])
        gf = int(j["placar_fora"])

        ratings.setdefault(casa, forca_inicial(casa))
        ratings.setdefault(fora, forca_inicial(fora))
        stats.setdefault(casa, novo_stats())
        stats.setdefault(fora, novo_stats())

        rc = ratings[casa]
        rf = ratings[fora]

        exp_casa = 1 / (1 + 10 ** ((rf - (rc + 55)) / 400))

        if gc > gf:
            real_casa = 1
            pontos_casa, pontos_fora = 3, 0
        elif gc == gf:
            real_casa = 0.5
            pontos_casa, pontos_fora = 1, 1
        else:
            real_casa = 0
            pontos_casa, pontos_fora = 0, 3

        margem = abs(gc - gf)
        k = 22 + min(12, margem * 4)

        delta = k * (real_casa - exp_casa)
        ratings[casa] = rc + delta
        ratings[fora] = rf - delta

        sc = stats[casa]
        sf = stats[fora]

        sc["jogos"] += 1
        sc["gf"] += gc
        sc["ga"] += gf
        sc["home_jogos"] += 1
        sc["home_gf"] += gc
        sc["home_ga"] += gf
        sc["pontos_recent"].append(pontos_casa)
        sc["gols_recent"].append(gc)

        sf["jogos"] += 1
        sf["gf"] += gf
        sf["ga"] += gc
        sf["away_jogos"] += 1
        sf["away_gf"] += gf
        sf["away_ga"] += gc
        sf["pontos_recent"].append(pontos_fora)
        sf["gols_recent"].append(gf)

        total_home_gols += gc
        total_away_gols += gf

    n = max(1, len(jogos))
    liga_home = total_home_gols / n if jogos else 1.35
    liga_away = total_away_gols / n if jogos else 1.05

    return {
        "ratings": ratings,
        "stats": stats,
        "jogos": len(jogos),
        "liga_home": max(0.8, min(2.2, liga_home)),
        "liga_away": max(0.6, min(1.8, liga_away)),
    }


def prever(casa, fora, contexto):
    ratings = contexto.get("ratings", {})
    stats = contexto.get("stats", {})
    jogos_modelo = contexto.get("jogos", 0)

    casa = nome_limpo(casa)
    fora = nome_limpo(fora)

    elo_casa = ratings.get(casa, forca_inicial(casa))
    elo_fora = ratings.get(fora, forca_inicial(fora))

    liga_home = contexto.get("liga_home", 1.35)
    liga_away = contexto.get("liga_away", 1.05)

    sc = stats.get(casa, novo_stats())
    sf = stats.get(fora, novo_stats())

    home_gf = media_suave(sc["home_gf"], sc["home_jogos"], liga_home)
    home_ga = media_suave(sc["home_ga"], sc["home_jogos"], liga_away)
    away_gf = media_suave(sf["away_gf"], sf["away_jogos"], liga_away)
    away_ga = media_suave(sf["away_ga"], sf["away_jogos"], liga_home)

    atk_casa = home_gf / liga_home
    def_fora = away_ga / liga_home
    atk_fora = away_gf / liga_away
    def_casa = home_ga / liga_away

    diff_elo = (elo_casa + 55) - elo_fora
    fator_casa = max(0.72, min(1.34, 1 + diff_elo / 950))
    fator_fora = max(0.72, min(1.34, 1 - diff_elo / 1000))

    forma_casa = sum(sc["pontos_recent"][-5:]) / max(1, len(sc["pontos_recent"][-5:])) if sc["pontos_recent"] else 1.35
    forma_fora = sum(sf["pontos_recent"][-5:]) / max(1, len(sf["pontos_recent"][-5:])) if sf["pontos_recent"] else 1.20

    fator_forma_casa = max(0.88, min(1.14, 1 + (forma_casa - 1.35) * 0.055))
    fator_forma_fora = max(0.88, min(1.14, 1 + (forma_fora - 1.20) * 0.055))

    gols_casa = liga_home * atk_casa * def_fora * fator_casa * fator_forma_casa
    gols_fora = liga_away * atk_fora * def_casa * fator_fora * fator_forma_fora

    if jogos_modelo < 8:
        # mistura com fallback para não forçar demais com pouca amostra
        fallback_casa = 1.35 + ((forca_inicial(casa) - forca_inicial(fora)) / 400) * 0.35
        fallback_fora = 1.05 - ((forca_inicial(casa) - forca_inicial(fora)) / 400) * 0.28
        peso = jogos_modelo / 8
        gols_casa = gols_casa * peso + fallback_casa * (1 - peso)
        gols_fora = gols_fora * peso + fallback_fora * (1 - peso)

    gols_casa = max(0.35, min(3.50, gols_casa))
    gols_fora = max(0.25, min(3.20, gols_fora))

    p_casa = p_empate = p_fora = 0.0
    over15 = over25 = btts = 0.0
    placares = []

    for i in range(9):
        for k in range(9):
            p = poisson(i, gols_casa) * poisson(k, gols_fora)
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
            if i > 0 and k > 0:
                btts += p

    total = p_casa + p_empate + p_fora
    if total:
        p_casa /= total
        p_empate /= total
        p_fora /= total

    probs = {
        "Casa": p_casa,
        "Empate": p_empate,
        "Fora": p_fora,
    }
    ordenadas = sorted(probs.items(), key=lambda x: x[1], reverse=True)
    palpite, p_top = ordenadas[0]
    p_segundo = ordenadas[1][1]

    # qualidade: quantidade de jogos dos times + tamanho da base
    jogos_times = sc["jogos"] + sf["jogos"]
    qualidade = min(1.0, (jogos_modelo / 30) * 0.55 + (jogos_times / 12) * 0.45)

    conf, conf_class = nivel_confianca(p_top, p_segundo, qualidade)

    placares_top = sorted(placares, reverse=True)[:3]

    return {
        "casa": casa,
        "fora": fora,
        "gols_casa": gols_casa,
        "gols_fora": gols_fora,
        "p_casa": p_casa,
        "p_empate": p_empate,
        "p_fora": p_fora,
        "over15": over15,
        "over25": over25,
        "btts": btts,
        "elo_casa": elo_casa,
        "elo_fora": elo_fora,
        "palpite": palpite,
        "prob_palpite": p_top,
        "confianca": conf,
        "conf_class": conf_class,
        "qualidade": qualidade,
        "placares_top": placares_top,
        "jogos_modelo": jogos_modelo,
        "amostra_times": jogos_times,
    }


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


def avaliar_jogo(jogo, contexto):
    real = resultado_real(jogo)
    if not real:
        return None

    r = prever(jogo["casa"], jogo["fora"], contexto)

    probs = {
        "Casa": r["p_casa"],
        "Empate": r["p_empate"],
        "Fora": r["p_fora"],
    }

    brier = sum((probs[k] - (1 if k == real else 0)) ** 2 for k in probs) / 3
    acertou = r["palpite"] == real

    total_gols = jogo["placar_casa"] + jogo["placar_fora"]
    real_over15 = total_gols >= 2
    real_over25 = total_gols >= 3
    real_btts = jogo["placar_casa"] > 0 and jogo["placar_fora"] > 0

    return {
        "jogo": jogo,
        "prev": r,
        "real": real,
        "acertou": acertou,
        "brier": brier,
        "over15_ok": (r["over15"] >= 0.55) == real_over15,
        "over25_ok": (r["over25"] >= 0.52) == real_over25,
        "btts_ok": (r["btts"] >= 0.52) == real_btts,
        "explicacao": explicar_erro(jogo, r, real, acertou),
    }


def explicar_erro(jogo, r, real, acertou):
    if acertou:
        if r["confianca"] == "Alta":
            return "Acerto forte: modelo tinha margem e boa base de dados."
        return "Acerto, mas com cautela: confiança não era máxima."

    if r["confianca"] == "Baixa":
        return "Erro aceitável: o próprio modelo marcava baixa confiança."

    if real == "Empate":
        return "Erro por empate: futebol tem alta variância quando as forças são próximas."

    if r["palpite"] == "Casa" and real == "Fora":
        return "Mandante foi superestimado ou visitante chegou melhor que o histórico indicava."

    if r["palpite"] == "Fora" and real == "Casa":
        return "Visitante foi superestimado ou mando de campo pesou mais que o previsto."

    return "Erro normal do modelo; revisar forma recente, desfalques e contexto do jogo."


# ============================================================
# COMPONENTES VISUAIS
# ============================================================

def card_jogo(jogo, contexto):
    r = prever(jogo["casa"], jogo["fora"], contexto)

    nome_palpite = {
        "Casa": jogo["casa"],
        "Fora": jogo["fora"],
        "Empate": "Empate",
    }[r["palpite"]]

    placar = ""
    if jogo.get("placar_casa") is not None:
        placar = f" — {jogo['placar_casa']} x {jogo['placar_fora']}"

    st.markdown(
        f"""
        <div class="game-card {r['conf_class']}">
            <div class="game-title">{esc(jogo['casa'])} x {esc(jogo['fora'])}{esc(placar)}</div>
            <div class="muted">{esc(jogo['data_txt'])} • {esc(status_legivel(jogo))}</div>
            <span class="pill">Palpite: <b>{esc(nome_palpite)}</b></span>
            <span class="pill">Prob.: <b>{esc(pct(r['prob_palpite']))}</b></span>
            <span class="pill">Confiança: <b>{esc(r['confianca'])}</b></span>
            <span class="pill">Gols esp.: <b>{r['gols_casa']:.2f} x {r['gols_fora']:.2f}</b></span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Ver análise detalhada"):
        c1, c2, c3 = st.columns(3)
        c1.metric(f"Vitória {jogo['casa']}", pct(r["p_casa"]))
        c2.metric("Empate", pct(r["p_empate"]))
        c3.metric(f"Vitória {jogo['fora']}", pct(r["p_fora"]))

        g1, g2, g3 = st.columns(3)
        g1.metric("+1.5 gols", pct(r["over15"]))
        g2.metric("+2.5 gols", pct(r["over25"]))
        g3.metric("Ambas marcam", pct(r["btts"]))

        ptxt = ", ".join([f"{i}x{k} ({pct(p)})" for p, i, k in r["placares_top"]])
        st.caption(f"Placares mais prováveis: {ptxt}")
        st.caption(
            f"Base do modelo: {r['jogos_modelo']} jogos encerrados. "
            f"Amostra dos times: {r['amostra_times']} jogos. "
            f"Qualidade estimada: {pct(r['qualidade'])}."
        )


def tabela_resumo(jogos, contexto):
    linhas = []
    for j in jogos:
        r = prever(j["casa"], j["fora"], contexto)
        nome_palpite = {"Casa": j["casa"], "Fora": j["fora"], "Empate": "Empate"}[r["palpite"]]
        linhas.append(
            {
                "Data": j["data_txt"],
                "Jogo": f"{j['casa']} x {j['fora']}",
                "Status": status_legivel(j),
                "Palpite": nome_palpite,
                "Prob.": pct(r["prob_palpite"]),
                "Confiança": r["confianca"],
                "+1.5": pct(r["over15"]),
                "+2.5": pct(r["over25"]),
                "Ambas": pct(r["btts"]),
            }
        )
    return pd.DataFrame(linhas)


# ============================================================
# APP
# ============================================================

st.title("⚽ Analisador Futebol Pro 2.0")
st.caption("Arquivo único para GitHub/Streamlit. Feito para PC e smartphone.")

with st.sidebar:
    st.header("Configurações")

    liga_nome = st.selectbox("Competição", list(COMPETICOES.keys()))
    liga = COMPETICOES[liga_nome]

    modo = st.radio(
        "Jogos",
        ["Hoje e próximos", "Ao vivo + 48h", "Últimos resultados", "Período personalizado"],
        index=0,
    )

    dias_historico = st.slider("Histórico usado pelo modelo", 15, 180, 75, step=15)

    somente_confianca = st.checkbox("Mostrar só confiança média/alta", value=False)
    busca = st.text_input("Filtrar time", placeholder="Ex.: Flamengo")

    if st.button("🔄 Atualizar dados"):
        st.cache_data.clear()
        st.rerun()

hoje = hoje_br()

if modo == "Hoje e próximos":
    inicio = hoje - timedelta(days=1)
    fim = hoje + timedelta(days=7)
elif modo == "Ao vivo + 48h":
    inicio = hoje - timedelta(days=1)
    fim = hoje + timedelta(days=1)
elif modo == "Últimos resultados":
    inicio = hoje - timedelta(days=7)
    fim = hoje
else:
    c1, c2 = st.sidebar.columns(2)
    inicio = c1.date_input("Início", hoje - timedelta(days=3))
    fim = c2.date_input("Fim", hoje + timedelta(days=3))

hist_inicio = hoje - timedelta(days=dias_historico)
hist_fim = hoje - timedelta(days=1)

with st.spinner("Carregando jogos e montando modelo..."):
    jogos_hist, logs_hist = buscar_periodo(liga, hist_inicio.isoformat(), hist_fim.isoformat())
    contexto = construir_contexto(jogos_hist)

    jogos, logs_jogos = buscar_periodo(liga, inicio.isoformat(), fim.isoformat())

# Filtros
if busca.strip():
    b = busca.strip().lower()
    jogos = [j for j in jogos if b in j["casa"].lower() or b in j["fora"].lower()]

if somente_confianca:
    jogos = [
        j for j in jogos
        if prever(j["casa"], j["fora"], contexto)["confianca"] in ("Média", "Alta")
    ]

aba_jogos, aba_diagnostico, aba_ranking = st.tabs(
    ["📋 Jogos e previsões", "🧪 Diagnóstico", "🏆 Ranking do modelo"]
)

with aba_jogos:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Jogos encontrados", len(jogos))
    m2.metric("Base do modelo", contexto["jogos"])
    m3.metric("Média gols casa", f"{contexto['liga_home']:.2f}")
    m4.metric("Média gols fora", f"{contexto['liga_away']:.2f}")

    if logs_jogos or logs_hist:
        with st.expander("Avisos de API"):
            for log in (logs_jogos + logs_hist)[:12]:
                st.write(log)

    st.info(
        "Use as previsões como análise estatística para o desafio entre amigos. "
        "Não existe garantia de resultado no futebol."
    )

    if not jogos:
        st.warning("Nenhum jogo encontrado para os filtros.")
    else:
        df = tabela_resumo(jogos, contexto)
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.subheader("Cards para celular")
        for jogo in jogos:
            card_jogo(jogo, contexto)

with aba_diagnostico:
    st.subheader("Diagnóstico dos últimos resultados")
    st.caption("Mede onde o modelo acertou/errou nos jogos já encerrados do recorte recente.")

    jogos_avaliar = [j for j in jogos_hist if j.get("completed")][-40:]
    avaliacoes = [avaliar_jogo(j, contexto) for j in jogos_avaliar]
    avaliacoes = [a for a in avaliacoes if a]

    if not avaliacoes:
        st.warning("Ainda não há jogos encerrados suficientes para diagnóstico.")
    else:
        total = len(avaliacoes)
        acertos = sum(a["acertou"] for a in avaliacoes)
        taxa = acertos / total if total else 0
        brier_medio = sum(a["brier"] for a in avaliacoes) / total

        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Jogos avaliados", total)
        d2.metric("Acertos 1X2", acertos, pct(taxa))
        d3.metric("Erros", total - acertos)
        d4.metric("Brier médio", f"{brier_medio:.3f}")

        filtro = st.radio("Mostrar", ["Todos", "Só acertos", "Só erros"], horizontal=True)

        lista = avaliacoes
        if filtro == "Só acertos":
            lista = [a for a in avaliacoes if a["acertou"]]
        elif filtro == "Só erros":
            lista = [a for a in avaliacoes if not a["acertou"]]

        for a in reversed(lista):
            j = a["jogo"]
            r = a["prev"]
            sinal = "✅" if a["acertou"] else "❌"
            palpite_nome = {"Casa": j["casa"], "Fora": j["fora"], "Empate": "Empate"}[r["palpite"]]
            real_nome = {"Casa": j["casa"], "Fora": j["fora"], "Empate": "Empate"}[a["real"]]

            st.markdown(
                f"""
                <div class="game-card {'good' if a['acertou'] else 'low'}">
                    <div class="game-title">{sinal} {esc(j['casa'])} {j['placar_casa']} x {j['placar_fora']} {esc(j['fora'])}</div>
                    <div class="muted">{esc(j['data_txt'])}</div>
                    <span class="pill">Palpite: <b>{esc(palpite_nome)}</b></span>
                    <span class="pill">Real: <b>{esc(real_nome)}</b></span>
                    <span class="pill">Confiança: <b>{esc(r['confianca'])}</b></span>
                    <span class="pill">Brier: <b>{a['brier']:.3f}</b></span>
                    <br><span class="muted">{esc(a['explicacao'])}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

with aba_ranking:
    st.subheader("Ranking dos mercados")
    st.caption("Ajuda a descobrir onde o modelo está melhor: resultado, gols ou ambas marcam.")

    jogos_avaliar = [j for j in jogos_hist if j.get("completed")][-60:]
    avaliacoes = [avaliar_jogo(j, contexto) for j in jogos_avaliar]
    avaliacoes = [a for a in avaliacoes if a]

    if not avaliacoes:
        st.warning("Sem amostra suficiente.")
    else:
        total = len(avaliacoes)

        linhas = [
            {
                "Mercado": "Resultado 1X2",
                "Acertos": sum(a["acertou"] for a in avaliacoes),
                "Total": total,
            },
            {
                "Mercado": "+1.5 gols",
                "Acertos": sum(a["over15_ok"] for a in avaliacoes),
                "Total": total,
            },
            {
                "Mercado": "+2.5 gols",
                "Acertos": sum(a["over25_ok"] for a in avaliacoes),
                "Total": total,
            },
            {
                "Mercado": "Ambas marcam",
                "Acertos": sum(a["btts_ok"] for a in avaliacoes),
                "Total": total,
            },
        ]

        for linha in linhas:
            linha["Taxa"] = linha["Acertos"] / max(1, linha["Total"])
            if linha["Taxa"] >= 0.68:
                linha["Leitura"] = "Forte"
            elif linha["Taxa"] >= 0.56:
                linha["Leitura"] = "Boa"
            elif linha["Taxa"] >= 0.48:
                linha["Leitura"] = "Instável"
            else:
                linha["Leitura"] = "Fraca"

        df_rank = pd.DataFrame(linhas).sort_values("Taxa", ascending=False)
        df_rank["Taxa"] = df_rank["Taxa"].map(pct)
        st.dataframe(df_rank, use_container_width=True, hide_index=True)

        melhor = df_rank.iloc[0]
        pior = df_rank.iloc[-1]

        st.success(f"Melhor mercado no recorte: {melhor['Mercado']} ({melhor['Taxa']}).")
        st.warning(f"Mercado mais fraco no recorte: {pior['Mercado']} ({pior['Taxa']}).")

st.caption(f"Atualizado na interface em {agora_br().strftime('%d/%m/%Y %H:%M:%S')} — horário de Brasília.")
