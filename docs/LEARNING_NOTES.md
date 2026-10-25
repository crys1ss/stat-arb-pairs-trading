# Quant Finance Learning Notes: Cointegration-Based Pairs Trading

Welcome to your project study guide! This document is written in clear, plain language to help you thoroughly understand every piece of your statistical arbitrage pairs trading project (`stat-arb-pairs-trading`). 

Use this guide to review key quantitative concepts, trace how the code works line by line, and practise your answers for technical interviews and viva exams.

---

## 1. Project Summary: The Dog & Stretchy Leash Analogy

### The Analogy
Imagine an owner walking two dogs connected by a stretchy bungee leash. 

```
Dog A (Bank of America: BAC)
    \
     \===== [Stretchy Leash: Cointegration Equilibrium] =====/
                                                             \
                                                      Dog B (PNC Financial: PNC)
```

1. **The Random Walks**: As the dogs walk through a park, each dog sniffs different trees, chases birds, and wanders unpredictably. Their path over the grass is a **random walk**—you cannot predict where they will wander next.
2. **The Leash (Cointegration)**: However, because of the stretchy leash connecting them, the dogs **cannot wander infinitely far apart**. If Dog A spots a squirrel and lunges forward, the leash stretches and gets tight.
3. **The Trade (Statistical Arbitrage)**: When the leash is stretched to an extreme distance, you bet that the leash will snap them back together:
   - You **sell** the dog that ran too far ahead (short the overpriced stock).
   - You **buy** the dog that fell behind (long the underpriced stock).
4. **The Mean Reversion**: When the dogs snap back to their normal walking distance, you close both positions and pocket the difference as profit.

### What Actually Happened in This Project?
We built this strategy using Python, calibrated it on 4 years of historical data (2018–2021), validated it on 1 year (2022), and then tested it on an untouched 2-year out-of-sample window (2023–2024):

- **In Training (2018–2021)**: The strategy looked great. Gross profit was **+$226.6k** and net profit after costs was **+$212.3k**.
- **In Out-of-Sample Test (2023–2024)**: The strategy **failed to produce positive net returns**. Gross profit was **+$10.6k**, but transaction fees ($15.6k) and short borrow fees ($2.6k) totaled **$18.2k**, resulting in a net loss of **-$7,613.28** (net Sharpe **-0.12**).

### Why Did It Fail? (The Two Real Causes)
1. **The Leash Was Mostly an Illusion (Screening Failure)**:
   When we tested 45 intra-sector candidate pairs in training and applied strict statistical corrections (Holm-Bonferroni) to guard against luck, **zero pairs survived**. Furthermore, 2 of our 5 fallback pairs (`COP_DVN` $p=0.053$, `COP_CVX` $p=0.090$) failed even an uncorrected 5% test. Cointegration never actually existed for `COP_DVN`. We weren't holding a bungee leash; we were holding two stray dogs wandering independently. `COP_DVN` alone lost **-$36,982.71**.
2. **Transaction Costs Ate All the Edge**:
   The gross profit was small, and executing 39 trades with 10.0 bps of friction per side (commission + slippage) plus 50 bps annual borrow fees overwhelmed gross earnings by 172%. The strategy needed transaction costs under **5.12 bps** just to break even.

---

## 2. Core Concepts Explained Simply

### 1. Short Selling
* **What it means**: Selling a stock you do not currently own, with the goal of buying it back later at a lower price.
* **How it works**: Your broker borrows the shares from another investor and lends them to you. You sell them on the open market and receive cash. Later, you "buy to cover" in the market and return the shares to the lender.
* **The risk**: If the stock price rises, your loss is theoretically unlimited.
* **The cost**: You must pay a **borrow fee** (in our backtest, 50 basis points per year, or 0.50% annualized) to the broker for renting the shares.

### 2. Correlation vs. Cointegration
This is the single most important distinction in statistical arbitrage:
* **Correlation ($\rho$)**: Measures whether two assets move in the same direction on a day-to-day basis (co-movement in percentage returns). 
  * *Example*: Two drunk friends walking out of a bar might step left and right together for 10 minutes, but after 2 hours they might end up miles apart in different neighborhoods.
* **Cointegration**: Measures whether a linear combination of two asset price levels is stationary (reverts to a constant long-term mean).
  * *Example*: A dog and its owner on a leash. They might step in opposite directions at any given second, but they cannot drift permanently apart.
* **Key takeaway**: High correlation does **not** prevent prices from drifting apart forever. Only cointegration guarantees a bounded, mean-reverting spread.

### 3. Z-Score ($z$)
* **What it means**: A standardized ruler that measures how many standard deviations the current spread is away from its historical average:
  $$z_t = \frac{s_t - \mu}{\sigma}$$
