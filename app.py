

Compartilhar

Iniciar teste gratuito
Lite
Aqui está o código absolutamente limpo.
O erro anterior aconteceu porque você copiou o texto "Código · 6.24 KB" que aparece no topo da visualização do arquivo. Esse texto não faz parte do código Python e causa o erro de sintaxe.
Instruções para funcionar agora:
Não copie o texto do chat. Em vez disso, baixe o arquivo app_final.py que anexei aqui.
Renomeie ele para app.py (se desejar).
Suba esse arquivo diretamente para o seu servidor Streamlit.
Este arquivo contém apenas o código necessário, sem nenhum caractere extra ou metadado. Ele foi validado e está pronto para rodar. Se precisar de qualquer outra coisa, estou à disposição!
app_final.py
Código · 5.57 KB
Ver todos os arquivos nesta tarefa
Como foi este resultado?
File "/mount/src/futebol/app.py", line 7
  Peço desculpas pelo erro! A imagem mostra um SyntaxError causado por um caractere invisível ou inválido (um ponto médio ·) que provavelmente apareceu durante a cópia do código.
                                                                                                                          ^
SyntaxError: invalid character '·' (U+00B7)
Lite
Você está copiando as minhas mensagens de texto para dentro do arquivo app.py. O Python está tentando ler as minhas explicações em português como se fossem código, e por isso dá erro.
O arquivo app.py deve conter APENAS o código.
Vou te enviar agora o código puro dentro de um bloco de código. Copie APENAS o que está dentro do bloco abaixo, ou melhor ainda, baixe o arquivo que anexei na mensagem anterior.
Python
import math
import pandas as pd
import requests
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta
from scipy.stats import poisson

# Configuração da Página
st.set_page_config(
    page_title="Analisador Esportivo Pro 8.0",
    page_icon="💰",
    layout="wide",
)

