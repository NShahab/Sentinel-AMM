# 📊 Financial Time Series Forecasting using LSTM & GRU

**Author: Nahid Shahab**
**Date: 2025-01-28**

## 1. Introduction

This project provides a comprehensive framework for forecasting financial time series, with a specific focus on cryptocurrency prices, using state-of-the-art deep learning models: Long Short-Term Memory (LSTM) and Gated Recurrent Unit (GRU) networks. Financial markets exhibit complex, non-linear, and often noisy patterns. LSTMs and GRUs are specifically designed to capture long-range temporal dependencies, making them suitable candidates for this task.

The primary objective is to develop, train, and evaluate these models to predict future price movements based on historical data. This involves several key stages: data acquisition and preprocessing, feature engineering with technical indicators, model building, robust training strategies, and thorough evaluation, including crucial steps to avoid common pitfalls like data leakage.

This document serves as a guide to understanding the project's workflow, architecture, implementation details, setup, usage, and results.

---

## 2. Project Workflow

The project follows these key steps:

1.  **Data Loading:** Read historical OHLCV data from a CSV file.
2.  **Preprocessing:** Convert time formats, set index, and handle missing values.
3.  **Resampling:** Adjust data to desired timeframes (1H, 4H, 1D).
4.  **Feature Engineering:** Calculate and add technical indicators (SMA, RSI, Bollinger Bands, ATR).
5.  **Data Splitting:** Divide the data chronologically into Training (80%), Validation (10%), and Testing (10%) sets.
6.  **Normalization:** Scale features between 0 and 1 using `MinMaxScaler`, **fitting only on the training set** to prevent data leakage.
7.  **Sequence Creation:** Transform data into sequences suitable for RNN input.
8.  **Model Building:** Define LSTM and GRU model architectures.
9.  **Model Training:** Train both models using training and validation sets, employing callbacks like Early Stopping, ReduceLROnPlateau, and ModelCheckpoint.
10. **Evaluation:** Assess model performance on the test set using MSE, RMSE, MAE, and R².
11. **Visualization:** Plot results and comparison metrics.

---

## 3. Data

*   **Source:** Historical OHLCV (Open, High, Low, Close, Volume) data, typically sourced from cryptocurrency exchanges like Binance.
*   **Format:** Requires a CSV file. Ensure it contains at least these columns: `open_time`, `open`, `high`, `low`, `close`, `volume`.
*   **Setup:** You must provide your own data file. Update the `file_path` variable in the `main()` function within the script to point to your CSV file's location (e.g., within your mounted Google Drive if using Colab).

---

## 4. Preprocessing & Feature Engineering

### 4.1 Data Loading & Initial Prep (`load_and_preprocess_data`)

*   Reads the CSV using Pandas.
*   Converts the `open_time` column to Python's `datetime` objects.
*   Sets `open_time` as the DataFrame index, crucial for time-based operations.
*   Selects the core OHLCV columns.
*   Drops any rows with missing data.

### 4.2 Resampling (`resample_data`)

*   Aggregates data into the specified timeframes ('1h', '4h', '1d').
*   Uses `first` for 'open', `max` for 'high', `min` for 'low', `last` for 'close', and `sum` for 'volume'. This ensures each new candle correctly represents its period.

### 4.3 Technical Indicators (`add_technical_indicators`)

*   Adds features to help the model understand market dynamics beyond raw price:
    *   **SMA (14):** Simple Moving Average (14-period) to identify trends.
    *   **RSI (14):** Relative Strength Index (14-period) to gauge momentum.
    *   **Bollinger Upper (20, 2):** Upper Bollinger Band (20-period, 2 std dev) to assess volatility.
    *   **ATR (14):** Average True Range (14-period) to measure volatility directly.
*   Drops rows with `NaN` values, which are inevitably created at the beginning when calculating rolling indicators.

### 4.4 Data Splitting & Normalization

*   **Splitting First:** The data (features) is split *before* scaling. This is **critical** to prevent data leakage.
*   **MinMaxScaler:** Features are scaled to [0, 1]. The scaler is `fit` **only** on the training data and then used to `transform` all three sets.

### 4.5 Sequence Creation (`create_sequences`)

*   Data is transformed into sequences of length 50 (`seq_length=50`). `X` contains the input sequences, and `y` contains the target 'close' price for the next step.

---

## 5. Model Architecture (`build_lstm_model`, `build_gru_model`)

