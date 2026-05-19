"""
Analisador Esportivo Pro 18 – Versão Final com Download e Aprendizado
====================================================
Melhorias:
- APRENDIZADO ATIVO: Regressão Logística integrada.
- DOWNLOAD DE DADOS: Botão para baixar o histórico em CSV.
- DOWNLOAD DO SCRIPT: Opção para baixar o código fonte atualizado.
"""

from __future__ import annotations

import math
import os
import re
import sqlite3
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional, Tuple

import pandas as pd
import streamlit as st

try:
    import requests
    REQUESTS_OK = True
except Exception:
    REQUESTS_OK = False

try:
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    SKLEARN_OK = True
except Exception:
    SKLEARN_OK = False


# ======================= CONFIGURAÇÃO =======================
st.set_page_config(
    page_title="Pro 18 - Analisador Esportivo",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "Analisador Esportivo Pro 18 - v1.0"}
)

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
HEADERS = {"User-Agent": "AnalisadorEsportivoPro/18.0"}
DB_PATH = "data/modelo_v18.db"

MAX_GOLS = 10
RETRIES = 3
MIN_JOGOS_TREINO = 10
DIXON_COLES_RHO = -0.13

HOME_ADV_LIGA = {
    "bra.1": 0.28, "bra.2": 0.27, "bra.copa_do_brazil": 0.22,
    "eng.1": 0.22, "esp.1": 0.24, "ita.1": 0.25, "ger.1": 0.26,
    "fra.1": 0.24, "uefa.champions": 0.20, "uefa.europa": 0.18,
    "conmebol.libertadores": 0.30, "conmebol.sudamericana": 0.28,
}

LIGAS = {
    "Brasileirão Série A": "bra.1",
    "Brasileirão Série B": "bra.2",
    "Copa do Brasil": "bra.copa_do_brazil",
    "Premier League": "eng.1",
    "La Liga": "esp.1",
    "Série A Itália": "ita.1",
    "Bundesliga": "ger.1",
    "Ligue 1": "fra.1",
    "Champions League": "uefa.champions",
    "Europa League": "uefa.europa",
    "Libertadores": "conmebol.libertadores",
    "Sul-Americana": "conmebol.sudamericana",
}

FORCA_BASE = {
    "flamengo": 86, "palmeiras": 84, "botafogo": 79, "atletico-mg": 76,
    "sao paulo": 78, "fluminense": 77, "gremio": 74, "internacional": 75,
    "corinthians": 76, "cruzeiro": 73, "bahia": 74, "fortaleza": 73,
    "vasco": 70, "santos": 72, "ceara": 69, "sport": 68, "vitoria": 69,
    "coritiba": 68, "athletico-pr": 72, "atletico goianiense": 68,
    "goias": 68, "cuiaba": 67, "juventude": 67, "chapecoense": 65,
    "crb": 65, "csa": 64, "paysandu": 64, "remo": 64,
    "ponte preta": 65, "guarani": 64, "novorizontino": 67,
    "mirassol": 68, "operario pr": 64, "vila nova": 66,
    "amazonas": 64, "america mineiro": 68, "bragantino": 72,
    "red bull bragantino": 72, "sao bernardo": 63, "tombense": 62,
    "volta redonda": 62, "santa cruz": 61, "retro": 61,
    "manchester city": 91, "arsenal": 88, "liverpool": 88,
    "chelsea": 82, "tottenham hotspur": 80, "manchester united": 81,
    "real madrid": 90, "barcelona": 87, "atletico madrid": 84,
    "bayern munich": 88, "borussia dortmund": 82, "bayer leverkusen": 84,
    "inter milan": 86, "juventus": 82, "milan": 81,
    "paris saint-germain": 88,
}

ALIASES = {
    "man city": "manchester city", "man utd": "manchester united",
    "man united": "manchester united", "tottenham": "tottenham hotspur",
    "spurs": "tottenham hotspur", "psg": "paris saint-germain",
    "paris sg": "paris saint-germain", "inter": "inter milan",
    "internazionale": "inter milan", "atletico mineiro": "atletico-mg",
    "atletico mg": "atletico-mg", "vasco da gama": "vasco",
    "sao paulo fc": "sao paulo", "gremio fbpa": "gremio",
    "athletico paranaense": "athletico-pr", "atletico pr": "athletico-pr",
    "red bull bragantino": "bragantino", "operario": "operario pr",
    "operario-pr": "operario pr",
}

