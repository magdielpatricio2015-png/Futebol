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
FUSO_UTC = ZoneInfo("UTC")

# TheSportsDB oferece uma chave PÚBLICA de testes ("3"), sem necessidade
# de cadastro nenhum — é a mesma usada por qualquer pessoa no mundo.
# Por ser compartilhada, o limite de 30 requisições/minuto é global, não
# individual, então pode falhar ocasionalmente em horários de pico —
# nesse caso, basta tentar buscar de novo em alguns segundos.
THESPORTSDB_BASE = "https://www.thesportsdb.com/api/v1/json/3"

# Não uso IDs numéricos fixos (que mudam e são fáceis de errar sem poder
# confirmar). Em vez disso, o app baixa a lista completa de ligas de
# futebol da TheSportsDB e localiza o ID certo pelo nome, usando estes
# termos de busca em inglês (idioma da base de dados).
LIGAS_BUSCA = {
    "Brasil - Série A": ["brazilian serie a"],
    "Brasil - Série B": ["brazilian serie b"],
    "Libertadores": ["copa libertadores"],
    "Sul-Americana": ["copa sudamericana"],
    "Premier League": ["english premier league"],
    "Champions League": ["uefa champions league"],
    "Europa League": ["uefa europa league"],
    "Conference League": ["uefa europa conference league"],
    "La Liga": ["spanish la liga"],
    "Serie A Italiana": ["italian serie a"],
    "Bundesliga": ["german bundesliga"],
    "Ligue 1": ["french ligue 1"],
    "Primeira Liga": ["portuguese primeira liga"],
    "Eredivisie": ["dutch eredivisie"],
    "MLS": ["american major league soccer"],
    "Liga MX": ["mexican liga mx", "mexican primera division"],
    "Liga Saudita": ["saudi professional league", "saudi arabian league"],
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
# BUSCA NA THESPORTSDB (sem cadastro)
# ============================================================

@st.cache_data(ttl=604800, show_spinner=False)  # 7 dias — a lista de ligas quase não muda
def obter_todas_ligas_futebol():
    resposta = requests.get(
        f"{THESPORTSDB_BASE}/all_leagues.php",
        timeout=20,
    )

    resposta.raise_for_status()
    dados = resposta.json()
    ligas = dados.get("leagues") or []

    return [liga for liga in ligas if liga.get("strSport") == "Soccer"]


def resolver_id_liga(nome_liga, todas_ligas):
    termos_busca = LIGAS_BUSCA[nome_liga]

    nomes_normalizados = {
        normalizar(liga["strLeague"]): liga["idLeague"]
        for liga in todas_ligas
        if liga.get("strLeague")
    }

    for termo in termos_busca:
        termo_normalizado = normalizar(termo)

        if termo_normalizado in nomes_normalizados:
            return nomes_normalizados[termo_normalizado]

        semelhantes = get_close_matches(
            termo_normalizado,
            nomes_normalizados.keys(),
            n=1,
            cutoff=0.6,
        )

        if semelhantes:
            return nomes_normalizados[semelhantes[0]]

    return None


@st.cache_data(ttl=900, show_spinner=False)
def buscar_proximos_jogos_liga(league_id):
    """
    A TheSportsDB (chave gratuita) retorna os próximos ~15 jogos de uma
    liga, sem filtro de data — filtramos localmente pelo período
    escolhido depois de baixar.
    """
    resposta = requests.get(
        f"{THESPORTSDB_BASE}/eventsnextleague.php",
        params={"id": league_id},
        timeout=20,
    )

    resposta.raise_for_status()

    return resposta.json()


def extrair_jogos(league_id, nome_liga):
    dados = buscar_proximos_jogos_liga(league_id)
    eventos = dados.get("events") or []

    jogos = []

    for evento in eventos:
        data_utc = None
        timestamp = evento.get("strTimestamp")

        if timestamp:
            try:
                data_utc = datetime.fromisoformat(
                    timestamp.replace("Z", "+00:00")
                )

                if data_utc.tzinfo is None:
                    data_utc = data_utc.replace(tzinfo=FUSO_UTC)

            except ValueError:
                data_utc = None

        if data_utc is None:
            data_evento = evento.get("dateEvent")
            hora_evento = evento.get("strTime") or "00:00:00"

            if not data_evento:
                continue

            try:
                data_utc = datetime.fromisoformat(
                    f"{data_evento}T{hora_evento}"
                ).replace(tzinfo=FUSO_UTC)

            except ValueError:
                continue

        data_local = data_utc.astimezone(FUSO)

        jogos.append({
            "id": str(evento.get("idEvent", "")),
            "data": data_local,
            "mandante": evento.get("strHomeTeam", "Mandante"),
            "visitante": evento.get("strAwayTeam", "Visitante"),
            "liga": nome_liga,
            "status": evento.get("strStatus") or "Agendado",
            "local": evento.get("strVenue") or "Local não informado",
        })

    return jogos


def buscar_todos_jogos(ligas, quantidade_dias):
    agora = datetime.now(FUSO)
    limite = agora + timedelta(days=quantidade_dias)

    jogos = []
    erros = []

    try:
        todas_ligas = obter_todas_ligas_futebol()
    except Exception as erro:
        return [], [f"Não foi possível carregar a lista de ligas da TheSportsDB: {erro}"]

    for nome_liga in ligas:
        try:
            league_id = resolver_id_liga(nome_liga, todas_ligas)

            if not league_id:
                erros.append(
                    f"{nome_liga}: não foi possível localizar essa liga "
                    f"na base da TheSportsDB."
                )
                continue

            jogos_liga = extrair_jogos(league_id, nome_liga)

            for jogo in jogos_liga:
                if agora <= jogo["data"] <= limite:
                    jogos.append(jogo)

        except requests.exceptions.HTTPError as erro:
            codigo = erro.response.status_code if erro.response is not None else "?"

            if codigo == 429:
                erros.append(
                    f"{nome_liga}: limite de requisições por minuto atingido "
                    f"(HTTP 429). Espere alguns segundos e tente de novo — "
                    f"esse limite é compartilhado por todos que usam a "
                    f"chave pública."
                )
            else:
                erros.append(f"{nome_liga}: erro HTTP {codigo}.")

        except requests.exceptions.Timeout:
            erros.append(f"{nome_liga}: a requisição excedeu o tempo limite.")

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
    list(LIGAS_BUSCA.keys()),
    default=[
        "Brasil - Série A",
        "Libertadores",
        "Premier League",
        "Champions League",
    ],
)

