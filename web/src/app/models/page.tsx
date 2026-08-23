"use client";

import { useEffect, useState } from "react";
import {
  Cpu,
  RefreshCw,
  Sliders,
  ShieldCheck,
  CheckCircle2,
  TrendingUp,
  Activity,
  Zap,
} from "lucide-react";
import { InfoTooltip } from "@/components/Tooltip";
import { MetricCard } from "@/components/MetricCard";
import { StrategyBlueprint } from "@/components/StrategyBlueprint";
import { api, ModelDetail, RegimeDetail } from "@/lib/api";
import { useTranslation } from "@/i18n";

export default function ModelsAndRegimesPage() {
  const { t } = useTranslation();
  const [models, setModels] = useState<ModelDetail[]>([]);
  const [selectedModel, setSelectedModel] = useState<ModelDetail | null>(null);
  const [regime, setRegime] = useState<RegimeDetail | null>(null);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    setLoading(true);
    try {
      const [modelList, currentRegime] = await Promise.all([
        api.getModels(),
        api.getCurrentRegime("SPY"),
      ]);
      setModels(modelList);
      if (modelList.length > 0) {
        setSelectedModel(modelList[0]);
      }
      setRegime(currentRegime);
    } catch (err) {
      console.error("Error fetching models/regimes:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const getQuadrantColor = (quadrant: string) => {
    switch (quadrant) {
      case "BULL_LOW_VOL":
        return "text-pos border-pos/30 bg-pos/10";
      case "BULL_HIGH_VOL":
        return "text-warn border-warn/30 bg-warn/10";
      case "BEAR_HIGH_VOL":
        return "text-neg border-neg/30 bg-neg/10";
      case "BEAR_LOW_VOL":
        return "text-warn border-warn/30 bg-warn/10";
      default:
        return "text-info border-info/30 bg-info/10";
    }
  };

  const getQuadrantLabel = (quadrant: string) => {
    switch (quadrant) {
      case "BULL_LOW_VOL":
        return t("models.quadrant_bull_low_vol");
      case "BULL_HIGH_VOL":
        return t("models.quadrant_bull_high_vol");
      case "BEAR_HIGH_VOL":
        return t("models.quadrant_bear_high_vol");
      case "BEAR_LOW_VOL":
        return t("models.quadrant_bear_low_vol");
      default:
        return t("models.quadrant_sideways");
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex items-center justify-between border-b border-border pb-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold font-mono tracking-tight text-text-1">
              {t("models.title")}
            </h1>
            <span className="badge-terminal bg-surface-2 text-info border border-border">
              L2
            </span>
          </div>
          <p className="text-xs text-text-3 font-mono mt-1">
            {t("models.subtitle")}
          </p>
        </div>

        <button
          onClick={loadData}
          disabled={loading}
          className="btn-terminal-ghost flex items-center gap-2 text-xs"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>{t("common.refresh")}</span>
        </button>
      </div>

      {/* Market Regime Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <h2 className="terminal-label text-text-1">{t("models.current_regime_title")}</h2>
            <InfoTooltip
              title={t("tooltips.regime_quadrant_title")}
              content={t("tooltips.regime_quadrant_desc")}
            />
          </div>
          <span className="text-[11px] font-mono text-text-3">{t("models.benchmark_lbl")}</span>
        </div>

        {regime ? (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className={`p-4 rounded border ${getQuadrantColor(regime.quadrant)} flex flex-col justify-between`}>
              <div>
                <div className="text-[10px] font-mono uppercase tracking-wider opacity-80 flex items-center justify-between">
                  <span>{t("models.state_quadrant")}</span>
                  <Zap className="w-3.5 h-3.5" />
                </div>
                <div className="text-base font-bold font-mono mt-1">
                  {getQuadrantLabel(regime.quadrant)}
                </div>
              </div>
              <div className="mt-3 text-[11px] font-mono opacity-90 leading-tight">
                {regime.rationale}
              </div>
            </div>

            <div className="card-terminal p-4 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between text-text-3 text-[10px] uppercase tracking-wider font-mono">
                  <div className="flex items-center">
                    <span>{t("models.trend_state")}</span>
                    <InfoTooltip
                      title={t("tooltips.trend_regime_title")}
                      content={t("tooltips.trend_regime_desc")}
                    />
                  </div>
                  <TrendingUp className="w-3.5 h-3.5 text-text-3" />
                </div>
                <div className="text-lg font-bold font-mono mt-1 text-text-1">
                  {regime.trend}
                </div>
              </div>
              <div className="text-[11px] font-mono text-text-3 mt-2">
                {t("models.trend_score")}: <span className={regime.trend_score >= 0 ? "text-pos font-semibold" : "text-neg font-semibold"}>{(regime.trend_score * 100).toFixed(1)}%</span>
              </div>
            </div>

            <div className="card-terminal p-4 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between text-text-3 text-[10px] uppercase tracking-wider font-mono">
                  <div className="flex items-center">
                    <span>{t("models.vol_state")}</span>
                    <InfoTooltip
                      title={t("tooltips.vol_regime_title")}
                      content={t("tooltips.vol_regime_desc")}
                    />
                  </div>
                  <Activity className="w-3.5 h-3.5 text-text-3" />
                </div>
                <div className="text-lg font-bold font-mono mt-1 text-text-1">
                  {regime.volatility}
                </div>
              </div>
              <div className="text-[11px] font-mono text-text-3 mt-2">
                {t("models.realized_vol_lbl")}: <span className="text-text-1 font-semibold">{(regime.realized_vol_21d * 100).toFixed(1)}%</span>
              </div>
            </div>

            <div className="card-terminal p-4 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between text-text-3 text-[10px] uppercase tracking-wider font-mono">
                  <div className="flex items-center">
                    <span>{t("models.market_breadth_lbl")}</span>
                    <InfoTooltip
                      title={t("tooltips.market_breadth_title")}
                      content={t("tooltips.market_breadth_desc")}
                    />
                  </div>
                  <ShieldCheck className="w-3.5 h-3.5 text-pos" />
                </div>
                <div className="text-lg font-bold font-mono mt-1 text-text-1">
                  {(regime.breadth_pct_50d * 100).toFixed(0)}% <span className="text-xs text-text-3 font-normal">{t("models.gt_50_sma")}</span>
                </div>
              </div>
              <div className="text-[11px] font-mono text-text-3 mt-2">
                {t("models.gt_200_sma")}: <span className="text-text-1 font-semibold">{(regime.breadth_pct_200d * 100).toFixed(0)}%</span>
              </div>
            </div>
          </div>
        ) : (
          <div className="card-terminal p-6 text-center text-text-3 text-xs font-mono">
            {t("models.loading_regime")}
          </div>
        )}
      </div>

      {/* Model Registry Section */}
      <div className="space-y-4 pt-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <h2 className="terminal-label text-text-1">{t("models.registry_title")}</h2>
            <InfoTooltip
              title={t("tooltips.model_registry_title")}
              content={t("tooltips.model_registry_desc")}
            />
          </div>
          <span className="text-[11px] font-mono text-text-3">
            {models.length} {t("models.registered_artifacts_count")}
          </span>
        </div>

        {models.length === 0 ? (
          <div className="card-terminal p-8 text-center text-text-3 text-xs font-mono">
            {t("models.no_models_found")}
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left: Model List */}
            <div className="space-y-2">
              {models.map((m) => {
                const isSelected =
                  selectedModel?.model_id === m.model_id &&
                  selectedModel?.version === m.version;
                return (
                  <button
                    key={`${m.model_id}-${m.version}`}
                    onClick={() => setSelectedModel(m)}
                    className={`w-full text-left p-3 rounded border transition-all font-mono ${
                      isSelected
                        ? "bg-surface-2 border-pos text-text-1"
                        : "bg-surface border-border text-text-2 hover:bg-surface-2"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Cpu className={`w-4 h-4 ${isSelected ? "text-pos" : "text-text-3"}`} />
                        <span className="text-xs font-bold text-text-1">{m.model_id}</span>
                      </div>
                      <span className="badge-terminal bg-surface text-[10px] text-text-3 border border-border">
                        v{m.version}
                      </span>
                    </div>

                    <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] text-text-3">
                      <div>
                        {t("common.type_lbl")}: <span className="text-text-2">{m.model_type}</span>
                      </div>
                      <div>
                        {t("common.horizon")}: <span className="text-text-2">{m.target_horizon_days}d</span>
                      </div>
                    </div>

                    <div className="mt-2 flex items-center justify-between text-[10px] text-text-3 border-t border-border-subtle pt-1.5">
                      <span>{t("models.cv_roc_auc")}:</span>
                      <span className="text-pos font-semibold">
                        {(m.metrics?.cv_roc_auc ?? 0).toFixed(3)}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Right: Selected Model Detail */}
            {selectedModel && (
              <div className="lg:col-span-2 card-terminal p-5 space-y-5">
                <div className="flex items-center justify-between border-b border-border-subtle pb-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-bold font-mono text-text-1">
                        {selectedModel.model_id}
                      </h3>
                      <span className="text-xs font-mono text-pos">
                        v{selectedModel.version}
                      </span>
                    </div>
                    <div className="text-[11px] font-mono text-text-3 mt-0.5">
                      {t("models.target_lbl")}: {selectedModel.target_name} ({selectedModel.target_horizon_days} {t("models.directional_classification")})
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="badge-terminal bg-surface-2 text-pos border border-border flex items-center gap-1 text-[10px]">
                      <CheckCircle2 className="w-3 h-3" />
                      {t("models.purged_cv_ready")}
                    </span>
                  </div>
                </div>

                {/* Performance & Training Specs */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="bg-surface-2 p-2.5 rounded border border-border">
                    <div className="text-[10px] font-mono text-text-3 uppercase flex items-center justify-between">
                      <span>{t("models.cv_roc_auc")}</span>
                      <InfoTooltip
                        title={t("tooltips.purged_cv_title")}
                        content={t("tooltips.purged_cv_desc")}
                      />
                    </div>
                    <div className="text-sm font-bold font-mono text-pos mt-1">
                      {(selectedModel.metrics?.cv_roc_auc ?? 0.5).toFixed(3)}
                    </div>
                  </div>

                  <div className="bg-surface-2 p-2.5 rounded border border-border">
                    <div className="text-[10px] font-mono text-text-3 uppercase flex items-center justify-between">
                      <span>{t("models.cv_accuracy")}</span>
                      <InfoTooltip
                        title={t("tooltips.cv_accuracy_title")}
                        content={t("tooltips.cv_accuracy_desc")}
                      />
                    </div>
                    <div className="text-sm font-bold font-mono text-text-1 mt-1">
                      {((selectedModel.metrics?.cv_accuracy ?? 0.5) * 100).toFixed(1)}%
                    </div>
                  </div>

                  <div className="bg-surface-2 p-2.5 rounded border border-border">
                    <div className="text-[10px] font-mono text-text-3 uppercase flex items-center justify-between">
                      <span>{t("models.train_partition")}</span>
                      <InfoTooltip
                        title={t("tooltips.holdout_guard_title")}
                        content={t("tooltips.train_partition_desc")}
                      />
                    </div>
                    <div className="text-xs font-mono text-text-2 mt-1">
                      {selectedModel.train_date_range?.[0]} &rarr; {selectedModel.train_date_range?.[1]}
                    </div>
                  </div>

                  <div className="bg-surface-2 p-2.5 rounded border border-border">
                    <div className="text-[10px] font-mono text-text-3 uppercase flex items-center justify-between">
                      <span>{t("models.features_lbl")}</span>
                      <InfoTooltip
                        title={t("tooltips.feature_count_title")}
                        content={t("tooltips.feature_count_desc")}
                      />
                    </div>
                    <div className="text-sm font-bold font-mono text-info mt-1">
                      {selectedModel.feature_names?.length || 0} {t("models.inputs_count")}
                    </div>
                  </div>
                </div>

                {/* Feature Importance Breakdown */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <div className="text-xs font-bold font-mono text-text-2">
                        {t("models.feature_importance_title")}
                      </div>
                      <InfoTooltip
                        title={t("tooltips.feature_importance_title")}
                        content={t("tooltips.feature_importance_desc")}
                      />
                    </div>
                    <span className="text-[10px] font-mono text-text-3">{t("models.norm_gbdt_weight")}</span>
                  </div>

                  <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                    {Object.entries(selectedModel.feature_importances || {})
                      .sort(([, a], [, b]) => b - a)
                      .map(([feat, imp]) => {
                        const pct = Math.max(2, Math.round(imp * 100));
                        return (
                          <div key={feat} className="space-y-1">
                            <div className="flex items-center justify-between text-[11px] font-mono">
                              <span className="text-text-2">{feat}</span>
                              <span className="text-text-1 font-semibold">{(imp * 100).toFixed(1)}%</span>
                            </div>
                            <div className="w-full bg-surface-2 h-1.5 rounded-full overflow-hidden">
                              <div
                                className="bg-pos h-full rounded-full transition-all duration-500"
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                          </div>
                        );
                      })}
                  </div>
                </div>

                {/* Hyperparameters Card */}
                <div className="border-t border-border-subtle pt-3">
                  <div className="text-[11px] font-mono text-text-3 uppercase mb-2">
                    {t("models.hyperparameters_title")}
                  </div>
                  <div className="bg-surface-2 p-3 rounded text-[11px] font-mono text-text-3 grid grid-cols-2 sm:grid-cols-3 gap-2">
                    <div>n_estimators: <span className="text-text-2">{selectedModel.hyperparameters?.n_estimators ?? 100}</span></div>
                    <div>learning_rate: <span className="text-text-2">{selectedModel.hyperparameters?.learning_rate ?? 0.05}</span></div>
                    <div>max_depth: <span className="text-text-2">{selectedModel.hyperparameters?.max_depth ?? 4}</span></div>
                    <div>num_leaves: <span className="text-text-2">{selectedModel.hyperparameters?.num_leaves ?? 15}</span></div>
                    <div>min_child_samples: <span className="text-text-2">{selectedModel.hyperparameters?.min_child_samples ?? 20}</span></div>
                    <div>reg_alpha / lambda: <span className="text-text-2">{selectedModel.hyperparameters?.reg_alpha ?? 0.1} / {selectedModel.hyperparameters?.reg_lambda ?? 1.0}</span></div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Quantitative Blueprint & Mathematical Model Architecture */}
      <StrategyBlueprint />
    </div>
  );
}
