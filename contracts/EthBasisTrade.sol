// SPDX-License-Identifier: MIT
pragma solidity 0.8.10;
pragma abicoder v2;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";
import "@uniswap/v3-periphery/contracts/libraries/TransferHelper.sol";
import "@uniswap/v3-periphery/contracts/interfaces/ISwapRouter.sol";
import "@uniswap/v3-core/contracts/interfaces/IUniswapV3Pool.sol";
import "@uniswap/v3-core/contracts/interfaces/pool/IUniswapV3PoolImmutables.sol";
import "@overlay/v1-core/contracts/interfaces/IOverlayV1Market.sol";
import "@overlay/v1-core/contracts/interfaces/IOverlayV1Token.sol";
import "@overlay/v1-core/contracts/libraries/FixedPoint.sol";
import "@overlay/v1-core/contracts/libraries/Risk.sol";
import "@overlay/v1-periphery/contracts/interfaces/IOverlayV1State.sol";

// forks of uniswap libraries for solidity^0.8.10
import "@overlay/v1-core/contracts/libraries/uniswap/v3-core/FullMath.sol";
import "@overlay/v1-core/contracts/libraries/uniswap/v3-core/TickMath.sol";

contract EthBasisTrade {
    using FixedPoint for uint256;
    uint256 internal constant ONE = 1e18; // 18 decimal places

    ISwapRouter public immutable swapRouter;
    IOverlayV1Token public immutable ovl;
    IOverlayV1Market public immutable ovlMarket;
    IOverlayV1State public immutable ovlState;
    address public immutable baseToken;
    address public immutable pool;
    address public immutable owner;

    uint256 public posId;

    /// @dev when currState = 0, contract holds spot WETH only
    /// @dev when currState = 1, contract holds a long on ETH/OVL
    uint256 public currState = 0; // TODO: change to enum

    constructor(
        ISwapRouter _swapRouter,
        address _ovlState,
        address _baseToken,
        address _ovl,
        address _pool,
        address _ovlMarket
    ) {
        owner = msg.sender;
        swapRouter = _swapRouter;
        ovlState = IOverlayV1State(_ovlState);
        baseToken = _baseToken;
        ovl = IOverlayV1Token(_ovl);
        pool = _pool;
        ovlMarket = IOverlayV1Market(_ovlMarket);
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "!owner");
        _;
    }

    /// TODO: Currently taking WETH deposits. Change to accept ETH deposits.
    function depositWeth(uint256 _amountIn) external onlyOwner {
        IERC20(baseToken).transferFrom(msg.sender, address(this), _amountIn);
    }

    function getOffsetTick(bool _toOvl) public view returns (int24 tick_) {
        int24 tickCurr;
        (, tickCurr, , , , , ) = IUniswapV3Pool(pool).slot0();
        if (_toOvl) {
            tick_ = tickCurr - 200;
        } else {
            tick_ = tickCurr + 200;
        }
    }

    /// @dev copied: ovlerlay-market/v1-core/contracts/feeds/uniswapv3/OverlayV1UniswapV3Feed.sol
    function getQuoteAtTick(
        int24 tick,
        uint128 baseAmount,
        address baseToken,
        address quoteToken
    ) public view returns (uint256 quoteAmount_) {
        uint160 sqrtRatioX96 = TickMath.getSqrtRatioAtTick(tick);

        // Calculate quoteAmount with better precision if it doesn't overflow when multiplied by
        // itself
        if (sqrtRatioX96 <= type(uint128).max) {
            uint256 ratioX192 = uint256(sqrtRatioX96) * sqrtRatioX96;
            quoteAmount_ = baseToken < quoteToken
                ? FullMath.mulDiv(ratioX192, baseAmount, 1 << 192)
                : FullMath.mulDiv(1 << 192, baseAmount, ratioX192);
        } else {
            uint256 ratioX128 = FullMath.mulDiv(sqrtRatioX96, sqrtRatioX96, 1 << 64);
            quoteAmount_ = baseToken < quoteToken
                ? FullMath.mulDiv(ratioX128, baseAmount, 1 << 128)
                : FullMath.mulDiv(1 << 128, baseAmount, ratioX128);
        }
    }

    function swapSingleToBaseTokenUniV3(uint256 _amountIn)
        public
        onlyOwner
        returns (uint256 amountOut_)
    {
        address tokenIn = address(ovl);
        address tokenOut = baseToken;

        int24 tick = getOffsetTick(false);
        uint256 amountOutMinimum = getQuoteAtTick(tick, uint128(_amountIn), tokenIn, tokenOut);

        TransferHelper.safeApprove(tokenIn, address(swapRouter), _amountIn);

        ISwapRouter.ExactInputSingleParams memory params = ISwapRouter.ExactInputSingleParams({
            tokenIn: tokenIn,
            tokenOut: tokenOut,
            fee: IUniswapV3PoolImmutables(pool).fee(),
            recipient: address(this),
            deadline: block.timestamp + 120,
            amountIn: _amountIn,
            amountOutMinimum: amountOutMinimum,
            sqrtPriceLimitX96: 0
        });

        amountOut_ = swapRouter.exactInputSingle(params);
    }

    function swapSingleToOvlUniV3(uint256 _amountIn)
        public
        onlyOwner
        returns (uint256 amountOut_)
    {
        address tokenIn = baseToken;
        address tokenOut = address(ovl);

        int24 tick = getOffsetTick(true);
        uint256 amountOutMinimum = getQuoteAtTick(tick, uint128(_amountIn), tokenIn, tokenOut);

        TransferHelper.safeApprove(tokenIn, address(swapRouter), _amountIn);

        ISwapRouter.ExactInputSingleParams memory params = ISwapRouter.ExactInputSingleParams({
            tokenIn: tokenIn,
            tokenOut: tokenOut,
            fee: IUniswapV3PoolImmutables(pool).fee(),
            recipient: address(this),
            deadline: block.timestamp + 120,
            amountIn: _amountIn,
            amountOutMinimum: amountOutMinimum,
            sqrtPriceLimitX96: 0
        });

        amountOut_ = swapRouter.exactInputSingle(params);
    }

    function buildOvlPosition(uint256 _amountInWithFees, uint256 _priceLimit)
        public
        onlyOwner
        returns (uint256 positionId_)
    {
        (uint256 collateral, uint256 fee) = getOverlayTradingFee(_amountInWithFees);
        TransferHelper.safeApprove(address(ovl), address(ovlMarket), collateral + fee);
        positionId_ = ovlMarket.build(collateral, ONE, true, _priceLimit);
    }

    function unwindOvlPosition(
        uint256 _positionId,
        uint256 _fraction,
        uint256 _priceLimit
    ) public onlyOwner {
        ovlMarket.unwind(_positionId, _fraction, _priceLimit);
    }

    /// @notice collateral is equal to notional size since leverage is always 1 for basis trade
    function getOverlayTradingFee(uint256 _amountInWithFees)
        public
        view
        returns (uint256 collateral_, uint256 fee_)
    {
        uint256 tradingFeeRate = ovlMarket.params(uint256(Risk.Parameters.TradingFeeRate));
        collateral_ = _amountInWithFees.divDown(ONE + tradingFeeRate);
        fee_ = collateral_.mulUp(tradingFeeRate);
    }

    function unwindAndSwap(
        uint256 _posId,
        uint256 _fraction,
        uint256 _priceLimit
    ) public onlyOwner returns (uint256) {
        unwindOvlPosition(_posId, _fraction, _priceLimit);
        uint256 ovlAmount = ovl.balanceOf(address(this));
        return swapSingleToBaseTokenUniV3(ovlAmount);
    }

    function swapAndBuild() public onlyOwner {
        uint256 baseTokenAmount = IERC20(baseToken).balanceOf(address(this));
        uint256 ovlAmount = swapSingleToOvlUniV3(baseTokenAmount);
        posId = buildOvlPosition(ovlAmount, 10e18);
    }

    function update() external {
        int256 fundingRate = ovlState.fundingRate(ovlMarket);
        if (fundingRate < 0) {
            require(currState == 0, "Already long");
            currState = 1;
            swapAndBuild();
        } else {
            require(currState == 1, "Already idle");
            currState = 0;
            unwindAndSwap(posId, ONE, 0);
        }
    }

    function withdraw() external onlyOwner {
        uint256 baseTokenAmount;
        if (currState == 0) {
            baseTokenAmount = IERC20(baseToken).balanceOf(address(this));
            _withdraw(baseTokenAmount);
        } else {
            baseTokenAmount = unwindAndSwap(posId, ONE, 0);
            _withdraw(baseTokenAmount);
        }
    }

    function _withdraw(uint256 _baseTokenAmount) public onlyOwner {
        IERC20(baseToken).transfer(msg.sender, _baseTokenAmount);
    }
}
