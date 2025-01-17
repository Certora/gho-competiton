import "VariableDebtToken.spec";

using GhoDiscountRateStrategy as discStrategy;
using DummyERC20WithTimedBalanceOf as discountToken;
using DummyPool as pool;

methods{
	
  	/***********************************;
    *    PoolAddressesProvider.sol     *;
    ************************************/
	function _.getACLManager() external => CONSTANT;

	/************************;
    *    ACLManager.sol     *;
    *************************/
    function _.isPoolAdmin(address user) external => retreivePoolAdminFromGhost(user) expect bool ALL;

	/******************************************************************;
	*	DummyERC20WithTimedBalanceOf.sol (linked to _discountToken)   *;
	*******************************************************************/
	// represent a random balance per block 
	function discountToken.balanceOf(address user) external returns (uint256) with (env e) => balanceOfDiscountTokenAtTimestamp(user, e.block.timestamp) ;

  	/************************************;
    *   DummyPool.sol (linked to POOL)  *;
    *************************************/
	// represent a random index per block
	function pool.getReserveNormalizedVariableDebt(address asset) external returns (uint256) with (env e) => indexAtTimestamp(e.block.timestamp);

	/************************************;
	*	GhoVariableDebtTokenHarness.sol	*;
	*************************************/
	function discStrategy.calculateDiscountRate(uint256, uint256) external returns (uint256) envfree;

	/************************************;
	*	GhoVariableDebtTokenHarness.sol	*;
	*************************************/
	function getUserCurrentIndex(address) external returns (uint256) envfree;
	function getUserDiscountRate(address) external returns (uint256) envfree;
	function getUserAccumulatedDebtInterest(address) external returns (uint256) envfree;
	function getBalanceOfDiscountToken(address) external returns (uint256);
	function rayDiv(uint256 x, uint256 y) external returns (uint256) envfree;
	function rayMul(uint256 x, uint256 y) external returns (uint256) envfree;
	function percentMul(uint256 x, uint256 y) external returns (uint256) envfree;

	/********************************;
	*	GhoVariableDebtToken.sol	*;
	*********************************/
	function totalSupply() external returns(uint256) envfree;
	function scaledTotalSupply() external returns(uint256) envfree;
	function balanceOf(address) external returns (uint256);
	function mint(address, address, uint256, uint256) external returns (bool, uint256);
	function burn(address ,uint256 ,uint256) external returns (uint256);
	function scaledBalanceOf(address) external returns (uint256) envfree;
	function getBalanceFromInterest(address) external returns (uint256) envfree;
	function rebalanceUserDiscountPercent(address) external;
	function updateDiscountDistribution(address ,address ,uint256 ,uint256 ,uint256) external;

	/********************************;
	*		View and Variable	 	*;
	*********************************/
	function getAToken() external returns(address) envfree;
	function getDiscountRateStrategy() external returns(address) envfree;
	function getDiscountToken() external returns(address) envfree;
	function POOL() external returns(address) envfree;
	function decimals() external returns(uint8) envfree;
	function UNDERLYING_ASSET_ADDRESS() external returns(address) envfree;
	function borrowAllowance(address, address) external returns(uint256) envfree;
	function getIncentivesController() external returns(address) envfree;
}

/**
* CVL implementation of rayMul
**/
function rayMulCVL(uint256 a, uint256 b) returns mathint {
	return ((a * b + (ray() / 2)) / ray());
}
function rayDivCVL(uint256 a, uint256 b) returns mathint {
	return ((a * ray() + (b / 2)) / b);
}


//todo: check balanceof after mint (stable index), burn after balanceof

definition MAX_DISCOUNT() returns uint256 = 10000; // equals to 100% discount, in points

ghost mapping(address => mapping (uint256 => uint256)) discount_ghost;
ghost mapping(uint256 => uint256) index_ghost;

/**
* Query index_ghost for the index value at the input timestamp
**/
function indexAtTimestamp(uint256 timestamp) returns uint256 {
    require index_ghost[timestamp] >= ray();
    return index_ghost[timestamp];
    // return 1001684385021630839436707910;//index_ghost[timestamp];
}

/**
* Query discount_ghost for the [user]'s balance of discount token at [timestamp]
**/
function balanceOfDiscountTokenAtTimestamp(address user, uint256 timestamp) returns uint256 {
	return discount_ghost[user][timestamp];
}

/**
* Returns an env instance with [ts] as the block timestamp
**/
function envAtTimestamp(uint256 ts) returns env {
	env e;
	require(e.block.timestamp == ts);
	return e;
}

/**
* @title at any point in time, the user's discount rate isn't larger than 100%
**/
invariant discountCantExceed100Percent(address user)
	getUserDiscountRate(user) <= MAX_DISCOUNT()
	filtered {
		f-> nonHarnessNonRevert(f)
	}
	{
		preserved updateDiscountDistribution(address sender,address recipient,uint256 senderDiscountTokenBalance,uint256 recipientDiscountTokenBalance,uint256 amount) with (env e) {
			require(indexAtTimestamp(e.block.timestamp) >= ray());
		}
	}

/**
* Imported rules from VariableDebtToken.spec
**/
//pass
use rule disallowedFunctionalities;


/**
* @title proves that the user's balance of debt token (as reported by GhoVariableDebtToken::balanceOf) can't increase by calling any external non-mint function.
**/
//pass
rule nonMintFunctionCantIncreaseBalance(method f) filtered { f-> f.selector != sig:mint(address, address, uint256, uint256).selector && nonHarnessNonRevert(f)} {
	address user;
	uint256 ts1;
	uint256 ts2;
	require(ts2 >= ts1);
	// Forcing the index to be fixed (otherwise the rule times out). For non-fixed index replace `==` with `>=`
	require((indexAtTimestamp(ts1) >= ray()) && 
			(indexAtTimestamp(ts2) == indexAtTimestamp(ts1)));

	require(getUserCurrentIndex(user) == indexAtTimestamp(ts1));
	requireInvariant discountCantExceed100Percent(user);

	env e = envAtTimestamp(ts2);
	uint256 balanceBeforeOp = balanceOf(e, user);
	calldataarg args;
	f(e,args);
	mathint balanceAfterOp = balanceOf(e, user);
	mathint allowedDiff = indexAtTimestamp(ts2) / ray();
	// assert(balanceAfterOp != balanceBeforeOp + allowedDiff + 1);
	assert(balanceAfterOp <= balanceBeforeOp + allowedDiff);
}

