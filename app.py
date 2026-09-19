from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
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

FUSO = ZoneInfo("America/Sao_Paulo")
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

# Header de navegador real. O User-Agent genérico anterior
# ("Mozilla/5.0 Previsor Futebol") pode ser rejeitado pela proteção
# anti-bot da ESPN, principalmente em servidores de nuvem (Streamlit Cloud,
# Render, etc.), fazendo a busca falhar silenciosamente.
HEADERS_ESPN = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
    "Referer": "https://www.espn.com/",
}


LIGAS = {
    "Brasil - Série A": "bra.1",
    "Brasil - Série B": "bra.2",
    "Libertadores": "conmebol.libertadores",
    "Sul-Americana": "conmebol.sudamericana",
    "Premier League": "eng.1",
    "Champions League": "uefa.champions",
    "Europa League": "uefa.europa",
    "Conference League": "uefa.europa.conf",
    "La Liga": "esp.1",
    "Serie A Italiana": "ita.1",
    "Bundesliga": "ger.1",
    "Ligue 1": "fra.1",
    "Primeira Liga": "por.1",
    "Eredivisie": "ned.1",
    "MLS": "usa.1",
    "Liga MX": "mex.1",
    "Liga Saudita": "ksa.1",
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
    "sport recife": 74.0,
    "mirassol": 74.5,

    "river plate": 84.0,
    "boca juniors": 83.0,
    "racing club": 80.0,
    "independiente": 78.5,
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


def limitar(valor, minimo, maximo):
    return max(minimo, min(valor, maximo))


def poisson(quantidade, media):
    return exp(-media) * (media ** quantidade) / factorial(quantidade)


def obter_rating(nome):
    nome = normalizar(nome)

    if nome in ALIASES:
        nome = ALIASES[nome]

    if nome in RATINGS:
        return RATINGS[nome]

    for time, rating in RATINGS.items():
        if nome in time or time in nome:
            return rating

    semelhantes = get_close_matches(
        nome,
        RATINGS.keys(),
        n=1,
        cutoff=0.70,
    )

    if semelhantes:
        return RATINGS[semelhantes[0]]

    return 75.0


# ============================================================
# PREVISÃO DE PLACAR, GOLS E ESCANTEIOS
# ============================================================

def calcular_previsao(mandante, visitante):
    rating_casa = obter_rating(mandante)
    rating_fora = obter_rating(visitante)

    diferenca = rating_casa - rating_fora

    gols_casa = limitar(
        1.38 + diferenca * 0.018,
        0.20,
        3.80,
    )

    gols_fora = limitar(
        1.08 - diferenca * 0.012,
        0.20,
        3.50,
    )

    matriz = []

    for casa in range(9):
        linha = []

        for fora in range(9):
            probabilidade = (
                poisson(casa, gols_casa)
                * poisson(fora, gols_fora)
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
                "Placar": f"{casa} x {fora}",
                "Probabilidade": matriz[casa][fora],
            })

    placares.sort(
        key=lambda item: item["Probabilidade"],
        reverse=True,
    )

    vitoria_casa = 0
    empate = 0
    vitoria_fora = 0
    over_25 = 0
    ambas_marcam = 0

    for casa in range(9):
        for fora in range(9):
            probabilidade = matriz[casa][fora]

            if casa > fora:
                vitoria_casa += probabilidade

            elif casa == fora:
                empate += probabilidade

            else:
                vitoria_fora += probabilidade

            if casa + fora >= 3:
                over_25 += probabilidade

            if casa >= 1 and fora >= 1:
                ambas_marcam += probabilidade

    media_escanteios = limitar(
        9.4 + ((rating_casa + rating_fora - 150) * 0.025),
        6.0,
        14.0,
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
        "gols_casa": gols_casa,
        "gols_fora": gols_fora,
        "total_gols": gols_casa + gols_fora,
        "placares": placares[:10],
        "vitoria_casa": vitoria_casa,
        "empate": empate,
        "vitoria_fora": vitoria_fora,
        "over_25": over_25,
        "under_25": 1 - over_25,
        "ambas_marcam": ambas_marcam,
        "media_escanteios": media_escanteios,
        "linhas_escanteios": linhas_escanteios,
    }


# ============================================================
# BUSCA DA ESPN
# ============================================================

