import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import numpy as np
from pathlib import Path
import sys
from decimal import Decimal, getcontext, ROUND_HALF_UP

# --- 0. Setup output directory ---
try:
    script_path_for_plots = Path(__file__).resolve()
    script_dir_for_plots = script_path_for_plots.parent
except NameError:
    script_dir_for_plots = Path('.').resolve()
    print(f"Warning: __file__ not defined for plot path. Using current working directory: {script_dir_for_plots}")

plots_dir = script_dir_for_plots / "plots_results"
plots_dir.mkdir(parents=True, exist_ok=True)
print(f"Plots will be saved in: {plots_dir}")

# --- Constants for Price Calculation ---
getcontext().prec = 78
TOKEN0_DECIMALS = 6
TOKEN1_DECIMALS = 18
TOKEN0_NAME = "USDC" 
TOKEN1_NAME = "WETH"

# --- 1. Data Loading ---
# Load the CSV files directly
try:
    df_pred_input = pd.read_csv("predictive_final.csv")
    df_base_input = pd.read_csv("baseline_final.csv")
    print("✅ CSV Files loaded successfully.")
except FileNotFoundError as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ An unexpected error occurred while reading CSV files: {e}")
    sys.exit(1)

# --- 2. Data Preprocessing ---
def preprocess_df(df_input: pd.DataFrame) -> pd.DataFrame:
    df = df_input.copy()
    
    # Convert timestamp
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    
    # Ensure numeric columns
    numeric_cols = [
        'range_width_multiplier_setting', 'external_api_eth_price', 'actualPrice_pool', 
        'sqrtPriceX96_pool', 'currentTick_pool', 'targetTickLower_offchain', 'targetTickUpper_offchain',
        'initial_contract_balance_token0', 'initial_contract_balance_token1', 'currentTickLower_contract',
        'currentTickUpper_contract', 'currentLiquidity_contract', 'finalTickLower_contract',
        'finalTickUpper_contract', 'finalLiquidity_contract', 'amount0_provided_to_mint',
        'amount1_provided_to_mint', 'fees_collected_token0', 'fees_collected_token1',
        'gas_used', 'gas_cost_eth', 'currentTick_pool_WETHUSDC_price',
        'finalTickLower_contract_WETHUSDC_price', 'finalTickUpper_contract_WETHUSDC_price',
        'amount_USDC_minted_readable', 'amount_USDC_minted_usd', 'initial_balance_USDC_readable',
        'initial_balance_USDC_usd', 'fees_USDC_collected_readable', 'fees_USDC_collected_usd',
        'amount_WETH_minted_readable', 'amount_WETH_minted_usd', 'initial_balance_WETH_readable',
        'initial_balance_WETH_usd', 'fees_WETH_collected_readable', 'fees_WETH_collected_usd'
    ]
    
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    return df

df_pred_analyzed_input = preprocess_df(df_pred_input.copy())
df_base_analyzed_input = preprocess_df(df_base_input.copy())

sns.set_theme(style="whitegrid", palette="muted", font_scale=1.1)
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.max_open_warning'] = 50

# --- 3. Helper & Metric Functions ---
def tick_to_usd_price(tick_val: float | str | Decimal,
                      token0_decimals: int = TOKEN0_DECIMALS,
                      token1_decimals: int = TOKEN1_DECIMALS) -> float | None:
    if not pd.notna(tick_val) or str(tick_val).strip() == "" or str(tick_val).strip().lower() == 'nan':
        return np.nan
    try:
        tick = Decimal(str(tick_val))
        numerator = Decimal('10') ** (token1_decimals - token0_decimals)
        denominator = Decimal('1.0001') ** tick
        if denominator == Decimal(0): return np.nan
        return float(numerator / denominator)
    except Exception:
        return np.nan

def calculate_errors(y_true, y_pred):
    errors = y_true - y_pred
    mae = np.mean(np.abs(errors))
    y_true_safe = np.where(y_true == 0, 1e-9, y_true)
    mape = np.mean(np.abs(errors / y_true_safe)) * 100
    return errors, mae, mape

def get_amounts_in_lp(liquidity: Decimal, current_tick: Decimal, lower_tick: Decimal, upper_tick: Decimal) -> tuple[int, int]:
    L = liquidity
    if not (pd.notna(float(current_tick)) and pd.notna(float(lower_tick)) and pd.notna(float(upper_tick))): return 0,0
    if L == 0: return 0, 0
    if lower_tick >= upper_tick: return 0,0
    try:
        sqrt_P_current = Decimal('1.0001')**(current_tick / Decimal('2'))
        sqrt_P_lower = Decimal('1.0001')**(lower_tick / Decimal('2'))
        sqrt_P_upper = Decimal('1.0001')**(upper_tick / Decimal('2'))
    except Exception: return 0,0
    amount0_in_lp, amount1_in_lp = Decimal(0), Decimal(0)
    if current_tick < lower_tick:
        amount0_in_lp = L * (Decimal(1) / sqrt_P_lower - Decimal(1) / sqrt_P_upper)
    elif current_tick >= upper_tick:
        amount1_in_lp = L * (sqrt_P_upper - sqrt_P_lower)
    else:
        amount0_in_lp = L * (Decimal(1) / sqrt_P_current - Decimal(1) / sqrt_P_upper)
        amount1_in_lp = L * (sqrt_P_current - sqrt_P_lower)
    return int(amount0_in_lp.to_integral_value(rounding=ROUND_HALF_UP)), \
           int(amount1_in_lp.to_integral_value(rounding=ROUND_HALF_UP))

