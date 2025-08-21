import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import boto3
import yaml
from sklearn.preprocessing import MinMaxScaler

# Set layout and background
st.set_page_config(
    layout="wide", 
    page_icon="vanderbilt_logo.svg",
    page_title="Vanderbilt Analytics"
)
st.sidebar.image("vanderbilt_logo.svg", width=75)

AWS_ACCESS_KEY_ID = st.secrets["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = st.secrets["AWS_SECRET_ACCESS_KEY"]
BUCKET_NAME = st.secrets["BUCKET_NAME"]
CSV_KEY = st.secrets["CSV_KEY"]

@st.cache_data(ttl=3600)
def load_data_from_s3():
    s3 = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )
    obj = s3.get_object(Bucket=BUCKET_NAME, Key=CSV_KEY)
    df = pd.read_csv(obj["Body"])
    return df

@st.cache_data()
def load_config():
    with open("config.yaml", "r") as file:
        return yaml.safe_load(file)

data = load_data_from_s3()
config = load_config()

def calculate_percentile(data):
    data = (
        data.groupby(["team", "player_name"])
        .mean()
        .reset_index()
    )
    return (
        data[["team", "player_name"]]
        .join(
            data.drop(columns=["team", "player_name"]).rank(pct=True).round(2) * 100
        )
    )

def calculate_mean(data):
    data = (
        data.groupby(["team", "player_name"])
        .mean()
        .round(2)
        .reset_index()
    )
    return data

st.sidebar.header("Filters")
season_select = st.sidebar.selectbox(
    options=data["year"].unique(),
    label="Select Season",
)

st.sidebar.subheader("Select Metrics")
metric_options = ["Average (per game)", "Percentile"]
selected_metric = st.sidebar.selectbox(
    "Select Metric",
    options=metric_options,
)


data = data[data["year"] == season_select]
data = data[data["player_name"] != "undefined"]

for new_col, (numerator, denominator) in config["metrics"].items():
    data[new_col] = data[numerator] / data[denominator]

data = data.fillna(0)

postional_subsets = {
    "Wingers": data[data["Position"].str.contains("LW") | data["Position"].str.contains("RW")],
    "Goalkeepers": data[data["Position"].str.contains("GK")],
    "Forwards": data[data["Position"].str.contains("CF")],
    "Attacking Midfielders": data[data["Position"].str.contains("AMF")],
    "Central Midfielders": data[data["Position"].str.contains("CMF") | (data["Position"].str.contains("DMF"))],
    "Outside Backs": data[(data["Position"].str.contains("LB")) | (data["Position"].str.contains("RB"))],
    "Center Backs": data[data["Position"].str.contains("CB")],
}