@st.cache_data(ttl=900, show_spinner=False)
def buscar_jogos_intervalo(slug, data_inicio, data_fim):
    """
    Busca todos os jogos de uma liga num intervalo de datas com
    UMA ÚNICA requisição (dates=inicio-fim), em vez de uma
    requisição por dia. Isso evita dezenas/centenas de chamadas
    sequenciais que podiam travar o app ou levar a ESPN a
    bloquear as requisições.
    """
    url = f"{ESPN_BASE}/{slug}/scoreboard"

    parametros = {
        "dates": f"{data_inicio}-{data_fim}",
        "limit": 300,
    }

    resposta = requests.get(
        url,
        params=parametros,
        timeout=20,
        headers=HEADERS_ESPN,
    )

    resposta.raise_for_status()

    return resposta.json()


def extrair_jogos(slug, nome_liga, data_inicio, data_fim):
    dados = buscar_jogos_intervalo(slug, data_inicio, data_fim)
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

            if competidor.get("homeAway") == "away":
                visitante = competidor

        if not mandante or not visitante:
            continue

        data_jogo = (
            competicao.get("date")
            or evento.get("date")
        )

        if not data_jogo:
            continue

        data_utc = datetime.fromisoformat(
            data_jogo.replace("Z", "+00:00")
        )

        data_local = data_utc.astimezone(FUSO)

        status = (
            competicao
            .get("status", {})
            .get("type", {})
            .get("description", "Sem informação")
        )

        nome_mandante = (
            mandante.get("team", {})
            .get("displayName", "Mandante")
        )

        nome_visitante = (
            visitante.get("team", {})
            .get("displayName", "Visitante")
        )

        jogos.append({
            "id": str(evento.get("id", "")),
            "data": data_local,
            "mandante": nome_mandante,
            "visitante": nome_visitante,
            "liga": nome_liga,
            "status": status,
            "local": (
                competicao.get("venue", {})
                .get("fullName", "Local não informado")
            ),
        })

    return jogos


def buscar_todos_jogos(ligas, quantidade_dias):
    agora = datetime.now(FUSO)
    data_inicio = agora.strftime("%Y%m%d")
    data_fim = (agora + timedelta(days=quantidade_dias)).strftime("%Y%m%d")

    jogos = []
    erros = []

    for nome_liga in ligas:
        slug = LIGAS[nome_liga]

        try:
            jogos_liga = extrair_jogos(
                slug,
                nome_liga,
                data_inicio,
                data_fim,
            )

            for jogo in jogos_liga:
                if jogo["data"] >= agora:
                    jogos.append(jogo)

        except requests.exceptions.HTTPError as erro:
            codigo = erro.response.status_code if erro.response is not None else "?"
            erros.append(
                f"{nome_liga}: a ESPN respondeu com erro HTTP {codigo}. "
                f"Isso costuma indicar bloqueio por excesso de requisições "
                f"ou por vir de um servidor de nuvem."
            )

        except requests.exceptions.Timeout:
            erros.append(
                f"{nome_liga}: a requisição excedeu o tempo limite (20s)."
            )

        except requests.exceptions.RequestException as erro:
            erros.append(f"{nome_liga}: falha de conexão ({erro}).")

        except Exception as erro:
            erros.append(f"{nome_liga}: erro inesperado ({erro}).")

    jogos.sort(key=lambda jogo: jogo["data"])

    jogos_unicos = []
    ids_vistos = set()

    for jogo in jogos:
        chave = jogo["id"]

        if chave in ids_vistos:
            continue

        ids_vistos.add(chave)
        jogos_unicos.append(jogo)

    return jogos_unicos, erros


# ============================================================
# EXIBIÇÃO DAS POSSIBILIDADES
# ============================================================

def mostrar_previsao(mandante, visitante):
    previsao = calcular_previsao(
        mandante,
        visitante,
    )

    st.subheader(
        f"{mandante} x {visitante}"
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Gols esperados",
        f"{previsao['total_gols']:.2f}",
    )

    col2.metric(
        "Gols do mandante",
        f"{previsao['gols_casa']:.2f}",
    )

    col3.metric(
        "Gols do visitante",
        f"{previsao['gols_fora']:.2f}",
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
            "Placar": item["Placar"],
            "Probabilidade": porcentagem(
                item["Probabilidade"]
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
            "Probabilidade": porcentagem(
                probabilidade
            ),
        })

    st.dataframe(
        tabela_escanteios,
        use_container_width=True,
        hide_index=True,
    )

    st.warning(
        "A previsão é estatística e não garante "
        "o resultado real."
    )


# ============================================================
# INTERFACE
# ============================================================

st.title("⚽ Previsor de Futebol")
st.caption(
    "Lista de jogos, horários e possibilidades estatísticas"
)

