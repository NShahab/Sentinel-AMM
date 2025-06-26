import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import numpy as np
from pathlib import Path
import sys
from decimal import Decimal, getcontext, ROUND_HALF_UP

# ==============================================
# 0. Setup and Configuration
# ==============================================
print("Initializing analysis environment...")

# Set up directories
try:
    script_dir = Path(__file__).parent.resolve()
except NameError:
    script_dir = Path('.').resolve()

input_csv_dir = script_dir / "processed_results"
output_plots_dir = script_dir / "plots_results"
output_plots_dir.mkdir(parents=True, exist_ok=True)

# Configure decimal precision
getcontext().prec = 78

# Constants
TOKEN0_DECIMALS = 6  # USDC
TOKEN1_DECIMALS = 18  # WETH
TOKEN0_NAME = "USDC"
TOKEN1_NAME = "WETH"

# ==============================================
# 1. Data Loading and Preparation
# ==============================================
print("\n1. Loading and preparing data...")

def load_and_prepare_data():
    """Load and preprocess the input CSV files"""
    try:
        fee_columns_to_preserve = {
            f'fees_{TOKEN0_NAME}_collected_usd': str,
            f'fees_{TOKEN1_NAME}_collected_usd': str
        }
        df_pred = pd.read_csv(input_csv_dir / "predictive_final.csv", dtype=fee_columns_to_preserve)
        df_base = pd.read_csv(input_csv_dir / "baseline_final.csv", dtype=fee_columns_to_preserve)
        
        for df in [df_pred, df_base]:
            for col in fee_columns_to_preserve.keys():
                if col in df.columns:
                    df[col] = df[col].apply(Decimal)
            
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.sort_values('timestamp', inplace=True)
        
        print("✅ Data loaded successfully with high-precision fees")
        return df_pred, df_base
    
    except Exception as e:
        print(f"❌ Error loading data: {str(e)}")
        sys.exit(1)

df_pred, df_base = load_and_prepare_data()

# ==============================================
# 2. Core Analysis Functions
# ==============================================
print("\n2. Defining analysis functions...")

def calculate_lp_amounts(liquidity, current_tick, lower_tick, upper_tick):
    """
    Calculate token amounts in a liquidity position
    Formula: Δx = L(1/√P_lower - 1/√P_upper)
             Δy = L(√P_upper - √P_lower)
    """
    if liquidity == 0 or lower_tick >= upper_tick:
        return 0, 0
    
    try:
        sqrt_P_current = Decimal('1.0001')**(Decimal(current_tick)/Decimal(2))
        sqrt_P_lower = Decimal('1.0001')**(Decimal(lower_tick)/Decimal(2))
        sqrt_P_upper = Decimal('1.0001')**(Decimal(upper_tick)/Decimal(2))
        liquidity = Decimal(liquidity)

        if current_tick < lower_tick:
            amount0 = liquidity * (Decimal(1)/sqrt_P_lower - Decimal(1)/sqrt_P_upper)
            amount1 = Decimal(0)
        elif current_tick >= upper_tick:
            amount0 = Decimal(0)
            amount1 = liquidity * (sqrt_P_upper - sqrt_P_lower)
        else:
            amount0 = liquidity * (Decimal(1)/sqrt_P_current - Decimal(1)/sqrt_P_upper)
            amount1 = liquidity * (sqrt_P_current - sqrt_P_lower)
            
        return float(amount0), float(amount1)
    except Exception:
        return 0, 0

