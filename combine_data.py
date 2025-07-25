
import zipfile
import re
import os
import yaml
import pandas as pd

def load_config():
    with open("config.yaml", "r") as file:
        return yaml.safe_load(file)
    
config = load_config()


def main():
    master = pd.DataFrame()

    for file in os.listdir("zips"):
        zip_path = os.path.join("zips", file)

        # Open the zip file
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # List all files in the archive
            for file_name in zip_ref.namelist():
                if file_name.startswith('SEC Players/') and file_name.endswith('.xlsx'):
                    player_name = file_name.split("stats")[-1].split(".xlsx")[0].strip().replace("copy", "")

                    with zip_ref.open(file_name) as file:
                        df = pd.read_excel(file)


                    df["home_team"] = df["Match"].str.split(" - ").apply(lambda x: x[0])
                    df["away_team"] = df["Match"].str.split(" - ").apply(lambda x: re.split(r'\d', x[-1], maxsplit=1)[0].strip()).str.replace("(P)", "").str.strip()
                    df["Date"] = pd.to_datetime(df["Date"], yearfirst=True)
                    df['year'] = df.Date.dt.year

                    for year in df["year"].unique():
                        df_sub = df[(df["Competition"].str.contains("NCAA")) & (df["year"] == year)]

                        if df_sub.empty:
                            continue
                        df_sub["team"] = pd.concat([df_sub['home_team'], df_sub['away_team']]).mode()[0]

                        df_sub["player_name"] = player_name

                        master = pd.concat([master, df_sub])
    master.columns = config["column_names"]
    master.to_csv("dash_data/test-sec-wsoc-combined.csv", index=False)

if __name__ == "__main__":
    main()
    print("Data combined and saved to dash_data/sec-wsoc-combined.csv")