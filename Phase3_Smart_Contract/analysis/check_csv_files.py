import pandas as pd
import numpy as np
from decimal import Decimal, getcontext, ROUND_HALF_UP

# Constants
getcontext().prec = 78
TOKEN0_DECIMALS = 6
TOKEN1_DECIMALS = 18

def preprocess(df_input: pd.DataFrame) -> pd.DataFrame:
    df = df_input.copy()
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')

    numeric_cols = [
        'predictedPrice_api', 'actualPrice_pool', 'currentTick_pool',
        'finalTickLower_contract', 'finalTickUpper_contract',
        'gas_cost_eth', 'liquidity_contract', 'finalLiquidity_contract',
        'amount0_provided_to_mint', 'amount1_provided_to_mint',
        'initial_contract_balance_token0', 'initial_contract_balance_token1',
        'fees_collected_token0', 'fees_collected_token1',
        'range_width_multiplier_setting'
    ]
    for col in numeric_cols:
        if col in df.columns:
            # Convert to string first to handle potential scientific notation
            temp_series_str = df[col].astype(str)
            df[col] = pd.to_numeric(temp_series_str, errors='coerce')

    if 'liquidity_contract' not in df.columns and 'finalLiquidity_contract' in df.columns:
        df['liquidity_contract'] = df['finalLiquidity_contract']

    cols_to_fillna = numeric_cols + ['liquidity_contract']
    for col in cols_to_fillna:
        if col in df.columns:
            df[col] = df[col].fillna(0)
        else:
            df[col] = 0

    if 'timestamp' in df.columns:
        df = df.sort_values('timestamp').reset_index(drop=True)
    return df

def uni_tick_to_price(tick_val: float | str | Decimal) -> float | None:
    if not pd.notna(tick_val) or str(tick_val).strip() == "":
        return np.nan
    try:
        price = Decimal('1.0001') ** Decimal(str(tick_val))
        return float(price)
    except (ValueError, TypeError, OverflowError):
        return np.nan

def get_amounts_in_lp(liquidity: Decimal, current_tick: Decimal, lower_tick: Decimal, upper_tick: Decimal) -> tuple[int, int]:
    L = liquidity
    if not (pd.notna(float(current_tick)) and pd.notna(float(lower_tick)) and pd.notna(float(upper_tick))):
        return 0,0
    if L == 0: return 0, 0
    if lower_tick >= upper_tick: return 0,0
    try:
        sqrt_P_current = Decimal('1.0001')**(current_tick / Decimal('2'))
        sqrt_P_lower = Decimal('1.0001')**(lower_tick / Decimal('2'))
        sqrt_P_upper = Decimal('1.0001')**(upper_tick / Decimal('2'))
    except Exception:
        return 0,0
    amount0_in_lp = Decimal(0)
    amount1_in_lp = Decimal(0)
    if current_tick < lower_tick:
        amount0_in_lp = L * (Decimal(1) / sqrt_P_lower - Decimal(1) / sqrt_P_upper)
    elif current_tick >= upper_tick:
        amount1_in_lp = L * (sqrt_P_upper - sqrt_P_lower)
    else:
        amount0_in_lp = L * (Decimal(1) / sqrt_P_current - Decimal(1) / sqrt_P_upper)
        amount1_in_lp = L * (sqrt_P_current - sqrt_P_lower)
    return int(amount0_in_lp.to_integral_value(rounding=ROUND_HALF_UP)), \
           int(amount1_in_lp.to_integral_value(rounding=ROUND_HALF_UP))

