/**
 * Node.js automated parity test for the browser pairs trading simulation engine.
 * Validates JS engine trade-by-trade against trades.json and periods.json within $1 tolerance.
 */

const fs = require('fs');
const path = require('path');
const engine = require('../js/engine.js');

const DATA_DIR = path.join(__dirname, '..', 'data');

function loadJson(name) {
  const filePath = path.join(DATA_DIR, name + '.json');
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function runParityTest() {
  console.log('Running JavaScript simulation engine parity test...');

  const pricesData = loadJson('prices');
  const pythonTrades = loadJson('trades');
  const periodsData = loadJson('periods');

  const baselineOptions = {
    entry_z: 2.0,
    exit_z: 0.5,
    max_hold_days: 30,
    cost_per_side_bps: 10.0,
    borrow_bps_annual: 50.0,
    execution_lag: 1,
    initial_capital: 1000000.0,
  };

  const periods = ['train', 'validation', 'test'];
  let totalErrors = 0;
  let maxTradeDiff = 0.0;
  let maxPeriodDiff = 0.0;
  let totalTradesChecked = 0;

  for (const period of periods) {
    console.log(`\nTesting period: ${period.toUpperCase()}`);
    const periodPrices = pricesData.periods[period];
    const expectedPeriod = periodsData.find((p) => p.period === period);
    const expectedTrades = pythonTrades.filter((t) => t.period === period);

    const result = engine.runSimulation(periodPrices, pricesData.pairs, baselineOptions);

    console.log(`  Engine trades: ${result.trades.length}, Expected trades: ${expectedTrades.length}`);
    if (result.trades.length !== expectedTrades.length) {
      console.error(`  ERROR: Trade count mismatch! got ${result.trades.length}, expected ${expectedTrades.length}`);
      totalErrors++;
    }

    // Check each trade
    for (let i = 0; i < expectedTrades.length; i++) {
      const exp = expectedTrades[i];
      // Find matching simulated trade by pair and entry_date
      const got = result.trades.find((t) => t.pair === exp.pair && t.entry_date === exp.entry_date);

      if (!got) {
        console.error(`  ERROR: Missing trade for ${exp.pair} on entry ${exp.entry_date}`);
        totalErrors++;
        continue;
      }

      totalTradesChecked++;
      const pnlDiff = Math.abs(got.net_pnl - exp.net_pnl);
      if (pnlDiff > maxTradeDiff) {
        maxTradeDiff = pnlDiff;
      }

      if (got.exit_date !== exp.exit_date) {
        console.error(`  ERROR: Exit date mismatch for ${exp.pair} (entry ${exp.entry_date}): got ${got.exit_date}, expected ${exp.exit_date}`);
        totalErrors++;
      }

      if (got.direction !== exp.direction) {
        console.error(`  ERROR: Direction mismatch for ${exp.pair}: got ${got.direction}, expected ${exp.direction}`);
        totalErrors++;
      }

      if (got.exit_reason !== exp.exit_reason) {
        console.error(`  ERROR: Exit reason mismatch for ${exp.pair}: got ${got.exit_reason}, expected ${exp.exit_reason}`);
        totalErrors++;
      }

      if (pnlDiff > 1.0) {
        console.error(`  ERROR: Net P&L mismatch for ${exp.pair} (${exp.entry_date} to ${exp.exit_date}): got ${got.net_pnl.toFixed(2)}, expected ${exp.net_pnl.toFixed(2)}, diff = $${pnlDiff.toFixed(2)}`);
        totalErrors++;
      }
    }

    // Check period total net P&L
    const periodPnlDiff = Math.abs(result.summary.netPnl - expectedPeriod.net_pnl);
    if (periodPnlDiff > maxPeriodDiff) {
      maxPeriodDiff = periodPnlDiff;
    }
    console.log(`  Period Net P&L: got $${result.summary.netPnl.toFixed(2)}, expected $${expectedPeriod.net_pnl.toFixed(2)}, diff = $${periodPnlDiff.toFixed(2)}`);

    if (periodPnlDiff > 1.0) {
      console.error(`  ERROR: Period Net P&L diff exceeds $1.00 tolerance! ($${periodPnlDiff.toFixed(2)})`);
      totalErrors++;
    }
  }

  console.log('\n================ PARITY TEST SUMMARY ================');
  console.log(`Total trades validated: ${totalTradesChecked} / 95`);
  console.log(`Max single trade P&L difference: $${maxTradeDiff.toFixed(4)}`);
  console.log(`Max period total P&L difference: $${maxPeriodDiff.toFixed(4)}`);
  console.log(`Total mismatches / errors: ${totalErrors}`);

  if (totalErrors === 0 && maxTradeDiff <= 1.0 && maxPeriodDiff <= 1.0) {
    console.log('\n[PASS] JavaScript simulation engine achieved EXACT PARITY (< $1) with Python results!');
    process.exit(0);
  } else {
    console.error('\n[FAIL] Parity test failed!');
    process.exit(1);
  }
}

runParityTest();
