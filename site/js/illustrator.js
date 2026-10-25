/**
 * Interactive Pairs Trading in 60 Seconds Illustration.
 * Animates two diverging and converging stock price lines with a synchronized gap meter.
 */

(function () {
  'use strict';

  function initIllustrator() {
    const wrap = document.getElementById('illustrator-canvas');
    if (!wrap) return;

    const meterFill = document.getElementById('meter-fill');
    const meterVal = document.getElementById('meter-val');
    const meterStatus = document.getElementById('meter-status');
    const playBtn = document.getElementById('illustrator-play-btn');

    // Generate realistic synthetic normalized path for illustration
    const N = 120;
    const data = [];
    for (let i = 0; i < N; i++) {
      const t = i / (N - 1); // 0 to 1
      // Baseline common trend
      const trend = 100 + 15 * Math.sin(t * Math.PI * 1.5) + t * 5;
      let spreadDev = 0;
      let phase = 'Equilibrium';
      let zScore = 0;

      if (t < 0.25) {
        // Tight equilibrium
        spreadDev = Math.sin(t * 40) * 0.8;
        phase = 'Stocks moving in lockstep equilibrium';
        zScore = spreadDev / 1.5;
      } else if (t < 0.6) {
        // Divergence shock
        const progress = (t - 0.25) / 0.35;
        const ramp = Math.sin(progress * Math.PI * 0.5);
        spreadDev = ramp * 8.5 + Math.sin(t * 30) * 0.5;
        if (progress > 0.65) {
          phase = 'Unusually wide gap (z ≥ 2.0)! Signal: Buy BAC, Sell PNC';
        } else {
          phase = 'Temporary shock: prices drift apart';
        }
        zScore = (spreadDev / 8.5) * 2.4;
      } else if (t < 0.85) {
        // Snapping back (mean reversion)
        const progress = (t - 0.6) / 0.25;
        const decay = Math.cos(progress * Math.PI * 0.5);
        spreadDev = decay * 8.5 + Math.sin(t * 30) * 0.4;
        phase = 'Mean reversion: prices snap back toward equilibrium';
        zScore = (spreadDev / 8.5) * 2.4;
      } else {
        // Back to normal
        spreadDev = Math.sin(t * 35) * 0.6;
        phase = 'Gap closed inside normal band (z ≤ 0.5). Profit locked in!';
        zScore = spreadDev / 1.5;
      }

      const pA = trend - spreadDev * 0.5;
      const pB = trend + spreadDev * 0.5;
      data.push({
        i,
        t,
        pA,
        pB,
        spread: pB - pA,
        zScore: zScore,
        phase: phase,
      });
    }

    let isPlaying = true;
    let currIdx = 0;
    let animId = null;
    let lastTime = 0;

    const w = wrap.clientWidth || 600;
    const h = 200;
    const margin = { top: 20, right: 90, bottom: 25, left: 45 };

    wrap.innerHTML = '';
    const svg = d3.select(wrap)
      .append('svg')
      .attr('width', '100%')
      .attr('viewBox', `0 0 ${w} ${h}`)
      .attr('role', 'img')
      .attr('aria-label', 'Two cointegrated stock price lines diverging and reverting');

    const x = d3.scaleLinear().domain([0, N - 1]).range([margin.left, w - margin.right]);
    const y = d3.scaleLinear().domain([88, 128]).range([h - margin.bottom, margin.top]);

    // Gridlines
    svg.append('g')
      .selectAll('line.grid')
      .data(y.ticks(4))
      .join('line')
      .attr('class', 'rp-grid')
      .attr('x1', margin.left)
      .attr('x2', w - margin.right)
      .attr('y1', (d) => y(d))
      .attr('y2', (d) => y(d))
      .style('stroke', 'var(--cds-chart-grid)')
      .style('stroke-width', 1);

    // Ghost trajectories
    const lineA = d3.line().x((d) => x(d.i)).y((d) => y(d.pA)).curve(d3.curveMonotoneX);
    const lineB = d3.line().x((d) => x(d.i)).y((d) => y(d.pB)).curve(d3.curveMonotoneX);

    svg.append('path')
      .datum(data)
      .attr('d', lineA)
      .style('fill', 'none')
      .style('stroke', 'var(--s1)')
      .style('stroke-width', 1.5)
      .style('opacity', 0.2);

    svg.append('path')
      .datum(data)
      .attr('d', lineB)
      .style('fill', 'none')
      .style('stroke', 'var(--s2)')
      .style('stroke-width', 1.5)
      .style('opacity', 0.2);

    // Dynamic active paths
    const activePathA = svg.append('path')
      .style('fill', 'none')
      .style('stroke', 'var(--s1)')
      .style('stroke-width', 2.5);

    const activePathB = svg.append('path')
      .style('fill', 'none')
      .style('stroke', 'var(--s2)')
      .style('stroke-width', 2.5);

    // Moving dots and labels
    const dotA = svg.append('circle').attr('r', 4.5).style('fill', 'var(--s1)').style('stroke', 'var(--color-panel)').style('stroke-width', 2);
    const dotB = svg.append('circle').attr('r', 4.5).style('fill', 'var(--s2)').style('stroke', 'var(--color-panel)').style('stroke-width', 2);

    const labelA = svg.append('text').attr('font-size', '12px').attr('font-weight', '600').style('fill', 'var(--s1)');
    const labelB = svg.append('text').attr('font-size', '12px').attr('font-weight', '600').style('fill', 'var(--s2)');

    // Vertical cursor line
    const cursorLine = svg.append('line')
      .attr('y1', margin.top)
      .attr('y2', h - margin.bottom)
      .style('stroke', 'var(--cds-chart-axis)')
      .style('stroke-dasharray', '2 2');

    // Divergence gap fill between lines
    const areaGen = d3.area()
      .x((d) => x(d.i))
      .y0((d) => y(d.pA))
      .y1((d) => y(d.pB))
      .curve(d3.curveMonotoneX);

    const areaPath = svg.append('path')
      .style('fill', 'var(--s4)')
      .style('opacity', 0.18);

    function updateFrame(idx) {
      const slice = data.slice(0, idx + 1);
      const curr = data[idx];

      activePathA.attr('d', lineA(slice));
      activePathB.attr('d', lineB(slice));
      areaPath.attr('d', areaGen(slice));

      const cx = x(curr.i);
      const cyA = y(curr.pA);
      const cyB = y(curr.pB);

      dotA.attr('cx', cx).attr('cy', cyA);
      dotB.attr('cx', cx).attr('cy', cyB);

      labelA.attr('x', cx + 8).attr('y', cyA + 4).text('Stock A (BAC)');
      labelB.attr('x', cx + 8).attr('y', cyB + 4).text('Stock B (PNC)');

      cursorLine.attr('x1', cx).attr('x2', cx);

      // Update Gap Meter UI
      const absZ = Math.min(3.0, Math.abs(curr.zScore));
      const pctWidth = Math.min(100, (absZ / 3.0) * 100);

      if (meterFill) {
        meterFill.style.width = pctWidth + '%';
        if (absZ >= 2.0) {
          meterFill.style.background = 'var(--color-bad)';
        } else if (absZ >= 1.0) {
          meterFill.style.background = 'var(--color-warn)';
        } else {
          meterFill.style.background = 'var(--color-ok)';
        }
      }

      if (meterVal) {
        meterVal.textContent = (curr.zScore < 0 ? '−' : '+') + Math.abs(curr.zScore).toFixed(2);
      }

      if (meterStatus) {
        meterStatus.textContent = curr.phase;
        if (absZ >= 2.0) {
          meterStatus.style.color = 'var(--color-bad)';
          meterStatus.style.fontWeight = '600';
        } else if (curr.phase.includes('closed') || curr.phase.includes('Equilibrium')) {
          meterStatus.style.color = 'var(--color-ok)';
          meterStatus.style.fontWeight = '500';
        } else {
          meterStatus.style.color = 'var(--color-fg-muted)';
          meterStatus.style.fontWeight = '400';
        }
      }
    }

    function stepAnimation(timestamp) {
      if (!isPlaying) return;
      if (timestamp - lastTime > 65) {
        currIdx = (currIdx + 1) % N;
        updateFrame(currIdx);
        lastTime = timestamp;
      }
      animId = requestAnimationFrame(stepAnimation);
    }

    if (playBtn) {
      playBtn.addEventListener('click', () => {
        isPlaying = !isPlaying;
        playBtn.textContent = isPlaying ? 'Pause Animation' : 'Play Animation';
        if (isPlaying) {
          animId = requestAnimationFrame(stepAnimation);
        } else if (animId) {
          cancelAnimationFrame(animId);
        }
      });
    }

    // Initial frame
    updateFrame(0);
    animId = requestAnimationFrame(stepAnimation);

    // Responsive redraw
    window.addEventListener('resize', () => {
      const newW = wrap.clientWidth;
      if (newW && Math.abs(newW - w) > 20) {
        if (animId) cancelAnimationFrame(animId);
        initIllustrator();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initIllustrator);
  } else {
    initIllustrator();
  }
})();
