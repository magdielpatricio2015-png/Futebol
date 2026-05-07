import math
import pandas as pd
import requests
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta
from scipy.stats import poisson

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Analisador Esportivo Pro 10.0", page_icon="🏟️", layout="wide")

# --- CONSTANTES ---
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
LIGAS = {
    "Brasileirão Série A": "bra.1",
    "Brasileirão Série B": "bra.2",
    "Copa do Brasil": "bra.copa_do_brasil",
    "La Liga (Espanha)": "esp.1",
    "Premier League (Inglaterra)": "eng.1",
    "Serie A (Itália)": "ita.1",
    "Bundesliga (Alemanha)": "ger.1",
    "Ligue 1 (França)": "fra.1",
    "Champions League": "uefa.champions",
    "Europa League": "uefa.europa",
    "Libertadores": "conmebol.libertadores",
    "Sul-Americana": "conmebol.sudamericana"
}

# --- ESTILIZAÇÃO (TEMA BRANCO) ---
st.markdown("""
    <style>
    .main { background-color: #ffffff; color: #000000; }
    .stMetric { background-color: #f0f2f6; padding: 15px; border-radius: 10px; border: 1px solid #d0d2d6; }
    .green { color: #28a745; font-weight: bold; }
    .red { color: #dc3545; font-weight: bold; }
    .live-badge { background-color: #ff4b4b; color: white; padding: 2px 8px; border-radius: 5px; font-size: 12px; font-weight: bold; }
    h1, h2, h3, p { color: #1e1e1e !important; }
    .stButton>button { background-color: #007bff; color: white; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- INICIALIZAÇÃO DE ESTADO ---
if 'historico' not in st.session_state:
    st.session_state.historico = []

# --- FUNÇÕES DE DADOS ---
def buscar_jogos(liga_id, apenas_ao_vivo=False):
    try:
        url = f"{ESPN_BASE}/{liga_id}/scoreboard"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        jogos = []
        for event in data.get('events', []):
            status = event['status']['type']['description']
            is_live = event['status']['type']['state'] == 'in'
            if apenas_ao_vivo and not is_live: continue
            comp = event['competitions'][0]
            jogos.append({
                "id": event['id'],
                "nome": event['name'],
                "home": comp['competitors'][0]['team']['displayName'],
                "away": comp['competitors'][1]['team']['displayName'],
                "placar": f"{comp['competitors'][0]['score']} - {comp['competitors'][1]['score']}",
                "status": status,
                "live": is_live
            })
        return jogos
    except: return []

# --- FUNÇÕES MATEMÁTICAS ---
def calcular_poisson(media_home, media_away):
    p_h, p_d, p_a = 0, 0, 0
    matrix = []
    for i in range(7):
        row = []
        for j in range(7):
            p = poisson.pmf(i, media_home) * poisson.pmf(j, media_away)
            row.append(p)
            if i > j: p_h += p
            elif i == j: p_d += p
            else: p_a += p
        matrix.append(row)
    return p_h, p_d, p_a, matrix

# --- INTERFACE ---
st.title("🏟️ Analisador Esportivo Pro 10.0")

menu = st.sidebar.radio("Navegação", ["Jogos ao Vivo 🔴", "Análise por Liga", "Performance (Green/Red)", "Gestão de Banca"])

if menu == "Jogos ao Vivo 🔴":
    st.header("🎮 Partidas em Tempo Real")
    todos_ao_vivo = []
    for nome, liga_id in LIGAS.items():
        jogos = buscar_jogos(liga_id, apenas_ao_vivo=True)
        for j in jogos:
            j['liga'] = nome
            todos_ao_vivo.append(j)
    if not todos_ao_vivo:
        st.info("Nenhum jogo ao vivo no momento nas ligas principais.")
    else:
        for j in todos_ao_vivo:
            with st.expander(f"LIVE: {j['nome']} ({j['liga']}) - {j['placar']}"):
                st.write(f"Status: {j['status']}")
                st.button("Analisar este jogo", key=j['id'])

elif menu == "Análise por Liga":
    liga_sel = st.selectbox("Selecione a Liga", list(LIGAS.keys()))
    jogos = buscar_jogos(LIGAS[liga_sel])
    if not jogos:
        st.warning("Nenhum jogo encontrado para esta liga hoje.")
    else:
        jogo_nome = st.selectbox("Selecione o Jogo", [f"{j['nome']} ({j['status']})" for j in jogos])
        jogo_data = next(j for j in jogos if f"{j['nome']} ({j['status']})" == jogo_nome)
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("📊 Médias de Gols")
            m_h = st.number_input(f"Média {jogo_data['home']}", 0.0, 5.0, 1.5)
            m_a = st.number_input(f"Média {jogo_data['away']}", 0.0, 5.0, 1.2)
        with c2:
            st.subheader("💰 Odds")
            o_h = st.number_input(f"Odd {jogo_data['home']}", 1.01, 50.0, 2.0)
            o_d = st.number_input("Odd Empate", 1.01, 50.0, 3.2)
            o_a = st.number_input(f"Odd {jogo_data['away']}", 1.01, 50.0, 3.5)
        if st.button("Calcular Valor"):
            p_h, p_d, p_a, matrix = calcular_poisson(m_h, m_a)
            res_cols = st.columns(3)
            def show_res(label, prob, market):
                ev = (prob * market) - 1
                color = "green" if ev > 0 else "red"
                st.markdown(f"**{label}**")
                st.write(f"Prob: {prob:.1%}")
                st.markdown(f"EV: <span class='{color}'>{ev:+.2%}</span>", unsafe_allow_html=True)
                if st.button(f"Registrar {label}", key=f"reg_{label}_{jogo_data['id']}"):
                    st.session_state.historico.append({"jogo": jogo_data['nome'], "aposta": label, "ev": ev, "data": datetime.now()})
                    st.success("Registrado!")
            with res_cols[0]: show_res(jogo_data['home'], p_h, o_h)
            with res_cols[1]: show_res("Empate", p_d, o_d)
            with res_cols[2]: show_res(jogo_data['away'], p_a, o_a)

elif menu == "Performance (Green/Red)":
    st.header("📈 Histórico de Análises (Últimas 24h)")
    if not st.session_state.historico:
        st.info("Nenhuma aposta registrada ainda.")
    else:
        df = pd.DataFrame(st.session_state.historico)
        limite = datetime.now() - timedelta(hours=24)
        df = df[df['data'] > limite]
        st.table(df[['data', 'jogo', 'aposta', 'ev']])
        greens = len(df[df['ev'] > 0])
        reds = len(df[df['ev'] <= 0])
        st.metric("Análises EV+", greens)
        st.metric("Análises EV-", reds)

elif menu == "Gestão de Banca":
    st.header("💰 Calculadora de Stake")
    banca = st.number_input("Banca Total (R$)", value=1000.0)
    odd = st.number_input("Odd", value=2.0)
    prob = st.slider("Sua Probabilidade (%)", 1, 100, 55) / 100
    q = 1 - prob
    b = odd - 1
    f_kelly = (b * prob - q) / b if b > 0 else 0
    stake = max(0, f_kelly * 0.25) * banca
    st.success(f"### Sugestão: R$ {stake:.2f}")

st.sidebar.divider()
st.sidebar.write("Versão 10.0 - Tema Claro")
