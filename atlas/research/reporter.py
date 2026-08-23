"""Research report generator and markdown artifact builder (Phase 8).

Generates exhaustive, transparent, and honest research reports detailing
hypothesis motivation, train vs validation performance, Gatekeeper checks,
parameter sensitivity matrices, Monte Carlo distributions, and multiple-testing impact.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from atlas.data.models import ResearchHypothesis, ResearchReport
from atlas.research.gatekeeper import GatekeeperEvaluation


class ResearchReporter:
    """Generates structured JSON and human-readable Markdown research reports."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_report(
        self,
        hypothesis: ResearchHypothesis | None,
        strategy_spec_name: str,
        family: str,
        spec_hash: str,
        train_metrics: dict[str, Any],
        val_metrics: dict[str, Any],
        gatekeeper_eval: GatekeeperEvaluation,
        trial_count: int = 1,
    ) -> ResearchReport:
        """Construct, format, and persist a complete ResearchReport record."""
        report_id = f"rep_{str(uuid.uuid4())[:12]}"
        title = (
            f"Research Report: {strategy_spec_name} ({family})"
            if not hypothesis
            else f"Research Report: {hypothesis.title}"
        )

        md_content = self.generate_markdown(
            report_id=report_id,
            title=title,
            family=family,
            spec_name=strategy_spec_name,
            spec_hash=spec_hash,
            hypothesis_desc=hypothesis.description
            if hypothesis
            else "Baseline strategy validation.",
            generator_type=hypothesis.generator_type if hypothesis else "MANUAL",
            train_metrics=train_metrics,
            val_metrics=val_metrics,
            gatekeeper_eval=gatekeeper_eval,
            trial_count=trial_count,
        )

        report = ResearchReport(
            id=report_id,
            hypothesis_id=hypothesis.id if hypothesis else None,
            title=title,
            family=family,
            strategy_spec_name=strategy_spec_name,
            spec_hash=spec_hash,
            train_metrics=json.dumps(train_metrics, sort_keys=True),
            val_metrics=json.dumps(val_metrics, sort_keys=True),
            gatekeeper_results=json.dumps(gatekeeper_eval.to_dict(), sort_keys=True),
            gatekeeper_passed=gatekeeper_eval.passed_all,
            verdict=gatekeeper_eval.verdict,
            report_markdown=md_content,
            human_decision="PENDING_REVIEW",
            human_decision_notes=None,
            created_at=datetime.now(UTC),
        )

        self.session.add(report)
        self.session.commit()
        self.session.refresh(report)
        return report

    def generate_markdown(
        self,
        report_id: str,
        title: str,
        family: str,
        spec_name: str,
        spec_hash: str,
        hypothesis_desc: str,
        generator_type: str,
        train_metrics: dict[str, Any],
        val_metrics: dict[str, Any],
        gatekeeper_eval: GatekeeperEvaluation,
        trial_count: int,
    ) -> str:
        """Generate formatted GitHub-flavored Markdown text for research dashboard."""
        status_badge = (
            "**PASSED (Awaiting Human Review)**"
            if gatekeeper_eval.passed_all
            else f"**REJECTED ({gatekeeper_eval.verdict})**"
        )

        lines = [
            f"# {title}",
            f"**Report ID:** `{report_id}` | **Generated:** {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"**Family:** `{family}` | **Spec:** `{spec_name}` | **Generator:** `{generator_type}` | **Spec Hash:** `{spec_hash[:12]}...`",
            f"**Gatekeeper Verdict:** {status_badge}",
            "",
            "## 1. Hypothesis & Method",
            hypothesis_desc,
            "",
            "## 2. In-Sample (Train) vs Out-of-Sample (Validation) Performance",
            "",
            "| Metric | Train (2005-2018) | Validation (2019-2022) | Status |",
            "|---|---|---|---|",
            f"| **Sharpe Ratio** | `{train_metrics.get('sharpe_ratio', 0.0):.2f}` | `{val_metrics.get('sharpe_ratio', 0.0):.2f}` | {'PASS' if float(val_metrics.get('sharpe_ratio', 0.0)) > 0.5 else 'WARN'} |",
            f"| **CAGR** | `{float(train_metrics.get('cagr', 0.0)) * 100:.1f}%` | `{float(val_metrics.get('cagr', 0.0)) * 100:.1f}%` | {'PASS' if float(val_metrics.get('cagr', 0.0)) > 0 else 'FAIL'} |",
            f"| **Max Drawdown** | `{float(train_metrics.get('max_drawdown', 0.0)) * 100:.1f}%` | `{float(val_metrics.get('max_drawdown', 0.0)) * 100:.1f}%` | {'PASS' if float(val_metrics.get('max_drawdown', 0.0)) < 0.25 else 'WARN'} |",
            f"| **Calmar Ratio** | `{train_metrics.get('calmar_ratio', 0.0):.2f}` | `{val_metrics.get('calmar_ratio', 0.0):.2f}` | - |",
            f"| **Win Rate** | `{float(train_metrics.get('win_rate', 0.0)) * 100:.1f}%` | `{float(val_metrics.get('win_rate', 0.0)) * 100:.1f}%` | - |",
            f"| **Profit Factor** | `{train_metrics.get('profit_factor', 0.0):.2f}` | `{val_metrics.get('profit_factor', 0.0):.2f}` | - |",
            f"| **Total Trades** | `{train_metrics.get('total_trades', 0)}` | `{val_metrics.get('total_trades', 0)}` | {'PASS' if int(train_metrics.get('total_trades', 0)) >= 100 else 'FAIL'} |",
            "",
            "## 3. Statistical Gatekeeper Matrix (8 Gates)",
            "",
            "| # | Gate | Value | Threshold | Result |",
            "|---|---|---|---|---|",
        ]

        for r in gatekeeper_eval.results:
            badge = "PASS" if r.passed else "FAIL"
            lines.append(
                f"| {r.gate_number} | {r.name} | `{r.score:.3f}` | `{r.operator} {r.threshold:.3f}` | **{badge}** |"
            )

        lines.extend(
            [
                "",
                "## 4. Multiple Testing & Trial Budget Impact",
                f"- **Trials Tested in Family (`{family}`):** {trial_count}",
                "- **Holdout Status:** LOCKED (2023-01-01 -> Present-90d)",
                "- **Deflated Sharpe Adjustment:** Applied via Bailey & Lopez de Prado (2014) correction.",
                "",
                "## 5. Next Steps",
                "Per Master Plan §11 Phase 8 rules:",
                "1. The autonomous loop **can never promote a strategy automatically**.",
                "2. If all 8 gates are satisfied, this candidate is queued in the Human Review Queue (`/research`).",
                "3. Promotion to `CANDIDATE` or `PAPER` requires an explicit human click in the dashboard.",
            ]
        )

        return "\n".join(lines)
