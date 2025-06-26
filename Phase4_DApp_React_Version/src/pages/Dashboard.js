import React, { useState, useEffect, useCallback } from 'react';
import { fetchBinancePrice, fetchPredictedPrice, formatPrice, calculatePriceDifference } from '../utils/api'; // تغییر fetchCurrentPrice به fetchBinancePrice و اضافه کردن calculatePriceDifference

const PriceCard = ({ title, price, isLoading, error, color, difference }) => ( // اضافه کردن پراپ difference
    <div className="col-md-6 mb-4">
        <div className="border rounded p-3 h-100 price-card">
            <h5 className="text-center">{title}</h5>
            <div className="text-center mt-3">
                <p className="text-muted mb-1">
                    {title.includes('Current') ? 'Market Price' : 'Predicted Price'}
                </p>
                <h3 className={`text-${color}`}>
                    {isLoading ? (
                        <div className={`spinner-border spinner-border-sm text-${color}`} role="status">
                            <span className="visually-hidden">Loading...</span>
                        </div>
                    ) : price ? (
                        `$${formatPrice(price)}`
                    ) : (
                        error || 'Error fetching data'
                    )}
                </h3>
                {difference && ( // نمایش اختلاف در صورت وجود
                    <p className={`mt-2 ${difference.difference > 0 ? 'text-success' : 'text-danger'}`}>
                        {difference.difference > 0 ? '+' : ''}${formatPrice(difference.difference)} ({difference.percentage.toFixed(2)}%)
                    </p>
                )}
            </div>
        </div>
    </div>
);

const TradingTips = () => (
    <div className="card shadow-sm">
        <div className="card-body">
            <h5 className="card-title">Trading Tips</h5>
            <ul className="list-group list-group-flush">
                <li className="list-group-item">Connect MetaMask wallet to start trading</li>
                <li className="list-group-item">Monitor real-time prices and predictions</li>
                <li className="list-group-item">Prices update automatically every 5 minutes</li>
                <li className="list-group-item">Make informed decisions based on AI predictions</li>
            </ul>
        </div>
    </div>
);

const Dashboard = () => {
    const [predictedPrice, setPredictedPrice] = useState(null);
    const [currentPrice, setCurrentPrice] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);
    const [priceDifference, setPriceDifference] = useState(null); // اضافه کردن state برای اختلاف قیمت

    const fetchData = useCallback(async () => {
        try {
            setIsLoading(true);
            setError(null);

            const [current, predicted] = await Promise.all([
                fetchBinancePrice(), // تغییر fetchCurrentPrice به fetchBinancePrice
                fetchPredictedPrice(),
            ]);

            setCurrentPrice(current);
            setPredictedPrice(predicted);

            const difference = calculatePriceDifference(predicted, current); // محاسبه اختلاف قیمت
            setPriceDifference(difference); // ذخیره اختلاف قیمت
        } catch (err) {
            setError(err.message);
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 300000);
        return () => clearInterval(interval);
    }, [fetchData]);

    return (
        <div className="container py-4">
            <div className="row">
                <div className="col-md-8 mx-auto">
                    <div className="card mb-4 shadow-sm">
                        <div className="card-body">
                            <h2 className="card-title h4 text-center mb-4">ETH/USDT Price</h2> {/* تغییر به ETH/USDT */}
                            <div className="row">
                                <PriceCard
                                    title="Current Price"
                                    price={currentPrice}
                                    isLoading={isLoading}
                                    error={error}
                                    color="primary"
                                />
                                <PriceCard
                                    title="4h Prediction"
                                    price={predictedPrice}
                                    isLoading={isLoading}
                                    error={error}
                                    color="success"
                                    difference={priceDifference} // ارسال اختلاف قیمت به کامپوننت PriceCard
                                />
                            </div>
                            {error && (
                                <div className="alert alert-warning mt-3" role="alert">
                                    {error}
                                </div>
                            )}
                        </div>
                    </div>
                    <TradingTips />
                </div>
            </div>
        </div>
    );
};

export default Dashboard;