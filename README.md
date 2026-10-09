# Statistical Arbitrage in Equity Markets: Cointegration-Based Pairs Trading with Out-of-Sample Validation

A quantitative research platform investigating whether cointegration-based pairs trading can generate robust, risk-adjusted returns after transaction costs in US equity markets.

## Research Overview
- **Question**: Can cointegration-based pairs trading produce robust out-of-sample performance after realistic transaction costs, and how sensitive are the results to model assumptions, pair selection, and market conditions?
- **Universe**: 18 large-cap S&P 500 equities across three sectors (Banking, Energy, Consumer Staples).
- **Evaluation Protocol**: Chronological split into Calibration (2018–2021), Validation (2022), and strictly locked Out-of-Sample Test (2023–2024).

## Setup & Reproduction
```bash
pip install -r requirements.txt
pytest -q
```
