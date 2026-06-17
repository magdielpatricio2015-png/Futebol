import streamlit as st
import requests
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

# ---------------------- CONFIGURAÇÃO DA PÁGINA ----------------------
st.set_page_config(
    page_title="Previsor de Futebol",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------- NOVO ESTILO: CLARO E LEGÍVEL ----------------------
st.markdown("""
    <style>
    /* Fundo branco limpo */
    .stApp {
        background-color: #f8fafc;
        color: #0f172a;
    }
    /* Título principal */
    .titulo {
        font-size: 2.5rem;
        text-align: center;
        color: #1e40af;
        font-weight: 800;
        margin-bottom: 2rem;
        letter-spacing: -0.5px;
    }
    /* Cartões */
    .card {
        background: #ffffff;
        border-radius: 20px;
        padding: 2rem;
        margin: 1.5rem 0;
        border-left: 6px solid #3b82f6;
        box-shadow: 0 10px 25px rgba(0,0,0,0.05);
        border: 1px solid #e2e8f0;
    }
    .prob-item {
        background: #f1f5f9;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin: 0.8rem 0;
        display: flex;
        align-items: center;
        justify-content: space-between;
        border: 1px solid #e2e8f0;
    }
    .prob-bar {
        height: 14px;
        border-radius: 7px;
        background: #e2e8f0;
        margin: 0 15px;
        flex: 1;
        overflow: hidden;
    }
    .bar-fill {
        height: 100%;
        border-radius: 7px;
    }
    .team-name {
        font-size: 1.15rem;
        font-weight: 700;
        color: #1e293b;
        min-width: 140px;
    }
    .percentage {
        font-weight: 800;
        font-size: 1.3rem;
        min-width: 60px;
        text-align: right;
        color: #0f172a;
    }
    .match-row {
        background: white;
        border-radius: 12px;
        padding: 1.2rem;
        margin: 0.6rem 0;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 2px 8px rgba(0,0,0,0.03);
        border: 1px solid #e2e8f0;
        transition: all 0.2s;
    }
    .match-row:hover {
        box-shadow: 0 6px 18px rgba(0,0,0,0.08);
        border-color: #3b82f6;
    }
    .match-time {
        font-size: 1rem;
        color: #64748b;
        min-width: 120px;
    }
    .match-teams {
        font-size: 1.1rem;
        font-weight: 600;
        color: #1e293b;
    }
    .match-league {
        font-size: 0.85rem;
        color: #3b82f6;
        font-weight: 600;
        text-transform: uppercase;
    }
    /* Sidebar clara */
    .css-1d391kg {
        background-color: #ffffff;
        border-right: 1px solid #e2e8f0;
    }
    .stButton>button {
        background: linear-gradient(135deg, #3b82f6, #2563eb);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 0.8rem 1.5rem;
        font-weight: 700;
        transition: all 0.2s;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(37,99,235,0.3);
    }
    </style>
""", unsafe_allow_html=True)

# ---------------------- FUNÇÃO PARA BUSCAR PRÓXIMOS JOGOS (API Football-Data) ----------------------
def get_upcoming_matches(api_key: str, hours_ahead: int = 48) -> List[Dict]:
    """
    Busca jogos agendados para as próximas horas usando football-data.org.
    Retorna lista de partidas formatadas.
    """
    url = "https://api.football-data.org/v4/matches"
    headers = {"X-Auth-Token": api_key}

    # Filtrar pelas próximas 48h
    now = datetime.now(timezone.utc)
    date_from = now.strftime("%Y-%m-%d")
    date_to = (now + timedelta(hours=hours_ahead)).strftime("%Y-%m-%d")

    params = {
        "dateFrom": date_from,
        "dateTo": date_to,
        "status": "SCHEDULED",
        "limit": 50  # máximo razoável
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            matches = []
            for m in data.get("matches", []):
                utc_time = datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00"))
                local_time = utc_time.astimezone()  # converte para fuso local
                matches.append({
                    "home": m["homeTeam"]["name"],
                    "away": m["awayTeam"]["name"],
                    "datetime": utc_time,
                    "formatted_time": local_time.strftime("%d/%m %H:%M"),
                    "competition": m["competition"]["name"],
                    "id": m["id"]
                })
            # Ordenar por data
            matches.sort(key=lambda x: x["datetime"])
            return matches[:20]  # mostra no máximo 20
        else:
            st.sidebar.warning(f"Erro na API: {response.status_code}")
            return []
    except Exception as e:
        st.sidebar.error(f"Falha na conexão: {e}")
        return []

# ---------------------- DADOS DE RATINGS (MANTIDOS PARA PREVISÃO) ----------------------
TEAMS = {
    "Copa do Mundo 🟢": {
        "Brasil 🇧🇷": 1820, "Argentina 🇦🇷": 1800, "França 🇫🇷": 1785, "Alemanha 🇩🇪": 1760,
        "Espanha 🇪🇸": 1750, "Inglaterra 🏴󠁧󠁢󠁥󠁮󠁧󠁿": 1745, "Holanda 🇳🇱": 1720, "Portugal 🇵🇹": 1710
    },
    "Brasileirão Série A 🇧🇷": {
        "Palmeiras": 1680, "Flamengo": 1660, "São Paulo": 1620, "Grêmio": 1600,
        "Atlético-MG": 1590, "Fluminense": 1580, "Internacional": 1570, "Athletico-PR": 1550
    },
    "Premier League 🏴󠁧󠁢󠁥󠁮󠁧󠁿": {
        "Manchester City": 1780, "Liverpool": 1760, "Arsenal": 1730, "Chelsea": 1710,
        "Manchester Utd": 1700, "Tottenham": 1680, "Newcastle": 1660, "Brighton": 1640
    },
    "La Liga 🇪🇸": {
        "Real Madrid": 1790, "Barcelona": 1770, "Atlético Madrid": 1740, "Sevilla": 1700,
        "Villarreal": 1680, "Real Betis": 1660, "Real Sociedad": 1650, "Athletic Bilbao": 1640
    },
    "Bundesliga 🇩🇪": {
        "Bayern Munique": 1800, "Borussia Dortmund": 1740, "RB Leipzig": 1720,
        "Bayer Leverkusen": 1700, "Eintracht Frankfurt": 1680, "Wolfsburg": 1660
    },
    "Série A Italiana 🇮🇹": {
        "Juventus": 1750, "Inter Milão": 1740, "Milan": 1730, "Napoli": 1710,
        "Roma": 1700, "Atalanta": 1680, "Lazio": 1660, "Fiorentina": 1640
    },
    "Liga dos Campeões 🏆": {
        "Real Madrid": 1790, "Manchester City": 1780, "Bayern Munique": 1800,
        "PSG": 1750, "Barcelona": 1770, "Arsenal": 1730, "Liverpool": 1760, "Inter Milão": 1740
    }
}

# ---------------------- MODELO DE PREDIÇÃO (POISSON) ----------------------
def poisson_pmf(k, lam):
    if lam < 0: return 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)

def predict_match(home_team, away_team, competition):
    home_rating = TEAMS[competition][home_team]
    away_rating = TEAMS[competition][away_team]
    home_advantage = 65
    base_home = 1.55
    base_away = 1.15
    rating_diff = home_rating - away_rating + home_advantage
    factor = 10 ** (rating_diff / 400)
    home_lambda = base_home * factor
    away_lambda = base_away / factor

    max_g = 8
    home_probs = [poisson_pmf(i, home_lambda) for i in range(max_g+1)]
    away_probs = [poisson_pmf(i, away_lambda) for i in range(max_g+1)]

    home_win = draw = away_win = 0.0
    for i in range(max_g+1):
        for j in range(max_g+1):
            prob = home_probs[i] * away_probs[j]
            if i > j: home_win += prob
            elif i == j: draw += prob
            else: away_win += prob
    total = home_win + draw + away_win
    return {
        "home_win": round((home_win/total)*100, 1),
        "draw": round((draw/total)*100, 1),
        "away_win": round((away_win/total)*100, 1)
    }

# ---------------------- INTERFACE ----------------------
st.markdown('<h1 class="titulo">⚽ Previsor de Jogos e Probabilidades</h1>', unsafe_allow_html=True)

# ---- SIDEBAR ----
st.sidebar.markdown("## 🔑 Chave da API (opcional)")
api_key = st.sidebar.text_input(
    "Football-Data.org API Key",
    type="password",
    help="Obtenha gratuitamente em https://www.football-data.org/client/register"
)
if not api_key:
    st.sidebar.info("👆 Cole sua chave gratuita para ver **jogos reais das próximas 48h**.")

st.sidebar.markdown("---")

# ---- ABA PRÓXIMOS JOGOS (48H) ----
if api_key:
    st.sidebar.markdown("## 📅 Próximos Jogos (48h)")
    if st.sidebar.button("🔄 Atualizar Jogos", use_container_width=True):
        with st.spinner("Buscando partidas..."):
            upcoming = get_upcoming_matches(api_key)
            if upcoming:
                st.session_state["upcoming_matches"] = upcoming
                st.sidebar.success(f"{len(upcoming)} jogos encontrados!")
            else:
                st.sidebar.warning("Nenhum jogo nas próximas 48h ou erro na API.")
else:
    st.sidebar.info("ℹ️ Insira a chave para carregar jogos reais.")

# Exibir próximos jogos na área principal (se existirem)
if "upcoming_matches" in st.session_state and st.session_state["upcoming_matches"]:
    st.markdown("## 📅 Próximos Jogos (Próximas 48 horas)")
    cols = st.columns(1)
    for match in st.session_state["upcoming_matches"]:
        st.markdown(f"""
        <div class="match-row">
            <span class="match-time">🕒 {match['formatted_time']}</span>
            <span class="match-teams">{match['home']} vs {match['away']}</span>
            <span class="match-league">{match['competition']}</span>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("---")

# ---- ABA PREVISOR ----
st.markdown("## 🔮 Prever Confronto Específico")

# Seletor de competição (para previsão)
competicao_selecionada = st.selectbox(
    "Escolha a competição:",
    list(TEAMS.keys())
)

times = list(TEAMS[competicao_selecionada].keys())
col1, col2 = st.columns(2)
with col1:
    time_casa = st.selectbox("🏠 Time da Casa", times, index=0)
with col2:
    time_visitante = st.selectbox("✈️ Time Visitante", times, index=1 if len(times)>1 else 0)

if st.button("🔮 Calcular Probabilidades", use_container_width=True):
    if time_casa == time_visitante:
        st.warning("Escolha times diferentes.")
    else:
        with st.spinner("Analisando..."):
            probs = predict_match(time_casa, time_visitante, competicao_selecionada)

        # Cartão do confronto
        st.markdown(f"""
        <div class="card">
            <div style="display: flex; align-items: center; justify-content: center; gap: 2rem;">
                <span style="font-size:1.6rem; font-weight:700; color:#1e293b;">{time_casa}</span>
                <span style="font-size:1.6rem; color:#64748b;">vs</span>
                <span style="font-size:1.6rem; font-weight:700; color:#1e293b;">{time_visitante}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Barras
        def prob_bar(label, prob, cor):
            st.markdown(f"""
            <div class="prob-item">
                <span class="team-name">{label}</span>
                <div class="prob-bar">
                    <div class="bar-fill" style="width: {prob}%; background: {cor};"></div>
                </div>
                <span class="percentage">{prob}%</span>
            </div>
            """, unsafe_allow_html=True)

        prob_bar("Vitória da Casa", probs["home_win"], "#22c55e")
        prob_bar("Empate", probs["draw"], "#eab308")
        prob_bar("Vitória do Visitante", probs["away_win"], "#3b82f6")

        maior = max(probs, key=probs.get)
        if maior == "home_win":
            st.success(f"✅ Favorito: **{time_casa}** (mandante)")
        elif maior == "away_win":
            st.info(f"✅ Favorito: **{time_visitante}** (visitante)")
        else:
            st.warning("⚖️ Confronto equilibrado, tendência a empate.")

# Explicação do modelo
with st.expander("ℹ️ Como funciona a previsão?"):
    st.markdown("""
    - **Ratings:** Cada time possui uma pontuação baseada em desempenho histórico (1500–1900).
    - **Vantagem de casa:** +65 pontos.
    - **Gols esperados:** Calculados via fator de força (escala logarítmica).
    - **Distribuição de Poisson:** Converte expectativa de gols em probabilidades de placares.
    - **Resultado:** Soma das probabilidades de vitória, empate e derrota.
    
    ⚠️ Dados de ratings são ilustrativos. Para uso profissional, alimente com estatísticas reais.
    """)

st.markdown("---")
st.caption("⚽ Previsor de Futebol • Próximos jogos via Football-Data.org • Ratings simulados")