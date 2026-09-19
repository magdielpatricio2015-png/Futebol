from datetime import datetime, timedelta
from math import exp, factorial
from difflib import get_close_matches
import unicodedata
import re

import requests
import streamlit as st


# ============================================================
# CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="Previsor de Futebol",
    page_icon="⚽",
    layout="wide",
)

FUSO_HORARIO = "America/Sao_Paulo"
URL_ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer"

LIGAS = {
    "Brasil - Série A": "bra.1",
    "Brasil - Série B": "bra.2",
    "Libertadores": "conmebol.libertadores",
    "Sul-Americana": "conmebol.sudamericana",
    "Premier League": "eng.1",
    "Champions League": "uefa.champions",
    "Europa League": "uefa.europa",
    "La Liga": "esp.1",
    "Serie A Italiana": "ita.1",
    "Bundesliga": "ger.1",
    "Ligue 1": "fra.1",
    "Primeira Liga": "por.1",
    "MLS": "usa.1",
    "Liga MX": "mex.1",
}

RATINGS = {
    "flamengo": 87.5,
    "palmeiras": 88.5,
    "botafogo": 84.5,
    "fluminense": 82.0,
    "sao paulo": 82.5,
    "corinthians": 80.0,
    "santos": 78.5,
    "gremio": 81.0,
    "internacional": 81.0,
    "atletico mineiro": 84.0,
    "cruzeiro": 79.5,
    "bahia": 79.0,
    "vasco da gama": 77.5,
    "fortaleza": 80.0,
    "athletico paranaense": 80.5,
    "bragantino": 79.0,
    "ceara": 76.0,
    "vitoria": 75.5,
    "juventude": 75.0,
    "sport": 74.0,
    "river plate": 84.0,
    "boca juniors": 83.0,
    "racing": 80.0,
    "nacional": 78.0,
    "penarol": 78.0,
    "colo colo": 77.0,
    "manchester city": 94.0,
    "arsenal": 91.0,
    "liverpool": 91.5,
    "chelsea": 86.0,
    "manchester united": 84.5,
    "tottenham": 85.5,
    "newcastle": 84.0,
    "aston villa": 84.0,
    "brighton": 82.0,
    "west ham": 80.0,
    "real madrid": 94.0,
    "barcelona": 91.0,
    "atletico madrid": 88.0,
    "athletic bilbao": 84.0,
    "real sociedad": 84.0,
    "villarreal": 82.0,
    "sevilla": 80.0,
    "real betis": 81.0,
    "inter": 90.5,
    "internazionale": 90.5,
    "milan": 87.5,
    "ac milan": 87.5,
    "juventus": 87.5,
    "napoli": 86.5,
    "atalanta": 86.0,
    "roma": 84.0,
    "lazio": 83.0,
    "bayern": 92.0,
    "bayern munich": 92.0,
    "borussia dortmund": 87.5,
    "bayer leverkusen": 90.0,
    "rb leipzig": 86.5,
    "psg": 91.0,
    "paris saint germain": 91.0,
    "marseille": 83.0,
    "monaco": 84.0,
    "lyon": 81.0,
    "benfica": 85.0,
    "porto": 84.0,
    "sporting": 85.0,
    "ajax": 81.0,
    "psv": 84.0,
    "feyenoord": 83.0,
    "brasil": 91.0,
    "argentina": 91.5,
    "franca": 91.0,
    "inglaterra": 89.5,
    "espanha": 89.0,
    "alemanha": 87.0,
    "portugal": 88.5,
    "italia": 87.0,
    "uruguai": 86.0,
    "colombia": 84.5,
    "mexico": 81.0,
    "japao": 80.0,
}

ALIASES = {
    "mengao": "flamengo",
    "mengo": "flamengo",
    "galo": "atletico mineiro",
    "verdao": "palmeiras",
    "timao": "corinthians",
    "peixe": "santos",
    "flu": "fluminense",
    "fogao": "botafogo",
    "vasco": "vasco da gama",
    "city": "manchester city",
    "man united": "manchester united",
    "spurs": "tottenham",
    "real": "real madrid",
}


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("ascii")
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9 ]", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def porcentagem(valor):
    return f"{valor * 100:.1f}%"


