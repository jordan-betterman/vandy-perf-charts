import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import boto3
import yaml

# Set layout and background
st.set_page_config(layout="wide", page_icon="vanderbilt_logo.svg")
st.sidebar.image("vanderbilt_logo.svg", width=75)

AWS_ACCESS_KEY_ID = st.secrets["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = st.secrets["AWS_SECRET_ACCESS_KEY"]
BUCKET_NAME = st.secrets["BUCKET_NAME"]
CSV_KEY = st.secrets["CSV_KEY"]

@st.cache_data
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

st.sidebar.header("Filters")
season_select = st.sidebar.selectbox(
    options=data["year"].unique(),
    label="Select Season",
)

data = data[data["year"] == season_select]
data = data[data["player_name"] != "undefined"]

for new_col, (numerator, denominator) in config["metrics"].items():
    data[new_col] = data[numerator] / data[denominator]

data = data.fillna(0)

def calculate_percentile(data):
    data = (
        data.groupby(["team", "player_name", "year"])
        .mean()
        .reset_index()
    )
    return (
        data[["team", "player_name", "year"]]
        .join(
            data.drop(columns=["team", "player_name", "year"]).rank(pct=True).round(2) * 100
        )
    )

postional_subsets = {
    "Wingers": data[data["Position"].str.contains("LW") | data["Position"].str.contains("RW")],
    "Goalkeepers": data[data["Position"].str.contains("GK")],
    "Forwards": data[data["Position"].str.contains("CF")],
    "Central Midfielders": data[data["Position"].str.contains("CMF") | (data["Position"].str.contains("AMF"))],
    "Defensive Midfielders": data[data["Position"].str.contains("DMF")],
    "Outside Backs": data[(data["Position"].str.contains("LB")) | (data["Position"].str.contains("RB"))],
    "Center Backs": data[data["Position"].str.contains("CB")],
}

def plot_radar(players, position, position_df, season=2024):
    subset_config = config["columns_config"][position]
    data = position_df.copy()
    columns = [val for val in subset_config["column_names"].keys()]
    labels = [val for val in subset_config["column_names"].values() if val != "data"]

    data = data.drop(columns=["year"])

    data = (
        data.groupby(["team", "player_name"])[columns]
        .mean()
        .reset_index()
    )

    
    data = data[["team", "player_name"]].join(
            data.drop(columns=["team", "player_name"]).rank(pct=True).round(2) * 100
        )

    # Only compute mean on the selected columns
    conference_avg = data[columns].mean().round(2)

    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=conference_avg.values,
            theta=labels,
            fill='toself',
            name='Big Ten Avg',
            line_color='rgba(179, 163, 105, 0.5)',
            fillcolor="rgba(179, 163, 105, 0.5)"
        )
    )

    if players:
        for player in players:
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
        radialaxis=dict(visible=True, range=[0, 100])
    ),
    margin=dict(t=80, b=80, l=100, r=100),  # add more space around
)
    return fig


# App layout
st.title("Vanderbilt Player Performance Charts")
st.header("For evaluating player performance in the SEC using percentile KPI metrics")



col1, col2 = st.columns(2)

for col, position in zip([col1, col2], ["Forwards", "Wingers"]):
    with col:
        st.header(position)
        options = ["Average"] + list(postional_subsets[position]["player_name"].unique())
        selected = st.multiselect(f"Select {position}", options=options, default=["Average"])
        fig = plot_radar([p for p in selected if p != "Average"], position, postional_subsets[position])
        st.plotly_chart(fig, use_container_width=True)

col3, col4 = st.columns(2)
for col, position in zip([col3, col4], ["Defensive Midfielders", "Central Midfielders"]):
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
