import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, GRU, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau, ModelCheckpoint
import joblib
import os

# Function to load and preprocess data
def load_and_preprocess_data(file_path):
    """
    Loads data from a CSV file, converts 'open_time' to datetime,
    sets it as index, selects relevant columns, and drops NA values.
    """
    data = pd.read_csv(file_path)
    data['open_time'] = pd.to_datetime(data['open_time'])
    data.set_index('open_time', inplace=True)
    data = data[['open', 'high', 'low', 'close', 'volume']]
    data.dropna(inplace=True)
    return data

# Function to resample data to different timeframes
def resample_data(data, timeframe):
    """
    Resamples the data to the specified timeframe and aggregates OHLCV.
    """
    tf_data = data.resample(timeframe).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    return tf_data

# Function to add technical indicators (including ATR)
def add_technical_indicators(data):
    """
    Adds SMA, RSI, Bollinger Bands, and ATR to the dataframe.
    """
    # Simple Moving Average
    data['SMA'] = data['close'].rolling(window=14).mean()

    # Relative Strength Index
    delta = data['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    data['RSI'] = 100 - (100 / (1 + rs))

    # Bollinger Bands
    data['Bollinger_Upper'] = data['close'].rolling(window=20).mean() + 2 * data['close'].rolling(window=20).std()

    # Average True Range (ATR)
    high_low = data['high'] - data['low']
    high_close = np.abs(data['high'] - data['close'].shift())
    low_close = np.abs(data['low'] - data['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1, skipna=False) # Ensure TR is calculated correctly
    data['ATR'] = tr.rolling(window=14).mean()

    data.dropna(inplace=True) # Drop rows with NaN values created by indicators
    return data

# Creating Sequences
def create_sequences(data, seq_length):
    """
    Creates sequences of data for LSTM/GRU input.
    'close' price (first column) is the target variable.
    """
    X, y = [], []
    if len(data) <= seq_length: # Check if data is long enough
        return np.array(X), np.array(y)
    for i in range(seq_length, len(data)):
        X.append(data[i-seq_length:i])
        y.append(data[i, 0])  # Target is the first column ('close')
    return np.array(X), np.array(y)

# Function to build the LSTM model with tanh
def build_lstm_model(input_shape):
    """
    Builds an LSTM model with tanh activation.
    """
    lstm_model = Sequential([
        LSTM(64, activation='tanh', return_sequences=True, input_shape=input_shape),
        Dropout(0.2),
        LSTM(64, activation='tanh', return_sequences=False),
        Dropout(0.2),
        Dense(32, activation='tanh'),
        Dense(1)  # Linear activation for regression output
    ])
    lstm_model.compile(optimizer='adam', loss='mse')
    return lstm_model

# Function to build the GRU model with tanh
def build_gru_model(input_shape):
    """
    Builds a GRU model with tanh activation.
    """
    gru_model = Sequential([
        GRU(64, activation='tanh', return_sequences=True, input_shape=input_shape),
        Dropout(0.2),
        GRU(64, activation='tanh', return_sequences=False),
        Dropout(0.2),
        Dense(32, activation='tanh'),
        Dense(1)  # Linear activation for regression output
    ])
    gru_model.compile(optimizer='adam', loss='mse')
    return gru_model

# Function to train the model
def train_model(model, X_train, y_train, X_val, y_val, epochs=100, batch_size=64, model_save_path='best_model.keras'):
    """
    Trains the model with early stopping, learning rate reduction, and model checkpointing.
    """
    early_stopping = EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)
    reduce_lr = ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, min_lr=1e-6, verbose=1)
    model_checkpoint = ModelCheckpoint(model_save_path, monitor='val_loss', save_best_only=True, verbose=1)

    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=[early_stopping, reduce_lr, model_checkpoint],
        verbose=1
    )
    return model, history