/**
* @title proves that a call to a non-mint operation won't increase the user's balance of the actual debt tokens (i.e. it's scaled balance)
**/
// pass
rule nonMintFunctionCantIncreaseScaledBalance(method f) filtered { f-> f.selector != sig:mint(address, address, uint256, uint256).selector && nonHarnessNonRevert(f) } {
	address user;
	uint256 ts1;
	uint256 ts2;
	require(ts2 >= ts1);
	require((indexAtTimestamp(ts1) >= ray()) && 
			(indexAtTimestamp(ts2) >= indexAtTimestamp(ts1)));

	require(getUserCurrentIndex(user) == indexAtTimestamp(ts1));
	requireInvariant discountCantExceed100Percent(user);
	uint256 balanceBeforeOp = scaledBalanceOf(user);
	env e = envAtTimestamp(ts2);
	calldataarg args;
	f(e,args);
	uint256 balanceAfterOp = scaledBalanceOf(user);
	assert(balanceAfterOp <= balanceBeforeOp);
}

/**
* @title proves that debt tokens aren't transferable
**/
// pass
rule debtTokenIsNotTransferable(method f) filtered {
	f-> nonHarnessNonRevert(f)
} {
	address user1;
	address user2;
	require(user1 != user2);
	uint256 scaledBalanceBefore1 = scaledBalanceOf(user1);
	uint256 scaledBalanceBefore2 = scaledBalanceOf(user2);
	env e;
	calldataarg args;
	f(e,args);
	uint256 scaledBalanceAfter1 = scaledBalanceOf(user1);
	uint256 scaledBalanceAfter2 = scaledBalanceOf(user2);

	assert( scaledBalanceBefore1 + scaledBalanceBefore2 == scaledBalanceAfter1 + scaledBalanceAfter2 
	=> (scaledBalanceBefore1 == scaledBalanceAfter1 && scaledBalanceBefore2 == scaledBalanceAfter2));
}

/**
* @title proves that only burn/mint/rebalanceUserDiscountPercent/updateDiscountDistribution can modify user's scaled balance
**/
// pass
rule onlyCertainFunctionsCanModifyScaledBalance(method f) filtered {
	f-> nonHarnessNonRevert(f)
} {
	address user;
	uint256 ts1;
	uint256 ts2;
	require(ts2 >= ts1);
	require((indexAtTimestamp(ts1) >= ray()) && 
			(indexAtTimestamp(ts2) >= indexAtTimestamp(ts1)));

	require(getUserCurrentIndex(user) == indexAtTimestamp(ts1));
	requireInvariant discountCantExceed100Percent(user);
	uint256 balanceBeforeOp = scaledBalanceOf(user);
	env e = envAtTimestamp(ts2);
	calldataarg args;
	f(e,args);
	uint256 balanceAfterOp = scaledBalanceOf(user);
	assert(balanceAfterOp != balanceBeforeOp => (
		(f.selector == sig:mint(address ,address ,uint256 ,uint256).selector) ||
		(f.selector == sig:burn(address ,uint256 ,uint256).selector) ||
		(f.selector == sig:updateDiscountDistribution(address ,address ,uint256 ,uint256 ,uint256).selector) ||
		(f.selector == sig:rebalanceUserDiscountPercent(address).selector)));
}

/**
* @title proves that only a call to decreaseBalanceFromInterest will decrease the user's accumulated interest listing.
**/
// pass
rule userAccumulatedDebtInterestWontDecrease(method f) filtered {
	f-> nonHarnessNonRevert(f)
} {
	address user;
	uint256 ts1;
	uint256 ts2;
	require(ts2 >= ts1);
	require((indexAtTimestamp(ts1) >= ray()) && 
			(indexAtTimestamp(ts2) >= indexAtTimestamp(ts1)));

	require(getUserCurrentIndex(user) == indexAtTimestamp(ts1));
	requireInvariant discountCantExceed100Percent(user);
	uint256 initAccumulatedInterest = getUserAccumulatedDebtInterest(user);
	env e2 = envAtTimestamp(ts2);
	calldataarg args;
	f(e2,args);
	uint256 finAccumulatedInterest = getUserAccumulatedDebtInterest(user);
	assert(initAccumulatedInterest > finAccumulatedInterest => f.selector == sig:decreaseBalanceFromInterest(address, uint256).selector);
}

/**
* @title proves that a user can't nullify its debt without calling burn
**/
// pass
rule userCantNullifyItsDebt(method f) filtered {
	f-> nonHarnessNonRevert(f)
}{
    address user;
    env e;
    env e2;
	require(getUserCurrentIndex(user) == indexAtTimestamp(e.block.timestamp));
	requireInvariant discountCantExceed100Percent(user);
	uint256 balanceBeforeOp = balanceOf(e, user);
	calldataarg args;
    require e2.block.timestamp == e.block.timestamp;
	f(e2,args);
	uint256 balanceAfterOp = balanceOf(e, user);
	assert((balanceBeforeOp > 0 && balanceAfterOp == 0) => (f.selector == sig:burn(address, uint256, uint256).selector));
}

/***************************************************************
* Integrity of Mint
***************************************************************/

/**
* @title proves that after calling mint, the user's discount rate is up to date
**/
rule integrityOfMint_updateDiscountRate() {
	address user1;
	address user2;
	env e;
	uint256 amount;
	uint256 index = indexAtTimestamp(e.block.timestamp);
	mint(e, user1, user2, amount, index);
	uint256 debtBalance = balanceOf(e, user2);
	uint256 discountBalance = getBalanceOfDiscountToken(e, user2);
	uint256 discountRate = getUserDiscountRate(user2);
	assert(discStrategy.calculateDiscountRate(debtBalance, discountBalance) == discountRate);
}

