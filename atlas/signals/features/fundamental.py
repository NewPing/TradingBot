"""Fundamental and valuation feature extractors with point-in-time filing discipline."""

from __future__ import annotations

import logging
from collections.abc import Sequence

import numpy as np

from atlas.core.context import MarketContext
from atlas.core.types import FundamentalSnapshot, Symbol
from atlas.signals.features.base import FeatureMetadata

logger = logging.getLogger("atlas.signals.features.fundamental")


class FundamentalFeatureExtractor:
    """Extracts valuation multiples, financial quality, growth, leverage, and Sloan accruals."""

    def __init__(self) -> None:
        pass

    @property
    def feature_names(self) -> list[str]:
        """List of fundamental and valuation feature column names."""
        return [
            # Valuation
            "fund_pe_ratio",
            "fund_ev_ebitda",
            "fund_fcf_yield",
            "fund_pb_ratio",
            "fund_ps_ratio",
            "fund_value_score",
            # Quality & Margins
            "fund_roic",
            "fund_roe",
            "fund_gross_margin",
            "fund_operating_margin",
            "fund_net_margin",
            "fund_accrual_ratio",
            "fund_quality_score",
            # Growth
            "fund_revenue_growth_yoy",
            "fund_eps_growth_yoy",
            "fund_fcf_growth_yoy",
            # Leverage & Solvency
            "fund_debt_to_equity",
            "fund_net_debt_to_ebitda",
            "fund_current_ratio",
            "fund_interest_coverage",
        ]

    @property
    def warmup_bars(self) -> int:
        return 1

    def metadata(self) -> list[FeatureMetadata]:
        return [
            FeatureMetadata(
                name="fund_roic",
                description="Return on Invested Capital (NOPAT / Invested Capital)",
                category="fundamental",
                lookback_bars=1,
                min_value=-1.0,
                max_value=2.0,
            ),
            FeatureMetadata(
                name="fund_accrual_ratio",
                description="Sloan Accrual Ratio ((Net Income - CFO) / Total Assets). Lower is higher quality.",
                category="fundamental",
                lookback_bars=1,
                min_value=-2.0,
                max_value=2.0,
            ),
            FeatureMetadata(
                name="fund_fcf_yield",
                description="Free Cash Flow Yield (FCF / Enterprise Value)",
                category="fundamental",
                lookback_bars=1,
                min_value=-0.5,
                max_value=0.5,
            ),
            FeatureMetadata(
                name="fund_ev_ebitda",
                description="Enterprise Value to EBITDA ratio",
                category="fundamental",
                lookback_bars=1,
                min_value=0.0,
                max_value=100.0,
            ),
            FeatureMetadata(
                name="fund_quality_score",
                description="Composite quality score [0, 1] based on ROIC, FCF, and low accruals",
                category="fundamental",
                lookback_bars=1,
                min_value=0.0,
                max_value=1.0,
                is_normalized=True,
            ),
            FeatureMetadata(
                name="fund_value_score",
                description="Composite valuation score [0, 1] based on low EV/EBITDA, P/E, and high FCF yield",
                category="fundamental",
                lookback_bars=1,
                min_value=0.0,
                max_value=1.0,
                is_normalized=True,
            ),
        ]

    def extract_pit(self, ctx: MarketContext, symbol: Symbol) -> dict[str, float]:
        """Extract latest PIT fundamental feature dictionary for symbol at or before ctx.now."""
        snapshot = ctx.fundamentals(symbol)
        if snapshot is None:
            return self._default_features()

        return self.compute_features_from_snapshot(snapshot)

    def _default_features(self) -> dict[str, float]:
        """Return zero/neutral default feature values when no fundamental filing exists."""
        return {
            "fund_pe_ratio": 0.0,
            "fund_ev_ebitda": 0.0,
            "fund_fcf_yield": 0.0,
            "fund_pb_ratio": 0.0,
            "fund_ps_ratio": 0.0,
            "fund_value_score": 0.5,
            "fund_roic": 0.0,
            "fund_roe": 0.0,
            "fund_gross_margin": 0.0,
            "fund_operating_margin": 0.0,
            "fund_net_margin": 0.0,
            "fund_accrual_ratio": 0.0,
            "fund_quality_score": 0.5,
            "fund_revenue_growth_yoy": 0.0,
            "fund_eps_growth_yoy": 0.0,
            "fund_fcf_growth_yoy": 0.0,
            "fund_debt_to_equity": 0.0,
            "fund_net_debt_to_ebitda": 0.0,
            "fund_current_ratio": 1.0,
            "fund_interest_coverage": 1.0,
        }

    def compute_features_from_snapshot(self, snapshot: FundamentalSnapshot) -> dict[str, float]:
        """Compute structured fundamental features from raw metrics."""
        m = snapshot.metrics

        pe = float(m.get("pe_ratio", 0.0))
        ev_ebitda = float(m.get("ev_to_ebitda", 0.0))
        fcf_yield = float(m.get("fcf_yield", 0.0))
        pb = float(m.get("pb_ratio", m.get("price_to_book", 0.0)))
        ps = float(m.get("ps_ratio", m.get("price_to_sales", 0.0)))

        roic = float(m.get("roic", 0.0))
        roe = float(m.get("roe", 0.0))
        gross_margin = float(m.get("gross_margin", 0.0))
        op_margin = float(m.get("operating_margin", 0.0))
        net_margin = float(m.get("net_margin", 0.0))

        # Sloan accruals: (Net Income - CFO) / Total Assets
        accrual_ratio = float(m.get("accrual_ratio", 0.0))
        if accrual_ratio == 0.0 and "total_assets" in m and float(m["total_assets"]) > 0:
            ni = float(m.get("net_income", 0.0))
            cfo = float(m.get("operating_cash_flow", 0.0))
            assets = float(m["total_assets"])
            accrual_ratio = (ni - cfo) / assets

        # Growth
        rev_growth = float(m.get("revenue_growth_yoy", m.get("revenue_growth", 0.0)))
        eps_growth = float(m.get("eps_growth_yoy", m.get("eps_growth", 0.0)))
        fcf_growth = float(m.get("fcf_growth_yoy", m.get("fcf_growth", 0.0)))

        # Solvency
        debt_to_equity = float(m.get("debt_to_equity", 0.0))
        net_debt_to_ebitda = float(m.get("net_debt_to_ebitda", 0.0))
        current_ratio = float(m.get("current_ratio", 1.0))
        interest_coverage = float(m.get("interest_coverage", 5.0))

        # Composite Quality Score [0, 1]
        # High ROIC (+), High Operating Margin (+), Low Sloan Accrual (+)
        roic_scaled = np.clip((roic - 0.05) / 0.25, 0.0, 1.0)
        margin_scaled = np.clip(op_margin / 0.30, 0.0, 1.0)
        # Sloan accrual: lower is better (< 0 is excellent, > 0.1 is suspect)
        accrual_scaled = np.clip(1.0 - (accrual_ratio + 0.05) / 0.15, 0.0, 1.0)
        fcf_yield_scaled = np.clip((fcf_yield - 0.02) / 0.08, 0.0, 1.0)

        quality_score = float(
            0.35 * roic_scaled
            + 0.25 * accrual_scaled
            + 0.20 * margin_scaled
            + 0.20 * fcf_yield_scaled
        )

        # Composite Value Score [0, 1]
        # Low EV/EBITDA (+), Low P/E (+), High FCF yield (+)
        ev_score = np.clip(1.0 - (ev_ebitda - 6.0) / 20.0, 0.0, 1.0) if ev_ebitda > 0 else 0.5
        pe_score = np.clip(1.0 - (pe - 10.0) / 30.0, 0.0, 1.0) if pe > 0 else 0.5
        value_score = float(0.40 * ev_score + 0.30 * pe_score + 0.30 * fcf_yield_scaled)

        return {
            "fund_pe_ratio": float(pe),
            "fund_ev_ebitda": float(ev_ebitda),
            "fund_fcf_yield": float(fcf_yield),
            "fund_pb_ratio": float(pb),
            "fund_ps_ratio": float(ps),
            "fund_value_score": float(np.clip(value_score, 0.0, 1.0)),
            "fund_roic": float(roic),
            "fund_roe": float(roe),
            "fund_gross_margin": float(gross_margin),
            "fund_operating_margin": float(op_margin),
            "fund_net_margin": float(net_margin),
            "fund_accrual_ratio": float(accrual_ratio),
            "fund_quality_score": float(np.clip(quality_score, 0.0, 1.0)),
            "fund_revenue_growth_yoy": float(rev_growth),
            "fund_eps_growth_yoy": float(eps_growth),
            "fund_fcf_growth_yoy": float(fcf_growth),
            "fund_debt_to_equity": float(debt_to_equity),
            "fund_net_debt_to_ebitda": float(net_debt_to_ebitda),
            "fund_current_ratio": float(current_ratio),
            "fund_interest_coverage": float(interest_coverage),
        }


