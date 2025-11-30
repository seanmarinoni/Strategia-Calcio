import requests
import json
import os
import pandas as pd
from datetime import datetime, timedelta

# Percorsi
# --- CODICE AGGIORNATO PER I PERCORSI ---
import os

# Determina la cartella dove si trova QUESTO file (cioè src/)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR) # La cartella superiore (progetto)

# Percorsi corretti
DATA_DIR = os.path.join(BASE_DIR, 'data')
CACHE_DIR = os.path.join(DATA_DIR, 'cache')

# ORA CERCA LA CHIAVE NELLA CARTELLA CORRENTE (src)
KEY_FILE = os.path.join(CURRENT_DIR, 'api_key.txt') 

# Crea cartella cache se non esiste
os.makedirs(CACHE_DIR, exist_ok=True)

# Crea cartella cache se non esiste
os.makedirs(CACHE_DIR, exist_ok=True)

# MAPPING: Nome tuo progetto -> ID API-Football (v3)
# ID presi da https://dashboard.api-football.com/
LEAGUE_MAP = {
    'Serie A': 135,
    'Serie B': 136,
    'Premier League': 39,
    'Bundesliga': 78,
    'Bundesliga 2': 79,
    'La Liga': 140,
    'La Liga 2': 141,
    'Ligue 1': 61,
    'Ligue 2': 62,
    'Eredivisie (Olanda)': 88,
    'Liga Portugal': 94,
    'Brasile Serie A': 71,
    'Jupiler League (Belgio)': 144,
    'Super Lig (Turchia)': 203,
    'Super League (Grecia)': 197
}

class FootballAPI:
    def __init__(self):
        self.api_key = self._load_key()
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {
            'x-rapidapi-host': "v3.football.api-sports.io",
            'x-rapidapi-key': self.api_key
        }

    def _load_key(self):
        try:
            with open(KEY_FILE, 'r') as f:
                key = f.read().strip()
                if len(key) < 10:
                    print("⚠️ ATTENZIONE: Chiave API sembra troppo corta o vuota.")
                return key
        except FileNotFoundError:
            print("❌ ERRORE CRITICO: File 'api_key.txt' non trovato in /data/")
            return ""

    def get_fixtures(self, league_name, season_code):
        """
        Scarica (o recupera da cache) TUTTO il calendario (Passato + Futuro)
        Costo: 1 Chiamata API al giorno per Lega.
        """
        if league_name not in LEAGUE_MAP:
            print(f"⚠️ Lega '{league_name}' non mappata in api_football.py")
            return []

        league_id = LEAGUE_MAP[league_name]
        
        # Conversione Stagione: '2526' -> 2025
        try:
            season_year = int("20" + season_code[:2])
        except:
            print(f"⚠️ Formato stagione errato: {season_code}, uso 2025 default")
            season_year = 2025

        # --- GESTIONE CACHE ---
        # Nome file cache: fixtures_135_2025.json
        cache_file = os.path.join(CACHE_DIR, f"fixtures_{league_id}_{season_year}.json")
        
        # Controllo se file esiste ed è recente (< 24 ore)
        if os.path.exists(cache_file):
            file_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
            if datetime.now() - file_time < timedelta(hours=24):
                # print(f"💾 Uso Cache locale per {league_name}") # Decommenta per debug
                with open(cache_file, 'r') as f:
                    return json.load(f)
        
        # --- CHIAMATA API (Se cache manca o vecchia) ---
        print(f"📡 Chiamata API per {league_name} ({season_year})... (-1 Credito)")
        
        url = f"{self.base_url}/fixtures"
        # Scarichiamo TUTTO per quella stagione (Past & Future)
        querystring = {"league": str(league_id), "season": str(season_year)}

        try:
            response = requests.get(url, headers=self.headers, params=querystring)
            data = response.json()
            
            # Gestione errori API
            if 'errors' in data and data['errors']:
                print(f"❌ Errore API: {data['errors']}")
                return []
            
            if 'response' not in data:
                print("⚠️ Risposta vuota dall'API")
                return []

            # PARSING DEI DATI
            clean_matches = []
            for item in data['response']:
                fixture = item['fixture']
                teams = item['teams']
                goals = item['goals']
                league_info = item['league']
                
                # short status: FT (Finito), NS (Not Started), PST (Postponed)
                status = fixture['status']['short']
                match_date_str = fixture['date'].split('T')[0] # YYYY-MM-DD
                
                match_info = {
                    'id': fixture['id'],
                    'date': match_date_str,
                    'home': teams['home']['name'],
                    'away': teams['away']['name'],
                    'status': status,
                    'home_goals': goals['home'],
                    'away_goals': goals['away'],
                    'round': league_info['round']
                }

                # Creazione Etichetta per Menu a Tendina
                if status in ['FT', 'AET', 'PEN']:
                    label = f"✅ {match_date_str} | {match_info['home']} {goals['home']}-{goals['away']} {match_info['away']}"
                    match_info['type'] = 'PAST'
                elif status in ['NS', 'TBD']:
                    label = f"📅 {match_date_str} | {match_info['home']} vs {match_info['away']}"
                    match_info['type'] = 'FUTURE'
                else:
                    # Live o Rinviata
                    label = f"⏱️ {match_date_str} ({status}) | {match_info['home']} vs {match_info['away']}"
                    match_info['type'] = 'FUTURE'

                match_info['label'] = label
                clean_matches.append(match_info)

            # Ordiniamo per data decrescente (i più recenti/futuri in alto) o crescente?
            # Meglio crescente (dal passato al futuro)
            clean_matches.sort(key=lambda x: x['date'])

            # SALVATAGGIO CACHE
            with open(cache_file, 'w') as f:
                json.dump(clean_matches, f)
            
            return clean_matches

        except Exception as e:
            print(f"❌ Eccezione API durante download: {e}")
            return []

    def get_match_odds(self, fixture_id):
        """
        Scarica le quote SOLO per un match specifico futuro.
        Costo: 1 Chiamata API.
        Da chiamare solo quando l'utente clicca 'Calcola'.
        """
        print(f"📡 Scarico quote live per match {fixture_id}... (-1 Credito)")
        url = f"{self.base_url}/odds"
        querystring = {"fixture": str(fixture_id)}
        
        try:
            response = requests.get(url, headers=self.headers, params=querystring)
            data = response.json()
            
            if not data['response']:
                print("⚠️ Nessuna quota disponibile per questo match.")
                return None
            
            # Cerchiamo un bookmaker affidabile (es. Bet365 id=1, o il primo disponibile)
            bookmakers = data['response'][0]['bookmakers']
            if not bookmakers: return None
            
            # Prendiamo il primo bookmaker (spesso è Bet365 o Unibet)
            bets = bookmakers[0]['bets']
            
            odds_dict = {}
            
            # Cerchiamo 'Match Winner' (id=1 di solito)
            for bet in bets:
                if bet['name'] == 'Match Winner':
                    for val in bet['values']:
                        if val['value'] == 'Home': odds_dict['1'] = float(val['odd'])
                        if val['value'] == 'Draw': odds_dict['X'] = float(val['odd'])
                        if val['value'] == 'Away': odds_dict['2'] = float(val['odd'])
            
            return odds_dict

        except Exception as e:
            print(f"❌ Errore scaricamento quote: {e}")
            return None