def calculate_v_lp_usd(row: pd.Series) -> float:
    L_val = Decimal(str(row.get('finalLiquidity_contract', row.get('liquidity_contract', 0))))
    current_tick_val = row.get('currentTick_pool')
    lower_tick_for_lp_calc = row.get('finalTickLower_contract')
    upper_tick_for_lp_calc = row.get('finalTickUpper_contract')
    eth_price_usd_val = row.get('actualPrice_pool')

    if pd.isna(current_tick_val) or pd.isna(lower_tick_for_lp_calc) or pd.isna(upper_tick_for_lp_calc) or L_val == 0:
        return 0.0

    current_tick_dec = Decimal(str(current_tick_val))
    lower_tick_dec_lp = Decimal(str(lower_tick_for_lp_calc))
    upper_tick_dec_lp = Decimal(str(upper_tick_for_lp_calc))
    eth_price_usd = Decimal(str(eth_price_usd_val)) if pd.notna(eth_price_usd_val) and eth_price_usd_val!=0 else Decimal(0)

    amt0_lp, amt1_lp = get_amounts_in_lp(L_val, current_tick_dec, lower_tick_dec_lp, upper_tick_dec_lp)

    v_lp_token0_usd = (Decimal(str(amt0_lp)) / (Decimal('10')**TOKEN0_DECIMALS))
    v_lp_token1_usd = (Decimal(str(amt1_lp)) / (Decimal('10')**TOKEN1_DECIMALS)) * eth_price_usd
    v_lp_usd_calc = v_lp_token0_usd + v_lp_token1_usd
    return float(v_lp_usd_calc)

# Load the data (replace with actual paths to your uploaded files)
try:
    # مسیرهای صحیح فایل‌های CSV خود را در اینجا قرار دهید
    predictive_csv_path = r"D:\Uni-Dex-Marketplace_test\Phase3_Smart_Contract\position_results_predictive.csv"
    baseline_csv_path = r"D:\Uni-Dex-Marketplace_test\Phase3_Smart_Contract\position_results_baseline.csv"

    df_pred_new = pd.read_csv(predictive_csv_path)
    df_base_new = pd.read_csv(baseline_csv_path)
except Exception as e:
    print(f"Error loading CSV files: {e}")
    exit()


df_pred_processed = preprocess(df_pred_new)
df_base_processed = preprocess(df_base_new)

df_pred_processed['calc_lower_price'] = df_pred_processed['finalTickLower_contract'].apply(uni_tick_to_price)
df_pred_processed['calc_upper_price'] = df_pred_processed['finalTickUpper_contract'].apply(uni_tick_to_price)
df_base_processed['calc_lower_price'] = df_base_processed['finalTickLower_contract'].apply(uni_tick_to_price)
df_base_processed['calc_upper_price'] = df_base_processed['finalTickUpper_contract'].apply(uni_tick_to_price)

df_pred_processed['v_lp_usd_calc'] = df_pred_processed.apply(calculate_v_lp_usd, axis=1)
df_base_processed['v_lp_usd_calc'] = df_base_processed.apply(calculate_v_lp_usd, axis=1)

output_messages = []