def analyze_data(df_input: pd.DataFrame, contract_type: str) -> tuple[dict, pd.DataFrame]:
    df = df_input.copy() 
    results = {}

    # --- is_in_range calculation ---
    price_range_lower_col = f'finalTickUpper_contract_{TOKEN1_NAME}{TOKEN0_NAME}_price' 
    price_range_upper_col = f'finalTickLower_contract_{TOKEN1_NAME}{TOKEN0_NAME}_price'

    if 'actualPrice_pool' in df.columns and \
       price_range_lower_col in df.columns and \
       price_range_upper_col in df.columns:
        
        price_range_lower_usd_series = df[price_range_lower_col]
        price_range_upper_usd_series = df[price_range_upper_col]
        valid_comparison = pd.notna(df['actualPrice_pool']) & pd.notna(price_range_lower_usd_series) & pd.notna(price_range_upper_usd_series)
        df['is_in_range'] = False 
        df.loc[valid_comparison, 'is_in_range'] = \
            (df.loc[valid_comparison, 'actualPrice_pool'] >= price_range_lower_usd_series[valid_comparison]) & \
            (df.loc[valid_comparison, 'actualPrice_pool'] <= price_range_upper_usd_series[valid_comparison])
        time_in_range_pct = df['is_in_range'].mean() * 100 if not df['is_in_range'].dropna().empty else 0.0
    else:
        print(f"Warning: Columns for is_in_range calc not found in {contract_type} data. Required: actualPrice_pool, {price_range_lower_col}, {price_range_upper_col}")
        df['is_in_range'] = False; time_in_range_pct = 0.0
    results['time_in_range_pct'] = time_in_range_pct
    
    # Prediction error metrics (only for Predictive strategy)
    if contract_type == 'Predictive':
        if 'actualPrice_pool' in df.columns and 'predictedPrice_api' in df.columns and not df.empty:
            valid_actual_prices = df['actualPrice_pool'][df['actualPrice_pool'] != 0]
            if not valid_actual_prices.empty:
                errors, mae, mape = calculate_errors(df['actualPrice_pool'], df['predictedPrice_api'])
                df['prediction_error_pct'] = np.where(df['actualPrice_pool'] != 0, (errors / df['actualPrice_pool']) * 100, 0.0)
                results['mae'] = mae; results['mape'] = mape
            else: df['prediction_error_pct'] = 0.0; results['mae'] = 0.0; results['mape'] = 0.0
        else: df['prediction_error_pct'] = 0.0; results['mae'] = 'N/A'; results['mape'] = 'N/A'
    
    # Initialize P&L columns
    pnl_cols = ['amount0_in_lp', 'amount1_in_lp', 'v_lp_usd', 'v_remaining_usd','v_current_total_usd', 
                'v_hodl_usd', 'il_usd', 'v_fees_usd','v_gas_usd', 'pnl_vs_hodl_usd', 'period_actual_pnl_usd',
                'value_lp_at_period_end_usd', 'pnl_lp_holding_period_usd','position_i_ended_in_range', 
                'net_pnl_period_usd']
    for col in pnl_cols:
        if col == 'position_i_ended_in_range': df[col] = pd.NA
        else: df[col] = 0.0

    # Calculate P&L metrics for each row
    for index, row in df.iterrows():
        try:
            # Get liquidity value
            l_val_str = "0"
            if contract_type == 'Predictive':
                l_val_str = str(row.get('liquidity_contract', '0'))
            elif contract_type == 'Baseline':
                l_val_str = str(row.get('finalLiquidity_contract', '0'))
            if not isinstance(l_val_str, str) or not l_val_str.strip() or l_val_str.lower() in ['none', 'nan']: 
                l_val_str = '0'
            try: L_val = Decimal(l_val_str)
            except: L_val = Decimal(0)

            # Get ticks and prices
            current_tick_val = row['currentTick_pool']
            lower_tick_for_lp_calc = row['finalTickLower_contract']
            upper_tick_for_lp_calc = row['finalTickUpper_contract']
            eth_price_usd_val = row['actualPrice_pool']
            
            current_tick_dec = Decimal(str(current_tick_val))
            lower_tick_dec_lp = Decimal(str(lower_tick_for_lp_calc))
            upper_tick_dec_lp = Decimal(str(upper_tick_for_lp_calc))
            eth_price_usd = Decimal(str(eth_price_usd_val)) if pd.notna(eth_price_usd_val) and eth_price_usd_val!=0 else Decimal(0)
            
            # Calculate amounts in LP
            amt0_lp, amt1_lp = 0,0
            if L_val > 0 and lower_tick_dec_lp < upper_tick_dec_lp:
                 amt0_lp, amt1_lp = get_amounts_in_lp(L_val, current_tick_dec, lower_tick_dec_lp, upper_tick_dec_lp)
            
            df.loc[index, 'amount0_in_lp'] = amt0_lp
            df.loc[index, 'amount1_in_lp'] = amt1_lp
            
            # Calculate LP value in USD
            v_lp_token0_usd = (Decimal(str(amt0_lp)) / (Decimal('10')**TOKEN0_DECIMALS))
            v_lp_token1_usd = (Decimal(str(amt1_lp)) / (Decimal('10')**TOKEN1_DECIMALS)) * eth_price_usd
            v_lp_usd_calc = v_lp_token0_usd + v_lp_token1_usd
            df.loc[index, 'v_lp_usd'] = float(v_lp_usd_calc)
            
            # Calculate remaining balance value
            bal0_before_mint_raw = Decimal(str(row.get('initial_contract_balance_token0',0)))
            bal1_before_mint_raw = Decimal(str(row.get('initial_contract_balance_token1',0)))
            amt0_minted_raw = Decimal(str(row.get('amount0_provided_to_mint',0)))
            amt1_minted_raw = Decimal(str(row.get('amount1_provided_to_mint',0)))
            
            remaining_token0_contract = bal0_before_mint_raw - amt0_minted_raw
            remaining_token1_contract = bal1_before_mint_raw - amt1_minted_raw
            
            v_remaining_token0_usd = (remaining_token0_contract / (Decimal('10')**TOKEN0_DECIMALS))
            v_remaining_token1_usd = (remaining_token1_contract / (Decimal('10')**TOKEN1_DECIMALS)) * eth_price_usd
            v_remaining_usd_calc = v_remaining_token0_usd + v_remaining_token1_usd
            df.loc[index, 'v_remaining_usd'] = float(v_remaining_usd_calc)
            
            # Current total value
            v_current_total_usd_calc = v_lp_usd_calc + v_remaining_usd_calc
            df.loc[index, 'v_current_total_usd'] = float(v_current_total_usd_calc)
            
            # HODL value
            v_hodl_token0_usd = (bal0_before_mint_raw / (Decimal('10')**TOKEN0_DECIMALS))
            v_hodl_token1_usd = (bal1_before_mint_raw / (Decimal('10')**TOKEN1_DECIMALS)) * eth_price_usd
            v_hodl_usd_calc = v_hodl_token0_usd + v_hodl_token1_usd
            df.loc[index, 'v_hodl_usd'] = float(v_hodl_usd_calc)
            
            # Impermanent loss
            il_usd_calc = v_hodl_usd_calc - v_current_total_usd_calc
            df.loc[index, 'il_usd'] = float(il_usd_calc)
            
            # Fees - using the actual fee values from the CSV
            fees_usdc = Decimal(str(row.get('fees_USDC_collected_usd', 0)))
            fees_weth = Decimal(str(row.get('fees_WETH_collected_usd', 0)))
            v_fees_usd_calc = fees_usdc + fees_weth
            df.loc[index, 'v_fees_usd'] = float(v_fees_usd_calc)
            
            # Gas costs
            gas_eth = Decimal(str(row.get('gas_cost_eth',0)))
            v_gas_usd_calc = gas_eth * eth_price_usd
            df.loc[index, 'v_gas_usd'] = float(v_gas_usd_calc)
            
            # P&L vs HODL
            pnl_vs_hodl_usd_calc = (v_current_total_usd_calc + v_fees_usd_calc) - v_hodl_usd_calc - v_gas_usd_calc
            df.loc[index, 'pnl_vs_hodl_usd'] = float(pnl_vs_hodl_usd_calc)
            
            # Period actual P&L
            if index == 0:
                df.loc[index, 'period_actual_pnl_usd'] = float(pnl_vs_hodl_usd_calc)
            else:
                v_current_total_usd_prev = Decimal(str(df.loc[index-1, 'v_current_total_usd']))
                current_gas_usd = Decimal(str(df.loc[index, 'v_gas_usd']))
                fees_this_period_usd = v_fees_usd_calc
                df.loc[index, 'period_actual_pnl_usd'] = float(v_current_total_usd_calc - v_current_total_usd_prev - current_gas_usd + fees_this_period_usd)
                
        except Exception as e:
            print(f"Error in main P&L loop for row {index}, contract {contract_type}: {e}.")
            for pnl_col_item_loop in pnl_cols:
                if pnl_col_item_loop == 'position_i_ended_in_range': 
                    df.loc[index, pnl_col_item_loop] = pd.NA
                else: 
                    df.loc[index, pnl_col_item_loop] = 0.0
    
    # Calculate holding period P&L
    if len(df) > 1:
        for i in range(len(df) - 1):
            try:
                # Get liquidity for this position
                l_i_loop_str = "0"
                row_i_data = df.loc[i]
                if contract_type == 'Predictive': 
                    l_i_loop_str = str(row_i_data.get('liquidity_contract', '0'))
                elif contract_type == 'Baseline': 
                    l_i_loop_str = str(row_i_data.get('finalLiquidity_contract', '0'))
                
                if not isinstance(l_i_loop_str, str) or not l_i_loop_str.strip() or l_i_loop_str.lower() in ['none', 'nan']: 
                    l_i_loop_str = '0'
                try: L_i_loop = Decimal(l_i_loop_str)
                except: L_i_loop = Decimal(0)

                if L_i_loop == Decimal(0):
                    df.loc[i, 'value_lp_at_period_end_usd'] = 0.0
                    df.loc[i, 'pnl_lp_holding_period_usd'] = 0.0
                    df.loc[i, 'position_i_ended_in_range'] = False
                    df.loc[i, 'net_pnl_period_usd'] = float(-Decimal(str(row_i_data.get('v_gas_usd',0))))
                    continue

                # Get ticks and prices for this position
                lower_tick_i_for_lp_calc_loop = row_i_data['finalTickLower_contract']
                upper_tick_i_for_lp_calc_loop = row_i_data['finalTickUpper_contract']
                v_lp_start_i_usd_val_loop = row_i_data['v_lp_usd']
                gas_cost_entry_i_usd_val_loop = row_i_data['v_gas_usd']
                
                # Get next row's data for end of period values
                row_i_plus_1_data = df.loc[i+1]
                current_tick_at_end_of_i_val_loop = row_i_plus_1_data['currentTick_pool']
                eth_price_at_end_of_i_val_loop = row_i_plus_1_data['actualPrice_pool']
                
                lower_tick_i_dec_lp_loop = Decimal(str(lower_tick_i_for_lp_calc_loop))
                upper_tick_i_dec_lp_loop = Decimal(str(upper_tick_i_for_lp_calc_loop))
                v_lp_start_i_usd_loop = Decimal(str(v_lp_start_i_usd_val_loop))
                gas_cost_entry_i_usd_loop = Decimal(str(gas_cost_entry_i_usd_val_loop))
                current_tick_at_end_of_i_dec_loop = Decimal(str(current_tick_at_end_of_i_val_loop))
                eth_price_at_end_of_i_loop = Decimal(str(eth_price_at_end_of_i_val_loop)) if pd.notna(eth_price_at_end_of_i_val_loop) and eth_price_at_end_of_i_val_loop!=0 else Decimal(0)
                
                # Calculate LP value at end of period
                amt0_lp_end_i, amt1_lp_end_i = 0,0
                if L_i_loop > 0 and lower_tick_i_dec_lp_loop < upper_tick_i_dec_lp_loop and eth_price_at_end_of_i_loop > 0:
                    amt0_lp_end_i, amt1_lp_end_i = get_amounts_in_lp(L_i_loop, current_tick_at_end_of_i_dec_loop, lower_tick_i_dec_lp_loop, upper_tick_i_dec_lp_loop)
                
                v_lp_end_i_token0_usd_loop = (Decimal(str(amt0_lp_end_i)) / (Decimal('10')**TOKEN0_DECIMALS))
                v_lp_end_i_token1_usd_loop = (Decimal(str(amt1_lp_end_i)) / (Decimal('10')**TOKEN1_DECIMALS)) * eth_price_at_end_of_i_loop
                v_lp_end_i_usd_calc_loop = v_lp_end_i_token0_usd_loop + v_lp_end_i_token1_usd_loop
                
                df.loc[i, 'value_lp_at_period_end_usd'] = float(v_lp_end_i_usd_calc_loop)
                
                # Holding period P&L
                pnl_lp_holding_calc_loop = v_lp_end_i_usd_calc_loop - v_lp_start_i_usd_loop
                df.loc[i, 'pnl_lp_holding_period_usd'] = float(pnl_lp_holding_calc_loop)
                
                # Net P&L for period
                df.loc[i, 'net_pnl_period_usd'] = float(pnl_lp_holding_calc_loop - gas_cost_entry_i_usd_loop)
                
                # Did position end in range?
                df.loc[i, 'position_i_ended_in_range'] = df.loc[i+1, 'is_in_range'] if 'is_in_range' in df.columns else False
                
            except Exception as e:
                print(f"Error in holding period P&L for row {i}, contract {contract_type}: {e}")
                df.loc[i, 'value_lp_at_period_end_usd'] = 0.0
                df.loc[i, 'pnl_lp_holding_period_usd'] = 0.0
                df.loc[i, 'position_i_ended_in_range'] = False
                df.loc[i, 'net_pnl_period_usd'] = float(-Decimal(str(df.loc[i].get('v_gas_usd',0))))
    
    # Handle last row
    if not df.empty:
        last_idx = len(df)-1
        df.loc[last_idx, 'net_pnl_period_usd'] = float(df.loc[last_idx, 'period_actual_pnl_usd']) if pd.notna(df.loc[last_idx, 'period_actual_pnl_usd']) else 0.0
        df.loc[last_idx, 'pnl_lp_holding_period_usd'] = 0.0
        df.loc[last_idx, 'value_lp_at_period_end_usd'] = float(df.loc[last_idx, 'v_lp_usd'])
        df.loc[last_idx, 'position_i_ended_in_range'] = pd.NA
    
    # Calculate cumulative values
    df['period_actual_pnl_usd'] = pd.to_numeric(df['period_actual_pnl_usd'], errors='coerce').fillna(0.0)
    df['net_pnl_period_usd'] = pd.to_numeric(df['net_pnl_period_usd'], errors='coerce').fillna(0.0)
    df['cumulative_actual_pnl_usd'] = df['period_actual_pnl_usd'].cumsum()
    df['cumulative_net_pnl_usd'] = df['net_pnl_period_usd'].cumsum()
    
    # Calculate rolling time in range
    df['rolling_tir'] = df['is_in_range'].rolling(window=5, min_periods=1).mean() * 100 
    
    # Populate results dictionary
    results['total_gas_cost_eth'] = df['gas_cost_eth'].sum()
    df['cumulative_gas_eth'] = df['gas_cost_eth'].cumsum()
    
    results['avg_v_lp_usd'] = df['v_lp_usd'].mean() if not df['v_lp_usd'].dropna().empty else 0.0
    results['final_v_lp_usd'] = df['v_lp_usd'].iloc[-1] if not df.empty and not df['v_lp_usd'].dropna().empty else 0.0
    results['total_il_usd'] = df['il_usd'].sum()
    results['avg_il_usd'] = df['il_usd'].mean() if not df['il_usd'].dropna().empty else 0.0
    results['total_fees_usd'] = df['v_fees_usd'].sum()
    results['total_gas_usd'] = df['v_gas_usd'].sum()
    results['total_pnl_vs_hodl_usd'] = df['pnl_vs_hodl_usd'].sum()
    results['final_cumulative_actual_pnl_usd'] = df['cumulative_actual_pnl_usd'].iloc[-1] if not df.empty and not df['cumulative_actual_pnl_usd'].dropna().empty else 0.0
    results['final_cumulative_net_pnl_usd'] = df['cumulative_net_pnl_usd'].iloc[-1] if not df.empty and not df['cumulative_net_pnl_usd'].dropna().empty else 0.0
    
    # Calculate % periods ended in range
    ended_in_range_series = df['position_i_ended_in_range'].iloc[:-1].dropna()
    if not ended_in_range_series.empty:
        if pd.api.types.is_object_dtype(ended_in_range_series) or pd.api.types.is_string_dtype(ended_in_range_series):
             ended_in_range_bool_series = ended_in_range_series.astype(str).str.lower().map({'true': True, 'false': False, 'nan': np.nan, '<na>': np.nan}).dropna().astype(bool)
        elif pd.api.types.is_numeric_dtype(ended_in_range_series): 
            ended_in_range_bool_series = ended_in_range_series.astype(bool)
        else: ended_in_range_bool_series = ended_in_range_series.astype(bool)
        if not ended_in_range_bool_series.empty: 
            results['percent_periods_ended_in_range'] = ended_in_range_bool_series.mean() * 100
        else: 
            results['percent_periods_ended_in_range'] = pd.NA
    else: 
        results['percent_periods_ended_in_range'] = pd.NA
    
    print(f"\n--- {contract_type} DataFrame Head (Post-Analysis) ---")
    cols_to_print = ['timestamp', 'actualPrice_pool','predictedPrice_api' if contract_type == 'Predictive' else '', 
                     f'finalTickLower_contract_{TOKEN1_NAME}{TOKEN0_NAME}_price', 
                     f'finalTickUpper_contract_{TOKEN1_NAME}{TOKEN0_NAME}_price', 
                     'liquidity_contract' if contract_type == 'Predictive' else 'finalLiquidity_contract', 
                     'v_lp_usd', 'is_in_range', 'v_fees_usd']
    cols_to_print = [col for col in cols_to_print if col in df.columns]
    print(df[cols_to_print].head())
    print(f"--- {contract_type} 'actualPrice_pool' Stats (Post-Analysis) ---")
    if 'actualPrice_pool' in df.columns: 
        print(df['actualPrice_pool'].describe())
    print("-----------------------------------------------------\n")
    
    return results, df

