import math
import re
import unicodedata
from datetime import datetime

import pandas as pd
import requests
import streamlit as st


st.set_page_config(
    page_title="Analisador Esportivo Pro",
    page_icon="⚽",
    layout="wide",
)


ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
HEADERS = {"User-Agent": "AnalisadorEsportivoPro/12.5"}

MAX_GOLS = 10
RETRIES = 2
DEFAULT_HOME_ADV = 0.25


LIGAS = {
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
    "flamengo": 86,
    "palmeiras": 84,
    "botafogo": 79,
    "atletico-mg": 76,
    "sao paulo": 78,
    "fluminense": 77,
    "gremio": 74,
    "internacional": 75,
    "corinthians": 76,
    "cruzeiro": 73,
    "bahia": 74,
    "fortaleza": 73,
    "vasco": 70,
    "santos": 72,
    "ceara": 69,
    "sport": 68,
    "vitoria": 69,
    "coritiba": 68,
    "manchester city": 91,
    "arsenal": 88,
    "liverpool": 88,
    "chelsea": 82,
    "tottenham hotspur": 80,
    "manchester united": 81,
    "real madrid": 90,
    "barcelona": 87,
    "atletico madrid": 84,
    "bayern munich": 88,
    "borussia dortmund": 82,
    "bayer leverkusen": 84,
    "inter milan": 86,
    "juventus": 82,
    "milan": 81,
    "paris saint-germain": 88,
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


def parse_dt(valor):
    if not valor:
        return None

    try:
        return datetime.fromisoformat(
            valor.replace("Z", "+00:00")
        ).astimezone().replace(tzinfo=None)
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

    return fetch_with_retry(
        f"{ESPN_BASE}/{liga_id}/scoreboard",
        params,
    )


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
                "home": nome_limpo(home.get("team", {}).get("displayName", "Casa")),
                "away": nome_limpo(away.get("team", {}).get("displayName", "Fora")),
                "home_score": placar(home),
                "away_score": placar(away),
                "data": dt,
                "status": status_type.get("description", ""),
                "estado": status_type.get("state", ""),
                "em_jogo": status_type.get("state") == "in",
                "finalizado": status_type.get("state") == "post",
                "futuro": status_type.get("state") == "pre",
            }
        )

    return jogos


def forca_time(nome):
    return FORCA_BASE.get(normalizar(nome), 70)


def eh_classico(home, away):
    return tuple(sorted([normalizar(home), normalizar(away)])) in CLASSICOS


def calcular_probabilidades(home, away):
    fh = forca_time(home)
    fa = forca_time(away)

    diff = fh - fa

    media_home = 1.4 + (diff * 0.02) + DEFAULT_HOME_ADV
    media_away = 1.1 - (diff * 0.015)

    if eh_classico(home, away):
        media_home *= 0.95
        media_away *= 0.98

    media_home = clamp(media_home, 0.2, 4.0)
    media_away = clamp(media_away, 0.2, 4.0)

    p_home = 0
    p_draw = 0
    p_away = 0
    p_over15 = 0
    p_over25 = 0
    p_over35 = 0
    p_under25 = 0
    p_btts = 0

    placares = []

    for gh in range(MAX_GOLS + 1):
        for ga in range(MAX_GOLS + 1):
            p = poisson_pmf(gh, media_home) * poisson_pmf(ga, media_away)

            placares.append((gh, ga, p))

            if gh > ga:
                p_home += p
            elif gh == ga:
                p_draw += p
            else:
                p_away += p

            total = gh + ga

            if total >= 2:
                p_over15 += p

            if total >= 3:
                p_over25 += p

            if total >= 4:
                p_over35 += p

            if total <= 2:
                p_under25 += p

            if gh > 0 and ga > 0:
                p_btts += p

    placares = sorted(placares, key=lambda x: x[2], reverse=True)

    dupla_1x = p_home + p_draw
    dupla_x2 = p_draw + p_away
    dupla_12 = p_home + p_away

    probs = {
        "home": clamp(p_home, 0, 1),
        "draw": clamp(p_draw, 0, 1),
        "away": clamp(p_away, 0, 1),
        "over15": clamp(p_over15, 0, 1),
        "over25": clamp(p_over25, 0, 1),
        "over35": clamp(p_over35, 0, 1),
        "under25": clamp(p_under25, 0, 1),
        "btts": clamp(p_btts, 0, 1),
        "dupla_1x": clamp(dupla_1x, 0, 1),
        "dupla_x2": clamp(dupla_x2, 0, 1),
        "dupla_12": clamp(dupla_12, 0, 1),
        "media_home": media_home,
        "media_away": media_away,
        "forca_home": fh,
        "forca_away": fa,
        "placares": placares[:5],
    }

    probs["odd_home"] = odd_justa(probs["home"])
    probs["odd_draw"] = odd_justa(probs["draw"])
    probs["odd_away"] = odd_justa(probs["away"])
    probs["odd_over25"] = odd_justa(probs["over25"])
    probs["odd_btts"] = odd_justa(probs["btts"])

    return probs


def melhor_mercado(probs, home, away):
    mercados = [
        (f"{home} vence", probs["home"]),
        ("Empate", probs["draw"]),
        (f"{away} vence", probs["away"]),
        ("Dupla chance 1X", probs["dupla_1x"]),
        ("Dupla chance X2", probs["dupla_x2"]),
        ("Dupla chance 12", probs["dupla_12"]),
        ("Over 1.5 gols", probs["over15"]),
        ("Over 2.5 gols", probs["over25"]),
        ("Under 2.5 gols", probs["under25"]),
        ("Ambos marcam", probs["btts"]),
    ]

    mercados = sorted(mercados, key=lambda x: x[1], reverse=True)
    return mercados[0]


