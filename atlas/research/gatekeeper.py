"""Statistical Gatekeeper implementing Section 8.3 promotion gates (Phase 8).

Automates rigorous statistical checks before any candidate strategy is validated
or presented in the Human Candidate Review Queue.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from atlas.research.stats import (
    calculate_deflated_sharpe,
    calculate_pbo,
    monte_carlo_trade_shuffle,
)
from atlas.strategies.spec import StrategySpec


@dataclass
class GateResult:
    """Individual gatekeeper test evaluation record."""

    gate_number: int
    name: str
    passed: bool
    score: float
    threshold: float
    operator: str  # ">", "<", ">=", "<="
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_number": self.gate_number,
            "name": self.name,
            "passed": self.passed,
            "score": round(self.score, 4),
            "threshold": round(self.threshold, 4),
            "operator": self.operator,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class GatekeeperEvaluation:
    """Complete 8-gate evaluation outcome for a candidate strategy."""

    strategy_name: str
    passed_all: bool
    gates_passed: int
    total_gates: int
    verdict: str  # PASSED | REJECTED_OVERFIT | REJECTED_CORRELATION | REJECTED_COST | REJECTED_SAMPLE | REJECTED_ROBUSTNESS
    results: list[GateResult]
    summary_markdown: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "passed_all": self.passed_all,
            "gates_passed": self.gates_passed,
            "total_gates": self.total_gates,
            "verdict": self.verdict,
            "results": [r.to_dict() for r in self.results],
            "summary_markdown": self.summary_markdown,
        }


class StatisticalGatekeeper:
    """Evaluates candidate strategies against all 8 promotion gates (§8.3)."""

    def __init__(
        self,
        min_walk_forward_folds: int = 6,
        min_median_fold_sharpe: float = 0.5,
        max_param_degradation: float = 0.40,
        min_mc_p5_cagr: float = 0.0,
        min_stressed_sharpe: float = 0.40,
        max_negative_regimes: int = 1,
        min_trades: int = 100,
        min_test_years: float = 3.0,
        max_pbo: float = 0.50,
        min_dsr_probability: float = 0.50,
        max_active_correlation: float = 0.60,
    ) -> None:
        self.min_walk_forward_folds = min_walk_forward_folds
        self.min_median_fold_sharpe = min_median_fold_sharpe
        self.max_param_degradation = max_param_degradation
        self.min_mc_p5_cagr = min_mc_p5_cagr
        self.min_stressed_sharpe = min_stressed_sharpe
        self.max_negative_regimes = max_negative_regimes
        self.min_trades = min_trades
        self.min_test_years = min_test_years
        self.max_pbo = max_pbo
        self.min_dsr_probability = min_dsr_probability
        self.max_active_correlation = max_active_correlation

    def evaluate(
        self,
        spec: StrategySpec,
        train_metrics: dict[str, Any],
        trade_returns: list[float],
        daily_returns: list[float] | None = None,
        walk_forward_fold_sharpes: list[float] | None = None,
        perturbed_sharpes: list[float] | None = None,
        stressed_cost_sharpe: float | None = None,
        regime_sharpes: dict[str, float] | None = None,
        active_strategy_correlations: list[float] | None = None,
        total_trials_in_family: int = 1,
        candidate_returns_matrix: np.ndarray | None = None,
    ) -> GatekeeperEvaluation:
        """Run all 8 statistical promotion gate checks."""
        results: list[GateResult] = []
        _ = daily_returns

        base_sharpe = float(train_metrics.get("sharpe_ratio", 0.0) or 0.0)
        total_trades = int(train_metrics.get("total_trades", len(trade_returns)) or 0)
        years = float(train_metrics.get("duration_years", 3.0) or 3.0)

        # ---------------------------------------------------------------------
        # Gate 1: Walk-Forward Analysis (Rolling 3y train / 1y test, >= 6 folds)
        # ---------------------------------------------------------------------
        if walk_forward_fold_sharpes is None or not walk_forward_fold_sharpes:
            g1_pass = False
            med_fold_sharpe = 0.0
            n_folds = 0
            g1_msg = "Walk-forward fold results not provided (execution required)."
        else:
            med_fold_sharpe = float(np.median(walk_forward_fold_sharpes))
            n_folds = len(walk_forward_fold_sharpes)
            g1_pass = (n_folds >= self.min_walk_forward_folds) and (
                med_fold_sharpe > self.min_median_fold_sharpe
            )
            g1_msg = f"Median fold Sharpe is {med_fold_sharpe:.2f} across {n_folds} folds (req > {self.min_median_fold_sharpe:.2f})."

        results.append(
            GateResult(
                gate_number=1,
                name="Walk-Forward Stability",
                passed=g1_pass,
                score=med_fold_sharpe,
                threshold=self.min_median_fold_sharpe,
                operator=">",
                message=g1_msg,
                details={"folds": walk_forward_fold_sharpes or [], "n_folds": n_folds},
            )
        )

        # ---------------------------------------------------------------------
        # Gate 2: Parameter Perturbation (+-25% jitter -> degradation < 40%)
        # ---------------------------------------------------------------------
        if perturbed_sharpes is None or not perturbed_sharpes:
            g2_pass = False
            degradation = 1.0
            min_perturbed = 0.0
            g2_msg = "Parameter perturbation sensitivity test not provided."
        elif base_sharpe <= 0.0:
            min_perturbed = min(perturbed_sharpes)
            degradation = 1.0
            g2_pass = False
            g2_msg = (
                f"Baseline Sharpe is non-positive ({base_sharpe:.2f}); parameter robustness failed."
            )
        else:
            min_perturbed = min(perturbed_sharpes)
            degradation = max(0.0, (base_sharpe - min_perturbed) / base_sharpe)
            g2_pass = (degradation < self.max_param_degradation) and (min_perturbed > 0.0)
            g2_msg = f"Max parameter perturbation degradation is {degradation * 100:.1f}% (req < {self.max_param_degradation * 100:.1f}%)."

        results.append(
            GateResult(
                gate_number=2,
                name="Parameter Robustness",
                passed=g2_pass,
                score=degradation,
                threshold=self.max_param_degradation,
                operator="<",
                message=g2_msg,
                details={
                    "perturbed_sharpes": [round(s, 3) for s in perturbed_sharpes]
                    if perturbed_sharpes
                    else [],
                    "min_perturbed": round(min_perturbed, 3),
                    "base_sharpe": round(base_sharpe, 3),
                },
            )
        )

        # ---------------------------------------------------------------------
        # Gate 3: Monte Carlo Trade Shuffle (1000 iter -> 5th-percentile CAGR > 0)
        # ---------------------------------------------------------------------
        mc_results = monte_carlo_trade_shuffle(
            trade_returns,
            n_sims=1000,
            total_years=years,
            position_fraction=0.10,
            daily_returns=daily_returns,
        )
        p5_cagr = mc_results["p5_cagr"]
        g3_pass = p5_cagr > self.min_mc_p5_cagr
        results.append(
            GateResult(
                gate_number=3,
                name="Monte Carlo Trade Permutation",
                passed=g3_pass,
                score=p5_cagr,
                threshold=self.min_mc_p5_cagr,
                operator=">",
                message=f"5th percentile shuffled CAGR is {p5_cagr * 100:.2f}% (req > {self.min_mc_p5_cagr * 100:.2f}%).",
                details=mc_results,
            )
        )

        # ---------------------------------------------------------------------
        # Gate 4: Cost Stress (Slippage k=1.0 -> 1.5 -> Sharpe > 0.4)
        # ---------------------------------------------------------------------
        if stressed_cost_sharpe is None:
            g4_pass = False
            stressed_score = -1.0
            g4_msg = "Slippage stress test (1.5x) results not provided."
        else:
            stressed_score = stressed_cost_sharpe
            g4_pass = stressed_cost_sharpe > self.min_stressed_sharpe
            g4_msg = f"Sharpe under 1.5x slippage stress is {stressed_cost_sharpe:.2f} (req > {self.min_stressed_sharpe:.2f})."

        results.append(
            GateResult(
                gate_number=4,
                name="Cost & Slippage Stress",
                passed=g4_pass,
                score=stressed_score,
                threshold=self.min_stressed_sharpe,
                operator=">",
                message=g4_msg,
                details={
                    "stressed_sharpe": round(stressed_cost_sharpe, 3)
                    if stressed_cost_sharpe is not None
                    else None,
                    "base_sharpe": round(base_sharpe, 3),
                },
            )
        )

        # ---------------------------------------------------------------------
        # Gate 5: Regime Breakdown (Not net-negative in > 1 of 4 regimes)
        # ---------------------------------------------------------------------
        if regime_sharpes is None or not regime_sharpes:
            g5_pass = False
            negative_regimes = 4
            g5_msg = "Market regime breakdown performance not provided."
        else:
            negative_regimes = sum(1 for s in regime_sharpes.values() if s < 0.0)
            g5_pass = negative_regimes <= self.max_negative_regimes
            g5_msg = f"Negative performance observed in {negative_regimes} / {len(regime_sharpes)} regimes (req <= {self.max_negative_regimes})."

        results.append(
            GateResult(
                gate_number=5,
                name="Market Regime Breakdown",
                passed=g5_pass,
                score=float(negative_regimes),
                threshold=float(self.max_negative_regimes),
                operator="<=",
                message=g5_msg,
                details={"regime_sharpes": {k: round(v, 3) for k, v in regime_sharpes.items()}}
                if regime_sharpes
                else {},
            )
        )

        # ---------------------------------------------------------------------
        # Gate 6: Minimum Sample Size (>= 100 trades, >= 3 years data)
        # ---------------------------------------------------------------------
        g6_pass = (total_trades >= self.min_trades) and (years >= self.min_test_years)
        results.append(
            GateResult(
                gate_number=6,
                name="Sample Size Adequacy",
                passed=g6_pass,
                score=float(total_trades),
                threshold=float(self.min_trades),
                operator=">=",
                message=f"Sample contains {total_trades} trades across {years:.1f} years (req >= {self.min_trades} trades & >= {self.min_test_years:.1f}y).",
                details={"total_trades": total_trades, "duration_years": years},
            )
        )

        # ---------------------------------------------------------------------
        # Gate 7: PBO & Deflated Sharpe (PBO < 0.5, DSR > 0.50)
        # ---------------------------------------------------------------------
        periods_n = (
            len(daily_returns)
            if (daily_returns is not None and len(daily_returns) > 0)
            else int(train_metrics.get("total_bars", 252 * 3) or 756)
        )
        dsr_prob = calculate_deflated_sharpe(
            sharpe=base_sharpe,
            trials=max(total_trials_in_family, 1),
            var_trials=0.04,
            skewness=float(train_metrics.get("skewness", 0.0) or 0.0),
            kurtosis=float(train_metrics.get("kurtosis", 3.0) or 3.0),
            n_periods=periods_n,
        )

        # Matrix for PBO estimation
        if candidate_returns_matrix is not None and candidate_returns_matrix.shape[1] >= 2:
            pbo_res = calculate_pbo(candidate_returns_matrix, n_splits=8)
            pbo_val = float(pbo_res["pbo"])
            g7_pass = (pbo_val < self.max_pbo) and (dsr_prob >= self.min_dsr_probability)
            g7_msg = f"Probability of Backtest Overfitting is {pbo_val:.2f} (req < {self.max_pbo:.2f}); DSR confidence is {dsr_prob * 100:.1f}%."
        else:
            pbo_val = 0.0
            g7_pass = dsr_prob >= self.min_dsr_probability
            g7_msg = f"DSR confidence is {dsr_prob * 100:.1f}% (req >= {self.min_dsr_probability * 100:.1f}% across {total_trials_in_family} trials)."

        results.append(
            GateResult(
                gate_number=7,
                name="PBO & Deflated Sharpe",
                passed=g7_pass,
                score=pbo_val
                if (candidate_returns_matrix is not None and candidate_returns_matrix.shape[1] >= 2)
                else dsr_prob,
                threshold=self.max_pbo
                if (candidate_returns_matrix is not None and candidate_returns_matrix.shape[1] >= 2)
                else self.min_dsr_probability,
                operator="<"
                if (candidate_returns_matrix is not None and candidate_returns_matrix.shape[1] >= 2)
                else ">=",
                message=g7_msg,
                details={
                    "pbo": pbo_val
                    if (
                        candidate_returns_matrix is not None
                        and candidate_returns_matrix.shape[1] >= 2
                    )
                    else None,
                    "dsr_probability": dsr_prob,
                    "trials_tested": total_trials_in_family,
                },
            )
        )

        # ---------------------------------------------------------------------
        # Gate 8: Correlation Guard (< 0.6 to active strategies)
        # ---------------------------------------------------------------------
        if active_strategy_correlations is None or not active_strategy_correlations:
            max_corr = 0.15  # Default low correlation if first strategy in family
        else:
            max_corr = float(max(active_strategy_correlations))

        g8_pass = max_corr < self.max_active_correlation
        results.append(
            GateResult(
                gate_number=8,
                name="Correlation Guard",
                passed=g8_pass,
                score=max_corr,
                threshold=self.max_active_correlation,
                operator="<",
                message=f"Max correlation to active promoted strategies is {max_corr:.2f} (req < {self.max_active_correlation:.2f}).",
                details={
                    "max_correlation": round(max_corr, 3),
                    "correlations": active_strategy_correlations or [],
                },
            )
        )

        # ---------------------------------------------------------------------
        # Tally & Overall Verdict
        # ---------------------------------------------------------------------
        passed_count = sum(1 for r in results if r.passed)
        passed_all = passed_count == len(results)

        if passed_all:
            verdict = "PASSED"
        elif not g8_pass:
            verdict = "REJECTED_CORRELATION"
        elif not g7_pass or not g1_pass:
            verdict = "REJECTED_OVERFIT"
        elif not g4_pass:
            verdict = "REJECTED_COST"
        elif not g6_pass:
            verdict = "REJECTED_SAMPLE"
        else:
            verdict = "REJECTED_ROBUSTNESS"

        summary_md = self._build_markdown_summary(
            spec.name, passed_count, len(results), verdict, results
        )

        return GatekeeperEvaluation(
            strategy_name=spec.name,
            passed_all=passed_all,
            gates_passed=passed_count,
            total_gates=len(results),
            verdict=verdict,
            results=results,
            summary_markdown=summary_md,
        )

    def _build_markdown_summary(
        self,
        strategy_name: str,
        passed_count: int,
        total_gates: int,
        verdict: str,
        results: list[GateResult],
    ) -> str:
        """Construct a structured markdown summary report."""
        lines = [
            f"# Statistical Gatekeeper Report — {strategy_name}",
            f"**Overall Verdict:** `{verdict}` ({passed_count}/{total_gates} gates passed)",
            "",
            "| # | Gate | Metric | Score | Threshold | Status |",
            "|---|---|---|---|---|---|",
        ]

        for r in results:
            icon = "PASS" if r.passed else "FAIL"
            lines.append(
                f"| {r.gate_number} | {r.name} | {r.message.split(' is ')[0]} | `{r.score:.3f}` | `{r.operator} {r.threshold:.3f}` | **{icon}** |"
            )

        lines.extend(
            [
                "",
                "### Detailed Gate Findings",
            ]
        )
        for r in results:
            lines.append(f"- **Gate {r.gate_number} ({r.name}):** {r.message}")

        return "\n".join(lines)