* $z = 0$: The spread is exactly at its normal historical mean.
* $z = +2.0$: The spread is 2 standard deviations wider than normal (Asset A is expensive relative to B). This triggers a **Short Spread** entry (short A, buy B).
* $z = -2.0$: The spread is 2 standard deviations narrower than normal (Asset A is cheap relative to B). This triggers a **Long Spread** entry (buy A, short B).
* $|z| \le 0.5$: The spread has reverted near the mean. Time to exit and lock in profit.

### 4. Hedge Ratio ($\beta$)
* **What it means**: The relative weight or sensitivity between the two stocks. We estimate it by regressing log price of stock A on log price of stock B:
  $$\ln(P_{A,t}) = \alpha + \beta \ln(P_{B,t}) + \epsilon_t$$
* If $\beta = 1.5$, it means that for every 1% move in stock B, stock A tends to move 1.5%.
* To make the trade dollar-neutral to broad industry moves, our portfolio weights are split inversely to price movements: $w_A = 1 / (1 + \beta)$ and $w_B = \beta / (1 + \beta)$.

### 5. Mean-Reversion Half-Life ($t_{1/2}$)
* **What it means**: The estimated number of trading days it takes for a dislocated spread to travel halfway back to its equilibrium mean.
* **How we compute it**: We run an autoregressive regression on spread changes:
  $$\Delta s_t = \gamma s_{t-1} + \mu + \epsilon_t$$
  The half-life formula used in code is:
  $$t_{1/2} = -\frac{\ln 2}{\gamma} \quad (\text{for } \gamma < 0)$$
* **Why it matters**:
  * If half-life is too short (< 1 day): The signal is microsecond microstructure noise, not an exploitable swing.
  * If half-life is too long (> 60 days): Capital is tied up for months in a slow-moving trade with high borrow costs. We look for $t_{1/2} \in [1, 60]$ days.

### 6. Overfitting (Data Snooping)
* **What it means**: Fitting a model so closely to the random noise of historical data that it fails to generalize to future data.
* **In our project**: If you test 45 intra-sector pairs at an uncorrected 5% significance level, probability theory predicts $45 \times 0.05 \approx 2.25$ pairs will look cointegrated by pure random chance!
* **The cure**: The **Holm-Bonferroni correction**, which adjusts the p-value threshold downward to ensure the entire basket has less than a 5% chance of containing even a single false discovery.

### 7. In-Sample vs. Out-of-Sample
* **In-Sample (Train: 2018–2021)**: The data used to discover patterns, select pairs, and fit hedge ratios. Performance here is always overly optimistic.
* **Validation (2022)**: An intermediate dataset used to test design tweaks (like our v1.1 re-entry cooldown) without burning the final test set.
* **Out-of-Sample (Test: 2023–2024)**: The untouched final exam. Kept in a vault until all code, parameters, and hypotheses are frozen. Out-of-sample results tell you the honest truth about real-world viability.

### 8. Transaction Costs & Friction
Every time a trade opens or closes, money leaks out:
* **Commissions**: Broker execution fee (modeled as 5.0 bps per side).
* **Slippage**: Crossing the bid-ask spread and market price impact (modeled as 5.0 bps per side).
* **Total round-trip trade friction**: 10.0 bps to enter and 10.0 bps to exit on both legs = **40.0 bps per pair round-trip**.
* **Short borrow cost**: 50 bps annualized, accrued daily for every day a short position remains open.

### 9. Break-Even Cost ($C^*$)
* **What it means**: The maximum trading fee you could pay before your total net profit falls to exactly $0.00$.
* If your strategy makes $10,000 gross on $20,000,000 of turnover, your break-even cost is $10,000 / $20,000,000 = 5.0$ bps.
* In our test period, the break-even cost was **5.12 bps**. Because realistic retail/institutional execution costs 10.0 bps, the strategy was mathematically doomed to lose money net of costs.

---

## 3. Walkthrough of `src/signals.py` (The State Machine)

The signal generator is a **deterministic causal state machine**. It evaluates spread z-scores bar-by-bar, never looks into the future, and outputs position commands (+1, -1, 0) and exit reasons.

Here is how each logical block works:

### Block 1: Initializing Variables & Flags
```python
pos = 0               # Current position: 0 = Flat, +1 = Long Spread, -1 = Short Spread
days_held = 0         # Counter: how many trading days the current trade has been open
cooldown_rem = 0      # Counter: how many bars remaining in re-entry cooldown
positions = []        # Array to store output positions for each bar
exit_reasons = []     # Array to store why a trade was closed
```
- The engine starts flat with zero open exposure.
- `cooldown_rem` tracks whether new entries are temporarily blocked.

