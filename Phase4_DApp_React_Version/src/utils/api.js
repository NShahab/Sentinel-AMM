// API endpoints
export const PREDICTION_API = "http://95.216.156.73:5000/predict_price";
export const BINANCE_API = "https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT";

// Fetch current price from Binance
export const fetchBinancePrice = async () => {
    try {
        const response = await fetch(BINANCE_API);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        return parseFloat(data.price);
    } catch (error) {
        console.error("Error fetching Binance price:", error);
        throw error;
    }
};

// Fetch predicted price
export const fetchPredictedPrice = async () => {
    try {
        const response = await fetch(`${PREDICTION_API}?symbol=ETHUSDT&interval=4h`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        if (!data.predicted_price) {
            throw new Error('No prediction data received');
        }
        return parseFloat(data.predicted_price);
    } catch (error) {
        console.error("Error fetching predicted price:", error);
        throw error;
    }
};

// Format price with 3 decimal places
export const formatPrice = (price) => {
    return price ? price.toLocaleString('en-US', {
        minimumFractionDigits: 3,
        maximumFractionDigits: 3
    }) : "N/A";
};

// Calculate price difference and percentage
export const calculatePriceDifference = (predictedPrice, currentPrice) => {
    if (predictedPrice && currentPrice) {
        const difference = predictedPrice - currentPrice;
        const percentage = (difference / currentPrice) * 100;
        return { difference, percentage };
    }
    return { difference: null, percentage: null };
};