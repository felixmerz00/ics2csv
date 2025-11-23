import pandas as pd
import os
from pathlib import Path

# Read all csv files in a directory
# Loop through all csv files in directory
def read_csv_files(input_path: Path) -> pd.DataFrame:
    all_files = [f for f in list(input_path.iterdir()) if f.suffix == '.csv']
    li = []

    for filename in all_files:
        # header=0 to use the first row as header
        df = pd.read_csv(os.path.join(input_path, filename), header=0)
        li.append(df)

    return pd.concat(li, axis=0, ignore_index=True)


# Sort events by starting date and time
def sort_events_by_start_date_time(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(by=['Event Start Date'])
    return df


# Create one file per year and write all events of that year into the file
def write_csv_files_per_year(df: pd.DataFrame, output_path: Path):
    years = df['Event Start Date'].str[:4].unique()

    for year in years:
        df_year = df[df['Event Start Date'].str.startswith(year)]
        df_year.to_csv(output_path / f'events_{year}.csv', index=False)


input_path = Path('~/Downloads').expanduser()
output_path = input_path / "unique_events"
output_path.mkdir(exist_ok=True)
df = read_csv_files(input_path)   # Read data from all csv files
df = df.drop_duplicates()    # Remove duplicate events
df = sort_events_by_start_date_time(df)   # Sort events by starting date and time
write_csv_files_per_year(df, output_path)   # Write a csv file for year
