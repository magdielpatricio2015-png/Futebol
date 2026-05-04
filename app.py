import math
import html
import re
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

# ============================================================
# ANALISADOR FUTEBOL PRO 6.0
# ESPN + Elo + Poisson + odds auto + xG + desfalques + live
# ============================================================

st.set_page_config(
    page_title="Analisador Futebol Pro 6.0",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

TZ_BR = ZoneInfo("America/Sao_Paulo")
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
HEADERS = {"User-Agent": "Mozilla/5.0 AnalisadorFutebolPro/6.0"}
MAX_GOLS = 12

COMPETICOES = {
    "Brasileirão Série A": {"espn": "bra.1", "odds": "soccer_brazil_campeonato"},
    "Brasileirão Série B": {"espn": "bra.2", "odds": "soccer_brazil_serie_b"},
    "Copa do Brasil": {"espn": "bra.copa_do_brasil", "odds": "soccer_brazil_cup"},
    "Libertadores": {"espn": "conmebol.libertadores", "odds": "soccer_conmebol_copa_libertadores"},
    "Sul-Americana": {"espn": "conmebol.sudamericana", "odds": "soccer_conmebol_copa_sudamericana"},
    "Premier League": {"espn": "eng.1", "odds": "soccer_epl"},
    "La Liga": {"espn": "esp.1", "odds": "soccer_spain_la_liga"},
    "Serie A Itália": {"espn": "ita.1", "odds": "soccer_italy_serie_a"},
    "Bundesliga": {"espn": "ger.1", "odds": "soccer_germany_bundesliga"},
    "Ligue 1": {"espn": "fra.1", "odds": "soccer_france_ligue_one"},
    "Champions League": {"espn": "uefa.champions", "odds": "soccer_uefa_champs_league"},
    "Europa League": {"espn": "uefa.europa", "odds": "soccer_uefa_europa_league"},
}

FORCA_BASE = {
    "Flamengo": 86, "Palmeiras": 85, "Botafogo": 81, "Atlético-MG": 80, "Atletico-MG": 80,
    "São Paulo": 78, "Sao Paulo": 78, "Fluminense": 78, "Grêmio": 77, "Gremio": 77,
    "Internacional": 77, "Corinthians": 76, "Cruzeiro": 75, "Bahia": 74, "Fortaleza": 73,
    "Vasco": 72, "Santos": 72, "Sport": 68, "Ceará": 69, "Ceara": 69, "Vitória": 69,
    "Vitoria": 69, "Manchester City": 91, "Arsenal": 88, "Liverpool": 88, "Chelsea": 82,
    "Tottenham Hotspur": 80, "Real Madrid": 90, "Barcelona": 88, "Atlético Madrid": 84,
    "Atletico Madrid": 84, "Bayern Munich": 88, "Borussia Dortmund": 82,
    "Bayer Leverkusen": 84, "Inter Milan": 86, "Juventus": 82, "PSG": 88,
}

APELIDOS = {
    "man city": "manchester city",
    "manchester city fc": "manchester city",
    "man utd": "manchester united",
    "man united": "manchester united",
    "spurs": "tottenham hotspur",
    "tottenham": "tottenham hotspur",
    "inter": "inter milan",
    "internazionale": "inter milan",
    "ac milan": "milan",
    "atletico mineiro": "atletico-mg",
    "atlético mineiro": "atletico-mg",
    "gremio": "grêmio",
    "sao paulo": "são paulo",
    "ceara": "ceará",
    "vitoria": "vitória",
    "flamengo rj": "flamengo",
    "palmeiras sp": "palmeiras",
    "corinthians sp": "corinthians",
    "psg": "paris saint-germain",
}

CLASSICOS = [
    ("Flamengo", "Vasco"), ("Flamengo", "Fluminense"), ("Flamengo", "Botafogo"),
    ("Corinthians", "Palmeiras"), ("Corinthians", "São Paulo"), ("Corinthians", "Santos"),
    ("Palmeiras", "São Paulo"), ("São Paulo", "Santos"),
    ("Grêmio", "Internacional"), ("Atletico-MG", "Cruzeiro"), ("Atlético-MG", "Cruzeiro"),
    ("Bahia", "Vitória"), ("Ceará", "Fortaleza"),
    ("Real Madrid", "Barcelona"), ("Manchester United", "Liverpool"),
    ("Arsenal", "Tottenham Hotspur"), ("Inter Milan", "AC Milan"),
]

JOGADORES_CHAVE = {
    "Flamengo": {
        "Giorgian de Arrascaeta": {"ataque": -0.16, "defesa": 0.00},
        "Erick Pulgar": {"ataque": -0.03, "defesa": -0.11},
        "Pedro": {"ataque": -0.13, "defesa": 0.00},
        "Bruno Henrique": {"ataque": -0.08, "defesa": 0.00},
    },
    "Palmeiras": {
        "Raphael Veiga": {"ataque": -0.10, "defesa": 0.00},
        "Gustavo Gómez": {"ataque": -0.02, "defesa": -0.10},
    },
    "Fluminense": {
        "Ganso": {"ataque": -0.09, "defesa": 0.00},