# --- تحلیل داده‌ها ---
results_pred, df_pred_analyzed = analyze_data(df_pred_analyzed_input.copy(), 'Predictive')
results_base, df_base_analyzed = analyze_data(df_base_analyzed_input.copy(), 'Baseline')

# --- 4. Create Summary DataFrame ---
summary_data = {
    'Metric': [
        'Time In Range (%)', 
        'Total Gas Cost (ETH)', 
        'Mean Absolute Error (MAE)', 
        'Mean Absolute Percentage Error (MAPE %)', 
        'Average LP Value (USD)', 
        'Final LP Value (USD)', 
        'Total Impermanent Loss (USD)', 
        'Average Impermanent Loss (USD)', 
        'Total Fees Earned (USD)', 
        'Total Gas Cost (USD)', 
        'Net P&L vs HODL (USD)', 
        'Final Cumulative Actual P&L (USD)', 
        '% Periods Ended In Range', 
        'Final Cumulative Net Holding P&L (USD)'
    ],
    'Predictive Strategy': [
        f"{results_pred.get('time_in_range_pct', 0):.2f}", 
        f"{results_pred.get('total_gas_cost_eth', 0):.6f}", 
        f"{results_pred.get('mae', 'N/A'):.2f}" if isinstance(results_pred.get('mae'), (int, float)) else 'N/A', 
        f"{results_pred.get('mape', 'N/A'):.2f}" if isinstance(results_pred.get('mape'), (int, float)) else 'N/A', 
        f"{results_pred.get('avg_v_lp_usd', 0):.2f}", 
        f"{results_pred.get('final_v_lp_usd', 0):.2f}", 
        f"{results_pred.get('total_il_usd', 0):.2f}", 
        f"{results_pred.get('avg_il_usd', 0):.2f}", 
        f"{results_pred.get('total_fees_usd', 0):.2f}", 
        f"{results_pred.get('total_gas_usd', 0):.2f}", 
        f"{results_pred.get('total_pnl_vs_hodl_usd', 0):.2f}", 
        f"{results_pred.get('final_cumulative_actual_pnl_usd', 0):.2f}", 
        f"{results_pred.get('percent_periods_ended_in_range', 'N/A'):.2f}" if pd.notna(results_pred.get('percent_periods_ended_in_range')) else 'N/A', 
        f"{results_pred.get('final_cumulative_net_pnl_usd', 0):.2f}"
    ],
    'Baseline Strategy': [
        f"{results_base.get('time_in_range_pct', 0):.2f}", 
        f"{results_base.get('total_gas_cost_eth', 0):.6f}", 
        'N/A', 
        'N/A', 
        f"{results_base.get('avg_v_lp_usd', 0):.2f}", 
        f"{results_base.get('final_v_lp_usd', 0):.2f}", 
        f"{results_base.get('total_il_usd', 0):.2f}", 
        f"{results_base.get('avg_il_usd', 0):.2f}", 
        f"{results_base.get('total_fees_usd', 0):.2f}", 
        f"{results_base.get('total_gas_usd', 0):.2f}", 
        f"{results_base.get('total_pnl_vs_hodl_usd', 0):.2f}", 
        f"{results_base.get('final_cumulative_actual_pnl_usd', 0):.2f}", 
        f"{results_base.get('percent_periods_ended_in_range', 'N/A'):.2f}" if pd.notna(results_base.get('percent_periods_ended_in_range')) else 'N/A', 
        f"{results_base.get('final_cumulative_net_pnl_usd', 0):.2f}"
    ]
}

