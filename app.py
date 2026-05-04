
import math
import html
import re
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st


# ============================================================
# ANALISADOR FUTEBOL PRO 5.0
# ESPN + Elo + Poisson + ajuste ao vivo + odds + xG + contexto
# ============================================================

st.set_page_config(
    page_title="Analisador Futebol Pro 5.0",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)

TZ_BR = ZoneInfo("America/Sao_Paulo")
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
HEADERS = {"User-Agent": "Mozilla/5.0 AnalisadorFutebolPro/5.0"}
MAX_GOLS = 10

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
    "Flamengo": 86, "Palmeiras": 85, "Botafogo": 81, "Atlético-MG": 80, "Atletico-MG": 80,
    "São Paulo": 78, "Sao Paulo": 78, "Fluminense": 78, "Grêmio": 77, "Gremio": 77,
    "Internacional": 77, "Corinthians": 76, "Cruzeiro": 75, "Bahia": 74, "Fortaleza": 73,
    "Vasco": 72, "Santos": 72, "Sport": 68, "Ceará": 69, "Ceara": 69, "Vitória": 69,
    "Vitoria": 69, "Manchester City": 91, "Arsenal": 88, "Liverpool": 88, "Chelsea": 82,
    "Tottenham Hotspur": 80, "Real Madrid": 90, "Barcelona": 88, "Atlético Madrid": 84,
    "Atletico Madrid": 84, "Bayern Munich": 88, "Borussia Dortmund": 82,
    "Bayer Leverkusen": 84, "Inter Milan": 86, "Juventus": 82, "PSG": 88,
}

CLASSICOS = [
    ("Flamengo", "Vasco"), ("Flamengo", "Fluminense"), ("Flamengo", "Botafogo"),
    ("Corinthians", "Palmeiras"), ("Corinthians", "São Paulo"), ("Corinthians", "Santos"),
    ("Palmeiras", "São Paulo"), ("São Paulo", "Santos"),
    ("Grêmio", "Internacional"), ("Atletico-MG", "Cruzeiro"), ("Atlético-MG", "Cruzeiro"),
    ("Bahia", "Vitória"), ("Ceará", "Fortaleza"),
    ("Real Madrid", "Barcelona"), ("Manchester United", "Liverpool"),
    ("Arsenal", "Tottenham Hotspur"), ("Inter Milan", "AC Milan"),
]

