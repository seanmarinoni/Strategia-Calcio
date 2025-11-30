import os

# --- PERCORSI FILE ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data', 'raw')

os.makedirs(DATA_DIR, exist_ok=True)

# --- 1. CAMPIONATI EUROPEI STANDARD (Stagionali) ---
# Scaricati dalla cartella /mmz4281/{stagione}/
LEAGUES = {
    # INGHILTERRA
    'Premier League': 'E0',
    'Championship': 'E1',
    'League 1': 'E2',
    'League 2': 'E3',
    'Conference': 'EC',
    
    # ITALIA
    'Serie A': 'I1',
    'Serie B': 'I2',
    
    # GERMANIA
    'Bundesliga': 'D1',
    'Bundesliga 2': 'D2',
    
    # SPAGNA
    'La Liga': 'SP1',
    'La Liga 2': 'SP2',
    
    # FRANCIA
    'Ligue 1': 'F1',
    'Ligue 2': 'F2',
    
    # ALTRI
    'Eredivisie (Olanda)': 'N1',
    'Jupiler League (Belgio)': 'B1',
    'Liga Portugal': 'P1',
    'Super Lig (Turchia)': 'T1',
    'Super League (Grecia)': 'G1',
    'Scotland Premier': 'SC0'
}

# --- 2. CAMPIONATI EXTRA (Anno Solare / Cartella "new") ---
# Questi file contengono solitamente la stagione corrente/recente
EXTRA_LEAGUES = {
    'MLS (USA)': 'USA',
    'Brasile Serie A': 'BRA', # Già che ci siamo, metto anche il Brasile
    'Argentina': 'ARG',       # E l'Argentina
    'Giappone': 'JPN'
}

# Stagioni Europee da analizzare
SEASONS = ['2122', '2223', '2324', '2425', '2526' ] 

# --- MAPPING COLONNE ---
COL_MAPPING = {
    'Date': 'Date',
    'HomeTeam': 'HomeTeam',
    'AwayTeam': 'AwayTeam',
    'home_goals': 'FTHG',
    'away_goals': 'FTAG',
    'result': 'FTR',
    'home_shots': 'HS',
    'away_shots': 'AS',
    'home_shots_target': 'HST', 
    'away_shots_target': 'AST',
    'home_corners': 'HC', 
    'away_corners': 'AC',
    'home_red': 'HR',
    'away_red': 'AR',
    'odds_1': 'B365H',
    'odds_X': 'B365D',
    'odds_2': 'B365A',
    'odds_over25': 'B365>2.5',
    'odds_under25': 'B365<2.5'
}

MIN_GAMES_PLAYED = 5