summary_df = pd.DataFrame(summary_data)
print("--- Results Summary Table ---")
print(summary_df.to_string(index=False))
print("\nN/A = Not Applicable or Not Calculated for this strategy.")
print("Note on P&L metrics: 'Actual P&L' reflects overall portfolio value change including fees and gas. 'Net Holding P&L' focuses on the P&L from LP value changes minus gas for each position's holding period.")

# --- 5. Plotting Individual Charts ---
plot_figsize = (12, 7)
date_formatter = mdates.DateFormatter('%Y-%m-%d %H:%M')
thousands_formatter = plt.FuncFormatter(lambda x, p: format(int(x), ','))

# Plot 1: Predictive Strategy: Price & Liquidity Range
pred_lower_price_range_col = f'finalTickUpper_contract_{TOKEN1_NAME}{TOKEN0_NAME}_price'
pred_upper_price_range_col = f'finalTickLower_contract_{TOKEN1_NAME}{TOKEN0_NAME}_price'

if not df_pred_analyzed.empty and 'actualPrice_pool' in df_pred_analyzed.columns and \
   pred_lower_price_range_col in df_pred_analyzed.columns and \
   pred_upper_price_range_col in df_pred_analyzed.columns and \
   not df_pred_analyzed['actualPrice_pool'].isnull().all() and \
   ('timestamp' in df_pred_analyzed.columns and pd.api.types.is_datetime64_any_dtype(df_pred_analyzed['timestamp'])):

    fig1, ax1 = plt.subplots(figsize=plot_figsize)
    sns.lineplot(data=df_pred_analyzed, x='timestamp', y='actualPrice_pool', label='Actual Price', marker='.', markersize=8, ax=ax1, color='blue', zorder=2)
    if 'predictedPrice_api' in df_pred_analyzed.columns and not df_pred_analyzed['predictedPrice_api'].isnull().all():
        sns.lineplot(data=df_pred_analyzed, x='timestamp', y='predictedPrice_api', label='Predicted Price', marker='x', markersize=8, linestyle='--', ax=ax1, color='green', zorder=2)
    
    predictive_range_label_added = False
    for i, row in df_pred_analyzed.iterrows():
        actual_plot_lower_price = row.get(pred_lower_price_range_col)
        actual_plot_upper_price = row.get(pred_upper_price_range_col)
        
        if i < 5: 
            print(f"Plot01 - Row {i}: Using PreConverted Range -> PriceL={actual_plot_lower_price}, PriceU={actual_plot_upper_price}")

        if pd.notna(actual_plot_lower_price) and pd.notna(actual_plot_upper_price) and actual_plot_lower_price < actual_plot_upper_price:
            current_segment_label = "_no_legend_"
            if not predictive_range_label_added: 
                current_segment_label = 'Predictive Range'
                predictive_range_label_added = True
                
            t_start = row['timestamp']
            t_end = pd.NaT
            if i < len(df_pred_analyzed) - 1: 
                t_end = df_pred_analyzed.loc[i + 1, 'timestamp']
            else: 
                if len(df_pred_analyzed) > 1:
                    ts_current = df_pred_analyzed['timestamp'].iloc[-1]
                    ts_prev = df_pred_analyzed['timestamp'].iloc[-2]
                    if pd.api.types.is_datetime64_any_dtype(ts_current) and pd.api.types.is_datetime64_any_dtype(ts_prev):
                        prev_duration = ts_current - ts_prev
                        if prev_duration.total_seconds() > 0: 
                            t_end = t_start + prev_duration
                        else: 
                            t_end = t_start + pd.Timedelta(hours=1)
                    else: 
                        t_end = t_start + pd.Timedelta(hours=1) 
                else: 
                    t_end = t_start + pd.Timedelta(hours=1)
                    
            if pd.notna(t_start) and pd.notna(t_end) and t_start < t_end:
                ax1.fill_between([t_start, t_end], actual_plot_lower_price, actual_plot_upper_price,
                                 alpha=0.15, color='lightgreen', label=current_segment_label, zorder=1)
                                 
    ax1.set_title('Predictive Strategy: Price & Liquidity Range', weight='bold')
    ax1.set_xlabel('Time')
    ax1.set_ylabel('ETH Price (USD)')
    
    all_y_values_plot1 = []
    if 'actualPrice_pool' in df_pred_analyzed: 
        all_y_values_plot1.extend(df_pred_analyzed['actualPrice_pool'].dropna().tolist())
    if 'predictedPrice_api' in df_pred_analyzed: 
        all_y_values_plot1.extend(df_pred_analyzed['predictedPrice_api'].dropna().tolist())
    if pred_lower_price_range_col in df_pred_analyzed: 
        all_y_values_plot1.extend(df_pred_analyzed[pred_lower_price_range_col].dropna().tolist())
    if pred_upper_price_range_col in df_pred_analyzed: 
        all_y_values_plot1.extend(df_pred_analyzed[pred_upper_price_range_col].dropna().tolist())
    
    all_y_values_plot1_numeric = [val for val in all_y_values_plot1 if isinstance(val, (int, float)) and pd.notna(val) and not np.isinf(val)]
    if not all_y_values_plot1_numeric and 'actualPrice_pool' in df_pred_analyzed:
        all_y_values_plot1_numeric = [p for p in df_pred_analyzed['actualPrice_pool'].tolist() if pd.notna(p) and p > 0]

    if all_y_values_plot1_numeric:
        plot1_min_y = min(all_y_values_plot1_numeric) * 0.95
        plot1_max_y = max(all_y_values_plot1_numeric) * 1.05
        if plot1_min_y == plot1_max_y: 
            plot1_min_y = (plot1_min_y * 0.9) if plot1_min_y!=0 else -1
            plot1_max_y = (plot1_max_y * 1.1) if plot1_max_y!=0 else 1
        if plot1_min_y <= 0 and max(all_y_values_plot1_numeric) > 0: 
            plot1_min_y = 0
        elif plot1_min_y == 0 and plot1_max_y == 0: 
            plot1_min_y = -1
            plot1_max_y = 1
        if plot1_max_y <= plot1_min_y: 
            plot1_max_y = plot1_min_y + 100 
            
        ax1.set_ylim(plot1_min_y, plot1_max_y)
        print(f"Plot01 Y-axis limits set to: ({plot1_min_y:.2f}, {plot1_max_y:.2f})")
    else: 
        print("Plot01: Could not determine Y-axis limits from data.")
    
    ax1.legend()
    ax1.tick_params(axis='x', rotation=30)
    ax1.xaxis.set_major_formatter(date_formatter)
    fig1.tight_layout()
    plt.savefig(plots_dir / "01_predictive_price_liquidity.png", dpi=300)
    plt.close(fig1)
    print(f"Plot saved: {plots_dir / '01_predictive_price_liquidity.png'}")