# ======================= ESTILO MODERNO =======================
def aplicar_estilo() -> None:
    st.markdown("""<style>
    html, body, [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
        color: #0f172a;
    }
    .block-container { padding: 2rem 1.5rem 5rem 1.5rem; max-width: 1400px; }
    h1 { font-size: 2.2rem !important; font-weight: 800 !important; background: linear-gradient(135deg, #6366f1, #ec4899); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; margin-bottom: 0.5rem !important; }
    h2 { color: #4f46e5 !important; font-weight: 700 !important; border-bottom: 2px solid #e2e8f0; padding-bottom: 0.8rem !important; margin-top: 1.5rem !important; }
    .card-modern { background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.2rem; margin: 0.8rem 0; box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08); transition: all 0.3s ease; }
    .card-modern:hover { border-color: #6366f1; box-shadow: 0 8px 20px rgba(99, 102, 241, 0.12); }
    .chip { display: inline-block; border-radius: 20px; padding: 0.4rem 0.9rem; margin: 0.3rem 0.4rem 0.3rem 0; font-size: 0.8rem; font-weight: 600; border: 1px solid #e2e8f0; }
    .chip-green { background: #dcfce7; color: #166534; border-color: #86efac; }
    .chip-blue { background: #dbeafe; color: #1e40af; border-color: #7dd3fc; }
    .chip-gray { background: #f1f5f9; color: #475569; border-color: #cbd5e1; }
    button { border-radius: 8px !important; font-weight: 600 !important; border: none !important; color: white !important; }
    button:hover { background: linear-gradient(135deg, #6366f1, #ec4899) !important; }
    </style>""", unsafe_allow_html=True)