/**
* @title proves the after calling mint, the user's state is updated with the recent index value
**/
rule integrityOfMint_updateIndex() {
	address user1;
	address user2;
	env e;
	uint256 amount;
	uint256 index;
	mint(e, user1, user2, amount, index);
	assert(getUserCurrentIndex(user2) == index);
}

/**
* @title proves that on a fixed index calling mint(user, amount) will increase the user's scaled balance by amount. 
**/
// pass
rule integrityOfMint_updateScaledBalance_fixedIndex() {
	address user;
	env e;
	uint256 balanceBefore = balanceOf(e, user);
	uint256 scaledBalanceBefore = scaledBalanceOf(user);
	address caller;
	uint256 amount;
	uint256 index = indexAtTimestamp(e.block.timestamp);
	require(getUserCurrentIndex(user) == index);
	mint(e, caller, user, amount, index);

	uint256 balanceAfter = balanceOf(e, user);
	mathint scaledBalanceAfter = scaledBalanceOf(user);
	mathint scaledAmount = rayDivCVL(amount, index);

	assert(scaledBalanceAfter == scaledBalanceBefore + scaledAmount);
}

/**
* @title proves that mint can't effect other user's scaled balance
**/
// pass
rule integrityOfMint_userIsolation() {
	address otherUser;
	uint256 scaledBalanceBefore = scaledBalanceOf(otherUser);
	env e;
	uint256 amount;
	uint256 index;
	address targetUser;
	address caller;
	mint(e, caller, targetUser, amount, index);
	uint256 scaledBalanceAfter = scaledBalanceOf(otherUser);
	assert(scaledBalanceAfter != scaledBalanceBefore => otherUser == targetUser);
}

/**
* @title proves that when calling mint, the user's balance (as reported by GhoVariableDebtToken::balanceOf) will increase if the call is made on bahalf of the user.
**/
rule onlyMintForUserCanIncreaseUsersBalance() {
	address user1;
    env e;
	require(getUserCurrentIndex(user1) == indexAtTimestamp(e.block.timestamp));
	
	uint256 finBalanceBeforeMint = balanceOf(e, user1);
	uint256 amount;
	mint(e,user1, user1, amount, indexAtTimestamp(e.block.timestamp));
	uint256 finBalanceAfterMint = balanceOf(e, user1);

	assert(finBalanceAfterMint != finBalanceBeforeMint);
}


//pass
use rule integrityMint_atoken;

/***************************************************************
* Integrity of Burn
***************************************************************/

/**
* @title proves that after calling burn, the user's discount rate is up to date
**/
rule integrityOfBurn_updateDiscountRate() {
	address user;
	env e;
	uint256 amount;
	uint256 index = indexAtTimestamp(e.block.timestamp);
	burn(e, user, amount, index);
	uint256 debtBalance = balanceOf(e, user);
	uint256 discountBalance = getBalanceOfDiscountToken(e, user);
	uint256 discountRate = getUserDiscountRate(user);
	assert(discStrategy.calculateDiscountRate(debtBalance, discountBalance) == discountRate);
}

/**
* @title proves the after calling burn, the user's state is updated with the recent index value
**/
rule integrityOfBurn_updateIndex() {
	address user;
	env e;
	uint256 amount;
	uint256 index;
	burn(e, user, amount, index);
	assert(getUserCurrentIndex(user) == index);
}

/**
* @title proves that calling burn with 0 amount doesn't change the user's balance
**/
use rule burnZeroDoesntChangeBalance;

/**
* @title proves a concrete case of repaying the full debt that ends with a zero balance
**/
rule integrityOfBurn_fullRepay_concrete() {
	env e;
	address user;
	uint256 currentDebt = balanceOf(e, user);
	uint256 index = indexAtTimestamp(e.block.timestamp);
	// handle timeouts
	require(getUserCurrentIndex(user) == ray());
	require(to_mathint(index) == 2*ray());
	require(to_mathint(scaledBalanceOf(user)) == 4*ray());
	
	burn(e, user, currentDebt, index);
	uint256 scaled = scaledBalanceOf(user);
	assert(scaled == 0);
}


/**
* @title proves that burn can't effect other user's scaled balance
**/
// pass
rule integrityOfBurn_userIsolation() {
	address otherUser;
	uint256 scaledBalanceBefore = scaledBalanceOf(otherUser);
	env e;
	uint256 amount;
	uint256 index;
	address targetUser;
	burn(e,targetUser, amount, index);
	uint256 scaledBalanceAfter = scaledBalanceOf(otherUser);
	assert(scaledBalanceAfter != scaledBalanceBefore => otherUser == targetUser);
}


/**
* @title proves the after calling updateDiscountDistribution, the user's state is updated with the recent index value
**/
rule integrityOfUpdateDiscountDistribution_updateIndex() {
	address sender;
	address recipient;
	uint256 senderDiscountTokenBalance;
    uint256 recipientDiscountTokenBalance;
	env e;
	uint256 amount;
	uint256 index = indexAtTimestamp(e.block.timestamp);
	updateDiscountDistribution(e, sender, recipient, senderDiscountTokenBalance, recipientDiscountTokenBalance, amount);
	assert(scaledBalanceOf(sender) > 0 => getUserCurrentIndex(sender) == index);
	assert(scaledBalanceOf(recipient) > 0 => getUserCurrentIndex(recipient) == index);
}


/**
* @title proves that updateDiscountDistribution can't effect other user's scaled balance
**/
// pass
rule integrityOfUpdateDiscountDistribution_userIsolation() {
	address otherUser;
	uint256 scaledBalanceBefore = scaledBalanceOf(otherUser);
	env e;
	uint256 amount;
	uint256 senderDiscountTokenBalance;
	uint256 recipientDiscountTokenBalance;
	address sender;
	address recipient;
	updateDiscountDistribution(e, sender, recipient, senderDiscountTokenBalance, recipientDiscountTokenBalance, amount);
	uint256 scaledBalanceAfter = scaledBalanceOf(otherUser);
	assert(scaledBalanceAfter != scaledBalanceBefore => (otherUser == sender || otherUser == recipient));
}