else: 
    print("Skipping plot 01 due to data/timestamp/required_column issues.")

# Plot 2: Baseline Strategy: Price & Liquidity Range
base_lower_price_range_col = f'finalTickUpper_contract_{TOKEN1_NAME}{TOKEN0_NAME}_price'
base_upper_price_range_col = f'finalTickLower_contract_{TOKEN1_NAME}{TOKEN0_NAME}_price'

if not df_base_analyzed.empty and 'actualPrice_pool' in df_base_analyzed.columns and \
   base_lower_price_range_col in df_base_analyzed.columns and \
   base_upper_price_range_col in df_base_analyzed.columns and \
   not df_base_analyzed['actualPrice_pool'].isnull().all() and \
   ('timestamp' in df_base_analyzed.columns and pd.api.types.is_datetime64_any_dtype(df_base_analyzed['timestamp'])):
    
    fig2, ax2 = plt.subplots(figsize=plot_figsize)
    sns.lineplot(data=df_base_analyzed, x='timestamp', y='actualPrice_pool', label='Actual Price', marker='.', markersize=8, ax=ax2, color='blue', zorder=2)
    
    baseline_range_label_added = False
    for i, row in df_base_analyzed.iterrows():
        actual_plot_lower_price = row.get(base_lower_price_range_col)
        actual_plot_upper_price = row.get(base_upper_price_range_col)
        
        if i < 5: 
            print(f"Plot02 - Row {i}: Using PreConverted Range -> PriceL={actual_plot_lower_price}, PriceU={actual_plot_upper_price}")
            
        if pd.notna(actual_plot_lower_price) and pd.notna(actual_plot_upper_price) and actual_plot_lower_price < actual_plot_upper_price:
            current_segment_label = "_no_legend_"
            if not baseline_range_label_added: 
                current_segment_label = 'Baseline Range'
                baseline_range_label_added = True
                
            t_start = row['timestamp']
            t_end = pd.NaT
            if i < len(df_base_analyzed) - 1: 
                t_end = df_base_analyzed.loc[i + 1, 'timestamp']
            else:
                if len(df_base_analyzed) > 1:
                    ts_current_b = df_base_analyzed['timestamp'].iloc[-1]
                    ts_prev_b = df_base_analyzed['timestamp'].iloc[-2]
                    if pd.api.types.is_datetime64_any_dtype(ts_current_b) and pd.api.types.is_datetime64_any_dtype(ts_prev_b):
                        prev_duration = ts_current_b - ts_prev_b
                        if prev_duration.total_seconds() > 0: 
                            t_end = t_start + prev_duration
                        else: 
                            t_end = t_start + pd.Timedelta(hours=1)
                    else: 
                        t_end = t_start + pd.Timedelta(hours=1)
                else: 
                    t_end = t_start + pd.Timedelta(hours=1)
                    
            if pd.notna(t_start) and pd.notna(t_end) and t_start < t_end:
                ax2.fill_between([t_start, t_end], actual_plot_lower_price, actual_plot_upper_price, 
                                 alpha=0.2, color='moccasin', label=current_segment_label, zorder=1)
    
    ax2.set_title('Baseline Strategy: Price & Liquidity Range', weight='bold')
    ax2.set_xlabel('Time')
    ax2.set_ylabel('ETH Price (USD)')
    
    all_y_values_plot2 = []
    if 'actualPrice_pool' in df_base_analyzed: 
        all_y_values_plot2.extend(df_base_analyzed['actualPrice_pool'].dropna().tolist())
    if base_lower_price_range_col in df_base_analyzed: 
        all_y_values_plot2.extend(df_base_analyzed[base_lower_price_range_col].dropna().tolist())
    if base_upper_price_range_col in df_base_analyzed: 
        all_y_values_plot2.extend(df_base_analyzed[base_upper_price_range_col].dropna().tolist())
    
    all_y_values_plot2_numeric = [val for val in all_y_values_plot2 if isinstance(val, (int, float)) and pd.notna(val) and not np.isinf(val)]
    if not all_y_values_plot2_numeric and 'actualPrice_pool' in df_base_analyzed:
        all_y_values_plot2_numeric = [p for p in df_base_analyzed['actualPrice_pool'].tolist() if pd.notna(p) and p > 0]
    
    if all_y_values_plot2_numeric:
        plot2_min_y = min(all_y_values_plot2_numeric) * 0.95
        plot2_max_y = max(all_y_values_plot2_numeric) * 1.05
        if plot2_min_y == plot2_max_y: 
            plot2_min_y = (plot2_min_y * 0.9) if plot2_min_y!=0 else -1
            plot2_max_y = (plot2_max_y * 1.1) if plot2_max_y!=0 else 1
        if plot2_min_y <= 0 and max(all_y_values_plot2_numeric) > 0: 
            plot2_min_y = 0
        if plot2_max_y <= plot2_min_y: 
            plot2_max_y = plot2_min_y + 100
        if plot2_min_y == 0 and plot2_max_y == 0 and len(all_y_values_plot2_numeric) > 0: 
            plot2_min_y = -1
            plot2_max_y = 1
        elif plot2_min_y == 0 and plot2_max_y == 0: 
            plot2_min_y = -1
            plot2_max_y = 1
            
        ax2.set_ylim(plot2_min_y, plot2_max_y)
        print(f"Plot02 Y-axis limits set to: ({plot2_min_y:.2f}, {plot2_max_y:.2f})")
    else: 
        print("Plot02: Could not determine Y-axis limits from data.")
    
    ax2.legend()
    ax2.tick_params(axis='x', rotation=30)
    ax2.xaxis.set_major_formatter(date_formatter)
    fig2.tight_layout()
    plt.savefig(plots_dir / "02_baseline_price_liquidity.png", dpi=300)
    plt.close(fig2)
    print(f"Plot saved: {plots_dir / '02_baseline_price_liquidity.png'}")
else: 
    print("Skipping plot 02 due to data/timestamp/required_column issues.")