def analyze_strategy(df, strategy_type):
    """Perform comprehensive analysis on a strategy dataframe"""
    results = {}
    
    df['lp_value_usd'] = 0.0
    df['hodl_value_usd'] = 0.0
    df['fees_usd'] = df[f'fees_{TOKEN0_NAME}_collected_usd'] + df[f'fees_{TOKEN1_NAME}_collected_usd']
    df['gas_cost_usd'] = df['gas_cost_eth'] * df['actualPrice_pool']
    
    for i, row in df.iterrows():
        liquidity = row['liquidity_contract'] if strategy_type == 'predictive' else row['finalLiquidity_contract']
        
        amount0, amount1 = calculate_lp_amounts(
            liquidity, row['currentTick_pool'], row['finalTickLower_contract'], row['finalTickUpper_contract']
        )
        lp_value = (amount0 / 10**TOKEN0_DECIMALS) + (amount1 / 10**TOKEN1_DECIMALS) * row['actualPrice_pool']
        df.at[i, 'lp_value_usd'] = lp_value
        
        hodl_value = (row['initial_contract_balance_token0'] / 10**TOKEN0_DECIMALS) + \
                     (row['initial_contract_balance_token1'] / 10**TOKEN1_DECIMALS) * row['actualPrice_pool']
        df.at[i, 'hodl_value_usd'] = hodl_value
        
        # Explicitly convert all components to Decimal before arithmetic
        pnl_vs_hodl = Decimal(str(lp_value)) + row['fees_usd'] - Decimal(str(hodl_value)) - Decimal(str(row['gas_cost_usd']))
        df.at[i, 'pnl_vs_hodl'] = pnl_vs_hodl
    
    df['cumulative_pnl'] = df['pnl_vs_hodl'].cumsum()
    df['cumulative_fees'] = df['fees_usd'].cumsum()
    df['cumulative_gas'] = df['gas_cost_usd'].cumsum()
    
    df['in_range'] = (df['actualPrice_pool'] >= df[f'finalTickLower_contract_{TOKEN1_NAME}{TOKEN0_NAME}_price']) & \
                     (df['actualPrice_pool'] <= df[f'finalTickUpper_contract_{TOKEN1_NAME}{TOKEN0_NAME}_price'])
    
    results['final_pnl'] = df['cumulative_pnl'].iloc[-1]
    results['time_in_range'] = df['in_range'].mean() * 100
    results['total_fees'] = df['fees_usd'].sum()
    results['total_gas'] = df['gas_cost_usd'].sum()
    results['avg_lp_value'] = df['lp_value_usd'].mean()
    
    return df, results

# ==============================================
# 3. Perform Analysis
# ==============================================
print("\n3. Analyzing strategies...")

df_pred, pred_results = analyze_strategy(df_pred.copy(), 'predictive')
df_base, base_results = analyze_strategy(df_base.copy(), 'baseline')

improvement = {
    'pnl_improvement': pred_results['final_pnl'] - base_results['final_pnl'],
    'relative_improvement': ((pred_results['final_pnl'] - base_results['final_pnl']) / 
                             abs(base_results['final_pnl'])) * 100 if base_results['final_pnl'] != 0 else float('inf'),
    'fee_improvement': pred_results['total_fees'] - base_results['total_fees']
}

print("✅ Analysis complete")
print(f"\nPredictive Strategy Results:\n{pred_results}")
print(f"\nBaseline Strategy Results:\n{base_results}")
print(f"\nImprovement Metrics:\n{improvement}")

# ==============================================
# 4. Visualization
# ==============================================
print("\n4. Generating visualizations...")

sns.set_style("whitegrid")
plt.rcParams.update({'figure.titlesize': 16, 'axes.titlesize': 14, 'axes.labelsize': 12, 
                     'xtick.labelsize': 10, 'ytick.labelsize': 10, 'legend.fontsize': 10})

usd_formatter = plt.FuncFormatter(lambda x, _: f'${x:,.0f}')
date_formatter = mdates.DateFormatter('%b %d')
palette = {'predictive': '#4C72B0', 'baseline': '#DD8452', 'improvement': '#55A868', 'hodl': '#333333'}