# Function to evaluate the model
def evaluate_model(model, X_test, y_test, scaler):
    """
    Evaluates the model on test data and returns metrics.
    """
    predictions = model.predict(X_test)
    num_features = scaler.n_features_in_

    # Rescale predictions
    dummy_preds = np.zeros((predictions.shape[0], num_features))
    dummy_preds[:, 0] = predictions.reshape(-1)  # Predictions for the first feature ('close')
    predictions_rescaled = scaler.inverse_transform(dummy_preds)[:, 0]

    # Rescale actual y_test values
    dummy_y_test = np.zeros((y_test.shape[0], num_features))
    dummy_y_test[:, 0] = y_test.reshape(-1) # Actual values for the first feature ('close')
    y_test_rescaled = scaler.inverse_transform(dummy_y_test)[:, 0]

    mse = mean_squared_error(y_test_rescaled, predictions_rescaled)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(y_test_rescaled, predictions_rescaled)
    r2 = r2_score(y_test_rescaled, predictions_rescaled)
    next_predicted_price = predictions_rescaled[-1] if len(predictions_rescaled) > 0 else np.nan

    return y_test_rescaled, predictions_rescaled, mse, rmse, mae, r2, next_predicted_price

# Function to save the trained model
def save_trained_model(model, model_type, timeframe):
    """
    Saves the trained model to a file.
    """
    model_filename = f'model_{model_type}_{timeframe}.keras'
    model.save(model_filename)
    print(f"Model for {model_type} at {timeframe} saved as {model_filename}")

# Function to plot results for each timeframe
def plot_results(y_test_rescaled, predictions_rescaled, model_type, timeframe, dates):
    """
    Plots actual vs. predicted prices.
    """
    plt.figure(figsize=(12, 6))
    plt.plot(dates, y_test_rescaled, label='Real Prices')
    plt.plot(dates, predictions_rescaled, label='Predicted Prices', linestyle='--')
    plt.title(f'{model_type} Model - {timeframe} Price Prediction')
    plt.xlabel('Time')
    plt.ylabel('Price')
    plt.legend()
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout() # Adjust layout to prevent labels from overlapping
    plt.savefig(f'{model_type}_{timeframe}_prediction.png')
    plt.show()

# Function to plot comparison of evaluation metrics
def plot_metrics_comparison(results):
    """
    Plots a bar chart comparing evaluation metrics for different models and timeframes.
    """
    timeframes = list(results.keys())
    if not timeframes:
        print("No results to plot for metrics comparison.")
        return

    metrics = ['MSE', 'RMSE', 'MAE', 'R²']
    model_types = list(results[timeframes[0]].keys()) # Get model types from the first timeframe

    metric_values = {metric: {model_type: [] for model_type in model_types} for metric in metrics}

    for tf in timeframes:
        for model_type in model_types:
            if model_type in results[tf]:
                for metric in metrics:
                    metric_values[metric][model_type].append(results[tf][model_type].get(metric, np.nan))
            else: # Handle missing model results for a timeframe
                 for metric in metrics:
                    metric_values[metric][model_type].append(np.nan)


    num_models = len(model_types)
    bar_width = 0.8 / num_models # Adjust bar width based on number of models
    
    plt.figure(figsize=(15, 12)) # Adjusted figure size
    for i, metric in enumerate(metrics):
        plt.subplot(2, 2, i + 1)
        x_pos_base = np.arange(len(timeframes))

        for j, model_type in enumerate(model_types):
            # Calculate offset for each model's bars
            offset = (j - (num_models - 1) / 2) * bar_width
            bars = plt.bar(x_pos_base + offset, metric_values[metric][model_type], bar_width, label=model_type)
            # Add text labels on bars
            for bar in bars:
                yval = bar.get_height()
                if not np.isnan(yval):
                    plt.text(bar.get_x() + bar.get_width()/2.0, yval, f'{yval:.2f}', va='bottom', ha='center')


        plt.title(f'{metric} Comparison')
        plt.xlabel('Timeframe')
        plt.ylabel(metric)
        plt.xticks(x_pos_base, timeframes)
        plt.legend()
        plt.grid(axis='y', linestyle='--')


    plt.tight_layout()
    plt.savefig('metrics_comparison.png')
    plt.show()