# Plot 3: Prediction Error Over Time
if 'prediction_error_pct' in df_pred_analyzed.columns and not df_pred_analyzed['prediction_error_pct'].dropna().empty:
    if not pd.api.types.is_datetime64_any_dtype(df_pred_analyzed['timestamp']): 
        df_pred_analyzed['timestamp'] = pd.to_datetime(df_pred_analyzed['timestamp'], errors='coerce')
    if pd.api.types.is_datetime64_any_dtype(df_pred_analyzed['timestamp']):
        fig3, ax3 = plt.subplots(figsize=plot_figsize)
        sns.lineplot(data=df_pred_analyzed, x='timestamp', y='prediction_error_pct', ax=ax3, color='r', label='Instantaneous Error (%)')
        ax3.axhline(0, color='grey', linestyle='--')
        
        mape_val = results_pred.get('mape', 'N/A')
        mape_display_str = f"{mape_val:.2f}%" if isinstance(mape_val, (float, int)) else "N/A"
        ax3.set_title(f"Prediction Error Over Time (MAPE: {mape_display_str})", weight='bold')
        ax3.tick_params(axis='x', rotation=30)
        
        non_empty_errors = df_pred_analyzed['prediction_error_pct'].dropna()
        if not non_empty_errors.empty:
            ax3_hist = ax3.inset_axes([0.65, 0.65, 0.3, 0.3])
            sns.histplot(non_empty_errors, bins=10, kde=False, ax=ax3_hist, color='r', alpha=0.6)
            ax3_hist.set_title('Error Distribution', fontsize=9)
        
        ax3.set_xlabel('Time')
        ax3.set_ylabel('Prediction Error (%)')
        ax3.xaxis.set_major_formatter(date_formatter)
        fig3.tight_layout()
        plt.savefig(plots_dir / "03_prediction_error.png", dpi=300)
        plt.close(fig3)
        print(f"Plot saved: {plots_dir / '03_prediction_error.png'}")
    else: 
        print("Skipping plot 03 due to timestamp issues in df_pred_analyzed.")
else: 
    print("Skipping plot 03: Prediction error data not available/empty in df_pred_analyzed.")

# Plot 4: Actual Price vs. Predicted Price
if 'actualPrice_pool' in df_pred_analyzed.columns and 'predictedPrice_api' in df_pred_analyzed.columns and not df_pred_analyzed[['actualPrice_pool', 'predictedPrice_api']].dropna(how='all').empty:
    fig4, ax4 = plt.subplots(figsize=(8,8))
    plot_data_scatter = df_pred_analyzed[['actualPrice_pool', 'predictedPrice_api']].dropna()
    
    if not plot_data_scatter.empty:
        sns.scatterplot(data=plot_data_scatter, x='actualPrice_pool', y='predictedPrice_api', ax=ax4, s=100, alpha=0.7, label='Predictions')
        
        min_val_actual = plot_data_scatter['actualPrice_pool'].min()
        max_val_actual = plot_data_scatter['actualPrice_pool'].max()
        min_val_pred = plot_data_scatter['predictedPrice_api'].min()
        max_val_pred = plot_data_scatter['predictedPrice_api'].max()
        
        if pd.notna(min_val_actual) and pd.notna(max_val_actual) and pd.notna(min_val_pred) and pd.notna(max_val_pred):
            overall_min = min(min_val_actual, min_val_pred)
            overall_max = max(max_val_actual, max_val_pred)
            
            if overall_min != overall_max:
                lims = [overall_min, overall_max]
                ax4.plot(lims, lims, 'k--', alpha=0.75, zorder=0, label='Ideal Prediction')
            else:
                offset = abs(overall_min * 0.1) if overall_min != 0 else 1
                ax4.plot([overall_min - offset, overall_max + offset], [overall_min - offset, overall_max + offset], 'k--', alpha=0.75, zorder=0, label='Ideal Prediction')
        
        ax4.set_title('Actual Price vs. Predicted Price', weight='bold')
        ax4.set_xlabel('Actual Price (USD)')
        ax4.set_ylabel('Predicted Price (USD)')
        ax4.legend()
        ax4.set_aspect('equal', adjustable='box')
        fig4.tight_layout()
        plt.savefig(plots_dir / "04_actual_vs_predicted_price.png", dpi=300)
        plt.close(fig4)
        print(f"Plot saved: {plots_dir / '04_actual_vs_predicted_price.png'}")
    else:
        plt.close(fig4)
        print("Skipping plot 04: No valid data points for scatter plot.")
else:
    print("Skipping plot 04: Price data not available in df_pred_analyzed.")

# Plot 5: Rolling Time-In-Range (%)
fig5, ax5 = plt.subplots(figsize=plot_figsize)
plot_5_drawn = False

if 'rolling_tir' in df_pred_analyzed.columns and not df_pred_analyzed['rolling_tir'].dropna().empty:
    if not pd.api.types.is_datetime64_any_dtype(df_pred_analyzed['timestamp']): 
        df_pred_analyzed['timestamp'] = pd.to_datetime(df_pred_analyzed['timestamp'], errors='coerce')
    if pd.api.types.is_datetime64_any_dtype(df_pred_analyzed['timestamp']): 
        sns.lineplot(data=df_pred_analyzed, x='timestamp', y='rolling_tir', label='Predictive', marker='.', ax=ax5)
        plot_5_drawn = True

if 'rolling_tir' in df_base_analyzed.columns and not df_base_analyzed['rolling_tir'].dropna().empty:
    if not pd.api.types.is_datetime64_any_dtype(df_base_analyzed['timestamp']): 
        df_base_analyzed['timestamp'] = pd.to_datetime(df_base_analyzed['timestamp'], errors='coerce')
    if pd.api.types.is_datetime64_any_dtype(df_base_analyzed['timestamp']): 
        sns.lineplot(data=df_base_analyzed, x='timestamp', y='rolling_tir', label='Baseline', marker='.', ax=ax5)
        plot_5_drawn = True

if plot_5_drawn:
    ax5.axhline(results_pred.get('time_in_range_pct', 0), linestyle='--', color='green', alpha=0.5, 
                label=f"Predictive Avg ({results_pred.get('time_in_range_pct', 0):.1f}%)")
    ax5.axhline(results_base.get('time_in_range_pct', 0), linestyle='--', color='orange', alpha=0.5, 
                label=f"Baseline Avg ({results_base.get('time_in_range_pct', 0):.1f}%)")
    
    ax5.set_title('Rolling Time-In-Range (%)', weight='bold')
    ax5.set_xlabel('Time')
    ax5.set_ylabel('TIR (%)')
    ax5.set_ylim(0, 105)
    ax5.legend()
    ax5.tick_params(axis='x', rotation=30)
    ax5.xaxis.set_major_formatter(date_formatter)
    fig5.tight_layout()
    plt.savefig(plots_dir / "05_rolling_time_in_range.png", dpi=300)
    plt.close(fig5)
    print(f"Plot saved: {plots_dir / '05_rolling_time_in_range.png'}")
else:
    plt.close(fig5)
    print("Skipping plot 05.")

# Plot 6: Cumulative Gas Costs (ETH)
fig6, ax6 = plt.subplots(figsize=plot_figsize)
plot_6_drawn = False

if 'cumulative_gas_eth' in df_pred_analyzed.columns and not df_pred_analyzed['cumulative_gas_eth'].dropna().empty:
    if not pd.api.types.is_datetime64_any_dtype(df_pred_analyzed['timestamp']): 
        df_pred_analyzed['timestamp'] = pd.to_datetime(df_pred_analyzed['timestamp'], errors='coerce')
    if pd.api.types.is_datetime64_any_dtype(df_pred_analyzed['timestamp']): 
        sns.lineplot(data=df_pred_analyzed, x='timestamp', y='cumulative_gas_eth', label='Predictive', marker='.', ax=ax6)
        plot_6_drawn = True

if 'cumulative_gas_eth' in df_base_analyzed.columns and not df_base_analyzed['cumulative_gas_eth'].dropna().empty:
    if not pd.api.types.is_datetime64_any_dtype(df_base_analyzed['timestamp']): 
        df_base_analyzed['timestamp'] = pd.to_datetime(df_base_analyzed['timestamp'], errors='coerce')
    if pd.api.types.is_datetime64_any_dtype(df_base_analyzed['timestamp']): 
        sns.lineplot(data=df_base_analyzed, x='timestamp', y='cumulative_gas_eth', label='Baseline', marker='.', ax=ax6)
        plot_6_drawn = True

if plot_6_drawn:
    ax6.set_title('Cumulative Gas Costs (ETH)', weight='bold')
    ax6.set_xlabel('Time')
    ax6.set_ylabel('Total Gas Cost (ETH)')
    ax6.legend()
    ax6.tick_params(axis='x', rotation=30)
    ax6.xaxis.set_major_formatter(date_formatter)
    fig6.tight_layout()
    plt.savefig(plots_dir / "06_cumulative_gas_costs_eth.png", dpi=300)
    plt.close(fig6)
    print(f"Plot saved: {plots_dir / '06_cumulative_gas_costs_eth.png'}")
else:
    plt.close(fig6)
    print("Skipping plot 06.")

