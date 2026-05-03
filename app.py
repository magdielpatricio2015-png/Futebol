import math
import html
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st


# ============================================================
# CONFIGURAÇÃO GERAL
# ============================================================

st.set_page_config(
    page_title="Analisador Futebol Pro 3.0",
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

# Base usada só quando há pouca amostra. O modelo vai corrigindo com os resultados reais.
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

HEADERS = {"User-Agent": "Mozilla/5.0 AnalisadorFutebolPro/3.0"}

MAX_GOLS = 10


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>
        .block-container { padding-top: .8rem; padding-bottom: 2rem; }
        .game-card {
            border: 1px solid rgba(150,150,150,.25);
            border-radius: 18px;
            padding: 14px 16px;
            margin-bottom: 12px;
            background: rgba(255,255,255,.045);
        }
        .game-title { font-size: 1.05rem; font-weight: 750; margin-bottom: 4px; }
        .muted { opacity: .72; font-size: .88rem; }
        .pill {
            display: inline-block;
            padding: 3px 9px;
            border-radius: 999px;
            border: 1px solid rgba(150,150,150,.35);
            font-size: .82rem;
            margin-right: 4px;
            margin-top: 5px;
        }
        .good { border-left: 5px solid #16a34a; }
        .medium { border-left: 5px solid #ca8a04; }
        .low { border-left: 5px solid #dc2626; }
        .live-box {
            border: 1px solid rgba(239,68,68,.45);
            border-radius: 18px;
            padding: 12px 14px;
            margin-bottom: 14px;
            background: rgba(239,68,68,.08);
        }
        @media (max-width: 700px) {
            .block-container { padding-left: .7rem; padding-right: .7rem; }
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
    return "".join(c for c in nome if not unicodedata.combining(c))


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
    lam = max(0.05, float(lam))
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


# ============================================================
# ESPN API
# ============================================================

@st.cache_data(ttl=45, show_spinner=False)
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


@st.cache_data(ttl=15, show_spinner=False)
def buscar_ao_vivo_rapido(liga):
    hoje = hoje_br()
    jogos = []
    logs = []

    for dia in [hoje - timedelta(days=1), hoje, hoje + timedelta(days=1)]:
        data, erro = buscar_scoreboard_data(liga, dia.isoformat())
        if erro:
            logs.append(erro)
        jogos.extend(extrair_jogos(data, liga))

    jogos = deduplicar(jogos)
    jogos.sort(
        key=lambda j: (
            0 if j.get("state") == "in" else 1 if j.get("state") == "pre" else 2,
            j.get("data") or agora_br(),
        )
    )
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
                "state": status.get("state", ""),
                "completed": bool(status.get("completed", False)),
                "status": status.get("detail") or status.get("shortDetail") or "",
            }
        )

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
# MODELO
# Melhorias:
# - amostra suavizada por liga
# - peso maior para jogos recentes
# - ajuste de empate
# - diagnóstico temporal sem vazamento
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
    jogos = [
        j for j in jogos_encerrados
        if j.get("completed") and j.get("placar_casa") is not None and j.get("data")
    ]
    jogos = sorted(jogos, key=lambda x: x.get("data") or agora_br())

    ratings = {}
    stats = {}

    total_home_gols = 0.0
    total_away_gols = 0.0
    total_peso = 0.0
    empates = 0.0

    for j in jogos:
        casa = j["casa"]
        fora = j["fora"]
        gc = int(j["placar_casa"])
        gf = int(j["placar_fora"])
        w = peso_recencia(j.get("data"), ref_dt)

        ratings.setdefault(casa, forca_inicial(casa))
        ratings.setdefault(fora, forca_inicial(fora))
        stats.setdefault(casa, novo_stats())
        stats.setdefault(fora, novo_stats())

        rc = ratings[casa]
        rf = ratings[fora]

        exp_casa = 1 / (1 + 10 ** ((rf - (rc + 58)) / 400))

        if gc > gf:
            real_casa = 1.0
            pontos_casa, pontos_fora = 3, 0
        elif gc == gf:
            real_casa = 0.5
            pontos_casa, pontos_fora = 1, 1
            empates += w
        else:
            real_casa = 0.0
            pontos_casa, pontos_fora = 0, 3

        margem = abs(gc - gf)
        k = (18 + min(16, margem * 5)) * (0.65 + 0.35 * w)
        delta = k * (real_casa - exp_casa)

        ratings[casa] = rc + delta
        ratings[fora] = rf - delta

        sc = stats[casa]
        sf = stats[fora]

        sc["jogos"] += 1
        sc["gf"] += gc * w
        sc["ga"] += gf * w
        sc["home_jogos"] += 1
        sc["home_gf"] += gc * w
        sc["home_ga"] += gf * w
        sc["peso_total"] += w
        sc["home_peso"] += w
        sc["pontos_recent"].append(pontos_casa)
        sc["gols_recent"].append(gc)

        sf["jogos"] += 1
        sf["gf"] += gf * w
        sf["ga"] += gc * w
        sf["away_jogos"] += 1
        sf["away_gf"] += gf * w
        sf["away_ga"] += gc * w
        sf["peso_total"] += w
        sf["away_peso"] += w
        sf["pontos_recent"].append(pontos_fora)
        sf["gols_recent"].append(gf)

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


def ajustar_empate(p_casa, p_empate, p_fora, taxa_empate_liga, diff_elo):
    # Aumenta empate quando forças são próximas; reduz em jogos muito desnivelados.
    proximidade = max(0, 1 - abs(diff_elo) / 260)
    alvo_empate = clamp(taxa_empate_liga + 0.055 * proximidade, 0.18, 0.36)

    mistura = 0.22
    novo_empate = p_empate * (1 - mistura) + alvo_empate * mistura
    restante_antigo = max(1e-9, p_casa + p_fora)
    restante_novo = 1 - novo_empate

    return (
        p_casa / restante_antigo * restante_novo,
        novo_empate,
        p_fora / restante_antigo * restante_novo,
    )


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

    # Fallback forte quando a liga tem pouca amostra.
    if jogos_modelo < 12:
        diff_base = forca_inicial(casa) - forca_inicial(fora)
        fallback_casa = 1.35 + (diff_base / 400) * 0.33
        fallback_fora = 1.05 - (diff_base / 400) * 0.26
        peso = jogos_modelo / 12
        gols_casa = gols_casa * peso + fallback_casa * (1 - peso)
        gols_fora = gols_fora * peso + fallback_fora * (1 - peso)

    gols_casa = clamp(gols_casa, 0.35, 3.60)
    gols_fora = clamp(gols_fora, 0.25, 3.25)

    p_casa = p_empate = p_fora = 0.0
    over15 = over25 = btts = under35 = 0.0
    placares = []

    for i in range(MAX_GOLS + 1):
        for k in range(MAX_GOLS + 1):
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
            if i + k <= 3:
                under35 += p
            if i > 0 and k > 0:
                btts += p

    total = p_casa + p_empate + p_fora
    if total:
        p_casa, p_empate, p_fora = p_casa / total, p_empate / total, p_fora / total

    p_casa, p_empate, p_fora = ajustar_empate(
        p_casa, p_empate, p_fora, contexto.get("taxa_empate", 0.27), diff_elo
    )

    probs = {"Casa": p_casa, "Empate": p_empate, "Fora": p_fora}
    ordenadas = sorted(probs.items(), key=lambda x: x[1], reverse=True)
    palpite, p_top = ordenadas[0]
    p_segundo = ordenadas[1][1]

    jogos_times = sc["jogos"] + sf["jogos"]
    qualidade = clamp((jogos_modelo / 42) * 0.52 + (jogos_times / 16) * 0.48, 0, 1)

    margem = p_top - p_segundo
    if qualidade >= 0.66 and p_top >= 0.60 and margem >= 0.13:
        confianca, conf_class = "Alta", "good"
    elif qualidade >= 0.45 and p_top >= 0.535 and margem >= 0.075:
        confianca, conf_class = "Média", "medium"
    else:
        confianca, conf_class = "Baixa", "low"

    # Sugestão: evitar forçar 1X2 quando o valor estatístico é baixo.
    melhor_mercado = "1X2"
    melhor_mercado_prob = p_top
    mercados = [
        ("+1.5 gols", over15),
        ("Under 3.5 gols", under35),
        ("Ambas marcam", btts),
        ("+2.5 gols", over25),
    ]
    for nome, prob in mercados:
        if prob >= melhor_mercado_prob + 0.08 and prob >= 0.58:
            melhor_mercado = nome
            melhor_mercado_prob = prob

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
        "under35": under35,
        "btts": btts,
        "elo_casa": elo_casa,
        "elo_fora": elo_fora,
        "diff_elo": diff_elo,
        "palpite": palpite,
        "prob_palpite": p_top,
        "confianca": confianca,
        "conf_class": conf_class,
        "qualidade": qualidade,
        "placares_top": sorted(placares, reverse=True)[:4],
        "jogos_modelo": jogos_modelo,
        "amostra_times": jogos_times,
        "melhor_mercado": melhor_mercado,
        "melhor_mercado_prob": melhor_mercado_prob,
    }


def explicar_erro(jogo, r, real, acertou):
    if acertou:
        if r["confianca"] == "Alta":
            return "Acerto forte: havia margem, probabilidade e amostra suficientes."
        return "Acerto com cautela: o modelo apontava vantagem, mas sem margem grande."

    if r["confianca"] == "Baixa":
        return "Erro aceitável: o próprio modelo marcava baixa confiança."

    if real == "Empate":
        return "Erro por empate: quando as forças são próximas, o empate tende a ser o maior vilão do 1X2."

    if r["palpite"] == "Casa" and real == "Fora":
        return "Mandante provavelmente foi superestimado; veja forma recente, escalação e calendário."
    if r["palpite"] == "Fora" and real == "Casa":
        return "Visitante provavelmente foi superestimado; mando e contexto podem ter pesado mais."

    return "Erro normal do modelo; vale revisar amostra, forma recente e notícias do jogo."


def avaliar_jogo_com_contexto_anterior(jogo, historico_antes):
    real = resultado_real(jogo)
    if not real or not jogo.get("data"):
        return None

    contexto_pre = construir_contexto(historico_antes, ref_dt=jogo["data"] - timedelta(minutes=1))
    r = prever(jogo["casa"], jogo["fora"], contexto_pre)

    probs = {"Casa": r["p_casa"], "Empate": r["p_empate"], "Fora": r["p_fora"]}
    brier = sum((probs[k] - (1 if k == real else 0)) ** 2 for k in probs) / 3

    total_gols = jogo["placar_casa"] + jogo["placar_fora"]
    real_over15 = total_gols >= 2
    real_over25 = total_gols >= 3
    real_under35 = total_gols <= 3
    real_btts = jogo["placar_casa"] > 0 and jogo["placar_fora"] > 0

    return {
        "jogo": jogo,
        "prev": r,
        "real": real,
        "acertou": r["palpite"] == real,
        "brier": brier,
        "over15_ok": (r["over15"] >= 0.56) == real_over15,
        "over25_ok": (r["over25"] >= 0.54) == real_over25,
        "under35_ok": (r["under35"] >= 0.58) == real_under35,
        "btts_ok": (r["btts"] >= 0.54) == real_btts,
        "explicacao": explicar_erro(jogo, r, real, r["palpite"] == real),
    }


def backtest_temporal(jogos_hist, limite=70, janela_treino=120):
    encerrados = [
        j for j in jogos_hist
        if j.get("completed") and j.get("placar_casa") is not None and j.get("data")
    ]
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
# UI
# ============================================================

def card_jogo(jogo, contexto):
    r = prever(jogo["casa"], jogo["fora"], contexto)

    nome_palpite = {"Casa": jogo["casa"], "Fora": jogo["fora"], "Empate": "Empate"}[r["palpite"]]
    placar = ""
    if jogo.get("placar_casa") is not None:
        placar = f" — {jogo['placar_casa']} x {jogo['placar_fora']}"

    css_extra = "live-box" if jogo.get("state") == "in" else f"game-card {r['conf_class']}"

    st.markdown(
        f"""
        <div class="{css_extra}">
            <div class="game-title">{esc(jogo['casa'])} x {esc(jogo['fora'])}{esc(placar)}</div>
            <div class="muted">{esc(jogo['data_txt'])} • {esc(status_legivel(jogo))}</div>
            <span class="pill">Palpite 1X2: <b>{esc(nome_palpite)}</b></span>
            <span class="pill">Prob.: <b>{esc(pct(r['prob_palpite']))}</b></span>
            <span class="pill">Confiança: <b>{esc(r['confianca'])}</b></span>
            <span class="pill">Melhor mercado: <b>{esc(r['melhor_mercado'])} {esc(pct(r['melhor_mercado_prob']))}</b></span>
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

        g1, g2, g3, g4 = st.columns(4)
        g1.metric("+1.5 gols", pct(r["over15"]))
        g2.metric("+2.5 gols", pct(r["over25"]))
        g3.metric("Under 3.5", pct(r["under35"]))
        g4.metric("Ambas marcam", pct(r["btts"]))

        ptxt = ", ".join([f"{i}x{k} ({pct(p)})" for p, i, k in r["placares_top"]])
        st.caption(f"Placares mais prováveis: {ptxt}")
        st.caption(
            f"Base: {r['jogos_modelo']} jogos. Amostra dos times: {r['amostra_times']} jogos. "
            f"Qualidade: {pct(r['qualidade'])}. Elo ajustado: {r['elo_casa']:.0f} x {r['elo_fora']:.0f}."
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
                "Palpite 1X2": nome_palpite,
                "Prob.": pct(r["prob_palpite"]),
                "Conf.": r["confianca"],
                "Melhor mercado": r["melhor_mercado"],
                "Prob. mercado": pct(r["melhor_mercado_prob"]),
                "+1.5": pct(r["over15"]),
                "+2.5": pct(r["over25"]),
                "U3.5": pct(r["under35"]),
                "Ambas": pct(r["btts"]),
            }
        )
    return pd.DataFrame(linhas)


def render_ao_vivo(liga, contexto, busca="", somente_confianca=False):
    jogos_live, logs = buscar_ao_vivo_rapido(liga)

    if busca.strip():
        b = normalizar_nome(busca)
        jogos_live = [
            j for j in jogos_live
            if b in normalizar_nome(j["casa"]) or b in normalizar_nome(j["fora"])
        ]

    if somente_confianca:
        jogos_live = [
            j for j in jogos_live
            if prever(j["casa"], j["fora"], contexto)["confianca"] in ("Média", "Alta")
        ]

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
            card_jogo(jogo, contexto)

    st.subheader("🕒 Próximos jogos")
    if not futuros:
        st.caption("Nenhum próximo jogo encontrado na janela rápida.")
    else:
        for jogo in futuros[:14]:
            card_jogo(jogo, contexto)

    with st.expander("✅ Encerrados recentes"):
        if not encerrados:
            st.caption("Nenhum encerrado recente.")
        else:
            for jogo in encerrados[:12]:
                card_jogo(jogo, contexto)


# ============================================================
# APP
# ============================================================

st.title("⚽ Analisador Futebol Pro 3.0")
st.caption("Modelo com Elo, Poisson calibrado, recência, ajuste de empate e diagnóstico temporal sem vazamento.")

with st.sidebar:
    st.header("Configurações")

    liga_nome = st.selectbox("Competição", list(COMPETICOES.keys()))
    liga = COMPETICOES[liga_nome]

    modo = st.radio(
        "Jogos",
        ["Hoje e próximos", "Ao vivo + 48h", "Últimos resultados", "Período personalizado"],
        index=0,
    )

    dias_historico = st.slider("Histórico usado pelo modelo", 30, 240, 120, step=15)
    limite_backtest = st.slider("Jogos no diagnóstico temporal", 20, 100, 60, step=10)

    somente_confianca = st.checkbox("Mostrar só confiança média/alta", value=False)
    busca = st.text_input("Filtrar time", placeholder="Ex.: Flamengo")

    st.divider()
    st.caption("Dica: previsões de confiança baixa são exibidas, mas devem ser evitadas no desafio.")

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

with st.spinner("Carregando jogos e calibrando modelo..."):
    jogos_hist, logs_hist = buscar_periodo(liga, hist_inicio.isoformat(), hist_fim.isoformat())
    contexto = construir_contexto(jogos_hist)
    jogos, logs_jogos = buscar_periodo(liga, inicio.isoformat(), fim.isoformat())

if busca.strip():
    b = normalizar_nome(busca)
    jogos = [j for j in jogos if b in normalizar_nome(j["casa"]) or b in normalizar_nome(j["fora"])]

if somente_confianca:
    jogos = [
        j for j in jogos
        if prever(j["casa"], j["fora"], contexto)["confianca"] in ("Média", "Alta")
    ]

aba_jogos, aba_diagnostico, aba_ranking = st.tabs(
    ["📋 Jogos e previsões", "🧪 Diagnóstico real", "🏆 Ranking de mercados"]
)

with aba_jogos:
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Jogos encontrados", len(jogos))
    m2.metric("Base do modelo", contexto["jogos"])
    m3.metric("Média casa", f"{contexto['liga_home']:.2f}")
    m4.metric("Média fora", f"{contexto['liga_away']:.2f}")
    m5.metric("Empate liga", pct(contexto["taxa_empate"]))

    if logs_jogos or logs_hist:
        with st.expander("Avisos de API"):
            for log in (logs_jogos + logs_hist)[:12]:
                st.write(log)

    st.info(
        "Use como análise estatística. Para mais acertibilidade, priorize: confiança média/alta, "
        "melhor mercado acima de 58% e boa amostra dos times."
    )

    if modo == "Ao vivo + 48h":

        @st.fragment(run_every="20s")
        def bloco_ao_vivo():
            render_ao_vivo(liga, contexto, busca, somente_confianca)

        bloco_ao_vivo()

    else:
        if not jogos:
            st.warning("Nenhum jogo encontrado para os filtros.")
        else:
            df = tabela_resumo(jogos, contexto)
            st.dataframe(df, use_container_width=True, hide_index=True)

            st.subheader("Cards para celular")
            for jogo in jogos:
                card_jogo(jogo, contexto)

with aba_diagnostico:
    st.subheader("Diagnóstico temporal dos últimos resultados")
    st.caption(
        "Aqui o app simula como teria previsto cada jogo usando apenas partidas anteriores a ele. "
        "Isso evita diagnóstico artificialmente otimista."
    )

    avaliacoes = backtest_temporal(jogos_hist, limite=limite_backtest, janela_treino=dias_historico)

    if not avaliacoes:
        st.warning("Ainda não há jogos encerrados suficientes para um diagnóstico temporal confiável.")
    else:
        total = len(avaliacoes)
        acertos = sum(a["acertou"] for a in avaliacoes)
        taxa = acertos / total if total else 0
        brier_medio = sum(a["brier"] for a in avaliacoes) / total
        altas_medias = [a for a in avaliacoes if a["prev"]["confianca"] in ("Média", "Alta")]
        taxa_filtrada = (
            sum(a["acertou"] for a in altas_medias) / len(altas_medias)
            if altas_medias else 0
        )

        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Jogos avaliados", total)
        d2.metric("Acertos 1X2", acertos, pct(taxa))
        d3.metric("Média/alta conf.", len(altas_medias), pct(taxa_filtrada))
        d4.metric("Brier médio", f"{brier_medio:.3f}")

        filtro = st.radio("Mostrar", ["Todos", "Só acertos", "Só erros", "Só média/alta"], horizontal=True)

        lista = avaliacoes
        if filtro == "Só acertos":
            lista = [a for a in avaliacoes if a["acertou"]]
        elif filtro == "Só erros":
            lista = [a for a in avaliacoes if not a["acertou"]]
        elif filtro == "Só média/alta":
            lista = altas_medias

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
                    <span class="pill">Prob.: <b>{esc(pct(r['prob_palpite']))}</b></span>
                    <span class="pill">Confiança: <b>{esc(r['confianca'])}</b></span>
                    <span class="pill">Brier: <b>{a['brier']:.3f}</b></span>
                    <br><span class="muted">{esc(a['explicacao'])}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

with aba_ranking:
    st.subheader("Ranking dos mercados")
    st.caption("Calculado com backtest temporal. Mostra onde o modelo está performando melhor no recorte.")

    avaliacoes = backtest_temporal(jogos_hist, limite=limite_backtest, janela_treino=dias_historico)

    if not avaliacoes:
        st.warning("Sem amostra suficiente.")
    else:
        total = len(avaliacoes)

        linhas = [
            {"Mercado": "Resultado 1X2", "Acertos": sum(a["acertou"] for a in avaliacoes), "Total": total},
            {"+": "", "Mercado": "+1.5 gols", "Acertos": sum(a["over15_ok"] for a in avaliacoes), "Total": total},
            {"Mercado": "+2.5 gols", "Acertos": sum(a["over25_ok"] for a in avaliacoes), "Total": total},
            {"Mercado": "Under 3.5 gols", "Acertos": sum(a["under35_ok"] for a in avaliacoes), "Total": total},
            {"Mercado": "Ambas marcam", "Acertos": sum(a["btts_ok"] for a in avaliacoes), "Total": total},
        ]

        for linha in linhas:
            linha.pop("+", None)
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

st.caption(
    f"Atualizado na interface em {agora_br().strftime('%d/%m/%Y %H:%M:%S')} — horário de Brasília."
)