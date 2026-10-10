# Quantitative Methodology & Statistical Formulations

This document formalizes the statistical hypotheses, mathematical formulations, econometric assumptions, and portfolio construction mechanics underlying the cointegration-based pairs trading research pipeline.

---

## 1. Candidate-Pair Screening & Statistical Testing

### 1.1 Null Hypothesis & Econometric Assumptions
For each candidate pair $(A, B)$ of equity series within the same industry sector:
- **Null Hypothesis ($H_0$)**: No cointegrating relationship exists between $A$ and $B$. Specifically, the regression residuals $\epsilon_t = \ln(P_{A,t}) - \alpha - \beta \ln(P_{B,t})$ follow a unit-root process ($I(1)$), implying that any apparent price linkage is non-stationary and spurious.
- **Alternative Hypothesis ($H_1$)**: The series are cointegrated ($CI(1, 1)$). There exists a stationary linear combination $\epsilon_t \sim I(0)$ exhibiting mean-reverting equilibrium.

### 1.2 Two-Step Engle-Granger Procedure & Bidirectional Maximum P-Value
The standard Engle-Granger test estimates OLS in step 1 and evaluates the Augmented Dickey-Fuller (ADF) statistic on regression residuals in step 2:
$$\ln(P_{A,t}) = \alpha_{A|B} + \beta_{A|B} \ln(P_{B,t}) + \epsilon_{t}^{A|B}$$

**Normalization Asymmetry**: Because OLS minimizes squared vertical errors along the dependent axis, regressing $A$ on $B$ yields a different test statistic and residual series than regressing $B$ on $A$ in finite samples. To eliminate normalization bias and prevent selecting pairs that appear cointegrated only due to arbitrary dependent leg assignment, we evaluate both regressions:
$$p_{\text{pair}} = \max\left(p_{A|B},\, p_{B|A}\right)$$
A pair is considered candidate-cointegrated only if stationarity is supported under **both** directional projections.

### 1.3 Family-Wise Error Rate Control via Holm-Bonferroni
Testing $m = 45$ candidate pairs simultaneously introduces substantial data-snooping risk. If tested independently at $\alpha = 0.05$, the probability of at least one false positive under the global null is:
$$1 - (1 - \alpha)^m = 1 - (0.95)^{45} \approx 90.1\%$$

To control the Family-Wise Error Rate (FWER) at $\alpha = 0.05$ without the excessive conservatism of standard Bonferroni, we apply the Holm-Bonferroni step-down algorithm:
1. Sort raw p-values in ascending order: $p_{(1)} \le p_{(2)} \le \dots \le p_{(m)}$.
2. Step-down adjusted p-values:
   $$\tilde{p}_{(i)} = \max_{k \le i} \min\left(1.0, \, (m - k + 1) \cdot p_{(k)}\right)$$
3. Reject $H_0$ if and only if $\tilde{p}_{(i)} < \alpha$.

### 1.4 Mean-Reversion Half-Life Filter
Statistical cointegration does not guarantee tradability on practical investment horizons. We model spread mean reversion using a discrete Ornstein-Uhlenbeck / AR(1) process:
$$\Delta s_t = \gamma s_{t-1} + \mu + \epsilon_t, \quad \text{where } \gamma = \lambda - 1$$
The half-life of mean reversion in trading days is:
$$t_{1/2} = -\frac{\ln(2)}{\gamma}, \quad \text{for } \gamma < 0$$
Pairs are filtered to satisfy $t_{1/2} \in [1, 60]$ trading days to eliminate high-frequency microstructural noise ($t_{1/2} < 1$) and untradeable multi-quarter trends ($t_{1/2} > 60$).

---

## 2. Hedge Ratios, Spread Dynamics & Position Mapping

### 2.1 OLS Hedge Estimation & Theoretical Limitations
The baseline hedge ratio is estimated via OLS on log prices during the training period:
$$\ln(P_{A,t}) = \hat{\alpha} + \hat{\beta} \ln(P_{B,t}) + \hat{\epsilon}_t$$

**Econometric Limitations**:
1. **Superconsistency vs. Standard Inference**: Under true cointegration, the OLS estimator $\hat{\beta}$ converges to the true parameter at rate $T$ rather than the classical $\sqrt{T}$ (superconsistency; Stock 1987). However, second-order asymptotic bias and non-standard limiting distributions invalidate classical $t$-statistics and standard errors.
2. **Parameter Drift**: Macroeconomic shifts, capital structure changes, or revenue divergence cause structural parameter instability over time.
3. **Out-of-Sample Mean Shift**: In out-of-sample periods, the spread mean $\mathbb{E}[s_t]$ is not guaranteed to remain at zero, potentially leading to persistent one-sided exposure if uncorrected.

### 2.2 Position Mapping & Capital Weights
A long spread position entails buying leg $A$ and shorting leg $B$. The gross capital weights allocated to the pair are:
$$w_A = \frac{1}{1 + |\hat{\beta}|}, \qquad w_B = -\frac{\hat{\beta}}{1 + |\hat{\beta}|}$$
such that total gross notional exposure matches the pair's allocated capital:
$$|w_A| + |w_B| = \frac{1 + |\hat{\beta}|}{1 + |\hat{\beta}|} = 1.0$$

**Approximation of Dollar Hedge Ratio**:
For small proportional price movements $\frac{\Delta P}{P} \approx \Delta \ln(P)$, the log-price elasticity $\hat{\beta} = \frac{\partial \ln P_A}{\partial \ln P_B}$ satisfies:
$$\frac{\Delta P_A}{P_A} \approx \hat{\beta} \frac{\Delta P_B}{P_B} \implies \Delta P_A \approx \hat{\beta} \left(\frac{P_A}{P_B}\right) \Delta P_B$$
Hence, holding $\$w_A$ of $A$ and $-\hat{\beta} w_A$ of $B$ achieves first-order market neutrality with respect to common factor shocks.

**Share Count Drift**:
At fill date $t$, share counts are established as:
$$N_A = \frac{\text{Capital}_{\text{pair}} \cdot |w_A|}{P_{A,t}}, \qquad N_B = -\text{sgn}(\hat{\beta}) \frac{\text{Capital}_{\text{pair}} \cdot |w_B|}{P_{B,t}}$$
Because share quantities are held fixed between entry and exit, relative price movements cause effective dollar weights to drift continuously while positions remain open.