# Plot 7: LP Position Value (USD)
fig7, ax7 = plt.subplots(figsize=plot_figsize)
plot_7_drawn = False

if 'v_lp_usd' in df_pred_analyzed.columns and not df_pred_analyzed['v_lp_usd'].dropna().empty:
    if not pd.api.types.is_datetime64_any_dtype(df_pred_analyzed['timestamp']): 
        df_pred_analyzed['timestamp'] = pd.to_datetime(df_pred_analyzed['timestamp'], errors='coerce')
    if pd.api.types.is_datetime64_any_dtype(df_pred_analyzed['timestamp']): 
        sns.lineplot(data=df_pred_analyzed, x='timestamp', y='v_lp_usd', label='Predictive LP Value (USD)', marker='.', ax=ax7, color='purple')
        plot_7_drawn = True

if 'v_lp_usd' in df_base_analyzed.columns and not df_base_analyzed['v_lp_usd'].dropna().empty:
    if not pd.api.types.is_datetime64_any_dtype(df_base_analyzed['timestamp']): 
        df_base_analyzed['timestamp'] = pd.to_datetime(df_base_analyzed['timestamp'], errors='coerce')
    if pd.api.types.is_datetime64_any_dtype(df_base_analyzed['timestamp']): 
        sns.lineplot(data=df_base_analyzed, x='timestamp', y='v_lp_usd', label='Baseline LP Value (USD)', marker='.', ax=ax7, color='brown')
        plot_7_drawn = True

if plot_7_drawn:
    ax7.set_title('LP Position Value Over Time (USD)', weight='bold')
    ax7.set_xlabel('Time')
    ax7.set_ylabel('LP Value (USD)')
    ax7.legend()
    ax7.tick_params(axis='x', rotation=30)
    ax7.yaxis.set_major_formatter(thousands_formatter)
    ax7.xaxis.set_major_formatter(date_formatter)
    fig7.tight_layout()
    plt.savefig(plots_dir / "07_lp_value_over_time.png", dpi=300)
    plt.close(fig7)
    print(f"Plot saved: {plots_dir / '07_lp_value_over_time.png'}")
else:
    plt.close(fig7)
    print("Skipping plot 07.")

# Plot 8: Impermanent Loss (USD)
fig8, ax8 = plt.subplots(figsize=plot_figsize)
plot_8_drawn = False

if 'il_usd' in df_pred_analyzed.columns and not df_pred_analyzed['il_usd'].dropna().empty:
    if not pd.api.types.is_datetime64_any_dtype(df_pred_analyzed['timestamp']): 
        df_pred_analyzed['timestamp'] = pd.to_datetime(df_pred_analyzed['timestamp'], errors='coerce')
    if pd.api.types.is_datetime64_any_dtype(df_pred_analyzed['timestamp']): 
        sns.lineplot(data=df_pred_analyzed, x='timestamp', y='il_usd', label='Predictive IL (USD)', marker='.', ax=ax8, color='cyan')
        plot_8_drawn = True

if 'il_usd' in df_base_analyzed.columns and not df_base_analyzed['il_usd'].dropna().empty:
    if not pd.api.types.is_datetime64_any_dtype(df_base_analyzed['timestamp']): 
        df_base_analyzed['timestamp'] = pd.to_datetime(df_base_analyzed['timestamp'], errors='coerce')
    if pd.api.types.is_datetime64_any_dtype(df_base_analyzed['timestamp']): 
        sns.lineplot(data=df_base_analyzed, x='timestamp', y='il_usd', label='Baseline IL (USD)', marker='.', ax=ax8, color='magenta')
        plot_8_drawn = True

if plot_8_drawn:
    ax8.set_title('Impermanent Loss Over Time (USD)', weight='bold')
    ax8.set_xlabel('Time')
    ax8.set_ylabel('Impermanent Loss (USD)')
    ax8.axhline(0, color='grey', linestyle='--')
    ax8.legend()
    ax8.tick_params(axis='x', rotation=30)
    ax8.yaxis.set_major_formatter(thousands_formatter)
    ax8.xaxis.set_major_formatter(date_formatter)
    fig8.tight_layout()
    plt.savefig(plots_dir / "08_impermanent_loss_over_time.png", dpi=300)
    plt.close(fig8)
    print(f"Plot saved: {plots_dir / '08_impermanent_loss_over_time.png'}")
else:
    plt.close(fig8)
    print("Skipping plot 08.")

# Plot 9: P&L vs HODL (USD)
fig9, ax9 = plt.subplots(figsize=plot_figsize)
plot_9_drawn = False

if 'pnl_vs_hodl_usd' in df_pred_analyzed.columns and not df_pred_analyzed['pnl_vs_hodl_usd'].dropna().empty:
    if not pd.api.types.is_datetime64_any_dtype(df_pred_analyzed['timestamp']): 
        df_pred_analyzed['timestamp'] = pd.to_datetime(df_pred_analyzed['timestamp'], errors='coerce')
    if pd.api.types.is_datetime64_any_dtype(df_pred_analyzed['timestamp']): 
        sns.lineplot(data=df_pred_analyzed, x='timestamp', y='pnl_vs_hodl_usd', label='Predictive P&L vs HODL (USD)', marker='.', ax=ax9, color='lime')
        plot_9_drawn = True

if 'pnl_vs_hodl_usd' in df_base_analyzed.columns and not df_base_analyzed['pnl_vs_hodl_usd'].dropna().empty:
    if not pd.api.types.is_datetime64_any_dtype(df_base_analyzed['timestamp']): 
        df_base_analyzed['timestamp'] = pd.to_datetime(df_base_analyzed['timestamp'], errors='coerce')
    if pd.api.types.is_datetime64_any_dtype(df_base_analyzed['timestamp']): 
        sns.lineplot(data=df_base_analyzed, x='timestamp', y='pnl_vs_hodl_usd', label='Baseline P&L vs HODL (USD)', marker='.', ax=ax9, color='red')
        plot_9_drawn = True

if plot_9_drawn:
    ax9.set_title('Net P&L vs HODL Per Period (USD)', weight='bold')
    ax9.set_xlabel('Time')
    ax9.set_ylabel('P&L vs HODL / Period (USD)')
    ax9.axhline(0, color='grey', linestyle='--')
    ax9.legend()
    ax9.tick_params(axis='x', rotation=30)
    ax9.yaxis.set_major_formatter(thousands_formatter)
    ax9.xaxis.set_major_formatter(date_formatter)
    fig9.tight_layout()
    plt.savefig(plots_dir / "09_pnl_vs_hodl_per_period.png", dpi=300)
    plt.close(fig9)
    print(f"Plot saved: {plots_dir / '09_pnl_vs_hodl_per_period.png'}")
else:
    plt.close(fig9)
    print("Skipping plot 09.")

# Plot 10: Cumulative Actual P&L (USD)
fig10, ax10 = plt.subplots(figsize=plot_figsize)
plot_10_drawn = False

if 'cumulative_actual_pnl_usd' in df_pred_analyzed.columns and not df_pred_analyzed['cumulative_actual_pnl_usd'].dropna().empty:
    if not pd.api.types.is_datetime64_any_dtype(df_pred_analyzed['timestamp']): 
        df_pred_analyzed['timestamp'] = pd.to_datetime(df_pred_analyzed['timestamp'], errors='coerce')
    if pd.api.types.is_datetime64_any_dtype(df_pred_analyzed['timestamp']): 
        sns.lineplot(data=df_pred_analyzed, x='timestamp', y='cumulative_actual_pnl_usd', label='Predictive Cum. Actual P&L (USD)', marker='.', ax=ax10, color='navy')
        plot_10_drawn = True

if 'cumulative_actual_pnl_usd' in df_base_analyzed.columns and not df_base_analyzed['cumulative_actual_pnl_usd'].dropna().empty:
    if not pd.api.types.is_datetime64_any_dtype(df_base_analyzed['timestamp']): 
        df_base_analyzed['timestamp'] = pd.to_datetime(df_base_analyzed['timestamp'], errors='coerce')
    if pd.api.types.is_datetime64_any_dtype(df_base_analyzed['timestamp']): 
        sns.lineplot(data=df_base_analyzed, x='timestamp', y='cumulative_actual_pnl_usd', label='Baseline Cum. Actual P&L (USD)', marker='.', ax=ax10, color='saddlebrown')
        plot_10_drawn = True

