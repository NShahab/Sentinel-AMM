# Simple Bitcoin Price Dashboard

A lightweight React application that displays Bitcoin price information and predictions.

## Features

- Current BTC/USDT price from Binance API
- 4-hour price prediction from custom API
- MetaMask wallet integration
- Bootstrap UI for fast loading and responsive design

## Project Structure

```
Simple_React_Version/
├── public/
│   └── index.html
├── src/
│   ├── components/
│   │   └── Header.js
│   ├── pages/
│   │   ├── Home.js
│   │   └── Dashboard.js
│   ├── utils/
│   │   └── api.js
│   ├── App.js
│   ├── index.js
│   └── index.css
└── package.json
```

## Getting Started

1. Install dependencies:
   ```
   npm install
   ```

2. Start the development server:
   ```
   npm start
   ```

3. Build for production:
   ```
   npm run build
   ```

## API Endpoints

- Binance API for current price: `https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT`
- Prediction API: `http://95.216.156.73:5000/predict_price?symbol=BTCUSDT&interval=4h`

## Technologies Used

- React.js
- Bootstrap 5
- React Router
- ethers.js for Ethereum wallet integration 