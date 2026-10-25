/**
 * Embedded Replay Controller.
 * Powers the #rp container within the main landing page, using data/ JSON files.
 */

(function () {
  'use strict';

  const CAPITAL = 1000000, MINUS = '−';
  const root = document.getElementById('rp');
  if (!root) return;

  const q = (s, el) => (el || root).querySelector(s);
  const h = (tag, cls, txt) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt != null) e.textContent = txt;
    return e;
  };
  const usd = (v, signed) => {
    const r = Math.round(v);
    return (r < 0 ? MINUS : (signed && r > 0 ? '+' : '')) + '$' + d3.format(',.0f')(Math.abs(r));
  };
  const usdC = (v) => (v < 0 ? MINUS : '') + '$' + (Math.abs(v) < 1000 ? d3.format(',.0f')(Math.abs(v)) : d3.format('.3~s')(Math.abs(v)));
  const pct = (v, d) => (v < 0 ? MINUS : '') + d3.format('.' + (d == null ? 1 : d) + '%')(Math.abs(v));
  const parse = d3.utcParse('%Y-%m-%d');
  const fDate = d3.utcFormat('%a %-d %b %Y');
  const fShort = d3.utcFormat('%-d %b %Y');
  const REASON = { mean_revert: 'z back inside 0.5 band', max_hold: '30-day time stop', period_end: 'period end liquidation' };
  const NAMES = ['daily', 'trades', 'pairs', 'periods', 'cost_curve', 'entry_exit'];
  const tip = q('.rp-tip');

  const S = { period: 'test', i: 0, playing: false, speed: 50, acc: 0, last: 0, raf: 0 };
  let D = null, charts = null, pairUI = null;

  function tipShow(ev, title, rows) {
    tip.replaceChildren(h('div', 'rp-tip-t', title));
    rows.forEach((r) => {
      const d = h('div', 'rp-tip-r');
      if (r[2]) { const s = h('i', 'rp-sw'); s.style.background = r[2]; d.appendChild(s); }
      d.appendChild(h('span', '', r[0])); d.appendChild(h('b', '', r[1])); tip.appendChild(d);
    });
    tip.hidden = false;
    const rb = root.getBoundingClientRect();
    let l = ev.clientX - rb.left + 14, t = ev.clientY - rb.top + 14;
    const tw = tip.offsetWidth, th = tip.offsetHeight;
    if (l + tw > rb.width - 4) l = ev.clientX - rb.left - tw - 14;
    if (l < 4) l = 4;
    if (t + th > rb.height - 4) t = ev.clientY - rb.top - th - 14;
    if (t < 4) t = 4;
    tip.style.left = l + 'px'; tip.style.top = t + 'px';
  }
  const tipHide = () => { tip.hidden = true; };

  /* ---------- data ---------- */
  function prep() {
    const ds = {}; NAMES.forEach((n) => { ds[n] = dash.data(n).data; });
    if (D && D.src === ds.daily) return;
    const pairs = ds.pairs.map((p) => ({ pair: p.pair, a: p.leg_a, b: p.leg_b, sector: p.sector, beta: +p.beta, half: +p.half_life_days }));
    const per = {};
    ds.daily.forEach((r) => { (per[r.period] = per[r.period] || { rows: [] }).rows.push(r); });
    Object.keys(per).forEach((key) => {
      const P = per[key];
      P.rows.sort((a, b) => +a.step - +b.step);
      P.n = P.rows.length;
      P.dates = P.rows.map((r) => parse(r.date));
      P.idx = new Map(P.rows.map((r, i) => [r.date, i]));
      P.net = P.rows.map((r) => +r.equity - CAPITAL);
      P.gross = P.rows.map((r) => +r.gross_equity - CAPITAL);
      P.dd = P.rows.map((r) => +r.drawdown);
      P.open = P.rows.map((r) => +r.open_pairs);
      P.z = {}; P.cum = {};
      pairs.forEach((p) => { let c = 0; P.z[p.pair] = P.rows.map((r) => +r['z_' + p.pair]); P.cum[p.pair] = P.rows.map((r) => (c += +r['pnl_' + p.pair])); });
      P.trades = ds.trades.filter((t) => t.period === key).map((t) => ({
        id: t.trade_id, pair: t.pair, dir: +t.direction, s: P.idx.get(t.signal_date), e: P.idx.get(t.entry_date), xs: P.idx.get(t.exit_signal_date), x: P.idx.get(t.exit_date),
        entry: t.entry_date, exit: t.exit_date, days: +t.holding_days, gross: +t.gross_pnl, costs: +t.costs, net: +t.net_pnl, reason: t.exit_reason,
      })).filter((t) => t.s != null && t.e != null && t.x != null);
      P.state = {}; P.held = {};
      pairs.forEach((p) => {
        const st = new Int8Array(P.n), hd = new Int16Array(P.n);
        P.trades.filter((t) => t.pair === p.pair).forEach((t) => { for (let k = t.e; k < t.x; k++) { st[k] = t.dir; hd[k] = k - t.e + 1; } });
        P.state[p.pair] = st; P.held[p.pair] = hd;
      });
      const ev = [];
      P.trades.forEach((t) => {
        ev.push({ i: t.s, k: 0, kind: 'Signal', t }); ev.push({ i: t.e, k: 1, kind: 'Opened', t });
        if (t.xs != null) ev.push({ i: t.xs, k: 2, kind: 'Exit signal', t });
        ev.push({ i: t.x, k: 3, kind: 'Closed', t });
      });
      ev.sort((a, b) => a.i - b.i || a.k - b.k);
      P.events = ev;
      P.closedBy = new Int16Array(P.n);
      P.trades.forEach((t) => { for (let k = t.x; k < P.n; k++) P.closedBy[k]++; });
      let zm = 0; pairs.forEach((p) => P.z[p.pair].forEach((v) => { if (Math.abs(v) > zm) zm = Math.abs(v); }));
      P.zmax = Math.max(4, Math.ceil(zm / 2) * 2);
    });
    const periods = {}; ds.periods.forEach((r) => { periods[r.period] = r; });
    D = { src: ds.daily, per, pairs, periods, costCurve: ds.cost_curve, grid: ds.entry_exit };
  }
  const P0 = () => D.per[S.period];
  const rm = (w) => (w < 520 ? 62 : 112);

  /* ---------- equity and drawdown ---------- */
  function buildEquity(el, P, w) {
    const h0 = 250, m = { t: 12, r: rm(w), b: 24, l: 52 };
    const svg = d3.select(el).html('').append('svg').attr('width', '100%').attr('viewBox', '0 0 ' + w + ' ' + h0).attr('role', 'img')
      .attr('aria-label', 'Cumulative net and gross profit and loss for the selected period');
    const x = d3.scaleUtc([P.dates[0], P.dates[P.n - 1]], [m.l, w - m.r]);
    const ext = d3.extent(P.net.concat(P.gross, [0]));
    const y = d3.scaleLinear([ext[0], ext[1]], [h0 - m.b, m.t]).nice(5);
    const ticks = y.ticks(5);
    const g = svg.append('g');
    g.selectAll('line.rp-grid').data(ticks).join('line').attr('class', 'rp-grid').attr('x1', m.l).attr('x2', w - m.r).attr('y1', y).attr('y2', y);
    g.selectAll('text.rp-tick').data(ticks).join('text').attr('class', 'rp-tick').attr('x', m.l - 8).attr('y', y).attr('dy', '0.32em').attr('text-anchor', 'end').text(usdC);
    g.append('line').attr('class', 'rp-zero').attr('x1', m.l).attr('x2', w - m.r).attr('y1', y(0)).attr('y2', y(0));
    g.append('g').attr('class', 'rp-ax').attr('transform', 'translate(0,' + (h0 - m.b) + ')').call(d3.axisBottom(x).ticks(w < 520 ? 4 : 7).tickSizeOuter(0))
      .attr('font-size', null).attr('font-family', null);
    const C = dash.colors, line = d3.line().x((d, i) => x(P.dates[i])).y((d) => y(d));
    g.append('path').attr('class', 'rp-ghost').attr('d', line(P.net)).style('stroke', C[0]);
    g.append('path').attr('class', 'rp-ghost').attr('d', line(P.gross)).style('stroke', C[1]);
    const pN = g.append('path').attr('class', 'rp-line').style('stroke', C[0]);
    const pG = g.append('path').attr('class', 'rp-line').style('stroke', C[1]);
    const cur = g.append('line').attr('class', 'rp-cursor').attr('y1', m.t).attr('y2', h0 - m.b);
    const dN = g.append('circle').attr('r', 4).style('fill', C[0]).style('stroke', 'var(--color-panel)').style('stroke-width', 2);
    const dG = g.append('circle').attr('r', 4).style('fill', C[1]).style('stroke', 'var(--color-panel)').style('stroke-width', 2);
    const lN = g.append('text').attr('class', 'rp-endlab').attr('dy', '0.32em');
    const lG = g.append('text').attr('class', 'rp-endlab').attr('dy', '0.32em');
    const ov = svg.append('rect').attr('x', m.l).attr('y', m.t).attr('width', w - m.l - m.r).attr('height', h0 - m.t - m.b).style('fill', 'transparent');
    const wide = w >= 520;
    ov.on('pointermove', (ev) => {
      const j = Math.max(0, Math.min(S.i, d3.bisectCenter(P.dates, x.invert(d3.pointer(ev, svg.node())[0]))));
      tipShow(ev, fDate(P.dates[j]), [['Net', usd(P.net[j], true), C[0]], ['Gross', usd(P.gross[j], true), C[1]], ['Costs so far', usd(P.gross[j] - P.net[j])], ['Drawdown', pct(P.dd[j])], ['Open pairs', String(P.open[j])]]);
    }).on('pointerleave', tipHide);
    return {
      x, m, update(i) {
        pN.attr('d', line(P.net.slice(0, i + 1))); pG.attr('d', line(P.gross.slice(0, i + 1)));
        const cx = x(P.dates[i]), yN = y(P.net[i]), yG = y(P.gross[i]);
        cur.attr('x1', cx).attr('x2', cx); dN.attr('cx', cx).attr('cy', yN); dG.attr('cx', cx).attr('cy', yG);
        if (wide) {
          lN.attr('x', w - m.r + 8).attr('y', yN).text('Net ' + usd(P.net[i], true));
          lG.attr('x', w - m.r + 8).attr('y', yG).text('Gross ' + usd(P.gross[i], true));
        } else { lN.text(''); lG.text(''); }
      },
    };
  }

  function buildDD(el, P, w) {
    const h0 = 96, m = { t: 8, r: rm(w), b: 20, l: 52 };
    const svg = d3.select(el).html('').append('svg').attr('width', '100%').attr('viewBox', '0 0 ' + w + ' ' + h0).attr('role', 'img')
      .attr('aria-label', 'Underwater drawdown for the selected period');
    const x = d3.scaleUtc([P.dates[0], P.dates[P.n - 1]], [m.l, w - m.r]);
    const minDD = Math.min(-0.01, d3.min(P.dd));
    const y = d3.scaleLinear([minDD, 0], [h0 - m.b, m.t]);
    const g = svg.append('g');
    g.selectAll('line.rp-grid').data(y.ticks(3)).join('line').attr('class', 'rp-grid').attr('x1', m.l).attr('x2', w - m.r).attr('y1', y).attr('y2', y);
    g.selectAll('text.rp-tick').data(y.ticks(3)).join('text').attr('class', 'rp-tick').attr('x', m.l - 8).attr('y', y).attr('dy', '0.32em').attr('text-anchor', 'end').text((v) => pct(v, 0));
    g.append('line').attr('class', 'rp-zero').attr('x1', m.l).attr('x2', w - m.r).attr('y1', y(0)).attr('y2', y(0));
    const area = d3.area().x((d, i) => x(P.dates[i])).y0(y(0)).y1((d) => y(d));
    const path = g.append('path').style('fill', 'var(--cds-chart-status-critical)').style('opacity', 0.28);
    const cur = g.append('line').attr('class', 'rp-cursor').attr('y1', m.t).attr('y2', h0 - m.b);
    const lab = g.append('text').attr('class', 'rp-endlab').attr('dy', '0.32em');
    const wide = w >= 520;
    return {
      update(i) {
        path.attr('d', area(P.dd.slice(0, i + 1)));
        const cx = x(P.dates[i]); cur.attr('x1', cx).attr('x2', cx);
        if (wide) lab.attr('x', w - m.r + 8).attr('y', y(P.dd[i])).text('DD ' + pct(P.dd[i], 1)); else lab.text('');
      },
    };
  }

  /* ---------- pair z-charts ---------- */
  function ensureCards() {
    if (pairUI) return;
    const box = q('#rp-pairs'); box.replaceChildren();
    pairUI = {};
    D.pairs.forEach((p, idx) => {
      const card = h('article', 'rp-card'); card.setAttribute('aria-labelledby', 'rp-p-' + p.pair);
      const top = h('div', 'rp-pair-top');
      const h3 = h('h3', '', p.a + ' / ' + p.b); h3.id = 'rp-p-' + p.pair;
      const chip = h('span', 'rp-chip', p.sector);
      const st = h('span', 'rp-state', 'Flat');
      top.append(h3, chip, st);
      const sub = h('div', 'rp-note rp-pair-sub', '—');
      const ch = h('div', 'rp-chart rp-zchart dash-skeleton'); ch.setAttribute('data-source', 'daily pairs');
      card.append(top, sub, ch); box.appendChild(card);
      pairUI[p.pair] = { card, st, sub, ch, p, idx };
    });
  }

  function buildZ(ui, P, w) {
    const p = ui.p, z = P.z[p.pair], h0 = 132, m = { t: 10, r: 16, b: 20, l: 36 };
    const svg = d3.select(ui.ch).html('').append('svg').attr('width', '100%').attr('viewBox', '0 0 ' + w + ' ' + h0).attr('role', 'img')
      .attr('aria-label', p.a + ' and ' + p.b + ' spread z-score trajectory');
    const x = d3.scaleUtc([P.dates[0], P.dates[P.n - 1]], [m.l, w - m.r]);
    const y = d3.scaleLinear([-P.zmax, P.zmax], [h0 - m.b, m.t]);
    const g = svg.append('g');
    g.append('line').attr('class', 'rp-zero').attr('x1', m.l).attr('x2', w - m.r).attr('y1', y(0)).attr('y2', y(0));
    [-2, 2].forEach((v) => g.append('line').attr('class', 'rp-entry').attr('x1', m.l).attr('x2', w - m.r).attr('y1', y(v)).attr('y2', y(v)));
    [-0.5, 0.5].forEach((v) => g.append('line').attr('class', 'rp-exit').attr('x1', m.l).attr('x2', w - m.r).attr('y1', y(v)).attr('y2', y(v)));
    g.selectAll('text.rp-tick').data([-P.zmax, -2, 0, 2, P.zmax]).join('text').attr('class', 'rp-tick').attr('x', m.l - 6).attr('y', y).attr('dy', '0.32em').attr('text-anchor', 'end')
      .text((v) => (v < 0 ? MINUS : '') + Math.abs(v));
    const tr = P.trades.filter((t) => t.pair === p.pair);
    const shades = g.selectAll('rect.rp-shade').data(tr).join('rect').attr('class', 'rp-shade')
      .attr('y', m.t).attr('height', h0 - m.t - m.b).style('fill', (t) => (t.dir > 0 ? dash.colors[2] : dash.colors[3]));
    const sig = g.selectAll('path.rp-sig').data(tr).join('path').attr('class', 'rp-mark')
      .attr('d', (t) => (t.dir > 0 ? 'M -4 3 L 4 3 L 0 -4 Z' : 'M -4 -3 L 4 -3 L 0 4 Z'))
      .attr('transform', (t) => 'translate(' + x(P.dates[t.s]) + ',' + y(z[t.s]) + ')')
      .style('stroke', (t) => (t.dir > 0 ? dash.colors[2] : dash.colors[3]));
    const xs = g.selectAll('circle.rp-xs').data(tr.filter((t) => t.xs != null)).join('circle').attr('class', 'rp-mark')
      .attr('r', 3.5).attr('cx', (t) => x(P.dates[t.xs])).attr('cy', (t) => y(z[t.xs]))
      .style('stroke', 'var(--color-fg-muted)');
    const line = d3.line().x((d, i) => x(P.dates[i])).y((d) => y(d));
    g.append('path').attr('class', 'rp-zghost').attr('d', line(z));
    const path = g.append('path').attr('class', 'rp-zline');
    const dot = g.append('circle').attr('r', 3.5).style('fill', 'var(--color-fg)').style('stroke', 'var(--color-panel)').style('stroke-width', 1.5);
    svg.append('rect').attr('x', m.l).attr('y', m.t).attr('width', w - m.l - m.r).attr('height', h0 - m.t - m.b).style('fill', 'transparent')
      .on('pointermove', (ev) => {
        const j = Math.max(0, Math.min(S.i, d3.bisectCenter(P.dates, x.invert(d3.pointer(ev, svg.node())[0]))));
        const s = P.state[p.pair][j];
        tipShow(ev, fDate(P.dates[j]), [['Z-score', (z[j] < 0 ? MINUS : '') + d3.format('.2f')(Math.abs(z[j]))], ['Position', s > 0 ? 'Long spread' : s < 0 ? 'Short spread' : 'Flat'], ['Pair profit so far', usd(P.cum[p.pair][j], true)]]);
      }).on('pointerleave', tipHide);
    return {
      update(i) {
        path.attr('d', line(z.slice(0, i + 1)));
        shades.attr('x', (t) => x(P.dates[t.e])).attr('width', (t) => Math.max(0, i < t.e ? 0 : x(P.dates[Math.min(i, t.x)]) - x(P.dates[t.e])));
        sig.style('display', (t) => (t.s <= i ? null : 'none')); xs.style('display', (t) => (t.xs <= i ? null : 'none'));
        dot.attr('cx', x(P.dates[i])).attr('cy', y(z[i]));
      },
    };
  }

  /* ---------- sensitivity ---------- */
  function drawHeat() {
    const el = q('#rp-heat'); el.replaceChildren();
    const rows = D.grid.filter((r) => r.period === S.period);
    const entries = [1.5, 2, 2.5], exits = [0, 0.5, 1];
    const mx = d3.max(rows, (r) => Math.abs(+r.net_pnl)) || 1;
    el.appendChild(h('div', 'hh', ''));
    exits.forEach((e) => el.appendChild(h('div', 'hh', 'Exit inside ' + e)));
    entries.forEach((en) => {
      el.appendChild(h('div', 'hh', 'Enter at ' + en));
      exits.forEach((ex) => {
        const r = rows.find((v) => +v.entry_z === en && +v.exit_z === ex), c = h('div', 'rp-cell');
        if (!r) { el.appendChild(c); return; }
        const v = +r.net_pnl, k = Math.round(10 + 32 * Math.abs(v) / mx);
        c.style.background = 'color-mix(in srgb, ' + (v >= 0 ? 'var(--color-ok)' : 'var(--cds-chart-status-critical)') + ' ' + k + '%, var(--color-panel))';
        c.appendChild(h('b', '', usd(v, true))); c.appendChild(h('small', '', r.trades + ' trades' + (en === 2 && ex === 0.5 ? ' · baseline' : '')));
        if (en === 2 && ex === 0.5) c.classList.add('base');
        el.appendChild(c);
      });
    });
    const pos = rows.filter((r) => +r.net_pnl > 0).length;
    q('#rp-heat-note').textContent = D.periods[S.period].name + ': ' + pos + ' of ' + rows.length + ' threshold pairs end with a profit after costs. Sensitivity, not selection.';
  }

  function buildCosts() {
    const el = q('#rp-costs'); el.replaceChildren();
    const w = Math.max(200, Math.min(300, el.clientWidth || 260));
    ['train', 'validation', 'test'].forEach((key) => {
      const pts = D.costCurve.filter((r) => r.period === key).map((r) => ({ c: +r.cost_per_side_bps, v: +r.net_pnl })).sort((a, b) => a.c - b.c);
      const be = +D.periods[key].breakeven_bps, fig = h('figure'), box = h('div', 'rp-chart');
      const h0 = 120, m = { t: 12, r: 12, b: 20, l: 46 };
      const svg = d3.select(box).append('svg').attr('width', '100%').attr('viewBox', '0 0 ' + w + ' ' + h0).attr('role', 'img').attr('aria-label', D.periods[key].name + ' net profit against trading cost');
      const x = d3.scaleLinear([0, 20], [m.l, w - m.r]);
      const ext = d3.extent(pts.map((p) => p.v).concat([0])), y = d3.scaleLinear(ext, [h0 - m.b, m.t]).nice(3);
      const g = svg.append('g'), tk = y.ticks(3);
      g.selectAll('line.rp-grid').data(tk).join('line').attr('class', 'rp-grid').attr('x1', m.l).attr('x2', w - m.r).attr('y1', y).attr('y2', y);
      g.selectAll('text.rp-tick').data(tk).join('text').attr('class', 'rp-tick').attr('x', m.l - 6).attr('y', y).attr('dy', '0.32em').attr('text-anchor', 'end').text(usdC);
      g.append('line').attr('class', 'rp-zero').attr('x1', m.l).attr('x2', w - m.r).attr('y1', y(0)).attr('y2', y(0));
      g.append('line').attr('class', 'rp-entry').attr('x1', x(10)).attr('x2', x(10)).attr('y1', m.t).attr('y2', h0 - m.b);
      g.append('text').attr('class', 'rp-lab').attr('x', x(10) + 4).attr('y', m.t + 8).text('assumed 10');
      g.append('g').attr('class', 'rp-ax').attr('transform', 'translate(0,' + (h0 - m.b) + ')').call(d3.axisBottom(x).tickValues([0, 5, 10, 20]).tickSizeOuter(0)).attr('font-size', null).attr('font-family', null);
      g.append('path').attr('class', 'rp-line').style('stroke', dash.colors[0]).attr('d', d3.line().x((p) => x(p.c)).y((p) => y(p.v))(pts));
      g.selectAll('circle.pt').data(pts).join('circle').attr('r', 3).attr('cx', (p) => x(p.c)).attr('cy', (p) => y(p.v)).style('fill', dash.colors[0]);
      if (be <= 20) g.append('circle').attr('r', 5).attr('cx', x(be)).attr('cy', y(0)).style('fill', 'var(--color-bg)').style('stroke', 'var(--color-fg)').style('stroke-width', 2);
      svg.append('rect').attr('x', m.l).attr('y', m.t).attr('width', w - m.l - m.r).attr('height', h0 - m.t - m.b).style('fill', 'transparent')
        .on('pointermove', (ev) => { const p = pts[d3.bisector((v) => v.c).center(pts, x.invert(d3.pointer(ev, svg.node())[0]))]; tipShow(ev, p.c + ' bps per side', [['Net profit', usd(p.v, true)]]); }).on('pointerleave', tipHide);
      const cap = h('figcaption', '', D.periods[key].name + ': breaks even at ' + d3.format('.1f')(be) + ' bps' + (be > 20 ? ' (off the chart)' : '') + '.');
      fig.append(box, cap); el.appendChild(fig);
    });
  }

  /* ---------- per frame ---------- */
  function drawHead() {
    const pr = D.periods[S.period], P = P0();
    q('#rp-take').textContent = pr.name + ' (' + pr.span + '): ' + usd(+pr.net_pnl, true) + ' after costs. Before costs the strategy made ' + usd(+pr.gross_pnl, true) +
      '; costs were ' + usd(+pr.costs) + ', which is ' + d3.format('.0%')(+pr.cost_drag) + ' of that gross figure.';
    q('#rp-results').replaceChildren(...[['Sharpe ratio', d3.format('.2f')(+pr.sharpe).replace('-', MINUS)], ['Annualised return', pct(+pr.cagr, 2)], ['Worst drawdown', pct(-Math.abs(+pr.max_drawdown), 1)],
      ['Win rate', pct(+pr.win_rate, 0)], ['Trading days', String(pr.days)]].map((r) => { const s = h('span', '', r[0] + ' '); s.appendChild(h('b', '', r[1])); return s; }));
    const sc = q('#rp-scrub'); sc.max = P.n - 1;
    q('#rp-eq-legend').replaceChildren(...[['Net, after costs', dash.colors[0]], ['Gross, before costs', dash.colors[1]]].map((r) => { const s = h('span'); const sw = h('i', 'rp-sw'); sw.style.background = r[1]; s.append(sw, document.createTextNode(r[0])); return s; }));
    const zl = q('#rp-z-legend'); zl.replaceChildren();
    [['Long spread held', dash.colors[2]], ['Short spread held', dash.colors[3]]].forEach((r) => { const s = h('span'), sw = h('i', 'rp-sw'); sw.style.background = r[1]; s.append(sw, document.createTextNode(r[0])); zl.appendChild(s); });
    ['▲ entry signal (flipped for short)', '○ exit signal', 'Dashed lines: enter at ±2', 'Dotted lines: exit inside ±0.5'].forEach((t) => zl.appendChild(h('span', '', t)));
  }

  function tone(el, v) { el.className = 'v ' + (Math.round(v) > 0 ? 'pos' : Math.round(v) < 0 ? 'neg' : ''); }

  function draw(i) {
    const P = P0(), pr = D.periods[S.period];
    q('#rp-scrub').value = i;
    q('#rp-date').textContent = fDate(P.dates[i]) + ' · day ' + (i + 1) + ' of ' + P.n;
    const tn = q('#t-net'); tn.textContent = usd(P.net[i], true); tone(tn, P.net[i]); q('#t-net-s').textContent = 'Period end ' + usd(+pr.net_pnl, true);
    const tg = q('#t-gross'); tg.textContent = usd(P.gross[i], true); tone(tg, P.gross[i]); q('#t-gross-s').textContent = 'Period end ' + usd(+pr.gross_pnl, true);
    q('#t-cost').textContent = usd(P.gross[i] - P.net[i]); q('#t-cost-s').textContent = 'Period end ' + usd(+pr.costs);
    q('#t-trades').textContent = P.closedBy[i] + ' of ' + pr.trades; q('#t-trades-s').textContent = P.open[i] + (P.open[i] === 1 ? ' pair open now' : ' pairs open now');
    charts.forEach((c) => c.update(i));
    D.pairs.forEach((p) => {
      const ui = pairUI[p.pair], s = P.state[p.pair][i], z = P.z[p.pair][i], c = dash.colors;
      ui.st.textContent = s > 0 ? 'Long spread' : s < 0 ? 'Short spread' : 'Flat';
      ui.st.style.borderColor = s > 0 ? c[2] : s < 0 ? c[3] : '';
      ui.sub.textContent = 'Z-score ' + (z < 0 ? MINUS : '') + d3.format('.2f')(Math.abs(z)) + (s ? ' · day ' + P.held[p.pair][i] + ' of the position' : '') + ' · profit so far ' + usd(P.cum[p.pair][i], true) +
        ' · hedge ratio ' + d3.format('.2f')(p.beta) + ' · half-life ' + d3.format('.0f')(p.half) + ' days';
    });
    const pn = (id) => D.pairs.find((p) => p.pair === id);
    const ev = []; for (let k = P.events.length - 1; k >= 0 && ev.length < 8; k--) if (P.events[k].i <= i) ev.push(P.events[k]);
    const feed = q('#rp-feed'); feed.replaceChildren();
    ev.forEach((e) => {
      const t = e.t, p = pn(t.pair), side = t.dir > 0 ? 'long' : 'short', li = h('li');
      let txt = p.a + ' / ' + p.b + ': ';
      if (e.kind === 'Signal') {
        txt += 'the price gap is unusually wide (z = ' + (P.z[t.pair][t.s] < 0 ? MINUS : '') + d3.format('.2f')(Math.abs(P.z[t.pair][t.s])) +
          '). Signal to bet on it closing: ' + (side === 'long' ? 'buy ' + p.a + ', sell ' + p.b : 'sell ' + p.a + ', buy ' + p.b) + " at tomorrow's close.";
      } else if (e.kind === 'Opened') {
        txt += 'order filled at market close: ' + (side === 'long' ? 'bought ' + p.a + ', sold ' + p.b : 'sold ' + p.a + ', bought ' + p.b) + '.';
      } else if (e.kind === 'Exit signal') {
        txt += 'gap reverted inside band (' + (REASON[t.reason] || t.reason) + '). Scheduled to liquidate at tomorrow\'s close.';
      } else {
        txt += 'trade closed, ' + usd(t.net, true) + ' net P&L after friction (' + (REASON[t.reason] || t.reason) + ').';
      }
      li.append(h('span', 'd', fShort(P.dates[e.i])), h('span', 't', e.kind), h('span', '', txt)); feed.appendChild(li);
    });
    q('#rp-feed-empty').hidden = ev.length > 0;
    const closed = P.trades.filter((t) => t.x <= i).sort((a, b) => b.x - a.x || b.e - a.e);
    q('#rp-tr-empty').hidden = closed.length > 0;
    const tb = d3.select(q('#rp-trades tbody'));
    tb.selectAll('tr').data(closed, (t) => t.id).join('tr').attr('data-key', (t) => t.id).each(function (t) {
      const p = pn(t.pair), cells = [[p.a + ' / ' + p.b, ''], [t.dir > 0 ? 'Long spread' : 'Short spread', ''], [t.entry, ''], [t.exit, ''], [String(t.days), 'n'], [usd(t.gross, true), 'n'], [usd(t.costs), 'n'], [usd(t.net, true), 'n ' + (t.net >= 0 ? 'pos' : 'neg')], [REASON[t.reason] || t.reason, '']];
      d3.select(this).selectAll('td').data(cells).join('td').attr('class', (c) => c[1]).text((c) => c[0]);
    }).order();
  }

  function layout() {
    const P = P0(); ensureCards();
    const eq = q('#rp-eq'), w = Math.max(280, Math.floor(eq.clientWidth || 640));
    charts = [buildEquity(eq, P, w), buildDD(q('#rp-dd'), P, w)];
    [q('#rp-eq'), q('#rp-dd')].forEach((e) => e.classList.remove('dash-skeleton'));
    D.pairs.forEach((p) => { const ui = pairUI[p.pair], zw = Math.max(240, Math.floor(ui.ch.clientWidth || 340)); charts.push(buildZ(ui, P, zw)); ui.ch.classList.remove('dash-skeleton'); });
    buildCosts(); drawHeat(); drawHead();
  }

  /* ---------- playback and controls ---------- */
  function setPlaying(on) {
    S.playing = on; q('#rp-play').textContent = on ? 'Pause' : 'Play';
    cancelAnimationFrame(S.raf);
    if (on) { S.last = performance.now(); S.acc = 0; S.raf = requestAnimationFrame(tick); }
  }
  function tick(ts) {
    if (!S.playing || !D) return;
    S.acc += Math.min(100, ts - S.last) * S.speed / 1000; S.last = ts;
    const adv = Math.floor(S.acc);
    if (adv > 0) { S.acc -= adv; S.i = Math.min(P0().n - 1, S.i + adv); draw(S.i); tipHide(); if (S.i >= P0().n - 1) { setPlaying(false); return; } }
    S.raf = requestAnimationFrame(tick);
  }
  function setPeriod(key) {
    setPlaying(false); S.period = key; S.i = P0().n - 1;
    root.querySelectorAll('.rp-tabs button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.period === key)));
    layout(); draw(S.i);
  }
  root.querySelectorAll('.rp-tabs button').forEach((b) => b.addEventListener('click', () => { if (D) setPeriod(b.dataset.period); }));
  q('#rp-play').addEventListener('click', () => { if (!D) return; if (S.playing) { setPlaying(false); return; } if (S.i >= P0().n - 1) { S.i = 0; draw(0); } setPlaying(true); });
  q('#rp-restart').addEventListener('click', () => { if (!D) return; S.i = 0; draw(0); setPlaying(true); });
  q('#rp-speed').addEventListener('change', (e) => { S.speed = +e.target.value; });
  q('#rp-scrub').addEventListener('input', (e) => { if (!D) return; setPlaying(false); S.i = Math.max(0, Math.min(P0().n - 1, +e.target.value)); draw(S.i); });

  dash.onData(() => {
    const st = NAMES.map((n) => dash.data(n).status);
    const bad = st.some((s) => s === 'error' || s === 'connect' || s === 'declined' || s === 'missing');
    root.classList.toggle('rp-failed', bad);
    if (bad) { setPlaying(false); return; }
    if (st.some((s) => s !== 'ok')) return;
    const first = !D; prep();
    if (first) S.i = P0().n - 1;
    layout(); draw(Math.min(S.i, P0().n - 1));
  });
})();
