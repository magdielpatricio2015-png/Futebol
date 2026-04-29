
  import streamlit as st
import urllib.request
import urllib.error
import urllib.parse
import json
import math
import hashlib
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

# ============================================================
# CONFIGURAÇÕES BÁSICAS
# ============================================================

st.set_page_config(
    page_title="Analisador de Futebol",
    page_icon="⚽",
    layout="centered",
    initial_sidebar_state="collapsed",
)

APP_TITLE = "⚽ Analisador de Futebol Online"
USUARIO = "admin"
SENHA = "12354"
TZ_BR = ZoneInfo("America/Sao_Paulo")


# ============================================================
# ESTILO VISUAL — MELHOR PARA CELULAR
# ============================================================

st.markdown(
    """
    <style>
        .main .block-container {
            padding-top: 1rem;
            padding-left: 0.8rem;
            padding-right: 0.8rem;
            max-width: 980px;
        }

        div[data-testid="stMetricValue"] {
            font-size: 1.35rem;
        }

        .card {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 16px;
            padding: 14px;
            margin-bottom: 12px;
            box-shadow: 0 2px 10px rgba(15, 23, 42, 0.06);
        }

        .card-title {
            font-size: 1.05rem;
            font-weight: 800;
            color: #0f172a;
            margin-bottom: 4px;
        }

        .muted {
            color: #64748b;
            font-size: 0.88rem;
        }

        .pill {
            display: inline-block;
            padding: 3px 9px;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 700;
            margin-right: 4px;
            background: #e0f2fe;
            color: #075985;
        }

        .live {
            background: #dcfce7;
            color: #166534;
        }

        .danger {
            background: #fee2e2;
            color: #991b1b;
        }

        .warn {
            background: #fef3c7;
            color: #92400e;
        }

        .big-number {
            font-size: 1.8rem;
            font-weight: 900;
            color: #111827;
        }

        .small-label {
            font-size: 0.78rem;
            color: #64748b;
            font-weight: 600;
        }

        @media (max-width: 640px) {
            .main .block-container {
                padding-left: 0.55rem;
                padding-right: 0.55rem;
            }

            .card {
                padding: 12px;
                border-radius: 14px;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# LOGIN
# ============================================================

def check_login():
    if "logado" not in st.session_state:
        st.session_state.logado = False

    if st.session_state.logado:
        return

    st.title("🔐 Login")
    st.info("Digite seu usuário e senha para acessar o app.")

    user = st.text_input("Usuário", value="", placeholder="admin")
    password = st.text_input("Senha", value="", type="password", placeholder="12354")

    entrar = st.button("Entrar", use_container_width=True)

    if entrar:
        user_ok = user.strip() == USUARIO
        pass_ok = password.strip() == SENHA

        if user_ok and pass_ok:
            st.session_state.logado = True
            st.success("Login realizado com sucesso.")
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos. Use: admin / 12354")

    st.stop()


check_login()


# ============================================================
# COMPETIÇÕES
# ============================================================

COMPETICOES = {
    "Brasileirão Série A 2026": {
        "key": "serie_a_2026",
        "espn": "bra.1",
        "tipo": "liga",
    },
    "Brasileirão Série B 2026": {
        "key": "serie_b_2026",
        "espn": "bra.2",
        "tipo": "liga",
    },
    "Copa do Brasil 2026": {
        "key": "copa_do_brasil_2026",
        "espn": "bra.copa_do_brasil",
        "tipo": "copa",
    },
    "Libertadores 2026": {
        "key": "libertadores_2026",
        "espn": "conmebol.libertadores",
        "tipo": "copa",
    },
    "Premier League 2025/26": {
        "key": "premier_league_2026",
        "espn": "eng.1",
        "tipo": "liga",
    },
}

FORCA_TIMES = {
    # Brasil
    "Flamengo": 86,
    "Palmeiras": 85,
    "Atlético-MG": 80,
    "Atletico Mineiro": 80,
    "Botafogo": 80,
    "São Paulo": 78,
    "Sao Paulo": 78,
    "Fluminense": 78,
    "Grêmio": 77,
    "Gremio": 77,
    "Internacional": 77,
    "Corinthians": 76,
    "Cruzeiro": 75,
    "Bahia": 74,
    "Athletico-PR": 74,
    "Athletico": 74,
    "Vasco": 72,
    "Vasco da Gama": 72,
    "Santos": 72,
    "Fortaleza": 72,
    "Ceará": 70,
    "Ceara": 70,
    "Vitória": 69,
    "Vitoria": 69,
    "Sport": 68,
    "Juventude": 67,
    "Mirassol": 67,
    "Bragantino": 72,
    "Red Bull Bragantino": 72,

    # Libertadores / estrangeiros comuns
    "River Plate": 84,
    "Boca Juniors": 82,
    "Racing Club": 78,
    "Independiente": 76,
    "Peñarol": 76,
    "Penarol": 76,
    "Nacional": 75,
    "Colo Colo": 75,
    "LDU": 76,
    "Barcelona SC": 74,
    "Olimpia": 74,
    "Cerro Porteño": 74,
    "Cerro Porteno": 74,

    # Inglaterra
    "Manchester City": 90,
    "Arsenal": 88,
    "Liverpool": 88,
    "Chelsea": 82,
    "Tottenham": 81,
    "Manchester United": 80,
    "Newcastle": 79,
    "Aston Villa": 79,
    "Brighton": 76,
    "West Ham": 75,
}


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def br_now():
    return datetime.now(TZ_BR)


def br_today():
    return br_now().date()


def fmt_data_iso(data_iso):
    try:
        return datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return data_iso or "Sem data"


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def normalizar_nome(nome):
    return " ".join(str(nome or "").strip().split())


def hash_forca_time(nome):
    """
    Gera uma força estável para times não cadastrados.
    Não é aleatório a cada execução.
    """
    nome = normalizar_nome(nome)
    if not nome:
        return 70

    if nome in FORCA_TIMES:
        return FORCA_TIMES[nome]

    # tenta por nome parcial
    for chave, valor in FORCA_TIMES.items():
        if chave.lower() in nome.lower() or nome.lower() in chave.lower():
            return valor

    h = hashlib.sha256(nome.encode("utf-8")).hexdigest()
    n = int(h[:8], 16)
    return 64 + (n % 15)


def poisson_pmf(k, lam):
    if lam <= 0:
        return 0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def calcular_probabilidades(casa, fora, campo_neutro=False):
    casa = normalizar_nome(casa)
    fora = normalizar_nome(fora)

    forca_casa = hash_forca_time(casa)
    forca_fora = hash_forca_time(fora)

    vantagem_casa = 0 if campo_neutro else 4

    rating_casa = forca_casa + vantagem_casa
    rating_fora = forca_fora

    diferenca = rating_casa - rating_fora

    gols_casa = max(0.45, 1.35 + diferenca * 0.025)
    gols_fora = max(0.35, 1.08 - diferenca * 0.020)

    max_gols = 7
    p_casa = 0.0
    p_empate = 0.0
    p_fora = 0.0
    over_15 = 0.0
    over_25 = 0.0
    ambas_marcam = 0.0

    for i in range(max_gols + 1):
        for j in range(max_gols + 1):
            p = poisson_pmf(i, gols_casa) * poisson_pmf(j, gols_fora)

            if i > j:
                p_casa += p
            elif i == j:
                p_empate += p
            else:
                p_fora += p

            if i + j >= 2:
                over_15 += p
            if i + j >= 3:
                over_25 += p
            if i > 0 and j > 0:
                ambas_marcam += p

    total_1x2 = p_casa + p_empate + p_fora
    if total_1x2 > 0:
        p_casa /= total_1x2
        p_empate /= total_1x2
        p_fora /= total_1x2

    intensidade = (forca_casa + forca_fora) / 2
    equilibrio = max(0, 100 - abs(forca_casa - forca_fora) * 3)

    escanteios_total = 8.5 + (intensidade - 70) * 0.10 + (equilibrio - 60) * 0.02
    escanteios_total = max(6.0, min(13.0, escanteios_total))

    cartoes_total = 4.0 + (equilibrio - 60) * 0.015
    cartoes_total = max(2.5, min(7.5, cartoes_total))

    prob_mais_8_escanteios = min(0.88, max(0.25, (escanteios_total - 6.5) / 7.0))
    prob_mais_9_escanteios = min(0.82, max(0.20, (escanteios_total - 7.2) / 7.0))
    prob_mais_3_cartoes = min(0.90, max(0.25, (cartoes_total - 2.2) / 4.8))
    prob_mais_4_cartoes = min(0.82, max(0.18, (cartoes_total - 3.0) / 4.8))

    return {
        "casa": casa,
        "fora": fora,
        "forca_casa": forca_casa,
        "forca_fora": forca_fora,
        "gols_casa": gols_casa,
        "gols_fora": gols_fora,
        "p_casa": p_casa,
        "p_empate": p_empate,
        "p_fora": p_fora,
        "over_15": over_15,
        "over_25": over_25,
        "ambas_marcam": ambas_marcam,
        "escanteios_total": escanteios_total,
        "cartoes_total": cartoes_total,
        "prob_mais_8_escanteios": prob_mais_8_escanteios,
        "prob_mais_9_escanteios": prob_mais_9_escanteios,
        "prob_mais_3_cartoes": prob_mais_3_cartoes,
        "prob_mais_4_cartoes": prob_mais_4_cartoes,
    }


def pct(valor):
    return f"{valor * 100:.1f}%"


def nivel_texto(prob):
    if prob >= 0.70:
        return "Alta"
    if prob >= 0.55:
        return "Boa"
    if prob >= 0.42:
        return "Média"
    return "Baixa"


def html_card_inicio():
    st.markdown('<div class="card">', unsafe_allow_html=True)


def html_card_fim():
    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# ESPN API
# ============================================================

def abrir_json(url, timeout=15):
    headers = {
        "User-Agent": "Mozilla/5.0 AnalisadorFutebolStreamlit/1.0",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    req = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")

    return json.loads(raw)


@st.cache_data(ttl=180, show_spinner=False)
def buscar_espn_scoreboard(slug, data_yyyymmdd):
    url = (
        f"https://site.api.espn.com/apis/site/v2/sports/soccer/"
        f"{slug}/scoreboard?dates={data_yyyymmdd}&limit=300&region=br&lang=pt"
    )

    try:
        data = abrir_json(url)
        return data, ""
    except urllib.error.HTTPError as e:
        return {}, f"Erro HTTP {e.code} ao buscar ESPN."
    except Exception as e:
        return {}, f"Falha ao buscar ESPN: {e}"


def extrair_jogos_espn(data):
    jogos = []

    eventos = data.get("events", []) if isinstance(data, dict) else []

    for ev in eventos:
        competicoes = ev.get("competitions") or []
        comp = competicoes[0] if competicoes else {}

        status = comp.get("status") or ev.get("status") or {}
        status_type = status.get("type") or {}
        status_state = status_type.get("state", "")
        status_name = status_type.get("description") or status_type.get("shortDetail") or ""
        status_detail = status_type.get("detail") or ev.get("status", {}).get("type", {}).get("detail", "")

        data_evento = ev.get("date", "")
        dt_br = None

        try:
            dt_utc = datetime.fromisoformat(data_evento.replace("Z", "+00:00"))
            dt_br = dt_utc.astimezone(TZ_BR)
        except Exception:
            dt_br = None

        casa = ""
        fora = ""
        placar_casa = None
        placar_fora = None

        for c in comp.get("competitors", []):
            team = c.get("team") or {}
            nome = (
                team.get("displayName")
                or team.get("shortDisplayName")
                or team.get("name")
                or "Time"
            )

            score = c.get("score")
            if score is not None:
                try:
                    score = int(score)
                except Exception:
                    pass

            if c.get("homeAway") == "home":
                casa = nome
                placar_casa = score
            elif c.get("homeAway") == "away":
                fora = nome
                placar_fora = score

        if not casa or not fora:
            continue

        jogos.append(
            {
                "id": ev.get("id", ""),
                "nome": ev.get("name", f"{casa} x {fora}"),
                "casa": casa,
                "fora": fora,
                "placar_casa": placar_casa,
                "placar_fora": placar_fora,
                "data": dt_br.strftime("%Y-%m-%d") if dt_br else "",
                "hora": dt_br.strftime("%H:%M") if dt_br else "",
                "status_state": status_state,
                "status_name": status_name,
                "status_detail": status_detail,
                "raw_status": status,
            }
        )

    jogos.sort(key=lambda x: (x.get("data", ""), x.get("hora", "")))
    return jogos


def buscar_jogos_periodo(slug, dias=14):
    todos = []
    logs = []

    hoje = br_today()

    for i in range(dias + 1):
        d = hoje + timedelta(days=i)
        data_key = d.strftime("%Y%m%d")
        data, erro = buscar_espn_scoreboard(slug, data_key)

        if erro:
            logs.append(f"{d.strftime('%d/%m')}: {erro}")
            continue

        jogos = extrair_jogos_espn(data)
        todos.extend(jogos)

    vistos = set()
    unicos = []

    for j in todos:
        chave = j.get("id") or f"{j['data']}-{j['hora']}-{j['casa']}-{j['fora']}"
        if chave in vistos:
            continue
        vistos.add(chave)
        unicos.append(j)

    unicos.sort(key=lambda x: (x.get("data", ""), x.get("hora", "")))
    return unicos, logs


def filtrar_ao_vivo(jogos):
    ao_vivo = []
    hoje = br_today().strftime("%Y-%m-%d")

    for j in jogos:
        state = str(j.get("status_state", "")).lower()
        detail = str(j.get("status_detail", "")).lower()
        name = str(j.get("status_name", "")).lower()

        if state == "in":
            ao_vivo.append(j)
        elif "tempo" in detail or "intervalo" in detail or "live" in detail:
            ao_vivo.append(j)
        elif j.get("data") == hoje and ("andamento" in name or "progress" in name):
            ao_vivo.append(j)

    return ao_vivo


# ============================================================
# COMPONENTES VISUAIS
# ============================================================

def mostrar_jogo_card(jogo, mostrar_analise=True):
    estado = str(jogo.get("status_state", "")).lower()
    ao_vivo = estado == "in"

    if ao_vivo:
        classe = "pill live"
        texto_status = "AO VIVO"
    elif estado == "post":
        classe = "pill danger"
        texto_status = "ENCERRADO"
    elif estado == "pre":
        classe = "pill"
        texto_status = "PRÓXIMO"
    else:
        classe = "pill warn"
        texto_status = jogo.get("status_name") or "STATUS"

    placar = ""
    if jogo.get("placar_casa") is not None and jogo.get("placar_fora") is not None:
        placar = f" — {jogo.get('placar_casa')} x {jogo.get('placar_fora')}"

    st.markdown(
        f"""
        <div class="card">
            <span class="{classe}">{texto_status}</span>
            <span class="muted">{fmt_data_iso(jogo.get("data"))} • {jogo.get("hora")}</span>
            <div class="card-title">{jogo.get("casa")} x {jogo.get("fora")}{placar}</div>
            <div class="muted">{jogo.get("status_detail") or jogo.get("status_name") or ""}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if mostrar_analise:
        with st.expander("Ver análise deste jogo"):
            mostrar_analise_partida(jogo.get("casa"), jogo.get("fora"))


def mostrar_analise_partida(casa, fora, campo_neutro=False):
    r = calcular_probabilidades(casa, fora, campo_neutro=campo_neutro)

    st.markdown(f"### {r['casa']} x {r['fora']}")

    c1, c2, c3 = st.columns(3)
    c1.metric(f"Vitória {r['casa']}", pct(r["p_casa"]))
    c2.metric("Empate", pct(r["p_empate"]))
    c3.metric(f"Vitória {r['fora']}", pct(r["p_fora"]))

    st.divider()

    c4, c5 = st.columns(2)
    c4.metric("Gols esperados mandante", f"{r['gols_casa']:.2f}")
    c5.metric("Gols esperados visitante", f"{r['gols_fora']:.2f}")

    c6, c7, c8 = st.columns(3)
    c6.metric("+1.5 gols", pct(r["over_15"]))
    c7.metric("+2.5 gols", pct(r["over_25"]))
    c8.metric("Ambas marcam", pct(r["ambas_marcam"]))

    st.divider()

    c9, c10 = st.columns(2)
    c9.metric("Média de escanteios", f"{r['escanteios_total']:.1f}")
    c10.metric("Média de cartões", f"{r['cartoes_total']:.1f}")

    c11, c12 = st.columns(2)
    c11.metric("+8 escanteios", pct(r["prob_mais_8_escanteios"]), nivel_texto(r["prob_mais_8_escanteios"]))
    c12.metric("+9 escanteios", pct(r["prob_mais_9_escanteios"]), nivel_texto(r["prob_mais_9_escanteios"]))

    c13, c14 = st.columns(2)
    c13.metric("+3 cartões", pct(r["prob_mais_3_cartoes"]), nivel_texto(r["prob_mais_3_cartoes"]))
    c14.metric("+4 cartões", pct(r["prob_mais_4_cartoes"]), nivel_texto(r["prob_mais_4_cartoes"]))

    st.warning(
        "As probabilidades são estimativas matemáticas. Use como leitura estatística, não como garantia de resultado."
    )


# ============================================================
# TOPO DO APP
# ============================================================

st.title(APP_TITLE)

col_top1, col_top2 = st.columns([3, 1])

with col_top1:
    competicao_nome = st.selectbox(
        "🏆 Campeonato ou copa",
        list(COMPETICOES.keys()),
        index=0,
        key="competicao_principal",
    )

with col_top2:
    st.write("")
    st.write("")
    if st.button("Sair", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

competicao = COMPETICOES[competicao_nome]
slug_espn = competicao["espn"]

st.caption(f"Selecionado: {competicao_nome}")

if st.button("🔄 Atualizar dados agora", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.divider()


# ============================================================
# ABAS
# ============================================================

tab_ao_vivo, tab_proximos, tab_analise, tab_ajuda = st.tabs(
    ["🔴 Ao vivo", "📅 Próximos", "📊 Analisar", "ℹ️ Ajuda"]
)


# ============================================================
# ABA AO VIVO
# ============================================================

with tab_ao_vivo:
    st.subheader("🔴 Jogos ao vivo")

    jogos_hoje, logs = buscar_jogos_periodo(slug_espn, dias=0)
    jogos_live = filtrar_ao_vivo(jogos_hoje)

    if jogos_live:
        st.success(f"{len(jogos_live)} jogo(s) ao vivo encontrado(s).")
        for jogo in jogos_live:
            mostrar_jogo_card(jogo, mostrar_analise=True)
    else:
        st.info("Nenhum jogo ao vivo encontrado agora para esta competição.")
        if jogos_hoje:
            st.markdown("### Jogos de hoje")
            for jogo in jogos_hoje:
                mostrar_jogo_card(jogo, mostrar_analise=True)
        else:
            st.warning("Não encontrei jogos hoje nessa competição.")

    if logs:
        with st.expander("Ver log"):
            for l in logs:
                st.write(l)


# ============================================================
# ABA PRÓXIMOS
# ============================================================

with tab_proximos:
    st.subheader("📅 Próximos jogos")

    dias = st.slider("Buscar jogos nos próximos dias", 1, 30, 14)

    jogos, logs = buscar_jogos_periodo(slug_espn, dias=dias)

    jogos_futuros = []
    hoje_iso = br_today().strftime("%Y-%m-%d")

    for j in jogos:
        state = str(j.get("status_state", "")).lower()
        if state != "post" and j.get("data", "") >= hoje_iso:
            jogos_futuros.append(j)

    if jogos_futuros:
        st.success(f"{len(jogos_futuros)} jogo(s) encontrado(s).")
        for jogo in jogos_futuros:
            mostrar_jogo_card(jogo, mostrar_analise=True)
    else:
        st.warning("Não encontrei próximos jogos para esta competição no período selecionado.")

    if logs:
        with st.expander("Ver log"):
            for l in logs:
                st.write(l)


# ============================================================
# ABA ANÁLISE MANUAL
# ============================================================

with tab_analise:
    st.subheader("📊 Análise manual")

    st.write("Digite dois times para calcular uma estimativa de vitória, gols, cartões e escanteios.")

    col1, col2 = st.columns(2)

    with col1:
        time_casa = st.text_input("Time mandante", value="Flamengo")

    with col2:
        time_fora = st.text_input("Time visitante", value="Palmeiras")

    campo_neutro = st.checkbox("Campo neutro", value=False)

    if st.button("Analisar partida", use_container_width=True):
        if not time_casa.strip() or not time_fora.strip():
            st.error("Digite o nome dos dois times.")
        else:
            mostrar_analise_partida(time_casa, time_fora, campo_neutro=campo_neutro)

    st.divider()

    st.markdown("### Analisar a partir dos próximos jogos")

    jogos_para_escolher, _logs = buscar_jogos_periodo(slug_espn, dias=14)

    if jogos_para_escolher:
        opcoes = []
        mapa = {}

        for j in jogos_para_escolher:
            label = f"{fmt_data_iso(j['data'])} {j['hora']} — {j['casa']} x {j['fora']}"
            opcoes.append(label)
            mapa[label] = j

        escolhido = st.selectbox("Escolha um jogo", opcoes)

        if st.button("Analisar jogo escolhido", use_container_width=True):
            j = mapa[escolhido]
            mostrar_analise_partida(j["casa"], j["fora"])
    else:
        st.info("Não há jogos carregados para análise automática nesta competição.")


# ============================================================
# ABA AJUDA
# ============================================================

with tab_ajuda:
    st.subheader("ℹ️ Como usar")

    st.markdown(
        """
        **Login do app:**

        - Usuário: `admin`
        - Senha: `12354`

        **O que foi melhorado nesta versão:**

        - O seletor de campeonato/copa fica no topo da tela.
        - Funciona melhor no celular.
        - Copa do Brasil e Libertadores aparecem como opção.
        - Não usa SofaScore.
        - Busca jogos pela ESPN.
        - Faz análise estimada de vitória, gols, cartões e escanteios.

        **Importante:**

        As estatísticas são estimativas. O app não garante resultado de jogo.
        Ele serve para leitura, comparação e análise.
        """
    )

    st.divider()

    st.markdown("### Competições disponíveis")

    for nome in COMPETICOES:
        st.write(f"✅ {nome}")

    st.divider()

    st.caption(f"Última atualização da tela: {br_now().strftime('%d/%m/%Y %H:%M:%S')}")