def poisson(quantidade, media):
    return exp(-media) * (media ** quantidade) / factorial(quantidade)


def rating_time(nome):
    nome_original = nome.strip()
    nome_normalizado = normalizar(nome_original)

    if nome_normalizado in ALIASES:
        nome_normalizado = ALIASES[nome_normalizado]

    if nome_normalizado in RATINGS:
        return RATINGS[nome_normalizado]

    for time, rating in RATINGS.items():
        if nome_normalizado in time or time in nome_normalizado:
            return rating

    semelhantes = get_close_matches(
        nome_normalizado,
        RATINGS.keys(),
        n=1,
        cutoff=0.70,
    )

    if semelhantes:
        return RATINGS[semelhantes[0]]

    return 75.0


# ============================================================
# PREVISÃO ESTATÍSTICA
# ============================================================

def calcular_previsao(mandante, visitante):
    rating_mandante = rating_time(mandante)
    rating_visitante = rating_time(visitante)

    diferenca = rating_mandante - rating_visitante

    gols_mandante = max(
        0.20,
        min(3.80, 1.38 + diferenca * 0.018),
    )

    gols_visitante = max(
        0.20,
        min(3.50, 1.08 - diferenca * 0.012),
    )

    matriz = []

    for gols_casa in range(9):
        linha = []

        for gols_fora in range(9):
            probabilidade = (
                poisson(gols_casa, gols_mandante)
                * poisson(gols_fora, gols_visitante)
            )
            linha.append(probabilidade)

        matriz.append(linha)

    total = sum(sum(linha) for linha in matriz)

    for casa in range(9):
        for fora in range(9):
            matriz[casa][fora] /= total

    placares = []

    for casa in range(9):
        for fora in range(9):
            placares.append({
                "placar": f"{casa} x {fora}",
                "probabilidade": matriz[casa][fora],
            })

    placares.sort(
        key=lambda item: item["probabilidade"],
        reverse=True,
    )

    prob_vitoria_casa = 0
    prob_empate = 0
    prob_vitoria_fora = 0
    prob_over_25 = 0
    prob_ambas_marcam = 0

    for casa in range(9):
        for fora in range(9):
            probabilidade = matriz[casa][fora]

            if casa > fora:
                prob_vitoria_casa += probabilidade
            elif casa == fora:
                prob_empate += probabilidade
            else:
                prob_vitoria_fora += probabilidade

            if casa + fora >= 3:
                prob_over_25 += probabilidade

            if casa >= 1 and fora >= 1:
                prob_ambas_marcam += probabilidade

    media_escanteios = max(
        6.0,
        min(
            14.0,
            9.4
            + ((rating_mandante + rating_visitante - 150) * 0.025),
        ),
    )

    linhas_escanteios = {}

    for linha in [7.5, 8.5, 9.5, 10.5, 11.5]:
        probabilidade = 0

        for quantidade in range(30):
            if quantidade > linha:
                probabilidade += poisson(
                    quantidade,
                    media_escanteios,
                )

        linhas_escanteios[linha] = probabilidade

    return {
        "gols_mandante": gols_mandante,
        "gols_visitante": gols_visitante,
        "total_gols": gols_mandante + gols_visitante,
        "placares": placares[:10],
        "vitoria_casa": prob_vitoria_casa,
        "empate": prob_empate,
        "vitoria_fora": prob_vitoria_fora,
        "over_25": prob_over_25,
        "under_25": 1 - prob_over_25,
        "ambas_marcam": prob_ambas_marcam,
        "media_escanteios": media_escanteios,
        "linhas_escanteios": linhas_escanteios,
    }


# ============================================================
# ESPN - BUSCA DE JOGOS
# ============================================================

