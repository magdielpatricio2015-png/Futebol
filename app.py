import streamlit as st
import math
from typing import Dict, Tuple

# ---------------------- CONFIGURAÇÃO DA PÁGINA ----------------------
st.set_page_config(
    page_title="Previsor de Partidas",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------- ESTILO (seu design criativo) ----------------------
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #f8fafc;
    }
    .titulo {
        font-size: 2.5rem;
        text-align: center;
        color: #fbbf24;
        font-weight: bold;
        margin-bottom: 2rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
    }
    .card {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 2rem;
        margin: 1.5rem 0;
        border-left: 6px solid #3b82f6;
        box-shadow: 0 8px 32px rgba(0,0,0,0.2);
        backdrop-filter: blur(10px);
    }
    .prob-item {
        background: rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 1.2rem;
        margin: 0.8rem 0;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .prob-bar {
        height: 18px;
        border-radius: 9px;
        background: rgba(255,255,255,0.1);
        margin: 0 15px;
        flex: 1;
    }
    .bar-fill {
        height: 100%;
        border-radius: 9px;
        background: linear-gradient(90deg, #3b82f6, #22c55e);
    }
    .team-name {
        font-size: 1.2rem;
        font-weight: bold;
        color: #f1f5f9;
        min-width: 140px;
    }
    .percentage {
        font-weight: bold;
        font-size: 1.3rem;
        min-width: 60px;
        text-align: right;
    }
    .css-1d391kg {
        background-color: rgba(15, 23, 42, 0.9);
    }
    </style>
""", unsafe_allow_html=True)

# ---------------------- DADOS DAS COMPETIÇÕES E RATINGS ----------------------
# Dicionário de times por competição com ratings (base 1500 = média)
TEAMS = {
    "Copa do Mundo 🟢": {
        "Brasil 🇧🇷": 1820,
        "Argentina 🇦🇷": 1800,
        "França 🇫🇷": 1785,
        "Alemanha 🇩🇪": 1760,
        "Espanha 🇪🇸": 1750,
        "Inglaterra 🏴󠁧󠁢󠁥󠁮󠁧󠁿": 1745,
        "Holanda 🇳🇱": 1720,
        "Portugal 🇵🇹": 1710,
        "Uruguai 🇺🇾": 1690,
        "Croácia 🇭🇷": 1680,
    },
    "Brasileirão Série A 🇧🇷": {
        "Palmeiras": 1680,
        "Flamengo": 1660,
        "São Paulo": 1620,
        "Grêmio": 1600,
        "Atlético-MG": 1590,
        "Fluminense": 1580,
        "Internacional": 1570,
        "Athletico-PR": 1550,
        "Corinthians": 1540,
        "Botafogo": 1520,
    },
    "Copa do Brasil 🇧🇷": {  # Usaremos os mesmos times do Brasileirão
        "Palmeiras": 1680, "Flamengo": 1660, "São Paulo": 1620, "Grêmio": 1600,
        "Atlético-MG": 1590, "Fluminense": 1580, "Internacional": 1570, "Athletico-PR": 1550,
        "Corinthians": 1540, "Botafogo": 1520,
    },
    "Premier League 🏴󠁧󠁢󠁥󠁮󠁧󠁿": {
        "Manchester City": 1780, "Liverpool": 1760, "Arsenal": 1730, "Chelsea": 1710,
        "Manchester Utd": 1700, "Tottenham": 1680, "Newcastle": 1660, "Brighton": 1640,
        "Aston Villa": 1620, "West Ham": 1600,
    },
    "La Liga 🇪🇸": {
        "Real Madrid": 1790, "Barcelona": 1770, "Atlético Madrid": 1740, "Sevilla": 1700,
        "Villarreal": 1680, "Real Betis": 1660, "Real Sociedad": 1650, "Athletic Bilbao": 1640,
        "Valencia": 1620, "Osasuna": 1590,
    },
    "Bundesliga 🇩🇪": {
        "Bayern Munique": 1800, "Borussia Dortmund": 1740, "RB Leipzig": 1720,
        "Bayer Leverkusen": 1700, "Eintracht Frankfurt": 1680, "Wolfsburg": 1660,
        "Borussia M'gladbach": 1640, "Freiburg": 1620, "Hoffenheim": 1600, "Mainz": 1580,
    },
    "Série A Italiana 🇮🇹": {
        "Juventus": 1750, "Inter Milão": 1740, "Milan": 1730, "Napoli": 1710,
        "Roma": 1700, "Atalanta": 1680, "Lazio": 1660, "Fiorentina": 1640,
        "Torino": 1620, "Bologna": 1600,
    },
    "Liga dos Campeões 🏆": {
        "Real Madrid": 1790, "Manchester City": 1780, "Bayern Munique": 1800,
        "PSG": 1750, "Barcelona": 1770, "Arsenal": 1730, "Liverpool": 1760,
        "Inter Milão": 1740, "Atlético Madrid": 1740, "Napoli": 1710,
    }
}

# ---------------------- FUNÇÃO DE PREDIÇÃO (MODELO POISSON) ----------------------
def poisson_pmf(k: int, lam: float) -> float:
    """Probabilidade de k gols dada média lam (Poisson)."""
    if lam < 0:
        return 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)

def predict_match(home_team: str, away_team: str, competition: str) -> Dict[str, float]:
    """
    Calcula probabilidades de vitória do time da casa, empate e vitória do visitante.
    Usa modelo de Poisson com ratings e vantagem do campo.
    """
    home_rating = TEAMS[competition][home_team]
    away_rating = TEAMS[competition][away_team]
    home_advantage = 65  # vantagem de jogar em casa em pontos de rating

    # Força relativa ajustada
    # Gols esperados: base * fator de força
    base_home_goals = 1.55
    base_away_goals = 1.15

    rating_diff = home_rating - away_rating + home_advantage
    # Fator multiplicador: time mais forte marca mais e sofre menos
    factor = 10 ** (rating_diff / 400)
    home_lambda = base_home_goals * factor
    away_lambda = base_away_goals / factor

    # Probabilidades até 8 gols (suficiente)
    max_goals = 8
    home_probs = [poisson_pmf(i, home_lambda) for i in range(max_goals + 1)]
    away_probs = [poisson_pmf(i, away_lambda) for i in range(max_goals + 1)]

    home_win_prob = 0.0
    draw_prob = 0.0
    away_win_prob = 0.0

    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            prob = home_probs[i] * away_probs[j]
            if i > j:
                home_win_prob += prob
            elif i == j:
                draw_prob += prob
            else:
                away_win_prob += prob

    # Normalizar (ignorar pequena cauda >8 gols)
    total = home_win_prob + draw_prob + away_win_prob
    if total > 0:
        home_win_prob /= total
        draw_prob /= total
        away_win_prob /= total

    return {
        "home_win": round(home_win_prob * 100, 1),
        "draw": round(draw_prob * 100, 1),
        "away_win": round(away_win_prob * 100, 1)
    }

# ---------------------- INTERFACE ----------------------
st.markdown('<h1 class="titulo">⚽ Previsor de Probabilidades de Partida</h1>', unsafe_allow_html=True)

# Sidebar
st.sidebar.markdown("## 🏆 Selecione a Competição")
competicao_selecionada = st.sidebar.selectbox(
    "Liga ou torneio:",
    list(TEAMS.keys())
)

# Times disponíveis na competição
times = list(TEAMS[competicao_selecionada].keys())

col1, col2 = st.columns(2)
with col1:
    time_casa = st.selectbox("🏠 Time da Casa", times, index=0)
with col2:
    # Garante que o visitante não seja o mesmo (valor padrão diferente)
    visitante_default = times[1] if len(times) > 1 else times[0]
    time_visitante = st.selectbox("✈️ Time Visitante", times, index=1)

# Botão de previsão
if st.button("🔮 Calcular Probabilidades", use_container_width=True):
    if time_casa == time_visitante:
        st.warning("Escolha times diferentes para a previsão.")
    else:
        with st.spinner("Analisando forças..."):
            probs = predict_match(time_casa, time_visitante, competicao_selecionada)

        # Exibição dos resultados
        st.markdown("---")
        st.markdown("## 📊 Probabilidades do Confronto")

        # Cartão principal com os times
        st.markdown(f"""
        <div class="card">
            <div style="display: flex; align-items: center; justify-content: center; gap: 2rem;">
                <span class="team-name" style="font-size:1.6rem;">{time_casa}</span>
                <span style="font-size:1.6rem; color:#fbbf24;">vs</span>
                <span class="team-name" style="font-size:1.6rem;">{time_visitante}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Barras de probabilidade customizadas
        def prob_bar(label, prob, cor):
            st.markdown(f"""
            <div class="prob-item">
                <span class="team-name">{label}</span>
                <div class="prob-bar">
                    <div class="bar-fill" style="width: {prob}%; background: linear-gradient(90deg, {cor}, {cor}88);"></div>
                </div>
                <span class="percentage" style="color: {cor};">{prob}%</span>
            </div>
            """, unsafe_allow_html=True)

        prob_bar("Vitória Casa", probs["home_win"], "#22c55e")
        prob_bar("Empate", probs["draw"], "#eab308")
        prob_bar("Vitória Visitante", probs["away_win"], "#3b82f6")

        # Interpretação rápida
        maior_prob = max(probs, key=probs.get)
        if maior_prob == "home_win":
            st.success(f"✅ O favorito é o **{time_casa}** (jogando em casa).")
        elif maior_prob == "away_win":
            st.info(f"✅ O favorito é o **{time_visitante}** (visitante).")
        else:
            st.warning("⚖️ O confronto está equilibrado, com maior chance de empate.")

# Explicação do modelo
with st.expander("ℹ️ Como funciona a previsão?"):
    st.markdown("""
    - Cada time possui um **rating** (baseado em desempenho histórico) que varia entre 1500 e 1900.
    - A **vantagem de jogar em casa** acrescenta 65 pontos ao rating do mandante.
    - Calculamos os **gols esperados** de cada time usando um fator de força (escala logarítmica).
    - Aplicamos a **distribuição de Poisson** para transformar gols esperados em probabilidades de placares.
    - Somamos as probabilidades dos cenários de vitória, empate e derrota para obter os percentuais exibidos.
    
    ⚠️ Esta é uma simulação baseada em dados fictícios, destinada a fins educacionais e de demonstração.
    """)

# Rodapé
st.markdown("---")
st.caption("Desenvolvido para prever possibilidades de vitória, empate ou derrota | Modelo Poisson • Ratings por competição")