### Block 2: The Time-Step Loop (Day-by-Day)
The engine steps through every trading day $t = 0, 1, \dots, T-1$. At each bar, it checks the current z-score $z_t$.

### Block 3: Exit Checks for Open Positions
If we are already in a trade (`pos != 0`), we check whether it is time to close it:

1. **Max Holding Horizon Stop (`max_hold`)**:
   ```python
   if days_held >= max_holding_days:  # 30 days in baseline
       pos = 0
       exit_reason = "max_hold"
       if cooldown_days > 0:
           cooldown_rem = cooldown_days
   ```
   *Why this exists*: Prevents a non-reverting spread from trapping capital indefinitely.
   *The v1.1 fix*: If closed due to timeout, set `cooldown_rem = cooldown_days` (e.g. 20 bars) to prevent immediately reopening the same bad trade on the very next bar!

2. **Divergence Stop Loss (`stop`)**:
   ```python
   elif stop_z is not None and abs(z) >= stop_z:
       pos = 0
       exit_reason = "stop"
       if cooldown_days > 0:
           cooldown_rem = cooldown_days
   ```
   *Why this exists*: If the spread blows out beyond extreme boundaries (e.g. $|z| \ge 4.0$), cut losses early. Also activates the cooldown.

3. **Normal Mean-Reversion Exit (`mean_revert`)**:
   ```python
   elif pos == 1 and z >= -exit_z:    # Long spread reverts up to -0.5
       pos = 0
       exit_reason = "mean_revert"
   elif pos == -1 and z <= exit_z:    # Short spread reverts down to +0.5
       pos = 0
       exit_reason = "mean_revert"
   ```
   *Why this exists*: The trade succeeded! The leash snapped back. Close the position for a profit.
   *Crucial rule*: A normal profitable exit **does NOT** trigger a cooldown.

### Block 4: Cooldown Decrement
If we are currently flat (`pos == 0`) and a cooldown is active (`cooldown_rem > 0`):
```python
if pos == 0 and cooldown_rem > 0:
    cooldown_rem -= 1
```
Each day we stay flat, the cooldown timer counts down toward zero. While `cooldown_rem > 0`, new entries are blocked.

### Block 5: Entry Logic (Opening New Trades)
If we are flat (`pos == 0`) AND not in cooldown (`cooldown_rem == 0`):
```python
if z <= -entry_z:       # z <= -2.0: Spread is abnormally low
    pos = 1             # Enter Long Spread (Buy A, Short B)
    days_held = 0
elif z >= entry_z:      # z >= +2.0: Spread is abnormally high
    pos = -1            # Enter Short Spread (Short A, Buy B)
    days_held = 0
```

### Block 6: Execution Lag Shift
```python
if execution_lag > 0:
    positions = positions.shift(execution_lag).fillna(0)
```
*Why this is vital*: A signal computed at the market close of Day $t$ cannot be traded at Day $t$'s close. It can only be filled at Day $t+1$'s close. Shifting by 1 bar prevents lookahead bias.

---

## 4. Top 10 Interview & Viva Questions (With Practice Answers)

Here are the 10 questions a professor, quant interviewer, or reviewer is most likely to ask, along with clear, practiced answers:

### Q1: "Why did your pairs trading strategy lose money out-of-sample?"
> **Answer**: "The failure was driven by two factors: **screening reality** and **transaction costs**. In training, zero pairs survived Holm-Bonferroni multiple testing correction, and 2 of our 5 fallback pairs weren't even cointegrated at the uncorrected 5% level. Specifically, `COP_DVN` was non-cointegrated noise that suffered persistent divergence, accounting for -$36.9k in losses. On top of that, transaction friction of 10 bps per side plus short borrow costs consumed 172% of gross trading profits. Our out-of-sample break-even cost was only 5.12 bps."

### Q2: "What is the difference between correlation and cointegration, and why do quants care?"
> **Answer**: "Correlation measures short-term co-movement in price returns, while cointegration measures a long-term stationary equilibrium in price levels. Two assets can have a high 90% correlation but permanently drift apart over time like two independent random walks. Cointegration guarantees that a linear combination of their prices has bounded variance and mean-reverts over a finite horizon, making it the proper foundation for pairs trading."

### Q3: "What is the Holm-Bonferroni method, and what happened when you ran it on your universe?"
> **Answer**: "When testing 45 pairs simultaneously at an alpha of 5%, the family-wise error rate inflates to over 90%, meaning you are almost guaranteed to find false positive cointegration by luck. Holm-Bonferroni is a step-down multiple-testing correction that controls this false discovery rate. In our universe of 18 stocks across Banks, Energy, and Staples, **zero pairs survived** the Holm-Bonferroni filter. This was our first warning that genuine cointegration in large-cap equities is rare."

