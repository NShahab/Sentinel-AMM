# README: Binance Historical Data Collection Script

This script facilitates downloading and updating cryptocurrency trading data (K-lines/Candlesticks) from the Binance API. It's designed to fetch data starting from a specific year, save it into yearly CSV files, and then combine them into a single, up-to-date dataset. It includes features for incremental updates and robust error handling.

## Features

1.  **Download Historical Data**: Fetches historical K-line data (Open, High, Low, Close, Volume - OHLCV) for a specified cryptocurrency symbol (e.g., `ETHUSDT`) and interval (e.g., `1h`).
2.  **Incremental Updates**: Automatically checks the last saved data point and only downloads *new* data since that time, making it efficient for regular updates.
3.  **Yearly Archiving**: Saves the downloaded data into separate CSV files for each year (e.g., `binance_data_ETHUSDT_2018.csv`, `binance_data_ETHUSDT_2019.csv`). This helps in managing large datasets.
4.  **Combined Dataset**: After updating, it combines all the yearly files into a single, comprehensive CSV file, named with the current date (e.g., `binance_data_ETHUSDT_combined_20231027.csv`).
5.  **Retry Mechanism**: Utilizes the `tenacity` library to automatically retry API requests in case of network issues or temporary API errors, enhancing reliability.
6.  **UTC Standardization**: All timestamps are handled and saved in Coordinated Universal Time (UTC) for consistency.
7.  **Customizable Parameters**: Easily configure the cryptocurrency `SYMBOL`, time `INTERVAL`, `START_YEAR`, and `DATA_DIR` (data directory) within the script.

## Dependencies

The script requires the following Python libraries:

* `requests`: For making HTTP requests to the Binance API.
* `pandas`: For data manipulation and saving/reading CSV files.
* `tenacity`: For implementing the retry logic.
* `pytz`: For handling timezones correctly, ensuring UTC.
* `pathlib`: For handling file paths in an OS-agnostic way (part of the standard library in Python 3.4+).
* `datetime`: For handling dates and times (part of the standard library).

You can install the necessary external libraries using pip:

```bash
pip install requests pandas tenacity pytz
## Configuration

Before running the script, you can adjust the following parameters in the "Settings" section:

*   `SYMBOL`: The trading pair you want to download (e.g., "BTCUSDT", "ETHUSDT").
*   `INTERVAL`: The K-line interval (e.g., "1m", "15m", "1h", "4h", "1d").
*   `START_YEAR`: The year from which you want to start downloading data if no data exists yet (e.g., 2018).
*   `DATA_DIR`: The name of the folder where the CSV files will be stored (e.g., `Path("binance_data")`).

## Usage

1.  **Save the code:** Save the provided Python script as a `.py` file (e.g., `download_binance.py`).
2.  **Install dependencies:** Run the `pip install` command shown above.
3.  **Configure (optional):** Edit the script to set your desired `SYMBOL`, `INTERVAL`, etc.
4.  **Run the script:** Open your terminal or command prompt, navigate to the directory where you saved the file, and run:

    ```bash
    python download_binance.py
    ```

The script will:

*   Create the data directory if it doesn't exist.
*   Check for existing data to determine the starting point.
*   Download new data in batches.
*   Save/update the yearly CSV files.
*   Create/update the combined CSV file.
*   Print progress messages to the console.

## File Structure

The script will create a folder (named as specified in `DATA_DIR`) containing:

*   **Yearly Files:** `binance_data_SYMBOL_YEAR.csv` (e.g., `binance_data_ETHUSDT_2018.csv`) - Each file contains data for one specific year.
*   **Combined File:** `binance_data_SYMBOL_combined_YYYYMMDD.csv` (e.g., `binance_data_ETHUSDT_combined_20231027.csv`) - A single file containing all data from the start year up to the latest downloaded point.

Each CSV file will have the `open_time` as the index (in UTC) and columns for `open`, `high`, `low`, `close`, and `volume`.