# ======================= BANCO DE DADOS =======================
def conectar_db() -> sqlite3.Connection:
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db() -> None:
    conn = conectar_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS previsoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT UNIQUE,
            esporte TEXT, liga_id TEXT, liga_nome TEXT, data_jogo TEXT,
            home TEXT, away TEXT, forca_home REAL, forca_away REAL,
            home_adv REAL, contexto TEXT,
            mercado_base TEXT, codigo_base TEXT, prob_base REAL,
            mercado_aprendido TEXT, codigo_aprendido TEXT, prob_aprendido REAL,
            ajuste_aplicado REAL, placar_previsto TEXT,
            escanteios_previstos TEXT, cartoes_previstos TEXT,
            home_score INTEGER, away_score INTEGER,
            acertou_base INTEGER, acertou_aprendido INTEGER,
            finalizado INTEGER DEFAULT 0, criado_em TEXT, data_utc TEXT
        )
    """)
    
    colunas_necessarias = [
        ("previsoes", "escanteios_previstos", "TEXT"),
        ("previsoes", "cartoes_previstos", "TEXT"),
        ("previsoes", "data_utc", "TEXT"),
        ("previsoes", "forca_home", "REAL"),
        ("previsoes", "forca_away", "REAL"),
    ]
    for tabela, coluna, tipo in colunas_necessarias:
        cur.execute(f"PRAGMA table_info({tabela})")
        if coluna not in {row[1] for row in cur.fetchall()}:
            cur.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
            
    conn.commit()
    conn.close()

def ler_tabela(sql: str, params=()) -> pd.DataFrame:
    conn = conectar_db()
    try: return pd.read_sql_query(sql, conn, params=params)
    except: return pd.DataFrame()
    finally: conn.close()

def executar(sql: str, params=()) -> None:
    conn = conectar_db()
    try: conn.execute(sql, params); conn.commit()
    finally: conn.close()


# ======================= UTILITÁRIOS =======================
def normalizar(nome: str) -> str:
    nome = str(nome or "").strip().lower()
    nome = unicodedata.normalize("NFD", nome)
    nome = "".join(c for c in nome if unicodedata.category(c) != "Mn")
    nome = nome.replace("'", "").replace(".", "").replace(",", "")
    nome = re.sub(r"\b(fc|sc)\b$", "", nome).strip()
    return ALIASES.get(nome, nome)

def pct(valor: float) -> str:
    return f"{valor * 100:.1f}%"

def traduzir_mercado(mercado: str) -> str:
    traducoes = {
        "casa_ou_empate": "Casa ou Empate",
        "empate_ou_fora": "Empate ou Fora",
        "casa_vence": "Casa vence",
        "fora_vence": "Fora vence",
        "empate": "Empate",
        "over_1.5": "Over 1.5 Gols",
        "over_2.5": "Over 2.5 Gols",
        "ambos_marcam": "Ambos marcam"
    }
    m_lower = str(mercado).lower()
    return traducoes.get(m_lower, mercado)

def parse_data_espn(valor: Any) -> Optional[datetime]:
    if not valor: return None
    try:
        dt = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except: return None


# ======================= CHAMADAS À API =======================
@st.cache_data(ttl=60*30, show_spinner=False)
def api_get_json(url: str, params=None) -> Optional[dict]:
    if not REQUESTS_OK: return None
    for t in range(RETRIES):
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=12)
            if resp.status_code == 200: return resp.json()
        except: pass
        time.sleep(0.5)
    return None

@st.cache_data(ttl=60*10, show_spinner=False)
def buscar_jogos_rodada(liga_id: str) -> pd.DataFrame:
    url = f"{ESPN_BASE}/{liga_id}/scoreboard"
    data = api_get_json(url, {"limit": 100})
    rows = []
    if not data: return pd.DataFrame(rows)
    for event in data.get("events", []):
        dt = parse_data_espn(event.get("date"))
        if not dt: continue
        comp = (event.get("competitions") or [{}])[0]
        home = away = h_score = a_score = None
        for team in comp.get("competitors", []):
            name = team.get("team", {}).get("displayName")
            score = team.get("score")
            if team.get("homeAway") == "home": home, h_score = name, score
            else: away, a_score = name, score
        status = event.get("status", {}).get("type", {})
        rows.append({
            "game_id": str(event.get("id")),
            "data_utc": dt.isoformat(),
            "data_local": dt.astimezone().strftime("%d/%m %H:%M"),
            "home": str(home), "away": str(away),
            "home_score": int(h_score) if str(h_score).isdigit() else None,
            "away_score": int(a_score) if str(a_score).isdigit() else None,
            "completed": bool(status.get("completed")),
            "status_text": status.get("shortDetail", "")
        })
    return pd.DataFrame(rows).sort_values("data_utc").reset_index(drop=True)


# ======================= APRENDIZADO DE MÁQUINA =======================
def treinar_modelo_ml():
    if not SKLEARN_OK: return None, None
    df = ler_tabela("""
        SELECT forca_home, forca_away, home_score, away_score 
        FROM previsoes 
        WHERE finalizado = 1 AND home_score IS NOT NULL AND away_score IS NOT NULL
    """)
    if len(df) < MIN_JOGOS_TREINO: return None, None
    X = df[['forca_home', 'forca_away']].values
    y = (df['home_score'] >= df['away_score']).astype(int).values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    model = LogisticRegression()
    model.fit(X_scaled, y)
    return model, scaler

def poisson(k: int, lamb: float) -> float:
    lamb = max(lamb, 0.05)
    return math.exp(-lamb) * (lamb**k) / math.factorial(k)

def analisar_jogo(home, away, liga_id, model=None, scaler=None):
    nh = normalizar(home); na = normalizar(away)
    fh = FORCA_BASE.get(nh, 72.0); fa = FORCA_BASE.get(na, 70.0)
    adv = HOME_ADV_LIGA.get(liga_id, 0.25)
    diff = (fh + adv * 10) - fa
    lh = max(1.28 + diff / 34, 0.2); la = max(1.08 - diff / 40, 0.2)
    prob_h = sum(poisson(h, lh) * poisson(a, la) for h in range(6) for a in range(6) if h > a)
    prob_d = sum(poisson(h, lh) * poisson(a, la) for h in range(6) for a in range(6) if h == a)
    prob_a = sum(poisson(h, lh) * poisson(a, la) for h in range(6) for a in range(6) if h < a)
    total = prob_h + prob_d + prob_a
    prob_h, prob_d, prob_a = prob_h/total, prob_d/total, prob_a/total
    ajuste_ml = 0.0
    if model and scaler:
        features = np.array([[fh, fa]])
        features_scaled = scaler.transform(features)
        prob_ml = model.predict_proba(features_scaled)[0][1]
        prob_base_he = prob_h + prob_d
        prob_final_he = (prob_base_he * 0.6) + (prob_ml * 0.4)
        ajuste_ml = prob_final_he - prob_base_he
        if prob_final_he > 0.5: res, cod, p = "casa_ou_empate", "casa_ou_empate", prob_final_he
        else: res, cod, p = "empate_ou_fora", "empate_ou_fora", (1 - prob_final_he)
    else:
        if prob_h > prob_a: res, cod, p = "casa_ou_empate", "casa_ou_empate", (prob_h + prob_d)
        else: res, cod, p = "empate_ou_fora", "empate_ou_fora", (prob_a + prob_d)
    base_esc = 9.5; base_cart = 4.2
    if "bra" in liga_id: base_cart += 1.2; base_esc += 0.5
    esc = f"{base_esc + (fh + fa - 140) / 20:.1f}"
    cart = f"{base_cart + (160 - fh - fa) / 30:.1f}"
    return res, cod, p, f"{int(lh)} x {int(la)}", esc, cart, fh, fa, ajuste_ml


# ======================= PERSISTÊNCIA =======================
def salvar_previsao(game_id, esporte, liga_id, liga_nome, data_jogo, home, away,
                    mercado, codigo, prob, placar, esc, cart, data_utc, fh, fa, ajuste, finalizado=0):
    agora = datetime.now().isoformat(timespec="seconds")
    executar("""
        INSERT OR REPLACE INTO previsoes (
            game_id, esporte, liga_id, liga_nome, data_jogo, home, away,
            mercado_aprendido, codigo_aprendido, prob_aprendido,
            placar_previsto, escanteios_previstos, cartoes_previstos,
            forca_home, forca_away, ajuste_aplicado,
            criado_em, data_utc, finalizado
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (str(game_id), str(esporte), str(liga_id), str(liga_nome), str(data_jogo),
          str(home), str(away), str(mercado), str(codigo), float(prob),
          str(placar), str(esc), str(cart), float(fh), float(fa), float(ajuste),
          agora, str(data_utc), int(finalizado)))