class SectorRelativeNormalizer:
    """Computes cross-sectional sector-relative z-scores for fundamental features."""

    def __init__(self, symbol_sector_map: dict[Symbol, str] | None = None) -> None:
        self.symbol_sector_map = symbol_sector_map or {}

    def compute_sector_zscores(
        self,
        universe_features: dict[Symbol, dict[str, float]],
        metrics_to_normalize: Sequence[str] | None = None,
    ) -> dict[Symbol, dict[str, float]]:
        """Normalize metrics relative to sector peers.

        Returns a dictionary mapping Symbol -> sector-normalized z-scores.
        """
        if metrics_to_normalize is None:
            metrics_to_normalize = [
                "fund_roic",
                "fund_ev_ebitda",
                "fund_fcf_yield",
                "fund_quality_score",
                "fund_value_score",
                "fund_accrual_ratio",
            ]

        # Group symbols by sector
        sector_symbols: dict[str, list[Symbol]] = {}
        for sym in universe_features:
            sec = self.symbol_sector_map.get(sym, "GENERAL")
            if sec not in sector_symbols:
                sector_symbols[sec] = []
            sector_symbols[sec].append(sym)

        result: dict[Symbol, dict[str, float]] = {sym: {} for sym in universe_features}

        for _sec, syms in sector_symbols.items():
            for metric in metrics_to_normalize:
                vals = np.array([universe_features[s].get(metric, 0.0) for s in syms], dtype=float)
                if len(vals) > 1:
                    mean = float(np.nanmean(vals))
                    std = float(np.nanstd(vals))
                    if std > 1e-6:
                        z_vals = np.clip((vals - mean) / std, -3.0, 3.0)
                    else:
                        z_vals = np.zeros_like(vals)
                else:
                    z_vals = np.zeros_like(vals)

                for idx, s in enumerate(syms):
                    result[s][f"sector_zscore_{metric.replace('fund_', '')}"] = float(z_vals[idx])

        return result