st.sidebar.caption(
    "⚠️ A fonte gratuita (TheSportsDB) retorna só os próximos ~15 jogos "
    "de cada liga. Em ligas muito movimentadas, buscar '30 dias' pode "
    "não trazer tudo que existe nesse intervalo — apenas os jogos mais "
    "próximos já cobrem a maior parte dos casos."
)

buscar = st.sidebar.button(
    "🔎 Buscar jogos",
    type="primary",
    use_container_width=True,
)

with st.sidebar.expander("🔧 Diagnóstico"):
    st.caption(
        "Testa se a TheSportsDB está respondendo e mostra qual ID de "
        "liga foi encontrado para o nome escolhido."
    )

    liga_teste = st.selectbox(
        "Liga para testar:",
        list(LIGAS_BUSCA.keys()),
        key="liga_teste",
    )

    if st.button("Testar conexão agora"):
        try:
            todas_ligas_teste = obter_todas_ligas_futebol()
            league_id_teste = resolver_id_liga(liga_teste, todas_ligas_teste)

            if not league_id_teste:
                st.error(
                    "Não encontrei essa liga na base da TheSportsDB "
                    "(pode ter mudado de nome)."
                )
            else:
                resposta_teste = requests.get(
                    f"{THESPORTSDB_BASE}/eventsnextleague.php",
                    params={"id": league_id_teste},
                    timeout=15,
                )

                st.write(f"ID encontrado: {league_id_teste}")
                st.write(f"Status HTTP: {resposta_teste.status_code}")

                if resposta_teste.ok:
                    eventos = resposta_teste.json().get("events") or []
                    st.success(
                        f"Conexão OK. {len(eventos)} jogo(s) futuro(s) "
                        f"encontrados para essa liga."
                    )
                else:
                    st.error(f"Resposta: {resposta_teste.text[:300]}")

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
            "Buscando jogos..."
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
        f"⚠️ {len(st.session_state.erros)} liga(s) tiveram problema na busca. "
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
            "as ligas e o período selecionados."
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