def plot_radar(players, position, position_df, season=2024):
    subset_config = config["columns_config"][position]
    data = position_df.copy()
    columns = [val for val in subset_config["column_names"].keys()]
    labels = [val for val in subset_config["column_names"].values() if val != "data"]

    data = data.drop(columns=["year"])

    if position == "Goalkeepers":
        data["gk_stat_shutout"] = (
            data["gk_stat_conceded_goals"] == 0
        ).astype(int)

        shutout_pct = (
            data.groupby(["team", "player_name"])
            ["gk_stat_shutout"]
            .mean()
            .reset_index()
        )
        shutout_pct.rename(columns={"gk_stat_shutout": "gk_stat_shutout_pct"}, inplace=True)

        data = data.merge(shutout_pct, on=["team", "player_name"], how="left")
    fig = go.Figure()

    if selected_metric == "Average (per game)":
        data = calculate_mean(data[columns + ["team", "player_name"]])

        scaler = MinMaxScaler((0, 100))
        std_data = scaler.fit_transform(data[columns])
        std_data = pd.DataFrame(std_data, columns=columns)
        std_data["team"] = data["team"]
        std_data["player_name"] = data["player_name"]
        conference_avg = std_data[columns].mean().round(2)

        hovertext = [
            f"{label}: {val:.2f}"
            for label, val in zip(labels, data[columns].mean().round(2).values.flatten())
        ]

        fig.add_trace(
            go.Scatterpolar(
                r=conference_avg.values.flatten(),
                theta=labels,
                fill='toself',
                name='SEC Avg',
                line_color='rgba(179, 163, 105, 0.5)',
                fillcolor="rgba(179, 163, 105, 0.5)",
                hovertext=hovertext,
                hoverinfo='text'
            )
        )


    elif selected_metric == "Percentile":
        data = calculate_percentile(data[columns + ["team", "player_name"]])
        conference_avg = data[columns].mean().round(2)
    
        fig.add_trace(
                go.Scatterpolar(
                    r=conference_avg.values.flatten(),
                    theta=labels,
                    fill='toself',
                    name='SEC Avg',
                    line_color='rgba(179, 163, 105, 0.5)',
                    fillcolor="rgba(179, 163, 105, 0.5)",
                )
            )

    if players:
        for player in players:
            if selected_metric == "Average (per game)":
                row = std_data[std_data["player_name"] == player]
                if not row.empty:
                    raw_row = data[data["player_name"] == player]
                    raw_values = raw_row[columns].values.flatten() if not raw_row.empty else row[columns].values.flatten()

                    hovertext = [
                        f"{label}: {raw_val:.2f}"
                        for label, raw_val in zip(labels, raw_values)
                    ]

                    fig.add_trace(go.Scatterpolar(
                        r=row[columns].values.flatten(),
                        theta=labels,
                        fill='toself',
                        name=player,
                        hovertext=hovertext,
                        hoverinfo='text',
                    ))
            elif selected_metric == "Percentile":
                row = data[data["player_name"] == player]
                if not row.empty:
                    fig.add_trace(go.Scatterpolar(
                        r=row[columns].values.flatten(),
                        theta=labels,
                        fill='toself',
                        name=player
                    ))

    fig.update_layout(
    polar=dict(
        angularaxis=dict(
            showticklabels=True,
        ),
        radialaxis=dict(visible=True, showticklabels=False, range=[0, 100])
    ),
    margin=dict(t=80, b=80, l=100, r=100),  # add more space around
)
    return fig


# App layout
st.title("Vanderbilt Player Performance Charts")
st.header("For evaluating player performance in the SEC using KPI metrics")

col1, col2 = st.columns(2)

for col, position in zip([col1, col2], ["Forwards", "Wingers"]):
    with col:
        st.header(position)
        options = ["Average"] + list(postional_subsets[position]["player_name"].unique())
        selected = st.multiselect(f"Select {position}", options=options, default=["Average"])
        fig = plot_radar([p for p in selected if p != "Average"], position, postional_subsets[position])
        st.plotly_chart(fig, use_container_width=True)

col3, col4 = st.columns(2)
for col, position in zip([col3, col4], ["Attacking Midfielders", "Central Midfielders"]):
    with col:
        st.header(position)
        options = ["Average"] + list(postional_subsets[position]["player_name"].unique())
        selected = st.multiselect(f"Select {position}", options=options, default=["Average"])
        fig = plot_radar([p for p in selected if p != "Average"], position, postional_subsets[position])
        st.plotly_chart(fig, use_container_width=True)

col5, col6 = st.columns(2)
for col, position in zip([col5, col6], ["Center Backs", "Outside Backs"]):
    with col:
        st.header(position)
        options = ["Average"] + list(postional_subsets[position]["player_name"].unique())
        selected = st.multiselect(f"Select {position}", options=options, default=["Average"])
        fig = plot_radar([p for p in selected if p != "Average"], position, postional_subsets[position])
        st.plotly_chart(fig, use_container_width=True)

position = "Goalkeepers"
st.header(position)
options = ["Average"] + list(postional_subsets[position]["player_name"].unique())
selected = st.multiselect(f"Select {position}", options=options, default=["Average"])
fig = plot_radar([p for p in selected if p != "Average"], position, postional_subsets[position])
st.plotly_chart(fig, use_container_width=True)