def atualizar_resultados_finalizados():
    pendentes = ler_tabela("SELECT game_id, liga_id FROM previsoes WHERE finalizado = 0")
    for _, row in pendentes.iterrows():
        url = f"{ESPN_BASE}/{row['liga_id']}/scoreboard"
        data = api_get_json(url, {"limit": 100})
        if not data: continue
        for event in data.get("events", []):
            if str(event.get("id")) == str(row["game_id"]):
                status = event.get("status", {}).get("type", {})
                if status.get("completed"):
                    comp = (event.get("competitions") or [{}])[0]
                    h_score = a_score = 0
                    for team in comp.get("competitors", []):
                        score = team.get("score")
                        if team.get("homeAway") == "home": h_score = int(score)
                        else: a_score = int(score)
                    executar("UPDATE previsoes SET finalizado = 1, home_score = ?, away_score = ? WHERE game_id = ?", 
                             (h_score, a_score, row["game_id"]))


# ======================= TELAS =======================
def tela_futebol():
    st.header("⚽ FUTEBOL COM APRENDIZADO")
    with st.spinner("Carregando inteligência..."):
        model, scaler = treinar_modelo_ml()
        if model: st.success("🤖 Modelo de Aprendizado Ativo!")
        else: st.info(f"📈 Sistema em fase de coleta ({MIN_JOGOS_TREINO} jogos necessários).")
    liga_nome = st.selectbox("Escolha a Liga", list(LIGAS.keys()))
    liga_id = LIGAS[liga_nome]
    if st.button("🔃 Atualizar Rodada e Resultados"):
        atualizar_resultados_finalizados()
        st.cache_data.clear()
        st.rerun()
    df_rodada = buscar_jogos_rodada(liga_id)
    if df_rodada.empty:
        st.warning("Nenhum jogo encontrado.")
        return
    st.markdown(f"### 📅 Jogos da Rodada ({len(df_rodada)})")
    for _, jogo in df_rodada.iterrows():
        game_id = str(jogo["game_id"])
        db_prev = ler_tabela("SELECT * FROM previsoes WHERE game_id = ?", (game_id,))
        if db_prev.empty:
            merc, cod, p, placar, esc, cart, fh, fa, ajuste = analisar_jogo(jogo["home"], jogo["away"], liga_id, model, scaler)
            salvar_previsao(game_id, "futebol", liga_id, liga_nome, jogo["data_utc"][:10], jogo["home"], jogo["away"],
                            merc, cod, p, placar, esc, cart, jogo["data_utc"], fh, fa, ajuste, 1 if jogo["completed"] else 0)
            db_prev = ler_tabela("SELECT * FROM previsoes WHERE game_id = ?", (game_id,))
        prev = db_prev.iloc[0]
        with st.container():
            col1, col2, col3 = st.columns([2, 2, 1.5])
            with col1:
                st.markdown(f"**{jogo['data_local']}**<br>**{jogo['home']}** vs **{jogo['away']}**", unsafe_allow_html=True)
                if jogo["completed"]: st.markdown(f"<span class='chip chip-gray'>Fim: {jogo['home_score']} x {jogo['away_score']}</span>", unsafe_allow_html=True)
                else: st.markdown(f"<span class='chip chip-blue'>{jogo['status_text']}</span>", unsafe_allow_html=True)
            with col2:
                mercado_claro = traduzir_mercado(prev['mercado_aprendido'])
                st.markdown(f"<span style='color: #4f46e5; font-weight: 700; font-size: 1.1rem;'>{mercado_claro}</span>", unsafe_allow_html=True)
                st.markdown(f"🎯 Placar: **{prev['placar_previsto']}**")
                st.markdown(f"🚩 Escanteios: **{prev['escanteios_previstos']}** | 🟨 Cartões: **{prev['cartoes_previstos']}**")
            with col3:
                st.markdown(f"<span style='color: #059669; font-weight: 800; font-size: 1.4rem;'>{pct(prev['prob_aprendido'])}</span>", unsafe_allow_html=True)
                if prev['ajuste_aplicado'] != 0:
                    cor = "blue" if prev['ajuste_aplicado'] > 0 else "red"
                    st.caption(f"Ajuste ML: :{cor}[{prev['ajuste_aplicado']*100:+.1f}%]")
                else: st.caption("Confiança (Base)")
            st.divider()