def find_normal_section(df: pd.DataFrame, strategy_name: str, reasonable_price_upper_bound: float = 10000.0, reasonable_price_lower_bound: float = 100.0):
    output_messages.append(f"\n--- Analyzing {strategy_name} Data ---")
    
    cols_to_inspect = ['timestamp', 'actualPrice_pool', 
                       'finalTickLower_contract', 'finalTickUpper_contract', 
                       'calc_lower_price', 'calc_upper_price', 
                       'finalLiquidity_contract', 'liquidity_contract', 
                       'v_lp_usd_calc', 'range_width_multiplier_setting']
    
    # Ensure all columns to inspect exist
    existing_cols_to_inspect = [col for col in cols_to_inspect if col in df.columns]
    
    if df.empty:
        output_messages.append(f"{strategy_name} DataFrame is empty.")
        return

    output_messages.append(f"First 5 rows of relevant columns for {strategy_name}:")
    output_messages.append(df[existing_cols_to_inspect].head().to_string())
    output_messages.append(f"\nStats for 'calc_upper_price' in {strategy_name}:")
    output_messages.append(df['calc_upper_price'].describe(percentiles=[.01, .05, .25, .5, .75, .95, .99]).to_string())
    output_messages.append(f"\nStats for 'v_lp_usd_calc' in {strategy_name}:")
    output_messages.append(df['v_lp_usd_calc'].describe(percentiles=[.01, .05, .25, .5, .75, .95, .99]).to_string())
    if 'range_width_multiplier_setting' in df.columns:
        output_messages.append(f"\nValue counts for 'range_width_multiplier_setting' in {strategy_name}:")
        output_messages.append(df['range_width_multiplier_setting'].value_counts().to_string())


    # Criteria for "normal" data
    # 1. Calculated upper price is within a reasonable market range
    # 2. Calculated lower price is also within a reasonable market range and positive
    # 3. Liquidity is present
    # 4. v_lp_usd is positive (meaning LP has value)
    
    # Check if necessary columns exist before applying boolean indexing
    liquidity_col_present = ('finalLiquidity_contract' in df.columns and 'liquidity_contract' in df.columns)
    
    if 'calc_upper_price' in df.columns and 'calc_lower_price' in df.columns and liquidity_col_present:
        normal_conditions = (
            (df['calc_upper_price'] < reasonable_price_upper_bound) &
            (df['calc_upper_price'] > reasonable_price_lower_bound) & # Avoid extremely low upper prices
            (df['calc_lower_price'] < reasonable_price_upper_bound) & # Ensure lower also in range
            (df['calc_lower_price'] > 0) & # Ensure lower price is positive
            (df['calc_lower_price'] < df['calc_upper_price']) & # Ensure range is valid
            ((df['finalLiquidity_contract'] > 0) | (df['liquidity_contract'] > 0))
        )
        
        # v_lp_usd_calc > 0 is a good indicator, especially for predictive
        if strategy_name.lower().startswith("predictive"):
            normal_conditions &= (df['v_lp_usd_calc'] > 1.0) # Using 1.0 to avoid floating point noise near zero
        else: # For baseline, v_lp_usd should also ideally be positive
            normal_conditions &= (df['v_lp_usd_calc'] > 1.0)

        normal_section = df[normal_conditions]

        if not normal_section.empty:
            first_normal_index = normal_section.index.min()
            first_normal_timestamp = df.loc[first_normal_index, 'timestamp']
            rwm_at_normal = df.loc[first_normal_index, 'range_width_multiplier_setting'] if 'range_width_multiplier_setting' in df.columns else 'N/A'
            output_messages.append(
                f"\nFor {strategy_name}, data appears 'more normal' (reasonable price range, liquidity, and v_lp_usd > 1.0) starting around:"
            )
            output_messages.append(f"  Row index: {first_normal_index}")
            output_messages.append(f"  Timestamp: {first_normal_timestamp}")
            output_messages.append(f"  RangeWidthMultiplier at this point: {rwm_at_normal}")
            output_messages.append("\n  Sample of first few 'normal' rows:")
            output_messages.append(normal_section[existing_cols_to_inspect].head().to_string())
        else:
            output_messages.append(f"\nCould not find a 'normal' section in {strategy_name} data based on the defined criteria (calc price range [{reasonable_price_lower_bound}-{reasonable_price_upper_bound}], liquidity > 0, v_lp_usd_calc > 1.0).")
            output_messages.append("  This might be due to: ")
            output_messages.append(f"  1. All calculated price ranges from ticks being outside [{reasonable_price_lower_bound}-{reasonable_price_upper_bound}]. Current min/max calc_upper_price: {df['calc_upper_price'].min()}/{df['calc_upper_price'].max()}")
            output_messages.append(f"  2. Liquidity being zero in all rows that meet price criteria. Non-zero liquidity rows: {((df['finalLiquidity_contract'] > 0) | (df['liquidity_contract'] > 0)).sum()}")
            output_messages.append(f"  3. v_lp_usd_calc not being > 1.0 in rows meeting other criteria. Rows with v_lp_usd_calc > 1.0: {(df['v_lp_usd_calc'] > 1.0).sum()}")
    else:
        output_messages.append(f"Skipping normal section analysis for {strategy_name} due to missing critical columns for criteria.")

find_normal_section(df_pred_processed, "Predictive")
find_normal_section(df_base_processed, "Baseline")

print("\n".join(output_messages))