# ----------------------------------------------
# Plot 1: Cumulative PnL Comparison
# ----------------------------------------------
print("Generating Plot 1: Cumulative PnL Comparison...")
fig1, ax1 = plt.subplots(figsize=(12, 6))
sns.lineplot(data=df_pred, x='timestamp', y='cumulative_pnl', 
             label=f'Predictive (Final: ${float(pred_results["final_pnl"]):,.2f})',
             color=palette['predictive'], linewidth=2.5, ax=ax1)
sns.lineplot(data=df_base, x='timestamp', y='cumulative_pnl',
             label=f'Baseline (Final: ${float(base_results["final_pnl"]):,.2f})',
             color=palette['baseline'], linewidth=2.5, ax=ax1)
max_date = max(df_pred['timestamp'].max(), df_base['timestamp'].max())
ax1.annotate(f'{float(improvement["relative_improvement"]):.1f}% Improvement',
             xy=(max_date, float(pred_results['final_pnl'])),
             xytext=(10, 10), textcoords='offset points',
             bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.5),
             arrowprops=dict(arrowstyle='->'))
ax1.set(title='Cumulative PnL: Predictive vs Baseline Strategy', ylabel='Cumulative PnL (USD)', xlabel='Date')
ax1.yaxis.set_major_formatter(usd_formatter)
ax1.xaxis.set_major_formatter(date_formatter)
ax1.axhline(0, color='gray', linestyle='--', alpha=0.7)
ax1.legend(loc='upper left')
plt.tight_layout()
plt.savefig(output_plots_dir / "1_cumulative_pnl_comparison.png", dpi=300, bbox_inches='tight')
plt.close(fig1)
print("✅ Saved Plot 1")

# ----------------------------------------------
# Plot 2: Strategy Components Breakdown
# ----------------------------------------------
print("Generating Plot 2: Strategy Components Breakdown...")
fig2, (ax2a, ax2b) = plt.subplots(1, 2, figsize=(14, 6), sharey=True)
components = ['Fees Earned', 'Gas Costs', 'Price Impact']

# <<<< START OF MODIFICATION >>>>
# Convert gas costs (float) to Decimal before performing arithmetic with other Decimal types.
# Use Decimal(str(float_value)) for safe conversion.

# Panel A: Predictive strategy
gas_cost_pred_decimal = Decimal(str(pred_results['total_gas']))
pred_values = [
    pred_results['total_fees'],
    -gas_cost_pred_decimal,
    pred_results['final_pnl'] - pred_results['total_fees'] + gas_cost_pred_decimal
]
# Convert final list to float for plotting
pred_values_float = [float(v) for v in pred_values]
ax2a.bar(components, pred_values_float, color=[palette['improvement'], palette['baseline'], palette['predictive']])
ax2a.set_title('Predictive Strategy PnL Components', pad=15)
ax2a.set_ylabel('USD Value')
ax2a.yaxis.set_major_formatter(usd_formatter)
for i, v in enumerate(pred_values_float):
    ax2a.text(i, v / 2, f'${v:,.2f}', ha='center', va='center', color='white', weight='bold')

# Panel B: Baseline strategy
gas_cost_base_decimal = Decimal(str(base_results['total_gas']))
base_values = [
    base_results['total_fees'],
    -gas_cost_base_decimal,
    base_results['final_pnl'] - base_results['total_fees'] + gas_cost_base_decimal
]
# Convert final list to float for plotting
base_values_float = [float(v) for v in base_values]
ax2b.bar(components, base_values_float, color=[palette['improvement'], palette['baseline'], palette['predictive']])
ax2b.set_title('Baseline Strategy PnL Components', pad=15)
ax2b.yaxis.set_major_formatter(usd_formatter)
for i, v in enumerate(base_values_float):
    ax2b.text(i, v / 2, f'${v:,.2f}', ha='center', va='center', color='white', weight='bold')

# <<<< END OF MODIFICATION >>>>

plt.tight_layout()
plt.savefig(output_plots_dir / "2_strategy_components.png", dpi=300)
plt.close(fig2)
print("✅ Saved Plot 2")