JOGADORES_CHAVE = {
    "Flamengo": {
        "Giorgian de Arrascaeta": {"ataque": -0.16, "defesa": 0.00},
        "Erick Pulgar": {"ataque": -0.03, "defesa": -0.11},
        "Pedro": {"ataque": -0.13, "defesa": 0.00},
        "Bruno Henrique": {"ataque": -0.08, "defesa": 0.00},
    },
    "Palmeiras": {
        "Raphael Veiga": {"ataque": -0.10, "defesa": 0.00},
        "Gustavo Gómez": {"ataque": -0.02, "defesa": -0.10},
    },
    "Fluminense": {
        "Ganso": {"ataque": -0.09, "defesa": 0.00},
        "Thiago Silva": {"ataque": 0.00, "defesa": -0.12},
    },
}

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
    </style>
    """,
    unsafe_allow_html=True,
)


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


def nomes_iguais(a, b):
    return normalizar_nome(a) == normalizar_nome(b)


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


def eh_classico(casa, fora):
    c, f = normalizar_nome(casa), normalizar_nome(fora)
    for a, b in CLASSICOS:
        if {c, f} == {normalizar_nome(a), normalizar_nome(b)}:
            return True
    return False


def extrair_minuto(status):
    txt = str(status or "")
    m = re.search(r"(\d+)\s*'\s*\+?\s*(\d+)?", txt)
    if m:
        return clamp(int(m.group(1)) + int(m.group(2) or 0), 1, 120)
    m = re.search(r"\b(\d{1,3})\b", txt)
    if m:
        return clamp(int(m.group(1)), 1, 120)
    if "half" in txt.lower() or "intervalo" in txt.lower():
        return 45
    return 0


def normalizar_probs(p_casa, p_empate, p_fora):
    total = max(1e-9, p_casa + p_empate + p_fora)
    return p_casa / total, p_empate / total, p_fora / total


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
    jogos, logs = [], []
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
    jogos, logs = [], []
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


@st.cache_data(ttl=1800, show_spinner=False)
def buscar_odds_theoddsapi(api_key, sport_key="soccer_brazil_campeonato", regions="us,eu", markets="h2h"):
    if not api_key:
        return [], "Sem chave da TheOddsAPI."
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {"apiKey": api_key, "regions": regions, "markets": markets, "oddsFormat": "decimal"}
    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        return r.json(), ""
    except requests.RequestException as e:
        return [], f"Erro TheOddsAPI: {e}"


def prob_implicita_decimal(odd):
    try:
        odd = float(odd)
        if odd <= 1:
            return None
        return 1 / odd
    except Exception:
        return None


def encontrar_odds_jogo(jogo, odds_data):
    if not odds_data:
        return None
    casa, fora = normalizar_nome(jogo["casa"]), normalizar_nome(jogo["fora"])
    for ev in odds_data:
        home = normalizar_nome(ev.get("home_team", ""))
        away = normalizar_nome(ev.get("away_team", ""))
        if not ((casa in home or home in casa) and (fora in away or away in fora)):
            continue
        probs = {"Casa": [], "Empate": [], "Fora": []}
        for book in ev.get("bookmakers", []):
            for market in book.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                for out in market.get("outcomes", []):
                    name = normalizar_nome(out.get("name", ""))
                    p = prob_implicita_decimal(out.get("price"))
                    if p is None:
                        continue
                    if name in home or home in name:
                        probs["Casa"].append(p)
                    elif name in away or away in name:
                        probs["Fora"].append(p)
                    elif "draw" in name or "empate" in name:
                        probs["Empate"].append(p)
        if all(probs[k] for k in probs):
            med = {k: sum(v) / len(v) for k, v in probs.items()}
            med["Casa"], med["Empate"], med["Fora"] = normalizar_probs(med["Casa"], med["Empate"], med["Fora"])
            return med
    return None


def carregar_xg_upload(uploaded_file):
    if uploaded_file is None:
        return {}
    try:
        df = pd.read_csv(uploaded_file)
        cols = {normalizar_nome(c): c for c in df.columns}
        col_time = cols.get("time") or cols.get("team") or cols.get("equipe")
        col_xg = cols.get("xg")
        col_xga = cols.get("xga")
        if not (col_time and col_xg and col_xga):
            st.warning("CSV xG precisa ter colunas: time/team/equipe, xg, xga.")
            return {}
        out = {}
        for _, row in df.iterrows():
            time = nome_limpo(row[col_time])
            out[normalizar_nome(time)] = {
                "time": time,
                "xg": float(row[col_xg]),
                "xga": float(row[col_xga]),
            }
        return out
    except Exception as e:
        st.warning(f"Não foi possível ler CSV xG: {e}")
        return {}


def novo_stats():
    return {
        "jogos": 0,
        "gf": 0.0, "ga": 0.0,
        "home_jogos": 0, "home_gf": 0.0, "home_ga": 0.0,
        "away_jogos": 0, "away_gf": 0.0, "away_ga": 0.0,
        "pontos_recent": [], "gols_recent": [],
        "peso_total": 0.0, "home_peso": 0.0, "away_peso": 0.0,
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
        "ratings": ratings, "stats": stats, "jogos": len(jogos), "peso_jogos": total_peso,
        "liga_home": clamp(liga_home, 0.85, 2.25),
        "liga_away": clamp(liga_away, 0.60, 1.85),
        "taxa_empate": clamp(taxa_empate, 0.18, 0.34),
        "ref_dt": ref_dt,
    }


def media_suave(valor, peso, media_liga, peso_liga=6.5):
    return (valor + media_liga * peso_liga) / max(0.1, peso + peso_liga)


def matriz_poisson(gols_casa, gols_fora, gc_base=0, gf_base=0, max_gols=MAX_GOLS):
    p_casa = p_empate = p_fora = 0.0
    over15 = over25 = btts = under35 = 0.0
    placares = []
    for i in range(max_gols + 1):
        for k in range(max_gols + 1):
            final_casa, final_fora = gc_base + i, gf_base + k
            p = poisson(i, gols_casa) * poisson(k, gols_fora)
            placares.append((p, final_casa, final_fora))
            if final_casa > final_fora:
                p_casa += p
            elif final_casa == final_fora:
                p_empate += p
            else:
                p_fora += p
            total_gols = final_casa + final_fora
            if total_gols >= 2: over15 += p
            if total_gols >= 3: over25 += p
            if total_gols <= 3: under35 += p
            if final_casa > 0 and final_fora > 0: btts += p
    p_casa, p_empate, p_fora = normalizar_probs(p_casa, p_empate, p_fora)
    return p_casa, p_empate, p_fora, over15, over25, under35, btts, sorted(placares, reverse=True)[:5]


def ajustar_empate(p_casa, p_empate, p_fora, taxa_empate_liga, diff_elo, classico=False):
    proximidade = max(0, 1 - abs(diff_elo) / 260)
    extra_classico = 0.035 if classico else 0.0
    alvo_empate = clamp(taxa_empate_liga + 0.055 * proximidade + extra_classico, 0.18, 0.39)
    mistura = 0.24 if classico else 0.20
    novo_empate = p_empate * (1 - mistura) + alvo_empate * mistura
    restante_antigo = max(1e-9, p_casa + p_fora)
    restante_novo = 1 - novo_empate
    return p_casa / restante_antigo * restante_novo, novo_empate, p_fora / restante_antigo * restante_novo


def aplicar_regularizacao(p_casa, p_empate, p_fora, peso=0.08):
    return (
        p_casa * (1 - peso) + (1 / 3) * peso,
        p_empate * (1 - peso) + (1 / 3) * peso,
        p_fora * (1 - peso) + (1 / 3) * peso,
    )


def aplicar_xg(casa, fora, gols_casa, gols_fora, xg_data, liga_home, liga_away, peso_xg):
    if not xg_data or peso_xg <= 0:
        return gols_casa, gols_fora, "Sem xG"
    xc = xg_data.get(normalizar_nome(casa))
    xf = xg_data.get(normalizar_nome(fora))
    if not (xc and xf):
        return gols_casa, gols_fora, "xG parcial/ausente"

    xg_gc = liga_home * (xc["xg"] / max(0.1, liga_home)) * (xf["xga"] / max(0.1, liga_home))
    xg_gf = liga_away * (xf["xg"] / max(0.1, liga_away)) * (xc["xga"] / max(0.1, liga_away))
    gols_casa = gols_casa * (1 - peso_xg) + xg_gc * peso_xg
    gols_fora = gols_fora * (1 - peso_xg) + xg_gf * peso_xg
    return gols_casa, gols_fora, "xG aplicado"


def aplicar_desfalques(casa, fora, gols_casa, gols_fora, desfalques_texto, peso_desfalque):
    if not desfalques_texto or peso_desfalque <= 0:
        return gols_casa, gols_fora, "Sem desfalques"
    linhas = [l.strip() for l in desfalques_texto.splitlines() if l.strip()]
    log = []
    for linha in linhas:
        partes = [p.strip() for p in linha.split(";")]
        if len(partes) >= 4:
            time, jogador, tipo, impacto = partes[:4]
            try:
                impacto = float(impacto) * peso_desfalque
            except Exception:
                continue
        else:
            txt = normalizar_nome(linha)
            achou = False
            for time_base, jogadores in JOGADORES_CHAVE.items():
                for jogador, imp in jogadores.items():
                    if normalizar_nome(jogador) in txt:
                        time, tipo, impacto = time_base, "ataque", imp["ataque"] * peso_desfalque
                        achou = True
                        break
                if achou:
                    break
            if not achou:
                continue

        if nomes_iguais(time, casa):
            if "def" in normalizar_nome(tipo):
                gols_fora *= 1 + abs(impacto)
            else:
                gols_casa *= 1 + impacto
            log.append(f"{time}: {jogador}")
        elif nomes_iguais(time, fora):
            if "def" in normalizar_nome(tipo):
                gols_casa *= 1 + abs(impacto)
            else:
                gols_fora *= 1 + impacto
            log.append(f"{time}: {jogador}")
    return clamp(gols_casa, 0.15, 4.2), clamp(gols_fora, 0.15, 4.0), ", ".join(log) if log else "Desfalques não casaram"


def prever(casa, fora, contexto, xg_data=None, odds_jogo=None, desfalques_texto="", params=None):
    params = params or {}
    casa, fora = nome_limpo(casa), nome_limpo(fora)
    ratings, stats = contexto.get("ratings", {}), contexto.get("stats", {})
    jogos_modelo = contexto.get("jogos", 0)
    liga_home, liga_away = contexto.get("liga_home", 1.35), contexto.get("liga_away", 1.05)
    classico = eh_classico(casa, fora)

    elo_casa = ratings.get(casa, forca_inicial(casa))
    elo_fora = ratings.get(fora, forca_inicial(fora))
    sc, sf = stats.get(casa, novo_stats()), stats.get(fora, novo_stats())

    home_gf = media_suave(sc["home_gf"], sc["home_peso"], liga_home)
    home_ga = media_suave(sc["home_ga"], sc["home_peso"], liga_away)
    away_gf = media_suave(sf["away_gf"], sf["away_peso"], liga_away)
    away_ga = media_suave(sf["away_ga"], sf["away_peso"], liga_home)

    atk_casa, def_fora = home_gf / liga_home, away_ga / liga_home
    atk_fora, def_casa = away_gf / liga_away, home_ga / liga_away

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

    if classico:
        gols_casa *= 0.94
        gols_fora *= 0.94

    gols_casa, gols_fora, xg_status = aplicar_xg(
        casa, fora, gols_casa, gols_fora, xg_data, liga_home, liga_away, params.get("peso_xg", 0.25)
    )

    gols_casa, gols_fora, desfalques_status = aplicar_desfalques(
        casa, fora, gols_casa, gols_fora, desfalques_texto, params.get("peso_desfalque", 1.0)
    )

    gols_casa = clamp(gols_casa, 0.25, 3.80)
    gols_fora = clamp(gols_fora, 0.20, 3.50)

    p_casa, p_empate, p_fora, over15, over25, under35, btts, placares = matriz_poisson(gols_casa, gols_fora)
    p_casa, p_empate, p_fora = ajustar_empate(
        p_casa, p_empate, p_fora, contexto.get("taxa_empate", 0.27), diff_elo, classico
    )
    p_casa, p_empate, p_fora = aplicar_regularizacao(
        p_casa, p_empate, p_fora, params.get("regularizacao", 0.08)
    )

    odds_status = "Sem odds"
    if odds_jogo:
        peso_odds = params.get("peso_odds", 0.25)
        p_casa = p_casa * (1 - peso_odds) + odds_jogo["Casa"] * peso_odds
        p_empate = p_empate * (1 - peso_odds) + odds_jogo["Empate"] * peso_odds
        p_fora = p_fora * (1 - peso_odds) + odds_jogo["Fora"] * peso_odds
        odds_status = "Odds aplicadas"
    p_casa, p_empate, p_fora = normalizar_probs(p_casa, p_empate, p_fora)

    probs = {"Casa": p_casa, "Empate": p_empate, "Fora": p_fora}
    ordenadas = sorted(probs.items(), key=lambda x: x[1], reverse=True)
    palpite, p_top = ordenadas[0]
    p_segundo = ordenadas[1][1]

    jogos_times = sc["jogos"] + sf["jogos"]
    qualidade = clamp(
        (jogos_modelo / 42) * 0.45 +
        (jogos_times / 16) * 0.35 +
        (0.10 if odds_jogo else 0) +
        (0.10 if xg_status == "xG aplicado" else 0),
        0, 1
    )
    margem = p_top - p_segundo

    if qualidade >= 0.68 and p_top >= 0.60 and margem >= 0.13 and not classico:
        confianca, conf_class = "Alta", "good"
    elif qualidade >= 0.46 and p_top >= 0.535 and margem >= 0.075:
        confianca, conf_class = "Média", "medium"
    else:
        confianca, conf_class = "Baixa", "low"

    melhor_mercado = "1X2"
    melhor_mercado_prob = p_top
    for nome, prob in [("+1.5 gols", over15), ("Under 3.5 gols", under35), ("Ambas marcam", btts), ("+2.5 gols", over25)]:
        if prob >= melhor_mercado_prob + 0.08 and prob >= 0.58:
            melhor_mercado, melhor_mercado_prob = nome, prob

    return {
        "casa": casa, "fora": fora, "gols_casa": gols_casa, "gols_fora": gols_fora,
        "p_casa": p_casa, "p_empate": p_empate, "p_fora": p_fora,
        "over15": over15, "over25": over25, "under35": under35, "btts": btts,
        "elo_casa": elo_casa, "elo_fora": elo_fora, "diff_elo": diff_elo,
        "palpite": palpite, "prob_palpite": p_top,
        "confianca": confianca, "conf_class": conf_class, "qualidade": qualidade,
        "placares_top": placares, "jogos_modelo": jogos_modelo, "amostra_times": jogos_times,
        "melhor_mercado": melhor_mercado, "melhor_mercado_prob": melhor_mercado_prob,
        "classico": classico, "xg_status": xg_status, "odds_status": odds_status,
        "desfalques_status": desfalques_status,
    }


def aplicar_vermelhos(lam_casa, lam_fora, vermelho_casa=0, vermelho_fora=0):
    if vermelho_casa:
        lam_casa *= 0.72 ** vermelho_casa
        lam_fora *= 1.22 ** vermelho_casa
    if vermelho_fora:
        lam_fora *= 0.72 ** vermelho_fora
        lam_casa *= 1.22 ** vermelho_fora
    return clamp(lam_casa, 0.02, 4.5), clamp(lam_fora, 0.02, 4.5)


def aplicar_pressao_live(lam_casa, lam_fora, pressao_casa=0, pressao_fora=0):
    lam_casa *= 1 + clamp(pressao_casa, -5, 5) * 0.035
    lam_fora *= 1 + clamp(pressao_fora, -5, 5) * 0.035
    return clamp(lam_casa, 0.02, 4.5), clamp(lam_fora, 0.02, 4.5)


def ajustar_ao_vivo(jogo, r_pre, vermelho_casa=0, vermelho_fora=0, pressao_casa=0, pressao_fora=0):
    if jogo.get("state") != "in":
        return r_pre

    minuto = extrair_minuto(jogo.get("status", ""))
    if minuto <= 0:
        minuto = 45

    gc = int(jogo.get("placar_casa") or 0)
    gf = int(jogo.get("placar_fora") or 0)

    total_estimado = 96 if minuto <= 90 else 120
    restante = clamp((total_estimado - minuto) / 90, 0.02, 1.05)

    lam_casa = r_pre["gols_casa"] * restante
    lam_fora = r_pre["gols_fora"] * restante

    favorito = "Casa" if r_pre["p_casa"] >= r_pre["p_fora"] else "Fora"
    if favorito == "Casa" and gc < gf:
        lam_casa *= 1.12
        lam_fora *= 1.05
    elif favorito == "Fora" and gf < gc:
        lam_fora *= 1.12
        lam_casa *= 1.05

    lam_casa, lam_fora = aplicar_vermelhos(lam_casa, lam_fora, vermelho_casa, vermelho_fora)
    lam_casa, lam_fora = aplicar_pressao_live(lam_casa, lam_fora, pressao_casa, pressao_fora)

    p_casa, p_empate, p_fora, over15, over25, under35, btts, placares = matriz_poisson(
        lam_casa, lam_fora, gc_base=gc, gf_base=gf, max_gols=8
    )

    probs = {"Casa": p_casa, "Empate": p_empate, "Fora": p_fora}
    palpite, prob_palpite = max(probs.items(), key=lambda x: x[1])

    out = dict(r_pre)
    out.update({
        "gols_casa": lam_casa, "gols_fora": lam_fora,
        "p_casa": p_casa, "p_empate": p_empate, "p_fora": p_fora,
        "over15": over15, "over25": over25, "under35": under35, "btts": btts,
        "placares_top": placares,
        "palpite": palpite, "prob_palpite": prob_palpite,
        "confianca": "Ao vivo", "conf_class": "medium",
        "melhor_mercado": "Live 1X2", "melhor_mercado_prob": prob_palpite,
        "minuto_live": minuto, "placar_live": f"{gc}x{gf}",
        "live_status": f"Recalculado com minuto {minuto}, placar {gc}x{gf}, vermelhos {vermelho_casa}x{vermelho_fora}.",
    })
    return out


def explicar_erro(jogo, r, real, acertou):
    if acertou:
        return "Acerto forte." if r["confianca"] == "Alta" else "Acerto com cautela."
    if r.get("classico"):
        return "Erro em clássico: rivalidade aumenta empate, variância e reduz previsibilidade."
    if real == "Empate":
        return "Erro por empate: o 1X2 costuma sofrer quando as forças são próximas."
    if r["palpite"] == "Casa" and real == "Fora":
        return "Mandante provavelmente foi superestimado; revise desfalques, calendário e forma."
    if r["palpite"] == "Fora" and real == "Casa":
        return "Visitante provavelmente foi superestimado; mando e contexto podem ter pesado."
    return "Erro normal do modelo; revise amostra, xG, odds e notícias do jogo."


def avaliar_jogo_com_contexto_anterior(jogo, historico_antes, xg_data=None, params=None):
    real = resultado_real(jogo)
    if not real or not jogo.get("data"):
        return None
    contexto_pre = construir_contexto(historico_antes, ref_dt=jogo["data"] - timedelta(minutes=1))
    r = prever(jogo["casa"], jogo["fora"], contexto_pre, xg_data=xg_data, params=params)
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


def backtest_temporal(jogos_hist, limite=70, janela_treino=120, xg_data=None, params=None):
    encerrados = [j for j in jogos_hist if j.get("completed") and j.get("placar_casa") is not None and j.get("data")]
    encerrados = sorted(encerrados, key=lambda x: x["data"])
    avaliacoes = []
    for j in encerrados[-limite:]:
        inicio = j["data"] - timedelta(days=janela_treino)
        antes = [x for x in encerrados if inicio <= x["data"] < j["data"]]
        if len(antes) < 8:
            continue
        a = avaliar_jogo_com_contexto_anterior(j, antes, xg_data=xg_data, params=params)
        if a:
            avaliacoes.append(a)
    return avaliacoes


def card_jogo(jogo, contexto, xg_data, odds_data, desfalques_texto, params):
    odds_jogo = encontrar_odds_jogo(jogo, odds_data) if params.get("usar_odds") else None
    r_pre = prever(
        jogo["casa"], jogo["fora"], contexto, xg_data=xg_data, odds_jogo=odds_jogo,
        desfalques_texto=desfalques_texto, params=params
    )

    if jogo.get("state") == "in":
        with st.expander(f"🔴 Ajustes ao vivo: {jogo['casa']} x {jogo['fora']}", expanded=False):
            c1, c2, c3, c4 = st.columns(4)
            vc = c1.number_input("Vermelhos casa", 0, 3, 0, key=f"vc_{jogo['id']}")
            vf = c2.number_input("Vermelhos fora", 0, 3, 0, key=f"vf_{jogo['id']}")
            pc = c3.slider("Pressão casa", -5, 5, 0, key=f"pc_{jogo['id']}")
            pf = c4.slider("Pressão fora", -5, 5, 0, key=f"pf_{jogo['id']}")
        r = ajustar_ao_vivo(jogo, r_pre, vc, vf, pc, pf)
    else:
        r = r_pre

    nome_palpite = {"Casa": jogo["casa"], "Fora": jogo["fora"], "Empate": "Empate"}[r["palpite"]]
    placar = f" — {jogo['placar_casa']} x {jogo['placar_fora']}" if jogo.get("placar_casa") is not None else ""
    css_extra = "live-box" if jogo.get("state") == "in" else f"game-card {r['conf_class']}"

    st.markdown(
        f"""
        <div class="{css_extra}">
            <div class="game-title">{esc(jogo['casa'])} x {esc(jogo['fora'])}{esc(placar)}</div>
            <div class="muted">{esc(jogo['data_txt'])} • {esc(status_legivel(jogo))}</div>
            <span class="pill">Palpite: <b>{esc(nome_palpite)}</b></span>
            <span class="pill">Prob.: <b>{esc(pct(r['prob_palpite']))}</b></span>
            <span class="pill">Confiança: <b>{esc(r['confianca'])}</b></span>
            <span class="pill">Mercado: <b>{esc(r['melhor_mercado'])} {esc(pct(r['melhor_mercado_prob']))}</b></span>
            <span class="pill">Gols esp.: <b>{r['gols_casa']:.2f} x {r['gols_fora']:.2f}</b></span>
            <span class="pill">Contexto: <b>{'Clássico' if r['classico'] else 'Normal'}</b></span>
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
            f"Base: {r['jogos_modelo']} jogos. Amostra times: {r['amostra_times']}. "
            f"Qualidade: {pct(r['qualidade'])}. Elo: {r['elo_casa']:.0f} x {r['elo_fora']:.0f}."
        )
        st.caption(
            f"Fontes/contexto: {r['xg_status']} • {r['odds_status']} • Desfalques: {r['desfalques_status']}"
        )
        if r.get("live_status"):
            st.warning(r["live_status"])


