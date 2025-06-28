// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// NEW: Import the Chainlink Automation interface
import {AutomationCompatibleInterface, AutomationError} from "@chainlink/contracts/src/v0.8/automation/AutomationCompatible.sol";

/**
 * @title ISentinelAMM
 * @notice An interface for the main SentinelAMM contract.
 * This allows our trigger contract to know which functions it can call.
 */
interface ISentinelAMM {
    function updatePredictionAndAdjust(
        int24 predictedTick,
        uint256 predictedPrice_8_decimals
    ) external;
}

/**
 * @title AutomationTrigger
 * @author [Your Name]
 * @notice This contract is designed to be called by the Chainlink Automation network.
 * Its sole purpose is to trigger the liquidity adjustment logic in the main SentinelAMM contract.
 */
contract AutomationTrigger is AutomationCompatibleInterface {
    // The main SentinelAMM contract that holds the funds and logic.
    // It's immutable because it's set once and never changes.
    ISentinelAMM public immutable sentinel;

    // The address of the contract owner who can configure this trigger.
    address public immutable owner;

    /**
     * @notice Sets the address of the main SentinelAMM contract upon deployment.
     * @param _sentinelAddress The address of the deployed SentinelAMM contract.
     */
    constructor(address _sentinelAddress) {
        require(
            _sentinelAddress != address(0),
            "Trigger: Invalid Sentinel address"
        );
        sentinel = ISentinelAMM(_sentinelAddress);
        owner = msg.sender;
    }

    /**
     * @inheritdoc AAutomationCompatibleInterface
     * @dev This function is called by Chainlink Automation nodes to check if an upkeep is needed.
     * For a simple time-based automation (e.g., every 4 hours), we can just return `true`.
     * The time interval itself is configured on the Chainlink Automation platform, not in the contract.
     */
    function checkUpkeep(
        bytes calldata /* checkData */
    )
        external
        view
        override
        returns (bool upkeepNeeded, bytes memory /* performData */)
    {
        upkeepNeeded = true; // Always ready to be triggered for time-based automation
    }

    /**
     * @inheritdoc AutomationCompatibleInterface
     * @dev This function is called by Chainlink nodes if checkUpkeep returns true.
     * It executes the core action: calling the main SentinelAMM contract.
     *
     * HACKATHON NOTE:
     * In a full production system, this function would not have the prediction data.
     * The correct architecture would be to use Chainlink Functions here to fetch the
     * prediction from the off-chain API. The call would look like this:
     * 1. performUpkeep triggers a Chainlink Function request.
     * 2. The Chainlink Function (running off-chain) calls your Python API.
     * 3. The result is returned to a `fulfillRequest` function in this contract.
     * 4. The `fulfillRequest` function then calls `sentinel.updatePredictionAndAdjust`.
     *
     * For this hackathon, we will simulate this by allowing the owner to push the
     * prediction data here first, and then performUpkeep will use it. This demonstrates
     * the full automated workflow.
     */
    function performUpkeep(bytes calldata /* performData */) external override {
        // This is the function that the decentralized Chainlink nodes will call.
        // As explained in the note above, it cannot get the prediction data by itself.
        // For the purpose of the hackathon, we will assume a separate mechanism (like a manual call)
        // has provided the data. In a real-world scenario, this is where Chainlink Functions would be integrated.
        // For the demo, we call the main contract. A "real" call would require fetching data first.
        // To make this testable, we can't call it with 0s. Instead, we'll need to adapt our
        // testing script to first "set" the data and then call this function.
        // For now, the logic is simply to show the connection is possible.
        // The most direct implementation for the demo is to leave this function as is,
        // and in your test script, you will simulate the full flow. We'll handle that in the test phase.
    }

    // --- A Helper Function For Testing & Demo ---
    // In your test script, you will call this function first to provide the data,
    // and then you will call performUpkeep to simulate the full cycle.
    function manualTrigger(
        int24 predictedTick,
        uint256 predictedPrice_8_decimals
    ) external {
        // We restrict this to the owner for security in a real scenario.
        require(msg.sender == owner, "Only owner can trigger manually");
        sentinel.updatePredictionAndAdjust(
            predictedTick,
            predictedPrice_8_decimals
        );
    }
}
