import streamlit as st
import pandas as pd
from src import data_loader, stats_engine

# --- NEWS EFFECTS (copiato da dashboard.py) ---
NEWS_EFFECTS = {
    "Nessuna News": {"att": 1.00, "def": 1.00},
    "Must Win (+Att / -Def)": {"att": 1.08, "def": 1.05},
    "Not Lose (Inv / +Def)": {"att": 1.00, "def": 0.94},
    "Derby (Teso -5% / -5%)": {"att": 0.95, "def": 0.95},
    "Stanchezza (-Att / -Def)": {"att": 0.92, "def": 1.10},
    "No Attaccante Key (-Att)": {"att": 0.92, "def": 1.00},
    "No Centrocampista Key": {"att": 0.94, "def": 1.04},
    "No Difensore Key (-Def)": {"att": 1.00, "def": 1.08},
    "Volatilità Alta (+Att / -Def)": {"att": 1.10, "def": 1.10},
}

# --- CACHE DATI ---
@st.cache_data
def load_data():
    return data_loader.load_all_data()

df = load_data()

st.title("📊 Strategia Calcio – Match Analyzer")

# --- SELEZIONE LEGA / STAGIONE / MATCH ---
if df.empty:
    st.error("Nessun dato disponibile. Controlla il download CSV.")
    st.stop()

leagues = sorted(df["League"].unique().tolist())
sel_league = st.selectbox("Lega", leagues)

df_league = df[df["League"] == sel_league]

seasons = sorted(df_league["Season"].unique().tolist(), reverse=True)
sel_season = st.selectbox("Stagione", seasons)

df_ls = df_league[df_league["Season"] == sel_season].sort_values(
    "Date", ascending=False
)

if df_ls.empty:
    st.warning("Nessun match trovato per questa combinazione.")
    st.stop()

# Costruiamo mappa etichetta -> riga
options = []
label_to_row = {}
for _, row in df_ls.iterrows():
    dt_str = row["Date"].strftime("%Y-%m-%d")
    label = f"{dt_str} | {row['HomeTeam']} vs {row['AwayTeam']}"
    options.append(label)
    label_to_row[label] = row

sel_match_label = st.selectbox("Match", options)
match_row = label_to_row[sel_match_label]

st.markdown(f"**Match selezionato:** {sel_match_label}")

# --- NEWS HOME / AWAY ---
st.subheader("📰 Pannello News (Delta Manuali)")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Squadra CASA**")
    news_att_home = st.selectbox("News Attacco Casa", list(NEWS_EFFECTS.keys()), key="nah")
    news_def_home = st.selectbox("News Difesa Casa", list(NEWS_EFFECTS.keys()), key="ndh")

with col2:
    st.markdown("**Squadra OSPITE**")
    news_att_away = st.selectbox("News Attacco Ospite", list(NEWS_EFFECTS.keys()), key="naa")
    news_def_away = st.selectbox("News Difesa Ospite", list(NEWS_EFFECTS.keys()), key="nda")

if st.button("🚀 Avvia Analisi"):
    with st.spinner("Calcolo in corso..."):
        res = stats_engine.calculate_match_prediction(
            df,
            date_match=match_row["Date"].strftime("%Y-%m-%d"),
            home_team=match_row["HomeTeam"],
            away_team=match_row["AwayTeam"],
            delta_att_home=NEWS_EFFECTS[news_att_home]["att"],
            delta_def_home=NEWS_EFFECTS[news_def_home]["def"],
            delta_att_away=NEWS_EFFECTS[news_att_away]["att"],
            delta_def_away=NEWS_EFFECTS[news_def_away]["def"],
        )

    if "error" in res:
        st.error(res["error"])
    else:
        lp = res["league_params"]
        ts = res["team_stats"]
        xg = res["xg_prediction"]
        odds = res["odds"]
        probs = res["probabilities"]

        st.subheader("1️⃣ Check Analisi Dati")
        st.write(
            f"- **Lega (Rolling):** {lp['games_analyzed']} partite\n"
            f"- **Coefficienti Lega:** b={lp['coef_b']}, c={lp['coef_c']}, d={lp['coef_d']}\n"
            f"- **Ancora Standard:** {lp['anchor_std']}\n"
            f"- **Red Cards (ultime 10):** Casa ({ts['home_red_cards']}), Ospite ({ts['away_red_cards']})"
        )

        st.subheader("2️⃣ Forze in campo (RAW)")
        def_eval = lambda v: "FORTE" if v < 1.0 else "DEBOLE"
        att_eval = lambda v: "FORTE" if v > 1.0 else "DEBOLE"

        df_forze = pd.DataFrame(
            [
                ["Attacco CASA", ts["home_raw_att"], att_eval(ts["home_raw_att"])],
                ["Difesa CASA", ts["home_raw_def"], def_eval(ts["home_raw_def"])],
                ["Attacco OSPITE", ts["away_raw_att"], att_eval(ts["away_raw_att"])],
                ["Difesa OSPITE", ts["away_raw_def"], def_eval(ts["away_raw_def"])],
            ],
            columns=["Parametro", "Valore Raw", "Valutazione"],
        )
        st.dataframe(df_forze, hide_index=True)

        st.subheader("3️⃣ xG & Quote Fair")
        col_xg1, col_xg2 = st.columns(2)
        with col_xg1:
            st.metric("xG Casa", xg["xg_home"])
        with col_xg2:
            st.metric("xG Ospite", xg["xg_away"])

        df_odds = pd.DataFrame(
            [
                ["1", probs["1"], odds["1"]],
                ["X", probs["X"], odds["X"]],
                ["2", probs["2"], odds["2"]],
                ["Goal (GG)", probs["Gol"], odds["Gol"]],
                ["Over 2.5", probs["Over2.5"], odds["Over2.5"]],
            ],
            columns=["Segno", "Prob %", "Quota Fair"],
        )
        st.table(df_odds)

        st.subheader("4️⃣ Top 5 Risultati Esatti")
        df_scores = pd.DataFrame(
            [
                (s["score"], s["prob"])
                for s in res["exact_score_top5"]
            ],
            columns=["Score", "Prob %"],
        )
        st.table(df_scores)