def main():
    aplicar_estilo()
    init_db()
    st.sidebar.markdown("<h1 style='text-align: center; color: #6366f1;'>⚽ PRO 18</h1>", unsafe_allow_html=True)
    pg = st.sidebar.radio("Navegação", ["⚽ Futebol", "📋 Histórico", "💾 Download"])
    if pg == "⚽ Futebol": tela_futebol()
    elif pg == "📋 Histórico":
        st.header("📋 HISTÓRICO DE APRENDIZADO")
        df_hist = ler_tabela("SELECT * FROM previsoes ORDER BY id DESC LIMIT 100")
        if not df_hist.empty:
            st.dataframe(df_hist)
            jogos_total = len(df_hist[df_hist['finalizado'] == 1])
            st.metric("Jogos no Histórico", jogos_total)
        else: st.info("O histórico aparecerá aqui conforme você visualizar os jogos.")
    else:
        st.header("💾 ÁREA DE DOWNLOAD")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📊 Dados do Modelo")
            df_full = ler_tabela("SELECT * FROM previsoes")
            if not df_full.empty:
                csv = df_full.to_csv(index=False).encode('utf-8')
                st.download_button("Baixar Histórico (CSV)", csv, "historico_analisador.csv", "text/csv")
            else: st.warning("Sem dados para baixar.")
        with col2:
            st.subheader("💻 Código Fonte")
            try:
                with open(__file__, "r", encoding="utf-8") as f:
                    code = f.read()
                st.download_button("Baixar app.py (Código)", code, "app.py", "text/plain")
            except: st.error("Não foi possível ler o arquivo do código.")

if __name__ == "__main__":
    main()
