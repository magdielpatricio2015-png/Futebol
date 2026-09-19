import math
import re
import unicodedata
from difflib import get_close_matches

import streamlit as st


# ============================================================
# CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="Previsor de Futebol",
    page_icon="⚽",
    layout="wide",
)

st.title("⚽ Previsor de Futebol")
st.caption("Estimativa estatística de placar, gols e escanteios")


# ============================================================
# RATINGS DOS TIMES
# ============================================================

TEAM_RATINGS = {
    # Brasil
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
    "athletico pr": 80.5,
    "bragantino": 79.0,
    "ceara": 76.0,
    "vitoria": 75.5,
    "juventude": 75.0,
    "sport": 74.0,

    # América do Sul
    "river plate": 84.0,
    "boca juniors": 83.0,
    "racing": 80.0,
    "independiente": 78.5,
    "nacional": 78.0,
    "penarol": 78.0,
    "colo colo": 77.0,

    # Inglaterra
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

    # Espanha
    "real madrid": 94.0,
    "barcelona": 91.0,
    "atletico madrid": 88.0,
    "athletic bilbao": 84.0,
    "real sociedad": 84.0,
    "villarreal": 82.0,
    "sevilla": 80.0,
    "real betis": 81.0,

    # Itália
    "inter": 90.5,
    "internazionale": 90.5,
    "milan": 87.5,
    "ac milan": 87.5,
    "juventus": 87.5,
    "napoli": 86.5,
    "atalanta": 86.0,
    "roma": 84.0,
    "lazio": 83.0,

    # Alemanha
    "bayern": 92.0,
    "bayern munich": 92.0,
    "borussia dortmund": 87.5,
    "bayer leverkusen": 90.0,
    "rb leipzig": 86.5,

    # França / Portugal / Holanda
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

    # Seleções
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
    "estados unidos": 80.5,
    "japao": 80.0,
}


