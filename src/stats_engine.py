import pandas as pd
import numpy as np
from scipy.stats import poisson
import datetime

# --- CONFIGURAZIONE COSTANTI ---
RHO = -0.13             # Correzione Dixon-Coles
N_GAMES_TEAM = 10       # Numero partite analisi Team
N_GAMES_LEAGUE = 380    # Finestra mobile Lega (Rolling Season)

def calculate_match_prediction(
    full_df: pd.DataFrame, 
    date_match: str, 
    home_team: str, 
    away_team: str,
    delta_att_home: float = 1.00,
    delta_def_home: float = 1.00,
    delta_att_away: float = 1.00,
    delta_def_away: float = 1.00
):
    """
    Funzione Principale (Orchestrator).
    Prende i dati, la data e i delta manuali. Restituisce un dizionario con l'analisi completa.
    """
    
    # 1. TIME TRAVEL: Taglio del Database (IL MURO)
    # Convertiamo la data e filtriamo STRETTAMENTE minore (<)
    target_dt = pd.to_datetime(date_match)
    df_past = full_df[full_df['Date'] < target_dt].copy()
    df_past = df_past.sort_values('Date').reset_index(drop=True)

    if df_past.empty:
        return {"error": "Nessun dato storico trovato prima della data selezionata."}

    # -------------------------------------------------------------------------
    # 2. CALIBRAZIONE LEGA (L'ANCORA)
    # -------------------------------------------------------------------------
    # Prendiamo le ultime 380 partite (o meno se non ce ne sono abbastanza)
    df_league = df_past.tail(N_GAMES_LEAGUE).copy()
    
    # Calcolo colonne derivate per la Lega (Tiri Fuori = Totali - Porta)
    df_league['Home_Shots_Off'] = df_league['home_shots'] - df_league['home_shots_target']
    df_league['Away_Shots_Off'] = df_league['away_shots'] - df_league['away_shots_target']

    # Medie Globali (Home + Away insieme per i coefficienti puri)
    avg_goals_global = (df_league['home_goals'].mean() + df_league['away_goals'].mean()) / 2
    avg_hst_global   = (df_league['home_shots_target'].mean() + df_league['away_shots_target'].mean()) / 2
    
    # Calcolo Coefficienti b, c, d
    # b = Tot Gol / Tot Tiri Porta (approssimato usando le medie)
    coef_b = avg_goals_global / avg_hst_global if avg_hst_global > 0 else 0
    coef_c = coef_b / 5.0
    coef_d = coef_b / 8.0

    # Funzione helper per calcolare il valore Sintetico Ibrido
    def calc_anchor_components(mean_goals, mean_hst, mean_hsoff, mean_corners):
        syn_val = (mean_hst * coef_b) + (mean_hsoff * coef_c) + (mean_corners * coef_d)
        # Fusione Ibrida: 60% Reale + 40% Sintetico
        anchor_val = (mean_goals * 0.60) + (syn_val * 0.40)
        return anchor_val

    # --- ANCORA HOME ---
    avg_g_h = df_league['home_goals'].mean()
    avg_hst_h = df_league['home_shots_target'].mean()
    avg_off_h = df_league['Home_Shots_Off'].mean()
    avg_cnr_h = df_league['home_corners'].mean()
    anchor_home = calc_anchor_components(avg_g_h, avg_hst_h, avg_off_h, avg_cnr_h)

    # --- ANCORA AWAY ---
    avg_g_a = df_league['away_goals'].mean()
    avg_hst_a = df_league['away_shots_target'].mean()
    avg_off_a = df_league['Away_Shots_Off'].mean()
    avg_cnr_a = df_league['away_corners'].mean()
    anchor_away = calc_anchor_components(avg_g_a, avg_hst_a, avg_off_a, avg_cnr_a)

    # --- ANCORA STANDARD (Denominatore Universale) ---
    # Global Anchor = media tra Home e Away Anchor pesata sui volumi, 
    # ma la formula semplice richiesta è (Anchor_Global / 2) o media delle due ancore.
    # Calcoliamo l'Ancora Globale sui dati aggregati e dividiamo per 2 come da specifica
    anchor_global_val = (anchor_home + anchor_away) # Somma dei potenziali
    # Nota: Nelle specifiche "Ancora_Team_Standard = Ancora_Global / 2".
    # Dove Ancora_Global è calcolata su tutti i match. 
    # Per coerenza matematica usiamo la media delle due ancore calcolate sopra.
    anchor_team_standard = (anchor_home + anchor_away) / 2.0

    # -------------------------------------------------------------------------
    # 3. ANALISI SQUADRE (I CONTENDENTI)
    # -------------------------------------------------------------------------
    
    # Analisi Home Team
    home_stats = _analyze_team(df_past, home_team, coef_b, coef_c, coef_d)
    if home_stats is None: return {"error": f"Dati insufficienti per {home_team}"}
    
    # Analisi Away Team
    away_stats = _analyze_team(df_past, away_team, coef_b, coef_c, coef_d)
    if away_stats is None: return {"error": f"Dati insufficienti per {away_team}"}

    # -------------------------------------------------------------------------
    # 4. APPLICAZIONE DELTA E CALCOLO xG
    # -------------------------------------------------------------------------
    
    # Applicazione Delta Manuali (News)
    att_home_adj = home_stats['attacco_raw'] * delta_att_home
    def_home_adj = home_stats['difesa_raw'] * delta_def_home # Permeabilità
    
    att_away_adj = away_stats['attacco_raw'] * delta_att_away
    def_away_adj = away_stats['difesa_raw'] * delta_def_away # Permeabilità

    # FORMULA INCROCIO xG (Rapporti Normalizzati)
    # xG_Home = (Att_H_Adj / Std) * (Def_A_Adj / Std) * Anchor_Home
    xg_home = (att_home_adj / anchor_team_standard) * (def_away_adj / anchor_team_standard) * anchor_home
    
    # xG_Away = (Att_A_Adj / Std) * (Def_H_Adj / Std) * Anchor_Away
    xg_away = (att_away_adj / anchor_team_standard) * (def_home_adj / anchor_team_standard) * anchor_away

    # -------------------------------------------------------------------------
    # 5. POISSON & DIXON-COLES (Probabilità e Quote)
    # -------------------------------------------------------------------------
    probs_data = _calculate_probabilities_dixon_coles(xg_home, xg_away)

    # -------------------------------------------------------------------------
    # 6. OUTPUT FINALE
    # -------------------------------------------------------------------------
    return {
        "match_info": {
            "date": date_match,
            "home": home_team,
            "away": away_team
        },
        "league_params": {
            "games_analyzed": len(df_league),
            "coef_b": round(coef_b, 4),
            "coef_c": round(coef_c, 4),
            "coef_d": round(coef_d, 4),
            "anchor_home": round(anchor_home, 3),
            "anchor_away": round(anchor_away, 3),
            "anchor_std": round(anchor_team_standard, 3)
        },
        "team_stats": {
            "home_raw_att": round(home_stats['attacco_raw'], 3),
            "home_raw_def": round(home_stats['difesa_raw'], 3),
            "away_raw_att": round(away_stats['attacco_raw'], 3),
            "away_raw_def": round(away_stats['difesa_raw'], 3),
            "home_red_cards": home_stats['red_cards_count'],
            "away_red_cards": away_stats['red_cards_count']
        },
        "xg_prediction": {
            "xg_home": round(xg_home, 4),
            "xg_away": round(xg_away, 4)
        },
        "odds": probs_data['odds'],
        "probabilities": probs_data['probs_pct'],
        "exact_score_top5": probs_data['top_5_scores']
    }

