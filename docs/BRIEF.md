# PROJECT BRIEF: Build a Recruiter-Ready Quantitative Finance Research Platform

Act as a quantitative researcher at a systematic trading firm, a senior Python engineer, and a rigorous code reviewer.

I am a third-year MBA-Tech Computer Engineering student at NMIMS MPSTME, aspiring to secure a Quant Research Intern or Quant Analyst Intern position at quantitative trading firms, proprietary trading firms, hedge funds, or investment banks.

I want to build a technically rigorous, portfolio-quality project that demonstrates statistical reasoning, financial research, Python programming, backtesting, and model validation.

Your task is to help me DESIGN, IMPLEMENT, TEST, DOCUMENT, and FINALIZE the entire project—not merely explain how I could build it.

## 1. Project title

**Statistical Arbitrage in Equity Markets: Cointegration-Based Pairs Trading with Out-of-Sample Validation**

The project must investigate whether cointegration-based pairs trading can produce robust, risk-adjusted returns after transaction costs.

Do not assume the strategy is profitable. Negative or inconclusive findings are acceptable if the research is rigorous.

## 2. My constraints and technical background

- Programming language: Python 3.
- Python level: Advanced.
- Mathematics: Some statistics, calculus, and linear algebra.
- Time budget: 14 days.
- Primary target: Quant Research / Quant Analyst internships.
- Development environment: Local machine, preferably VS Code.
- Version control: Git and GitHub.
- Budget: Prefer free and publicly accessible tools and datasets.
- Optional extension: C++, but only if the core Python project is complete.

Prioritize a fully working, reproducible research system over an elaborate user interface.

## 3. Core research question

Can a cointegration-based pairs-trading strategy produce robust out-of-sample performance after realistic transaction costs, and how sensitive are the results to model assumptions, pair selection, and market conditions?

The project must answer this question empirically.

## 4. Dataset and universe

Use daily adjusted stock-price data from a suitable source such as Yahoo Finance via yfinance, subject to data availability and applicable terms.

Start with approximately 10–20 liquid US equities from a small number of related sectors.

Requirements:
- Define and document the universe-selection criteria.
- Use a consistent date range and trading calendar.
- Inspect missing observations, duplicates, corporate-action adjustments, and abnormal values.
- Handle missing data explicitly; do not silently forward-fill prices to manufacture observations.
- Record the data retrieval date and assumptions.
- Make data acquisition reproducible.
- Cache downloaded data locally where appropriate.
- Do not assume that historical constituents were available at the time unless survivorship bias is addressed.
- Do not use future information to select stocks or pairs.
- Do not fabricate market data or research results.

If the free data source is unavailable, explain the problem and provide a clear alternative rather than silently generating synthetic data and presenting it as real market data.

## 5. Statistical methodology

Implement the following research pipeline.

### A. Exploratory data analysis

- Plot adjusted price series and log prices.
- Calculate daily returns and summary statistics.
- Examine missing data and data-quality issues.
- Investigate whether the selected series are plausibly integrated of order one before applying the cointegration methodology.

### B. Candidate-pair screening

- Generate candidate pairs within the selected universe.
- Apply appropriate stationarity and cointegration tests.
- Use the Engle–Granger two-step approach as the initial methodology.
- Document the null hypothesis, assumptions, test statistics, and p-values.
- Correct for multiple hypothesis testing, for example with Holm–Bonferroni.
- Record the number of pairs tested and the number that pass the screening criteria.
- Perform selection using training data only.

Do not assume that highly correlated stocks are necessarily cointegrated.

### C. Hedge ratio and spread construction

Estimate the hedge ratio using a regression fitted on training data:

log(P_A,t) = alpha + beta * log(P_B,t) + residual_t

Define the spread as:

spread_t = log(P_A,t) - alpha_hat - beta_hat * log(P_B,t)

Explain the limitations of the regression and the stationarity assumptions.

For the baseline strategy, estimate parameters on the training period. Do not fit parameters on the entire dataset before evaluating the test period.

### D. Signal generation

Calculate a spread z-score using documented training or rolling-window statistics.

Implement a transparent baseline strategy with configurable parameters:
- Entry threshold: absolute z-score of 2.0.
- Exit threshold: absolute z-score of 0.5 or lower.
- A configurable maximum holding period.
- Explicit rules for position direction and closing trades.
- No overlapping positions in a pair unless deliberately supported and tested.

