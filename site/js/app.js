/**
 * Main application script.
 * Coordinates sticky navigation, hero headline loading from periods.json,
 * and global glossary tooltips.
 */

(function () {
  'use strict';

  const MINUS = '−';

  const usd = (v, signed) => {
    const r = Math.round(v);
    return (r < 0 ? MINUS : (signed && r > 0 ? '+' : '')) + '$' + d3.format(',.0f')(Math.abs(r));
  };

  const GLOSSARY = {
    spread: 'The price gap between two cointegrated stocks, calculated as ln(Price A) − α − β × ln(Price B).',
    'z-score': 'A normalized measure of how rare today\'s spread is, expressed in standard deviations from the historical training mean.',
    cointegration: 'A statistical property where two non-stationary price series share a stationary linear combination that does not drift apart indefinitely.',
    'hedge ratio': 'The parameter beta (β) that determines the number of shares of Stock B to short per share of Stock A to eliminate directional market risk.',
    'half-life': 'The estimated number of trading days for a spread divergence to revert halfway back to its mean.',
    'basis point': 'One-hundredth of a percentage point (0.01% or 0.0001). 10 bps equals 0.10%.',
    'long spread': 'A trade that bets the spread will widen upward: buying Stock A and selling Stock B.',
    'short spread': 'A trade that bets the spread will revert downward: selling Stock A and buying Stock B.',
    'sharpe ratio': 'Excess annualized return per unit of volatility, assuming zero risk-free rate.',
    drawdown: 'The percentage decline in portfolio equity from its historical peak high-water mark.',
    slippage: 'The difference between the expected execution price and the actual fill price (modeled as 5 bps per leg).',
    'borrow cost': 'Annual fee paid to prime brokers to borrow shares for shorting (modeled as 50 bps/year).',
    overfitting: 'Designing trading rules that fit historical random noise rather than genuine recurring economic signals.',
    'out-of-sample': 'A strictly locked time period (2023–2024) untouched during strategy design and parameter selection.',
  };

  // Populate Hero honest test headline dynamically from periods.json
  async function loadHeroHeadline() {
    try {
      const res = await fetch('data/periods.json');
      if (!res.ok) return;
      const periods = await res.json();
      const test = periods.find((p) => p.period === 'test');
      if (!test) return;

      const netEl = document.getElementById('hero-test-net');
      const grossEl = document.getElementById('hero-test-gross');
      const costsEl = document.getElementById('hero-test-costs');
      const descEl = document.getElementById('hero-test-desc');

      if (netEl) {
        netEl.textContent = usd(test.net_pnl, true);
        netEl.className = 'stat-val ' + (test.net_pnl >= 0 ? 'pos' : 'neg');
      }
      if (grossEl) {
        grossEl.textContent = usd(test.gross_pnl, true);
        grossEl.className = 'stat-val ' + (test.gross_pnl >= 0 ? 'pos' : 'neg');
      }
      if (costsEl) {
        costsEl.textContent = usd(test.costs);
      }
      if (descEl) {
        descEl.innerHTML = `Gross profit was positive (<b>${usd(test.gross_pnl, true)}</b>), but real-world execution costs erased 100% of the gains, resulting in an honest <b>${usd(test.net_pnl, true)}</b> net loss.`;
      }
    } catch (e) {
      console.warn('Hero metrics load deferred', e);
    }
  }

  // Global tooltip for inline glossary terms
  function initGlossaryTooltips() {
    let tooltip = document.getElementById('glossary-tooltip');
    if (!tooltip) {
      tooltip = document.createElement('div');
      tooltip.id = 'glossary-tooltip';
      tooltip.className = 'rp-tip';
      tooltip.hidden = true;
      document.body.appendChild(tooltip);
    }

    document.querySelectorAll('.term-tip').forEach((el) => {
      const termKey = el.getAttribute('data-term') || el.textContent.trim().toLowerCase();
      const def = GLOSSARY[termKey] || el.getAttribute('title');

      if (def) {
        el.removeAttribute('title'); // Prevent native browser tooltip collision

        el.addEventListener('mouseenter', (ev) => {
          tooltip.innerHTML = `
            <div class="rp-tip-t" style="font-weight:600; text-transform:capitalize;">${termKey}</div>
            <div style="font-size:12px; line-height:1.4; color:var(--color-fg);">${def}</div>
          `;
          tooltip.hidden = false;

          const rect = el.getBoundingClientRect();
          const tipRect = tooltip.getBoundingClientRect();
          const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
          const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;

          let top = rect.bottom + scrollTop + 6;
          let left = rect.left + scrollLeft;

          if (left + tipRect.width > document.documentElement.clientWidth - 16) {
            left = document.documentElement.clientWidth - tipRect.width - 16;
          }
          if (left < 16) left = 16;

          tooltip.style.top = top + 'px';
          tooltip.style.left = left + 'px';
        });

        el.addEventListener('mouseleave', () => {
          tooltip.hidden = true;
        });
      }
    });
  }

  // Active navigation highlight
  function initNavScrollSpy() {
    const sections = document.querySelectorAll('section[id], div[id="rp"]');
    const navLinks = document.querySelectorAll('.nav-link');

    window.addEventListener('scroll', () => {
      let current = '';
      const scrollPos = window.scrollY + 120;

      sections.forEach((sec) => {
        const top = sec.offsetTop;
        const height = sec.offsetHeight;
        if (scrollPos >= top && scrollPos < top + height) {
          current = sec.getAttribute('id');
        }
      });

      navLinks.forEach((link) => {
        link.classList.remove('active');
        if (link.getAttribute('href') === '#' + current) {
          link.classList.add('active');
        }
      });
    }, { passive: true });
  }

  // Math details toggle in Section 2
  function initMathToggle() {
    const btn = document.getElementById('math-toggle-btn');
    const details = document.getElementById('math-details-card');
    if (!btn || !details) return;

    btn.addEventListener('click', () => {
      const isHidden = details.hidden;
      details.hidden = !isHidden;
      btn.textContent = isHidden ? 'Hide the maths' : 'Show the maths';
      btn.setAttribute('aria-expanded', String(isHidden));
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    loadHeroHeadline();
    initGlossaryTooltips();
    initNavScrollSpy();
    initMathToggle();
  });
})();
