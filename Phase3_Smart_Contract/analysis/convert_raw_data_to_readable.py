import pandas as pd
import numpy as np
from decimal import Decimal, getcontext
from pathlib import Path

# --- Constants ---
# These can be changed for different token pairs (e.g., WBTC/USDC)
getcontext().prec = 78
TOKEN0_NAME = "USDC"
TOKEN1_NAME = "WETH"
TOKEN0_DECIMALS = 6
TOKEN1_DECIMALS = 18

# --- Live Prices (Can be updated for future runs) ---
TOKEN0_USD_PRICE = 1.00
TOKEN1_USD_PRICE = 2616.50  # Price used for the last calculation

# --- Conversion Functions ---
def tick_to_usd_price(tick_val: float | str | Decimal,
                      token0_decimals: int = TOKEN0_DECIMALS,
                      token1_decimals: int = TOKEN1_DECIMALS) -> float | None:
    """
    Converts a Uniswap V3 tick to a human-readable price of token1 in terms of token0.
    The formula for price based on a tick is: P(i) = 1.0001^i
    This function adjusts the price for the different decimal counts between the two tokens.
    """
    if not pd.notna(tick_val) or str(tick_val).strip() == "" or str(tick_val).strip().lower() == 'nan':
        return np.nan
    try:
        tick = Decimal(str(tick_val))
        # Formula: price = 1.0001^tick * (10^(decimals_token0 - decimals_token1))
        # We calculate the inverse price (token1/token0), so the formula is adjusted.
        numerator = Decimal('10') ** (token1_decimals - token0_decimals)
        denominator = Decimal('1.0001') ** tick
        if denominator == Decimal(0): return np.nan
        return float(numerator / denominator)
    except Exception:
        return np.nan

def amount_to_readable(amount_val: float | str | Decimal, decimals: int) -> float | None:
    """
    Converts a raw token amount to a human-readable format.
    Raw amounts are stored as integers in the smallest unit of the token (e.g., Wei for ETH).
    Formula: readable_amount = raw_amount / (10^decimals)
    """
    if not pd.notna(amount_val) or str(amount_val).strip() == "" or str(amount_val).strip().lower() == 'nan':
        return np.nan
    try:
        amount = Decimal(str(amount_val))
        return float(amount / (Decimal('10') ** decimals))
    except Exception:
        return np.nan

def format_and_round(df_series: pd.Series, round_digits: int) -> pd.Series:
    """Safely converts a pandas Series to a numeric type and rounds it."""
    s = pd.to_numeric(df_series.astype(str).str.replace(',', '', regex=False), errors='coerce')
    if pd.api.types.is_numeric_dtype(s):
        return s.round(round_digits)
    return df_series

def process_file(input_filepath: Path, output_filepath: Path, token0_price: float, token1_price: float):
    """Reads a CSV, converts data, calculates USD values, and saves a new CSV."""
    print(f"Processing {input_filepath} -> {output_filepath}...")
    try:
        df = pd.read_csv(input_filepath)
    except Exception as e:
        print(f"   ❌ Error reading {input_filepath}: {e}")
        return

    df_out = df.copy()

    # --- Tick to Price Conversion ---
    tick_columns_to_convert = [
        'currentTick_pool', 'finalTickLower_contract', 'finalTickUpper_contract', 'predictedTick_calculated'
    ]
    for col in tick_columns_to_convert:
        if col in df_out.columns:
            new_col_name = f'{col}_{TOKEN1_NAME}{TOKEN0_NAME}_price'
            df_out[new_col_name] = df_out[col].apply(tick_to_usd_price)
            df_out[new_col_name] = format_and_round(df_out[new_col_name], 4)

    # --- Amount to Readable and USD Value Conversion ---
    token_configs = [
        {'id': 0, 'name': TOKEN0_NAME, 'decimals': TOKEN0_DECIMALS, 'price': token0_price},
        {'id': 1, 'name': TOKEN1_NAME, 'decimals': TOKEN1_DECIMALS, 'price': token1_price}
    ]

    for config in token_configs:
        # Map raw column names to new, readable base names
        cols_to_convert = {
            f'amount{config["id"]}_provided_to_mint': f'amount_{config["name"]}_minted',
            f'initial_contract_balance_token{config["id"]}': f'initial_balance_{config["name"]}',
            f'fees_collected_token{config["id"]}': f'fees_{config["name"]}_collected'
        }

        for col, new_base_name in cols_to_convert.items():
            if col in df_out.columns:
                readable_col_name = f'{new_base_name}_readable'
                usd_col_name = f'{new_base_name}_usd'

                # Step 1: Calculate the human-readable amount from the raw integer amount
                df_out[readable_col_name] = df_out[col].apply(lambda x: amount_to_readable(x, config["decimals"]))
                
                # Apply specific rounding rules for readable amounts
                if 'fees' in readable_col_name:
                    df_out[readable_col_name] = format_and_round(df_out[readable_col_name], 8)
                else:
                    df_out[readable_col_name] = format_and_round(df_out[readable_col_name], 4)

                # Step 2: Calculate the USD value based on the readable amount and the token's price
                df_out[usd_col_name] = df_out[readable_col_name] * config['price']
                df_out[usd_col_name] = format_and_round(df_out[usd_col_name], 4)


    # --- Final Formatting for Other Columns ---
    price_cols_to_round = ['actualPrice_pool', 'predictedPrice_api']
    for col in price_cols_to_round:
        if col in df_out.columns:
            df_out[col] = pd.to_numeric(df_out[col], errors='coerce').round(4)
            
    if 'gas_cost_eth' in df_out.columns:
        df_out['gas_cost_eth'] = pd.to_numeric(df_out['gas_cost_eth'], errors='coerce').round(6)

    # --- Save the Final CSV File ---
    try:
        df_out.to_csv(output_filepath, index=False, encoding='utf-8')
        print(f"   ✅ Successfully created {output_filepath}")
    except Exception as e:
        print(f"   ❌ Error writing {output_filepath}: {e}")

# --- Main Execution Block ---
if __name__ == "__main__":
    # This setup allows the script to find the CSV files when run from the command line.
    try:
        script_path = Path(__file__).resolve()
        script_dir = script_path.parent
        # Assumes the input CSVs are in the parent directory of the script's directory
        csv_base_dir = script_dir.parent 
    except NameError:
        # Fallback for environments where __file__ is not defined (e.g., notebooks)
        script_dir = Path('.').resolve()
        csv_base_dir = script_dir
        print(f"Warning: __file__ not defined. Using CWD for script_dir: {script_dir}")

    # Define the input files and the names for their converted versions
    input_files_info = [
        {"original": "position_results_predictive.csv", "converted": "predictive_final.csv"},
        {"original": "position_results_baseline.csv", "converted": "baseline_final.csv"}
    ]

    # Define where to save the output files
    output_dir = script_dir / "processed_results"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Loop through the files and process them
    for file_info in input_files_info:
        original_file_path = csv_base_dir / file_info["original"]
        converted_file_path = output_dir / file_info["converted"]
        
        if original_file_path.exists():
            process_file(original_file_path, converted_file_path, TOKEN0_USD_PRICE, TOKEN1_USD_PRICE)
        else:
            print(f"   ❌ Input file not found: {original_file_path}")
    
    print("\nConversion process finished.")