For example:
- A sufficiently positive spread triggers a short-spread position.
- A sufficiently negative spread triggers a long-spread position.
- The position closes when the spread returns near its estimated mean, subject to the specified risk rules.

Define position sizes and hedge weights precisely. Explain how the strategy translates log-price spreads into actual stock quantities or portfolio weights.

These thresholds are baseline hypotheses, not proven optimal parameters. Do not optimize parameters on the final test set.

## 6. Backtesting engine

Build a modular backtester with realistic, explicitly documented assumptions.

It must support:
- Chronological signal generation.
- Position tracking and trade accounting.
- Execution no earlier than the next available trading opportunity after a close-based signal.
- Transaction costs.
- Configurable slippage assumptions.
- Long and short legs.
- Portfolio-level return calculation.
- Capital allocation and position sizing.
- Exposure and holding-period tracking.
- Equity curves and drawdowns.
- Trade logs and per-pair results.

Avoid look-ahead bias, accidental use of future data, unrealistic fills, incorrect return alignment, and double-counted costs.

If borrow fees, short-sale restrictions, dividends, or market impact cannot be modelled accurately, explicitly state the limitation and provide a sensitivity analysis where feasible.

Do not assume every trade can be executed at the closing price that generated the signal.

## 7. Backtesting and validation protocol

Use a chronological split. An initial example is:
- Training: 2018–2022.
- Out-of-sample test: 2023–2024.

Check data availability before fixing the dates. Adjust the periods if necessary and document the reasons before evaluating final results.

The methodology must:
- Perform pair selection and model fitting using training data only.
- Freeze the research decisions before final test evaluation.
- Use only information available at each signal date.
- Avoid random train/test splits for time-series evaluation.
- Correct for multiple testing during pair screening.
- Clearly distinguish training, validation, and final test results.
- Compare performance before and after costs.
- Test robustness across reasonable pre-specified entry/exit thresholds and transaction-cost assumptions.
- Evaluate results across multiple candidate pairs rather than showcasing only the best-performing pair.
- Investigate market exposure, unstable hedge ratios, spread divergence, structural breaks, and strategy failure cases.

If the test period is used repeatedly to choose parameters, disclose that it is no longer an untouched final test set.

## 8. Performance metrics

Calculate and explain the following, using clearly defined portfolio-level returns:

1. Cumulative and annualized returns.
2. Annualized volatility.
3. Sharpe ratio, with the risk-free-rate assumption documented.
4. Maximum drawdown.
5. Turnover.
6. Gross and net P&L.
7. Number of trades.
8. Win rate and average trade return, with caveats.
9. Average and maximum holding period.
10. Exposure and concentration.
11. Performance by pair and by subperiod.
12. Sensitivity to transaction costs and model parameters.

Use consistent annualization assumptions and ensure that the equity curve and return series are mathematically consistent.

A z-score or a profitable spread chart is not a substitute for portfolio performance.

Do not hardcode, manufacture, or guess any performance metrics.

## 9. Required visualizations

Create clear, professional plots:
- Adjusted prices and log prices for selected pairs.
- Spread series with estimated mean and entry/exit thresholds.
- Spread z-score with entry and exit signals.
- Training versus out-of-sample equity curves.
- Drawdown curve.
- Gross versus net performance.
- Parameter-sensitivity analysis.
- Pair-level performance comparison.
- Distribution of trade returns or holding periods.

Every figure must be generated from actual project results, have descriptive labels, and be saved in the reports/figures/ directory.

Do not generate fake charts or illustrative results that could be mistaken for actual backtest outputs.

## 10. Required technology stack

Use:
- Python 3.
- pandas and NumPy.
- SciPy.
- statsmodels.
- Matplotlib.
- yfinance or another documented data source.
- pytest.
- Git and GitHub.

Use additional libraries only where they materially improve the implementation.

Do not introduce machine learning, deep learning, reinforcement learning, or C++ unless the core project is complete and validated.

## 11. Required GitHub repository structure

Create a professional, modular repository with a structure similar to:

