import math
import html
import re
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st


st.set_page_config(
    page_title="Analisador Esportivo Pro 7.0",
    page_icon="🏟️",
    layout="wide",
    initial_sidebar_state="expanded",
)

TZ_BR = ZoneInfo("America/Sao_Paulo")
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
ODDS_BASE = "https://api.the-odds-api.com/v4/sports"
HEADERS = {"User-Agent": "Mozilla/5.0 AnalisadorEsportivoPro/7.0"}
MAX_GOLS = 10


COMPETICOES_FUTEBOL = {
    "Brasileirão Série A": {"espn": "bra.1", "odds": "soccer_brazil_campeonato"},
    "Brasileirão Série B": {"espn": "bra.2", "odds": "soccer_brazil_serie_b"},
    "Copa do Brasil": {"espn": "bra.copa_do_brasil", "odds": "soccer_brazil_copa_do_brasil"},
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

TORNEIOS_TENIS = {
    "ATP French Open": "tennis_atp_french_open",
    "WTA French Open": "tennis_wta_french_open",
    "ATP Wimbledon": "tennis_atp_wimbledon",
    "WTA Wimbledon": "tennis_wta_wimbledon",
    "ATP US Open": "tennis_atp_us_open",
    "WTA US Open": "tennis_wta_us_open",
    "ATP Australian Open": "tennis_atp_aus_open_singles",
    "WTA Australian Open": "tennis_wta_aus_open_singles",
    "ATP Italian Open": "tennis_atp_italian_open",
    "WTA Italian Open": "tennis_wta_italian_open",
    "ATP Madrid Open": "tennis_atp_madrid_open",
    "WTA Madrid Open": "tennis_wta_madrid_open",
    "ATP Miami Open": "tennis_atp_miami_open",
    "WTA Miami Open": "tennis_wta_miami_open",
    "ATP Indian Wells": "tennis_atp_indian_wells",
    "WTA Indian Wells": "tennis_wta_indian_wells",
    "ATP Monte-Carlo Masters": "tennis_atp_monte_carlo_masters",
    "ATP Cincinnati Open": "tennis_atp_cincinnati_open",
    "WTA Cincinnati Open": "tennis_wta_cincinnati_open",
    "ATP Canadian Open": "tennis_atp_canadian_open",
    "WTA Canadian Open": "tennis_wta_canadian_open",
    "ATP Shanghai Masters": "tennis_atp_shanghai_masters",
    "ATP Paris Masters": "tennis_atp_paris_masters",
    "WTA China Open": "tennis_wta_china_open",
    "ATP China Open": "tennis_atp_china_open",
}

FORCA_BASE = {
    "Flamengo": 86, "Palmeiras": 85, "Botafogo": 81, "Atlético-MG": 80,
    "São Paulo": 78, "Fluminense": 78, "Grêmio": 77, "Internacional": 77,
    "Corinthians": 76, "Cruzeiro": 75, "Bahia": 74, "Fortaleza": 73,
    "Vasco": 72, "Santos": 72, "Sport": 68, "Ceará": 69, "Vitória": 69,
    "Manchester City": 91, "Arsenal": 88, "Liverpool": 88, "Chelsea": 82,
    "Tottenham Hotspur": 80, "Real Madrid": 90, "Barcelona": 88,
    "Atlético Madrid": 84, "Bayern Munich": 88, "Borussia Dortmund": 82,
    "Bayer Leverkusen": 84, "Inter Milan": 86, "Juventus": 82, "PSG": 88,
}

CLASSICOS = {
    tuple(sorted(["flamengo", "vasco"])),
    tuple(sorted(["flamengo", "fluminense"])),
    tuple(sorted(["flamengo", "botafogo"])),
    tuple(sorted(["palmeiras", "corinthians"])),
    tuple(sorted(["sao paulo", "corinthians"])),
    tuple(sorted(["sao paulo", "palmeiras"])),
    tuple(sorted(["gremio", "internacional"])),
    tuple(sorted(["atletico-mg", "cruzeiro"])),
    tuple(sorted(["real madrid", "barcelona"])),
    tuple(sorted(["manchester united", "manchester city"])),
    tuple(sorted(["liverpool", "everton"])),
    tuple(sorted(["inter milan", "milan"])),
}

ALIASES = {
    "man city": "manchester city",
    "man utd": "manchester united",
    "man united": "manchester united",
    "tottenham": "tottenham hotspur",
