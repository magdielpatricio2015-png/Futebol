import math, re, unicodedata
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import pandas as pd, requests, streamlit as st

# ------- CONFIGURAÇÃO DA PÁGINA -------
st.set_page_config(page_title="Analisador Esportivo Pro 10.4", page_icon="⚽", layout="wide")

# ------- CONSTANTES -------
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
HEADERS = {"User-Agent": "AnalisadorEsportivoPro/10.4"}
MAX_GOLS = 10
RETRIES = 2

LIGAS = {
    "Brasileirão Série A": "bra.1", "Brasileirão Série B": "bra.2",
    "Copa do Brasil": "bra.copa_do_brasil", "Libertadores": "conmebol.libertadores",
    "Sul-Americana": "conmebol.sudamericana", "Premier League": "eng.1",
    "La Liga": "esp.1", "Serie A (Itália)": "ita.1", "Bundesliga": "ger.1",
    "Ligue 1": "fra.1", "Champions League": "uefa.champions", "Europa League": "uefa.europa",
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
    "man city": "manchester city", "man utd": "manchester united",
    "man united": "manchester united", "tottenham": "tottenham hotspur",
    "spurs": "tottenham hotspur", "psg": "paris saint-germain",
    "paris sg": "paris saint-germain", "inter": "inter milan",
    "internazionale": "inter milan", "atletico mineiro": "atletico-mg",
    "atletico mg": "atletico-mg", "vasco da gama": "vasco",
}

