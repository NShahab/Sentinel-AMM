import React, { useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { ethers } from 'ethers';

const ConnectionStatus = ({ status }) => {
    if (!status) return null;
    return (
        <div className={`alert alert-${status.type} mb-4`} role="alert">
            {status.message}
        </div>
    );
};

const ConnectedAccount = ({ account }) => (
    <div className="mb-4">
        <div className="alert alert-info">
            <strong>Connected Account:</strong><br />
            <small>{account}</small>
        </div>
        <Link to="/dashboard" className="btn btn-primary btn-lg">
            Go to ETH/USDT Dashboard
        </Link>
    </div>
);

const ConnectWalletButton = ({ onClick, isConnecting, account }) => (
    <button
        className="btn btn-primary btn-lg"
        onClick={onClick}
        disabled={isConnecting}
        title={account ? account : undefined}
    >
        {isConnecting ? (
            <>
                <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                Connecting...
            </>
        ) : account ? (
            'Connected'
        ) : (
            'Connect MetaMask'
        )}
    </button>
);

const Home = () => {
    const [isConnecting, setIsConnecting] = useState(false);
    const [connectionStatus, setConnectionStatus] = useState(null);
    const [account, setAccount] = useState(null);

    const connectWallet = useCallback(async () => {
        if (typeof window.ethereum !== 'undefined') {
            try {
                setIsConnecting(true);
                const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
                const provider = new ethers.providers.Web3Provider(window.ethereum);

                setAccount(accounts[0]);
                setConnectionStatus({
                    type: 'success',
                    message: 'Your wallet has been connected successfully.'
                });
            } catch (error) {
                setConnectionStatus({
                    type: 'danger',
                    message: 'Please make sure MetaMask is installed and unlocked.'
                });
            } finally {
                setIsConnecting(false);
            }
        } else {
            setConnectionStatus({
                type: 'warning',
                message: 'Please install MetaMask first.'
            });
        }
    }, []);

    return (
        <div className="container py-5">
            <div className="row justify-content-center">
                <div className="col-md-8">
                    <div className="card shadow-sm">
                        <div className="card-body text-center p-5">
                            <h1 className="h3 mb-4">Welcome to Ethereum Price Dashboard</h1>
                            <ConnectionStatus status={connectionStatus} />
                            {account ? (
                                <ConnectedAccount account={account} />
                            ) : (
                                <div className="d-grid gap-3">
                                    <ConnectWalletButton
                                        onClick={connectWallet}
                                        isConnecting={isConnecting}
                                        account={account}
                                    />
                                    <Link to="/dashboard" className="btn btn-outline-secondary">
                                        View ETH/USDT Dashboard Without Connecting
                                    </Link>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Home;