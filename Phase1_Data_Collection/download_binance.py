import requests
import pandas as pd
import datetime
from tenacity import retry, stop_after_attempt, wait_fixed
from pathlib import Path
import pytz # For working with timezones

# --- Settings ---
SYMBOL = "ETHUSDT"
INTERVAL = "1h"
START_YEAR = 2018
DATA_DIR = Path("binance_data") # Folder name for storing data

# --- Create data folder if it doesn't exist ---
DATA_DIR.mkdir(exist_ok=True)

@retry(stop=stop_after_attempt(5), wait=wait_fixed(10))
def get_binance_data(symbol, interval, start_dt, end_dt):
    """Get historical K-line data from Binance."""
    url = "https://api.binance.com/api/v3/klines"

    # Convert dates to millisecond timestamp and UTC
    start_ts = int(start_dt.timestamp() * 1000)
    end_ts = int(end_dt.timestamp() * 1000)

    all_data = []
    current_start_ts = start_ts

    print(f"Getting {symbol} from {start_dt.strftime('%Y-%m-%d %H:%M:%S')} to {end_dt.strftime('%Y-%m-%d %H:%M:%S')}...")

    while current_start_ts < end_ts:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current_start_ts,
            "endTime": end_ts, # We can request until the end, Binance limits to 1000
            "limit": 1000
        }
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status() # Raise exception for bad status codes
            klines = response.json()

            if not klines:
                print("  No more data found for this period.")
                break # Exit loop if no data is returned

            all_data.extend(klines)
            # Update start time to the last candle's time + 1 millisecond
            current_start_ts = klines[-1][0] + 1
            print(f"    {len(klines)} candles received, new start: {pd.to_datetime(current_start_ts, unit='ms', utc=True).strftime('%Y-%m-%d %H:%M:%S')}")

        except requests.exceptions.RequestException as e:
            print(f"  Request failed: {e}. Retrying...")
            raise # Re-raise exception to activate retry

    if not all_data:
        return pd.DataFrame() # Return empty DataFrame if no data exists

    df = pd.DataFrame(all_data, columns=[
        "open_time", "open", "high", "low", "close", "volume", "close_time",
        "quote_asset_volume", "number_of_trades", "taker_buy_base_asset_volume",
        "taker_buy_quote_asset_volume", "ignore"
    ])

    df["open_time"] = pd.to_datetime(df["open_time"], unit='ms', utc=True) # Use UTC
    df.set_index("open_time", inplace=True)
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    # Remove potential duplicate data at the boundaries
    df = df[~df.index.duplicated(keep='first')]
    return df

def get_last_saved_timestamp(symbol):
    """Find the timestamp of the last saved data point."""
    files = sorted(DATA_DIR.glob(f'binance_data_{symbol}_*.csv'))

    # Ignore 'combined' files
    files = [f for f in files if "combined" not in f.name]

    if not files:
        return None

    last_file = files[-1]
    try:
        df = pd.read_csv(last_file, index_col="open_time", parse_dates=True)
        # Ensure the index is converted to UTC
        df.index = df.index.tz_localize('UTC') if df.index.tz is None else df.index.tz_convert('UTC')

        if not df.empty:
            # Return the timestamp of the *last* row + 1 millisecond
            return df.index[-1] + pd.Timedelta(milliseconds=1)
        else:
            return None
    except Exception as e:
        print(f"Error reading or processing {last_file}: {e}")
        return None

def save_data(df, symbol):
    """Save data to CSV files, named by year."""
    if df.empty:
        return

    # Group by year and save each year in a separate file
    for year, group_df in df.groupby(df.index.year):
        file_path = DATA_DIR / f'binance_data_{symbol}_{year}.csv'

        # Check for file existence and append/overwrite
        if file_path.exists():
            print(f"  Reading existing data for year {year}...")
            existing_df = pd.read_csv(file_path, index_col="open_time", parse_dates=True)
            # Ensure both indexes are converted to UTC
            existing_df.index = existing_df.index.tz_localize('UTC') if existing_df.index.tz is None else existing_df.index.tz_convert('UTC')
            group_df.index = group_df.index.tz_localize('UTC') if group_df.index.tz is None else group_df.index.tz_convert('UTC')

            combined_df = pd.concat([existing_df, group_df])
            # Remove duplicates, keeping the newest data
            combined_df = combined_df[~combined_df.index.duplicated(keep='last')]
            combined_df.sort_index(inplace=True)
        else:
            combined_df = group_df

        combined_df.to_csv(file_path)
        print(f"  Data saved/updated: {file_path}")

def update_binance_data(symbol, interval):
    """Download and update Binance data from 2018 to now."""
    utc = pytz.UTC
    # Define the absolute start date (January 1, 2018) as UTC
    start_date_abs = datetime.datetime(START_YEAR, 1, 1, tzinfo=utc)
    # Define the end date (now) as UTC
    end_date = datetime.datetime.now(utc)

    # Find the last saved timestamp
    last_timestamp = get_last_saved_timestamp(symbol)

    # Determine the start date for this download session
    start_date = last_timestamp if last_timestamp else start_date_abs

    # Ensure the start date is not after the end date
    if start_date >= end_date:
        print("Data is already up-to-date.")
        return

    print(f"Starting download from: {start_date.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Ending download at: {end_date.strftime('%Y-%m-%d %H:%M:%S')}")

    # Get new data
    new_data_df = get_binance_data(symbol, interval, start_date, end_date)

    if not new_data_df.empty:
        print(f"{len(new_data_df)} new data points downloaded.")
        # Save new data (append to yearly files)
        save_data(new_data_df, symbol)
    else:
        print("No new data was downloaded.")

def combine_yearly_data(symbol, data_dir):
    """Combines all yearly data files into a single CSV file."""
    print("\nStarting the process of combining yearly files...")
    files_to_combine = sorted(data_dir.glob(f'binance_data_{symbol}_*.csv'))

    # Remove 'combined' files from the list so they are not used in re-combination
    files_to_combine = [f for f in files_to_combine if "combined" not in f.name]

    if not files_to_combine:
        print("No data files found to combine.")
        return

    all_dfs = []
    for file in files_to_combine:
        try:
            print(f"  Reading: {file.name}")
            df = pd.read_csv(file, index_col="open_time", parse_dates=True)
            # Ensure the index is converted to UTC
            df.index = df.index.tz_localize('UTC') if df.index.tz is None else df.index.tz_convert('UTC')
            all_dfs.append(df)
        except Exception as e:
            print(f"    Error reading {file.name}: {e}")

    if not all_dfs:
        print("No data was read to combine.")
        return

    print("  Combining data...")
    combined_df = pd.concat(all_dfs)

    print("  Sorting and removing duplicates...")
    combined_df.sort_index(inplace=True)
    combined_df = combined_df[~combined_df.index.duplicated(keep='last')]

    # Create filename with the current date
    today_str = datetime.datetime.now().strftime("%Y%m%d")
    combined_file_name = data_dir / f'binance_data_{symbol}_combined_{today_str}.csv'

    print(f"  Saving combined file to: {combined_file_name}")
    combined_df.to_csv(combined_file_name)
    print(f"Combined file with {len(combined_df)} rows of data saved successfully.")

# --- Main Execution ---
if __name__ == "__main__":
    print("--- Starting Binance Data Download and Combination Script ---")

    # Step 1: Update yearly data
    update_binance_data(SYMBOL, INTERVAL)

    # Step 2: Combine yearly files into a single master file
    combine_yearly_data(SYMBOL, DATA_DIR)

    print("--- End of Script ---")