CLASSICOS = {
    tuple(sorted(["flamengo", "vasco"])), tuple(sorted(["flamengo", "fluminense"])),
    tuple(sorted(["flamengo", "botafogo"])), tuple(sorted(["palmeiras", "corinthians"])),
    tuple(sorted(["sao paulo", "corinthians"])), tuple(sorted(["sao paulo", "palmeiras"])),
    tuple(sorted(["gremio", "internacional"])), tuple(sorted(["atletico-mg", "cruzeiro"])),
    tuple(sorted(["real madrid", "barcelona"])), tuple(sorted(["manchester united", "manchester city"])),
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

# ------- ESTILOS -------
st.markdown("""
<style>
    .main { background-color: #ffffff; color: #111827; }
    .block-container { padding-top: 1rem; max-width: 1450px; }
    section[data-testid="stSidebar"] { background: #f1f5f9; }
    .hero {
        border: 1px solid #d7dce2; background: #f8fafc; border-radius: 8px;
        padding: 18px 20px; margin-bottom: 16px;
    }
    .hero h1 { margin: 0; font-size: 2rem; color: #111827; }
    .hero p { margin: 6px 0 0; color: #475569; }
    .card {
        border: 1px solid #d7dce2; border-radius: 8px; padding: 14px 16px;
        margin: 10px 0; background: #ffffff; transition: all 0.2s;
    }
    .card.good { border-left: 6px solid #16a34a; }
    .card.medium { border-left: 6px solid #eab308; }
    .card.low { border-left: 6px solid #dc2626; }
    .card.live { border-left: 6px solid #2563eb; }
    .card-title { font-size: 1.15rem; font-weight: 800; margin-bottom: 6px; }
    .muted { color: #64748b; font-size: .88rem; }
    .pill {
        display: inline-block; padding: 4px 9px; margin: 4px 5px 0 0;
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
    .form-badge {
        display: inline-block; width: 22px; height: 22px; line-height: 22px;
        text-align: center; border-radius: 4px; font-size: 0.8rem; font-weight: bold; margin-right: 2px;
    }
    .form-v { background: #16a34a; color: white; }
    .form-e { background: #eab308; color: white; }
    .form-d { background: #dc2626; color: white; }
    .live-badge {
        background: #dc2626; color: white; padding: 2px 8px; border-radius: 4px;
        font-weight: bold; font-size: 0.8rem; margin-left: 8px;
    }
    .finisher-name { font-weight: 700; }
    .finisher-prob { color: #2563eb; font-weight: 700; margin-left: 8px; }
    .team-info { display: flex; align-items: center; gap: 12px; margin-bottom: 6px; color: #475569; }
</style>
""", unsafe_allow_html=True)

# ------- SESSÃO -------
if "historico" not in st.session_state: st.session_state.historico = []
if "jogo_manual" not in st.session_state: st.session_state.jogo_manual = None

# ------- FUNÇÕES AUXILIARES -------
def hoje(): return datetime.now().date()
def nome_limpo(nome): return " ".join(str(nome or "").strip().split())
def normalizar(nome):
    nome = nome_limpo(nome).lower()
    nome = unicodedata.normalize("NFKD", nome)
    nome = "".join(c for c in nome if not unicodedata.combining(c))
    nome = re.sub(r"\b(fc|cf|sc|afc)\b", "", nome)
    nome = re.sub(r"[^a-z0-9\s\-]", "", nome)
    nome = re.sub(r"\s+", " ", nome).strip()
    return ALIASES.get(nome, nome)

def parse_dt(valor):
    if not valor: return None
    try: return datetime.fromisoformat(valor.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
    except: return None

def pct(x): return f"{100 * float(x):.1f}%"
def clamp(v, lo, hi): return max(lo, min(hi, v))
def poisson_pmf(k, media):
    media = max(0.03, float(media))
    return math.exp(-media) * (media ** k) / math.factorial(k)

def prob_over(media, linha):
    corte = int(math.floor(linha))
    return clamp(1 - sum(poisson_pmf(k, media) for k in range(corte + 1)), 0.0, 1.0)

def odd_justa(prob): return 1 / max(prob, 0.0001)
def valor_esperado(prob, odd): return prob * odd - 1 if odd > 1 else 0
def kelly_stake(prob, odd, banca, fracao=0.25):
    if odd <= 1 or banca <= 0: return 0.0
    b = odd - 1; q = 1 - prob
    return max(0.0, ((b * prob - q) / b) * fracao * banca)

# ------- API ESPN -------
def fetch_with_retry(url, params=None, retries=RETRIES):
    for i in range(retries):
        try:
            resp = requests.get(url, params=params or {}, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            return resp.json(), ""
        except requests.RequestException as exc:
            if i == retries - 1: return {}, f"Erro ESPN: {exc}"
    return {}, ""

@st.cache_data(ttl=240, show_spinner=False)
def buscar_scoreboard(liga_id, data_iso=None):
    params = {"limit": 300}
    if data_iso: params["dates"] = data_iso.replace("-", "")
    return fetch_with_retry(f"{ESPN_BASE}/{liga_id}/scoreboard", params)

@st.cache_data(ttl=3600, show_spinner=False)
def buscar_classificacao(liga_id):
    url = f"{ESPN_BASE}/{liga_id}/standings"
    payload, err = fetch_with_retry(url)
    if err or not payload: return {}
    tabela = {}
    try:
        for group in payload.get("children", []):
            for entry in group.get("standings", {}).get("entries", []):
                time_nome = entry.get("team", {}).get("displayName", "")
                time_nome_limpo = nome_limpo(time_nome)
                pos = entry.get("rank", 99)
                if pos == 99:
                    stats_list = entry.get("stats", [{}])
                    if stats_list: pos = int(stats_list[0].get("value", 99))
                tabela[time_nome_limpo] = {"posicao": pos, "time_original": time_nome}
    except: pass
    return tabela

def extrair_jogos(payload, liga_id):
    jogos = []
    for event in payload.get("events", []) or []:
        comps = event.get("competitions") or []
        if not comps: continue
        comp = comps[0]
        competidores = comp.get("competitors") or []
        if len(competidores) < 2: continue
        home = next((c for c in competidores if c.get("homeAway") == "home"), competidores[0])
        away = next((c for c in competidores if c.get("homeAway") == "away"), competidores[1])
        status_type = event.get("status", {}).get("type", {})
        def placar(c):
            try: return int(c.get("score", 0))
            except: return 0
        dt = parse_dt(event.get("date"))
        jogos.append({
            "id": str(event.get("id", "")), "liga": liga_id, "nome": event.get("name", ""),
            "home": nome_limpo(home.get("team", {}).get("displayName", "Casa")),
            "away": nome_limpo(away.get("team", {}).get("displayName", "Fora")),
            "placar_home": placar(home), "placar_away": placar(away),
            "placar": f"{placar(home)} - {placar(away)}",
            "data": dt, "data_txt": dt.strftime("%d/%m %H:%M") if dt else "Sem data",
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
        if erro: logs.append(erro)
        jogos.extend(extrair_jogos(payload, liga_id))
        dia += timedelta(days=1)
    vistos = {}
    for j in jogos:
        key = (j.get("id") or "", j["home"], j["away"], j["data_txt"])
        vistos[key] = j
    return sorted(vistos.values(), key=lambda x: x.get("data") or datetime.now()), logs

# ------- MODELO COM POSIÇÃO E FORMA -------
def forca_inicial(time, posicoes=None):
    nt = normalizar(time)
    if posicoes and time in posicoes:
        pos = posicoes[time].get("posicao", 10)
        return 2000 - (pos - 1) * (700 / 19)
    for nome, valor in FORCA_BASE.items():
        if normalizar(nome) == nt: return 1700 + valor * 2
    seed = sum(ord(c) for c in nome_limpo(time))
    return 1700 + (seed % 200) - 100

def novo_stats():
    return {"jogos": 0, "gf": 0.0, "ga": 0.0, "home_gf": 0.0, "home_ga": 0.0,
            "home_j": 0, "away_gf": 0.0, "away_ga": 0.0, "away_j": 0}

def construir_contexto(jogos, posicoes=None):
    encerrados = [j for j in jogos if j.get("completed")]
    ratings, stats = {}, {}
    total_home = total_away = empates = n = 0
    for j in sorted(encerrados, key=lambda x: x.get("data") or datetime.min):
        home, away = j["home"], j["away"]
        gh, ga = int(j["placar_home"]), int(j["placar_away"])
        ratings.setdefault(home, forca_inicial(home, posicoes))
        ratings.setdefault(away, forca_inicial(away, posicoes))
        stats.setdefault(home, novo_stats()); stats.setdefault(away, novo_stats())

        exp_home = 1 / (1 + 10 ** ((ratings[away] - (ratings[home] + 58)) / 400))
        real_home = 1.0 if gh > ga else 0.5 if gh == ga else 0.0
        delta = 22 * (real_home - exp_home)
        ratings[home] += delta; ratings[away] -= delta

        for st_team, gf, ga_val, is_home in [(stats[home], gh, ga, True), (stats[away], ga, gh, False)]:
            st_team["jogos"] += 1
            st_team["gf"] += gf; st_team["ga"] += ga_val
            if is_home:
                st_team["home_j"] += 1; st_team["home_gf"] += gf; st_team["home_ga"] += ga_val
            else:
                st_team["away_j"] += 1; st_team["away_gf"] += gf; st_team["away_ga"] += ga_val

        total_home += gh; total_away += ga
        empates += 1 if gh == ga else 0
        n += 1
    return {
        "ratings": ratings, "stats": stats, "jogos": n,
        "media_home": total_home / max(1, n), "media_away": total_away / max(1, n),
        "taxa_empate": empates / max(1, n),
    }

def media_time(stats, time, campo, padrao):
    s = stats.get(time)
    if not s: return padrao
    if campo == "home_gf": return s["home_gf"] / max(1, s["home_j"])
    if campo == "home_ga": return s["home_ga"] / max(1, s["home_j"])
    if campo == "away_gf": return s["away_gf"] / max(1, s["away_j"])
    if campo == "away_ga": return s["away_ga"] / max(1, s["away_j"])
    return padrao

def calcular_forma(jogos, time_normalizado):
    jogos_time = [j for j in jogos if j.get("completed") and
                  (normalizar(j["home"]) == time_normalizado or normalizar(j["away"]) == time_normalizado)]
    jogos_time = sorted(jogos_time, key=lambda x: x.get("data") or datetime.min, reverse=True)[:5]
    forma = []
    for j in jogos_time:
        if normalizar(j["home"]) == time_normalizado:
            gh, ga = int(j["placar_home"]), int(j["placar_away"])
        else:
            ga, gh = int(j["placar_home"]), int(j["placar_away"])
        forma.append("V" if gh > ga else ("E" if gh == ga else "D"))
    return forma

def calcular_pontos_forma(forma):
    pts = sum(3 if r == "V" else (1 if r == "E" else 0) for r in forma)
    return pts, " ".join(forma)

def prever_jogo(jogo, contexto, posicoes=None, formas=None, desf_h=0, desf_a=0, ajuste_h=0, ajuste_a=0):
    home, away = jogo["home"], jogo["away"]
    ratings, stats = contexto["ratings"], contexto["stats"]
    rh = ratings.get(home, forca_inicial(home, posicoes)) + ajuste_h - desf_h * 18
    ra = ratings.get(away, forca_inicial(away, posicoes)) + ajuste_a - desf_a * 18

    liga_h = contexto["media_home"] or 1.35
    liga_a = contexto["media_away"] or 1.05
    ataque_h = media_time(stats, home, "home_gf", liga_h)
    defesa_a = media_time(stats, away, "away_ga", liga_h)
    ataque_a = media_time(stats, away, "away_gf", liga_a)
    defesa_h = media_time(stats, home, "home_ga", liga_a)

    fator_pos_h, fator_pos_a = 1.0, 1.0
    if posicoes:
        pos_h = posicoes.get(home, {}).get("posicao", 10)
        pos_a = posicoes.get(away, {}).get("posicao", 10)
        fator_pos_h = 1 + max(0, (16 - pos_h)) * 0.025
        fator_pos_a = 1 + max(0, (16 - pos_a)) * 0.025
        ataque_h *= fator_pos_h; defesa_a /= max(fator_pos_a, 0.1)
        ataque_a *= fator_pos_a; defesa_h /= max(fator_pos_h, 0.1)

    fator_forma_h, fator_forma_a = 1.0, 1.0
    if formas:
        pts_h, _ = calcular_pontos_forma(formas.get(home, []))
        pts_a, _ = calcular_pontos_forma(formas.get(away, []))
        fator_forma_h = 1 + (pts_h - 7.5) * 0.03
        fator_forma_a = 1 + (pts_a - 7.5) * 0.03
        ataque_h *= fator_forma_h; ataque_a *= fator_forma_a

    elo_gap = (rh - ra + 58) / 400
    lam_h = clamp((0.52 * ataque_h + 0.48 * defesa_a) * (1 + 0.16 * elo_gap), 0.25, 3.8)
    lam_a = clamp((0.52 * ataque_a + 0.48 * defesa_h) * (1 - 0.14 * elo_gap), 0.20, 3.4)

    mat = matriz_poisson(lam_h, lam_a)
    p_h = sum(mat[i][j] for i in range(MAX_GOLS+1) for j in range(MAX_GOLS+1) if i > j)
    p_d = sum(mat[i][i] for i in range(MAX_GOLS+1))
    p_a = sum(mat[i][j] for i in range(MAX_GOLS+1) for j in range(MAX_GOLS+1) if i < j)
    p_d = 0.74 * p_d + 0.26 * contexto.get("taxa_empate", 0.26)
    total = p_h + p_d + p_a
    p_h, p_d, p_a = p_h/total, p_d/total, p_a/total

    over15 = 1 - sum(mat[i][j] for i in range(MAX_GOLS+1) for j in range(MAX_GOLS+1) if i+j <= 1)
    over25 = 1 - sum(mat[i][j] for i in range(MAX_GOLS+1) for j in range(MAX_GOLS+1) if i+j <= 2)
    under35 = sum(mat[i][j] for i in range(MAX_GOLS+1) for j in range(MAX_GOLS+1) if i+j <= 3)
    btts = sum(mat[i][j] for i in range(1, MAX_GOLS+1) for j in range(1, MAX_GOLS+1))
    placares = sorted([(mat[i][j], i, j) for i in range(MAX_GOLS+1) for j in range(MAX_GOLS+1)], reverse=True)[:3]

    riscos = []
    if tuple(sorted([normalizar(home), normalizar(away)])) in CLASSICOS: riscos.append("clássico")
    amostra = stats.get(home, {}).get("jogos", 0) + stats.get(away, {}).get("jogos", 0)
    if amostra < 10: riscos.append("baixa amostra")
    if abs(p_h - p_a) < 0.08: riscos.append("forças próximas")
    if desf_h or desf_a: riscos.append(f"desfalques {home}:{desf_h} {away}:{desf_a}")

    probs = {"Casa": p_h, "Empate": p_d, "Fora": p_a}
    palpite = max(probs, key=probs.get)
    prob_palpite = probs[palpite]
    mercados = {
        "Over 1.5 gols": over15, "Over 2.5 gols": over25, "Under 3.5 gols": under35,
        "Ambas marcam": btts, f"{home} ou empate": p_h + p_d, f"{away} ou empate": p_a + p_d,
    }
    melhor_mercado, melhor_prob = max(mercados.items(), key=lambda x: x[1])
    score = int(clamp(45 + prob_palpite*38 + melhor_prob*18 + min(amostra,40)*0.25 - len(riscos)*6, 0, 96))
    decisao, cor, classe = ("Apostar", "green", "good") if score >= 76 else (("Cuidado", "amber", "medium") if score >= 62 else ("Evitar", "red", "low"))

    extras = calcular_cartoes_escanteios(lam_h, lam_a, p_d, riscos)
    return {
        "p_h": p_h, "p_d": p_d, "p_a": p_a, "lam_h": lam_h, "lam_a": lam_a,
        "over15": over15, "over25": over25, "under35": under35, "btts": btts,
        "placares": placares, "palpite": palpite, "prob_palpite": prob_palpite,
        "melhor_mercado": melhor_mercado, "melhor_prob": melhor_prob,
        "score": score, "decisao": decisao, "cor": cor, "classe": classe, "riscos": riscos,
        "fator_pos_h": fator_pos_h, "fator_pos_a": fator_pos_a,
        "fator_forma_h": fator_forma_h, "fator_forma_a": fator_forma_a,
        **extras,
    }

def calcular_cartoes_escanteios(m_h, m_a, p_empate, riscos):
    total_gols = m_h + m_a
    equilibrio = 1 - abs(m_h - m_a) / max(0.2, total_gols)
    classico = 0.45 if "clássico" in riscos else 0.0
    cartoes_total = clamp(3.2 + 1.25*equilibrio + 0.75*p_empate + classico, 2.4, 7.2)
    cartoes_home = cartoes_total * clamp(0.49 + 0.06*(m_a - m_h), 0.38, 0.62)
    escanteios_total = clamp(7.1 + 1.2*total_gols + 0.75*equilibrio, 6.0, 13.5)
    escanteios_home = escanteios_total * clamp(0.54 + 0.08*(m_h - m_a), 0.40, 0.68)
    return {
        "cartoes_total": cartoes_total, "cartoes_home": cartoes_home, "cartoes_away": cartoes_total - cartoes_home,
        "over_25_cartoes": prob_over(cartoes_total, 2.5), "over_35_cartoes": prob_over(cartoes_total, 3.5),
        "over_45_cartoes": prob_over(cartoes_total, 4.5),
        "escanteios_total": escanteios_total, "escanteios_home": escanteios_home, "escanteios_away": escanteios_total - escanteios_home,
        "over_75_escanteios": prob_over(escanteios_total, 7.5), "over_85_escanteios": prob_over(escanteios_total, 8.5),
        "over_95_escanteios": prob_over(escanteios_total, 9.5), "over_105_escanteios": prob_over(escanteios_total, 10.5),
    }

def matriz_poisson(m_h, m_a):
    mat = [[poisson_pmf(i, m_h) * poisson_pmf(j, m_a) for j in range(MAX_GOLS+1)] for i in range(MAX_GOLS+1)]
    total = sum(sum(row) for row in mat) or 1
    return [[p/total for p in row] for row in mat]

# ------- BALANÇO 24H -------
def calcular_balanco_24h(jogos):
    agora = datetime.now(); limite = agora - timedelta(hours=24)
    encerrados = [j for j in jogos if j.get("completed") and j.get("data") and limite <= j["data"] <= agora]
    if not encerrados: return []
    todos = sorted([j for j in jogos if j.get("completed") and j.get("data")], key=lambda x: x["data"])
    ctx = {"ratings": {}, "stats": {}, "jogos": 0, "media_home": 0.0, "media_away": 0.0, "taxa_empate": 0.0}
    resultados = []
    encerrados_set = {j["id"] for j in encerrados}
    for jogo in todos:
        if jogo["id"] in encerrados_set:
            prev = prever_jogo(jogo, ctx)
            gols = jogo["placar_home"] + jogo["placar_away"]
            acertos = []; erros = []
            if prev["over25"] >= 0.5:
                if gols > 2.5: acertos.append("Over 2.5")
                else: erros.append("Over 2.5")
            else:
                if gols <= 2.5: acertos.append("Under 2.5")
                else: erros.append("Under 2.5")
            resultados.append({"jogo": f"{jogo['home']} {jogo['placar_home']} x {jogo['placar_away']} {jogo['away']}",
                               "gols": gols, "previsao_over25": prev["over25"], "acertos": acertos, "erros": erros})
        # atualiza contexto
        home, away = jogo["home"], jogo["away"]
        gh, ga = int(jogo["placar_home"]), int(jogo["placar_away"])
        ctx["ratings"].setdefault(home, 1700); ctx["ratings"].setdefault(away, 1700)
        ctx["stats"].setdefault(home, novo_stats()); ctx["stats"].setdefault(away, novo_stats())
        exp_home = 1/(1+10**((ctx["ratings"][away] - (ctx["ratings"][home]+58))/400))
        real_home = 1.0 if gh > ga else 0.5 if gh == ga else 0.0
        delta = 22*(real_home - exp_home)
        ctx["ratings"][home] += delta; ctx["ratings"][away] -= delta
        for st_team, gf, ga_val, is_home in [(ctx["stats"][home], gh, ga, True), (ctx["stats"][away], ga, gh, False)]:
            st_team["jogos"] += 1; st_team["gf"] += gf; st_team["ga"] += ga_val
            if is_home: st_team["home_j"] += 1; st_team["home_gf"] += gf; st_team["home_ga"] += ga_val
            else: st_team["away_j"] += 1; st_team["away_gf"] += gf; st_team["away_ga"] += ga_val
        ctx["jogos"] += 1
        ctx["media_home"] = sum(s["home_gf"] for s in ctx["stats"].values()) / ctx["jogos"]
        ctx["media_away"] = sum(s["away_ga"] for s in ctx["stats"].values()) / ctx["jogos"]
        ctx["taxa_empate"] = sum(1 for j2 in todos if j2["data"] <= jogo["data"] and j2["placar_home"] == j2["placar_away"]) / ctx["jogos"]
    return resultados

# ------- RENDERIZAÇÃO -------
def obter_finalizadores(time_nome):
    return JOGADORES.get(normalizar(time_nome), [])

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

    mapa = {"Casa": home, "Fora": away, "Empate": "Empate"}
    riscos = ", ".join(r["riscos"]) if r["riscos"] else "baixo risco"

    # HTML principal (limpo, sem <pr>)
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
        <br>
        <span class="decision {r['cor']}">{r['decisao']}</span>
        <span class="pill">Score: <strong>{r['score']}/100</strong></span>
        <span class="pill">Alertas: <strong>{riscos}</strong></span>
    </div>
    """
    st.markdown(html_card, unsafe_allow_html=True)

    # Expander com fatores de ajuste
    with st.expander("🔍 Ver ajustes do modelo"):
        st.markdown(f"""
        **Fatores aplicados:**
        - Posição na tabela: {home} x{factor_str(r['fator_pos_h'])}, {away} x{factor_str(r['fator_pos_a'])}
        - Forma recente (últimos 5 jogos): {home} x{factor_str(r['fator_forma_h'])}, {away} x{factor_str(r['fator_forma_a'])}
        - Média de gols esperados ajustada: {home} {r['lam_h']:.2f} vs {away} {r['lam_a']:.2f}
        """)

    if not jogo.get("completed"):
        finalizadores_home = obter_finalizadores(home)
        finalizadores_away = obter_finalizadores(away)
        if finalizadores_home or finalizadores_away:
            with st.expander(f"⚽ Prováveis finalizadores em {home} x {away}"):
                col1, col2 = st.columns(2)
                p_gol_home = 1 - poisson_pmf(0, r["lam_h"])
                p_gol_away = 1 - poisson_pmf(0, r["lam_a"])
                with col1:
                    st.markdown(f"**{home}** (prob. gol: {pct(p_gol_home)})")
                    for nome, peso in finalizadores_home:
                        st.markdown(f"- {nome}: {pct(p_gol_home * peso)}")
                with col2:
                    st.markdown(f"**{away}** (prob. gol: {pct(p_gol_away)})")
                    for nome, peso in finalizadores_away:
                        st.markdown(f"- {nome}: {pct(p_gol_away * peso)}")

def factor_str(valor):
    if valor > 1: return f"⬆️ {valor:.2f}"
    elif valor < 1: return f"⬇️ {valor:.2f}"
    else: return "1.00"

def render_value_box(titulo, prob, odd, banca):
    ev = valor_esperado(prob, odd)
    stake = kelly_stake(prob, odd, banca)
    color = "#16a34a" if ev > 0 else "#dc2626"
    st.markdown(f"""
    <div style="border:1px solid #d7dce2; border-radius:8px; padding:10px; margin:5px 0; background:#f8fafc;">
        <strong>{titulo}</strong><br>
        <span>Probabilidade: {pct(prob)} | Odd informada: {odd:.2f} | Odd justa: {odd_justa(prob):.2f}</span><br>
        <span style="color:{color}; font-weight:bold;">EV: {ev:+.2f}</span> |
        <span>Stake sugerido (Kelly 25%): R$ {stake:.2f}</span>
    </div>
    """, unsafe_allow_html=True)

def main():
    st.markdown('<div class="hero"><h1>⚽ Analisador Esportivo Pro 10.4</h1><p>Probabilidades baseadas em posição na tabela, forma recente e histórico de gols.</p></div>', unsafe_allow_html=True)

    with st.sidebar:
        st.header("Configuração")
        liga_nome = st.selectbox("Liga", list(LIGAS.keys()))
        liga_id = LIGAS[liga_nome]
        col1, col2 = st.columns(2)
        with col1: dias_passado = st.slider("Dias passados", 0, 30, 10)
        with col2: dias_futuro = st.slider("Dias futuros", 0, 7, 3)
        mostrar_ao_vivo = st.checkbox("🔴 Mostrar apenas jogos ao vivo")
        modo_manual = st.checkbox("Adicionar jogo manual")
        if modo_manual:
            with st.form("manual_form"):
                home = st.text_input("Time da casa"); away = st.text_input("Time visitante")
                desf_h = st.number_input("Desfalques casa", 0, 5, 0); desf_a = st.number_input("Desfalques fora", 0, 5, 0)
                if st.form_submit_button("Adicionar") and home and away:
                    st.session_state.jogo_manual = (criar_jogo_manual(home, away), desf_h, desf_a)
        st.markdown("---")
        odd_input = st.text_input("Odd do palpite (ex: 2.10)")
        banca = st.number_input("Banca (R$)", 0.0, 100000.0, 1000.0, step=100.0)

    with st.spinner("Buscando dados e calculando..."):
        jogos, logs = buscar_periodo(liga_id, dias_passado, dias_futuro)
        classif = buscar_classificacao(liga_id)
        contexto = construir_contexto(jogos, posicoes=classif)
        formas = {}
        for j in jogos:
            for time in [j["home"], j["away"]]:
                tn = normalizar(time)
                if tn not in formas: formas[tn] = calcular_forma(jogos, tn)

        todos_jogos = []
        for j in jogos:
            if not j.get("completed") or j.get("live"):
                prev = prever_jogo(j, contexto, posicoes=classif, formas=formas)
                todos_jogos.append((j, prev))
        if st.session_state.jogo_manual:
            mj, mh, ma = st.session_state.jogo_manual
            prev_m = prever_jogo(mj, contexto, posicoes=classif, formas=formas, desf_h=mh, desf_a=ma)
            todos_jogos.append((mj, prev_m))
        if mostrar_ao_vivo:
            todos_jogos = [(j, p) for j, p in todos_jogos if j.get("live")]
        todos_jogos.sort(key=lambda x: (not x[0].get("live"), x[0].get("data") or datetime.max))

    st.header(f"{'📺 Jogos ao vivo' if mostrar_ao_vivo else '📊 Análises'} – {liga_nome} ({len(todos_jogos)} jogos)")
    if logs:
        with st.expander("Logs de erro"): 
            for log in logs: st.warning(log)
    if not todos_jogos: st.info("Nenhum jogo encontrado."); return

    for jogo, prev in todos_jogos:
        render_card(jogo, prev, classif, formas)
        try: odd = float(odd_input) if odd_input else 0
        except: odd = 0
        if odd > 0:
            prob = prev["p_h"] if prev["palpite"] == "Casa" else (prev["p_a"] if prev["palpite"] == "Fora" else prev["p_d"])
            mercado = f"Vitória {jogo['home']}" if prev["palpite"] == "Casa" else (f"Vitória {jogo['away']}" if prev["palpite"] == "Fora" else "Empate")
            render_value_box(f"{mercado} (Palpite)", prob, odd, banca)

    # Balanço 24h
    st.header("📈 Balanço das últimas 24h")
    res = calcular_balanco_24h(jogos)
    if not res:
        st.info("Nenhum jogo encerrado nas últimas 24h.")
    else:
        acertos = sum(len(r["acertos"]) for r in res); erros = sum(len(r["erros"]) for r in res)
        st.markdown(f"**Acertos:** {acertos} | **Erros:** {erros} | **Total:** {len(res)}")
        st.dataframe(pd.DataFrame(res)[["jogo", "gols", "previsao_over25"]].assign(
            previsao=lambda df: df["previsao_over25"].apply(lambda x: "Over" if x>=0.5 else "Under"),
            resultado=lambda df: df.apply(lambda row: "✔" if (row["previsao"]=="Over" and row["gols"]>2.5) or (row["previsao"]=="Under" and row["gols"]<=2.5) else "✘", axis=1)
        ), use_container_width=True)

    # Resumo cartões/escanteios
    st.subheader("📋 Resumo – Cartões e Escanteios")
    df_resumo = pd.DataFrame([{
        "Jogo": f"{j['home']} x {j['away']}",
        "Cartões esp.": round(r["cartoes_total"], 1),
        "Over 2.5 cartões": pct(r["over_25_cartoes"]),
        "Over 3.5 cartões": pct(r["over_35_cartoes"]),
        "Escanteios esp.": round(r["escanteios_total"], 1),
        "Over 7.5 esc.": pct(r["over_75_escanteios"]),
        "Over 8.5 esc.": pct(r["over_85_escanteios"]),
    } for j, r in todos_jogos])
    st.dataframe(df_resumo, use_container_width=True)

    # Histórico
    st.session_state.historico.extend(todos_jogos)
    st.subheader("📜 Histórico da sessão")
    hist_df = pd.DataFrame([{
        "Data": j.get("data_txt"), "Jogo": f"{j['home']} x {j['away']}",
        "Palpite": mapa_palpite(j, r), "Prob.": pct(r["prob_palpite"]),
        "Score": r["score"], "Decisão": r["decisao"],
    } for j, r in st.session_state.historico])
    st.dataframe(hist_df.tail(20), use_container_width=True)

def mapa_palpite(jogo, pred):
    mp = {"Casa": jogo["home"], "Fora": jogo["away"], "Empate": "Empate"}
    return mp.get(pred["palpite"], pred["palpite"])

if __name__ == "__main__":
    main()
