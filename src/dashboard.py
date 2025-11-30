import ipywidgets as widgets
from IPython.display import display, HTML, clear_output
import pandas as pd
from . import stats_engine

# --- DIZIONARIO DELTA NEWS ---
# Mappa le etichette ai valori (Attacco, Difesa)
# Ricorda: Attacco > 1 (Bonus), Difesa > 1 (Malus/Danno)
NEWS_EFFECTS = {
    "Nessuna News": {"att": 1.00, "def": 1.00},
    "Must Win (+Att / -Def)": {"att": 1.08, "def": 1.05},  # Sbilanciata avanti
    "Not Lose (Inv / +Def)": {"att": 1.00, "def": 0.94},   # Difesa solida
    "Derby (Teso -5% / -5%)": {"att": 0.95, "def": 0.95},  # Pochi gol
    "Stanchezza (-Att / -Def)": {"att": 0.92, "def": 1.10},# Subiscono di più
    "No Attaccante Key (-Att)": {"att": 0.92, "def": 1.00},
    "No Centrocampista Key": {"att": 0.94, "def": 1.04},
    "No Difensore Key (-Def)": {"att": 1.00, "def": 1.08}, # Subiscono di più
    "Volatilità Alta (+Att / -Def)": {"att": 1.10, "def": 1.10} # Partita pazza
}