# Main function to execute all steps
def main():
    """
    Main function to run the stock price prediction pipeline.
    """
    file_path = '/content/drive/MyDrive/binance_data_20180101_to_20241229.csv' # Update with your file path
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"Error: Data file not found at {file_path}")
        print("Please ensure the file path is correct and you have mounted Google Drive if using Colab.")
        return

    timeframes = {'1h': '1 Hour', '4h': '4 Hours', '1d': '1 Day'}
    seq_length = 50  # Sequence length for LSTM/GRU
    results = {}     # To store evaluation results

    # Load initial data
    base_data = load_and_preprocess_data(file_path)
    if base_data.empty:
        print("No data loaded. Exiting.")
        return

    for tf_key, tf_name in timeframes.items():
        print(f"\nProcessing timeframe: {tf_name} ({tf_key})")
        results[tf_name] = {}

        # Resample and add indicators
        tf_data_processed = resample_data(base_data.copy(), tf_key) # Use a copy to avoid modifying base_data
        if tf_data_processed.empty:
            print(f"No data after resampling for {tf_name}. Skipping.")
            continue
        
        tf_data_with_indicators = add_technical_indicators(tf_data_processed)
        if tf_data_with_indicators.empty:
            print(f"No data after adding technical indicators for {tf_name}. Skipping.")
            continue

        # Define feature columns, ensuring 'close' is first for y and evaluation
        feature_cols = ['close', 'open', 'high', 'low', 'volume', 'SMA', 'RSI', 'Bollinger_Upper', 'ATR']
        
        # Ensure all feature columns exist
        missing_cols = [col for col in feature_cols if col not in tf_data_with_indicators.columns]
        if missing_cols:
            print(f"Missing columns for {tf_name}: {missing_cols}. Skipping.")
            continue
            
        tf_data_ordered = tf_data_with_indicators[feature_cols]
        features_np = tf_data_ordered.values

        # 1. Split features *before* normalization
        train_split_idx = int(0.8 * len(features_np))
        val_split_idx = train_split_idx + int(0.1 * len(features_np))

        train_features = features_np[:train_split_idx]
        val_features = features_np[train_split_idx:val_split_idx]
        test_features = features_np[val_split_idx:]

        if not (len(train_features) > seq_length and len(val_features) > seq_length and len(test_features) > seq_length):
            print(f"Insufficient data for train/val/test split after considering seq_length for {tf_name}. Skipping.")
            continue

        # 2. Normalize data (Fit only on train, transform all)
        scaler = MinMaxScaler(feature_range=(0, 1))
        
        # Fit ONLY on train_features and transform it
        train_data_normalized = scaler.fit_transform(train_features)
        
        # Transform val and test features using the *fitted* scaler
        val_data_normalized = scaler.transform(val_features)
        test_data_normalized = scaler.transform(test_features)

        # 3. Save the scaler
        scaler_path = f'scaler_{tf_key}.pkl'
        joblib.dump(scaler, scaler_path)
        print(f"Scaler for {tf_name} saved to {scaler_path}")

        # Create sequences for each split
        X_train, y_train = create_sequences(train_data_normalized, seq_length)
        X_val, y_val = create_sequences(val_data_normalized, seq_length)
        X_test, y_test = create_sequences(test_data_normalized, seq_length)

        # Check if we have enough data to proceed after creating sequences
        if X_train.shape[0] == 0 or X_val.shape[0] == 0 or X_test.shape[0] == 0:
            print(f"Skipping {tf_name} due to insufficient data after creating sequences.")
            continue
        
        # Prepare dates for plotting (align with y_test)
        # The dates should correspond to the start of the test_features, adjusted for seq_length
        test_dates_start_index = val_split_idx + seq_length
        dates_for_plot = tf_data_ordered.index[test_dates_start_index : test_dates_start_index + len(y_test)]

        if len(dates_for_plot) != len(y_test):
            print(f"Warning: Mismatch between dates ({len(dates_for_plot)}) and y_test ({len(y_test)}) in {tf_name}. Plotting might be affected.")
            # Fallback if lengths don't match, though ideally they should
            dates_for_plot = tf_data_ordered.index[val_split_idx + seq_length : val_split_idx + seq_length + len(y_test)]


        # --- LSTM Model ---
        print(f"\n--- Training LSTM Model for {tf_name} ---")
        lstm_model_path = f'best_lstm_model_{tf_key}.keras'
        lstm_model = build_lstm_model((X_train.shape[1], X_train.shape[2]))
        lstm_model, _ = train_model(lstm_model, X_train, y_train, X_val, y_val, epochs=100, model_save_path=lstm_model_path) # 100 epochs, can be adjusted
        
        print(f"--- Evaluating LSTM Model for {tf_name} ---")
        y_test_r_lstm, preds_r_lstm, mse_l, rmse_l, mae_l, r2_l, next_p_l = evaluate_model(lstm_model, X_test, y_test, scaler)
        results[tf_name]['LSTM'] = {'MSE': mse_l, 'RMSE': rmse_l, 'MAE': mae_l, 'R²': r2_l, 'Next Predicted Price': next_p_l}
        save_trained_model(lstm_model, 'LSTM', tf_key)
        if len(dates_for_plot) == len(y_test_r_lstm):
             plot_results(y_test_r_lstm, preds_r_lstm, 'LSTM', tf_name, dates_for_plot)
        else:
            print(f"Skipping LSTM plot for {tf_name} due to date/prediction length mismatch.")


        # --- GRU Model ---
        print(f"\n--- Training GRU Model for {tf_name} ---")
        gru_model_path = f'best_gru_model_{tf_key}.keras'
        gru_model = build_gru_model((X_train.shape[1], X_train.shape[2]))
        gru_model, _ = train_model(gru_model, X_train, y_train, X_val, y_val, epochs=100, model_save_path=gru_model_path) # 100 epochs
        
        print(f"--- Evaluating GRU Model for {tf_name} ---")
        y_test_r_gru, preds_r_gru, mse_g, rmse_g, mae_g, r2_g, next_p_g = evaluate_model(gru_model, X_test, y_test, scaler)
        results[tf_name]['GRU'] = {'MSE': mse_g, 'RMSE': rmse_g, 'MAE': mae_g, 'R²': r2_g, 'Next Predicted Price': next_p_g}
        save_trained_model(gru_model, 'GRU', tf_key)
        if len(dates_for_plot) == len(y_test_r_gru):
            plot_results(y_test_r_gru, preds_r_gru, 'GRU', tf_name, dates_for_plot)
        else:
            print(f"Skipping GRU plot for {tf_name} due to date/prediction length mismatch.")


    # Display evaluation metrics
    print("\n--- Comparison of Evaluation Metrics ---")
    for tf_name_res, metrics_res in results.items():
        print(f"\nTimeframe: {tf_name_res}")
        for model_name, metrics_values in metrics_res.items():
            print(f"  Model: {model_name}")
            print(f"    MSE: {metrics_values.get('MSE', float('nan')):.2f}")
            print(f"    RMSE: {metrics_values.get('RMSE', float('nan')):.2f}")
            print(f"    MAE: {metrics_values.get('MAE', float('nan')):.2f}")
            print(f"    R²: {metrics_values.get('R²', float('nan')):.2f}")
            print(f"    Next Predicted Price: {metrics_values.get('Next Predicted Price', float('nan')):.2f}")

    # Plot metrics comparison
    plot_metrics_comparison(results)
    print("\nProcessing complete.")

if __name__ == '__main__':
    # To run in Google Colab, ensure you mount your drive first if file_path is in Drive
    # from google.colab import drive
    # drive.mount('/content/drive')
    main()
