/**
 * 3-Step Guided Tour for First-Time Visitors to the Replay Section.
 * Stored in localStorage and fully dismissible.
 */

(function () {
  'use strict';

  const STORAGE_KEY = 'stat_arb_pairs_tour_dismissed';

  const STEPS = [
    {
      targetId: 'rp-play',
      title: 'Step 1 of 3: Watch it trade',
      text: 'Press <b>Play</b> to run the day-by-day simulation across historical market days. You can adjust speed or drag the date scrubber at any time.',
      placement: 'bottom',
    },
    {
      targetId: 'h-pairs',
      title: 'Step 2 of 3: Spread z-score signals',
      text: 'Each chart shows a pair\'s price spread in standard deviations. When the line crosses the dashed threshold (±2.0), the gap is unusually wide and triggers an entry signal.',
      placement: 'top',
    },
    {
      targetId: 'h-feed',
      title: 'Step 3 of 3: Events & cost deductions',
      text: 'Signals execute at the next day\'s market close. Follow live orders in the events feed and inspect closed trades with all commissions, slippage, and borrow costs deducted.',
      placement: 'top',
    },
  ];

  let currentStep = 0;
  let overlayEl = null;
  let cardEl = null;

  function createTourElements() {
    if (cardEl) return;

    overlayEl = document.createElement('div');
    overlayEl.className = 'tour-overlay';
    document.body.appendChild(overlayEl);

    cardEl = document.createElement('div');
    cardEl.className = 'tour-card';
    cardEl.setAttribute('role', 'dialog');
    cardEl.setAttribute('aria-modal', 'true');
    cardEl.setAttribute('aria-label', 'Guided Tour');
    document.body.appendChild(cardEl);

    overlayEl.addEventListener('click', dismissTour);
  }

  function renderStep(idx) {
    if (!cardEl) createTourElements();
    const step = STEPS[idx];
    const target = document.getElementById(step.targetId);

    if (!target) {
      dismissTour();
      return;
    }

    target.scrollIntoView({ behavior: 'smooth', block: 'center' });

    cardEl.innerHTML = `
      <div class="tour-step-badge">${step.title}</div>
      <p class="tour-body">${step.text}</p>
      <div class="tour-actions">
        <button type="button" class="tour-btn" id="tour-dismiss-btn">Dismiss</button>
        <div style="display:flex; gap:0.4rem;">
          ${idx > 0 ? '<button type="button" class="tour-btn" id="tour-prev-btn">Back</button>' : ''}
          <button type="button" class="tour-btn tour-btn-primary" id="tour-next-btn">${idx === STEPS.length - 1 ? 'Finish' : 'Next'}</button>
        </div>
      </div>
    `;

    document.getElementById('tour-dismiss-btn').addEventListener('click', dismissTour);
    if (idx > 0) {
      document.getElementById('tour-prev-btn').addEventListener('click', () => {
        currentStep--;
        renderStep(currentStep);
      });
    }
    document.getElementById('tour-next-btn').addEventListener('click', () => {
      if (idx === STEPS.length - 1) {
        dismissTour();
      } else {
        currentStep++;
        renderStep(currentStep);
      }
    });

    overlayEl.classList.add('active');
    cardEl.style.display = 'flex';

    setTimeout(() => {
      positionCard(target, step.placement);
    }, 150);
  }

  function positionCard(target, placement) {
    const rect = target.getBoundingClientRect();
    const cardRect = cardEl.getBoundingClientRect();
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;

    let top = 0;
    let left = rect.left + scrollLeft + (rect.width / 2) - (cardRect.width / 2);

    if (placement === 'bottom') {
      top = rect.bottom + scrollTop + 12;
    } else {
      top = rect.top + scrollTop - cardRect.height - 12;
    }

    // Boundary constraints
    const maxLeft = document.documentElement.clientWidth - cardRect.width - 16;
    if (left < 16) left = 16;
    if (left > maxLeft) left = maxLeft;
    if (top < 16) top = rect.bottom + scrollTop + 12;

    cardEl.style.top = `${top}px`;
    cardEl.style.left = `${left}px`;
  }

  function dismissTour() {
    try {
      localStorage.setItem(STORAGE_KEY, 'true');
    } catch (e) {
      // localStorage may fail in private mode
    }
    if (overlayEl) overlayEl.classList.remove('active');
    if (cardEl) cardEl.style.display = 'none';
  }

  function startTour(force) {
    let alreadyDismissed = false;
    try {
      alreadyDismissed = localStorage.getItem(STORAGE_KEY) === 'true';
    } catch (e) {}

    if (alreadyDismissed && !force) return;

    createTourElements();
    currentStep = 0;
    renderStep(currentStep);
  }

  window.addEventListener('resize', () => {
    if (cardEl && cardEl.style.display !== 'none' && STEPS[currentStep]) {
      const target = document.getElementById(STEPS[currentStep].targetId);
      if (target) positionCard(target, STEPS[currentStep].placement);
    }
  });

  // Expose re-run
  window.relaunchReplayTour = function () {
    startTour(true);
  };

  // Delayed check after DOM is ready
  window.addEventListener('load', () => {
    setTimeout(() => {
      startTour(false);
    }, 1200);
  });
})();
