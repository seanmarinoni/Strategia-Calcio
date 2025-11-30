import pandas as pd
import os
import requests
from . import config

def download_data():
    """
    Scarica SIA i campionati Europei (Stagionali) SIA quelli Extra (MLS, Brasile, ecc).
    """
    base_url_euro = "https://www.football-data.co.uk/mmz4281/"
    base_url_extra = "https://www.football-data.co.uk/new/"
    
    print("--- INIZIO DOWNLOAD DATI ---")
    
    # 1. DOWNLOAD EUROPA (Ciclo su Stagioni)
    print(">> Scarico Leghe Europee...")
    for league_name, league_code in config.LEAGUES.items():
        for season in config.SEASONS:
            url = f"{base_url_euro}{season}/{league_code}.csv"
            filename = f"{league_code}_{season}.csv"
            _download_file(url, filename, f"{league_name} ({season})")

    # 2. DOWNLOAD EXTRA (MLS, Brasile - Anno Solare)
    # Questi file su football-data si aggiornano sovrascrivendosi, contengono l'anno corrente
    print(">> Scarico Leghe Extra (USA, BRA, ecc)...")
    for league_name, league_code in config.EXTRA_LEAGUES.items():
        url = f"{base_url_extra}{league_code}.csv"
        # Aggiungiamo un suffisso per riconoscerli
        filename = f"{league_code}_current.csv" 
        _download_file(url, filename, league_name)

def _download_file(url, filename, label):
    """Funzione helper per scaricare un singolo file"""
    file_path = os.path.join(config.DATA_DIR, filename)
    try:
        response = requests.get(url, timeout=10) # Timeout per evitare blocchi
        if response.status_code == 200:
            with open(file_path, 'wb') as f:
                f.write(response.content)
            print(f"✅ OK: {label}")
        else:
            # Molti vecchi campionati minori potrebbero non esserci per tutte le stagioni
            pass 
    except Exception as e:
        print(f"❌ Errore {label}: {e}")

def load_all_data():
    """
    Carica Europa + Extra e unifica tutto.
    """
    all_files = [f for f in os.listdir(config.DATA_DIR) if f.endswith('.csv')]
    
    if not all_files:
        print("Dataset vuoto. Avvio download...")
        download_data()
        all_files = [f for f in os.listdir(config.DATA_DIR) if f.endswith('.csv')]

    df_list = []
    
    # Mappe per i nomi leggibili
    euro_map = {v: k for k, v in config.LEAGUES.items()}
    extra_map = {v: k for k, v in config.EXTRA_LEAGUES.items()}
    
    print(f"\n--- CARICAMENTO DATI ({len(all_files)} file) ---")
    
    for filename in all_files:
        file_path = os.path.join(config.DATA_DIR, filename)
        try:
            # Gestione encoding per file con caratteri strani (accenti brasiliani, ecc)
            df = pd.read_csv(file_path, encoding='latin1') 
            
            # Identificazione Lega
            code = filename.split('_')[0]
            if code in euro_map:
                league_name = euro_map[code]
            elif code in extra_map:
                league_name = extra_map[code]
            else:
                league_name = code # Fallback

            # Standardizzazione Colonne
            cols_to_use = {v: k for k, v in config.COL_MAPPING.items() if v in df.columns}
            df.rename(columns=cols_to_use, inplace=True)
            df = df[list(cols_to_use.values())]
            
            df['League'] = league_name
            
            # Gestione Stagione (per Extra mettiamo 'Current')
            if 'current' in filename:
                df['Season'] = 'Current'
            else:
                df['Season'] = filename.split('_')[1].replace('.csv', '')

            df_list.append(df)
            
        except Exception as e:
            # print(f"Skip {filename}: {e}") # Decommenta per debug
            pass

    if not df_list:
        return pd.DataFrame()

    full_df = pd.concat(df_list, ignore_index=True)
    
    # Pulizia
    full_df['Date'] = pd.to_datetime(full_df['Date'], dayfirst=True, errors='coerce')
    full_df.dropna(subset=['Date', 'home_goals', 'away_goals'], inplace=True)
    
    # Riempimento 0
    if 'home_red' in full_df.columns:
        full_df['home_red'] = full_df['home_red'].fillna(0)
        full_df['away_red'] = full_df['away_red'].fillna(0)
    
    full_df = full_df.sort_values('Date').reset_index(drop=True)
    
    print(f"✅ DATABASE PRONTO: {len(full_df)} partite caricate.")
    print(f"   Leghe incluse: {full_df['League'].unique()}")
    
    return full_df

if __name__ == "__main__":
    download_data()
    # df = load_all_data()