/***************************************************************
* Integrity of rebalanceUserDiscountPercent
***************************************************************/

/**
* @title proves that after calling rebalanceUserDiscountPercent, the user's discount rate is up to date
**/
rule integrityOfRebalanceUserDiscountPercent_updateDiscountRate() {
	address user;
	env e;
	rebalanceUserDiscountPercent(e, user);
	assert(discStrategy.calculateDiscountRate(balanceOf(e, user), getBalanceOfDiscountToken(e, user)) == getUserDiscountRate(user));
}

/**
* @title proves that after calling rebalanceUserDiscountPercent, the user's state is updated with the recent index value
**/
rule integrityOfRebalanceUserDiscountPercent_updateIndex() {
	address user;
	env e;
	rebalanceUserDiscountPercent(e, user);
	uint256 index = indexAtTimestamp(e.block.timestamp);
	assert(getUserCurrentIndex(user) == index);
}

/**
* @title proves that rebalanceUserDiscountPercent can't effect other user's scaled balance
**/
// pass
rule integrityOfRebalanceUserDiscountPercent_userIsolation() {
	address otherUser;
	uint256 scaledBalanceBefore = scaledBalanceOf(otherUser);
	env e;
	address targetUser;
	rebalanceUserDiscountPercent(e, targetUser);
	uint256 scaledBalanceAfter = scaledBalanceOf(otherUser);
	assert(scaledBalanceAfter != scaledBalanceBefore => otherUser == targetUser);
}

/***************************************************************
* Integrity of balanceOf
***************************************************************/

/**
* @title proves that a user with 100% discounts has a fixed balance over time
**/
rule integrityOfBalanceOf_fullDiscount() {
	address user;
	uint256 fullDiscountRate = 10000; //100%
	require(getUserDiscountRate(user) == fullDiscountRate);
	env e1;
	env e2;
	uint256 index1 = indexAtTimestamp(e1.block.timestamp);
	uint256 index2 = indexAtTimestamp(e2.block.timestamp);
	assert(balanceOf(e1, user) == balanceOf(e2, user));
}

/**
* @title proves that a user's balance, with no discount, is equal to rayMul(scaledBalance, current index)
**/
rule integrityOfBalanceOf_noDiscount() {
	address user;
	require(getUserDiscountRate(user) == 0);
	env e;
	uint256 scaledBalance = scaledBalanceOf(user);
	uint256 currentIndex = indexAtTimestamp(e.block.timestamp);
	mathint expectedBalance = rayMulCVL(scaledBalance, currentIndex);
	assert(to_mathint(balanceOf(e, user)) == expectedBalance);
}

/**
* @title proves the a user with zero scaled balance has a zero balance
**/
rule integrityOfBalanceOf_zeroScaledBalance() {
	address user;
	env e;
	uint256 scaledBalance = scaledBalanceOf(user);
	require(scaledBalance == 0);
	assert(balanceOf(e, user) == 0);
}

rule burnAllDebtReturnsZeroDebt(address user) {
    env e;
	uint256 _variableDebt = balanceOf(e, user);
	burn(e, user, _variableDebt, indexAtTimestamp(e.block.timestamp));
	uint256 variableDebt_ = balanceOf(e, user);
    assert(variableDebt_ == 0);
}


/************************************************************
* 					Participant rules						*
************************************************************/

// keeps track of users with pool admin permissions in order to return a consistent value per user
ghost mapping(address => bool) poolAdmin_ghost;

// returns whether the user is a pool admin
function retreivePoolAdminFromGhost(address user) returns bool{
    return poolAdmin_ghost[user];
}

/***************    Sanity and Revertion    ***************/

// Some function will always revert
definition alwaysRevertFunction(method f ) returns bool = (
	f.selector == sig:decreaseAllowance(address,uint256).selector 
	|| f.selector == sig:allowance(address,address).selector 
	|| f.selector == sig:increaseAllowance(address,uint256).selector 
	|| f.selector == sig:transfer(address,uint256).selector 
	|| f.selector == sig:transferFrom(address,address,uint256).selector 
	|| f.selector == sig:approve(address,uint256).selector 
);

// harness nonview functions 
definition harnessFunction(method f) returns bool = (
	f.selector == sig:accrueDebtOnAction(address, uint256, uint256, uint256).selector
);

// non harness non revert function 
definition nonHarnessNonRevert(method f) returns bool = (
	!harnessFunction(f) && !alwaysRevertFunction(f)
);

// sanity check 
rule sanity(
	env e ,
	method f,
	calldataarg args
) filtered {
	f-> nonHarnessNonRevert(f)
}{
	f(e, args);
	satisfy true;
}

/***************    ACCESS CONTROL    ***************/
// onlyPoolAdmin function access control check
rule onlyPoolAdmin(
	env e,
	method f,
	calldataarg args
) filtered {
	f -> nonHarnessNonRevert(f)
} {
	address _AToken = getAToken();
	address _discountStrat = getDiscountRateStrategy();
	address _discountToken = getDiscountToken();
	
	f(e,args);

	address AToken_ = getAToken();
	address discountStrat_ = getDiscountRateStrategy();
	address discountToken_ = getDiscountToken();
	
	assert _AToken != AToken_ 
		|| _discountStrat != discountStrat_
		|| _discountToken != discountToken_
		=> retreivePoolAdminFromGhost(e.msg.sender), "broken acess control: Pool Admin";
}