def tabela_resumo(jogos, contexto, xg_data, odds_data, desfalques_texto, params):
    linhas = []
    for j in jogos:
        odds_jogo = encontrar_odds_jogo(j, odds_data) if params.get("usar_odds") else None
        r = prever(j["casa"], j["fora"], contexto, xg_data=xg_data, odds_jogo=odds_jogo, desfalques_texto=desfalques_texto, params=params)
        nome_palpite = {"Casa": j["casa"], "Fora": j["fora"], "Empate": "Empate"}[r["palpite"]]
        linhas.append({
            "Data": j["data_txt"], "Jogo": f"{j['casa']} x {j['fora']}", "Status": status_legivel(j),
            "Palpite 1X2": nome_palpite, "Prob.": pct(r["prob_palpite"]), "Conf.": r["confianca"],
            "Melhor mercado": r["melhor_mercado"], "Prob. mercado": pct(r["melhor_mercado_prob"]),
            "+1.5": pct(r["over15"]), "+2.5": pct(r["over25"]), "U3.5": pct(r["under35"]), "Ambas": pct(r["btts"]),
            "Contexto": "Clássico" if r["classico"] else "",
            "xG": r["xg_status"], "Odds": r["odds_status"],
        })
    return pd.DataFrame(linhas)


def render_ao_vivo(liga, contexto, busca, somente_confianca, xg_data, odds_data, desfalques_texto, params):
    jogos_live, logs = buscar_ao_vivo_rapido(liga)
    if busca.strip():
        b = normalizar_nome(busca)
        jogos_live = [j for j in jogos_live if b in normalizar_nome(j["casa"]) or b in normalizar_nome(j["fora"])]
    if somente_confianca:
        jogos_live = [
            j for j in jogos_live
            if prever(j["casa"], j["fora"], contexto, xg_data=xg_data, desfalques_texto=desfalques_texto, params=params)["confianca"] in ("Média", "Alta")
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
            card_jogo(jogo, contexto, xg_data, odds_data, desfalques_texto, params)

    st.subheader("🕒 Próximos jogos")
    if not futuros:
        st.caption("Nenhum próximo jogo encontrado na janela rápida.")
    else:
        for jogo in futuros[:14]:
            card_jogo(jogo, contexto, xg_data, odds_data, desfalques_texto, params)

    with st.expander("✅ Encerrados recentes"):
        for jogo in encerrados[:12]:
            card_jogo(jogo, contexto, xg_data, odds_data, desfalques_texto, params)


st.title("⚽ Analisador Futebol Pro 5.0")
st.caption("ESPN + Elo + Poisson calibrado + clássicos + xG opcional + odds opcional + desfalques + ajuste ao vivo.")

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
    st.subheader("Fontes extras")

    uploaded_xg = st.file_uploader("CSV xG opcional: time,xg,xga", type=["csv"])
    peso_xg = st.slider("Peso do xG", 0.0, 0.60, 0.25, step=0.05)

    usar_odds = st.checkbox("Usar odds TheOddsAPI", value=False)
    odds_key = st.text_input("TheOddsAPI key", type="password")
    sport_key = st.text_input("Sport key TheOddsAPI", value="soccer_brazil_campeonato")
    peso_odds = st.slider("Peso das odds", 0.0, 0.50, 0.25, step=0.05)

    st.divider()
    st.subheader("Contexto manual")
    st.caption("Formato: Time; Jogador; ataque/defesa; impacto. Ex.: Flamengo; Arrascaeta; ataque; -0.16")
    desfalques_texto = st.text_area("Desfalques / contexto", height=120)
    peso_desfalque = st.slider("Peso dos desfalques", 0.0, 1.50, 1.0, step=0.10)

    regularizacao = st.slider("Regularização contra excesso de confiança", 0.00, 0.20, 0.08, step=0.01)

    if st.button("🔄 Atualizar dados"):
        st.cache_data.clear()
        st.rerun()

params = {
    "usar_odds": usar_odds,
    "peso_odds": peso_odds,
    "peso_xg": peso_xg,
    "peso_desfalque": peso_desfalque,
    "regularizacao": regularizacao,
}

xg_data = carregar_xg_upload(uploaded_xg)

odds_data, erro_odds = ([], "")
if usar_odds:
    odds_data, erro_odds = buscar_odds_theoddsapi(odds_key, sport_key=sport_key)

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

with st.spinner("Carregando jogos, odds/xG e calibrando modelo..."):
    jogos_hist, logs_hist = buscar_periodo(liga, hist_inicio.isoformat(), hist_fim.isoformat())
    contexto = construir_contexto(jogos_hist)
    jogos, logs_jogos = buscar_periodo(liga, inicio.isoformat(), fim.isoformat())

if busca.strip():
    b = normalizar_nome(busca)
    jogos = [j for j in jogos if b in normalizar_nome(j["casa"]) or b in normalizar_nome(j["fora"])]

if somente_confianca:
    jogos = [
        j for j in jogos
        if prever(j["casa"], j["fora"], contexto, xg_data=xg_data, desfalques_texto=desfalques_texto, params=params)["confianca"] in ("Média", "Alta")
    ]

aba_jogos, aba_diagnostico, aba_ranking, aba_fontes = st.tabs(
    ["📋 Jogos e previsões", "🧪 Diagnóstico real", "🏆 Ranking de mercados", "🧩 Fontes extras"]
)

with aba_jogos:
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Jogos", len(jogos))
    m2.metric("Base modelo", contexto["jogos"])
    m3.metric("Média casa", f"{contexto['liga_home']:.2f}")
    m4.metric("Média fora", f"{contexto['liga_away']:.2f}")
    m5.metric("Empate liga", pct(contexto["taxa_empate"]))
    m6.metric("xG times", len(xg_data))

    if erro_odds:
        st.warning(erro_odds)
    if logs_jogos or logs_hist:
        with st.expander("Avisos de API"):
            for log in (logs_jogos + logs_hist)[:12]:
                st.write(log)

    st.info(
        "Use como análise estatística, não garantia. Agora o app pondera contexto: clássicos, desfalques, xG, odds e jogo ao vivo."
    )

    if modo == "Ao vivo + 48h":
        @st.fragment(run_every="20s")
        def bloco_ao_vivo():
            render_ao_vivo(liga, contexto, busca, somente_confianca, xg_data, odds_data, desfalques_texto, params)
        bloco_ao_vivo()
    else:
        if not jogos:
            st.warning("Nenhum jogo encontrado para os filtros.")
        else:
            df = tabela_resumo(jogos, contexto, xg_data, odds_data, desfalques_texto, params)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.subheader("Cards para celular")
            for jogo in jogos:
                card_jogo(jogo, contexto, xg_data, odds_data, desfalques_texto, params)

with aba_diagnostico:
    st.subheader("Diagnóstico temporal dos últimos resultados")
    st.caption("Simula como o app teria previsto cada jogo usando só partidas anteriores a ele.")
    avaliacoes = backtest_temporal(jogos_hist, limite=limite_backtest, janela_treino=dias_historico, xg_data=xg_data, params=params)

    if not avaliacoes:
        st.warning("Ainda não há jogos encerrados suficientes para diagnóstico confiável.")
    else:
        total = len(avaliacoes)
        acertos = sum(a["acertou"] for a in avaliacoes)
        taxa = acertos / total
        brier_medio = sum(a["brier"] for a in avaliacoes) / total
        altas_medias = [a for a in avaliacoes if a["prev"]["confianca"] in ("Média", "Alta")]
        taxa_filtrada = sum(a["acertou"] for a in altas_medias) / len(altas_medias) if altas_medias else 0

        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Jogos avaliados", total)
        d2.metric("Acertos 1X2", acertos, pct(taxa))
        d3.metric("Média/alta", len(altas_medias), pct(taxa_filtrada))
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
            j, r = a["jogo"], a["prev"]
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
    avaliacoes = backtest_temporal(jogos_hist, limite=limite_backtest, janela_treino=dias_historico, xg_data=xg_data, params=params)
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
            linha["Taxa"] = pct(linha["Taxa_num"])
            linha["Leitura"] = "Forte" if linha["Taxa_num"] >= 0.68 else "Boa" if linha["Taxa_num"] >= 0.58 else "Instável" if linha["Taxa_num"] >= 0.50 else "Fraca"
        df_rank = pd.DataFrame(linhas).sort_values("Taxa_num", ascending=False)
        melhor, pior = df_rank.iloc[0], df_rank.iloc[-1]
        st.dataframe(df_rank.drop(columns=["Taxa_num"]), use_container_width=True, hide_index=True)
        st.success(f"Melhor mercado no recorte: {melhor['Mercado']} ({melhor['Taxa']}).")
        st.warning(f"Mercado mais fraco no recorte: {pior['Mercado']} ({pior['Taxa']}).")

with aba_fontes:
    st.subheader("Como alimentar melhor o modelo")
    st.markdown(
        """
        **xG CSV:** envie um arquivo com colunas `time,xg,xga`, usando médias por jogo.

        Exemplo:

        ```csv
        time,xg,xga
        Flamengo,1.85,1.05
        Fluminense,1.40,1.30
        ```

        **Odds:** ative TheOddsAPI na barra lateral e configure o `sport_key`.  
        Para Brasileirão, normalmente use `soccer_brazil_campeonato`.

        **Desfalques/contexto:** use uma linha por jogador/evento:

        ```text
        Flamengo; Giorgian de Arrascaeta; ataque; -0.16
        Flamengo; Erick Pulgar; defesa; -0.11
        ```

        Impacto negativo em `ataque` reduz gols esperados do time.  
        Impacto negativo em `defesa` aumenta gols esperados do adversário.
        """
    )
    if xg_data:
        st.dataframe(pd.DataFrame(xg_data.values()), use_container_width=True, hide_index=True)

st.caption(f"Atualizado em {agora_br().strftime('%d/%m/%Y %H:%M:%S')} — horário de Brasília.")