def _analyze_team(df_hist, team_name, b, c, d):
    """
    Analizza le ultime N10 partite della squadra (Casa+Trasferta).
    Applica Time Decay e Filtro Cartellino Rosso.
    """
    # Filtra partite dove la squadra gioca
    mask = (df_hist['HomeTeam'] == team_name) | (df_hist['AwayTeam'] == team_name)
    team_games = df_hist[mask].copy()
    
    # Ordina e prendi le ultime 10
    team_games = team_games.sort_values('Date').tail(N_GAMES_TEAM)
    
    if len(team_games) < 5: # Minimo partite per avere un dato sensato
        return None

    # Creiamo liste per i valori normalizzati
    stats = {
        'goals_for': [], 'hst_for': [], 'off_for': [], 'corn_for': [],
        'goals_ag': [], 'hst_ag': [], 'off_ag': [], 'corn_ag': [],
        'weights': []
    }
    
    red_cards_count = 0

    # Iteriamo per normalizzare (Home vs Away perspective) e calcolare pesi
    # Usiamo enumerate per il Time Decay (i=0 è la più vecchia, i=9 la più recente)
    # Generiamo pesi esponenziali: da circa 0.6 a 1.0
    time_weights = np.exp(np.linspace(-0.5, 0, len(team_games))) 
    
    for i, (_, row) in enumerate(team_games.iterrows()):
        is_home = (row['HomeTeam'] == team_name)
        
        # 1. Rilevazione Red Cards (Rumore)
        # Se c'è un rosso (per chiunque), la partita è "inquinata" -> Peso dimezzato
        has_red = (row['home_red'] > 0) or (row['away_red'] > 0)
        base_weight = time_weights[i]
        
        if has_red:
            final_weight = base_weight * 0.5
            red_cards_count += 1
        else:
            final_weight = base_weight
            
        stats['weights'].append(final_weight)
        
        # 2. Estrazione Statistiche (Attacco e Difesa)
        if is_home:
            # Attacco (Fatti)
            stats['goals_for'].append(row['home_goals'])
            stats['hst_for'].append(row['home_shots_target'])
            stats['off_for'].append(row['home_shots'] - row['home_shots_target'])
            stats['corn_for'].append(row['home_corners'])
            # Difesa (Subiti)
            stats['goals_ag'].append(row['away_goals'])
            stats['hst_ag'].append(row['away_shots_target'])
            stats['off_ag'].append(row['away_shots'] - row['away_shots_target'])
            stats['corn_ag'].append(row['away_corners'])
        else:
            # Squadra è Away -> Invertiamo
            # Attacco (Fatti)
            stats['goals_for'].append(row['away_goals'])
            stats['hst_for'].append(row['away_shots_target'])
            stats['off_for'].append(row['away_shots'] - row['away_shots_target'])
            stats['corn_for'].append(row['away_corners'])
            # Difesa (Subiti)
            stats['goals_ag'].append(row['home_goals'])
            stats['hst_ag'].append(row['home_shots_target'])
            stats['off_ag'].append(row['home_shots'] - row['home_shots_target'])
            stats['corn_ag'].append(row['home_corners'])

    # 3. Calcolo Medie Pesate
    # Funzione helper interna
    def w_avg(values, weights):
        return np.average(values, weights=weights)

    w = stats['weights']
    
    # ATTACCO RAW
    avg_gf = w_avg(stats['goals_for'], w)
    syn_att = (w_avg(stats['hst_for'], w) * b) + \
              (w_avg(stats['off_for'], w) * c) + \
              (w_avg(stats['corn_for'], w) * d)
    
    attacco_raw = (avg_gf * 0.60) + (syn_att * 0.40)
    
    # DIFESA RAW (Permeabilità)
    avg_ga = w_avg(stats['goals_ag'], w)
    syn_def = (w_avg(stats['hst_ag'], w) * b) + \
              (w_avg(stats['off_ag'], w) * c) + \
              (w_avg(stats['corn_ag'], w) * d)
              
    difesa_raw = (avg_ga * 0.60) + (syn_def * 0.40)
    
    return {
        'attacco_raw': attacco_raw,
        'difesa_raw': difesa_raw,
        'red_cards_count': red_cards_count
    }