class StrategyDashboard:
    def __init__(self, df):
        self.df = df
        self.output_area = widgets.Output()
        
        # --- 1. WIDGET SELEZIONE MATCH ---
        
        # Dropdown Lega
        leagues = sorted(self.df['League'].unique().tolist())
        self.dd_league = widgets.Dropdown(options=leagues, description='Lega:')
        
        # Dropdown Stagione (Filtrerà i match)
        # Ordiniamo le stagioni in modo inverso (dalla più recente)
        seasons = sorted(self.df['Season'].unique().tolist(), reverse=True)
        self.dd_season = widgets.Dropdown(options=seasons, description='Stagione:')
        
        # Dropdown Match (Data | Casa vs Ospite)
        self.dd_match = widgets.Dropdown(description='Match:', layout={'width': '400px'})
        
        # Eventi: Quando cambio Lega o Stagione, aggiorno la lista match
        self.dd_league.observe(self._update_match_list, names='value')
        self.dd_season.observe(self._update_match_list, names='value')
        
        # --- 2. WIDGET NEWS (DELTA) ---
        
        style = {'description_width': 'initial'}
        
        # Casa
        self.lbl_home = widgets.Label(value="SQUADRA CASA (Home)")
        self.dd_news_att_home = widgets.Dropdown(options=NEWS_EFFECTS.keys(), description='News Attacco:', style=style)
        self.dd_news_def_home = widgets.Dropdown(options=NEWS_EFFECTS.keys(), description='News Difesa:', style=style)
        
        # Ospite
        self.lbl_away = widgets.Label(value="SQUADRA OSPITE (Away)")
        self.dd_news_att_away = widgets.Dropdown(options=NEWS_EFFECTS.keys(), description='News Attacco:', style=style)
        self.dd_news_def_away = widgets.Dropdown(options=NEWS_EFFECTS.keys(), description='News Difesa:', style=style)
        
        # Bottone Calcola
        self.btn_calc = widgets.Button(
            description='AVVIA ANALISI 🚀',
            button_style='success', # 'success', 'info', 'warning', 'danger' or ''
            layout={'width': '98%', 'height': '50px'}
        )
        self.btn_calc.on_click(self._run_calculation)

        # Inizializza la lista match
        self._update_match_list(None)

    def _update_match_list(self, change):
        """Filtra il DataFrame per Lega/Stagione e popola il dropdown match"""
        sel_league = self.dd_league.value
        sel_season = self.dd_season.value
        
        # Filtra
        mask = (self.df['League'] == sel_league) & (self.df['Season'] == sel_season)
        filtered = self.df[mask].sort_values('Date', ascending=False)
        
        if filtered.empty:
            self.dd_match.options = [("Nessun match trovato", None)]
            return

        # Crea lista opzioni: "2024-03-10 | Milan vs Empoli" -> (value=row_index)
        options = []
        for idx, row in filtered.iterrows():
            dt_str = row['Date'].strftime('%Y-%m-%d')
            label = f"{dt_str} | {row['HomeTeam']} vs {row['AwayTeam']}"
            # Salviamo l'indice del DF e i nomi squadra come valore
            val = {
                'date': dt_str,
                'home': row['HomeTeam'],
                'away': row['AwayTeam']
            }
            options.append((label, val))
            
        self.dd_match.options = options

    def display(self):
        """Mostra la Dashboard"""
        
        # Layout Grafico
        match_box = widgets.VBox([
            widgets.HBox([self.dd_league, self.dd_season]),
            self.dd_match
        ])
        
        news_home_box = widgets.VBox([self.lbl_home, self.dd_news_att_home, self.dd_news_def_home])
        news_away_box = widgets.VBox([self.lbl_away, self.dd_news_att_away, self.dd_news_def_away])
        news_box = widgets.HBox([news_home_box, news_away_box])
        
        ui = widgets.VBox([
            widgets.HTML("<h2>🎛️ Control Panel Strategia</h2>"),
            match_box,
            widgets.HTML("<hr>"),
            widgets.HTML("<h4>📰 Pannello News (Delta Manuali)</h4>"),
            news_box,
            widgets.HTML("<br>"),
            self.btn_calc,
            self.output_area
        ])
        
        display(ui)

    def _run_calculation(self, b):
        """Callback del bottone: Raccoglie dati e chiama StatsEngine"""
        match_val = self.dd_match.value
        
        if not match_val:
            with self.output_area:
                clear_output()
                print("❌ Errore: Seleziona un match valido.")
            return

        # Recupera i moltiplicatori dai menu News
        delta_att_h = NEWS_EFFECTS[self.dd_news_att_home.value]['att']
        delta_def_h = NEWS_EFFECTS[self.dd_news_def_home.value]['def']
        
        delta_att_a = NEWS_EFFECTS[self.dd_news_att_away.value]['att']
        delta_def_a = NEWS_EFFECTS[self.dd_news_def_away.value]['def']

        # --- CHIAMATA AL MOTORE ---
        with self.output_area:
            clear_output()
            print("⏳ Analisi in corso...")
            
            result = stats_engine.calculate_match_prediction(
                self.df,
                date_match=match_val['date'],
                home_team=match_val['home'],
                away_team=match_val['away'],
                delta_att_home=delta_att_h,
                delta_def_home=delta_def_h,
                delta_att_away=delta_att_a,
                delta_def_away=delta_def_a
            )
            
            if "error" in result:
                print(f"❌ {result['error']}")
            else:
                self._render_output(result)

    def _render_output(self, res):
        """Genera l'HTML e le tabelle finali"""
        clear_output()
        
        # Dati Estratti
        lp = res['league_params']
        ts = res['team_stats']
        xg = res['xg_prediction']
        odds = res['odds']
        probs = res['probabilities']
        
        # Helper per colore forza (Verde=Forte, Rosso=Debole)
        def color_att(val): return "green" if val > 1.0 else "red"
        def color_def(val): return "green" if val < 1.0 else "red" # Difesa < 1 è buona
        
        # HTML Costruzione
        html = f"""
        <style>
            .res-table {{ width: 100%; border-collapse: collapse; font-family: Arial; }}
            .res-table td, .res-table th {{ border: 1px solid #ddd; padding: 8px; text-align: center; }}
            .res-table th {{ background-color: #f2f2f2; }}
            .strong {{ color: green; font-weight: bold; }}
            .weak {{ color: red; font-weight: bold; }}
            .title {{ background-color: #333; color: white; padding: 5px; }}
        </style>
        
        <h2 style='text-align:center;'>📊 ANALISI MATCH REPORT</h2>
        <h3 style='text-align:center;'>{res['match_info']['home']} vs {res['match_info']['away']}</h3>
        <p style='text-align:center;'>Data Analisi: {res['match_info']['date']}</p>
        
        <!-- SEZIONE 1: CHECK ANALISI -->
        <div class='title'>1. CHECK ANALISI DATI</div>
        <ul>
            <li><b>Lega (Rolling):</b> {lp['games_analyzed']} partite analizzate pre-match.</li>
            <li><b>Coefficienti Lega:</b> b={lp['coef_b']}, c={lp['coef_c']}, d={lp['coef_d']}</li>
            <li><b>Ancora Standard:</b> {lp['anchor_std']}</li>
            <li><b>Red Cards (ultime 10):</b> Casa ({ts['home_red_cards']}), Ospite ({ts['away_red_cards']})</li>
        </ul>

        <!-- SEZIONE 2: FORZE IN CAMPO -->
        <div class='title'>2. FORZE IN CAMPO (RAW + ADJ)</div>
        <table class='res-table'>
            <tr>
                <th>Parametro</th>
                <th>Valore Raw</th>
                <th>Valutazione</th>
            </tr>
            <tr>
                <td>Attacco CASA</td>
                <td>{ts['home_raw_att']}</td>
                <td style='color:{color_att(ts['home_raw_att'])}'>{'FORTE' if ts['home_raw_att'] > 1 else 'DEBOLE'}</td>
            </tr>
            <tr>
                <td>Difesa CASA</td>
                <td>{ts['home_raw_def']}</td>
                <td style='color:{color_def(ts['home_raw_def'])}'>{'FORTE' if ts['home_raw_def'] < 1 else 'DEBOLE'}</td>
            </tr>
            <tr>
                <td>Attacco OSPITE</td>
                <td>{ts['away_raw_att']}</td>
                <td style='color:{color_att(ts['away_raw_att'])}'>{'FORTE' if ts['away_raw_att'] > 1 else 'DEBOLE'}</td>
            </tr>
            <tr>
                <td>Difesa OSPITE</td>
                <td>{ts['away_raw_def']}</td>
                <td style='color:{color_def(ts['away_raw_def'])}'>{'FORTE' if ts['away_raw_def'] < 1 else 'DEBOLE'}</td>
            </tr>
        </table>
        <br>

        <!-- SEZIONE 3: PREVISIONE PRINCIPALE -->
        <div class='title'>3. PREVISIONE XG & QUOTE FAIR</div>
        <table class='res-table'>
            <tr>
                <th>Metrica</th>
                <th>Casa</th>
                <th>Ospite</th>
            </tr>
            <tr>
                <td><b>Expected Goals (xG)</b></td>
                <td><b>{xg['xg_home']}</b></td>
                <td><b>{xg['xg_away']}</b></td>
            </tr>
        </table>
        <br>
        <table class='res-table'>
            <tr>
                <th>Segno</th>
                <th>Probabilità %</th>
                <th>Quota Fair (Decimal)</th>
            </tr>
            <tr>
                <td>1 (Home Win)</td>
                <td>{probs['1']}%</td>
                <td><b>@{odds['1']}</b></td>
            </tr>
            <tr>
                <td>X (Draw)</td>
                <td>{probs['X']}%</td>
                <td><b>@{odds['X']}</b></td>
            </tr>
            <tr>
                <td>2 (Away Win)</td>
                <td>{probs['2']}%</td>
                <td><b>@{odds['2']}</b></td>
            </tr>
             <tr>
                <td>Goal (GG)</td>
                <td>{probs['Gol']}%</td>
                <td><b>@{odds['Gol']}</b></td>
            </tr>
             <tr>
                <td>Over 2.5</td>
                <td>{probs['Over2.5']}%</td>
                <td><b>@{odds['Over2.5']}</b></td>
            </tr>
        </table>

        <!-- SEZIONE 4: RISULTATI ESATTI -->
        <br>
        <div class='title'>4. TOP 5 RISULTATI ESATTI (Dixon-Coles)</div>
        <table class='res-table' style='width:50%; margin:auto;'>
            <tr>
                <th>Score</th>
                <th>Prob %</th>
            </tr>
        """
        
        for score in res['exact_score_top5']:
            html += f"<tr><td>{score['score']}</td><td>{score['prob']}%</td></tr>"
            
        html += "</table>"
        
        display(HTML(html))