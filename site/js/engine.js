/**
 * Client-side pairs trading simulation engine.
 * Exact JavaScript port of Python pipeline (src/signals.py, src/backtest.py, src/portfolio.py).
 */

(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.PairsEngine = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  /**
   * Run multi-pair portfolio simulation across a given period.
   *
   * @param {Object} periodPrices - { dates: string[], prices: { [ticker]: number[] } }
   * @param {Array} pairsMeta - Array of pair metadata objects (alpha, beta, mu_train, sd_train, leg_a, leg_b, pair)
   * @param {Object} options - Strategy and execution parameters
   *   - entry_z: float (default 2.0)
   *   - exit_z: float (default 0.5)
   *   - max_hold_days: int (default 30)
   *   - cost_per_side_bps: float (default 10.0)
   *   - borrow_bps_annual: float (default 50.0)
   *   - execution_lag: int (default 1)
   *   - initial_capital: float (default 1000000.0)
   */
  function runSimulation(periodPrices, pairsMeta, options) {
    options = options || {};
    const entry_z = options.entry_z !== undefined ? options.entry_z : 2.0;
    const exit_z = options.exit_z !== undefined ? options.exit_z : 0.5;
    const max_hold_days = options.max_hold_days !== undefined ? options.max_hold_days : 30;
    const cost_per_side_bps = options.cost_per_side_bps !== undefined ? options.cost_per_side_bps : 10.0;
    const borrow_bps_annual = options.borrow_bps_annual !== undefined ? options.borrow_bps_annual : 50.0;
    const execution_lag = options.execution_lag !== undefined ? options.execution_lag : 1;
    const initial_capital = options.initial_capital !== undefined ? options.initial_capital : 1000000.0;

    const dates = periodPrices.dates;
    const n = dates.length;
    const k_pairs = pairsMeta.length;
    const pair_capital = initial_capital / k_pairs;

    const pairResults = [];
    let allTrades = [];

    const portGrossPnl = new Float64Array(n);
    const portTradeCost = new Float64Array(n);
    const portBorrowCost = new Float64Array(n);
    const portNetPnl = new Float64Array(n);
    const portOpenPairs = new Int32Array(n);

    for (let pIdx = 0; pIdx < k_pairs; pIdx++) {
      const pm = pairsMeta[pIdx];
      const pA = periodPrices.prices[pm.leg_a];
      const pB = periodPrices.prices[pm.leg_b];

      const res = simulatePair({
        pairName: pm.pair,
        dates: dates,
        priceA: pA,
        priceB: pB,
        alpha: pm.alpha,
        beta: pm.beta,
        mu_train: pm.mu_train,
        sd_train: pm.sd_train,
        capital: pair_capital,
        entry_z: entry_z,
        exit_z: exit_z,
        max_hold_days: max_hold_days,
        cost_per_side_bps: cost_per_side_bps,
        borrow_bps_annual: borrow_bps_annual,
        execution_lag: execution_lag,
      });

      pairResults.push(res);
      allTrades = allTrades.concat(res.trades);

      for (let t = 0; t < n; t++) {
        portGrossPnl[t] += res.grossPnl[t];
        portTradeCost[t] += res.tradeCost[t];
        portBorrowCost[t] += res.borrowCost[t];
        portNetPnl[t] += res.netPnl[t];
        if (res.inPosition[t]) {
          portOpenPairs[t] += 1;
        }
      }
    }

    // Sort trades chronologically by entry_date, then exit_date, then pair
    allTrades.sort((a, b) => {
      if (a.entry_date !== b.entry_date) return a.entry_date.localeCompare(b.entry_date);
      if (a.exit_date !== b.exit_date) return a.exit_date.localeCompare(b.exit_date);
      return a.pair.localeCompare(b.pair);
    });

    const equity = new Float64Array(n);
    const grossEquity = new Float64Array(n);
    const drawdown = new Float64Array(n);

    let cumNet = 0.0;
    let cumGross = 0.0;
    let peakEquity = initial_capital;

    for (let t = 0; t < n; t++) {
      cumNet += portNetPnl[t];
      cumGross += portGrossPnl[t];
      equity[t] = initial_capital + cumNet;
      grossEquity[t] = initial_capital + cumGross;
      if (equity[t] > peakEquity) {
        peakEquity = equity[t];
      }
      drawdown[t] = peakEquity > 0 ? (equity[t] - peakEquity) / peakEquity : 0.0;
    }

    const totalGross = cumGross;
    const totalTradeCost = portTradeCost.reduce((a, b) => a + b, 0);
    const totalBorrowCost = portBorrowCost.reduce((a, b) => a + b, 0);
    const totalCosts = totalTradeCost + totalBorrowCost;
    const totalNet = cumNet;
    const endingEquity = initial_capital + totalNet;

    // Win rate
    const winningTrades = allTrades.filter((tr) => tr.net_pnl > 0);
    const winRate = allTrades.length > 0 ? winningTrades.length / allTrades.length : 0.0;

    return {
      dates: dates,
      equity: equity,
      grossEquity: grossEquity,
      drawdown: drawdown,
      openPairs: portOpenPairs,
      trades: allTrades,
      pairResults: pairResults,
      summary: {
        initialCapital: initial_capital,
        endingEquity: endingEquity,
        netPnl: totalNet,
        grossPnl: totalGross,
        totalCosts: totalCosts,
        tradeCosts: totalTradeCost,
        borrowCosts: totalBorrowCost,
        nTrades: allTrades.length,
        winRate: winRate,
      },
    };
  }

  /**
   * Simulate a single pair.
   */
  function simulatePair(cfg) {
    const dates = cfg.dates;
    const n = dates.length;
    const pA = cfg.priceA;
    const pB = cfg.priceB;
    const alpha = cfg.alpha;
    const beta = cfg.beta;
    const mu = cfg.mu_train;
    const sd = cfg.sd_train;
    const capital = cfg.capital;

    const entry_z = cfg.entry_z;
    const exit_z = cfg.exit_z;
    const max_hold_days = cfg.max_hold_days;
    const costRate = (cfg.cost_per_side_bps / 10000.0);
    const dailyBorrowRate = (cfg.borrow_bps_annual / 10000.0) / 252.0;
    const lag = cfg.execution_lag;

    // 1. Compute spread & z-score
    const z = new Float64Array(n);
    for (let t = 0; t < n; t++) {
      const sp = Math.log(pA[t]) - alpha - beta * Math.log(pB[t]);
      z[t] = (sp - mu) / sd;
    }

    // 2. Generate signals via state machine (src/signals.py)
    const stateArr = new Int32Array(n);
    const entryFlagArr = new Uint8Array(n);
    const exitFlagArr = new Uint8Array(n);
    const exitReasonArr = new Array(n);
    const daysHeldArr = new Int32Array(n);

    let currentState = 0;
    let daysHeld = 0;

    for (let t = 0; t < n; t++) {
      const zt = z[t];
      const isNan = Number.isNaN(zt);

      if (currentState === 0) {
        if (!isNan) {
          if (zt >= entry_z) {
            currentState = -1;
            daysHeld = 1;
            stateArr[t] = -1;
            entryFlagArr[t] = 1;
            daysHeldArr[t] = 1;
          } else if (zt <= -entry_z) {
            currentState = 1;
            daysHeld = 1;
            stateArr[t] = 1;
            entryFlagArr[t] = 1;
            daysHeldArr[t] = 1;
          } else {
            stateArr[t] = 0;
            daysHeldArr[t] = 0;
          }
        } else {
          stateArr[t] = 0;
          daysHeldArr[t] = 0;
        }
      } else {
        daysHeld += 1;
        let exitTriggered = false;
        let reason = null;

        if (!isNan) {
          if (currentState === 1 && zt >= -exit_z) {
            exitTriggered = true;
            reason = 'mean_revert';
          } else if (currentState === -1 && zt <= exit_z) {
            exitTriggered = true;
            reason = 'mean_revert';
          } else if (daysHeld >= max_hold_days) {
            exitTriggered = true;
            reason = 'max_hold';
          }
        } else {
          if (daysHeld >= max_hold_days) {
            exitTriggered = true;
            reason = 'max_hold';
          }
        }

        if (exitTriggered) {
          exitFlagArr[t] = 1;
          exitReasonArr[t] = reason;
          daysHeldArr[t] = daysHeld;
          stateArr[t] = 0;
          currentState = 0;
          daysHeld = 0;
        } else {
          stateArr[t] = currentState;
          daysHeldArr[t] = daysHeld;
        }
      }
    }

    // 3. Backtest pair execution loop (src/backtest.py)
    const absBeta = Math.abs(beta);
    const denom = 1.0 + absBeta;
    const wA = 1.0 / denom;
    const wB = -beta / denom;
    const notionalA = capital * Math.abs(wA);
    const notionalB = capital * Math.abs(wB);
    const sgnBeta = beta >= 0 ? 1.0 : -1.0;

    const grossPnlArr = new Float64Array(n);
    const tradeCostArr = new Float64Array(n);
    const borrowCostArr = new Float64Array(n);
    const netPnlArr = new Float64Array(n);
    const inPosArr = new Uint8Array(n);

    let inPos = false;
    let currDir = 0;
    let currSharesA = 0.0;
    let currSharesB = 0.0;
    let currShortNotional = 0.0;
    let currEntryIdx = -1;
    let currSigIdx = -1;
    let currEntryPA = 0.0;
    let currEntryPB = 0.0;
    let currEntryCost = 0.0;
    let currTradeGross = 0.0;
    let currTradeBorrow = 0.0;

    const pendingEntries = [];
    const pendingExits = [];
    const tradeRecords = [];

    for (let t = 0; t < n; t++) {
      // 1. Accrue daily gross P&L and borrow cost from prior close
      if (inPos) {
        const pnlA = currSharesA * (pA[t] - pA[t - 1]);
        const pnlB = currSharesB * (pB[t] - pB[t - 1]);
        const dayGross = pnlA + pnlB;
        const dayBorrow = dailyBorrowRate * currShortNotional;

        grossPnlArr[t] = dayGross;
        borrowCostArr[t] = dayBorrow;
        currTradeGross += dayGross;
        currTradeBorrow += dayBorrow;
      }

      // 2. Process fills at CLOSE of bar t
      let exitNow = false;
      let exitReasonStr = null;
      let exitSigDate = null;

      if (inPos) {
        if (pendingExits.length > 0 && pendingExits[0].fill_idx === t) {
          const pe = pendingExits.shift();
          exitNow = true;
          exitReasonStr = pe.exit_reason;
          exitSigDate = dates[pe.signal_idx];
        } else if (t === n - 1) {
          exitNow = true;
          if (pendingExits.length > 0) {
            const pe = pendingExits.shift();
            exitReasonStr = pe.exit_reason;
            exitSigDate = dates[pe.signal_idx];
          } else {
            exitReasonStr = 'period_end';
            exitSigDate = dates[t];
          }
        }
      }

      if (exitNow) {
        const exitPA = pA[t];
        const exitPB = pB[t];
        const exitNotionalA = Math.abs(currSharesA) * exitPA;
        const exitNotionalB = Math.abs(currSharesB) * exitPB;
        const exitCost = costRate * (exitNotionalA + exitNotionalB);

        tradeCostArr[t] += exitCost;
        const totalTradeCosts = currEntryCost + exitCost + currTradeBorrow;
        const netTradePnl = currTradeGross - totalTradeCosts;
        const holdingDays = t - currEntryIdx;

        tradeRecords.push({
          pair: cfg.pairName,
          direction: currDir,
          signal_date: dates[currSigIdx],
          entry_date: dates[currEntryIdx],
          exit_signal_date: exitSigDate,
          exit_date: dates[t],
          holding_days: holdingDays,
          entry_price_a: currEntryPA,
          entry_price_b: currEntryPB,
          exit_price_a: exitPA,
          exit_price_b: exitPB,
          gross_pnl: currTradeGross,
          costs: totalTradeCosts,
          net_pnl: netTradePnl,
          exit_reason: exitReasonStr,
        });

        inPos = false;
        currDir = 0;
        currSharesA = 0.0;
        currSharesB = 0.0;
        currShortNotional = 0.0;
      }

      // Check entry fill
      if (!inPos && t < n - 1 && pendingEntries.length > 0 && pendingEntries[0].fill_idx === t) {
        const pe = pendingEntries.shift();
        const fillPA = pA[t];
        const fillPB = pB[t];
        currDir = pe.direction;

        currSharesA = currDir * (notionalA / fillPA);
        currSharesB = -currDir * sgnBeta * (notionalB / fillPB);

        if (currSharesA < 0.0) {
          currShortNotional = notionalA;
        } else if (currSharesB < 0.0) {
          currShortNotional = notionalB;
        } else {
          currShortNotional = 0.0;
        }

        const entryTradedNotional = notionalA + notionalB;
        currEntryCost = costRate * entryTradedNotional;
        tradeCostArr[t] += currEntryCost;

        inPos = true;
        currEntryIdx = t;
        currSigIdx = pe.signal_idx;
        currEntryPA = fillPA;
        currEntryPB = fillPB;
        currTradeGross = 0.0;
        currTradeBorrow = 0.0;
      }

      // 3. Schedule new signals emitted at CLOSE of bar t
      if (exitFlagArr[t]) {
        pendingExits.push({
          fill_idx: t + lag,
          signal_idx: t,
          exit_reason: exitReasonArr[t] || 'signal_exit',
        });
      }
      if (entryFlagArr[t]) {
        pendingEntries.push({
          fill_idx: t + lag,
          signal_idx: t,
          direction: stateArr[t],
        });
      }

      // 4. Bar net P&L
      netPnlArr[t] = grossPnlArr[t] - tradeCostArr[t] - borrowCostArr[t];
      inPosArr[t] = inPos ? 1 : 0;
    }

    return {
      pair: cfg.pairName,
      z: z,
      grossPnl: grossPnlArr,
      tradeCost: tradeCostArr,
      borrowCost: borrowCostArr,
      netPnl: netPnlArr,
      inPosition: inPosArr,
      trades: tradeRecords,
    };
  }

  return {
    runSimulation: runSimulation,
    simulatePair: simulatePair,
  };
});
