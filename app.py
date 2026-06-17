import streamlit as st

# ---------------------- CONFIGURAÇÃO ----------------------
st.set_page_config(
    page_title="Análise de Futebol",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------- ESTILO CRIATIVO E AGRADÁVEL ----------------------
st.markdown("""
    <style>
    /* Fundo geral */
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #f8fafc;
    }
    
    /* Título principal */
    .titulo {
        font-size: 2.5rem;
        text-align: center;
        color: #fbbf24;
        font-weight: bold;
        margin-bottom: 2rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
    }
    
    /* Cartões de resultado */
    .card {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 2rem;
        margin: 1.5rem 0;
        border-left: 6px solid #3b82f6;
        box-shadow: 0 8px 32px rgba(0,0,0,0.2);
        backdrop-filter: blur(10px);
    }
    
    /* Texto dos times */
    .time {
        font-size: 1.8rem;
        font-weight: bold;
        color: #f1f5f9;
    }
    
    .placar {
        font-size: 2.2rem;
        font-weight: bold;
        color: #fbbf24;
        margin: 0 2rem;
    }
    
    /* Estatísticas */
    .estat-item {
        background: rgba(255,255,255,0.05);
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
    }
    
    /* Sidebar */
    .css-1d391kg {
        background-color: rgba(15, 23, 42, 0.9);
    }
    </style>
""", unsafe_allow_html=True)

# ---------------------- MENU LATERAL - SELETOR DE LIGAS ----------------------
st.sidebar.markdown("## ⚽ Escolha a Competição")

# Lista completa com Copa do Mundo e principais ligas
competicao = st.sidebar.selectbox(
    "Selecione:",
    [
        "Copa do Mundo 🟢",
        "Brasileirão Série A 🇧🇷",
        "Copa do Brasil 🇧🇷",
        "Premier League 🏴󠁧󠁢󠁥󠁮󠁧󠁿",
        "La Liga 🇪🇸",
        "Bundesliga 🇩🇪",
        "Série A Italiana 🇮🇹",
        "Liga dos Campeões 🏆"
    ]
)

# ---------------------- DADOS POR COMPETIÇÃO ----------------------
dados = {
    "Copa do Mundo 🟢": {
        "time_casa": "Brasil",
        "time_visitante": "Argentina",
        "gols_casa": 2,
        "gols_visitante": 1,
        "data": "18/06/2026",
        "estatisticas": {
            "Posse de bola": "52%",
            "Chutes ao gol": "9",
            "Escanteios": "7",
            "Cartões amarelos": "3",
            "Defesas importantes": "4"
        }
    },
    "Brasileirão Série A 🇧🇷": {
        "time_casa": "Palmeiras",
        "time_visitante": "Flamengo",
        "gols_casa": 3,
        "gols_visitante": 2,
        "data": "17/06/2026",
        "estatisticas": {
            "Posse de bola": "56%",
            "Chutes ao gol": "11",
            "Escanteios": "8",
            "Cartões amarelos": "2",
            "Impedimentos": "3"
        }
    },
    "Copa do Brasil 🇧🇷": {
        "time_casa": "São Paulo",
        "time_visitante": "Grêmio",
        "gols_casa": 1,
        "gols_visitante": 1,
        "data": "16/06/2026",
        "estatisticas": {
            "Posse de bola": "48%",
            "Chutes ao gol": "5",
            "Escanteios": "4",
            "Cartões amarelos": "4",
            "Pênaltis marcados": "0"
        }
    },
    "Premier League 🏴󠁧󠁢󠁥󠁮󠁧󠁿": {
        "time_casa": "Manchester City",
        "time_visitante": "Liverpool",
        "gols_casa": 2,
        "gols_visitante": 2,
        "data": "15/06/2026",
        "estatisticas": {
            "Posse de bola": "62%",
            "Chutes ao gol": "13",
            "Escanteios": "9",
            "Cartões amarelos": "1",
            "Passes certos": "89%"
        }
    },
    "La Liga 🇪🇸": {
        "time_casa": "Real Madrid",
        "time_visitante": "Barcelona",
        "gols_casa": 4,
        "gols_visitante": 1,
        "data": "14/06/2026",
        "estatisticas": {
            "Posse de bola": "59%",
            "Chutes ao gol": "10",
            "Escanteios": "6",
            "Cartões amarelos": "2",
            "Faltas cometidas": "12"
        }
    },
    "Bundesliga 🇩🇪": {
        "time_casa": "Bayern de Munique",
        "time_visitante": "Borussia Dortmund",
        "gols_casa": 3,
        "gols_visitante": 0,
        "data": "13/06/2026",
        "estatisticas": {
            "Posse de bola": "65%",
            "Chutes ao gol": "12",
            "Escanteios": "7",
            "Cartões amarelos": "1",
            "Impedimentos": "2"
        }
    },
    "Série A Italiana 🇮🇹": {
        "time_casa": "Juventus",
        "time_visitante": "Milan",
        "gols_casa": 1,
        "gols_visitante": 0,
        "data": "12/06/2026",
        "estatisticas": {
            "Posse de bola": "51%",
            "Chutes ao gol": "6",
            "Escanteios": "3",
            "Cartões amarelos": "3",
            "Defesas": "5"
        }
    },
    "Liga dos Campeões 🏆": {
        "time_casa": "Paris Saint-Germain",
        "time_visitante": "Manchester City",
        "gols_casa": 2,
        "gols_visitante": 3,
        "data": "11/06/2026",
        "estatisticas": {
            "Posse de bola": "47%",
            "Chutes ao gol": "8",
            "Escanteios": "5",
            "Cartões amarelos": "2",
            "Melhor jogador": "Haaland"
        }
    }
}

# ---------------------- EXIBIÇÃO DOS DADOS (SEM ERROS DE SINTAXE) ----------------------
try:
    dados_partida = dados[competicao]
    
    st.markdown(f'<h1 class="titulo">{competicao.split(" ")[0]} 🏆</h1>')

    # Cartão de Resultado
    st.markdown(f"""
    <div class="card">
        <h3 style="text-align:center; color:#93c5fd;">📅 {dados_partida['data']}</h3>
        <div style="display:flex; align-items:center; justify-content:center; margin:2rem 0;">
            <span class="time">{dados_partida['time_casa']}</span>
            <span class="placar">{dados_partida['gols_casa']} x {dados_partida['gols_visitante']}</span>
            <span class="time">{dados_partida['time_visitante']}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Estatísticas
    st.subheader("📊 Estatísticas Completas")
    for item, valor in dados_partida['estatisticas'].items():
        st.markdown(f'<div class="estat-item"><strong>{item}:</strong> {valor}</div>', unsafe_allow_html=True)

    # Resultado final
    if dados_partida['gols_casa'] > dados_partida['gols_visitante']:
        mensagem = f"✅ Vitória do {dados_partida['time_casa']}!"
        cor = "#22c55e"
    elif dados_partida['gols_visitante'] > dados_partida['gols_casa']:
        mensagem = f"✅ Vitória do {dados_partida['time_visitante']}!"
        cor = "#22c55e"
    else:
        mensagem = "⚖️ Partida terminou empatada!"
        cor = "#eab308"

    st.markdown(f"""
    <div style="background:rgba(255,255,255,0.1); padding:1rem; border-radius:8px; text-align:center; margin-top:2rem; border-left:5px solid {cor};">
        <h3>{mensagem}</h3>
    </div>
    """, unsafe_allow_html=True)

except Exception as e:
    st.error(f"⚠️ Erro: {str(e)}")

# ---------------------- RODAPÉ ----------------------
st.markdown("---")
st.caption("Desenvolvido para acompanhar as melhores competições do mundo | Versão 2.0")