# --- ESTILIZAÇÃO ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #3e4150; }
    .value-bet { color: #00ff00; font-weight: bold; }
    .no-value { color: #ff4b4b; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE CÁLCULO ---

def calcular_poisson(media_home, media_away):
    prob_home = 0
    prob_draw = 0
    prob_away = 0
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
    stake_sugerida = max(0, f_kelly * fracao)
    return stake_sugerida * banca

# --- INTERFACE ---

st.title("🏟️ Analisador Esportivo Pro 8.0")
st.subheader("Futebol & Tênis - Inteligência para Apostas de Valor")

menu = st.sidebar.selectbox("Selecione o Esporte", ["Futebol", "Tênis", "Gestão de Banca"])

if menu == "Futebol":
    st.header("⚽ Análise de Futebol (Modelo Poisson)")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Dados do Confronto")
        time_h = st.text_input("Time da Casa", "Flamengo")
        time_a = st.text_input("Time Visitante", "Palmeiras")
        media_gols_h = st.number_input(f"Média de Gols Marcados ({time_h})", min_value=0.0, value=1.8, step=0.1)
        media_gols_a = st.number_input(f"Média de Gols Marcados ({time_a})", min_value=0.0, value=1.2, step=0.1)
    with col2:
        st.subheader("Odds do Mercado")
        odd_h = st.number_input(f"Odd {time_h}", min_value=1.01, value=2.10)
        odd_d = st.number_input("Odd Empate", min_value=1.01, value=3.40)
        odd_a = st.number_input(f"Odd {time_a}", min_value=1.01, value=3.80)
    if st.button("Analisar Partida"):
        p_h, p_d, p_a, matrix = calcular_poisson(media_gols_h, media_gols_a)
        fair_h = 1/p_h if p_h > 0 else 0
        fair_d = 1/p_d if p_d > 0 else 0
        fair_a = 1/p_a if p_a > 0 else 0
        st.divider()
        res_cols = st.columns(3)
        def display_value(label, prob, fair, market):
            ev = (prob * market) - 1
            color = "value-bet" if ev > 0 else "no-value"
            st.markdown(f"### {label}")
            st.write(f"Probabilidade: **{prob:.1%}**")
            st.write(f"Odd Justa: **{fair:.2f}**")
            st.write(f"Odd Mercado: **{market:.2f}**")
            st.markdown(f"Valor Esperado (EV): <span class='{color}'>{ev:+.2%}</span>", unsafe_allow_html=True)
        with res_cols[0]: display_value(time_h, p_h, fair_h, odd_h)
        with res_cols[1]: display_value("Empate", p_d, fair_d, odd_d)
        with res_cols[2]: display_value(time_a, p_a, fair_a, odd_a)
        st.subheader("📊 Matriz de Probabilidades (Placar Exato)")
        fig = go.Figure(data=go.Heatmap(z=matrix, x=[str(i) for i in range(7)], y=[str(i) for i in range(7)], colorscale='Viridis'))
        fig.update_layout(xaxis_title=f"Gols {time_a}", yaxis_title=f"Gols {time_h}")
        st.plotly_chart(fig, use_container_width=True)

elif menu == "Tênis":
    st.header("🎾 Análise de Tênis (Performance & Superfície)")
    col1, col2 = st.columns(2)
    with col1:
        jogador1 = st.text_input("Jogador 1", "Novak Djokovic")
        win_rate1 = st.slider(f"Win Rate Recente ({jogador1}) %", 0, 100, 85)
        h2h1 = st.number_input(f"Vitórias H2H ({jogador1})", 0, 20, 5)
    with col2:
        jogador2 = st.text_input("Jogador 2", "Carlos Alcaraz")
        win_rate2 = st.slider(f"Win Rate Recente ({jogador2}) %", 0, 100, 75)
        h2h2 = st.number_input(f"Vitórias H2H ({jogador2})", 0, 20, 3)
    total_points = win_rate1 + win_rate2 + (h2h1 * 5) + (h2h2 * 5)
    if total_points > 0:
        p1 = (win_rate1 + (h2h1 * 5)) / total_points
        p2 = (win_rate2 + (h2h2 * 5)) / total_points
    else:
        p1, p2 = 0.5, 0.5
    st.divider()
    st.subheader("Projeção de Vencedor")
    t_col1, t_col2 = st.columns(2)
    t_col1.metric(jogador1, f"{p1:.1%}", f"Odd Justa: {1/p1 if p1 > 0 else 0:.2f}")
    t_col2.metric(jogador2, f"{p2:.1%}", f"Odd Justa: {1/p2 if p2 > 0 else 0:.2f}")

elif menu == "Gestão de Banca":
    st.header("💰 Calculadora de Gestão de Banca")
    banca_total = st.number_input("Valor Total da Banca (R$)", min_value=0.0, value=1000.0)
    odd_selecionada = st.number_input("Odd da Aposta", min_value=1.01, value=2.0)
    prob_estimada = st.slider("Sua Probabilidade Estimada (%)", 1, 100, 55) / 100
    stake = criterio_kelly(prob_estimada, odd_selecionada, banca_total)
    st.divider()
    if stake > 0:
        st.success(f"### Sugestão de Entrada: R$ {stake:.2f}")
        st.write(f"Isso representa **{(stake/banca_total):.1%}** da sua banca.")
    else:
        st.error("### Sem Valor: Não aposte nesta seleção.")

st.sidebar.divider()
st.sidebar.info("Dica de Monetização: Use este app para criar um grupo de Tips VIP. A análise baseada em Poisson e Kelly diferencia você de amadores.")
Atenção: Apague tudo o que estiver no seu arquivo app.py atual e cole apenas o código acima. Se você copiar as minhas frases de desculpas ou explicações, o erro continuará.
ME D EO APP.PY COMPLETO 
Lite
Aqui está o código COMPLETO e LIMPO do seu app.py.
IMPORTANTE: Apague tudo o que você tem no seu arquivo atual e cole APENAS o que está no bloco abaixo. Não inclua nenhuma frase minha dentro do arquivo.
Python
import math
import pandas as pd
import requests
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta
from scipy.stats import poisson

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(
    page_title="Analisador Esportivo Pro 8.0",
    page_icon="💰",
    layout="wide",
)

# 2. ESTILIZAÇÃO CUSTOMIZADA
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #3e4150; }
    .value-bet { color: #00ff00; font-weight: bold; }
    .no-value { color: #ff4b4b; }
    </style>
    """, unsafe_allow_html=True)

# 3. FUNÇÕES MATEMÁTICAS
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

# 4. INTERFACE PRINCIPAL
st.title("🏟️ Analisador Esportivo Pro 8.0")
st.subheader("Futebol & Tênis - Inteligência para Apostas de Valor")

menu = st.sidebar.selectbox("Selecione o Esporte", ["Futebol", "Tênis", "Gestão de Banca"])

if menu == "Futebol":
    st.header("⚽ Análise de Futebol (Modelo Poisson)")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Dados do Confronto")
        time_h = st.text_input("Time da Casa", "Flamengo")
        time_a = st.text_input("Time Visitante", "Palmeiras")
        media_gols_h = st.number_input(f"Média de Gols Marcados ({time_h})", min_value=0.0, value=1.8, step=0.1)
        media_gols_a = st.number_input(f"Média de Gols Marcados ({time_a})", min_value=0.0, value=1.2, step=0.1)
    with col2:
        st.subheader("Odds do Mercado")
        odd_h = st.number_input(f"Odd {time_h}", min_value=1.01, value=2.10)
        odd_d = st.number_input("Odd Empate", min_value=1.01, value=3.40)
        odd_a = st.number_input(f"Odd {time_a}", min_value=1.01, value=3.80)
    
    if st.button("Analisar Partida"):
        p_h, p_d, p_a, matrix = calcular_poisson(media_gols_h, media_gols_a)
        fair_h, fair_d, fair_a = 1/p_h if p_h>0 else 0, 1/p_d if p_d>0 else 0, 1/p_a if p_a>0 else 0
        st.divider()
        res_cols = st.columns(3)
        def display_value(label, prob, fair, market):
            ev = (prob * market) - 1
            color = "value-bet" if ev > 0 else "no-value"
            st.markdown(f"### {label}")
            st.write(f"Probabilidade: **{prob:.1%}**")
            st.write(f"Odd Justa: **{fair:.2f}**")
            st.write(f"Odd Mercado: **{market:.2f}**")
            st.markdown(f"Valor Esperado (EV): <span class='{color}'>{ev:+.2%}</span>", unsafe_allow_html=True)
        with res_cols[0]: display_value(time_h, p_h, fair_h, odd_h)
        with res_cols[1]: display_value("Empate", p_d, fair_d, odd_d)
        with res_cols[2]: display_value(time_a, p_a, fair_a, odd_a)
        st.subheader("📊 Matriz de Probabilidades (Placar Exato)")
        fig = go.Figure(data=go.Heatmap(z=matrix, x=[str(i) for i in range(7)], y=[str(i) for i in range(7)], colorscale='Viridis'))
        fig.update_layout(xaxis_title=f"Gols {time_a}", yaxis_title=f"Gols {time_h}")
        st.plotly_chart(fig, use_container_width=True)

elif menu == "Tênis":
    st.header("🎾 Análise de Tênis (Performance & Superfície)")
    col1, col2 = st.columns(2)
    with col1:
        jogador1 = st.text_input("Jogador 1", "Novak Djokovic")
        win_rate1 = st.slider(f"Win Rate Recente ({jogador1}) %", 0, 100, 85)
        h2h1 = st.number_input(f"Vitórias H2H ({jogador1})", 0, 20, 5)
    with col2:
        jogador2 = st.text_input("Jogador 2", "Carlos Alcaraz")
        win_rate2 = st.slider(f"Win Rate Recente ({jogador2}) %", 0, 100, 75)
        h2h2 = st.number_input(f"Vitórias H2H ({jogador2})", 0, 20, 3)
    total_points = win_rate1 + win_rate2 + (h2h1 * 5) + (h2h2 * 5)
    p1, p2 = ((win_rate1 + (h2h1 * 5)) / total_points, (win_rate2 + (h2h2 * 5)) / total_points) if total_points > 0 else (0.5, 0.5)
    st.divider()
    st.subheader("Projeção de Vencedor")
    t_col1, t_col2 = st.columns(2)
    t_col1.metric(jogador1, f"{p1:.1%}", f"Odd Justa: {1/p1 if p1 > 0 else 0:.2f}")
    t_col2.metric(jogador2, f"{p2:.1%}", f"Odd Justa: {1/p2 if p2 > 0 else 0:.2f}")

elif menu == "Gestão de Banca":
    st.header("💰 Calculadora de Gestão de Banca")
    banca_total = st.number_input("Valor Total da Banca (R$)", min_value=0.0, value=1000.0)
    odd_selecionada = st.number_input("Odd da Aposta", min_value=1.01, value=2.0)
    prob_estimada = st.slider("Sua Probabilidade Estimada (%)", 1, 100, 55) / 100
    stake = criterio_kelly(prob_estimada, odd_selecionada, banca_total)
    st.divider()
    if stake > 0:
        st.success(f"### Sugestão de Entrada: R$ {stake:.2f}")
        st.write(f"Isso representa **{(stake/banca_total):.1%}** da sua banca.")
    else:
        st.error("### Sem Valor: Não aposte nesta seleção.")

st.sidebar.divider()
st.sidebar.info("Dica de Monetização: Use este app para criar um grupo de Tips VIP. A análise baseada em Poisson e Kelly diferencia você de amadores.")
Dica: Baixe o arquivo app_final.py anexo para garantir que nenhum erro de cópia aconteça. Se precisar de mais alguma coisa, estou aqui!
app_final.py
Código · 5.57 KB
Ver todos os arquivos nesta tarefa
Como foi este resultado?
File "/mount/src/futebol/app.py", line 23
  Código · 5.57 KB
         ^
SyntaxError: invalid character '·' (U+00B7)
Lite
PARE! VOCÊ ESTÁ COPIANDO O TEXTO ERRADO.
O erro SyntaxError: invalid character '·' acontece porque você está copiando o título da janela ("Código · 5.57 KB") para dentro do seu arquivo. Esse texto NÃO é código Python.
🛑 O QUE NÃO FAZER:
Não copie o cabeçalho cinza que aparece no topo do arquivo.
✅ O QUE FAZER (Siga exatamente estes passos):
BAIXE O ARQUIVO: Clique no botão de download (ícone de seta para baixo) no arquivo app_final.py que está anexado a esta mensagem.
NÃO COPIE E COLE: Use o arquivo baixado diretamente.
SE FOR COPIAR: Copie APENAS o texto que começa com import math e termina com amadores.").
Aqui está o código novamente. COMECE A COPIAR DA LINHA 1 ABAIXO:
Python
import math
import pandas as pd
import requests
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta
from scipy.stats import poisson

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(
    page_title="Analisador Esportivo Pro 8.0",
    page_icon="💰",
    layout="wide",
)

# 2. ESTILIZAÇÃO CUSTOMIZADA
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #3e4150; }
    .value-bet { color: #00ff00; font-weight: bold; }
    .no-value { color: #ff4b4b; }
    </style>
    """, unsafe_allow_html=True)

# 3. FUNÇÕES MATEMÁTICAS
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

# 4. INTERFACE PRINCIPAL
st.title("🏟️ Analisador Esportivo Pro 8.0")
st.subheader("Futebol & Tênis - Inteligência para Apostas de Valor")

menu = st.sidebar.selectbox("Selecione o Esporte", ["Futebol", "Tênis", "Gestão de Banca"])

if menu == "Futebol":
    st.header("⚽ Análise de Futebol (Modelo Poisson)")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Dados do Confronto")
        time_h = st.text_input("Time da Casa", "Flamengo")
        time_a = st.text_input("Time Visitante", "Palmeiras")
        media_gols_h = st.number_input(f"Média de Gols Marcados ({time_h})", min_value=0.0, value=1.8, step=0.1)
        media_gols_a = st.number_input(f"Média de Gols Marcados ({time_a})", min_value=0.0, value=1.2, step=0.1)
    with col2:
        st.subheader("Odds do Mercado")
        odd_h = st.number_input(f"Odd {time_h}", min_value=1.01, value=2.10)
        odd_d = st.number_input("Odd Empate", min_value=1.01, value=3.40)
        odd_a = st.number_input(f"Odd {time_a}", min_value=1.01, value=3.80)
    
    if st.button("Analisar Partida"):
        p_h, p_d, p_a, matrix = calcular_poisson(media_gols_h, media_gols_a)
        fair_h, fair_d, fair_a = 1/p_h if p_h>0 else 0, 1/p_d if p_d>0 else 0, 1/p_a if p_a>0 else 0
        st.divider()
        res_cols = st.columns(3)
        def display_value(label, prob, fair, market):
            ev = (prob * market) - 1
            color = "value-bet" if ev > 0 else "no-value"
            st.markdown(f"### {label}")
            st.write(f"Probabilidade: **{prob:.1%}**")
            st.write(f"Odd Justa: **{fair:.2f}**")
            st.write(f"Odd Mercado: **{market:.2f}**")
            st.markdown(f"Valor Esperado (EV): <span class='{color}'>{ev:+.2%}</span>", unsafe_allow_html=True)
        with res_cols[0]: display_value(time_h, p_h, fair_h, odd_h)
        with res_cols[1]: display_value("Empate", p_d, fair_d, odd_d)
        with res_cols[2]: display_value(time_a, p_a, fair_a, odd_a)
        st.subheader("📊 Matriz de Probabilidades (Placar Exato)")
        fig = go.Figure(data=go.Heatmap(z=matrix, x=[str(i) for i in range(7)], y=[str(i) for i in range(7)], colorscale='Viridis'))
        fig.update_layout(xaxis_title=f"Gols {time_a}", yaxis_title=f"Gols {time_h}")
        st.plotly_chart(fig, use_container_width=True)

elif menu == "Tênis":
    st.header("🎾 Análise de Tênis (Performance & Superfície)")
    col1, col2 = st.columns(2)
    with col1:
        jogador1 = st.text_input("Jogador 1", "Novak Djokovic")
        win_rate1 = st.slider(f"Win Rate Recente ({jogador1}) %", 0, 100, 85)
        h2h1 = st.number_input(f"Vitórias H2H ({jogador1})", 0, 20, 5)
    with col2:
        jogador2 = st.text_input("Jogador 2", "Carlos Alcaraz")
        win_rate2 = st.slider(f"Win Rate Recente ({jogador2}) %", 0, 100, 75)
        h2h2 = st.number_input(f"Vitórias H2H ({jogador2})", 0, 20, 3)
    total_points = win_rate1 + win_rate2 + (h2h1 * 5) + (h2h2 * 5)
    p1, p2 = ((win_rate1 + (h2h1 * 5)) / total_points, (win_rate2 + (h2h2 * 5)) / total_points) if total_points > 0 else (0.5, 0.5)
    st.divider()
    st.subheader("Projeção de Vencedor")
    t_col1, t_col2 = st.columns(2)
    t_col1.metric(jogador1, f"{p1:.1%}", f"Odd Justa: {1/p1 if p1 > 0 else 0:.2f}")
    t_col2.metric(jogador2, f"{p2:.1%}", f"Odd Justa: {1/p2 if p2 > 0 else 0:.2f}")

elif menu == "Gestão de Banca":
    st.header("💰 Calculadora de Gestão de Banca")
    banca_total = st.number_input("Valor Total da Banca (R$)", min_value=0.0, value=1000.0)
    odd_selecionada = st.number_input("Odd da Aposta", min_value=1.01, value=2.0)
    prob_estimada = st.slider("Sua Probabilidade Estimada (%)", 1, 100, 55) / 100
    stake = criterio_kelly(prob_estimada, odd_selecionada, banca_total)
    st.divider()
    if stake > 0:
        st.success(f"### Sugestão de Entrada: R$ {stake:.2f}")
        st.write(f"Isso representa **{(stake/banca_total):.1%}** da sua banca.")
    else:
        st.error("### Sem Valor: Não aposte nesta seleção.")

st.sidebar.divider()
st.sidebar.info("Dica de Monetização: Use este app para criar um grupo de Tips VIP. A análise baseada em Poisson e Kelly diferencia você de amadores.")
app_final.py
Código · 5.57 KB
Ver todos os arquivos nesta tarefa
Tarefa concluída
Como foi este resultado?
Sugestões de acompanhamento




app_final.py
import math
import pandas as pd
import requests
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta
from scipy.stats import poisson

# Configuração da Página
st.set_page_config(
    page_title="Analisador Esportivo Pro 8.0",
    page_icon="💰",
    layout="wide",
)

# --- ESTILIZAÇÃO ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #3e4150; }
    .value-bet { color: #00ff00; font-weight: bold; }
    .no-value { color: #ff4b4b; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE CÁLCULO ---

def calcular_poisson(media_home, media_away):
    prob_home = 0
    prob_draw = 0
    prob_away = 0
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
    stake_sugerida = max(0, f_kelly * fracao)
    return stake_sugerida * banca

# --- INTERFACE ---

st.title("🏟️ Analisador Esportivo Pro 8.0")
st.subheader("Futebol & Tênis - Inteligência para Apostas de Valor")

menu = st.sidebar.selectbox("Selecione o Esporte", ["Futebol", "Tênis", "Gestão de Banca"])

if menu == "Futebol":
    st.header("⚽ Análise de Futebol (Modelo Poisson)")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Dados do Confronto")
        time_h = st.text_input("Time da Casa", "Flamengo")
        time_a = st.text_input("Time Visitante", "Palmeiras")
        media_gols_h = st.number_input(f"Média de Gols Marcados ({time_h})", min_value=0.0, value=1.8, step=0.1)
        media_gols_a = st.number_input(f"Média de Gols Marcados ({time_a})", min_value=0.0, value=1.2, step=0.1)
    with col2:
        st.subheader("Odds do Mercado")
        odd_h = st.number_input(f"Odd {time_h}", min_value=1.01, value=2.10)
        odd_d = st.number_input("Odd Empate", min_value=1.01, value=3.40)
        odd_a = st.number_input(f"Odd {time_a}", min_value=1.01, value=3.80)
    if st.button("Analisar Partida"):
        p_h, p_d, p_a, matrix = calcular_poisson(media_gols_h, media_gols_a)
        fair_h = 1/p_h if p_h > 0 else 0
        fair_d = 1/p_d if p_d > 0 else 0
        fair_a = 1/p_a if p_a > 0 else 0
        st.divider()
        res_cols = st.columns(3)
        def display_value(label, prob, fair, market):
            ev = (prob * market) - 1
            color = "value-bet" if ev > 0 else "no-value"
            st.markdown(f"### {label}")
            st.write(f"Probabilidade: **{prob:.1%}**")
            st.write(f"Odd Justa: **{fair:.2f}**")
            st.write(f"Odd Mercado: **{market:.2f}**")
            st.markdown(f"Valor Esperado (EV): <span class='{color}'>{ev:+.2%}</span>", unsafe_allow_html=True)
        with res_cols[0]: display_value(time_h, p_h, fair_h, odd_h)
        with res_cols[1]: display_value("Empate", p_d, fair_d, odd_d)
        with res_cols[2]: display_value(time_a, p_a, fair_a, odd_a)
        st.subheader("📊 Matriz de Probabilidades (Placar Exato)")
        fig = go.Figure(data=go.Heatmap(z=matrix, x=[str(i) for i in range(7)], y=[str(i) for i in range(7)], colorscale='Viridis'))
        fig.update_layout(xaxis_title=f"Gols {time_a}", yaxis_title=f"Gols {time_h}")
        st.plotly_chart(fig, use_container_width=True)

elif menu == "Tênis":
    st.header("🎾 Análise de Tênis (Performance & Superfície)")
    col1, col2 = st.columns(2)
    with col1:
        jogador1 = st.text_input("Jogador 1", "Novak Djokovic")
        win_rate1 = st.slider(f"Win Rate Recente ({jogador1}) %", 0, 100, 85)
        h2h1 = st.number_input(f"Vitórias H2H ({jogador1})", 0, 20, 5)
    with col2:
        jogador2 = st.text_input("Jogador 2", "Carlos Alcaraz")
        win_rate2 = st.slider(f"Win Rate Recente ({jogador2}) %", 0, 100, 75)
        h2h2 = st.number_input(f"Vitórias H2H ({jogador2})", 0, 20, 3)
    total_points = win_rate1 + win_rate2 + (h2h1 * 5) + (h2h2 * 5)
    if total_points > 0:
        p1 = (win_rate1 + (h2h1 * 5)) / total_points
        p2 = (win_rate2 + (h2h2 * 5)) / total_points
    else:
        p1, p2 = 0.5, 0.5
    st.divider()
    st.subheader("Projeção de Vencedor")
    t_col1, t_col2 = st.columns(2)
    t_col1.metric(jogador1, f"{p1:.1%}", f"Odd Justa: {1/p1 if p1 > 0 else 0:.2f}")
    t_col2.metric(jogador2, f"{p2:.1%}", f"Odd Justa: {1/p2 if p2 > 0 else 0:.2f}")

elif menu == "Gestão de Banca":
    st.header("💰 Calculadora de Gestão de Banca")
    banca_total = st.number_input("Valor Total da Banca (R$)", min_value=0.0, value=1000.0)
    odd_selecionada = st.number_input("Odd da Aposta", min_value=1.01, value=2.0)
    prob_estimada = st.slider("Sua Probabilidade Estimada (%)", 1, 100, 55) / 100
    stake = criterio_kelly(prob_estimada, odd_selecionada, banca_total)
    st.divider()
    if stake > 0:
        st.success(f"### Sugestão de Entrada: R$ {stake:.2f}")
        st.write(f"Isso representa **{(stake/banca_total):.1%}** da sua banca.")
    else:
        st.error("### Sem Valor: Não aposte nesta seleção.")

st.sidebar.divider()
st.sidebar.info("Dica de Monetização: Use este app para criar um grupo de Tips VIP. A análise baseada em Poisson e Kelly diferencia você de amadores.")
Melhore App.py para Análise Esportiva e Ganhar Dinheiro - Manus