# Continue with the rest of the script...
# (The rest of the script from the previous version is unchanged)
# ----------------------------------------------
# Plot 3: Price Prediction Accuracy
# ----------------------------------------------
print("Generating Plot 3: Price Prediction Accuracy...")

if 'predictedPrice_api' in df_pred.columns:
    fig3, ax3 = plt.subplots(figsize=(12, 6))
    
    sns.lineplot(data=df_pred, x='timestamp', y='actualPrice_pool', 
                 label='Actual ETH Price', color=palette['hodl'], linewidth=2, ax=ax3)
    sns.lineplot(data=df_pred, x='timestamp', y='predictedPrice_api', 
                 label='Predicted Price', color=palette['predictive'], linestyle='--', linewidth=2, ax=ax3)
    
    mae = (df_pred['predictedPrice_api'] - df_pred['actualPrice_pool']).abs().mean()
    ax3.annotate(f'Mean Absolute Error: ${mae:.2f}', 
                 xy=(0.05, 0.95), xycoords='axes fraction',
                 bbox=dict(boxstyle='round', fc='white', ec='gray', alpha=0.8))
    
    ax3.set(title='Price Prediction Accuracy', ylabel='ETH Price (USD)', xlabel='Date')
    ax3.yaxis.set_major_formatter(usd_formatter)
    ax3.xaxis.set_major_formatter(date_formatter)
    ax3.legend()
    
    plt.tight_layout()
    plt.savefig(output_plots_dir / "3_price_prediction_accuracy.png", dpi=300)
    plt.close(fig3)
    print("✅ Saved Plot 3")
else:
    print("⚠️ Skipping Plot 3 - Prediction data not available")

# ----------------------------------------------
# Plot 4: Liquidity Range Effectiveness
# ----------------------------------------------
print("Generating Plot 4: Liquidity Range Effectiveness...")

fig4, ax4 = plt.subplots(figsize=(12, 6))

price_upper_bound = df_pred[f'finalTickUpper_contract_{TOKEN1_NAME}{TOKEN0_NAME}_price']
price_lower_bound = df_pred[f'finalTickLower_contract_{TOKEN1_NAME}{TOKEN0_NAME}_price']

ax4.fill_between(df_pred['timestamp'], price_lower_bound, price_upper_bound, 
                 alpha=0.2, color=palette['predictive'], label='Predictive Liquidity Range', step='post')

sns.lineplot(data=df_pred, x='timestamp', y='actualPrice_pool', 
             label='Actual Price', color=palette['hodl'], linewidth=2, ax=ax4)

ax4.set(title='Liquidity Range Effectiveness (Predictive Strategy)', ylabel='ETH Price (USD)', xlabel='Date')
ax4.yaxis.set_major_formatter(usd_formatter)
ax4.xaxis.set_major_formatter(date_formatter)
ax4.legend()
ax4.set_ylim(bottom=price_lower_bound.min()*0.98, top=price_upper_bound.max()*1.02)

plt.tight_layout()
plt.savefig(output_plots_dir / "4_liquidity_range_effectiveness.png", dpi=300)
plt.close(fig4)
print("✅ Saved Plot 4")

# ----------------------------------------------
# Plot 5: Performance Metrics Radar Chart
# ----------------------------------------------
print("Generating Plot 5: Performance Metrics Radar Chart...")

from math import pi

metrics = ['PnL', 'Fees Earned', 'Time in Range', 'LP Value']
pnl_max = max(abs(float(pred_results['final_pnl'])), abs(float(base_results['final_pnl'])), 1)
fees_max = max(abs(float(pred_results['total_fees'])), abs(float(base_results['total_fees'])), 1)
lp_val_max = max(pred_results['avg_lp_value'], base_results['avg_lp_value'], 1)