// onlyAToken can decrease balance 
rule onlyAToken_decreaseBalance(
	env e,
	method f,
	calldataarg args,
	address user
) filtered {
	f -> nonHarnessNonRevert(f)
} {
	uint256 balanceBefore = getBalanceFromInterest(user);
	f(e,args);
	uint256 balanceAfter = getBalanceFromInterest(user);
	assert balanceAfter < balanceBefore 
		=> e.msg.sender == getAToken() 
		&& f.selector == sig:decreaseBalanceFromInterest(address,uint256).selector
		, "broken access control: AToken";
}

// onlyAdmin can mint and burn 
rule onlyPool (
	env e ,
	method f ,
	calldataarg args,
	address poolAddr
) filtered {
	f -> f.selector == sig:mint(address, address, uint256, uint256).selector || f.selector == sig:burn(address, uint256, uint256).selector
} {
	require poolAddr == POOL();
	f@withrevert(e,args);
	assert e.msg.sender != poolAddr => lastReverted, "broken access control: POOL";
}

// onlyDiscountToken can execute updateDiscountDistribution
rule onlyDiscountToken (
	env e,
	calldataarg args,
	address discountTokenAddr
) {
	require discountTokenAddr ==  getDiscountToken();
	updateDiscountDistribution@withrevert(e,args);
	assert e.msg.sender != discountTokenAddr => lastReverted, "broken access control: DiscountToken";
}

/***************    VARIABLE VALIDATION    ***************/

// Zero Addresses 

// AToken cannot set to 0
rule  ATokenNoZero(env e, address newAToken) {
	address before = getAToken();
	setAToken(e, newAToken);
	assert getAToken() != 0;
	assert getAToken() == newAToken;
	assert getAToken() != before => before == 0;
}

// discountRateStrategy cannot set to 0
rule  discountStratNoZero(env e, address addr) {
	updateDiscountRateStrategy(e, addr);
	assert getDiscountRateStrategy() != 0;
	assert getDiscountRateStrategy() == addr;
}

// discountToken cannot set to 0
rule  discountTokenNoZero(env e, address addr) {
	updateDiscountToken(e, addr);
	assert getDiscountToken() != 0;
	assert getDiscountToken() == addr;
}

/***************    FUNCTION VALIDATION    ***************/

// mint() should decrease Borrow allowance if user != onBehalfOf
rule integrityOfMint_decreaseAllowance(
	env e, 
	address user,
	address onBehalfOf,
	uint256 amount, 
	uint256 index
) {
	uint256 allowanceBefore = borrowAllowance(onBehalfOf, user);

	mint(e, user, onBehalfOf, amount, index);

	uint256 allowanceAfter = borrowAllowance(onBehalfOf, user);
	assert user != onBehalfOf <=> allowanceBefore - allowanceAfter == to_mathint(amount);
}

//initializing related hook 
ghost bool init;
hook Sload bool val currentContract.initializing STORAGE{
	require init == val;
}
hook Sstore currentContract.initializing bool val STORAGE{
	init = val;
}
//initializing should always false 
invariant initializingAlwaysFalse()
	init == false
	filtered {
		f -> nonHarnessNonRevert(f)
	}

//integrity of Initialize, only called once and set several variable
rule initialize_integrity(
	env e,
    address initializingPool,\
    address underlyingAsset,
    address incentivesController,
    uint8 debtTokenDecimals,
    string debtTokenName,
    string debtTokenSymbol,
    bytes params
) {
	requireInvariant initializingAlwaysFalse();
	initialize@withrevert(
		e, 
		initializingPool,
		underlyingAsset,
		incentivesController,
		debtTokenDecimals,
		debtTokenName,
		debtTokenSymbol,
		params
	);
	bool firstRevert = lastReverted;
	if (!firstRevert) {
	assert decimals() == debtTokenDecimals;
	assert getIncentivesController() == incentivesController;
	assert UNDERLYING_ASSET_ADDRESS() == underlyingAsset;
	}
	assert initializingPool != POOL() => firstRevert;
}

//initialize should only called once
rule initialize_onlyOnce(
	env e,
	calldataarg args
) {
	requireInvariant initializingAlwaysFalse();
	initialize(e, args);
	initialize@withrevert(e,args);
	assert lastReverted;
}

// accrueDebtOnAction should return correct number
rule accrueDebtOnAction_integrity(
    env e,
	address user,
    uint256 previousScaledBalance,
    uint256 discountPercent,
    uint256 index
) {
	uint256 balanceIncrease;
	uint256 discountScaled;
	uint256 prevIndex = getUserCurrentIndex(user);
	uint256 prevBalance = getBalanceFromInterest(user);
	require index >= prevIndex;
	
	balanceIncrease, discountScaled = accrueDebtOnAction(e, user, previousScaledBalance, discountPercent, index);
	
	mathint increase = rayMul(previousScaledBalance, index) - rayMul(previousScaledBalance, prevIndex);
	mathint discount = percentMul(assert_uint256(increase), discountPercent);
	mathint scaledDiscCalc = rayDiv(assert_uint256(discount), index); 

	assert discountPercent == 0 => to_mathint(balanceIncrease) == increase;
	assert discountPercent != 0 && increase != 0 
		=> to_mathint(discountScaled) == scaledDiscCalc 
		&& to_mathint(balanceIncrease) == increase - discount;
	assert getUserCurrentIndex(user) == index; 
	assert to_mathint(getBalanceFromInterest(user)) == balanceIncrease + prevBalance;
}

// mint should burn or mint correct amount 
rule integrityOfMint_preciseCalculation(
	env e,
	address caller,
	address user,
	uint256 amount,
	uint256 index
) {
	uint256 amountScaled = rayDiv(amount, index);
	uint256 discountPercent = getUserDiscountRate(user);
	uint256 prevBalance = scaledBalanceOf(user);
	uint256 balanceIncrease; uint256 discountScaled;
	balanceIncrease, discountScaled = accrueDebtOnActionCalculation(e, user, prevBalance, discountPercent, index);
	uint256 supplyBefore = scaledTotalSupply();
	mint(e, caller, user, amount, index);
	uint256 supplyAfter = scaledTotalSupply();
	assert amountScaled > discountScaled => supplyAfter - supplyBefore == amountScaled - discountScaled;
	assert amountScaled <= discountScaled => supplyBefore - supplyAfter == discountScaled - amountScaled;
}