if plot_10_drawn:
    ax10.set_title('Cumulative Actual P&L (Portfolio Value Change - Gas + Fees)', weight='bold')
    ax10.set_xlabel('Time')
    ax10.set_ylabel('Cumulative Actual P&L (USD)')
    ax10.axhline(0, color='grey', linestyle='--')
    ax10.legend()
    ax10.tick_params(axis='x', rotation=30)
    ax10.yaxis.set_major_formatter(thousands_formatter)
    ax10.xaxis.set_major_formatter(date_formatter)
    fig10.tight_layout()
    plt.savefig(plots_dir / "10_cumulative_actual_pnl.png", dpi=300)
    plt.close(fig10)
    print(f"Plot saved: {plots_dir / '10_cumulative_actual_pnl.png'}")
else:
    plt.close(fig10)
    print("Skipping plot 10.")

# Plot 11: Cumulative Net Holding P&L (USD)
fig11, ax11 = plt.subplots(figsize=plot_figsize)
plot_11_drawn = False

if 'cumulative_net_pnl_usd' in df_pred_analyzed.columns and not df_pred_analyzed['cumulative_net_pnl_usd'].dropna().empty:
    if not pd.api.types.is_datetime64_any_dtype(df_pred_analyzed['timestamp']): 
        df_pred_analyzed['timestamp'] = pd.to_datetime(df_pred_analyzed['timestamp'], errors='coerce')
    if pd.api.types.is_datetime64_any_dtype(df_pred_analyzed['timestamp']): 
        sns.lineplot(data=df_pred_analyzed, x='timestamp', y='cumulative_net_pnl_usd', label='Predictive Cum. Net Holding P&L (USD)', marker='.', ax=ax11, color='green')
        plot_11_drawn = True

if 'cumulative_net_pnl_usd' in df_base_analyzed.columns and not df_base_analyzed['cumulative_net_pnl_usd'].dropna().empty:
    if not pd.api.types.is_datetime64_any_dtype(df_base_analyzed['timestamp']): 
        df_base_analyzed['timestamp'] = pd.to_datetime(df_base_analyzed['timestamp'], errors='coerce')
    if pd.api.types.is_datetime64_any_dtype(df_base_analyzed['timestamp']): 
        sns.lineplot(data=df_base_analyzed, x='timestamp', y='cumulative_net_pnl_usd', label='Baseline Cum. Net Holding P&L (USD)', marker='.', ax=ax11, color='darkorange')
        plot_11_drawn = True

if plot_11_drawn:
    ax11.set_title('Cumulative Net Holding Period P&L (LP Value Change - Gas)', weight='bold')
    ax11.set_xlabel('Time')
    ax11.set_ylabel('Cumulative Net Holding P&L (USD)')
    ax11.axhline(0, color='grey', linestyle='--')
    ax11.legend()
    ax11.tick_params(axis='x', rotation=30)
    ax11.yaxis.set_major_formatter(thousands_formatter)
    ax11.xaxis.set_major_formatter(date_formatter)
    fig11.tight_layout()
    plt.savefig(plots_dir / "11_cumulative_net_holding_pnl.png", dpi=300)
    plt.close(fig11)
    print(f"Plot saved: {plots_dir / '11_cumulative_net_holding_pnl.png'}")
else:
    plt.close(fig11)
    print("Skipping plot 11.")

# Plot 12: % Holding Periods Ended In Range
ended_in_range_data_for_plot12 = []

if pd.notna(results_pred.get('percent_periods_ended_in_range')) and results_pred.get('percent_periods_ended_in_range') is not None:
    ended_in_range_data_for_plot12.append({
        'Strategy': 'Predictive', 
        'Percent': results_pred.get('percent_periods_ended_in_range')
    })

if pd.notna(results_base.get('percent_periods_ended_in_range')) and results_base.get('percent_periods_ended_in_range') is not None:
    ended_in_range_data_for_plot12.append({
        'Strategy': 'Baseline', 
        'Percent': results_base.get('percent_periods_ended_in_range')
    })

if ended_in_range_data_for_plot12:
    fig12, ax12 = plt.subplots(figsize=(8,6))
    df_ended_in_range = pd.DataFrame(ended_in_range_data_for_plot12)
    
    sns.barplot(
        x='Strategy', 
        y='Percent', 
        data=df_ended_in_range, 
        ax=ax12, 
        hue='Strategy', 
        palette={'Predictive':'skyblue', 'Baseline':'lightcoral'}, 
        legend=False
    )
    
    ax12.set_title('% Holding Periods Ended In Range', weight='bold')
    ax12.set_xlabel('Strategy')
    ax12.set_ylabel('Percent (%)')
    ax12.set_ylim(0, 105)
    
    for p_patch in ax12.patches:
        ax12.annotate(
            f"{p_patch.get_height():.1f}%", 
            (p_patch.get_x() + p_patch.get_width() / 2., p_patch.get_height()), 
            ha='center', 
            va='center', 
            xytext=(0, 5), 
            textcoords='offset points'
        )
    
    fig12.tight_layout()
    plt.savefig(plots_dir / "12_percent_periods_ended_in_range.png", dpi=300)
    plt.close(fig12)
    print(f"Plot saved: {plots_dir / '12_percent_periods_ended_in_range.png'}")
else:
    print("Skipping plot 12.")

# Plot 13: Distribution of Impermanent Loss (USD)
fig13, ax13 = plt.subplots(figsize=plot_figsize)
plot_13_drawn = False

if 'il_usd' in df_pred_analyzed.columns and not df_pred_analyzed['il_usd'].dropna().empty:
    sns.histplot(
        df_pred_analyzed['il_usd'].dropna(), 
        bins=20, 
        color='blue', 
        alpha=0.6, 
        label='Predictive IL', 
        ax=ax13, 
        kde=True
    )
    plot_13_drawn = True

if 'il_usd' in df_base_analyzed.columns and not df_base_analyzed['il_usd'].dropna().empty:
    sns.histplot(
        df_base_analyzed['il_usd'].dropna(), 
        bins=20, 
        color='orange', 
        alpha=0.6, 
        label='Baseline IL', 
        ax=ax13, 
        kde=True
    )
    plot_13_drawn = True

if plot_13_drawn:
    ax13.set_title('Distribution of Impermanent Loss (USD)', weight='bold')
    ax13.set_xlabel('Impermanent Loss (USD)')
    ax13.set_ylabel('Frequency')
    ax13.axhline(0, color='grey', linestyle='--')
    ax13.legend()
    ax13.xaxis.set_major_formatter(thousands_formatter)
    fig13.tight_layout()
    plt.savefig(plots_dir / "13_distribution_impermanent_loss.png", dpi=300)
    plt.close(fig13)
    print(f"Plot saved: {plots_dir / '13_distribution_impermanent_loss.png'}")
else:
    plt.close(fig13)
    print("Skipping plot 13.")

# --- 6. Create and Save Summary Table Image ---
fig_table, ax_table = plt.subplots(figsize=(16, 6))
ax_table.set_title("Results Summary Table", weight='bold', size=14, y=1.08)
ax_table.axis('tight')
ax_table.axis('off')

the_table = ax_table.table(
    cellText=summary_df.values, 
    colLabels=summary_df.columns,
    colWidths=[0.40] + [0.18]*(len(summary_df.columns)-1),
    cellLoc='left', 
    loc='center', 
    colColours=["#E8E8E8"]*len(summary_df.columns)
)

the_table.auto_set_font_size(False)
the_table.set_fontsize(9)
the_table.scale(1, 1.9)

for (row_idx, col_idx), cell in the_table.get_celld().items():
    if row_idx == 0:
        cell.set_text_props(weight='bold', ha='center')
    else:
        cell.set_text_props(ha='left', wrap=True)
        if col_idx > 0:
            cell.set_text_props(ha='right')

summary_table_filename = plots_dir / "summary_table.png"
fig_table.tight_layout(pad=0.5)
plt.savefig(summary_table_filename, dpi=300, bbox_inches='tight')
print(f"Summary table saved as {summary_table_filename}")
plt.close(fig_table)

# --- 7. End of Script ---
print("\nAll plots and table have been saved to the 'plots_results' directory.")