def _calculate_probabilities_dixon_coles(lamb, mu):
    """
    Genera probabilità e quote usando Poisson + Correzione Dixon-Coles
    """
    max_goals = 10
    matrix = np.zeros((max_goals, max_goals))
    
    # 1. Matrice Base (Indipendente)
    for x in range(max_goals):     # Home Goals
        for y in range(max_goals): # Away Goals
            prob = poisson.pmf(x, lamb) * poisson.pmf(y, mu)
            matrix[x, y] = prob

    # 2. Correzione Dixon-Coles
    # Modifica solo 0-0, 0-1, 1-0, 1-1
    # Rho = -0.13 (costante globale)
    
    # Helper per calcolo correzione
    def correction_factor(x, y):
        if x == 0 and y == 0:
            return 1 - (lamb * mu * RHO)
        elif x == 0 and y == 1:
            return 1 + (lamb * RHO)
        elif x == 1 and y == 0:
            return 1 + (mu * RHO)
        elif x == 1 and y == 1:
            return 1 - RHO
        else:
            return 1.0

    # Applichiamo correzione
    for x in [0, 1]:
        for y in [0, 1]:
            factor = correction_factor(x, y)
            # Safety Check: max(0, ...) per evitare probabilità negative su xG alti
            matrix[x, y] = matrix[x, y] * max(0, factor)

    # 3. Normalizzazione (Re-Balancing)
    # La somma non è più 1.000, quindi dividiamo tutto per la nuova somma
    total_prob = np.sum(matrix)
    matrix = matrix / total_prob
    
    # 4. Aggregazione Risultati
    prob_home = np.sum(np.tril(matrix, -1)) # Triangolo inferiore (x > y)
    prob_draw = np.sum(np.diag(matrix))     # Diagonale (x == y)
    prob_away = np.sum(np.triu(matrix, 1))  # Triangolo superiore (y > x)
    
    # Goal / NoGoal
    prob_ng = matrix[0,0] + np.sum(matrix[0, 1:]) + np.sum(matrix[1:, 0]) # Uno dei due a 0
    prob_gg = 1 - prob_ng
    
    # Over / Under 2.5
    # Somma celle dove (x+y) < 2.5 (0-0, 1-0, 0-1, 1-1, 2-0, 0-2)
    mask_under = np.fromfunction(lambda i, j: (i + j) < 2.5, (max_goals, max_goals), dtype=int)
    prob_under = np.sum(matrix * mask_under)
    prob_over = 1 - prob_under

    # 5. Quote Decimali (Fair Odds)
    def to_odd(p): return round(1/p, 2) if p > 0.001 else 999.00

    odds = {
        '1': to_odd(prob_home),
        'X': to_odd(prob_draw),
        '2': to_odd(prob_away),
        'Gol': to_odd(prob_gg),
        'NoGol': to_odd(prob_ng),
        'Over2.5': to_odd(prob_over),
        'Under2.5': to_odd(prob_under)
    }

    probabilities = {
        '1': round(prob_home * 100, 1),
        'X': round(prob_draw * 100, 1),
        '2': round(prob_away * 100, 1),
        'Gol': round(prob_gg * 100, 1),
        'NoGol': round(prob_ng * 100, 1),
        'Over2.5': round(prob_over * 100, 1),
        'Under2.5': round(prob_under * 100, 1)
    }
    
    # 6. Top 5 Risultati Esatti
    scores_list = []
    for x in range(max_goals):
        for y in range(max_goals):
            scores_list.append({
                'score': f"{x}-{y}",
                'prob': matrix[x, y]
            })
    
    # Ordina per probabilità decrescente
    scores_list.sort(key=lambda k: k['prob'], reverse=True)
    top_5 = scores_list[:5]
    for s in top_5:
        s['prob'] = round(s['prob'] * 100, 1) # Converti in %

    return {
        'odds': odds,
        'probs_pct': probabilities,
        'top_5_scores': top_5
    }