// burn should burn correct amount 
rule integrityOfBurn_preciseCalculation(
	env e,
	address user,
	uint256 amount,
	uint256 index
) {
	uint256 amountScaled = rayDiv(amount, index);
	uint256 balanceBeforeBurn = balanceOf(e, user);
	uint256 prevBalance = scaledBalanceOf(user);
	uint256 discountPercent = getUserDiscountRate(user);
	uint256 balanceIncrease; uint256 discountScaled;
	balanceIncrease, discountScaled = accrueDebtOnActionCalculation(e, user, prevBalance, discountPercent, index);
	uint256 supplyBefore = scaledTotalSupply();
	burn(e, user, amount, index);
	uint256 supplyAfter = scaledTotalSupply();
	assert amount == balanceBeforeBurn => supplyBefore - supplyAfter == to_mathint(prevBalance);
	assert amount != balanceBeforeBurn => supplyBefore - supplyAfter == amountScaled + discountScaled;
}

// rebalanceUserDiscountPercent should burn correct amount 
rule rebalanceUserDiscountPercent_preciseCalculation(
	env e,
	address user
) {
	uint256 index = indexAtTimestamp(e.block.timestamp);
	uint256 discountPercent = getUserDiscountRate(user);
	uint256 prevBalance = scaledBalanceOf(user);
	uint256 balanceIncrease; uint256 discountScaled;
	balanceIncrease, discountScaled = accrueDebtOnActionCalculation(e, user, prevBalance, discountPercent, index);
	uint256 supplyBefore = scaledTotalSupply();
	rebalanceUserDiscountPercent(e, user);
	uint256 supplyAfter = scaledTotalSupply();
	assert supplyBefore - supplyAfter == to_mathint(discountScaled);
}

// updateDiscountDistribution should burn correct amount (sender side)
rule updateDiscountDistribution_preciseCalculation_sender(
	env e,    
	address sender,
    address recipient,
    uint256 senderDiscountTokenBalance,
    uint256 recipientDiscountTokenBalance,
    uint256 amount
) {
	uint256 recipientBalance = scaledBalanceOf(recipient);
	require recipientBalance == 0;
	uint256 index = indexAtTimestamp(e.block.timestamp);
	uint256 discountPercent = getUserDiscountRate(sender);
	uint256 prevBalance = scaledBalanceOf(sender);
	uint256 balanceIncrease; uint256 discountScaled;
	balanceIncrease, discountScaled = accrueDebtOnActionCalculation(e, sender, prevBalance, discountPercent, index);
	uint256 supplyBefore = scaledTotalSupply();
	updateDiscountDistribution(e, sender, recipient, senderDiscountTokenBalance, recipientDiscountTokenBalance, amount);
	uint256 supplyAfter = scaledTotalSupply();
	assert prevBalance > 0  => supplyBefore - supplyAfter == to_mathint(discountScaled);
}

// updateDiscountDistribution should update discount rate of sender
rule updateDiscountDistribution_updateDiscountRate_sender(
	env e,    
	address sender,
    address recipient,
    uint256 senderDiscountTokenBalance,
    uint256 recipientDiscountTokenBalance,
    uint256 amount
) {
	uint256 recipientBalance = scaledBalanceOf(recipient);
	require recipientBalance == 0;
	uint256 prevBalance = scaledBalanceOf(sender);
	updateDiscountDistribution(e, sender, recipient, senderDiscountTokenBalance, recipientDiscountTokenBalance, amount);

	uint256 discountPercent = getUserDiscountRate(sender);
	uint256 balance = balanceOf(e, sender);
	mathint balanceOfDiscountToken = senderDiscountTokenBalance - amount;
	assert prevBalance > 0  => balanceOfDiscountToken >= 0;
	assert prevBalance > 0  => (discStrategy.calculateDiscountRate(balance, require_uint256(balanceOfDiscountToken)) == getUserDiscountRate(sender)); 
}

// updateDiscountDistribution should burn correct amount (receiver side) 
rule updateDiscountDistribution_preciseCalculation_recipient(
	env e,    
	address sender,
    address recipient,
    uint256 senderDiscountTokenBalance,
    uint256 recipientDiscountTokenBalance,
    uint256 amount
) {
	uint256 senderBalance = scaledBalanceOf(sender);
	require senderBalance == 0;
	uint256 index = indexAtTimestamp(e.block.timestamp);
	uint256 discountPercent = getUserDiscountRate(recipient);
	uint256 prevBalance = scaledBalanceOf(recipient);
	uint256 balanceIncrease; uint256 discountScaled;
	balanceIncrease, discountScaled = accrueDebtOnActionCalculation(e, recipient, prevBalance, discountPercent, index);
	uint256 supplyBefore = scaledTotalSupply();
	updateDiscountDistribution(e, sender, recipient, senderDiscountTokenBalance, recipientDiscountTokenBalance, amount);
	uint256 supplyAfter = scaledTotalSupply();
	assert prevBalance > 0  => supplyBefore - supplyAfter == to_mathint(discountScaled);
}


// updateDiscountDistribution should update discount rate of recipient
rule updateDiscountDistribution_updateDiscountRate_recipient(
	env e,    
	address sender,
    address recipient,
    uint256 senderDiscountTokenBalance,
    uint256 recipientDiscountTokenBalance,
    uint256 amount
) {
	uint256 senderBalance = scaledBalanceOf(sender);
	require senderBalance == 0;
	uint256 prevBalance = scaledBalanceOf(recipient);
	updateDiscountDistribution(e, sender, recipient, senderDiscountTokenBalance, recipientDiscountTokenBalance, amount);

	uint256 discountPercent = getUserDiscountRate(recipient);
	uint256 balance = balanceOf(e, recipient);
	mathint balanceOfDiscountToken = recipientDiscountTokenBalance + amount;
	assert prevBalance > 0 => (discStrategy.calculateDiscountRate(balance, require_uint256(balanceOfDiscountToken)) == getUserDiscountRate(recipient)); 
}

