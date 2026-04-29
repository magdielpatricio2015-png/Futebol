import streamlit as st

# ===== LOGIN SIMPLES =====
USUARIO = "admin"
SENHA = "12354"

def check_login():
    if "logado" not in st.session_state:
        st.session_state.logado = False

    if not st.session_state.logado:
        st.title("🔐 Login necessário")

        user = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")

        if st.button("Entrar"):
            if user == USUARIO and password == SENHA:
                st.session_state.logado = True
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos")

        st.stop()

check_login()
import json
import math
import os
import ssl
import sys
import subprocess
import tempfile
import time
import traceback
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from collections import defaultdict


# ── Gráficos ──────────────────────────────────────────────────────────────────
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.figure import Figure
import matplotlib.gridspec as gridspec
import numpy as np

APP_TITLE = "Analisador de Futebol v72 — Mais Intuitivo"
CACHE_DIR = os.path.join(tempfile.gettempdir(), "analisador_futebol_v71_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# ── Paleta de cores ───────────────────────────────────────────────────────────
COLORS = {
    "bg_dark":     "#eef2f7",
    "bg_panel":    "#ffffff",
    "bg_card":     "#f8fafc",
    "accent_blue": "#2563eb",
    "accent_green":"#15803d",
    "accent_red":  "#dc2626",
    "accent_yel":  "#b45309",
    "accent_gray": "#94a3b8",
    "text_light":  "#111827",
    "text_dim":    "#475569",
    "home_color":  "#1d4ed8",
    "away_color":  "#c2410c",
    "win_color":   "#15803d",
    "draw_color":  "#b45309",
    "loss_color":  "#b91c1c",
}

# ── Matplotlib tema escuro ────────────────────────────────────────────────────
plt.rcParams.update({
    "figure.facecolor":  COLORS["bg_dark"],
    "axes.facecolor":    COLORS["bg_panel"],
    "axes.edgecolor":    COLORS["accent_gray"],
    "axes.labelcolor":   COLORS["text_light"],
    "xtick.color":       COLORS["text_dim"],
    "ytick.color":       COLORS["text_dim"],
    "text.color":        COLORS["text_light"],
    "grid.color":        "#d7dee9",
    "grid.linestyle":    "--",
    "grid.alpha":        0.5,
    "font.family":       "DejaVu Sans",
    "font.size":         9,
})


def now_br():
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def parse_iso_date(value: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except Exception:
        return None


def format_date_br(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return value or "N/D"


def normalize_team_name(name: str) -> str:
    return " ".join((name or "").strip().lower().split())


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def pct2(value: float) -> str:
    return f"{value * 100:.2f}%"


def simple_key(value: str) -> str:
    value = str(value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    for old, new in [("saf", ""), ("fc", ""), ("f.c.", ""), ("-", " "), (".", " ")]:
        value = value.replace(old, new)
    return " ".join(value.split())


SOFASCORE_TEAM_ALIASES = {
    "Santos": "Santos",
    "Vasco da Gama": "Vasco da Gama",
    "Coritiba": "Coritiba",
    "Athletico Paranaense": "Athletico",
    "Atlético Mineiro": "Atletico Mineiro",
    "Grêmio": "Gremio",
    "Remo": "Clube do Remo",
    "Red Bull Bragantino": "Red Bull Bragantino",
}

SOFASCORE_LEAGUES = {
    "serie_a_2026": {"tournament": 325, "season": 87678, "year": "2026", "name": "Brasileirão Série A 2026"},
    "serie_b_2026": {"tournament": 390, "season": 89840, "year": "2026", "name": "Brasileirão Série B 2026"},
    "premier_league_2026": {"tournament": 17, "season": 76986, "year": "25/26", "name": "Premier League 2025/26"},
}

ESPN_LEAGUES = {
    "serie_a_2026": "bra.1",
    "serie_b_2026": "bra.2",
    "premier_league_2026": "eng.1",
    "copa_do_brasil_2026": "bra.copa_do_brasil",
    "libertadores_2026": "conmebol.libertadores",
}

THESPORTSDB_LEAGUES = {
    "serie_a_2026": "4351",
    "serie_b_2026": "4404",
    "premier_league_2026": "4328",
}


# ══════════════════════════════════════════════════════════════════════════════
#  CLIENTE SOFASCORE
# ══════════════════════════════════════════════════════════════════════════════
class ESPNClient:
    BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

    def __init__(self, timeout=16):
        self.timeout = timeout
        self.last_log = []
        self.cache = {}

    def _urlopen_json(self, url):
        if url in self.cache:
            return self.cache[url]
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        })
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        self.cache[url] = data
        return data

    def _try_json(self, url):
        try:
            return self._urlopen_json(url)
        except urllib.error.HTTPError as e:
            self.last_log.append(f"ESPN HTTP {e.code}: {url}")
        except Exception as e:
            self.last_log.append(f"ESPN falhou: {url} -> {e}")
        return None

    @staticmethod
    def _event_datetime(value):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone()
        except Exception:
            return None

    def fetch_league_schedule(self, league_key, league_teams=None, days_ahead=14):
        self.last_log = []
        slug = ESPN_LEAGUES.get(league_key)
        if not slug:
            return [], "Liga sem fonte ESPN configurada."
        today = datetime.now().date()
        team_keys = {simple_key(t) for t in (league_teams or [])}
        matches = []
        seen = set()
        for offset in range(days_ahead + 1):
            day = today + timedelta(days=offset)
            date_key = day.strftime("%Y%m%d")
            url = f"{self.BASE}/{slug}/scoreboard?dates={date_key}&limit=100&region=br&lang=pt"
            data = self._try_json(url)
            if not data:
                continue
            for ev in data.get("events", []):
                event_id = ev.get("id")
                if not event_id or event_id in seen:
                    continue
                seen.add(event_id)
                comps = ev.get("competitions") or []
                comp = comps[0] if comps else {}
                status_type = (((comp.get("status") or {}).get("type") or {}).get("state") or "").lower()
                if status_type == "post":
                    continue
                dt = self._event_datetime(ev.get("date", ""))
                if not dt:
                    continue
                home_name = away_name = ""
                for competitor in comp.get("competitors", []):
                    team = competitor.get("team") or {}
                    name = team.get("displayName") or team.get("shortDisplayName") or team.get("name") or ""
                    if competitor.get("homeAway") == "home":
                        home_name = name
                    elif competitor.get("homeAway") == "away":
                        away_name = name
                if not home_name or not away_name:
                    continue
                if team_keys and simple_key(home_name) not in team_keys and simple_key(away_name) not in team_keys:
                    continue
                matches.append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "time": dt.strftime("%H:%M"),
                    "home_team": home_name,
                    "away_team": away_name,
                    "_espn_event_id": event_id,
                    "source": "ESPN",
                })
        matches.sort(key=lambda m: (m.get("date", ""), m.get("time", "")))
        self.last_log.append(f"ESPN: {len(matches)} jogo(s) encontrado(s).")
        return matches, "\n".join(self.last_log)


