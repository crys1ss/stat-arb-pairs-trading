/**
 * What-If Playground Controller.
 * Interactive strategy parameter experimentation using the verified PairsEngine.
 */

(function () {
  'use strict';

  const CAPITAL = 1000000;
  const MINUS = '−';

  const usd = (v, signed) => {
    const r = Math.round(v);
    return (r < 0 ? MINUS : (signed && r > 0 ? '+' : '')) + '$' + d3.format(',.0f')(Math.abs(r));
  };
  const usdC = (v) => (v < 0 ? MINUS : '') + '$' + (Math.abs(v) < 1000 ? d3.format(',.0f')(Math.abs(v)) : d3.format('.3~s')(Math.abs(v)));
  const pct = (v) => (v < 0 ? MINUS : '') + d3.format('.1%')(Math.abs(v));

  let pricesCache = null;
  let baselineResultsCache = {};
  let currentPeriod = 'test';

  const DEFAULTS = {
    entry_z: 2.0,
    exit_z: 0.5,
    max_hold_days: 30,
    cost_per_side_bps: 10.0,
    cooldown_days: 0,
  };

  async function loadPrices() {
    if (pricesCache) return pricesCache;
    const res = await fetch('data/prices.json');
    if (!res.ok) throw new Error('Failed to load prices.json');
    pricesCache = await res.json();
    return pricesCache;
  }

  function getBaselineResult(period, data) {
    if (baselineResultsCache[period]) return baselineResultsCache[period];
    const periodPrices = data.periods[period];
    const res = PairsEngine.runSimulation(periodPrices, data.pairs, {
      entry_z: DEFAULTS.entry_z,
      exit_z: DEFAULTS.exit_z,
      max_hold_days: DEFAULTS.max_hold_days,
      cost_per_side_bps: DEFAULTS.cost_per_side_bps,
      borrow_bps_annual: 50.0,
      execution_lag: 1,
      initial_capital: CAPITAL,
      cooldown_days: DEFAULTS.cooldown_days,
    });
    baselineResultsCache[period] = res;
    return res;
  }

  function renderComparisonChart(container, periodPrices, userResult, baselineResult) {
    container.innerHTML = '';
    const w = Math.max(280, container.clientWidth || 600);
    const h = 260;
    const m = { top: 20, right: 90, bottom: 25, left: 55 };

    const svg = d3.select(container)
      .append('svg')
      .attr('width', '100%')
      .attr('viewBox', `0 0 ${w} ${h}`)
      .attr('role', 'img')
      .attr('aria-label', 'Net equity comparison between user settings and baseline');

    const dates = userResult.dates.map((d) => d3.utcParse('%Y-%m-%d')(d));
    const userNet = Array.from(userResult.equity).map((eq) => eq - CAPITAL);
    const baseNet = Array.from(baselineResult.equity).map((eq) => eq - CAPITAL);

    const x = d3.scaleUtc().domain([dates[0], dates[dates.length - 1]]).range([m.left, w - m.right]);
    const ext = d3.extent(userNet.concat(baseNet, [0]));
    const y = d3.scaleLinear().domain([ext[0], ext[1]]).range([h - m.bottom, m.top]).nice(5);

    // Gridlines
    svg.append('g')
      .selectAll('line.grid')
      .data(y.ticks(5))
      .join('line')
      .attr('class', 'rp-grid')
      .attr('x1', m.left)
      .attr('x2', w - m.right)
      .attr('y1', (d) => y(d))
      .attr('y2', (d) => y(d))
      .style('stroke', 'var(--cds-chart-grid)')
      .style('stroke-width', 1);

    // Zero reference line
    svg.append('line')
      .attr('x1', m.left)
      .attr('x2', w - m.right)
      .attr('y1', y(0))
      .attr('y2', y(0))
      .style('stroke', 'var(--cds-chart-reference)')
      .style('stroke-width', 1);

    // X Axis
    svg.append('g')
      .attr('class', 'rp-ax')
      .attr('transform', `translate(0, ${h - m.bottom})`)
      .call(d3.axisBottom(x).ticks(w < 520 ? 4 : 7).tickSizeOuter(0))
      .attr('font-size', null)
      .attr('font-family', null);

    // Y Axis labels
    svg.append('g')
      .selectAll('text.tick')
      .data(y.ticks(5))
      .join('text')
      .attr('class', 'rp-tick')
      .attr('x', m.left - 8)
      .attr('y', (d) => y(d))
      .attr('dy', '0.32em')
      .attr('text-anchor', 'end')
      .text(usdC);

    const lineGen = d3.line().x((d, i) => x(dates[i])).y((d) => y(d));

    // Baseline Line (Dashed)
    svg.append('path')
      .datum(baseNet)
      .attr('d', lineGen)
      .style('fill', 'none')
      .style('stroke', 'var(--color-fg-muted)')
      .style('stroke-width', 1.6)
      .style('stroke-dasharray', '4 4');

    // User Settings Line (Solid vibrant)
    svg.append('path')
      .datum(userNet)
      .attr('d', lineGen)
      .style('fill', 'none')
      .style('stroke', 'var(--s1)')
      .style('stroke-width', 2.5);

    // End Dots and Labels
    const lastIdx = dates.length - 1;
    const lastUser = userNet[lastIdx];
    const lastBase = baseNet[lastIdx];

    svg.append('circle')
      .attr('cx', x(dates[lastIdx]))
      .attr('cy', y(lastBase))
      .attr('r', 4)
      .style('fill', 'var(--color-fg-muted)')
      .style('stroke', 'var(--color-panel)')
      .style('stroke-width', 1.5);

    svg.append('circle')
      .attr('cx', x(dates[lastIdx]))
      .attr('cy', y(lastUser))
      .attr('r', 4.5)
      .style('fill', 'var(--s1)')
      .style('stroke', 'var(--color-panel)')
      .style('stroke-width', 2);

    svg.append('text')
      .attr('x', x(dates[lastIdx]) + 8)
      .attr('y', y(lastUser) + 4)
      .style('fill', 'var(--s1)')
      .style('font-size', '12px')
      .style('font-weight', '600')
      .text('Your run: ' + usd(lastUser, true));

    svg.append('text')
      .attr('x', x(dates[lastIdx]) + 8)
      .attr('y', y(lastBase) + 4)
      .style('fill', 'var(--color-fg-muted)')
      .style('font-size', '11.5px')
      .text('Baseline: ' + usd(lastBase, true));
  }

  function generateExplorationTakeaway(userOpts, userSum, baseSum) {
    const diffNet = userSum.netPnl - baseSum.netPnl;
    const diffTrades = userSum.nTrades - baseSum.nTrades;
    const diffCosts = userSum.totalCosts - baseSum.totalCosts;

    let narrative = '';

    if (userOpts.entry_z < DEFAULTS.entry_z) {
      narrative += `Lowering the entry threshold to <b>${userOpts.entry_z}</b> triggered <b>${diffTrades >= 0 ? '+' + diffTrades : diffTrades}</b> additional trades. `;
    } else if (userOpts.entry_z > DEFAULTS.entry_z) {
      narrative += `Raising the entry threshold to <b>${userOpts.entry_z}</b> filtered out noisy signals, resulting in <b>${Math.abs(diffTrades)} fewer trades</b>. `;
    } else {
      narrative += `With baseline entry threshold <b>${userOpts.entry_z}</b>, `;
    }

    if (userOpts.cost_per_side_bps > DEFAULTS.cost_per_side_bps) {
      narrative += `Higher friction of <b>${userOpts.cost_per_side_bps} bps</b> added <b>${usd(diffCosts)}</b> in trading drag. `;
    } else if (userOpts.cost_per_side_bps < DEFAULTS.cost_per_side_bps) {
      narrative += `Lower friction of <b>${userOpts.cost_per_side_bps} bps</b> saved <b>${usd(Math.abs(diffCosts))}</b> in transaction costs. `;
    }

    if (userOpts.cooldown_days > 0) {
      narrative += `A <b>${userOpts.cooldown_days}-day re-entry cooldown</b> prevented immediately reopening failed pairs after time stops or stop exits. `;
    }

    if (diffNet > 500) {
      narrative += `Overall, these settings improved Net P&L by <b>${usd(diffNet, true)}</b> compared to the research baseline.`;
    } else if (diffNet < -500) {
      narrative += `Overall, these settings reduced Net P&L by <b>${usd(Math.abs(diffNet))}</b> compared to the research baseline.`;
    } else {
      narrative += `Overall, Net P&L ended within <b>${usd(Math.abs(diffNet))}</b> of the research baseline.`;
    }

    return narrative;
  }

  async function runPlaygroundSimulation() {
    const data = await loadPrices();

    const entry_z = parseFloat(document.getElementById('sim-entry-z').value);
    const exit_z = parseFloat(document.getElementById('sim-exit-z').value);
    const max_hold = parseInt(document.getElementById('sim-max-hold').value, 10);
    const cost_bps = parseFloat(document.getElementById('sim-cost-bps').value);
    const cooldown_el = document.getElementById('sim-cooldown');
    const cooldown_days = cooldown_el ? parseInt(cooldown_el.value, 10) : 0;

    const userOpts = {
      entry_z: entry_z,
      exit_z: exit_z,
      max_hold_days: max_hold,
      cost_per_side_bps: cost_bps,
      borrow_bps_annual: 50.0,
      execution_lag: 1,
      initial_capital: CAPITAL,
      cooldown_days: cooldown_days,
    };

    const periodPrices = data.periods[currentPeriod];
    const userResult = PairsEngine.runSimulation(periodPrices, data.pairs, userOpts);
    const baseResult = getBaselineResult(currentPeriod, data);

    // Update KPI Tiles
    const userSum = userResult.summary;
    const baseSum = baseResult.summary;

    const setTile = (id, val, baseVal, isCurrency) => {
      const el = document.getElementById(id);
      const sub = document.getElementById(id + '-sub');
      if (!el) return;
      el.textContent = isCurrency ? usd(val, true) : String(val);
      el.className = 'stat-val ' + (Math.round(val) > 0 ? 'pos' : Math.round(val) < 0 ? 'neg' : '');

      if (sub) {
        const diff = val - baseVal;
        const diffStr = (diff > 0 ? '+' : diff < 0 ? MINUS : '') + (isCurrency ? '$' + d3.format(',.0f')(Math.abs(diff)) : Math.abs(diff));
        sub.textContent = `Baseline: ${isCurrency ? usd(baseVal, true) : baseVal} (${diffStr})`;
      }
    };

    setTile('sim-net', userSum.netPnl, baseSum.netPnl, true);
    setTile('sim-gross', userSum.grossPnl, baseSum.grossPnl, true);
    setTile('sim-costs', userSum.totalCosts, baseSum.totalCosts, true);
    setTile('sim-trades', userSum.nTrades, baseSum.nTrades, false);

    // Render chart
    const chartWrap = document.getElementById('playground-chart');
    if (chartWrap) {
      renderComparisonChart(chartWrap, periodPrices, userResult, baseResult);
    }

    // Dynamic takeaway
    const takeEl = document.getElementById('sim-takeaway-text');
    if (takeEl) {
      takeEl.innerHTML = generateExplorationTakeaway(userOpts, userSum, baseSum);
    }
  }

  function setupControls() {
    const bindSlider = (id, valId, format) => {
      const input = document.getElementById(id);
      const display = document.getElementById(valId);
      if (!input || !display) return;
      input.addEventListener('input', () => {
        display.textContent = format(input.value);
      });
    };

    bindSlider('sim-entry-z', 'sim-entry-z-val', (v) => parseFloat(v).toFixed(1));
    bindSlider('sim-exit-z', 'sim-exit-z-val', (v) => parseFloat(v).toFixed(1));
    bindSlider('sim-max-hold', 'sim-max-hold-val', (v) => v + ' days');
    bindSlider('sim-cost-bps', 'sim-cost-bps-val', (v) => parseFloat(v).toFixed(1) + ' bps');
    bindSlider('sim-cooldown', 'sim-cooldown-val', (v) => v + ' days');

    // Run button
    const runBtn = document.getElementById('sim-run-btn');
    if (runBtn) {
      runBtn.addEventListener('click', runPlaygroundSimulation);
    }

    // Reset button
    const resetBtn = document.getElementById('sim-reset-btn');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        document.getElementById('sim-entry-z').value = DEFAULTS.entry_z;
        document.getElementById('sim-entry-z-val').textContent = DEFAULTS.entry_z.toFixed(1);

        document.getElementById('sim-exit-z').value = DEFAULTS.exit_z;
        document.getElementById('sim-exit-z-val').textContent = DEFAULTS.exit_z.toFixed(1);

        document.getElementById('sim-max-hold').value = DEFAULTS.max_hold_days;
        document.getElementById('sim-max-hold-val').textContent = DEFAULTS.max_hold_days + ' days';

        document.getElementById('sim-cost-bps').value = DEFAULTS.cost_per_side_bps;
        document.getElementById('sim-cost-bps-val').textContent = DEFAULTS.cost_per_side_bps.toFixed(1) + ' bps';

        if (document.getElementById('sim-cooldown')) {
          document.getElementById('sim-cooldown').value = DEFAULTS.cooldown_days;
          document.getElementById('sim-cooldown-val').textContent = DEFAULTS.cooldown_days + ' days';
        }

        runPlaygroundSimulation();
      });
    }

    // Period switcher buttons in playground
    const periodBtns = document.querySelectorAll('.sim-period-btn');
    periodBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        periodBtns.forEach((b) => b.setAttribute('aria-pressed', 'false'));
        btn.setAttribute('aria-pressed', 'true');
        currentPeriod = btn.getAttribute('data-period');
        runPlaygroundSimulation();
      });
    });
  }

  // Lazy initialize playground when it scrolls into view or on first interaction
  let initialized = false;
  function checkPlaygroundVisibility() {
    if (initialized) return;
    const el = document.getElementById('playground');
    if (!el) return;
    const rect = el.getBoundingClientRect();
    if (rect.top < window.innerHeight + 400) {
      initialized = true;
      setupControls();
      runPlaygroundSimulation();
    }
  }

  window.addEventListener('scroll', checkPlaygroundVisibility, { passive: true });
  window.addEventListener('load', () => {
    setTimeout(checkPlaygroundVisibility, 800);
  });
})();