def nivel_confianca(prob):
    if prob >= 0.72:
        return "🟢 ALTA"
    if prob >= 0.58:
        return "🟡 MÉDIA"
    return "🔴 BAIXA"


def status_label(jogo):
    if jogo["em_jogo"]:
        return "🔴 Ao vivo"
    if jogo["finalizado"]:
        return "✅ Finalizado"
    if jogo["futuro"]:
        return "🕒 Futuro"
    return jogo["status"] or "Status não informado"


st.title("⚽ Analisador Esportivo Pro")
st.caption("ESPN API + Poisson + força base + odds justas + recomendações.")

with st.sidebar:
    st.header("Filtros")

    liga_nome = st.selectbox("Liga", list(LIGAS.keys()))

    usar_data = st.checkbox("Filtrar por data")
    data_escolhida = None

    if usar_data:
        data_escolhida = st.date_input("Data").isoformat()

    filtro_status = st.selectbox(
        "Status",
        ["Todos", "Ao vivo", "Futuros", "Finalizados"],
    )

    mostrar_tabela = st.checkbox("Mostrar tabela resumo", value=True)

    if st.button("Atualizar dados"):
        st.cache_data.clear()
        st.rerun()


liga_id = LIGAS[liga_nome]

with st.spinner("Buscando jogos na ESPN..."):
    payload, erro = buscar_scoreboard(liga_id, data_escolhida)

if erro:
    st.error(erro)
    st.stop()

jogos = extrair_jogos(payload, liga_id)

if filtro_status == "Ao vivo":
    jogos = [j for j in jogos if j["em_jogo"]]
elif filtro_status == "Futuros":
    jogos = [j for j in jogos if j["futuro"]]
elif filtro_status == "Finalizados":
    jogos = [j for j in jogos if j["finalizado"]]

if not jogos:
    st.warning("Nenhum jogo encontrado para os filtros escolhidos.")
    st.stop()

st.subheader(f"{liga_nome} — {len(jogos)} jogo(s) encontrado(s)")

resumo = []

for jogo in jogos:
    probs = calcular_probabilidades(jogo["home"], jogo["away"])
    mercado, prob_mercado = melhor_mercado(probs, jogo["home"], jogo["away"])

    placar_txt = ""
    if jogo["finalizado"] or jogo["em_jogo"]:
        placar_txt = f" — {jogo['home_score']} x {jogo['away_score']}"

    data_txt = "Data não informada"
    if jogo["data"]:
        data_txt = jogo["data"].strftime("%d/%m/%Y %H:%M")

    placar_mais_provavel = probs["placares"][0]
    placar_exato = f"{placar_mais_provavel[0]} x {placar_mais_provavel[1]}"

    resumo.append(
        {
            "Jogo": f"{jogo['home']} x {jogo['away']}",
            "Status": status_label(jogo),
            "Casa": pct(probs["home"]),
            "Empate": pct(probs["draw"]),
            "Fora": pct(probs["away"]),
            "Over 2.5": pct(probs["over25"]),
            "BTTS": pct(probs["btts"]),
            "Melhor mercado": mercado,
            "Probabilidade": pct(prob_mercado),
            "Confiança": nivel_confianca(prob_mercado),
        }
    )

    with st.container(border=True):
        st.markdown(f"### {jogo['home']} x {jogo['away']}{placar_txt}")
        st.write(f"**Status:** {status_label(jogo)}")
        st.write(f"**Data:** {data_txt}")

        if eh_classico(jogo["home"], jogo["away"]):
            st.warning("Clássico detectado: modelo aplicou ajuste de cautela.")

        st.info(
            f"🎯 Melhor mercado: **{mercado}** — "
            f"{pct(prob_mercado)} | Confiança: {nivel_confianca(prob_mercado)}"
        )

        c1, c2, c3 = st.columns(3)

        c1.metric("Força casa", probs["forca_home"])
        c2.metric("Força fora", probs["forca_away"])
        c3.metric("Placar provável", placar_exato)

        c1, c2, c3, c4, c5 = st.columns(5)

        c1.metric("Casa", pct(probs["home"]), f"Odd {probs['odd_home']:.2f}")
        c2.metric("Empate", pct(probs["draw"]), f"Odd {probs['odd_draw']:.2f}")
        c3.metric("Fora", pct(probs["away"]), f"Odd {probs['odd_away']:.2f}")
        c4.metric("Over 2.5", pct(probs["over25"]), f"Odd {probs['odd_over25']:.2f}")
        c5.metric("BTTS", pct(probs["btts"]), f"Odd {probs['odd_btts']:.2f}")

        c1, c2, c3, c4, c5 = st.columns(5)

        c1.metric("Over 1.5", pct(probs["over15"]))
        c2.metric("Over 3.5", pct(probs["over35"]))
        c3.metric("Under 2.5", pct(probs["under25"]))
        c4.metric("Dupla 1X", pct(probs["dupla_1x"]))
        c5.metric("Dupla X2", pct(probs["dupla_x2"]))

        with st.expander("Ver placares exatos mais prováveis"):
            dados_placares = []

            for gh, ga, p in probs["placares"]:
                dados_placares.append(
                    {
                        "Placar": f"{gh} x {ga}",
                        "Probabilidade": pct(p),
                        "Odd justa": round(odd_justa(p), 2),
                    }
                )

            st.dataframe(
                pd.DataFrame(dados_placares),
                use_container_width=True,
                hide_index=True,
            )


if mostrar_tabela:
    st.divider()
    st.subheader("Resumo geral")

    st.dataframe(
        pd.DataFrame(resumo),
        use_container_width=True,
        hide_index=True,
    )

st.success("Aplicação carregada corretamente.")