st.sidebar.header("Filtros dos jogos")

periodo = st.sidebar.selectbox(
    "Buscar jogos dos próximos:",
    [
        "2 dias",
        "7 dias",
        "15 dias",
        "30 dias",
    ],
)

dias = {
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
    "🔎 Buscar jogos",
    type="primary",
    use_container_width=True,
)

with st.sidebar.expander("🔧 Diagnóstico de conexão"):
    st.caption(
        "Se a busca continuar sem trazer jogos, use este botão para "
        "testar a conexão direta com a ESPN e ver a resposta bruta."
    )

    liga_teste = st.selectbox(
        "Liga para testar:",
        list(LIGAS.keys()),
        key="liga_teste",
    )

    if st.button("Testar conexão agora"):
        slug_teste = LIGAS[liga_teste]
        url_teste = f"{ESPN_BASE}/{slug_teste}/scoreboard"

        try:
            resposta_teste = requests.get(
                url_teste,
                params={"limit": 20},
                timeout=20,
                headers=HEADERS_ESPN,
            )

            st.write(f"URL: {url_teste}")
            st.write(f"Status HTTP: {resposta_teste.status_code}")

            if resposta_teste.ok:
                quantidade_eventos = len(
                    resposta_teste.json().get("events", [])
                )
                st.success(
                    f"Conexão OK. {quantidade_eventos} evento(s) "
                    f"encontrados sem filtro de data."
                )
            else:
                st.error(
                    f"A ESPN recusou a requisição "
                    f"(HTTP {resposta_teste.status_code}). "
                    f"Trecho da resposta: {resposta_teste.text[:300]}"
                )

        except Exception as erro:
            st.error(f"Falha ao conectar: {erro}")

if "jogos" not in st.session_state:
    st.session_state.jogos = []

if "erros" not in st.session_state:
    st.session_state.erros = []

if "ja_buscou" not in st.session_state:
    st.session_state.ja_buscou = False


if buscar:
    if not ligas_selecionadas:
        st.error(
            "Selecione pelo menos uma liga."
        )

    else:
        with st.spinner(
            "Buscando jogos na ESPN..."
        ):
            jogos, erros = buscar_todos_jogos(
                ligas_selecionadas,
                dias,
            )

        st.session_state.jogos = jogos
        st.session_state.erros = erros
        st.session_state.ja_buscou = True


if st.session_state.erros:
    st.error(
        f"⚠️ {len(st.session_state.erros)} liga(s) falharam na busca. "
        f"Veja os detalhes abaixo."
    )

    with st.expander("Avisos da busca", expanded=True):
        for erro in st.session_state.erros:
            st.warning(erro)


jogos = st.session_state.jogos

st.header("Lista de jogos")

if not jogos:
    if st.session_state.ja_buscou:
        st.warning(
            "A busca foi feita, mas nenhum jogo foi encontrado para "
            "as ligas e o período selecionados. Isso pode significar "
            "que não há partidas marcadas nesse intervalo, ou que a "
            "ESPN recusou a requisição — use o diagnóstico de conexão "
            "na barra lateral para verificar."
        )
    else:
        st.info(
            "Selecione as ligas na barra lateral "
            "e clique em 'Buscar jogos'."
        )

else:
    opcoes = []

    for indice, jogo in enumerate(jogos):
        horario = jogo["data"].strftime(
            "%d/%m/%Y às %H:%M"
        )

        opcoes.append(
            f"{horario} | "
            f"{jogo['mandante']} x "
            f"{jogo['visitante']} | "
            f"{jogo['liga']}"
        )

    indice_escolhido = st.selectbox(
        "Selecione um jogo:",
        range(len(jogos)),
        format_func=lambda indice: opcoes[indice],
    )

    jogo = jogos[indice_escolhido]

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Data e horário",
        jogo["data"].strftime(
            "%d/%m/%Y %H:%M"
        ),
    )

    col2.metric(
        "Competição",
        jogo["liga"],
    )

    col3.metric(
        "Status",
        jogo["status"],
    )

    st.write(
        f"**Local:** {jogo['local']}"
    )

    if st.button(
        "📊 Ver possibilidades estatísticas",
        type="primary",
        use_container_width=True,
    ):
        mostrar_previsao(
            jogo["mandante"],
            jogo["visitante"],
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
    if (
        not mandante_manual.strip()
        or not visitante_manual.strip()
    ):
        st.error(
            "Digite os dois times."
        )

    else:
        mostrar_previsao(
            mandante_manual,
            visitante_manual,
        )