// integrity of decreaseBalanceFromInterest, should decrease excact amount
rule decreaseBalanceFromInterest_integrity(
	env e ,
	address user,
	address others,
	uint256 amount
) {
	uint256 _balance = getBalanceFromInterest(user);
	uint256 _balanceOthers = getBalanceFromInterest(others);

	decreaseBalanceFromInterest(e, user, amount);

	uint256 balance_ = getBalanceFromInterest(user);
	uint256 balanceOthers_ = getBalanceFromInterest(others);
	assert _balance - balance_ == to_mathint(amount); 
	assert user != others => _balanceOthers == balanceOthers_;
}

// balanceOf should return correct number 
rule balanceOf_integrity(
	env e,
	address user
) {
	requireInvariant discountCantExceed100Percent(user);
	uint256 index = indexAtTimestamp(e.block.timestamp);
	uint256 prevIndex = getUserCurrentIndex(user);
	uint256 discountPercent = getUserDiscountRate(user);
	uint256 scaledBalance = scaledBalanceOf(user);
	uint256 balance = balanceOf(e, user);

	uint256 calcBalance = rayMul(scaledBalance, index);

	assert scaledBalance == 0 => balance == 0;
	assert prevIndex == index => balance == calcBalance;
	assert discountPercent !=0 
		&& prevIndex != index 
		=> to_mathint(balance)  
		== calcBalance 
		- percentMul(
			require_uint256(calcBalance - rayMul(scaledBalance, prevIndex)), 
			discountPercent
		);
}



/***************    SATISFY MULTIPLE RETURN CONDITION    ***************/
// GENERAL EXPLANATION ABOUT RULES BELOW
// several rules have more than 1 return cases
// using satisfy true isn't enough to check whether every return case can run or not
// using this rules below we check that for every function with more than 1 return cases 
// every return cases can be executed

// balanceOf have several return case and all of them should have a way to return
rule balanceOf_multiReturn_1(
	env e,
	address user
) {
	requireInvariant discountCantExceed100Percent(user);
	uint256 index = indexAtTimestamp(e.block.timestamp);
	uint256 prevIndex = getUserCurrentIndex(user);
	uint256 discountPercent = getUserDiscountRate(user);
	uint256 scaledBalance = scaledBalanceOf(user);
	uint256 balance = balanceOf(e, user);

	uint256 calcBalance = rayMul(scaledBalance, index);

	satisfy scaledBalance == 0;
}

// balanceOf have several return case and all of them should have a way to return
rule balanceOf_multiReturn_2(
	env e,
	address user
) {
	requireInvariant discountCantExceed100Percent(user);
	uint256 index = indexAtTimestamp(e.block.timestamp);
	uint256 prevIndex = getUserCurrentIndex(user);
	uint256 discountPercent = getUserDiscountRate(user);
	uint256 scaledBalance = scaledBalanceOf(user);
	uint256 balance = balanceOf(e, user);

	uint256 calcBalance = rayMul(scaledBalance, index);

	satisfy scaledBalance != 0 && prevIndex == index;
}

// balanceOf have several return case and all of them should have a way to return
rule balanceOf_multiReturn_3(
	env e,
	address user
) {
	requireInvariant discountCantExceed100Percent(user);
	uint256 index = indexAtTimestamp(e.block.timestamp);
	uint256 prevIndex = getUserCurrentIndex(user);
	uint256 discountPercent = getUserDiscountRate(user);
	uint256 scaledBalance = scaledBalanceOf(user);
	uint256 balance = balanceOf(e, user);

	uint256 calcBalance = rayMul(scaledBalance, index);

	satisfy scaledBalance != 0 && prevIndex != index && discountPercent == 0;
}

// updateDiscountDistribution have several return case and all of them should have a way to return
rule updateDiscountDistribution_multiReturn_1(
	env e,    
	address sender,
    address recipient,
    uint256 senderDiscountTokenBalance,
    uint256 recipientDiscountTokenBalance,
    uint256 amount
) {
	uint256 recipientBalance = scaledBalanceOf(recipient);
	uint256 index = indexAtTimestamp(e.block.timestamp);
	uint256 discountPercent = getUserDiscountRate(sender);
	uint256 prevBalance = scaledBalanceOf(sender);
	uint256 balanceIncrease; uint256 discountScaled;
	balanceIncrease, discountScaled = accrueDebtOnActionCalculation(e, sender, prevBalance, discountPercent, index);
	uint256 supplyBefore = scaledTotalSupply();
	updateDiscountDistribution(e, sender, recipient, senderDiscountTokenBalance, recipientDiscountTokenBalance, amount);
	uint256 supplyAfter = scaledTotalSupply();
	satisfy recipientBalance == 0 && prevBalance != 0;
}

// updateDiscountDistribution have several return case and all of them should have a way to return
rule updateDiscountDistribution_multiReturn_2(
	env e,    
	address sender,
    address recipient,
    uint256 senderDiscountTokenBalance,
    uint256 recipientDiscountTokenBalance,
    uint256 amount
) {
	uint256 recipientBalance = scaledBalanceOf(recipient);
	uint256 index = indexAtTimestamp(e.block.timestamp);
	uint256 discountPercent = getUserDiscountRate(sender);
	uint256 prevBalance = scaledBalanceOf(sender);
	uint256 balanceIncrease; uint256 discountScaled;
	balanceIncrease, discountScaled = accrueDebtOnActionCalculation(e, sender, prevBalance, discountPercent, index);
	uint256 supplyBefore = scaledTotalSupply();
	updateDiscountDistribution(e, sender, recipient, senderDiscountTokenBalance, recipientDiscountTokenBalance, amount);
	uint256 supplyAfter = scaledTotalSupply();
	satisfy recipientBalance != 0 && prevBalance == 0;
}