### Q4: "If zero pairs passed the Holm filter, why did you continue the backtest?"
> **Answer**: "We had a pre-registered protocol in our project plan: if zero pairs passed Holm, we selected an exploratory fallback basket consisting of the top 5 pairs by lowest raw p-value that met the half-life bound (1 to 60 days). This allowed us to rigorously test whether an exploratory basket could survive out-of-sample. It proved that trading pairs without confirmed cointegration leads directly to severe non-reverting losses."

### Q5: "What was your worst single trade, and what caused it?"
> **Answer**: "Our worst trade was in `COP_DVN` during the 2022 validation period, losing -$35,583, and its repeated entries in 2023–2024. The spread blew out and never reverted. Because the baseline model lacked a divergence stop loss, the trade was held for the full 29-day maximum holding horizon before being liquidated at peak divergence. Furthermore, because the spread was still wide at exit, the engine immediately re-entered the trade the next day, multiplying the loss."

### Q6: "How did you fix that repeated re-entry problem in v1.1?"
> **Answer**: "We added an optional `cooldown_days` parameter to the signal generator. Whenever a trade exits due to `max_hold` or `stop`, new entries on that pair are locked for a specified window (e.g. 20 trading days). Normal mean-reverting exits do not trigger a cooldown. Evaluating this on the 2022 validation period eliminated 9 churned trades, reduced `COP_DVN` losses by $16.7k, and boosted net validation Sharpe from 0.15 to 0.63."

### Q7: "Why didn't you evaluate your v1.1 cooldown on the 2023–2024 test period?"
> **Answer**: "Because that would violate out-of-sample data hygiene. The 2023–2024 test period was our locked 'vault' dataset used for our v1 final evaluation. Once a test dataset has been inspected, modifying code and re-running on it turns it into an in-sample training set, creating post-hoc lookahead bias. All v1.1 cooldown experiments were strictly restricted to the 2022 validation period."

### Q8: "Is your strategy market-neutral? What was its market beta?"
> **Answer**: "The full-span beta to SPY was +0.0075 with an $R^2$ of 0.28%, confirming near-zero overall market exposure. In the test period, the Newey-West HAC beta was statistically significant at $\beta = -0.0318$ ($t = -2.66$), but its economic magnitude is negligible. The strategy failed because of idiosyncratic spread divergence and transaction friction, not because of market movements."

### Q9: "What is execution lag and why is it important?"
> **Answer**: "Execution lag accounts for the time between signal generation and order fill. In our pipeline, signals are calculated using daily closing prices at day $t$, but cannot be filled until day $t+1$'s close (`execution_lag = 1`). Assuming instant fills at day $t$'s close introduces lookahead bias and unrealistically inflates performance."

### Q10: "If you had 3 more months and a research budget, how would you improve this strategy?"
> **Answer**: "Three primary enhancements:
> 1. **Dynamic Hedge Ratios via Kalman Filters**: Replace static in-sample OLS with state-space models that adapt hedge ratios continuously to shifting company fundamentals.
> 2. **Divergence Stop Losses & Cooldowns**: Enforce strict volatility stops ($|z| \ge 4.0$) combined with re-entry cooldowns to cut runaway divergence early.
> 3. **Higher Frequency / Lower Friction Instruments**: Transition from single-stock equities (which suffer 10 bps friction and borrow fees) to highly liquid ETFs or futures with sub-basis-point tick spreads and zero short borrow drag."

---

## 5. Honest Project Limitations (The "Real Talk" Checklist)

When presenting this project to experienced quants, being completely upfront about limitations demonstrates maturity and integrity:

1. **Survivorship Bias**:
   We selected 18 large-cap stocks that were continuous S&P 500 members from 2018 through 2024. We did not include companies that went bankrupt, merged, or were delisted during that time.
2. **Small Universe**:
   Our universe had only 18 tickers (45 candidate pairs). In large-cap equities, true cointegration is scarce; expanding the universe to 100+ stocks might surface more candidates, though multiple-testing hurdles also grow.
3. **Static In-Sample Parameters**:
   The baseline strategy fit $\alpha$, $\beta$, $\mu$, and $\sigma$ once on 2018–2021 data and held them static through 2024. In the real world, industrial relationships shift across interest rate regimes and corporate actions.
4. **Simplified Corporate Actions & Borrow Mechanics**:
   - Dividends were handled via price adjustments rather than physical cash flow debits on short legs.
   - Borrow fees were assumed to be a fixed 50 bps annual rate; hard-to-borrow spikes and recall risks were not simulated.
5. **Execution Realism**:
   Orders executed at $t+1$ close with a static 5 bps slippage penalty, ignoring order book depth, Market-on-Close (MOC) imbalance queues, and non-linear market impact.
