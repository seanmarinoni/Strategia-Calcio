import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import ipywidgets as widgets
from IPython.display import display, clear_output
from .data_loader import load_all_data

class DashboardTecnica:
    def __init__(self):
        self.df = load_all_data()
        
    def _calculate_rsi_wilder(self, series, period=5):
        delta = series.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.ewm(com=period-1, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(com=period-1, min_periods=period, adjust=False).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)

    def _prepare_team_data(self, team, league, season, method):
        # Filtro base
        mask = (self.df['League'] == league) & \
               (self.df['Season'] == season) & \
               ((self.df['HomeTeam'] == team) | (self.df['AwayTeam'] == team))
        
        tdf = self.df[mask].sort_values('Date').copy().reset_index(drop=True)
        if tdf.empty: return pd.DataFrame()

        # --- FILTRO AGGIUNTIVO: Solo partite GIOCATE ---
        # 1. Elimina righe dove mancano i gol (partite future nel calendario)
        tdf = tdf.dropna(subset=['home_goals', 'away_goals'])
        
        # 2. Elimina partite con data futura rispetto ad oggi (sicurezza extra)
        tdf = tdf[tdf['Date'] <= pd.Timestamp.now()]
        
        # Se dopo il filtro è vuoto, ritorna
        if tdf.empty: return pd.DataFrame()
        
        equity_vals = []
        outcomes = []
        curr_eq = 0
        
        for _, row in tdf.iterrows():
            is_home = (row['HomeTeam'] == team)
            gh = row['home_goals']
            ga = row['away_goals']
            
            if gh == ga: res = 'D'
            elif gh > ga: res = 'H'
            else: res = 'A'
            
            val = 0
            outcome = 'D'
            
            if res == 'D':
                val = 1 if method == 'points' else 0
                outcome = 'D'
            elif (is_home and res == 'H') or (not is_home and res == 'A'):
                val = 3 if method == 'points' else 1
                outcome = 'W'
            else:
                val = 0 if method == 'points' else -1
                outcome = 'L'
            
            curr_eq += val
            equity_vals.append(curr_eq)
            outcomes.append(outcome)
            
        tdf['Equity'] = equity_vals
        tdf['Outcome'] = outcomes
        tdf['MatchNum'] = range(1, len(tdf) + 1)
        tdf['Opponent'] = np.where(tdf['HomeTeam'] == team, tdf['AwayTeam'], tdf['HomeTeam'])
        
        return tdf

    def _add_indicators(self, df, params):
        if df.empty: return df
        eq = df['Equity']
        if params['sma_s_on']: df['SMA_S'] = eq.rolling(window=params['sma_s_val']).mean()
        if params['sma_m_on']: df['SMA_M'] = eq.rolling(window=params['sma_m_val']).mean()
        if params['ema_s_on']: df['EMA_S'] = eq.ewm(span=params['ema_s_val'], adjust=False).mean()
        if params['ema_m_on']: df['EMA_M'] = eq.ewm(span=params['ema_m_val'], adjust=False).mean()
        if params['rsi_on']: df['RSI'] = self._calculate_rsi_wilder(eq, period=5)
        return df

    def _plot_graph(self, data1, name1, data2=None, name2=None, params=None):
        rows_config = []
        rows_config.append(('eq', data1, name1))
        if params['rsi_on']: rows_config.append(('rsi', data1, ""))
        
        if data2 is not None:
            rows_config.append(('eq', data2, name2))
            if params['rsi_on']: rows_config.append(('rsi', data2, ""))
            
        n_rows = len(rows_config)
        if n_rows == 0: return

        # Layout Respiro: 70% Equity, 30% RSI
        specs = []
        titles = []
        for r_type, _, name in rows_config:
            if r_type == 'eq': 
                specs.append(0.70)
                titles.append(f"<b>{name}</b> - Equity")
            else: 
                specs.append(0.30)
                titles.append(f"RSI (5)")
        
        total_spec = sum(specs)
        final_specs = [s/total_spec for s in specs]

        fig = make_subplots(
            rows=n_rows, cols=1,
            shared_xaxes=False,
            vertical_spacing=0.08,
            row_heights=final_specs,
            subplot_titles=titles
        )

        for i, (r_type, df, name) in enumerate(rows_config):
            row_idx = i + 1
            
            if r_type == 'eq':
                colors = {'W': '#00cc00', 'D': '#ffcc00', 'L': '#ff0000'}
                for k in range(len(df)-1):
                    curr, nxt = df.iloc[k], df.iloc[k+1]
                    fig.add_trace(go.Scatter(
                        x=[curr['MatchNum'], nxt['MatchNum']], y=[curr['Equity'], nxt['Equity']],
                        mode='lines', line=dict(color=colors.get(nxt['Outcome'], '#888'), width=3),
                        showlegend=False, hoverinfo='skip'
                    ), row=row_idx, col=1)
                
                fig.add_trace(go.Scatter(
                    x=df['MatchNum'], y=df['Equity'], mode='markers',
                    marker=dict(color='black', size=6, line=dict(width=1, color='white')),
                    text=df['Date'].dt.strftime('%d/%m') + " vs " + df['Opponent'],
                    hovertemplate="Match %{x}<br>%{text}<br><b>Eq: %{y}</b><extra></extra>", 
                    showlegend=False
                ), row=row_idx, col=1)
                
                if params['sma_s_on'] and 'SMA_S' in df: fig.add_trace(go.Scatter(x=df['MatchNum'], y=df['SMA_S'], line=dict(color='royalblue', width=1.5), name=f"SMA {params['sma_s_val']}", showlegend=(row_idx==1)), row=row_idx, col=1)
                if params['sma_m_on'] and 'SMA_M' in df: fig.add_trace(go.Scatter(x=df['MatchNum'], y=df['SMA_M'], line=dict(color='orange', width=1.5), name=f"SMA {params['sma_m_val']}", showlegend=(row_idx==1)), row=row_idx, col=1)
                if params['ema_s_on'] and 'EMA_S' in df: fig.add_trace(go.Scatter(x=df['MatchNum'], y=df['EMA_S'], line=dict(color='cyan', width=1, dash='dot'), name=f"EMA {params['ema_s_val']}", showlegend=(row_idx==1)), row=row_idx, col=1)
                if params['ema_m_on'] and 'EMA_M' in df: fig.add_trace(go.Scatter(x=df['MatchNum'], y=df['EMA_M'], line=dict(color='magenta', width=1, dash='dot'), name=f"EMA {params['ema_m_val']}", showlegend=(row_idx==1)), row=row_idx, col=1)

                ymin, ymax = df['Equity'].min(), df['Equity'].max()
                delta = ymax - ymin if ymax != ymin else 1
                pad = delta * 0.25
                fig.update_yaxes(range=[ymin - pad, ymax + pad], row=row_idx, col=1)

            else:
                fig.add_trace(go.Scatter(x=df['MatchNum'], y=df['RSI'], line=dict(color='#8e44ad', width=2), showlegend=False), row=row_idx, col=1)
                fig.add_shape(type="line", x0=0, x1=len(df)+1, y0=70, y1=70, line=dict(color="red", dash="dot"), row=row_idx, col=1)
                fig.add_shape(type="line", x0=0, x1=len(df)+1, y0=30, y1=30, line=dict(color="green", dash="dot"), row=row_idx, col=1)
                fig.update_yaxes(range=[0, 100], row=row_idx, col=1)

        total_h = 500 if data2 is None else 900
        fig.update_layout(template="plotly_white", height=total_h, margin=dict(t=40, b=30, l=50, r=40), hovermode="x unified")
        display(fig)

    def show_interface(self):
        if self.df.empty:
            print("❌ Nessun dato caricato.")
            return

        leagues = sorted(self.df['League'].unique())
        w_league = widgets.Dropdown(options=leagues, description='Lega:')
        w_season = widgets.Dropdown(description='Stagione:')
        w_team1 = widgets.Dropdown(description='Squadra 1:')
        w_show_team2 = widgets.Checkbox(value=False, description='Confronta')
        w_team2 = widgets.Dropdown(description='Squadra 2:', disabled=True)
        w_method = widgets.ToggleButtons(options=['tick', 'points'], description='Metodo:', button_style='info')

        style = {'description_width': 'initial'}
        w_chk_sma_s = widgets.Checkbox(value=True, description='SMA Brv')
        w_sli_sma_s = widgets.IntSlider(value=5, min=3, max=7, description='P:', style=style, layout=widgets.Layout(width='120px'))
        w_chk_sma_m = widgets.Checkbox(value=True, description='SMA Med')
        w_sli_sma_m = widgets.IntSlider(value=15, min=7, max=15, description='P:', style=style, layout=widgets.Layout(width='120px'))
        w_chk_ema_s = widgets.Checkbox(value=False, description='EMA Brv')
        w_sli_ema_s = widgets.IntSlider(value=5, min=3, max=7, description='P:', style=style, layout=widgets.Layout(width='120px'))
        w_chk_ema_m = widgets.Checkbox(value=False, description='EMA Med')
        w_sli_ema_m = widgets.IntSlider(value=12, min=7, max=15, description='P:', style=style, layout=widgets.Layout(width='120px'))
        w_chk_rsi = widgets.Checkbox(value=True, description='RSI (Wilder)')
        
        out = widgets.Output()

        def update_seasons(*args):
            avail = sorted(self.df[self.df['League'] == w_league.value]['Season'].unique(), reverse=True)
            w_season.options = avail
            
        def update_teams(*args):
            mask = (self.df['League'] == w_league.value) & (self.df['Season'] == w_season.value)
            teams = sorted(pd.concat([self.df[mask]['HomeTeam'], self.df[mask]['AwayTeam']]).unique())
            w_team1.options = teams
            w_team2.options = teams
            
        def toggle_team2(*args): w_team2.disabled = not w_show_team2.value; update_graph()

        def update_graph(*args):
            with out:
                clear_output(wait=True)
                if not w_team1.value: return

                params = {'sma_s_on': w_chk_sma_s.value, 'sma_s_val': w_sli_sma_s.value,
                          'sma_m_on': w_chk_sma_m.value, 'sma_m_val': w_sli_sma_m.value,
                          'ema_s_on': w_chk_ema_s.value, 'ema_s_val': w_sli_ema_s.value,
                          'ema_m_on': w_chk_ema_m.value, 'ema_m_val': w_sli_ema_m.value,
                          'rsi_on': w_chk_rsi.value}
                
                # 1. Carica dati
                df1 = self._prepare_team_data(w_team1.value, w_league.value, w_season.value, w_method.value)
                
                # 2. SE i dati esistono, calcola indicatori (QUESTO MANCAVA PRIMA!)
                if not df1.empty:
                    df1 = self._add_indicators(df1, params)
                    d_start = df1['Date'].iloc[0].strftime('%d/%m/%Y')
                    d_end = df1['Date'].iloc[-1].strftime('%d/%m/%Y')
                    print(f"📊 {w_team1.value}: {len(df1)} partite giocate ({d_start} -> {d_end})")
                
                df2 = None
                if w_show_team2.value and w_team2.value:
                    df2 = self._prepare_team_data(w_team2.value, w_league.value, w_season.value, w_method.value)
                    if not df2.empty:
                        df2 = self._add_indicators(df2, params) # Anche qui
                        d_start2 = df2['Date'].iloc[0].strftime('%d/%m/%Y')
                        d_end2 = df2['Date'].iloc[-1].strftime('%d/%m/%Y')
                        print(f"📊 {w_team2.value}: {len(df2)} partite giocate ({d_start2} -> {d_end2})")
                
                self._plot_graph(df1, w_team1.value, df2, w_team2.value if w_show_team2.value else None, params)

        w_league.observe(update_seasons, 'value')
        w_season.observe(update_teams, 'value')
        w_league.observe(update_teams, 'value')
        w_show_team2.observe(toggle_team2, 'value')
        for t in [w_team1, w_team2, w_method, w_chk_rsi, w_chk_sma_s, w_sli_sma_s, w_chk_sma_m, w_sli_sma_m, w_chk_ema_s, w_sli_ema_s, w_chk_ema_m, w_sli_ema_m]:
            t.observe(update_graph, 'value')

        update_seasons()
        update_teams()
        
        box_data = widgets.HBox([widgets.VBox([w_league, w_season]), widgets.VBox([w_team1, w_team2, w_show_team2]), widgets.VBox([w_method])])
        box_tech = widgets.VBox([
            widgets.HBox([w_chk_sma_s, w_sli_sma_s, widgets.Label("|"), w_chk_sma_m, w_sli_sma_m]),
            widgets.HBox([w_chk_ema_s, w_sli_ema_s, widgets.Label("|"), w_chk_ema_m, w_sli_ema_m]),
            w_chk_rsi
        ])

        display(widgets.VBox([box_data, widgets.HTML("<hr>"), box_tech, out]))
        update_graph()

def mostra_dashboard():
    d = DashboardTecnica()
    d.show_interface()