@st.cache_data(ttl=900)
def buscar_jogos(slug, dias):
    agora = datetime.now()
    final = agora + timedelta(days=dias)

    data_inicio = agora.strftime("%Y%m%d")
    data_final = final.strftime("%Y%m%d")

    if data_inicio == data_final:
        datas = data_inicio
    else:
        datas = f"{data_inicio}-{data_final}"

    url = f"{URL_ESPN}/{slug}/scoreboard"

    parametros = {
        "dates": datas,
        "limit": 100,
        "region": "br",
        "lang": "pt",
    }

    resposta = requests.get(
        url,
        params=parametros,
        timeout=20,
        headers={
            "User-Agent": "Mozilla/5.0 Previsor Futebol",
        },
    )

    resposta.raise_for_status()

    dados = resposta.json()
    jogos = []

    for evento in dados.get("events", []):
        competicoes = evento.get("competitions", [])

        if not competicoes:
            continue

        competicao = competicoes[0]
        competidores = competicao.get("competitors", [])

        mandante = None
        visitante = None

        for competidor in competidores:
            if competidor.get("homeAway") == "home":
                mandante = competidor
            elif competidor.get("homeAway") == "away":
                visitante = competidor

        if not mandante or not visitante:
            continue

        data_jogo = competicao.get("date") or evento.get("date")

        if not data_jogo:
            continue

        data_convertida = datetime.fromisoformat(
            data_jogo.replace("Z", "+00:00")
        )

        data_local = data_convertida.astimezone()

        status = (
            competicao
            .get("status", {})
            .get("type", {})
            .get("description", "Sem informação")
        )

        jogos.append({
            "id": str(evento.get("id", "")),
            "data": data_local,
            "mandante": mandante.get("team", {}).get(
                "displayName",
                "Mandante",
            ),
            "visitante": visitante.get("team", {}).get(
                "displayName",
                "Visitante",
            ),
            "status": status,
            "local": competicao.get("venue", {}).get(
                "fullName",
                "Local não informado",
            ),
        })

    jogos.sort(key=lambda jogo: jogo["data"])

    return jogos


def carregar_todos_jogos(ligas, dias):
    todos = []
    erros = []

    for liga in ligas:
        slug = LIGAS[liga]

        try:
            jogos = buscar_jogos(slug, dias)

            for jogo in jogos:
                jogo["liga"] = liga

            todos.extend(jogos)

        except Exception as erro:
            erros.append(f"{liga}: {erro}")

    vistos = set()
    resultado = []

    for jogo in todos:
        chave = jogo["id"]

        if chave in vistos:
            continue

        vistos.add(chave)
        resultado.append(jogo)

    resultado.sort(key=lambda jogo: jogo["data"])

    return resultado, erros


# ============================================================
# EXIBIÇÃO DA PREVISÃO
# ============================================================

