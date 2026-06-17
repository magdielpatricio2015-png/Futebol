import streamlit as st
import requests
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import random

# ---------------------- CONFIG ----------------------
st.set_page_config(page_title="Previsor de Futebol", page_icon="⚽", layout="wide")

st.markdown("""
<style>
.titulo {font-size: 2.8rem; text-align: center; font-weight: 800; margin: 1rem 0;}
.card {background: var(--background-color); border-radius: 20px; padding: 2rem; margin: 1rem 0; box-shadow: 0 10px 25px rgba(0,0,0,0.08);}
.prob-item {background: var(--secondary-background-color); border-radius: 12px; padding: 1.2rem; margin: 0.8rem 0; display: flex; align-items: center;}
.match-row {padding: 1.2rem; border-radius: 12px; background: var(--background-color); margin: 0.6rem 0; box-shadow: 0 2px 8px rgba(0,0,0,0.05);}
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="titulo">⚽ Previsor de Futebol com API Real</h1>', unsafe_allow_html=True)

# ---------------------- API-FOOTBALL ----------------------
API_BASE = "https://v3.football.api-sports.io"

@st.cache_data(ttl=1800)  # 30 minutos
def api_football_request(endpoint: str, params: dict = None, api_key: str = None) -> dict:
    if not api_key:
        return {"error": "API Key não informada"}
    headers = {
        "x-apisports-key": api_key
    }
    try:
        response = requests.get(f"{API_BASE}{endpoint}", headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Status {response.status_code}: {response.text[:200]}"}
    except Exception as e:
        return {"error": str(e)}

# ---------------------- RATINGS (mantido como fallback) ----------------------
TEAMS = { ... }  # Mantenha seu dicionário de ratings aqui (pode deixar o mesmo de antes)

def predict_match(...):  # Mantenha sua função de previsão (Monte Carlo)

# ---------------------- SIDEBAR ----------------------
st.sidebar.markdown("## 🔑 API Key")
api_key = st.sidebar.text_input(
    "API-Football Key (gratuita)",
    type="password",
    help="Cadastre-se grátis em https://www.api-football.com"
)

st.sidebar.markdown("---")
st.sidebar.info("100 requests/dia no plano gratuito")

# ---------------------- TABS ----------------------
tab1, tab2 = st.tabs(["📅 Próximos Jogos (API Real)", "🔮 Previsor"])

with tab1:
    st.markdown("## 📅 Próximos Jogos")
    
    if not api_key:
        st.warning("Insira sua API Key acima para carregar jogos reais.")
    else:
        if st.button("🔄 Buscar Jogos das Próximas 48h", type="primary"):
            with st.spinner("Buscando na API-Football..."):
                # Busca fixtures dos próximos dias
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                tomorrow = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d")
                
                params = {
                    "date": today,           # pode ajustar para from/to se preferir
                    "timezone": "America/Sao_Paulo"
                }
                
                data = api_football_request("/fixtures", params, api_key)
                
                if "error" in data:
                    st.error(data["error"])
                else:
                    matches = data.get("response", [])[:25]
                    if matches:
                        st.success(f"{len(matches)} jogos encontrados!")
                        for m in matches:
                            fixture = m["fixture"]
                            teams = m["teams"]
                            local_time = datetime.fromisoformat(fixture["date"].replace("Z", "+00:00")).astimezone()
                            
                            st.markdown(f"""
                            <div class="match-row">
                                <strong>{local_time.strftime("%d/%m %H:%M")}</strong> — 
                                {fixture.get('venue', {}).get('name', '—')}<br>
                                <b>{teams['home']['name']}</b> vs <b>{teams['away']['name']}</b>
                                <span style="color:#3b82f6"> • {m['league']['name']}</span>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.info("Nenhum jogo encontrado no período.")

with tab2:
    st.markdown("## 🔮 Previsor de Confronto")
    # (Mantenha a parte de previsão com ratings + possibilidade futura de puxar stats reais da API)

# ... resto do código (explicação, etc.)

st.caption("Integração com API-Football • Previsões baseadas em ratings + Monte Carlo")