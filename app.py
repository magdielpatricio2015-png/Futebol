import math
import pandas as pd
import requests
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime
from scipy.stats import poisson

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Analisador Esportivo Pro 9.0", page_icon="🏟️", layout="wide")

# --- CONSTANTES ---
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
COMPETICOES = {
    "Brasileirão Série A": "bra.1",
    "Premier League": "eng.1",
    "La Liga": "esp.1",
    "Serie A Itália": "ita.1",
    "Bundesliga": "ger.1",
    "Champions League": "uefa.champions",
    "Libertadores": "conmebol.libertadores"
}

# --- ESTILIZAÇÃO ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #3e4150; }
    .value-bet { color: #00ff00; font-weight: bold; }
    .no-value { color: #ff4b4b; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE DADOS ---
def buscar_jogos_espn(liga_id):
    try:
        url = f"{ESPN_BASE}/{liga_id}/scoreboard"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        jogos = []
        for event in data.get('events', []):
            competitor_h = event['competitions'][0]['competitors'][0]
            competitor_a = event['competitions'][0]['competitors'][1]
            jogos.append({
                "id": event['id'],
                "nome": event['name'],
                "home": competitor_h['team']['displayName'],
                "away": competitor_a['team']['displayName'],
                "data": event['date']
            })
        return jogos
    except:
        return []

# --- FUNÇÕES MATEMÁTICAS ---
def calcular_poisson(media_home, media_away):
    prob_home, prob_draw, prob_away = 0, 0, 0
    matrix = []
    for i in range(7):
        row = []
        for j in range(7):
            p = poisson.pmf(i, media_home) * poisson.pmf(j, media_away)
            row.append(p)
            if i > j: prob_home += p
            elif i == j: prob_draw += p
            else: prob_away += p
        matrix.append(row)
    return prob_home, prob_draw, prob_away, matrix

def criterio_kelly(prob_estimada, odd_casa, banca, fracao=0.25):
    if odd_casa <= 1: return 0
    q = 1 - prob_estimada
    b = odd_casa - 1
    f_kelly = (b * prob_estimada - q) / b
    return max(0, f_kelly * fracao) * banca

# --- INTERFACE ---
st.title("🏟️ Analisador Esportivo Pro 9.0")
st.subheader("Dados Reais ESPN + Inteligência de Apostas")

menu = st.sidebar.selectbox("Selecione o Esporte", ["Futebol (Jogos Reais)", "Tênis", "Gestão de Banca"])

if menu == "Futebol (Jogos Reais)":
    liga_nome = st.selectbox("Selecione a Competição", list(COMPETICOES.keys()))
    liga_id = COMPETICOES[liga_nome]
    
    with st.spinner(f"Buscando jogos de {liga_nome}..."):
        jogos = buscar_jogos_espn(liga_id)
    
    if not jogos:
        st.warning("Nenhum jogo encontrado para esta liga no momento.")
    else:
        jogo_selecionado = st.selectbox("Selecione a Partida", [j['nome'] for j in jogos])
        dados_jogo = next(j for j in jogos if j['nome'] == jogo_selecionado)
        
        st.divider()
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Estimativa de Gols")
            m_h = st.number_input(f"Média de Gols: {dados_jogo['home']}", 0.0, 5.0, 1.5)
            m_a = st.number_input(f"Média de Gols: {dados_jogo['away']}", 0.0, 5.0, 1.2)
            
        with col2:
            st.subheader("💰 Odds do Mercado")
            o_h = st.number_input(f"Odd {dados_jogo['home']}", 1.01, 50.0, 2.0)
            o_d = st.number_input("Odd Empate", 1.01, 50.0, 3.2)
            o_a = st.number_input(f"Odd {dados_jogo['away']}", 1.01, 50.0, 3.5)
            
        if st.button("Analisar Valor"):
            p_h, p_d, p_a, matrix = calcular_poisson(m_h, m_a)
            fair_h, fair_d, fair_a = 1/p_h if p_h>0 else 0, 1/p_d if p_d>0 else 0, 1/p_a if p_a>0 else 0
            
            res_cols = st.columns(3)
            def display_value(label, prob, fair, market):
                ev = (prob * market) - 1
                color = "value-bet" if ev > 0 else "no-value"
                st.markdown(f"### {label}")
                st.write(f"Probabilidade: **{prob:.1%}**")
                st.write(f"Odd Justa: **{fair:.2f}**")
                st.markdown(f"Valor Esperado (EV): <span class='{color}'>{ev:+.2%}</span>", unsafe_allow_html=True)
            
            with res_cols[0]: display_value(dados_jogo['home'], p_h, fair_h, o_h)
            with res_cols[1]: display_value("Empate", p_d, fair_d, o_d)
            with res_cols[2]: display_value(dados_jogo['away'], p_a, fair_a, o_a)
            
            st.subheader("📊 Matriz de Placar Exato")
            fig = go.Figure(data=go.Heatmap(z=matrix, x=[str(i) for i in range(7)], y=[str(i) for i in range(7)], colorscale='Viridis'))
            fig.update_layout(xaxis_title=f"Gols {dados_jogo['away']}", yaxis_title=f"Gols {dados_jogo['home']}")
            st.plotly_chart(fig, use_container_width=True)

elif menu == "Tênis":
    st.header("🎾 Análise de Tênis")
    j1 = st.text_input("Jogador 1", "Novak Djokovic")
    j2 = st.text_input("Jogador 2", "Carlos Alcaraz")
    wr1 = st.slider(f"Win Rate {j1} (%)", 0, 100, 80)
    wr2 = st.slider(f"Win Rate {j2} (%)", 0, 100, 75)
    total = wr1 + wr2
    p1, p2 = (wr1/total, wr2/total) if total > 0 else (0.5, 0.5)
    st.metric(j1, f"{p1:.1%}", f"Odd Justa: {1/p1:.2f}")
    st.metric(j2, f"{p2:.1%}", f"Odd Justa: {1/p2:.2f}")

elif menu == "Gestão de Banca":
    st.header("💰 Gestão de Banca")
    banca = st.number_input("Banca Total (R$)", value=1000.0)
    odd = st.number_input("Odd da Aposta", value=2.0)
    prob = st.slider("Sua Probabilidade (%)", 1, 100, 55) / 100
    stake = criterio_kelly(prob, odd, banca)
    st.success(f"Sugestão de Entrada: R$ {stake:.2f}")

st.sidebar.info("Este app une dados reais da ESPN com modelos de Poisson para encontrar apostas de valor.")