pred_normalized = [
    float(pred_results['final_pnl']) / pnl_max,
    float(pred_results['total_fees']) / fees_max,
    pred_results['time_in_range'] / 100,
    pred_results['avg_lp_value'] / lp_val_max
]

base_normalized = [
    float(base_results['final_pnl']) / pnl_max,
    float(base_results['total_fees']) / fees_max,
    base_results['time_in_range'] / 100,
    base_results['avg_lp_value'] / lp_val_max
]

angles = list(np.linspace(0, 2 * pi, len(metrics), endpoint=False))
angles += angles[:1] 
pred_normalized += pred_normalized[:1]
base_normalized += base_normalized[:1]

fig5 = plt.figure(figsize=(8, 8))
ax5 = fig5.add_subplot(111, polar=True)
ax5.plot(angles, pred_normalized, color=palette['predictive'], linewidth=2, label='Predictive')
ax5.fill(angles, pred_normalized, color=palette['predictive'], alpha=0.25)
ax5.plot(angles, base_normalized, color=palette['baseline'], linewidth=2, label='Baseline')
ax5.fill(angles, base_normalized, color=palette['baseline'], alpha=0.25)

ax5.set_thetagrids(np.degrees(angles[:-1]), metrics)
ax5.set_title('Normalized Performance Metrics Comparison', pad=20)
ax5.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))

plt.tight_layout()
plt.savefig(output_plots_dir / "5_performance_radar.png", dpi=300)
plt.close(fig5)
print("✅ Saved Plot 5")

# ==============================================
# 5. Generate Summary Report
# ==============================================
print("\n5. Generating summary report...")

summary_data = {
    'Metric': ['Final Cumulative PnL', 'Total Fees Earned', 'Total Gas Costs', 
               'Average LP Value', 'Time in Range (%)', 'PnL Improvement vs Base'],
    'Predictive': [
        f"${float(pred_results['final_pnl']):,.2f}", f"${float(pred_results['total_fees']):,.2f}",
        f"${pred_results['total_gas']:.2f}", f"${pred_results['avg_lp_value']:,.2f}",
        f"{pred_results['time_in_range']:.1f}%", f"{float(improvement['relative_improvement']):.1f}%"
    ],
    'Baseline': [
        f"${float(base_results['final_pnl']):,.2f}", f"${float(base_results['total_fees']):,.2f}",
        f"${base_results['total_gas']:.2f}", f"${base_results['avg_lp_value']:,.2f}",
        f"{base_results['time_in_range']:.1f}%", "Reference"
    ]
}

summary_df = pd.DataFrame(summary_data)
fig_table, ax_table = plt.subplots(figsize=(10, 4))
ax_table.axis('off')
ax_table.axis('tight')
table = ax_table.table(cellText=summary_df.values, colLabels=summary_df.columns, 
                       cellLoc='center', loc='center', colColours=['#f7f7f7']*len(summary_df.columns))
table.auto_set_font_size(False)
table.set_fontsize(10)
table.scale(1.2, 1.5)
ax_table.set_title('Strategy Performance Summary', pad=20, fontsize=12)
plt.savefig(output_plots_dir / "6_performance_summary.png", dpi=300, bbox_inches='tight')
plt.close(fig_table)
print("✅ Saved summary table")

# ==============================================
# Final Output
# ==============================================
print("\n✅ Analysis complete! All visualizations saved to:", output_plots_dir)
print("\nKey Findings:")
print(f"- Predictive strategy improved PnL by {float(improvement['relative_improvement']):.1f}% over baseline")
print(f"- Achieved {pred_results['time_in_range']:.1f}% time in range (vs {base_results['time_in_range']:.1f}% baseline)")
print(f"- Generated ${float(pred_results['total_fees']):,.2f} in fees (vs ${float(base_results['total_fees']):,.2f} baseline)")
print(f"- Final PnL: ${float(pred_results['final_pnl']):,.2f} (vs ${float(base_results['final_pnl']):,.2f} baseline)")