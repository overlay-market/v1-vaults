// SPDX-License-Identifier: MIT
pragma solidity 0.8.10;
pragma abicoder v2;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@uniswap/v3-periphery/contracts/libraries/TransferHelper.sol";
import "@uniswap/v3-periphery/contracts/interfaces/ISwapRouter.sol";
import "@uniswap/v3-core/contracts/interfaces/IUniswapV3Pool.sol";
import "@overlay/v1-core/contracts/interfaces/IOverlayV1Market.sol";
import "@overlay/v1-core/contracts/interfaces/IOverlayV1Token.sol";
import "@overlay/v1-core/contracts/libraries/FixedPoint.sol";

// forks of uniswap libraries for solidity^0.8.10
import "./libraries/uniswapv3-core/FullMath.sol";
import "./libraries/uniswapv3-core/TickMath.sol";

contract EthBasisTrade {
    using FixedPoint for uint256;
    uint256 public immutable ONE = 1e18;

    ISwapRouter public immutable swapRouter;
    IOverlayV1Token public immutable ovl;
    IOverlayV1Market public immutable ovlMarket;
    address public immutable WETH9;
    address public immutable pool;

    // tracking info of depositors who depostied
    // before contract went long
    uint256 public totalPre;
    address[] public depositorAddressPre;
    struct dInfoPreStruct {
        uint256 amount;
        uint256 arrIdx;
    }
    mapping(address => dInfoPreStruct) public depositorInfoPre;
    uint256 public depositorIdPre;

    // tracking info of depositors who deposited
    // after contract went long
    address[] public depositorAddressPost;
    mapping (address => uint256) depositorAddressPostIdx;
    struct dInfoPostStruct {
        uint256 amount;
        uint256 posId;
    }
    mapping(address => dInfoPostStruct[]) public depositorInfoPost;

    /// @dev when currState = 0, contract holds spot WETH only
    /// @dev when currState = 1, contract holds a long on ETH/OVL
    uint256 public currState = 0; // TODO: change to enum

    uint24 public constant poolFee = 3000;

    /// @param toState the state to which the contract transitioned
    /// @param amount the amount of weth going long or getting unwound
    event Update(uint256 toState, uint256 amount);

    constructor(
        ISwapRouter _swapRouter,
        address _WETH9,
        address _ovl,
        address _pool,
        address _ovlMarket
    ) {
        swapRouter = _swapRouter;
        WETH9 = _WETH9;
        ovl = IOverlayV1Token(_ovl);
        pool = _pool;
        ovlMarket = IOverlayV1Market(_ovlMarket);
    }

    /// TODO: Currently taking WETH deposits. Change to accept ETH deposits.
    function depositWeth(uint256 amountIn) public {
        IERC20(WETH9).transferFrom(msg.sender, address(this), amountIn);
        if (currState == 0) {
            totalPre = totalPre + amountIn;
            if (depositorInfoPre[msg.sender].amount > 0) {
                depositorInfoPre[msg.sender].amount += amountIn;
            } else {
                depositorAddressPre.push(msg.sender);
                depositorInfoPre[msg.sender].arrIdx = depositorAddressPre.length - 1;
                depositorInfoPre[msg.sender].amount = amountIn;
            }
        } else {
            updatePost(amountIn);
        }
    }

    /// @dev similar to getQuoteAtTick in uniswap v3
    function getQuoteAtTick(
        bool toEth,
        uint128 baseAmount,
        address baseToken,
        address quoteToken
    ) public view returns (uint256 quoteAmount) {
        int24 tick;
        int24 tick_curr;
        (, tick_curr, , , , , ) = IUniswapV3Pool(pool).slot0();
        if (toEth == true) {
            tick = tick_curr + 200;
        } else {
            tick = tick_curr - 200;
        }
        uint160 sqrtRatioX96 = TickMath.getSqrtRatioAtTick(tick);
        // Calculate quoteAmount with better precision if
        // it doesn't overflow when multiplied by itself
        if (sqrtRatioX96 <= type(uint128).max) {
            uint256 ratioX192 = uint256(sqrtRatioX96) * sqrtRatioX96;
            quoteAmount = baseToken < quoteToken
                ? FullMath.mulDiv(ratioX192, baseAmount, 1 << 192)
                : FullMath.mulDiv(1 << 192, baseAmount, ratioX192);
        } else {
            uint256 ratioX128 = FullMath.mulDiv(sqrtRatioX96, sqrtRatioX96, 1 << 64);
            quoteAmount = baseToken < quoteToken
                ? FullMath.mulDiv(ratioX128, baseAmount, 1 << 128)
                : FullMath.mulDiv(1 << 128, baseAmount, ratioX128);
        }
    }

    function swapExactInputSingle(uint256 amountIn, bool toEth)
        public
        returns (uint256 amountOut)
    {
        address tokenIn;
        address tokenOut;

        if (toEth == true) {
            tokenIn = address(ovl);
            tokenOut = WETH9;
        } else {
            tokenIn = WETH9;
            tokenOut = address(ovl);
        }
        uint256 amountOutFactor = getQuoteAtTick(toEth, 1e18, tokenIn, tokenOut);
        uint256 amountOutMinimum = FullMath.mulDiv(amountOutFactor, amountIn, 1e18);

        TransferHelper.safeApprove(tokenIn, address(swapRouter), amountIn);

        ISwapRouter.ExactInputSingleParams memory params = ISwapRouter.ExactInputSingleParams({
            tokenIn: tokenIn,
            tokenOut: tokenOut,
            fee: poolFee,
            recipient: address(this),
            deadline: block.timestamp + 120,
            amountIn: amountIn,
            amountOutMinimum: amountOutMinimum,
            sqrtPriceLimitX96: 0
        });

        amountOut = swapRouter.exactInputSingle(params);
    }

    function buildOvlPosition(
        uint256 collateral,
        uint256 fee,
        uint256 priceLimit
    ) public returns (uint256 positionId_) {
        TransferHelper.safeApprove(address(ovl), address(ovlMarket), collateral + fee);
        positionId_ = ovlMarket.build(collateral, 1e18, true, priceLimit);
    }

    function unwindOvlPosition(
        uint256 positionId,
        uint256 fraction,
        uint256 priceLimit
    ) public {
        ovlMarket.unwind(positionId, fraction, priceLimit);
    }

    /// @notice collateral is equal to notional size since leverage is always 1 for basis trade
    function getOverlayTradingFee(uint256 totalSize)
        public
        view
        returns (uint256 collateral, uint256 fee)
    {
        collateral = totalSize.divDown(1e18 + ovlMarket.params(11));
        fee = collateral.mulUp(ovlMarket.params(11));
    }

    function update(bool wethToLong) external {
        if (wethToLong) {
            currState = 1;
            uint256 ovlTotalPre = swapExactInputSingle(totalPre, false);
            (uint256 collateral, uint256 fee) = getOverlayTradingFee(ovlTotalPre);
            depositorIdPre = buildOvlPosition(collateral, fee, 10e18); // TODO: fix price limit
        } else {
            currState = 0;
            uint256 deltaPerc;
            uint256 i;
            uint256 j;
            uint256 ovlBalancePreUnwind;
            uint256 ovlAmount;
            uint256 ethAmount;
            ovlBalancePreUnwind = ovl.balanceOf(address(this));
            unwindOvlPosition(depositorIdPre, 1e18, 0); // TODO: fix price limit
            ovlAmount = ovl.balanceOf(address(this)) - ovlBalancePreUnwind;
            ethAmount = swapExactInputSingle(ovlAmount, true);
            // TODO: subtracting 10 wei for each address. check if right way to avoid rounding issues.
            // if yes, then write a function to use this dust when enough accumulated
            uint256 amountToSplit = ethAmount - (10 * depositorAddressPre.length);
            if (amountToSplit >= totalPre) {
                uint256 delta = amountToSplit - totalPre;
                deltaPerc = delta.divDown(totalPre) + 1e18; // TODO: better name reqd since 1e18 added
            } else {
                uint256 delta = totalPre - amountToSplit;
                deltaPerc = 1e18 - delta.divDown(totalPre); // TODO: better name reqd since 1e18 added
            }
            for (i = 0; i < depositorAddressPre.length; i += 1) {
                depositorInfoPre[depositorAddressPre[i]].amount =
                    depositorInfoPre[depositorAddressPre[i]].amount.mulDown(deltaPerc);
            }
            totalPre = ethAmount;

            for (i = 0; i < depositorAddressPost.length; i += 1) {
                for (j = 0; j < depositorInfoPost[depositorAddressPost[i]].length; j += 1) {
                    ovlBalancePreUnwind = ovl.balanceOf(address(this));
                    unwindOvlPosition(depositorInfoPost[depositorAddressPost[i]][j].posId , 1e18, 0); // TODO: fix price limit
                    ovlAmount = ovl.balanceOf(address(this)) - ovlBalancePreUnwind;
                    ethAmount = swapExactInputSingle(ovlAmount, true);
                    totalPre += ethAmount;
                    depositorInfoPre[depositorAddressPost[i]].amount += ethAmount;
                }
                depositorAddressPre.push(depositorAddressPost[i]);
            }
        }
    }

    function updatePost(uint256 amount) internal {
        depositorAddressPost.push(msg.sender);
        depositorAddressPostIdx[msg.sender] = depositorAddressPost.length - 1;
        dInfoPostStruct memory dInfo;
        dInfo.amount = amount;
        uint256 ovlTotalPre = swapExactInputSingle(amount, false);
        (uint256 collateral, uint256 fee) = getOverlayTradingFee(ovlTotalPre);
        dInfo.posId = buildOvlPosition(collateral, fee, 10e18); // TODO: fix price limit
        depositorInfoPost[msg.sender].push(dInfo);
    }


    function withdrawIdle(uint256 percentage) public returns (uint256) {
        require(currState == 0, "!idle");
        require(percentage <= ONE, ">100%");
        
        uint256 ethAmount;
        ethAmount = depositorInfoPre[msg.sender].amount.mulDown(percentage);
        depositorInfoPre[msg.sender].amount = depositorInfoPre[msg.sender].amount - ethAmount;
        if (depositorInfoPre[msg.sender].amount < 10) {
            depositorInfoPre[msg.sender].amount = 0;
            depositorInfoPre[depositorAddressPre[depositorAddressPre.length - 1]].arrIdx = depositorInfoPre[msg.sender].arrIdx;
            depositorAddressPre[depositorInfoPre[msg.sender].arrIdx] = depositorAddressPre[depositorAddressPre.length - 1];
            depositorAddressPre.pop();
            depositorInfoPre[msg.sender].arrIdx = 0;
        }
        TransferHelper.safeApprove(WETH9, msg.sender, ethAmount);
        IERC20(WETH9).transferFrom(address(this), msg.sender, ethAmount);
        return ethAmount;
    }

    function withdrawLongPreDepositor(uint256 percentage) public returns (uint256 ethAmount) {
        require(currState == 1, "!long");
        require(percentage <= ONE, ">100%");
        require(depositorInfoPre[msg.sender].amount > 0, "!deposit");
        
        uint256 depShare = depositorInfoPre[msg.sender].amount.divDown(totalPre);
        uint256 withdrawShare = depShare.mulDown(percentage);
        depositorInfoPre[msg.sender].amount = depositorInfoPre[msg.sender].amount.mulDown(ONE - percentage); // TODO: check rounding issues
        if (percentage == ONE) {
            depositorInfoPre[msg.sender].amount = 0;
            depositorInfoPre[depositorAddressPre[depositorAddressPre.length - 1]].arrIdx = depositorInfoPre[msg.sender].arrIdx;
            depositorAddressPre[depositorInfoPre[msg.sender].arrIdx] = depositorAddressPre[depositorAddressPre.length - 1];
            depositorAddressPre.pop();
            depositorInfoPre[msg.sender].arrIdx = 0;
        }
        ethAmount = _withdrawLong(depositorIdPre, withdrawShare);
    }
    
    function withdrawLongPostDepositor(uint256 percentage, uint256 idx) public returns (uint256 ethAmount) {
        require(currState == 1, "!long");
        require(percentage <= ONE, ">100%");
        require(depositorInfoPost[msg.sender][idx].amount > 0, "!deposit");
        
        uint256 pos = depositorInfoPost[msg.sender][idx].posId;
        
        if (percentage == ONE) {
            depositorAddressPostIdx[depositorAddressPost[depositorAddressPost.length - 1]] = depositorAddressPostIdx[msg.sender];
            depositorAddressPost[depositorAddressPostIdx[msg.sender]] = depositorAddressPost[depositorAddressPost.length - 1];
            depositorAddressPost.pop();
            depositorAddressPostIdx[msg.sender] = 0;
            
            depositorInfoPost[msg.sender][idx] = depositorInfoPost[msg.sender][depositorInfoPost[msg.sender].length - 1];
            depositorInfoPost[msg.sender].pop();
        }
        ethAmount = _withdrawLong(pos, percentage);
    }

    function _withdrawLong(uint256 pos, uint256 percentage) internal returns (uint256 ethAmount) {
        require(percentage <= ONE, ">100%");

        uint256 ovlBalancePreUnwind = ovl.balanceOf(address(this));
        unwindOvlPosition(pos, percentage, 0); // TODO: fix price limit
        uint256 ovlAmount = ovl.balanceOf(address(this)) - ovlBalancePreUnwind;
        ethAmount = swapExactInputSingle(ovlAmount, true);
        TransferHelper.safeApprove(WETH9, msg.sender, ethAmount);
        IERC20(WETH9).transferFrom(address(this), msg.sender, ethAmount);
    }

    function getDepositorAddressPreLength() public view returns (uint256) {
        return depositorAddressPre.length;
    }
}
