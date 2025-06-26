import React, { useState, useEffect, useCallback } from 'react';
import { Link, useLocation } from 'react-router-dom';
import styled from 'styled-components';
import { FaWallet, FaSignOutAlt } from 'react-icons/fa';

const Nav = styled.nav`
    background-color: #007bff;
    padding: 1rem 0;
    color: white;
`;

const NavContainer = styled.div`
    display: flex;
    justify-content: space-between;
    align-items: center;
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 1rem;
`;

const NavLinks = styled.ul`
    list-style: none;
    display: flex;
    margin: 0;
    padding: 0;
`;

const NavLink = styled(Link)`
    color: white;
    text-decoration: none;
    margin-right: 1rem;
    padding: 0.5rem 1rem;
    border-radius: 4px;

    &.active {
        background-color: #0056b3;
    }
`;

const WalletButton = styled.button`
    background-color: white;
    color: #007bff;
    border: none;
    padding: 0.5rem 1rem;
    border-radius: 4px;
    cursor: pointer;
    display: flex;
    align-items: center;

    &:hover {
        background-color: #f0f0f0;
    }
`;

const Dropdown = styled.div`
    position: relative;
    display: inline-block;
`;

const DropdownContent = styled.ul`
    display: ${(props) => (props.open ? 'block' : 'none')};
    position: absolute;
    background-color: white;
    min-width: 160px;
    box-shadow: 0px 8px 16px 0px rgba(0, 0, 0, 0.2);
    z-index: 1;
    list-style: none;
    padding: 0;
    margin: 0;
    right: 0;
`;

const DropdownItem = styled.li`
    padding: 12px 16px;
    text-decoration: none;
    display: block;
    color: #333;
    cursor: pointer;

    &:hover {
        background-color: #f0f0f0;
    }
`;

const Header = () => {
    const location = useLocation();
    const [account, setAccount] = useState(null);
    const [dropdownOpen, setDropdownOpen] = useState(false);

    useEffect(() => {
        const checkConnection = async () => {
            if (window.ethereum) {
                try {
                    const accounts = await window.ethereum.request({ method: 'eth_accounts' });
                    setAccount(accounts[0] || null);
                } catch (error) {
                    console.error('Error checking connection:', error);
                }
                window.ethereum.on('accountsChanged', (accounts) => setAccount(accounts[0] || null));
            }
            return () => window.ethereum?.removeListener('accountsChanged', () => { });
        };
        checkConnection();
    }, []);

    const connectWallet = useCallback(async () => {
        if (window.ethereum) {
            try {
                const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
                setAccount(accounts[0]);
            } catch (error) {
                console.error('Connection error:', error);
            }
        } else {
            alert('Please install MetaMask!');
        }
    }, []);

    const disconnectWallet = useCallback(() => {
        setAccount(null);
        setDropdownOpen(false);
    }, []);

    const formatAddress = (address) => address ? `${address.slice(0, 6)}...${address.slice(-4)}` : '';

    return (
        <Nav>
            <NavContainer>
                <Link to="/" style={{ color: 'white', textDecoration: 'none', fontSize: '1.2rem' }}>
                    ETH/USDT Dashboard
                </Link>
                <NavLinks>
                    <NavLink to="/" active={location.pathname === '/' ? 1 : undefined}>
                        Home
                    </NavLink>
                    <NavLink to="/dashboard" active={location.pathname === '/dashboard' ? 1 : undefined}>
                        Dashboard
                    </NavLink>
                </NavLinks>
                {account ? (
                    <Dropdown>
                        <WalletButton onClick={() => setDropdownOpen(!dropdownOpen)}>
                            {formatAddress(account)}
                            <FaSignOutAlt style={{ marginLeft: '0.5rem' }} />
                        </WalletButton>
                        <DropdownContent open={dropdownOpen}>
                            <DropdownItem onClick={disconnectWallet}>Disconnect</DropdownItem>
                        </DropdownContent>
                    </Dropdown>
                ) : (
                    <WalletButton onClick={connectWallet}>
                        <FaWallet style={{ marginRight: '0.5rem' }} />
                        Connect Wallet
                    </WalletButton>
                )}
            </NavContainer>
        </Nav>
    );
};

export default Header;