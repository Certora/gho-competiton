// SPDX-License-Identifier: agpl-3.0
pragma solidity 0.8.10;

import {IVariableDebtToken} from '@aave/core-v3/contracts/interfaces/IVariableDebtToken.sol';

/**
 * @title IGhoVariableDebtToken
 * @author Aave
 * @notice Defines the basic interface of the VariableDebtToken
 */
interface IGhoVariableDebtToken is IVariableDebtToken {
  /**
   * @dev Emitted when the address of the GHO AToken is set
   * @param aToken The address of the GhoAToken contract
   **/
  event ATokenSet(address indexed aToken);

  /**
   * @dev Emitted when the GhoDiscountRateStrategy is updated
   * @param oldDiscountRateStrategy The address of the old GhoDiscountRateStrategy
   * @param newDiscountRateStrategy The address of the new GhoDiscountRateStrategy
   **/
  event DiscountRateStrategyUpdated(
    address indexed oldDiscountRateStrategy,
    address indexed newDiscountRateStrategy
  );

  /**
   * @dev Emitted when the Discount Token is updated
   * @param oldDiscountToken The address of the old discount token
   * @param newDiscountToken The address of the new discount token
   **/
  event DiscountTokenUpdated(address indexed oldDiscountToken, address indexed newDiscountToken);

  /**
   * @dev Emitted when the discount lock period is updated
   * @param oldDiscountLockPeriod The value of the old DiscountLockPeriod
   * @param newDiscountLockPeriod The value of the new DiscountLockPeriod
   **/
  event DiscountLockPeriodUpdated(
    uint256 indexed oldDiscountLockPeriod,
    uint256 indexed newDiscountLockPeriod
  );

  /**
   * @dev Emitted when a user's discount or rebalanceTimestamp is updated
   * @param user The address of the user
   * @param discountPercent The discount percent of the user
   * @param rebalanceTimestamp Timestamp when a users locked discount can be rebalanced
   **/
  event DiscountPercentLocked(
    address indexed user,
    uint256 indexed discountPercent,
    uint256 indexed rebalanceTimestamp
  );

  /**
   * @notice Sets a reference to the GHO AToken
   * @param ghoAToken The address of the GhoAToken contract
   **/
  function setAToken(address ghoAToken) external;

  /**
   * @notice Returns the address of the GHO AToken
   * @return The address of the GhoAToken contract
   **/
  function getAToken() external view returns (address);

  /**
   * @notice Updates the Discount Rate Strategy
   * @param newDiscountRateStrategy The address of DiscountRateStrategy contract
   **/
  function updateDiscountRateStrategy(address newDiscountRateStrategy) external;

  /**
   * @notice Returns the address of the Discount Rate Strategy
   * @return The address of DiscountRateStrategy contract
   **/
  function getDiscountRateStrategy() external view returns (address);

  /**
   * @notice Updates the Discount Token
   * @param newDiscountToken The address of the DiscountToken contract
   **/
  function updateDiscountToken(address newDiscountToken) external;

  /**
   * @notice Returns the address of the Discount Token
   * @return address The address of DiscountToken
   **/
  function getDiscountToken() external view returns (address);

  /**
   * @notice Updates the discount percents of the users when a discount token transfer occurs
   * @param sender The address of sender
   * @param recipient The address of recipient
   * @param senderDiscountTokenBalance The sender discount token balance
   * @param recipientDiscountTokenBalance The recipient discount token balance
   * @param amount The amount of discount token being transferred
   **/
  function updateDiscountDistribution(
    address sender,
    address recipient,
    uint256 senderDiscountTokenBalance,
    uint256 recipientDiscountTokenBalance,
    uint256 amount
  ) external;

  /**
   * @notice Returns the discount percent being applied to the debt interest of the user
   * @param user The address of the user
   * @return The discount percent (expressed in bps)
   */
  function getDiscountPercent(address user) external view returns (uint256);

  /*
   * @dev Returns the amount of interests accumulated by the user
   * @param user The address of the user
   * @return The amount of interests accumulated by the user
   */
  function getBalanceFromInterest(address user) external view returns (uint256);

  /**
   * @dev Decrease the amount of interests accumulated by the user
   * @param user The address of the user
   * @param amount The value to be decrease
   */
  function decreaseBalanceFromInterest(address user, uint256 amount) external;

  /**
   * @notice Rebalances the discount percent of a user if they are past their rebalance timestamp
   * @param user The address of the user
   */
  function rebalanceUserDiscountPercent(address user) external;

  /**
   * @notice Updates the discount percent lock period
   * @param newLockPeriod The new discount lock period (in seconds)
   */
  function updateDiscountLockPeriod(uint256 newLockPeriod) external;

  /**
   * @notice Returns the discount percent lock period
   * @return The discount percent lock period (in seconds)
   */
  function getDiscountLockPeriod() external view returns (uint256);

  /**
   * @notice Returns the timestamp at which a user's discount percent can be rebalanced
   * @param user The address of the user's rebalance timestamp being requested
   * @return The time when a users discount percent can be rebalanced
   */
  function getUserRebalanceTimestamp(address user) external view returns (uint256);
}