class TheSportsDBClient:
    BASE = "https://www.thesportsdb.com/api/v1/json/123"

    def __init__(self, timeout=16):
        self.timeout = timeout
        self.last_log = []
        self.cache = {}

    def _urlopen_json(self, url):
        if url in self.cache:
            return self.cache[url]
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json,text/plain,*/*",
        })
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        self.cache[url] = data
        return data

    def _try_json(self, url):
        try:
            return self._urlopen_json(url)
        except urllib.error.HTTPError as e:
            self.last_log.append(f"TheSportsDB HTTP {e.code}: {url}")
        except Exception as e:
            self.last_log.append(f"TheSportsDB falhou: {url} -> {e}")
        return None

    @staticmethod
    def _parse_event_datetime(event):
        timestamp = event.get("strTimestamp") or ""
        if timestamp:
            try:
                return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone()
            except Exception:
                pass
        date_value = event.get("dateEvent") or event.get("dateEventLocal") or ""
        time_value = event.get("strTimeLocal") or event.get("strTime") or "00:00:00"
        try:
            return datetime.strptime(f"{date_value} {time_value[:5]}", "%Y-%m-%d %H:%M")
        except Exception:
            return None

    def fetch_league_schedule(self, league_key, league_teams=None, days_ahead=14):
        self.last_log = []
        league_id = THESPORTSDB_LEAGUES.get(league_key)
        if not league_id:
            return [], "Liga sem fonte TheSportsDB configurada."
        today = datetime.now().date()
        end_day = today + timedelta(days=days_ahead)
        team_keys = {simple_key(t) for t in (league_teams or [])}
        url = f"{self.BASE}/eventsnextleague.php?id={league_id}"
        data = self._try_json(url)
        matches = []
        seen = set()
        for ev in (data or {}).get("events") or []:
            event_id = ev.get("idEvent")
            if not event_id or event_id in seen:
                continue
            seen.add(event_id)
            dt = self._parse_event_datetime(ev)
            if not dt or not (today <= dt.date() <= end_day):
                continue
            home_name = ev.get("strHomeTeam") or ""
            away_name = ev.get("strAwayTeam") or ""
            if not home_name or not away_name:
                continue
            if team_keys and simple_key(home_name) not in team_keys and simple_key(away_name) not in team_keys:
                continue
            matches.append({
                "date": dt.strftime("%Y-%m-%d"),
                "time": dt.strftime("%H:%M"),
                "home_team": home_name,
                "away_team": away_name,
                "_thesportsdb_event_id": event_id,
                "source": "TheSportsDB",
            })
        matches.sort(key=lambda m: (m.get("date", ""), m.get("time", "")))
        self.last_log.append(f"TheSportsDB: {len(matches)} jogo(s) encontrado(s).")
        return matches, "\n".join(self.last_log)


class SofaScoreClient:
    BASE = "https://www.sofascore.com/api/v1"

    def __init__(self, timeout=16):
        self.timeout = timeout
        self.cache = {}
        self.team_cache = {}
        self.season_cache = {}
        self.last_log = []
        self.ssl_context = self._make_ssl_context(allow_insecure=False)
        self.ssl_compat_context = None
        self.ssl_compat_used = False

    @staticmethod
    def _make_ssl_context(allow_insecure=False):
        if allow_insecure:
            try:
                return ssl._create_unverified_context()
            except Exception:
                return None
        try:
            import certifi
            return ssl.create_default_context(cafile=certifi.where())
        except Exception:
            return ssl.create_default_context()

    @staticmethod
    def _is_ssl_certificate_error(exc):
        text = str(exc).lower()
        return (
            "certificate_verify_failed" in text
            or ("certificado" in text and "ssl" in text)
            or "unable to get local issuer certificate" in text
            or isinstance(getattr(exc, "reason", None), ssl.SSLCertVerificationError)
        )

    def _open_request(self, req):
        try:
            return urllib.request.urlopen(req, timeout=self.timeout, context=self.ssl_context)
        except Exception as e:
            if not self._is_ssl_certificate_error(e):
                raise
            if self.ssl_compat_context is None:
                self.ssl_compat_context = self._make_ssl_context(allow_insecure=True)
            if not self.ssl_compat_used:
                self._log("SSL compatibilidade ativada para dados públicos do SofaScore.")
                self.ssl_compat_used = True
            return urllib.request.urlopen(req, timeout=self.timeout, context=self.ssl_compat_context)

    def _log(self, msg):
        self.last_log.append(str(msg))

    def _urlopen_json(self, url):
        if url in self.cache:
            return self.cache[url]
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AnalisadorFutebol/7.2",
                "Accept": "application/json,text/plain,*/*",
                "Referer": "https://www.sofascore.com/pt/",
                "Origin": "https://www.sofascore.com",
            },
        )
        with self._open_request(req) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        self.cache[url] = data
        return data

    def _try_json(self, url):
        try:
            return self._urlopen_json(url)
        except urllib.error.HTTPError as e:
            self._log(f"HTTP {e.code}: {url}")
        except Exception as e:
            self._log(f"Falhou: {url} -> {e}")
        return None

    def _walk_dicts(self, obj):
        if isinstance(obj, dict):
            yield obj
            for v in obj.values():
                yield from self._walk_dicts(v)
        elif isinstance(obj, list):
            for item in obj:
                yield from self._walk_dicts(item)

    def _extract_team_candidates(self, data):
        candidates = []
        for d in self._walk_dicts(data):
            entity = d.get("entity") if isinstance(d.get("entity"), dict) else d
            if not isinstance(entity, dict):
                continue
            if "id" not in entity:
                continue
            sport = entity.get("sport") or {}
            sport_name = simple_key(sport.get("name") or sport.get("slug") or "")
            entity_type = simple_key(entity.get("type") or d.get("type") or "")
            name = entity.get("name") or entity.get("shortName") or entity.get("slug") or ""
            if not name:
                continue
            if sport_name and "football" not in sport_name and "futebol" not in sport_name:
                continue
            if entity_type and entity_type not in ("team", "equipa", "time"):
                if not (entity.get("name") and entity.get("slug")):
                    continue
            candidates.append(entity)
        return candidates

    def _score_team_candidate(self, candidate, wanted):
        wanted_key = simple_key(wanted)
        name = candidate.get("name") or ""
        short = candidate.get("shortName") or ""
        slug = candidate.get("slug") or ""
        text = simple_key(f"{name} {short} {slug}")
        score = 0
        if simple_key(name) == wanted_key or simple_key(short) == wanted_key:
            score += 100
        if wanted_key and wanted_key in text:
            score += 40
        for piece in wanted_key.split():
            if len(piece) >= 3 and piece in text:
                score += 8
        bad_words = ["women", "feminino", "u20", "sub 20", "u23", "youth"]
        if any(w in text for w in bad_words):
            score -= 25
        country = candidate.get("country") or {}
        country_text = simple_key(country.get("name") or country.get("alpha2") or "")
        if country_text in ("brazil", "brasil", "br"):
            score += 8
        return score

    def find_team_id(self, app_team_name, cache=None):
        cache = cache if cache is not None else self.team_cache
        alias = SOFASCORE_TEAM_ALIASES.get(app_team_name, app_team_name)
        cache_keys = {simple_key(app_team_name), simple_key(alias)}
        for key in cache_keys:
            if key and key in cache:
                return cache[key]

        queries = []
        for q in (alias, app_team_name, simple_key(alias)):
            if q and q not in queries:
                queries.append(q)

        best = None
        best_score = -999
        for q in queries:
            encoded = urllib.parse.quote(q)
            urls = [
                f"{self.BASE}/search/all?q={encoded}",
                f"{self.BASE}/search/teams?q={encoded}",
                f"{self.BASE}/search?q={encoded}",
            ]
            for url in urls:
                data = self._try_json(url)
                if not data:
                    continue
                for cand in self._extract_team_candidates(data):
                    score = self._score_team_candidate(cand, alias)
                    if score > best_score:
                        best_score = score
                        best = cand
            if best and best_score >= 80:
                break

        if not best:
            raise RuntimeError(f"Não encontrei o time no SofaScore: {app_team_name}")
        team_id = int(best["id"])
        team_name = best.get("name") or best.get("shortName") or app_team_name
        result = (team_id, team_name)
        for key in cache_keys:
            if key:
                cache[key] = result
        return result

    def fetch_team_season_stats(self, team_id, tournament_id, season_id):
        """Busca estatísticas de temporada do time: cartões, escanteios, etc."""
        url = f"{self.BASE}/team/{team_id}/unique-tournament/{tournament_id}/season/{season_id}/statistics/overall"
        data = self._try_json(url)
        if not data or "statistics" not in data:
            return {}
        s = data["statistics"]
        matches = max(s.get("matches", 1), 1)
        return {
            "season_matches": matches,
            "season_yellow_cards": s.get("yellowCards", 0),
            "season_red_cards": s.get("redCards", 0),
            "season_yellow_red_cards": s.get("yellowRedCards", 0),
            "season_corners": s.get("corners", 0),
            "season_corners_against": s.get("cornersAgainst", 0),
            "season_yellow_cards_against": s.get("yellowCardsAgainst", 0),
            "season_red_cards_against": s.get("redCardsAgainst", 0),
            "season_fouls": s.get("fouls", 0),
            "season_shots_on_target": s.get("shotsOnTarget", 0),
            "season_big_chances": s.get("bigChances", 0),
            "season_goals": s.get("goalsScored", 0),
            "season_goals_conceded": s.get("goalsConceded", 0),
            "season_clean_sheets": s.get("cleanSheets", 0),
            "season_possession_avg": s.get("averageBallPossession", 50.0),
            # médias por jogo
            "avg_yellow_per_game": s.get("yellowCards", 0) / matches,
            "avg_red_per_game": s.get("redCards", 0) / matches,
            "avg_corners_for_per_game": s.get("corners", 0) / matches,
            "avg_corners_against_per_game": s.get("cornersAgainst", 0) / matches,
            "avg_goals_per_game": s.get("goalsScored", 0) / matches,
            "avg_goals_conceded_per_game": s.get("goalsConceded", 0) / matches,
        }

    def fetch_event_statistics(self, event_id):
        url = f"{self.BASE}/event/{event_id}/statistics"
        data = self._try_json(url)
        if not data or "statistics" not in data:
            return {}
        result = {}
        for period_block in data.get("statistics", []):
            if period_block.get("period") != "ALL":
                continue
            for group in period_block.get("groups", []):
                for item in group.get("statisticsItems", []):
                    key = item.get("key", "")
                    hv = item.get("homeValue")
                    av = item.get("awayValue")
                    if key == "cornerKicks":
                        result["home_corners"] = hv
                        result["away_corners"] = av
                    elif key == "yellowCards":
                        result["home_yellow_cards"] = hv
                        result["away_yellow_cards"] = av
                    elif key == "ballPossession":
                        result["home_possession"] = hv
                        result["away_possession"] = av
                    elif key == "totalShotsOnGoal":
                        result["home_shots"] = hv
                        result["away_shots"] = av
                    elif key == "shotsOnGoal":
                        result["home_shots_on_target"] = hv
                        result["away_shots_on_target"] = av
                    elif key == "fouls":
                        result["home_fouls"] = hv
                        result["away_fouls"] = av
                    elif key == "expectedGoals":
                        result["home_xg"] = hv
                        result["away_xg"] = av
        return result

    def fetch_event_cards_from_incidents(self, event_id, home_id=None, away_id=None):
        url = f"{self.BASE}/event/{event_id}/incidents"
        data = self._try_json(url)
        if not data:
            return {}
        incidents = data.get("incidents") if isinstance(data, dict) else []
        if not isinstance(incidents, list):
            return {}
        home_yellow = home_red = away_yellow = away_red = 0
        for inc in incidents:
            if not isinstance(inc, dict):
                continue
            inc_type = (inc.get("incidentType") or "").lower()
            if inc_type not in ("card",):
                continue
            card_type = (inc.get("incidentClass") or "").lower()
            team = inc.get("team") or {}
            team_id = team.get("id")
            if card_type in ("yellow", "yellowcard"):
                if home_id and team_id and int(team_id) == int(home_id):
                    home_yellow += 1
                elif away_id and team_id and int(team_id) == int(away_id):
                    away_yellow += 1
            elif card_type in ("red", "redcard", "yellowred"):
                if home_id and team_id and int(team_id) == int(home_id):
                    home_red += 1
                elif away_id and team_id and int(team_id) == int(away_id):
                    away_red += 1
        result = {}
        if home_yellow or home_red:
            result["home_yellow_cards"] = home_yellow
            result["home_red_cards"] = home_red
        if away_yellow or away_red:
            result["away_yellow_cards"] = away_yellow
            result["away_red_cards"] = away_red
        return result

    def _resolve_season(self, league_key):
        cfg = SOFASCORE_LEAGUES.get(league_key)
        if not cfg:
            return None, None
        tid = cfg["tournament"]
        sid = cfg["season"]
        if league_key in self.season_cache:
            return tid, self.season_cache[league_key]
        url = f"{self.BASE}/unique-tournament/{tid}/seasons"
        data = self._try_json(url)
        if data and isinstance(data.get("seasons"), list):
            for s in data["seasons"]:
                if str(s.get("year", "")) == str(cfg.get("year", "")):
                    sid = s["id"]
                    break
        self.season_cache[league_key] = sid
        return tid, sid

    def fetch_league_schedule(self, league_key, league_teams=None, days_ahead=14):
        self.last_log = []
        tid, sid = self._resolve_season(league_key)
        if not tid:
            return [], "Liga não configurada."
        today = datetime.now().date()
        end_day = today + timedelta(days=days_ahead)
        matches = []
        seen = set()
        for round_num in range(1, 40):
            url = f"{self.BASE}/unique-tournament/{tid}/season/{sid}/events/round/{round_num}"
            data = self._try_json(url)
            if not data:
                break
            events = data.get("events") if isinstance(data, dict) else []
            if not isinstance(events, list) or not events:
                break
            found_future = False
            for ev in events:
                ts = ev.get("startTimestamp")
                if not ts:
                    continue
                ev_date = datetime.fromtimestamp(int(ts)).date()
                if ev_date < today or ev_date > end_day:
                    continue
                found_future = True
                status = ev.get("status") or {}
                if status.get("type") in ("finished", "ended"):
                    continue
                event_id = ev.get("id")
                if event_id in seen:
                    continue
                seen.add(event_id)
                home_name = (ev.get("homeTeam") or {}).get("name", "")
                away_name = (ev.get("awayTeam") or {}).get("name", "")
                if league_teams:
                    hk = simple_key(home_name)
                    ak = simple_key(away_name)
                    team_keys = {simple_key(t) for t in league_teams}
                    if hk not in team_keys and ak not in team_keys:
                        continue
                ev_time = datetime.fromtimestamp(int(ts)).strftime("%H:%M")
                matches.append({
                    "date": ev_date.strftime("%Y-%m-%d"),
                    "time": ev_time,
                    "home_team": home_name,
                    "away_team": away_name,
                    "_sofascore_event_id": event_id,
                })
            if not found_future:
                break
        self._log(f"Agenda: {len(matches)} jogo(s) encontrado(s).")
        return matches, "\n".join(self.last_log)

    def _is_finished_event(self, event):
        status = event.get("status") or {}
        status_type = (status.get("type") or "").lower()
        if "notstarted" in status_type or "inprogress" in status_type:
            return False
        if any(x in status_type for x in ("finished", "ended", "after", "aet", "ap")):
            return True
        return (event.get("homeScore", {}).get("current") is not None and
                event.get("awayScore", {}).get("current") is not None)

    def fetch_last_matches_for_team(self, app_team_name, limit=8):
        team_id, sofa_name = self.find_team_id(app_team_name)
        matches = []
        seen_events = set()
        for page in range(0, 4):
            data = self._try_json(f"{self.BASE}/team/{team_id}/events/last/{page}")
            if not data:
                continue
            events = data.get("events") if isinstance(data, dict) else []
            if not isinstance(events, list):
                continue
            for ev in events:
                if len(matches) >= limit:
                    break
                if not isinstance(ev, dict) or not self._is_finished_event(ev):
                    continue
                event_id = ev.get("id")
                if not event_id or event_id in seen_events:
                    continue
                seen_events.add(event_id)
                home_team = ev.get("homeTeam") or {}
                away_team = ev.get("awayTeam") or {}
                home_id = home_team.get("id")
                away_id = away_team.get("id")
                home_name = home_team.get("name") or "Mandante"
                away_name = away_team.get("name") or "Visitante"
                if home_id is not None and int(home_id) == int(team_id):
                    home_name = app_team_name
                if away_id is not None and int(away_id) == int(team_id):
                    away_name = app_team_name
                hg = ev.get("homeScore", {}).get("current")
                ag = ev.get("awayScore", {}).get("current")
                if hg is None or ag is None:
                    continue
                ts = ev.get("startTimestamp")
                date = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d") if ts else ""
                stats = self.fetch_event_statistics(event_id)
                incident_cards = self.fetch_event_cards_from_incidents(event_id, home_id=home_id, away_id=away_id)
                for key, value in incident_cards.items():
                    if stats.get(key) is None:
                        stats[key] = value
                record = {
                    "date": date,
                    "home_team": home_name,
                    "away_team": away_name,
                    "home_goals": int(hg),
                    "away_goals": int(ag),
                    "_sofascore_event_id": event_id,
                    "source": "SofaScore",
                }
                for key, value in stats.items():
                    if value is not None:
                        record[key] = int(round(value)) if isinstance(value, float) and value == int(value) else value
                matches.append(record)
                time.sleep(0.15)
            if len(matches) >= limit:
                break
        self._log(f"{app_team_name}: {len(matches)} jogo(s) recentes.")
        return matches[:limit]

    def fetch_last_matches_for_teams(self, home_team, away_team, limit=8):
        self.last_log = []
        all_matches = []
        for team in (home_team, away_team):
            try:
                all_matches.extend(self.fetch_last_matches_for_team(team, limit=limit))
            except Exception as e:
                self._log(f"Erro buscando {team}: {e}")
        unique = {}
        for m in all_matches:
            key = m.get("_sofascore_event_id") or (m.get("date"), simple_key(m.get("home_team")), simple_key(m.get("away_team")))
            unique[key] = m
        return list(unique.values()), "\n".join(self.last_log)




