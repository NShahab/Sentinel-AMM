// contracts/mocks/MockAggregatorV3.sol
pragma solidity ^0.8.20;

/**
 * @title MockAggregatorV3
 * @notice This is a mock contract for the Chainlink Price Feed.
 * @dev It's used in testing environments to return a predictable, hardcoded price,
 * removing the dependency on live networks or forking.
 */
contract MockAggregatorV3 {
    // This mock always returns a fixed price of $3,400 with 8 decimals.
    int256 private constant MOCK_PRICE = 2440 * 10 ** 8;

    /**
     * @dev Returns the hardcoded price data, mimicking the real Chainlink Aggregator.
     * The roundId, startedAt, and answeredInRound are set to non-zero values for realism.
     */
    function latestRoundData()
        external
        view
        returns (
            uint80 roundId,
            int256 answer,
            uint256 startedAt,
            uint256 updatedAt,
            uint80 answeredInRound
        )
    {
        return (1, MOCK_PRICE, block.timestamp - 30, block.timestamp, 1);
    }

    /**
     * @dev Returns the number of decimals for the price feed.
     */
    function decimals() external pure returns (uint8) {
        return 8;
    }
}