// mint have several return case and all of them should have a way to return
rule mint_multiReturn_1(
	env e,
	address caller,
	address user,
	uint256 amount,
	uint256 index
) {
	require index == indexAtTimestamp(e.block.timestamp);
	uint256 amountScaled = rayDiv(amount, index);
	uint256 discountPercent = getUserDiscountRate(user);
	uint256 prevBalance = scaledBalanceOf(user);
	uint256 balanceIncrease; uint256 discountScaled;
	balanceIncrease, discountScaled = accrueDebtOnActionCalculation(e, user, prevBalance, discountPercent, index);
	uint256 supplyBefore = scaledTotalSupply();
	mint(e, caller, user, amount, index);
	uint256 supplyAfter = scaledTotalSupply();
	satisfy supplyBefore > supplyAfter; 
}

// mint have several return case and all of them should have a way to return
rule mint_multiReturn_2(
	env e,
	address caller,
	address user,
	uint256 amount,
	uint256 index
) {
	require index == indexAtTimestamp(e.block.timestamp);
	uint256 amountScaled = rayDiv(amount, index);
	uint256 discountPercent = getUserDiscountRate(user);
	uint256 prevBalance = scaledBalanceOf(user);
	uint256 balanceIncrease; uint256 discountScaled;
	balanceIncrease, discountScaled = accrueDebtOnActionCalculation(e, user, prevBalance, discountPercent, index);
	uint256 supplyBefore = scaledTotalSupply();
	mint(e, caller, user, amount, index);
	uint256 supplyAfter = scaledTotalSupply();
	satisfy supplyAfter > supplyBefore;
}

// burn have several return case and all of them should have a way to return
rule burn_multiReturn_1(
	env e,
	address user,
	uint256 amount,
	uint256 index
) {
	require index == indexAtTimestamp(e.block.timestamp);
	uint256 amountScaled = rayDiv(amount, index);
	uint256 balanceBeforeBurn = balanceOf(e, user);
	uint256 prevBalance = scaledBalanceOf(user);
	require prevBalance < balanceBeforeBurn;
	uint256 discountPercent = getUserDiscountRate(user);
	uint256 balanceIncrease; uint256 discountScaled;
	balanceIncrease, discountScaled = accrueDebtOnActionCalculation(e, user, prevBalance, discountPercent, index);
	burn(e, user, amount, index);
	satisfy amount == balanceBeforeBurn && discountScaled != 0;
}

// burn have several return case and all of them should have a way to return
rule burn_multiReturn_2(
	env e,
	address user,
	uint256 amount,
	uint256 index
) {
	require index == indexAtTimestamp(e.block.timestamp);
	uint256 amountScaled = rayDiv(amount, index);
	uint256 balanceBeforeBurn = balanceOf(e, user);
	uint256 prevBalance = scaledBalanceOf(user);
	uint256 discountPercent = getUserDiscountRate(user);
	uint256 balanceIncrease; uint256 discountScaled;
	balanceIncrease, discountScaled = accrueDebtOnActionCalculation(e, user, prevBalance, discountPercent, index);
	burn(e, user, amount, index);
	satisfy amount != balanceBeforeBurn;
}

// burn have several return case and all of them should have a way to return
rule burn_multiReturn_3(
	env e,
	address user,
	uint256 amount,
	uint256 index
) {
	require index == indexAtTimestamp(e.block.timestamp);
	uint256 amountScaled = rayDiv(amount, index);
	uint256 balanceBeforeBurn = balanceOf(e, user);
	uint256 prevBalance = scaledBalanceOf(user);
	uint256 discountPercent = getUserDiscountRate(user);
	uint256 balanceIncrease; uint256 discountScaled;
	balanceIncrease, discountScaled = accrueDebtOnActionCalculation(e, user, prevBalance, discountPercent, index);
	burn(e, user, amount, index);
	satisfy balanceIncrease > amount;
}

// burn have several return case and all of them should have a way to return
rule burn_multiReturn_4(
	env e,
	address user,
	uint256 amount,
	uint256 index
) {
	require index == indexAtTimestamp(e.block.timestamp);
	uint256 amountScaled = rayDiv(amount, index);
	uint256 balanceBeforeBurn = balanceOf(e, user);
	uint256 prevBalance = scaledBalanceOf(user);
	uint256 discountPercent = getUserDiscountRate(user);
	uint256 balanceIncrease; uint256 discountScaled;
	balanceIncrease, discountScaled = accrueDebtOnActionCalculation(e, user, prevBalance, discountPercent, index);
	burn(e, user, amount, index);
	satisfy balanceIncrease < amount;
}

// accrueDebtOnAction have several return case and all of them should have a way to return
rule accrueDebtOnAction_multiReturn_1(
    env e,
	address user,
    uint256 previousScaledBalance,
    uint256 discountPercent,
    uint256 index
) {
	uint256 balanceIncrease;
	uint256 discountScaled;
	uint256 prevIndex = getUserCurrentIndex(user);
	uint256 prevBalance = getBalanceFromInterest(user);
	require index >= prevIndex;
	
	balanceIncrease, discountScaled = accrueDebtOnAction(e, user, previousScaledBalance, discountPercent, index);
	
	mathint increase = rayMul(previousScaledBalance, index) - rayMul(previousScaledBalance, prevIndex);

	satisfy discountPercent != 0 && increase != 0 ;
}

// accrueDebtOnAction have several return case and all of them should have a way to return
rule accrueDebtOnAction_multiReturn_2(
    env e,
	address user,
    uint256 previousScaledBalance,
    uint256 discountPercent,
    uint256 index
) {
	uint256 balanceIncrease;
	uint256 discountScaled;
	uint256 prevIndex = getUserCurrentIndex(user);
	uint256 prevBalance = getBalanceFromInterest(user);
	require index >= prevIndex;
	
	balanceIncrease, discountScaled = accrueDebtOnAction(e, user, previousScaledBalance, discountPercent, index);
	
	mathint increase = rayMul(previousScaledBalance, index) - rayMul(previousScaledBalance, prevIndex);

	satisfy discountPercent == 0 || increase == 0 ;
}