*   **Type:** `Sequential` Keras models.
*   **Recurrent Layers (LSTM/GRU):** Two layers with 64 units each and `tanh` activation.
*   **Dropout (0.2):** Applied after each recurrent layer for regularization.
*   **Dense Layer:** 32 units, `tanh` activation.
*   **Output Layer (Dense):** 1 unit (linear activation).
*   **Compilation:** `optimizer='adam'`, `loss='mse'`.

---

## 6. Model Training (`train_model`)

*   Uses `model.fit()` with `epochs=100` and `batch_size=64`.
*   **Callbacks:**
    *   **`EarlyStopping(patience=10, restore_best_weights=True)`:** Stops training early and keeps the best weights.
    *   **`ReduceLROnPlateau(patience=5, factor=0.5)`:** Reduces learning rate if training plateaus.
    *   **`ModelCheckpoint(save_best_only=True)`:** Saves the best performing model to disk.

---

## 7. Evaluation (`evaluate_model`)

*   Rescales predictions and actuals back to the original price range.
*   Calculates **MSE**, **RMSE**, **MAE**, and **R²**.

---

## 8. Installation & Setup

### 8.1 Requirements:

*   Python: 3.9.0
*   TensorFlow: 2.12.0
*   Keras: 2.12.0 (Part of TensorFlow)
*   NumPy: 1.23.5 (*Note: TensorFlow 2.12 needs NumPy < 2.0*)
*   Pandas: 2.2.3
*   SciPy: 1.13.1
*   Matplotlib: 3.x.x
*   Scikit-learn: 1.x.x
*   Joblib: 1.x.x

### 8.2 Installation:

```bash
# Create & activate virtual environment
python -m venv myenv
source myenv/bin/activate # Linux/macOS
# myenv\Scripts\activate # Windows

# Install packages
pip install tensorflow==2.12.0 pandas==2.2.3 numpy==1.23.5 matplotlib scikit-learn joblib scipy==1.13.1

### 8.3 Google Colab:

Most libraries are pre-installed.
You only need to mount your Google Drive to access the data file:

```python
from google.colab import drive
drive.mount('/content/drive')
```
9. How to Run
Clone/download the repository/script.
Set up your environment and install packages (or use Google Colab).
Ensure your data CSV file is available.
Edit the file_path in main() to match your data file location (especially important in Colab, e.g., /content/drive/MyDrive/your_file.csv).
Run the script: python your_script_name.py (or run the cells in your Colab notebook).
Monitor the console/Colab output for progress and results.
Check the working directory (/content/ in Colab) for saved models (.keras), scalers (.pkl), and plots (.png). Remember to save these from Colab if you need them permanently.
10. Results & Interpretation (Based on Latest Run)
10.1 Quantitative Results:
Timeframe	Model	MSE	RMSE	MAE	R²	Next Predicted Price
1 Hour	LSTM	937.71	30.62	21.18	1.00	2746.63
GRU	846.23	29.09	20.47	1.00	2726.05
4 Hours	LSTM	4061.40	63.73	46.08	0.99	2665.44
GRU	3263.49	57.13	41.11	0.99	2708.92
1 Day	LSTM	21293.56	145.92	108.41	0.96	2629.20
GRU	19996.03	141.41	104.88	0.96	2610.98

Export to Sheets
10.2 Critical Interpretation Note:
The R² values presented (1.00, 0.99, 0.96) are extremely high and highly suspect for financial forecasting, even after addressing the initial normalization leak. Such values strongly suggest either:

A remaining data leakage issue or flaw in the evaluation process.
The model is primarily learning a very strong short-term persistence (Naive Forecast).
It is IMPERATIVE to investigate these R² values further and, most importantly, compare these RMSE/MAE results against a Naive Forecast to determine if these complex models provide any meaningful advantage. Trusting these results without further validation and baseline comparison is not recommended.

10.3 Initial Analysis (Based solely on these numbers):
Based strictly on these numbers (and acknowledging the R² warning), the GRU model appears to outperform the LSTM model across all timeframes, showing slightly lower errors.

11. Conclusion & Future Work
This project demonstrates the application of LSTM and GRU models for financial forecasting, highlighting the importance of proper methodology. While the models show high R² values, these require significant critical review and further investigation before any conclusions about predictive power can be drawn. The comparison suggests GRU might have a slight edge in this run.

Future Directions:

Crucially: Implement and compare with a Naive Forecast.
Investigate potential sources of data leakage or evaluation issues.
Rigorous hyperparameter optimization.
Exploration of advanced architectures (Attention, Transformers).
Inclusion of external features (news, sentiment).
Deployment and real-world performance tracking (only after robust validation).