def mostrar_previsao(mandante, visitante):
    previsao = calcular_previsao(mandante, visitante)

    st.subheader(f"{mandante} x {visitante}")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Gols esperados",
        f"{previsao['total_gols']:.2f}",
    )

    col2.metric(
        "Gols do mandante",
        f"{previsao['gols_mandante']:.2f}",
    )

    col3.metric(
        "Gols do visitante",
        f"{previsao['gols_visitante']:.2f}",
    )

    col4.metric(
        "Escanteios esperados",
        f"{previsao['media_escanteios']:.1f}",
    )

    st.markdown("### Probabilidade do resultado")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Vitória do mandante",
        porcentagem(previsao["vitoria_casa"]),
    )

    col2.metric(
        "Empate",
        porcentagem(previsao["empate"]),
    )

    col3.metric(
        "Vitória do visitante",
        porcentagem(previsao["vitoria_fora"]),
    )

    st.markdown("### Possibilidades de gols")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Mais de 2.5 gols",
        porcentagem(previsao["over_25"]),
    )

    col2.metric(
        "Menos de 2.5 gols",
        porcentagem(previsao["under_25"]),
    )

    col3.metric(
        "Ambas marcam",
        porcentagem(previsao["ambas_marcam"]),
    )

    st.markdown("### Placares mais prováveis")

    tabela_placares = []

    for item in previsao["placares"]:
        tabela_placares.append({
            "Placar": item["placar"],
            "Probabilidade": porcentagem(
                item["probabilidade"]
            ),
        })

    st.dataframe(
        tabela_placares,
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### Possibilidades de escanteios")

    tabela_escanteios = []

    for linha, probabilidade in previsao[
        "linhas_escanteios"
    ].items():
        tabela_escanteios.append({
            "Mercado": f"Mais de {linha} escanteios",
            "Probabilidade": porcentagem(probabilidade),
        })

    st.dataframe(
        tabela_escanteios,
        use_container_width=True,
        hide_index=True,
    )

    st.warning(
        "Estas são estimativas estatísticas. "
        "Não há garantia de acerto."
    )


# ============================================================
# INTERFACE PRINCIPAL
# ============================================================

st.title("⚽ Previsor de Futebol")
st.caption(
    "Lista de jogos, horários e possibilidades estatísticas"
)

st.sidebar.header("Filtros dos jogos")

periodo = st.sidebar.selectbox(
    "Mostrar jogos dos próximos:",
    {
        "2 dias": 2,
        "7 dias": 7,
        "15 dias": 15,
        "30 dias": 30,
    }.keys(),
)

quantidade_dias = {
    "2 dias": 2,
    "7 dias": 7,
    "15 dias": 15,
    "30 dias": 30,
}[periodo]

ligas_selecionadas = st.sidebar.multiselect(
    "Escolha as ligas:",
    list(LIGAS.keys()),
    default=[
        "Brasil - Série A",
        "Libertadores",
        "Premier League",
        "Champions League",
    ],
)

buscar = st.sidebar.button(
    "🔎 Buscar lista de jogos",
    type="primary",
    use_container_width=True,
)

if "jogos" not in st.session_state:
    st.session_state.jogos = []

if "erros" not in st.session_state:
    st.session_state.erros = []


if buscar:
    if not ligas_selecionadas:
        st.error("Escolha pelo menos uma liga.")
    else:
        with st.spinner("Buscando jogos na ESPN..."):
            jogos, erros = carregar_todos_jogos(
                ligas_selecionadas,
                quantidade_dias,
            )

        st.session_state.jogos = jogos
        st.session_state.erros = erros


if st.session_state.erros:
    with st.expander("Avisos da busca"):
        for erro in st.session_state.erros:
            st.warning(erro)


jogos = st.session_state.jogos

st.header("Lista de jogos")

if not jogos:
    st.info(
        "Escolha as ligas na barra lateral e clique em "
        "'Buscar lista de jogos'."
    )
else:
    opcoes = []

    for indice, jogo in enumerate(jogos):
        horario = jogo["data"].strftime("%d/%m/%Y às %H:%M")

        opcoes.append(
            f"{horario} | {jogo['mandante']} x "
            f"{jogo['visitante']} | {jogo['liga']}"
        )

    indice_escolhido = st.selectbox(
        "Selecione um jogo:",
        range(len(jogos)),
        format_func=lambda indice: opcoes[indice],
    )

    jogo_escolhido = jogos[indice_escolhido]

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Data e horário",
        jogo_escolhido["data"].strftime(
            "%d/%m/%Y %H:%M"
        ),
    )

    col2.metric(
        "Competição",
        jogo_escolhido["liga"],
    )

    col3.metric(
        "Status",
        jogo_escolhido["status"],
    )

    st.write(
        f"**Local:** {jogo_escolhido['local']}"
    )

    calcular_jogo = st.button(
        "📊 Ver possibilidades estatísticas",
        type="primary",
        use_container_width=True,
    )

    if calcular_jogo:
        mostrar_previsao(
            jogo_escolhido["mandante"],
            jogo_escolhido["visitante"],
        )


st.markdown("---")

st.header("Previsão manual")

col1, col2 = st.columns(2)

with col1:
    mandante_manual = st.text_input(
        "Time mandante",
        value="Flamengo",
    )

with col2:
    visitante_manual = st.text_input(
        "Time visitante",
        value="Palmeiras",
    )

if st.button(
    "Calcular previsão manual",
    use_container_width=True,
):
    if not mandante_manual.strip() or not visitante_manual.strip():
        st.error("Digite os dois times.")
    else:
        mostrar_previsao(
            mandante_manual,
            visitante_manual,
        )