stat-arb-pairs-trading/
├── README.md
├── requirements.txt
├── .gitignore
├── configs/
│   └── baseline.yaml
├── data/
│   └── README.md
├── notebooks/
│   └── exploratory_analysis.ipynb
├── src/
│   ├── __init__.py
│   ├── data.py
│   ├── validation.py
│   ├── pairs.py
│   ├── signals.py
│   ├── backtest.py
│   ├── portfolio.py
│   ├── metrics.py
│   └── plotting.py
├── tests/
│   ├── test_data.py
│   ├── test_signals.py
│   ├── test_backtest.py
│   └── test_metrics.py
└── reports/
    ├── research_report.md
    ├── results/
    └── figures/

You may modify the structure if necessary, but keep the system modular and easy to understand.

Do not commit secrets, virtual environments, caches, or unnecessarily large raw datasets. Include instructions for obtaining the data and reproducing the results.

## 12. Code quality and testing

The code must:
- Use clear function names, type hints where useful, and docstrings.
- Separate data acquisition, statistical analysis, signals, execution, metrics, and visualization.
- Avoid monolithic notebooks.
- Include deterministic unit tests for important calculations.
- Test signal timing, position changes, transaction-cost deductions, return alignment, drawdown calculations, and edge cases.
- Handle missing values and failed statistical tests gracefully.
- Use reproducible configurations and random seeds for any stochastic procedures.
- Include a clean dependency file and environment setup instructions.
- Run without requiring credentials or paid APIs.

Do not claim the code passes tests unless the tests have actually been run.

## 13. Research report

Create a concise, professional research report covering:

1. Abstract and research question.
2. Financial intuition and hypothesis.
3. Dataset and universe selection.
4. Statistical methodology.
5. Pair-selection procedure.
6. Trading and execution rules.
7. Backtesting assumptions.
8. Training and out-of-sample results.
9. Risk and performance analysis.
10. Robustness checks.
11. Limitations and possible sources of bias.
12. Conclusion and future work.

Distinguish observations from interpretations. Explain both successful and unsuccessful findings.

The report must not imply that a historical backtest guarantees future profitability or that this project represents a live-trading system.

## 14. README and recruiter presentation

The README must contain:
- A concise project overview.
- The research question.
- The methodology and mathematical intuition.
- A system architecture overview.
- Installation instructions.
- Data acquisition instructions.
- A single reproducible command for running the research pipeline where feasible.
- Unit-test instructions.
- Actual results and plots, once computed.
- Limitations and ethical/data-use notes.
- A list of future improvements.

Make the repository professional enough for a quantitative research hiring manager to inspect in approximately five minutes.

Prioritize research quality over decorative UI design.

## 15. Two-week execution plan

Organize the work into these milestones:

Days 1–2: Data pipeline, repository, data-quality checks.

Days 3–4: Exploratory analysis, stationarity and pair screening.

Days 5–6: Hedge ratios, spread construction and signals.

Days 7–8: Backtester, execution assumptions and unit tests.

Days 9–10: Out-of-sample evaluation and metrics.

Days 11–12: Robustness, sensitivity and failure analysis.

Days 13–14: Research report, documentation, reproducibility and GitHub polish.

At the end of each milestone, summarize what is implemented, what has been tested, what remains, and which commands I should run next.

## 16. CV bullet guidance

After the project is complete, generate two or three concise resume bullets using only verified implementation details.

Use quantified results only when they have been calculated from actual experiments. If the strategy is unprofitable, do not hide that fact or invent attractive metrics. Emphasize rigorous testing, research design, implementation, and model validation where supported by the work.

Do not claim that I developed a profitable strategy merely because I implemented a backtester.

## 17. Your working procedure

Follow this workflow:

1. Inspect your execution environment and determine what files and tools you can actually create or run.
2. Propose a compact implementation plan and identify critical design decisions.
3. Build the minimum viable research pipeline first.
4. Run it on actual downloaded data.
5. Run unit tests and fix implementation bugs.
6. Inspect the results and verify the calculations.
7. Add robustness analysis.
8. Write the research report and README from actual findings.
9. Produce a final checklist and suggested CV bullets.

If you can create and edit project files directly, do so rather than giving me only snippets. If you cannot execute code or access market data, state the limitation and provide runnable code and precise commands without pretending execution succeeded.

Work incrementally. Do not dump thousands of lines of untested code in a single response. Start by presenting the architecture, the data and statistical assumptions, and the first implementation milestone. Then proceed through the project in manageable, testable stages.

**Final standard:** This project must be a reproducible quantitative research exercise, not a superficial trading bot, a copied tutorial, or a fabricated performance demonstration.