# ══════════════════════════════════════════════════════════════════════════════
#  MONITOR AO VIVO E MODELO DE PRESSAO PARA ESCANTEIOS
# ══════════════════════════════════════════════════════════════════════════════
def _safe_number(value, default=0.0):
    """Converte valores vindos das fontes online para numero."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("%", "").replace(",", ".")
    cleaned = []
    for ch in text:
        if ch.isdigit() or ch in ".-":
            cleaned.append(ch)
    try:
        return float("".join(cleaned))
    except Exception:
        return default


def _safe_int(value, default=0):
    try:
        return int(round(_safe_number(value, default)))
    except Exception:
        return default


def _event_minute_from_status(status):
    """Tenta extrair o minuto atual a partir de diferentes formatos de status."""
    if not isinstance(status, dict):
        return 0
    for key in ("displayClock", "clock"):
        raw = status.get(key)
        if raw is None:
            continue
        text = str(raw)
        digits = ""
        for ch in text:
            if ch.isdigit():
                digits += ch
            elif digits:
                break
        if digits:
            return max(0, min(130, int(digits)))
    desc = str(status.get("description") or status.get("shortDetail") or "")
    digits = ""
    for ch in desc:
        if ch.isdigit():
            digits += ch
        elif digits:
            break
    if digits:
        return max(0, min(130, int(digits)))
    return 0


def _score_text(home_score, away_score):
    if home_score is None or away_score is None:
        return "- x -"
    return f"{home_score} x {away_score}"


def espn_fetch_live_matches(self, league_key, league_teams=None):
    """Busca jogos ao vivo pela ESPN sem chave de API."""
    self.last_log = []
    slug = ESPN_LEAGUES.get(league_key)
    if not slug:
        return [], "Liga sem fonte ESPN configurada para ao vivo."
    today_key = datetime.now().strftime("%Y%m%d")
    team_keys = {simple_key(t) for t in (league_teams or [])}
    url = f"{self.BASE}/{slug}/scoreboard?dates={today_key}&limit=100&region=br&lang=pt"
    data = self._try_json(url)
    matches = []
    for ev in (data or {}).get("events", []):
        comps = ev.get("competitions") or []
        comp = comps[0] if comps else {}
        status = comp.get("status") or ev.get("status") or {}
        status_type = ((status.get("type") or {}).get("state") or status.get("state") or "").lower()
        # ESPN geralmente usa: pre, in, post.
        if status_type not in ("in", "live", "inprogress"):
            continue
        home_name = away_name = ""
        home_score = away_score = None
        home_id = away_id = None
        for competitor in comp.get("competitors", []):
            team = competitor.get("team") or {}
            name = team.get("displayName") or team.get("shortDisplayName") or team.get("name") or ""
            score = competitor.get("score")
            if competitor.get("homeAway") == "home":
                home_name = name
                home_score = _safe_int(score, 0)
                home_id = team.get("id")
            elif competitor.get("homeAway") == "away":
                away_name = name
                away_score = _safe_int(score, 0)
                away_id = team.get("id")
        if not home_name or not away_name:
            continue
        if team_keys and simple_key(home_name) not in team_keys and simple_key(away_name) not in team_keys:
            continue
        minute = _event_minute_from_status(status)
        status_desc = status.get("displayClock") or ((status.get("type") or {}).get("description")) or "Ao vivo"
        matches.append({
            "event_id": f"espn_{ev.get('id')}",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M"),
            "home_team": home_name,
            "away_team": away_name,
            "home_score": home_score,
            "away_score": away_score,
            "minute": minute,
            "status": str(status_desc),
            "source": "ESPN ao vivo",
            "stats": {},
            "home_id": home_id,
            "away_id": away_id,
        })
    self.last_log.append(f"ESPN ao vivo: {len(matches)} jogo(s) encontrado(s).")
    return matches, "\n".join(self.last_log)


ESPNClient.fetch_live_matches = espn_fetch_live_matches


def sofascore_fetch_live_matches(self, league_key, league_teams=None):
    """Busca jogos ao vivo pelo endpoint público de futebol do SofaScore."""
    self.last_log = []
    cfg = SOFASCORE_LEAGUES.get(league_key)
    wanted_tid = str(cfg.get("tournament")) if cfg else ""
    team_keys = {simple_key(t) for t in (league_teams or [])}
    data = self._try_json(f"{self.BASE}/sport/football/events/live")
    events = (data or {}).get("events") if isinstance(data, dict) else []
    matches = []
    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        tournament = ev.get("tournament") or {}
        unique = tournament.get("uniqueTournament") or {}
        tid = str(unique.get("id") or tournament.get("id") or "")
        home_team = ev.get("homeTeam") or {}
        away_team = ev.get("awayTeam") or {}
        home_name = home_team.get("name") or home_team.get("shortName") or "Mandante"
        away_name = away_team.get("name") or away_team.get("shortName") or "Visitante"
        if wanted_tid and tid and tid != wanted_tid:
            # Se o endpoint vier amplo demais, filtra pela liga quando possivel.
            continue
        if team_keys and simple_key(home_name) not in team_keys and simple_key(away_name) not in team_keys:
            continue
        event_id = ev.get("id")
        status = ev.get("status") or {}
        minute = _event_minute_from_status(status)
        hs = (ev.get("homeScore") or {}).get("current")
        aw = (ev.get("awayScore") or {}).get("current")
        stats = {}
        if event_id:
            try:
                stats = self.fetch_event_statistics(event_id) or {}
            except Exception as exc:
                self._log(f"Falhou estatísticas ao vivo {event_id}: {exc}")
        matches.append({
            "event_id": f"sofa_{event_id}",
            "_sofascore_event_id": event_id,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M"),
            "home_team": home_name,
            "away_team": away_name,
            "home_score": hs,
            "away_score": aw,
            "minute": minute,
            "status": status.get("description") or status.get("type") or "Ao vivo",
            "source": "SofaScore ao vivo",
            "stats": stats,
            "home_id": home_team.get("id"),
            "away_id": away_team.get("id"),
        })
    self._log(f"SofaScore ao vivo: {len(matches)} jogo(s) encontrado(s).")
    return matches, "\n".join(self.last_log)


SofaScoreClient.fetch_live_matches = sofascore_fetch_live_matches


class LivePressureAnalyzer:
    """Calcula uma leitura simples de pressao recente para escanteios.

    Importante: sem API paga, a qualidade depende do que ESPN/SofaScore entregarem.
    Quando não houver estatística ao vivo, o programa mostra a limitação em vez de inventar certeza.
    """

    def __init__(self):
        self.snapshots = defaultdict(list)

    def _extract_team_stats(self, match):
        stats = match.get("stats") or {}
        return {
            "home_corners": _safe_number(stats.get("home_corners"), 0),
            "away_corners": _safe_number(stats.get("away_corners"), 0),
            "home_shots": _safe_number(stats.get("home_shots"), 0),
            "away_shots": _safe_number(stats.get("away_shots"), 0),
            "home_sot": _safe_number(stats.get("home_shots_on_target"), 0),
            "away_sot": _safe_number(stats.get("away_shots_on_target"), 0),
            "home_possession": _safe_number(stats.get("home_possession"), 0),
            "away_possession": _safe_number(stats.get("away_possession"), 0),
        }

    def _snapshot(self, match):
        values = self._extract_team_stats(match)
        values["ts"] = time.time()
        values["minute"] = _safe_number(match.get("minute"), 0)
        return values

    def _recent_delta(self, event_id, field, seconds):
        items = self.snapshots.get(event_id, [])
        if len(items) < 2:
            return 0.0
        latest = items[-1]
        older = None
        target = latest["ts"] - seconds
        for item in reversed(items[:-1]):
            if item["ts"] <= target:
                older = item
                break
        if older is None:
            older = items[0]
        return max(0.0, latest.get(field, 0) - older.get(field, 0))

    def evaluate(self, match, prediction=None):
        event_id = match.get("event_id") or f"manual_{match.get('home_team')}_{match.get('away_team')}"
        snap = self._snapshot(match)
        self.snapshots[event_id].append(snap)
        self.snapshots[event_id] = self.snapshots[event_id][-30:]

        minute = max(1.0, snap.get("minute") or 1.0)
        home_score = _safe_number(match.get("home_score"), 0)
        away_score = _safe_number(match.get("away_score"), 0)

        expected_total = 9.5
        expected_home = 4.8
        expected_away = 4.4
        if prediction and prediction.get("corners"):
            c = prediction["corners"]
            expected_total = max(5.0, _safe_number(c.get("total_expected"), 9.5))
            expected_home = max(1.0, _safe_number(c.get("home_expected"), 4.8))
            expected_away = max(1.0, _safe_number(c.get("away_expected"), 4.4))

        total_corners = snap["home_corners"] + snap["away_corners"]
        total_shots = snap["home_shots"] + snap["away_shots"]
        total_sot = snap["home_sot"] + snap["away_sot"]
        corner_pace_90 = (total_corners / minute) * 90.0
        shot_pace_90 = (total_shots / minute) * 90.0

        recent_home = (
            self._recent_delta(event_id, "home_corners", 300) * 13 +
            self._recent_delta(event_id, "home_shots", 300) * 5 +
            self._recent_delta(event_id, "home_sot", 300) * 9
        )
        recent_away = (
            self._recent_delta(event_id, "away_corners", 300) * 13 +
            self._recent_delta(event_id, "away_shots", 300) * 5 +
            self._recent_delta(event_id, "away_sot", 300) * 9
        )

        home_score_pressure = 28.0
        away_score_pressure = 28.0
        # Ritmo de escanteios até aqui comparado com o esperado pré-jogo.
        pace_bonus = max(-10.0, min(22.0, (corner_pace_90 / expected_total - 1.0) * 28.0))
        shots_bonus = max(0.0, min(14.0, (shot_pace_90 - 18.0) * 0.75))
        home_score_pressure += pace_bonus + shots_bonus
        away_score_pressure += pace_bonus + shots_bonus

        # Time que mais finaliza/ataca no momento recebe mais peso.
        home_score_pressure += min(18.0, snap["home_shots"] * 1.2 + snap["home_sot"] * 2.0)
        away_score_pressure += min(18.0, snap["away_shots"] * 1.2 + snap["away_sot"] * 2.0)
        home_score_pressure += min(20.0, recent_home)
        away_score_pressure += min(20.0, recent_away)

        if snap["home_possession"] >= 58:
            home_score_pressure += 7
        if snap["away_possession"] >= 58:
            away_score_pressure += 7
        if home_score < away_score:
            home_score_pressure += 6
        elif away_score < home_score:
            away_score_pressure += 6

        # Ajuste pela força esperada de escanteios por time.
        home_score_pressure += max(-5.0, min(8.0, (expected_home - 4.5) * 2.2))
        away_score_pressure += max(-5.0, min(8.0, (expected_away - 4.0) * 2.2))

        best_side = "Mandante" if home_score_pressure >= away_score_pressure else "Visitante"
        best_team = match.get("home_team") if best_side == "Mandante" else match.get("away_team")
        score = max(home_score_pressure, away_score_pressure)
        score = max(5.0, min(95.0, score))

        if not match.get("stats"):
            score = min(score, 45.0)
            label = "SEM DADOS"
            probability = min(0.42, score / 100.0)
            reason = "Fonte ao vivo retornou placar/status, mas não retornou estatísticas de pressão."
        else:
            probability = max(0.10, min(0.88, score / 100.0))
            if score >= 70:
                label = "ALTA"
            elif score >= 55:
                label = "MEDIA"
            elif score >= 42:
                label = "BAIXA/MEDIA"
            else:
                label = "BAIXA"
            reason = (
                f"Ritmo projetado de escanteios: {corner_pace_90:.1f}/90min; "
                f"finalizações projetadas: {shot_pace_90:.1f}/90min."
            )

        return {
            "label": label,
            "score": score,
            "probability_next_10": probability,
            "best_team": best_team or "N/D",
            "best_side": best_side,
            "reason": reason,
            "corner_pace_90": corner_pace_90,
            "shot_pace_90": shot_pace_90,
            "expected_total_corners": expected_total,
            "home_pressure": home_score_pressure,
            "away_pressure": away_score_pressure,
            "snapshots": len(self.snapshots.get(event_id, [])),
        }

# ══════════════════════════════════════════════════════════════════════════════
#  DADOS DAS LIGAS
# ══════════════════════════════════════════════════════════════════════════════
SERIE_A_TEAMS = [
    "Palmeiras", "Flamengo", "Fluminense", "São Paulo", "Athletico Paranaense",
    "Bahia", "Coritiba", "Botafogo", "Red Bull Bragantino",
    "Vasco da Gama", "Grêmio", "Cruzeiro", "Vitória",
    "Corinthians", "Atlético Mineiro", "Internacional",
    "Santos", "Mirassol", "Remo", "Chapecoense",
]

SERIE_A_STANDINGS = [
    {"pos": 1, "team": "Palmeiras",            "pts": 32, "pj": 13, "v": 10, "e": 2, "d": 1, "gp": 23, "gc": 10, "sg": 13, "ca": 25, "cv": 2,  "ap": 82},
    {"pos": 2, "team": "Flamengo",             "pts": 26, "pj": 12, "v":  8, "e": 2, "d": 2, "gp": 24, "gc": 10, "sg": 14, "ca": 22, "cv": 1,  "ap": 72},
    {"pos": 3, "team": "Fluminense",           "pts": 26, "pj": 13, "v":  8, "e": 2, "d": 3, "gp": 23, "gc": 16, "sg":  7, "ca": 28, "cv": 2,  "ap": 67},
    {"pos": 4, "team": "São Paulo",            "pts": 23, "pj": 13, "v":  7, "e": 2, "d": 4, "gp": 17, "gc": 11, "sg":  6, "ca": 21, "cv": 1,  "ap": 59},
    {"pos": 5, "team": "Athletico Paranaense", "pts": 22, "pj": 13, "v":  7, "e": 1, "d": 5, "gp": 20, "gc": 15, "sg":  5, "ca": 30, "cv": 3,  "ap": 56},
    {"pos": 6, "team": "Bahia",               "pts": 21, "pj": 12, "v":  6, "e": 3, "d": 3, "gp": 17, "gc": 14, "sg":  3, "ca": 24, "cv": 2,  "ap": 58},
    {"pos": 7, "team": "Coritiba",        "pts": 19, "pj": 13, "v":  5, "e": 4, "d": 4, "gp": 15, "gc": 13, "sg":  2, "ca": 26, "cv": 1,  "ap": 49},
    {"pos": 8, "team": "Botafogo",            "pts": 17, "pj": 12, "v":  5, "e": 2, "d": 5, "gp": 24, "gc": 24, "sg":  0, "ca": 29, "cv": 3,  "ap": 47},
    {"pos": 9, "team": "Red Bull Bragantino", "pts": 17, "pj": 13, "v":  5, "e": 2, "d": 6, "gp": 15, "gc": 15, "sg":  0, "ca": 23, "cv": 1,  "ap": 44},
    {"pos":10, "team": "Vasco da Gama",   "pts": 16, "pj": 13, "v":  4, "e": 4, "d": 5, "gp": 18, "gc": 19, "sg": -1, "ca": 27, "cv": 2,  "ap": 41},
    {"pos":11, "team": "Grêmio",              "pts": 16, "pj": 13, "v":  4, "e": 4, "d": 5, "gp": 15, "gc": 16, "sg": -1, "ca": 25, "cv": 2,  "ap": 41},
    {"pos":12, "team": "Cruzeiro",            "pts": 16, "pj": 13, "v":  4, "e": 4, "d": 5, "gp": 17, "gc": 21, "sg": -4, "ca": 22, "cv": 1,  "ap": 41},
    {"pos":13, "team": "Vitória",             "pts": 15, "pj": 12, "v":  4, "e": 3, "d": 5, "gp": 12, "gc": 17, "sg": -5, "ca": 20, "cv": 1,  "ap": 42},
    {"pos":14, "team": "Corinthians",         "pts": 15, "pj": 13, "v":  3, "e": 6, "d": 4, "gp":  9, "gc": 11, "sg": -2, "ca": 18, "cv": 0,  "ap": 38},
    {"pos":15, "team": "Atlético Mineiro",    "pts": 14, "pj": 13, "v":  4, "e": 2, "d": 7, "gp": 14, "gc": 18, "sg": -4, "ca": 32, "cv": 3,  "ap": 36},
    {"pos":16, "team": "Internacional",       "pts": 13, "pj": 13, "v":  3, "e": 4, "d": 6, "gp": 12, "gc": 17, "sg": -5, "ca": 24, "cv": 2,  "ap": 33},
    {"pos":17, "team": "Santos",           "pts": 12, "pj": 13, "v":  3, "e": 3, "d": 7, "gp": 11, "gc": 18, "sg": -7, "ca": 21, "cv": 1,  "ap": 31},
    {"pos":18, "team": "Mirassol",            "pts": 11, "pj": 13, "v":  3, "e": 2, "d": 8, "gp":  9, "gc": 19, "sg":-10, "ca": 19, "cv": 1,  "ap": 28},
    {"pos":19, "team": "Remo",                "pts":  9, "pj": 13, "v":  2, "e": 3, "d": 8, "gp":  8, "gc": 20, "sg":-12, "ca": 23, "cv": 2,  "ap": 23},
    {"pos":20, "team": "Chapecoense",         "pts":  8, "pj": 13, "v":  2, "e": 2, "d": 9, "gp":  7, "gc": 20, "sg":-13, "ca": 17, "cv": 1,  "ap": 21},
]

SERIE_A_PAST = [
    {"date":"2026-04-17","home_team":"Palmeiras","away_team":"Coritiba","home_goals":2,"away_goals":0,"home_corners":7,"away_corners":4,"home_yellow_cards":1,"away_yellow_cards":2},
    {"date":"2026-04-17","home_team":"Flamengo","away_team":"Mirassol","home_goals":3,"away_goals":1,"home_corners":8,"away_corners":3,"home_yellow_cards":2,"away_yellow_cards":3},
    {"date":"2026-04-18","home_team":"Cruzeiro","away_team":"Bahia","home_goals":1,"away_goals":1,"home_corners":5,"away_corners":6,"home_yellow_cards":2,"away_yellow_cards":2},
    {"date":"2026-04-18","home_team":"Fluminense","away_team":"Remo","home_goals":2,"away_goals":0,"home_corners":9,"away_corners":3,"home_yellow_cards":1,"away_yellow_cards":3},
    {"date":"2026-04-18","home_team":"Botafogo","away_team":"Chapecoense","home_goals":1,"away_goals":0,"home_corners":6,"away_corners":4,"home_yellow_cards":3,"away_yellow_cards":2},
    {"date":"2026-04-19","home_team":"Atlético Mineiro","away_team":"São Paulo","home_goals":1,"away_goals":1,"home_corners":5,"away_corners":7,"home_yellow_cards":4,"away_yellow_cards":2},
    {"date":"2026-04-19","home_team":"Internacional","away_team":"Corinthians","home_goals":2,"away_goals":1,"home_corners":6,"away_corners":5,"home_yellow_cards":2,"away_yellow_cards":1},
    {"date":"2026-04-19","home_team":"Grêmio","away_team":"Vitória","home_goals":1,"away_goals":0,"home_corners":7,"away_corners":4,"home_yellow_cards":2,"away_yellow_cards":3},
    {"date":"2026-04-20","home_team":"Athletico Paranaense","away_team":"Santos","home_goals":2,"away_goals":1,"home_corners":8,"away_corners":5,"home_yellow_cards":3,"away_yellow_cards":2},
    {"date":"2026-04-20","home_team":"Red Bull Bragantino","away_team":"Vasco da Gama","home_goals":1,"away_goals":0,"home_corners":6,"away_corners":5,"home_yellow_cards":1,"away_yellow_cards":3},
]

SERIE_A_FUTURE = [
    {"date":"2026-04-27","time":"16:00","home_team":"Bahia","away_team":"Santos"},
    {"date":"2026-04-27","time":"18:30","home_team":"Botafogo","away_team":"Internacional"},
    {"date":"2026-04-27","time":"18:30","home_team":"Remo","away_team":"Cruzeiro"},
    {"date":"2026-04-27","time":"21:00","home_team":"São Paulo","away_team":"Mirassol"},
    {"date":"2026-04-28","time":"16:00","home_team":"Corinthians","away_team":"Vasco da Gama"},
    {"date":"2026-04-28","time":"16:00","home_team":"Grêmio","away_team":"Coritiba"},
    {"date":"2026-04-28","time":"18:30","home_team":"Athletico Paranaense","away_team":"Vitória"},
    {"date":"2026-04-28","time":"18:30","home_team":"Red Bull Bragantino","away_team":"Palmeiras"},
    {"date":"2026-04-28","time":"20:30","home_team":"Atlético Mineiro","away_team":"Flamengo"},
    {"date":"2026-04-28","time":"20:30","home_team":"Fluminense","away_team":"Chapecoense"},
]

SERIE_B_TEAMS = [
    "Sport", "Goiás", "América-MG", "Ceará", "Avaí", "Vila Nova",
    "CRB", "Athletic Club", "Novorizontino", "Operário-PR",
    "Paysandu", "Botafogo-SP", "Amazonas", "Volta Redonda",
    "Criciúma", "Ferroviária", "Atlético-GO", "Chapecoense",
    "Coritiba", "Remo"
]

SERIE_B_STANDINGS = [
    {"pos":1,"team":"Sport","pts":24,"pj":11,"v":7,"e":3,"d":1,"gp":18,"gc":7,"sg":11,"ca":15,"cv":1,"ap":72},
    {"pos":2,"team":"Goiás","pts":22,"pj":11,"v":6,"e":4,"d":1,"gp":15,"gc":8,"sg":7,"ca":18,"cv":0,"ap":66},
    {"pos":3,"team":"América-MG","pts":20,"pj":11,"v":6,"e":2,"d":3,"gp":16,"gc":11,"sg":5,"ca":20,"cv":1,"ap":60},
    {"pos":4,"team":"Ceará","pts":19,"pj":11,"v":5,"e":4,"d":2,"gp":14,"gc":10,"sg":4,"ca":17,"cv":0,"ap":57},
    {"pos":5,"team":"Avaí","pts":18,"pj":11,"v":5,"e":3,"d":3,"gp":12,"gc":10,"sg":2,"ca":16,"cv":1,"ap":54},
    {"pos":6,"team":"Vila Nova","pts":17,"pj":11,"v":5,"e":2,"d":4,"gp":11,"gc":10,"sg":1,"ca":19,"cv":1,"ap":51},
    {"pos":7,"team":"CRB","pts":17,"pj":11,"v":4,"e":5,"d":2,"gp":10,"gc":8,"sg":2,"ca":14,"cv":0,"ap":51},
    {"pos":8,"team":"Athletic Club","pts":15,"pj":11,"v":4,"e":3,"d":4,"gp":13,"gc":12,"sg":1,"ca":21,"cv":2,"ap":45},
    {"pos":9,"team":"Novorizontino","pts":14,"pj":11,"v":4,"e":2,"d":5,"gp":11,"gc":12,"sg":-1,"ca":16,"cv":1,"ap":42},
    {"pos":10,"team":"Operário-PR","pts":14,"pj":11,"v":3,"e":5,"d":3,"gp":9,"gc":9,"sg":0,"ca":13,"cv":0,"ap":42},
]

SERIE_B_PAST = [
    {"date":"2026-04-18","home_team":"Sport","away_team":"Botafogo-SP","home_goals":2,"away_goals":0,"home_corners":7,"away_corners":3,"home_yellow_cards":1,"away_yellow_cards":2},
    {"date":"2026-04-18","home_team":"Goiás","away_team":"Amazonas","home_goals":1,"away_goals":0,"home_corners":6,"away_corners":4,"home_yellow_cards":2,"away_yellow_cards":1},
    {"date":"2026-04-19","home_team":"América-MG","away_team":"Volta Redonda","home_goals":2,"away_goals":1,"home_corners":8,"away_corners":5,"home_yellow_cards":2,"away_yellow_cards":3},
    {"date":"2026-04-19","home_team":"Ceará","away_team":"Criciúma","home_goals":1,"away_goals":1,"home_corners":5,"away_corners":6,"home_yellow_cards":3,"away_yellow_cards":2},
    {"date":"2026-04-20","home_team":"Avaí","away_team":"Ferroviária","home_goals":2,"away_goals":0,"home_corners":7,"away_corners":3,"home_yellow_cards":1,"away_yellow_cards":2},
]

SERIE_B_FUTURE = [
    {"date":"2026-04-27","time":"16:00","home_team":"Sport","away_team":"Novorizontino"},
    {"date":"2026-04-27","time":"18:30","home_team":"Goiás","away_team":"Ceará"},
    {"date":"2026-04-28","time":"16:00","home_team":"América-MG","away_team":"CRB"},
    {"date":"2026-04-28","time":"18:30","home_team":"Avaí","away_team":"Athletic Club"},
]

PREMIER_TEAMS = [
    "Liverpool", "Arsenal", "Chelsea", "Manchester City", "Aston Villa",
    "Tottenham", "Manchester United", "Newcastle", "Brighton", "West Ham",
    "Brentford", "Fulham", "Crystal Palace", "Wolves", "Everton",
    "Nottingham Forest", "Bournemouth", "Leicester", "Ipswich", "Southampton",
]

PREMIER_STANDINGS = [
    {"pos":1,"team":"Liverpool","pts":76,"pj":32,"v":23,"e":7,"d":2,"gp":75,"gc":31,"sg":44,"ca":45,"cv":2,"ap":79},
    {"pos":2,"team":"Arsenal","pts":68,"pj":32,"v":20,"e":8,"d":4,"gp":65,"gc":30,"sg":35,"ca":52,"cv":3,"ap":71},
    {"pos":3,"team":"Chelsea","pts":62,"pj":32,"v":18,"e":8,"d":6,"gp":68,"gc":42,"sg":26,"ca":58,"cv":4,"ap":65},
    {"pos":4,"team":"Manchester City","pts":58,"pj":32,"v":17,"e":7,"d":8,"gp":60,"gc":45,"sg":15,"ca":48,"cv":2,"ap":60},
    {"pos":5,"team":"Aston Villa","pts":55,"pj":32,"v":16,"e":7,"d":9,"gp":62,"gc":50,"sg":12,"ca":44,"cv":3,"ap":57},
    {"pos":6,"team":"Tottenham","pts":52,"pj":32,"v":15,"e":7,"d":10,"gp":58,"gc":52,"sg":6,"ca":50,"cv":3,"ap":54},
    {"pos":7,"team":"Manchester United","pts":42,"pj":32,"v":11,"e":9,"d":12,"gp":38,"gc":50,"sg":-12,"ca":55,"cv":4,"ap":44},
    {"pos":8,"team":"Newcastle","pts":48,"pj":32,"v":14,"e":6,"d":12,"gp":50,"gc":45,"sg":5,"ca":46,"cv":2,"ap":50},
    {"pos":9,"team":"Brighton","pts":46,"pj":32,"v":13,"e":7,"d":12,"gp":55,"gc":52,"sg":3,"ca":42,"cv":1,"ap":48},
    {"pos":10,"team":"West Ham","pts":38,"pj":32,"v":10,"e":8,"d":14,"gp":42,"gc":55,"sg":-13,"ca":48,"cv":3,"ap":40},
]

PREMIER_PAST = [
    {"date":"2026-04-19","home_team":"Liverpool","away_team":"Arsenal","home_goals":2,"away_goals":1,"home_corners":6,"away_corners":8,"home_yellow_cards":2,"away_yellow_cards":3},
    {"date":"2026-04-19","home_team":"Arsenal","away_team":"Brighton","home_goals":2,"away_goals":0,"home_corners":9,"away_corners":5,"home_yellow_cards":1,"away_yellow_cards":2},
    {"date":"2026-04-20","home_team":"Manchester City","away_team":"Chelsea","home_goals":2,"away_goals":2,"home_corners":7,"away_corners":6,"home_yellow_cards":2,"away_yellow_cards":2},
    {"date":"2026-04-20","home_team":"Aston Villa","away_team":"Newcastle","home_goals":1,"away_goals":1,"home_corners":5,"away_corners":7,"home_yellow_cards":3,"away_yellow_cards":2},
]

PREMIER_FUTURE = [
    {"date":"2026-04-27","time":"16:00","home_team":"Liverpool","away_team":"Tottenham"},
    {"date":"2026-04-28","time":"16:00","home_team":"Arsenal","away_team":"Manchester United"},
    {"date":"2026-04-29","time":"16:00","home_team":"Manchester City","away_team":"Brighton"},
    {"date":"2026-04-30","time":"12:30","home_team":"Chelsea","away_team":"Aston Villa"},
]


# ══════════════════════════════════════════════════════════════════════════════
#  MODELO DE LIGA
# ══════════════════════════════════════════════════════════════════════════════
class League:
    def __init__(self, key, name, teams, standings=None, future_matches=None, past_matches=None,
                 avg_home_goals=None, avg_away_goals=None, source_note="snapshot"):
        self.key = key
        self.name = name
        self.teams = list(teams or [])
        self.standings = list(standings or [])
        self.future_matches = list(future_matches or [])
        self.past_matches = list(past_matches or [])
        self.avg_home_goals = avg_home_goals
        self.avg_away_goals = avg_away_goals
        self.source_note = source_note
        self.last_update = now_br()
        self.team_stats = {}
        # Estatísticas de temporada do SofaScore (cartões/escanteios reais)
        self.season_stats = {}
        self._build_stats()

    def _build_stats(self):
        if self.past_matches:
            self._build_stats_from_matches()
        else:
            self._build_stats_from_standings()

    def _build_stats_from_matches(self):
        ordered_matches = sorted(
            self.past_matches,
            key=lambda m: parse_iso_date(m.get("date", "")) or datetime.min
        )
        total_home_goals = sum(m.get("home_goals", 0) for m in ordered_matches)
        total_away_goals = sum(m.get("away_goals", 0) for m in ordered_matches)
        total_matches = len(ordered_matches)
        if total_matches <= 0:
            self._build_stats_from_standings()
            return
        base_home = total_home_goals / total_matches
        base_away = total_away_goals / total_matches
        if self.avg_home_goals is None:
            self.avg_home_goals = base_home
        if self.avg_away_goals is None:
            self.avg_away_goals = base_away
        self.avg_total_corners = getattr(self, "avg_total_corners", None) or self._safe_avg_total(
            ordered_matches, "home_corners", "away_corners", fallback=10.0)
        self.avg_home_corners = getattr(self, "avg_home_corners", None) or self._safe_avg_one_side(
            ordered_matches, "home_corners", fallback=5.3)
        self.avg_away_corners = getattr(self, "avg_away_corners", None) or self._safe_avg_one_side(
            ordered_matches, "away_corners", fallback=4.7)
        self.avg_total_cards = getattr(self, "avg_total_cards", None) or self._safe_avg_cards(
            ordered_matches, fallback=5.0)
        self.avg_home_cards = getattr(self, "avg_home_cards", None) or self._safe_avg_team_cards(
            ordered_matches, side="home", fallback=2.4)
        self.avg_away_cards = getattr(self, "avg_away_cards", None) or self._safe_avg_team_cards(
            ordered_matches, side="away", fallback=2.6)

        home_scored = defaultdict(float)
        home_conceded = defaultdict(float)
        away_scored = defaultdict(float)
        away_conceded = defaultdict(float)
        home_played = defaultdict(int)
        away_played = defaultdict(int)
        recent = defaultdict(list)

        for m in ordered_matches:
            h = m["home_team"]
            a = m["away_team"]
            hg = m.get("home_goals", 0)
            ag = m.get("away_goals", 0)
            hc = m.get("home_corners")
            ac = m.get("away_corners")
            hy = m.get("home_yellow_cards")
            ay = m.get("away_yellow_cards")
            hr = m.get("home_red_cards")
            ar = m.get("away_red_cards")
            home_scored[h] += hg
            home_conceded[h] += ag
            away_scored[a] += ag
            away_conceded[a] += hg
            home_played[h] += 1
            away_played[a] += 1
            recent[h].append({
                "date": m.get("date", ""), "gf": hg, "ga": ag, "is_home": True,
                "corners_for": hc, "corners_against": ac,
                "cards": self._cards_value(hy, hr),
                "opponent_cards": self._cards_value(ay, ar),
                "result": "W" if hg > ag else ("D" if hg == ag else "L"),
            })
            recent[a].append({
                "date": m.get("date", ""), "gf": ag, "ga": hg, "is_home": False,
                "corners_for": ac, "corners_against": hc,
                "cards": self._cards_value(ay, ar),
                "opponent_cards": self._cards_value(hy, hr),
                "result": "W" if ag > hg else ("D" if ag == hg else "L"),
            })

        stats = {}
        for team in self.teams:
            hp = home_played[team]
            ap = away_played[team]
            avg_home_scored = (home_scored[team] + self.avg_home_goals * 5) / (hp + 5)
            avg_home_conceded = (home_conceded[team] + self.avg_away_goals * 5) / (hp + 5)
            avg_away_scored = (away_scored[team] + self.avg_away_goals * 5) / (ap + 5)
            avg_away_conceded = (away_conceded[team] + self.avg_home_goals * 5) / (ap + 5)
            home_attack = avg_home_scored / max(self.avg_home_goals, 0.01)
            home_defense = avg_home_conceded / max(self.avg_away_goals, 0.01)
            away_attack = avg_away_scored / max(self.avg_away_goals, 0.01)
            away_defense = avg_away_conceded / max(self.avg_home_goals, 0.01)

            last8 = sorted(
                recent[team],
                key=lambda x: parse_iso_date(x.get("date", "")) or datetime.min
            )[-8:]

            wins = draws = losses = 0
            form_points = 0
            gf8 = ga8 = 0.0
            home_wins = home_losses = away_wins = away_losses = 0
            for g in last8:
                gf8 += g["gf"]
                ga8 += g["ga"]
                if g["gf"] > g["ga"]:
                    wins += 1
                    form_points += 3
                    if g["is_home"]:
                        home_wins += 1
                    else:
                        away_wins += 1
                elif g["gf"] == g["ga"]:
                    draws += 1
                    form_points += 1
                else:
                    losses += 1
                    if g["is_home"]:
                        home_losses += 1
                    else:
                        away_losses += 1

            form_ratio = form_points / max(len(last8) * 3, 1)
            form_factor = 0.88 + (form_ratio * 0.24)
            recent_goals_for = self._weighted_avg([g["gf"] for g in last8], fallback=(self.avg_home_goals + self.avg_away_goals) / 2)
            recent_goals_against = self._weighted_avg([g["ga"] for g in last8], fallback=(self.avg_home_goals + self.avg_away_goals) / 2)
            corners_for_values = [g["corners_for"] for g in last8 if g.get("corners_for") is not None]
            corners_against_values = [g["corners_against"] for g in last8 if g.get("corners_against") is not None]
            cards_values = [g["cards"] for g in last8 if g.get("cards") is not None]
            opponent_cards_values = [g["opponent_cards"] for g in last8 if g.get("opponent_cards") is not None]

            # Forma recente como string (ex: "WWDLW")
            form_str = "".join(g["result"] for g in last8[-5:])

            stats[team] = {
                "overall_played": hp + ap,
                "home_played": hp,
                "away_played": ap,
                "home_attack": self._regress_to_mean(home_attack),
                "home_defense": self._regress_to_mean(home_defense),
                "away_attack": self._regress_to_mean(away_attack),
                "away_defense": self._regress_to_mean(away_defense),
                "wins": wins, "draws": draws, "losses": losses,
                "home_wins": home_wins, "home_losses": home_losses,
                "away_wins": away_wins, "away_losses": away_losses,
                "form_factor": max(0.78, min(1.24, form_factor)),
                "form_str": form_str,
                "last8_count": len(last8),
                "last8_gf_avg": recent_goals_for,
                "last8_ga_avg": recent_goals_against,
                "last8_goal_balance": (gf8 - ga8) / max(len(last8), 1),
                "corners_for_avg": self._weighted_avg(corners_for_values, fallback=self.avg_total_corners / 2),
                "corners_against_avg": self._weighted_avg(corners_against_values, fallback=self.avg_total_corners / 2),
                "cards_avg": self._weighted_avg(cards_values, fallback=self.avg_total_cards / 2),
                "opponent_cards_avg": self._weighted_avg(opponent_cards_values, fallback=self.avg_total_cards / 2),
                "has_corner_data": len(corners_for_values) >= 3,
                "has_card_data": len(cards_values) >= 3,
                "recent_games": last8,
            }
        self.team_stats = stats

    @staticmethod
    def _cards_value(yellow, red):
        if yellow is None:
            if red is None or float(red or 0) == 0:
                return None
            return float(red or 0) * 2.0
        return float(yellow or 0) + (float(red or 0) * 2.0)

    @staticmethod
    def _weighted_avg(values, fallback=0.0):
        clean = [float(v) for v in values if v is not None]
        if not clean:
            return float(fallback)
        weights = list(range(1, len(clean) + 1))
        return sum(v * w for v, w in zip(clean, weights)) / max(sum(weights), 1)

    @staticmethod
    def _safe_avg_one_side(matches, field, fallback):
        values = [m.get(field) for m in matches if m.get(field) is not None]
        return sum(values) / len(values) if values else fallback

    @staticmethod
    def _safe_avg_total(matches, home_field, away_field, fallback):
        values = []
        for m in matches:
            h = m.get(home_field)
            a = m.get(away_field)
            if h is not None and a is not None:
                values.append(h + a)
        return sum(values) / len(values) if values else fallback

    @staticmethod
    def _safe_avg_cards(matches, fallback):
        values = []
        for m in matches:
            home = League._cards_value(m.get("home_yellow_cards"), m.get("home_red_cards"))
            away = League._cards_value(m.get("away_yellow_cards"), m.get("away_red_cards"))
            if home is not None and away is not None:
                values.append(home + away)
        return sum(values) / len(values) if values else fallback

    @staticmethod
    def _safe_avg_team_cards(matches, side, fallback):
        yfield = f"{side}_yellow_cards"
        rfield = f"{side}_red_cards"
        values = []
        for m in matches:
            value = League._cards_value(m.get(yfield), m.get(rfield))
            if value is not None:
                values.append(value)
        return sum(values) / len(values) if values else fallback

    @staticmethod
    def poisson(k, lam):
        if lam <= 0:
            return 1.0 if k == 0 else 0.0
        return (math.exp(-lam) * (lam ** k)) / math.factorial(k)

    @staticmethod
    def poisson_cdf(max_k, lam):
        return sum(League.poisson(k, lam) for k in range(0, max_k + 1))

    @staticmethod
    def poisson_over(line, lam):
        threshold = int(math.floor(line)) + 1
        return max(0.0, min(1.0, 1.0 - League.poisson_cdf(threshold - 1, lam)))

    @staticmethod
    def _clamp(value, low, high):
        return min(max(value, low), high)

    @staticmethod
    def _regress_to_mean(value, target=1.0, strength=0.80):
        return (value * strength) + (target * (1 - strength))

    def _build_stats_from_standings(self):
        if self.avg_home_goals is None:
            self.avg_home_goals = 1.35
        if self.avg_away_goals is None:
            self.avg_away_goals = 1.05
        stats = {}
        for row in self.standings:
            team = row["team"]
            pj = max(row.get("pj", 1), 1)
            gp = row.get("gp", 0)
            gc = row.get("gc", 0)
            sg = row.get("sg", gp - gc)
            pts = row.get("pts", 0)
            ca = row.get("ca", 0)
            attack_base = 1.0 + ((gp / pj) - 1.2) * 0.20
            defense_base = 1.0 + ((gc / pj) - 1.0) * 0.20
            form_factor = 0.90 + min(pts / (pj * 3), 1.0) * 0.20
            cards_per_game = ca / pj if pj > 0 else 2.5
            stats[team] = {
                "overall_played": pj,
                "home_played": max(1, pj // 2),
                "away_played": max(1, pj // 2),
                "home_attack": self._regress_to_mean(attack_base + (sg / pj) * 0.03),
                "home_defense": self._regress_to_mean(defense_base - (sg / pj) * 0.01),
                "away_attack": self._regress_to_mean(attack_base + (sg / pj) * 0.02),
                "away_defense": self._regress_to_mean(defense_base - (sg / pj) * 0.008),
                "wins": row.get("v", 0), "draws": row.get("e", 0), "losses": row.get("d", 0),
                "home_wins": 0, "home_losses": 0, "away_wins": 0, "away_losses": 0,
                "form_factor": max(0.80, min(1.20, form_factor)),
                "form_str": "",
                "last8_count": min(pj, 8),
                "last8_gf_avg": gp / pj,
                "last8_ga_avg": gc / pj,
                "last8_goal_balance": sg / pj,
                "corners_for_avg": 5.0,
                "corners_against_avg": 5.0,
                "cards_avg": cards_per_game,
                "opponent_cards_avg": 2.5,
                "has_corner_data": False,
                "has_card_data": False,
                "recent_games": [],
            }
        for team in self.teams:
            stats.setdefault(team, {
                "overall_played": 0, "home_played": 0, "away_played": 0,
                "home_attack": 1.0, "home_defense": 1.0, "away_attack": 1.0, "away_defense": 1.0,
                "wins": 0, "draws": 0, "losses": 0,
                "home_wins": 0, "home_losses": 0, "away_wins": 0, "away_losses": 0,
                "form_factor": 1.0, "form_str": "",
                "last8_count": 0, "last8_gf_avg": 1.2, "last8_ga_avg": 1.2,
                "last8_goal_balance": 0.0, "corners_for_avg": 5.0, "corners_against_avg": 5.0,
                "cards_avg": 2.5, "opponent_cards_avg": 2.5,
                "has_corner_data": False, "has_card_data": False, "recent_games": [],
            })
        self.team_stats = stats

    def confidence_level(self, home_team, away_team):
        hs = self.team_stats[home_team]
        aws = self.team_stats[away_team]
        min_games = min(hs.get("last8_count", hs["overall_played"]), aws.get("last8_count", aws["overall_played"]))
        if min_games >= 8 and hs.get("has_corner_data") and hs.get("has_card_data") and aws.get("has_corner_data") and aws.get("has_card_data"):
            return "Alta"
        if min_games >= 6:
            return "Média"
        if min_games >= 3:
            return "Baixa"
        return "Muito baixa"

    def predict_match(self, home_team, away_team):
        hs = self.team_stats[home_team]
        aws = self.team_stats[away_team]

        # ── Gols esperados ──────────────────────────────────────────────────
        base_lambda_home = self.avg_home_goals * hs["home_attack"] * aws["away_defense"]
        base_lambda_away = self.avg_away_goals * aws["away_attack"] * hs["home_defense"]
        recent_home_factor = self._clamp(
            ((hs["last8_gf_avg"] / max((self.avg_home_goals + self.avg_away_goals) / 2, 0.20)) * 0.65) +
            ((aws["last8_ga_avg"] / max((self.avg_home_goals + self.avg_away_goals) / 2, 0.20)) * 0.35),
            0.72, 1.35)
        recent_away_factor = self._clamp(
            ((aws["last8_gf_avg"] / max((self.avg_home_goals + self.avg_away_goals) / 2, 0.20)) * 0.65) +
            ((hs["last8_ga_avg"] / max((self.avg_home_goals + self.avg_away_goals) / 2, 0.20)) * 0.35),
            0.72, 1.35)
        lambda_home = self._clamp(base_lambda_home * hs["form_factor"] * recent_home_factor, 0.20, 4.80)
        lambda_away = self._clamp(base_lambda_away * aws["form_factor"] * recent_away_factor, 0.20, 4.80)

        p_home = p_draw = p_away = 0.0
        score_probs = []
        for hg in range(0, 8):
            for ag in range(0, 8):
                p = self.poisson(hg, lambda_home) * self.poisson(ag, lambda_away)
                score_probs.append(((hg, ag), p))
                if hg > ag:
                    p_home += p
                elif hg == ag:
                    p_draw += p
                else:
                    p_away += p
        total = p_home + p_draw + p_away or 1.0
        p_home /= total
        p_draw /= total
        p_away /= total
        score_probs.sort(key=lambda x: x[1], reverse=True)

        # ── Análise de vitória detalhada ────────────────────────────────────
        # Fator casa/fora: mandante tem vantagem histórica
        home_advantage = 1.0 + (0.08 if hs.get("home_wins", 0) > hs.get("home_losses", 0) else 0.0)
        away_disadvantage = 1.0 - (0.05 if aws.get("away_losses", 0) > aws.get("away_wins", 0) else 0.0)
        # Índice de força relativa
        home_strength = (hs["home_attack"] * (2.0 - aws["away_defense"])) * hs["form_factor"] * home_advantage
        away_strength = (aws["away_attack"] * (2.0 - hs["home_defense"])) * aws["form_factor"] * away_disadvantage
        total_strength = home_strength + away_strength + 0.001
        win_index_home = home_strength / total_strength
        win_index_away = away_strength / total_strength

        # Probabilidade de BTTS (ambas marcam)
        p_home_scores = 1.0 - self.poisson(0, lambda_home)
        p_away_scores = 1.0 - self.poisson(0, lambda_away)
        p_btts = p_home_scores * p_away_scores

        # Over/Under gols
        expected_total_goals = lambda_home + lambda_away
        p_over_1_5 = self.poisson_over(1.5, expected_total_goals)
        p_over_2_5 = self.poisson_over(2.5, expected_total_goals)
        p_over_3_5 = self.poisson_over(3.5, expected_total_goals)

        # ── Escanteios ──────────────────────────────────────────────────────
        # Usa dados de temporada se disponíveis, senão usa últimos 8 jogos
        h_season = self.season_stats.get(home_team, {})
        a_season = self.season_stats.get(away_team, {})

        h_corners_for = h_season.get("avg_corners_for_per_game") or hs["corners_for_avg"]
        h_corners_against = h_season.get("avg_corners_against_per_game") or hs["corners_against_avg"]
        a_corners_for = a_season.get("avg_corners_for_per_game") or aws["corners_for_avg"]
        a_corners_against = a_season.get("avg_corners_against_per_game") or aws["corners_against_avg"]

        expected_home_corners = (h_corners_for * 0.58) + (a_corners_against * 0.42)
        expected_away_corners = (a_corners_for * 0.58) + (h_corners_against * 0.42)
        expected_total_corners = self._clamp(expected_home_corners + expected_away_corners, 5.0, 17.0)

        corners = {
            "home_expected": expected_home_corners,
            "away_expected": expected_away_corners,
            "total_expected": expected_total_corners,
            "over_7_5": self.poisson_over(7.5, expected_total_corners),
            "over_8_5": self.poisson_over(8.5, expected_total_corners),
            "over_9_5": self.poisson_over(9.5, expected_total_corners),
            "over_10_5": self.poisson_over(10.5, expected_total_corners),
            "over_11_5": self.poisson_over(11.5, expected_total_corners),
            "home_over_3_5": self.poisson_over(3.5, self._clamp(expected_home_corners, 1.5, 10.0)),
            "home_over_4_5": self.poisson_over(4.5, self._clamp(expected_home_corners, 1.5, 10.0)),
            "home_over_5_5": self.poisson_over(5.5, self._clamp(expected_home_corners, 1.5, 10.0)),
            "away_over_2_5": self.poisson_over(2.5, self._clamp(expected_away_corners, 1.2, 9.0)),
            "away_over_3_5": self.poisson_over(3.5, self._clamp(expected_away_corners, 1.2, 9.0)),
            "away_over_4_5": self.poisson_over(4.5, self._clamp(expected_away_corners, 1.2, 9.0)),
            "has_data": bool(hs.get("has_corner_data") and aws.get("has_corner_data")),
            "has_season_data": bool(h_season and a_season),
        }

        # ── Cartões ─────────────────────────────────────────────────────────
        h_cards = h_season.get("avg_yellow_per_game") or hs["cards_avg"]
        a_cards = a_season.get("avg_yellow_per_game") or aws["cards_avg"]
        h_opp_cards = h_season.get("avg_yellow_per_game") or hs["opponent_cards_avg"]
        a_opp_cards = a_season.get("avg_yellow_per_game") or aws["opponent_cards_avg"]

        expected_home_cards = (h_cards * 0.62) + (a_opp_cards * 0.38)
        expected_away_cards = (a_cards * 0.62) + (h_opp_cards * 0.38)
        balance_factor = 1.0 + (0.08 if abs(p_home - p_away) < 0.12 else 0.0)
        expected_total_cards = self._clamp((expected_home_cards + expected_away_cards) * balance_factor, 1.5, 11.0)

        # Probabilidade de cartão vermelho (baseada em dados de temporada)
        h_red_rate = h_season.get("avg_red_per_game", 0.08)
        a_red_rate = a_season.get("avg_red_per_game", 0.08)
        p_any_red = 1.0 - (1.0 - h_red_rate) * (1.0 - a_red_rate)

        cards = {
            "home_expected": expected_home_cards,
            "away_expected": expected_away_cards,
            "total_expected": expected_total_cards,
            "over_2_5": self.poisson_over(2.5, expected_total_cards),
            "over_3_5": self.poisson_over(3.5, expected_total_cards),
            "over_4_5": self.poisson_over(4.5, expected_total_cards),
            "over_5_5": self.poisson_over(5.5, expected_total_cards),
            "over_6_5": self.poisson_over(6.5, expected_total_cards),
            "home_over_1_5": self.poisson_over(1.5, self._clamp(expected_home_cards, 0.5, 6.0)),
            "home_over_2_5": self.poisson_over(2.5, self._clamp(expected_home_cards, 0.5, 6.0)),
            "away_over_1_5": self.poisson_over(1.5, self._clamp(expected_away_cards, 0.5, 6.0)),
            "away_over_2_5": self.poisson_over(2.5, self._clamp(expected_away_cards, 0.5, 6.0)),
            "p_any_red": min(p_any_red, 0.99),
            "has_data": bool(hs.get("has_card_data") and aws.get("has_card_data")),
            "has_season_data": bool(h_season and a_season),
        }

        return {
            "lambda_home": lambda_home,
            "lambda_away": lambda_away,
            "p_home": p_home,
            "p_draw": p_draw,
            "p_away": p_away,
            "p_btts": p_btts,
            "p_over_1_5": p_over_1_5,
            "p_over_2_5": p_over_2_5,
            "p_over_3_5": p_over_3_5,
            "expected_total_goals": expected_total_goals,
            "win_index_home": win_index_home,
            "win_index_away": win_index_away,
            "top_scores": score_probs[:8],
            "corners": corners,
            "cards": cards,
            "home_last8": hs,
            "away_last8": aws,
        }

    def get_matches_range(self, start_offset_days, end_offset_days):
        today = datetime.now().date()
        start_day = today + timedelta(days=start_offset_days)
        end_day = today + timedelta(days=end_offset_days)
        filtered = []
        for m in self.future_matches:
            dt = parse_iso_date(m.get("date", ""))
            if dt and start_day <= dt.date() <= end_day:
                filtered.append(m)
        return filtered

    def get_matches_today(self):
        return self.get_matches_range(0, 0)


# ══════════════════════════════════════════════════════════════════════════════
#  GERENCIADORES
# ══════════════════════════════════════════════════════════════════════════════
class LeagueManager:
    def __init__(self):
        self.leagues = {}
        self.active_league_key = None

    def register_league(self, league):
        self.leagues[league.key] = league
        if self.active_league_key is None:
            self.active_league_key = league.key

    def get_active_league(self):
        return self.leagues.get(self.active_league_key)

    def switch_league(self, league_key):
        if league_key in self.leagues:
            self.active_league_key = league_key
            return True
        return False

    def list_leagues(self):
        return [(k, league.name) for k, league in self.leagues.items()]

    def update_league(self, league_key, new_standings=None, new_future_matches=None, new_past_matches=None):
        if league_key not in self.leagues:
            return False
        league = self.leagues[league_key]
        if new_standings is not None:
            league.standings = list(new_standings)
        if new_future_matches is not None:
            league.future_matches = list(new_future_matches)
        if new_past_matches is not None:
            league.past_matches = list(new_past_matches)
        league.last_update = now_br()
        league._build_stats()
        return True


# ══════════════════════════════════════════════════════════════════════════════
#  COPAS — SNAPSHOT LEVE PARA NÃO TRAVAR A INTERFACE
# ══════════════════════════════════════════════════════════════════════════════
def _make_cup_standings(teams):
    rows = []
    for i, team in enumerate(teams, start=1):
        rows.append({
            "pos": i, "team": team, "pts": 0, "pj": 0, "v": 0, "e": 0, "d": 0,
            "gp": 0, "gc": 0, "sg": 0, "ca": 0, "cv": 0, "ap": 0
        })
    return rows

COPA_DO_BRASIL_TEAMS = [
    "Flamengo", "Palmeiras", "Corinthians", "São Paulo", "Santos", "Fluminense",
    "Vasco da Gama", "Botafogo", "Atlético Mineiro", "Cruzeiro", "Grêmio",
    "Internacional", "Bahia", "Fortaleza", "Ceará", "Sport", "Athletico Paranaense",
    "Goiás", "Vitória", "Red Bull Bragantino"
]

COPA_DO_BRASIL_FUTURE = [
    {"date":"2026-04-29","time":"19:00","home_team":"Cruzeiro","away_team":"Vila Nova"},
    {"date":"2026-04-29","time":"21:30","home_team":"Flamengo","away_team":"Botafogo"},
    {"date":"2026-04-30","time":"19:00","home_team":"Palmeiras","away_team":"Ceará"},
    {"date":"2026-04-30","time":"21:30","home_team":"Atlético Mineiro","away_team":"Grêmio"},
]

COPA_DO_BRASIL_PAST = [
    {"date":"2026-04-10","home_team":"Flamengo","away_team":"Atlético Mineiro","home_goals":2,"away_goals":1,"home_corners":6,"away_corners":4,"home_yellow_cards":2,"away_yellow_cards":3,"home_red_cards":0,"away_red_cards":0},
    {"date":"2026-04-11","home_team":"Palmeiras","away_team":"Corinthians","home_goals":1,"away_goals":1,"home_corners":5,"away_corners":5,"home_yellow_cards":3,"away_yellow_cards":4,"home_red_cards":0,"away_red_cards":0},
    {"date":"2026-04-12","home_team":"Cruzeiro","away_team":"Bahia","home_goals":1,"away_goals":0,"home_corners":4,"away_corners":3,"home_yellow_cards":2,"away_yellow_cards":2,"home_red_cards":0,"away_red_cards":0},
]

LIBERTADORES_TEAMS = [
    "Flamengo", "Palmeiras", "São Paulo", "Botafogo", "Fluminense", "Atlético Mineiro",
    "River Plate", "Boca Juniors", "Racing", "Estudiantes", "Peñarol", "Nacional",
    "Colo-Colo", "Universidad de Chile", "Independiente del Valle", "LDU Quito",
    "Olimpia", "Cerro Porteño", "Atlético Nacional", "Millonarios"
]

LIBERTADORES_FUTURE = [
    {"date":"2026-04-29","time":"21:30","home_team":"Flamengo","away_team":"River Plate"},
    {"date":"2026-04-30","time":"19:00","home_team":"Palmeiras","away_team":"Boca Juniors"},
    {"date":"2026-05-01","time":"21:30","home_team":"São Paulo","away_team":"Peñarol"},
    {"date":"2026-05-02","time":"21:30","home_team":"Atlético Mineiro","away_team":"Olimpia"},
]

LIBERTADORES_PAST = [
    {"date":"2026-04-09","home_team":"Flamengo","away_team":"Peñarol","home_goals":2,"away_goals":0,"home_corners":7,"away_corners":3,"home_yellow_cards":2,"away_yellow_cards":4,"home_red_cards":0,"away_red_cards":0},
    {"date":"2026-04-10","home_team":"River Plate","away_team":"Palmeiras","home_goals":1,"away_goals":1,"home_corners":6,"away_corners":4,"home_yellow_cards":3,"away_yellow_cards":3,"home_red_cards":0,"away_red_cards":0},
    {"date":"2026-04-11","home_team":"Boca Juniors","away_team":"São Paulo","home_goals":1,"away_goals":0,"home_corners":5,"away_corners":4,"home_yellow_cards":4,"away_yellow_cards":3,"home_red_cards":0,"away_red_cards":0},
]


class LeagueFactory:
    @staticmethod
    def create_serie_a_2026():
        return League(
            key="serie_a_2026", name="Brasileirão Série A 2026",
            teams=SERIE_A_TEAMS, standings=SERIE_A_STANDINGS,
            future_matches=SERIE_A_FUTURE, past_matches=SERIE_A_PAST,
            avg_home_goals=1.45, avg_away_goals=1.10, source_note="snapshot Série A 2026")

    @staticmethod
    def create_serie_b_2026():
        return League(
            key="serie_b_2026", name="Brasileirão Série B 2026",
            teams=SERIE_B_TEAMS, standings=SERIE_B_STANDINGS,
            future_matches=SERIE_B_FUTURE, past_matches=SERIE_B_PAST,
            avg_home_goals=1.32, avg_away_goals=0.98, source_note="snapshot Série B 2026")

    @staticmethod
    def create_premier_league_2026():
        return League(
            key="premier_league_2026", name="Premier League 2025/26",
            teams=PREMIER_TEAMS, standings=PREMIER_STANDINGS,
            future_matches=PREMIER_FUTURE, past_matches=PREMIER_PAST,
            avg_home_goals=1.53, avg_away_goals=1.21, source_note="snapshot Premier League")

    @staticmethod
    def create_copa_do_brasil_2026():
        return League(
            key="copa_do_brasil_2026", name="Copa do Brasil 2026",
            teams=COPA_DO_BRASIL_TEAMS, standings=_make_cup_standings(COPA_DO_BRASIL_TEAMS),
            future_matches=COPA_DO_BRASIL_FUTURE, past_matches=COPA_DO_BRASIL_PAST,
            avg_home_goals=1.34, avg_away_goals=1.02, source_note="snapshot Copa do Brasil")

    @staticmethod
    def create_libertadores_2026():
        return League(
            key="libertadores_2026", name="Libertadores 2026",
            teams=LIBERTADORES_TEAMS, standings=_make_cup_standings(LIBERTADORES_TEAMS),
            future_matches=LIBERTADORES_FUTURE, past_matches=LIBERTADORES_PAST,
            avg_home_goals=1.40, avg_away_goals=0.95, source_note="snapshot Libertadores")



# ═══════════════════════════════════════════════════════════════════════
# APP WEB - Streamlit
# ═══════════════════════════════════════════════════════════════════════
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Analisador de Futebol Online", page_icon="⚽", layout="wide")

@st.cache_resource
def carregar_manager():
    manager = LeagueManager()
    for maker in [
        LeagueFactory.create_serie_a_2026,
        LeagueFactory.create_serie_b_2026,
        LeagueFactory.create_premier_league_2026,
        LeagueFactory.create_copa_do_brasil_2026,
        LeagueFactory.create_libertadores_2026,
    ]:
        manager.register_league(maker())
    return manager

def pct(x):
    try:
        return f"{float(x)*100:.1f}%"
    except Exception:
        return "-"

def num(x):
    try:
        return f"{float(x):.2f}"
    except Exception:
        return "-"

def df_matches(matches):
    return pd.DataFrame([{
        "Data": format_date_br(m.get("date", "")),
        "Hora": m.get("time", ""),
        "Mandante": m.get("home_team", ""),
        "Visitante": m.get("away_team", ""),
        "Fonte": m.get("source", "snapshot"),
    } for m in matches])

def df_standings(rows):
    return pd.DataFrame([{
        "#": r.get("pos", ""), "Time": r.get("team", ""), "Pts": r.get("pts", 0),
        "PJ": r.get("pj", 0), "V": r.get("v", 0), "E": r.get("e", 0), "D": r.get("d", 0),
        "GP": r.get("gp", 0), "GC": r.get("gc", 0), "SG": r.get("sg", 0), "Aprov.%": r.get("ap", 0),
    } for r in rows])

manager = carregar_manager()
league_options = {name: key for key, name in manager.list_leagues()}

st.title("⚽ Analisador de Futebol Online")
st.caption("Versão web da v72: abre pelo navegador e mantém análise de vitória, escanteios e cartões.")

with st.sidebar:
    st.header("Controles")
    league_name = st.selectbox("Campeonato", list(league_options.keys()))
    league_key = league_options[league_name]
    manager.switch_league(league_key)
    league = manager.get_active_league()
    st.caption(f"Base: {league.source_note}")
    st.caption(f"Atualizado: {league.last_update}")
    st.warning("Leitura estatística. Não é garantia de aposta.", icon="⚠️")

col1, col2, col3 = st.columns(3)
col1.metric("Média gols mandante", num(league.avg_home_goals))
col2.metric("Média gols visitante", num(league.avg_away_goals))
col3.metric("Times cadastrados", len(league.teams))

tab_analisar, tab_agenda, tab_tabela, tab_online = st.tabs(["🔎 Analisar partida", "📅 Próximos jogos", "📊 Tabela", "🌐 Online"])

with tab_analisar:
    c1, c2 = st.columns(2)
    with c1:
        home = st.selectbox("Mandante", league.teams, index=0, key=f"home_{league.key}")
    with c2:
        away_list = [t for t in league.teams if t != home]
        away = st.selectbox("Visitante", away_list, index=0, key=f"away_{league.key}")

    if st.button("Analisar partida", type="primary", use_container_width=True):
        pred = league.predict_match(home, away)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(f"Vitória {home}", pct(pred["p_home"]))
        m2.metric("Empate", pct(pred["p_draw"]))
        m3.metric(f"Vitória {away}", pct(pred["p_away"]))
        m4.metric("Ambas marcam", pct(pred["p_btts"]))

        st.subheader("Gols esperados")
        g1, g2, g3 = st.columns(3)
        g1.metric(home, num(pred["lambda_home"]))
        g2.metric(away, num(pred["lambda_away"]))
        g3.metric("Total esperado", num(pred["expected_total_goals"]))

        st.subheader("Escanteios")
        corners = pred["corners"]
        e1, e2, e3, e4 = st.columns(4)
        e1.metric(f"{home}", num(corners["home_expected"]))
        e2.metric(f"{away}", num(corners["away_expected"]))
        e3.metric("Total esperado", num(corners["total_expected"]))
        e4.metric("Over 9.5", pct(corners["over_9_5"]))
        st.dataframe(pd.DataFrame([
            {"Mercado":"Over 7.5", "Probabilidade": pct(corners["over_7_5"])},
            {"Mercado":"Over 8.5", "Probabilidade": pct(corners["over_8_5"])},
            {"Mercado":"Over 9.5", "Probabilidade": pct(corners["over_9_5"])},
            {"Mercado":"Over 10.5", "Probabilidade": pct(corners["over_10_5"])},
            {"Mercado":f"{home} Over 4.5", "Probabilidade": pct(corners["home_over_4_5"])},
            {"Mercado":f"{away} Over 3.5", "Probabilidade": pct(corners["away_over_3_5"])},
        ]), hide_index=True, use_container_width=True)

        st.subheader("Cartões")
        cards = pred["cards"]
        ca1, ca2, ca3, ca4 = st.columns(4)
        ca1.metric(f"{home}", num(cards["home_expected"]))
        ca2.metric(f"{away}", num(cards["away_expected"]))
        ca3.metric("Total esperado", num(cards["total_expected"]))
        ca4.metric("Over 4.5", pct(cards["over_4_5"]))
        st.dataframe(pd.DataFrame([
            {"Mercado":"Over 2.5", "Probabilidade": pct(cards["over_2_5"])},
            {"Mercado":"Over 3.5", "Probabilidade": pct(cards["over_3_5"])},
            {"Mercado":"Over 4.5", "Probabilidade": pct(cards["over_4_5"])},
            {"Mercado":"Over 5.5", "Probabilidade": pct(cards["over_5_5"])},
            {"Mercado":"Cartão vermelho", "Probabilidade": pct(cards["p_any_red"])},
        ]), hide_index=True, use_container_width=True)

        st.subheader("Placares mais prováveis")
        st.dataframe(pd.DataFrame([
            {"Placar": f"{hg} x {ag}", "Probabilidade": pct(p)}
            for (hg, ag), p in pred["top_scores"]
        ]), hide_index=True, use_container_width=True)

with tab_agenda:
    st.subheader("Próximos jogos cadastrados")
    df = df_matches(league.future_matches)
    if df.empty:
        st.info("Nenhum jogo cadastrado nesta base.")
    else:
        st.dataframe(df, hide_index=True, use_container_width=True)

with tab_tabela:
    st.subheader("Tabela")
    df = df_standings(league.standings)
    if df.empty:
        st.info("Tabela indisponível nesta base.")
    else:
        st.dataframe(df, hide_index=True, use_container_width=True)

with tab_online:
    st.subheader("Busca online")
    st.info("Esta versão tenta buscar agenda online por ESPN/TheSportsDB. Para dados realmente ao vivo, o ideal é conectar uma fonte permitida/API; raspagem pode ser bloqueada.")
    if st.button("Tentar atualizar agenda online", use_container_width=True):
        found = []
        logs = []
        for nome, client in [("ESPN", ESPNClient()), ("TheSportsDB", TheSportsDBClient())]:
            try:
                found = client.fetch_league_schedule(league.key, league.teams, days_ahead=14)
                logs.append(f"{nome}: {len(found)} jogo(s) encontrado(s).")
                if found:
                    break
            except Exception as exc:
                logs.append(f"{nome}: erro: {exc}")
        st.text("\n".join(logs))
        if found:
            st.dataframe(df_matches(found), hide_index=True, use_container_width=True)
        else:
            st.warning("Não encontrei jogos online agora. A base local continua funcionando.")