ALIASES = {
    "mengao": "flamengo",
    "mengo": "flamengo",
    "galo": "atletico mineiro",
    "verdão": "palmeiras",
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


def obter_rating(nome_time):
    nome_original = nome_time.strip()
    nome = normalizar(nome_original)

    if nome in ALIASES:
        nome = ALIASES[nome]

    if nome in TEAM_RATINGS:
        return TEAM_RATINGS[nome], nome_original, "exato"

    # Procura parcial
    for time, rating in TEAM_RATINGS.items():
        if nome in time or time in nome:
            return rating, nome_original, "aproximado"

    # Procura semelhante
    similares = get_close_matches(
        nome,
        TEAM_RATINGS.keys(),
        n=1,
        cutoff=0.70,
    )

    if similares:
        time_encontrado = similares[0]
        return TEAM_RATINGS[time_encontrado], nome_original, "semelhante"

    # Rating padrão para time desconhecido
    return 75.0, nome_original, "padrão"


def limitar(valor, minimo, maximo):
    return max(minimo, min(valor, maximo))


def porcentagem(valor):
    return f"{valor * 100:.1f}%"


def poisson(k, media):
    """
    Probabilidade de acontecerem exatamente k eventos
    considerando uma distribuição de Poisson.
    """
    return math.exp(-media) * (media ** k) / math.factorial(k)


# ============================================================
# MODELO DE PREVISÃO
# ============================================================

def calcular_previsao(time_casa, time_fora):
    rating_casa, nome_casa, metodo_casa = obter_rating(time_casa)
    rating_fora, nome_fora, metodo_fora = obter_rating(time_fora)

    diferenca_rating = rating_casa - rating_fora

    # Gols esperados
    gols_casa = limitar(
        1.35 + diferenca_rating * 0.018,
        0.20,
        3.80,
    )

    gols_fora = limitar(
        1.05 - diferenca_rating * 0.012,
        0.20,
        3.50,
    )

    # Matriz de placares de 0x0 até 8x8
    matriz = []

    for gols_mandante in range(9):
        linha = []

        for gols_visitante in range(9):
            probabilidade = (
                poisson(gols_mandante, gols_casa)
                * poisson(gols_visitante, gols_fora)
            )
            linha.append(probabilidade)

        matriz.append(linha)

    # Normaliza a matriz
    soma = sum(sum(linha) for linha in matriz)

    for mandante in range(9):
        for visitante in range(9):
            matriz[mandante][visitante] /= soma

    placares = []

    for mandante in range(9):
        for visitante in range(9):
            placares.append(
                {
                    "placar": f"{mandante} x {visitante}",
                    "gols_casa": mandante,
                    "gols_fora": visitante,
                    "probabilidade": matriz[mandante][visitante],
                }
            )

    placares.sort(
        key=lambda item: item["probabilidade"],
        reverse=True,
    )

    # Resultado final
    prob_casa = 0.0
    prob_empate = 0.0
    prob_fora = 0.0

    for mandante in range(9):
        for visitante in range(9):
            probabilidade = matriz[mandante][visitante]

            if mandante > visitante:
                prob_casa += probabilidade
            elif mandante == visitante:
                prob_empate += probabilidade
            else:
                prob_fora += probabilidade

    # Mais de 2.5 gols
    prob_over_25 = 0.0

    for mandante in range(9):
        for visitante in range(9):
            if mandante + visitante >= 3:
                prob_over_25 += matriz[mandante][visitante]

    # Ambas marcam
    prob_ambas_marcam = 0.0

    for mandante in range(1, 9):
        for visitante in range(1, 9):
            prob_ambas_marcam += matriz[mandante][visitante]

    # Escanteios
    # Modelo separado dos gols.
    media_escanteios = limitar(
        9.4 + ((rating_casa + rating_fora - 150) * 0.025),
        6.0,
        14.0,
    )

    linhas_escanteios = {}

    for linha in [7.5, 8.5, 9.5, 10.5, 11.5]:
        probabilidade_mais = 0.0

        for quantidade in range(30):
            if quantidade > linha:
                probabilidade_mais += poisson(
                    quantidade,
                    media_escanteios,
                )

        linhas_escanteios[linha] = probabilidade_mais

    return {
        "time_casa": nome_casa,
        "time_fora": nome_fora,
        "rating_casa": rating_casa,
        "rating_fora": rating_fora,
        "metodo_casa": metodo_casa,
        "metodo_fora": metodo_fora,
        "gols_casa": gols_casa,
        "gols_fora": gols_fora,
        "total_gols": gols_casa + gols_fora,
        "placares": placares[:10],
        "prob_casa": prob_casa,
        "prob_empate": prob_empate,
        "prob_fora": prob_fora,
        "over_25": prob_over_25,
        "under_25": 1 - prob_over_25,
        "ambas_marcam": prob_ambas_marcam,
        "media_escanteios": media_escanteios,
        "linhas_escanteios": linhas_escanteios,
    }


# ============================================================
# INTERFACE
# ============================================================

st.sidebar.header("Configuração do jogo")

time_casa = st.sidebar.text_input(
    "Time mandante",
    value="Flamengo",
)

time_fora = st.sidebar.text_input(
    "Time visitante",
    value="Palmeiras",
)

calcular = st.sidebar.button(
    "CALCULAR PREVISÃO",
    type="primary",
    use_container_width=True,
)


if calcular:
    if not time_casa.strip() or not time_fora.strip():
        st.error("Digite os dois times.")
        st.stop()

    previsao = calcular_previsao(
        time_casa,
        time_fora,
    )

    st.success(
        f"Previsão calculada para "
        f"{previsao['time_casa']} x {previsao['time_fora']}"
    )

    st.subheader("Resumo da previsão")

    coluna1, coluna2, coluna3, coluna4 = st.columns(4)

    coluna1.metric(
        "Gols esperados",
        f"{previsao['total_gols']:.2f}",
    )

    coluna2.metric(
        "Gols do mandante",
        f"{previsao['gols_casa']:.2f}",
    )

    coluna3.metric(
        "Gols do visitante",
        f"{previsao['gols_fora']:.2f}",
    )

    coluna4.metric(
        "Escanteios esperados",
        f"{previsao['media_escanteios']:.1f}",
    )

    st.subheader("Probabilidade do resultado")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Vitória do mandante",
        porcentagem(previsao["prob_casa"]),
    )

    col2.metric(
        "Empate",
        porcentagem(previsao["prob_empate"]),
    )

    col3.metric(
        "Vitória do visitante",
        porcentagem(previsao["prob_fora"]),
    )

    st.subheader("Mercados de gols")

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

    st.subheader("Placares exatos mais prováveis")

    tabela_placares = []

    for item in previsao["placares"]:
        tabela_placares.append(
            {
                "Placar": item["placar"],
                "Probabilidade": porcentagem(
                    item["probabilidade"]
                ),
            }
        )

    st.dataframe(
        tabela_placares,
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Previsão de escanteios")

    st.write(
        f"Média estimada de escanteios: "
        f"**{previsao['media_escanteios']:.1f}**"
    )

    tabela_escanteios = []

    for linha, probabilidade in previsao[
        "linhas_escanteios"
    ].items():
        tabela_escanteios.append(
            {
                "Linha": f"Mais de {linha} escanteios",
                "Probabilidade": porcentagem(probabilidade),
            }
        )

    st.dataframe(
        tabela_escanteios,
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Informações utilizadas")

    st.write(
        f"Rating do mandante: "
        f"**{previsao['rating_casa']:.1f}** "
        f"({previsao['metodo_casa']})"
    )

    st.write(
        f"Rating do visitante: "
        f"**{previsao['rating_fora']:.1f}** "
        f"({previsao['metodo_fora']})"
    )

    st.warning(
        "A previsão é estatística e não garante o resultado real. "
        "Para melhorar a precisão, use médias recentes de gols, "
        "escanteios, desfalques, escalações e desempenho como mandante "
        "ou visitante."
    )

else:
    st.info(
        "Digite os times na barra lateral e clique em "
        "**CALCULAR PREVISÃO**."
    )

    st.markdown(
        """
        ### O aplicativo calcula:

        - Placares exatos mais prováveis;
        - Quantidade esperada de gols;
        - Probabilidade de vitória, empate e derrota;
        - Mais ou menos de 2.5 gols;
        - Probabilidade de ambas as equipes marcarem;
        - Média esperada de escanteios;
        - Probabilidade de mais de 7.5, 8.5, 9.5, 10.5 e 11.5 escanteios.
        """
    )
