import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, GRU, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping
import os

# Function to load and preprocess data
def load_and_preprocess_data(file_path):
    data = pd.read_csv(file_path)
    data['open_time'] = pd.to_datetime(data['open_time'])
    data.set_index('open_time', inplace=True)
    data = data[['open', 'high', 'low', 'close', 'volume']]
    data.dropna(inplace=True)
    return data

# Function to resample data to different timeframes
def resample_data(data, timeframe):
    tf_data = data.resample(timeframe).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    return tf_data

# Function to add technical indicators
def add_technical_indicators(data):
    data['SMA'] = data['close'].rolling(window=14).mean()

    delta = data['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    data['RSI'] = 100 - (100 / (1 + rs))

    data['Bollinger_Upper'] = data['close'].rolling(window=20).mean() + 2 * data['close'].rolling(window=20).std()
    data.dropna(inplace=True)
    return data

# Function to normalize data
def normalize_data(data):
    scaler = MinMaxScaler(feature_range=(0, 1))
    normalized_data = scaler.fit_transform(data)
    return normalized_data, scaler

# Creating Sequences
def create_sequences(data, seq_length):
    X, y = [], []
    for i in range(seq_length, len(data)):
        X.append(data[i-seq_length:i])
        y.append(data[i, 0])  # Assuming y is the 'close' price, which is at index 0
    return np.array(X), np.array(y)

# Main function to execute all steps
def main():
    #file_path = '/content/drive/MyDrive/binance_data_20180101_to_20241229.csv'
    file_path = r'D:\Uniswap-Decentralized-Marketplace\Phase1_Data_Collection\binance_data_20180101_to_20241229.csv'
    timeframes = {'1h': '1 Hour', '4h': '4 Hours', '1d': '1 Day'}
    seq_length = 50

    data = load_and_preprocess_data(file_path)

    for tf, tf_name in timeframes.items():
        print(f"\nProcessing timeframe: {tf_name}")

        tf_data = resample_data(data, tf)
        tf_data = add_technical_indicators(tf_data)
        features = tf_data[['close', 'open', 'high', 'low', 'volume', 'SMA', 'RSI', 'Bollinger_Upper']].values

        # Normalize data
        normalized_features, scaler = normalize_data(features)

        # Split data into train (80%), validation (10%), and test (10%)
        train_size = int(0.8 * len(normalized_features))
        val_size = int(0.1 * len(normalized_features))
        test_size = len(normalized_features) - train_size - val_size

        train_data = normalized_features[:train_size]
        val_data = normalized_features[train_size:train_size+val_size]
        test_data = normalized_features[train_size+val_size:]

        # Create sequences for each split
        X_train, y_train = create_sequences(train_data, seq_length)
        X_val, y_val = create_sequences(val_data, seq_length)
        X_test, y_test = create_sequences(test_data, seq_length)

        # Extract date index for plotting
        dates = tf_data.index[train_size + val_size + seq_length:]

        # Print dataset sizes
        print(f"Total samples: {len(normalized_features)}")
        print(f"Train size: {len(X_train)}, Validation size: {len(X_val)}, Test size: {len(X_test)}")

        # Check date alignment
        print(f"Dates available for test set: {len(dates)}")
        print(f"First test date: {dates[0] if len(dates) > 0 else 'No data'}")

# Execute the main function
main()
