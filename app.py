import streamlit as st

# ---------------------- CONFIGURAÇÃO DA PÁGINA ----------------------
st.set_page_config(
    page_title="Análise de Futebol",
    page_icon="⚽",
    layout="centered",
    initial_sidebar_state="expanded"
)

# ---------------------- ESTILO PERSONALIZADO ----------------------
st.markdown("""
    <style>
    .titulo {
        font-size: 2.2rem;
        color: #2c3e50;
        text-align: center;
        margin-bottom: 2rem;
    }
    .card {
        padding: 1.5rem;
        border-radius: 10px;
        background-color: #f8f9fa;
        margin: 1rem 0;
        border-left: 5px solid #27ae60;
    }
    </style>
""", unsafe_allow_html=True)

# ---------------------- CABEÇALHO ----------------------
st.markdown('<h1 class="titulo">⚽ Painel de Análise de Futebol</h1>', unsafe_allow_html=True)

# ---------------------- DADOS DE EXEMPLO (substitua pela sua lógica) ----------------------
placar = "2 x 1"
time_casa = "Flamengo"
time_visitante = "Vasco"
gols_casa = 2
gols_visitante = 1
estatisticas = {
    "Posse de Bola": "58% x 42%",
    "Chutes a Gol": "7 x 3",
    "Escanteios": "6 x 2"
}

# ---------------------- EXIBIÇÃO DOS DADOS (f-strings CORRETAS) ----------------------
try:
    # Seção de Resultado
    st.markdown(f"""
    <div class="card">
        <h3>Resultado da Partida</h3>
        <p><strong>{time_casa}</strong> {gols_casa} x {gols_visitante} <strong>{time_visitante}</strong></p>
        <p>Placar final: {placar}</p>
    </div>
    """, unsafe_allow_html=True)

    # Seção de Estatísticas
    st.subheader("📊 Estatísticas do Jogo")
    for item, valor in estatisticas.items():
        st.markdown(f"- **{item}**: {valor}")

    # Exemplo de formatação segura
    vencedor = time_casa if gols_casa > gols_visitante else time_visitante if gols_visitante > gols_casa else "Empate"
    st.success(f"🏆 Resultado final: {vencedor}")

except SyntaxError as e:
    st.error(f"Erro de sintaxe no código: {str(e)}")
except Exception as e:
    st.error(f"Ocorreu um erro inesperado: {str(e)}")

# ---------------------- RODAPÉ ----------------------
st.markdown("---")
st.caption("Desenvolvido com Streamlit | Dados de exemplo")
