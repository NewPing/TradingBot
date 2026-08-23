"use client";

import { useEffect, useState } from "react";
import {
  Newspaper,
  Sparkles,
  TrendingUp,
  TrendingDown,
  Clock,
  Zap,
  ShieldCheck,
  Send,
  FileText,
  ChevronRight,
  Hash,
  AlertCircle,
  BarChart2,
  Lock,
} from "lucide-react";
import { InfoTooltip } from "@/components/Tooltip";
import { useTranslation } from "@/i18n";
import {
  api,
  NewsArticleDTO,
  NewsStatsResponse,
  PromptTemplateDTO,
  SymbolSentimentResponse,
  NewsScoreDTO,
} from "@/lib/api";

export default function NarrativePage() {
  const { t } = useTranslation();
  const [newsFeed, setNewsFeed] = useState<NewsArticleDTO[]>([]);
  const [stats, setStats] = useState<NewsStatsResponse | null>(null);
  const [prompts, setPrompts] = useState<PromptTemplateDTO[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState("NVDA");
  const [symbolSentiment, setSymbolSentiment] = useState<SymbolSentimentResponse | null>(null);
  const [selectedArticle, setSelectedArticle] = useState<NewsArticleDTO | null>(null);
  const [loading, setLoading] = useState(true);

  // On-demand scoring test state
  const [customTitle, setCustomTitle] = useState("");
  const [customSummary, setCustomSummary] = useState("");
  const [customSymbol, setCustomSymbol] = useState("NVDA");
  const [scoringLoading, setScoringLoading] = useState(false);
  const [testScoreResult, setTestScoreResult] = useState<NewsScoreDTO | null>(null);

  useEffect(() => {
    loadAllData();
  }, [selectedSymbol]);

  async function loadAllData() {
    setLoading(true);
    const [feed, statsData, promptsData, sentData] = await Promise.all([
      api.getNewsFeed(),
      api.getNewsStats(),
      api.getPromptTemplates(),
      api.getSymbolSentiment(selectedSymbol),
    ]);

    setNewsFeed(feed);
    setStats(statsData);
    setPrompts(promptsData);
    setSymbolSentiment(sentData);
    if (feed.length > 0 && !selectedArticle) {
      setSelectedArticle(feed[0]);
    }
    setLoading(false);
  }

  async function handleTestScore(e: React.FormEvent) {
    e.preventDefault();
    if (!customTitle || !customSummary) return;

    setScoringLoading(true);
    setTestScoreResult(null);

    const result = await api.scoreNewsArticle({
      symbols: [customSymbol.toUpperCase()],
      title: customTitle,
      summary: customSummary,
    });

    setTestScoreResult(result);
    setScoringLoading(false);
  }

  const sentimentColor = (score: number) => {
    if (score > 0.2) return "text-pos";
    if (score < -0.2) return "text-neg";
    return "text-text-2";
  };

  const sentimentBg = (score: number) => {
    if (score > 0.2) return "bg-pos/10 border-pos/30 text-pos";
    if (score < -0.2) return "bg-neg/10 border-neg/30 text-neg";
    return "bg-surface-2 border-border text-text-2";
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-text-1 font-mono flex items-center gap-2">
              <Newspaper className="w-5 h-5 text-pos" />
              {t("narrative.title")}
            </h1>
            <InfoTooltip
              title={t("tooltips.l4_narrative_title")}
              content={t("tooltips.l4_narrative_desc")}
            />
          </div>
          <p className="text-xs text-text-3 font-mono mt-1">
            {t("narrative.subtitle")}
          </p>
        </div>

        {/* Top Badges */}
        <div className="flex items-center gap-2">
          <div className="bg-surface border border-border px-3 py-1.5 rounded flex items-center gap-2 text-xs font-mono">
            <Sparkles className="w-3.5 h-3.5 text-pos" />
            <span className="text-text-3">{t("narrative.active_model")}</span>
            <span className="text-text-1 font-semibold">{stats?.llm_model || "Qwen3.8-27B-Q4"}</span>
            <InfoTooltip
              title="Local LLM Inference"
              content="Runs deterministic quantized model inference locally or via API with zero external network leakage and structured JSON validation."
            />
          </div>
          <div className="bg-surface border border-border px-3 py-1.5 rounded flex items-center gap-2 text-xs font-mono">
            <ShieldCheck className="w-3.5 h-3.5 text-info" />
            <span className="text-text-3">{t("narrative.shorting_status")}</span>
            <span className={stats?.allow_short ? "text-pos font-semibold" : "text-warn font-semibold"}>
              {stats?.allow_short ? t("narrative.enabled_swing") : t("narrative.armed_spec")}
            </span>
            <InfoTooltip
              title={t("tooltips.short_selling_title")}
              content={t("tooltips.short_selling_desc")}
            />
          </div>
        </div>
      </div>

      {/* Metric Cards Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-surface border border-border rounded p-4">
          <div className="flex items-center justify-between text-text-3 text-xs font-mono mb-1">
            <div className="flex items-center">
              <span>{t("narrative.active_prompt")}</span>
              <InfoTooltip
                title={t("tooltips.prompt_version_title")}
                content={t("tooltips.prompt_version_desc")}
              />
            </div>
            <Hash className="w-3.5 h-3.5 text-text-3" />
          </div>
          <div className="text-lg font-bold font-mono text-text-1">
            {stats?.active_prompt_version || "v1.0"}{" "}
            <span className="text-[10px] text-text-3 font-normal">({stats?.active_prompt_hash || "1a7b8e39f201"})</span>
          </div>
          <div className="text-[11px] font-mono text-pos mt-1 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-pos" />
            {t("narrative.schema_enforced")}
          </div>
        </div>

        <div className="bg-surface border border-border rounded p-4">
          <div className="flex items-center justify-between text-text-3 text-xs font-mono mb-1">
            <div className="flex items-center">
              <span>{t("narrative.inference_latency")}</span>
              <InfoTooltip
                title={t("tooltips.llm_latency_title")}
                content={t("tooltips.llm_latency_desc")}
              />
            </div>
            <Clock className="w-3.5 h-3.5 text-text-3" />
          </div>
          <div className="text-lg font-bold font-mono text-text-1">
            {stats?.p95_latency_ms || 480} ms
          </div>
          <div className="text-[11px] font-mono text-text-3 mt-1">
            {t("narrative.avg_latency_sub")}: {stats?.avg_latency_ms || 300} ms (&lt; 5000ms)
          </div>
        </div>

        <div className="bg-surface border border-border rounded p-4">
          <div className="flex items-center justify-between text-text-3 text-xs font-mono mb-1">
            <div className="flex items-center">
              <span>{t("narrative.articles_scored")}</span>
              <InfoTooltip
                title={t("tooltips.narrative_coverage_title")}
                content={t("tooltips.narrative_coverage_desc")}
              />
            </div>
            <FileText className="w-3.5 h-3.5 text-text-3" />
          </div>
          <div className="text-lg font-bold font-mono text-text-1">
            {stats?.scored_articles || 12}
          </div>
          <div className="text-[11px] font-mono text-text-3 mt-1">
            {t("narrative.zero_dup_hashing")}
          </div>
        </div>

        <div className="bg-surface border border-border rounded p-4">
          <div className="flex items-center justify-between text-text-3 text-xs font-mono mb-1">
            <div className="flex items-center">
              <span>{t("narrative.borrow_cost")}</span>
              <InfoTooltip
                title={t("tooltips.short_borrow_title")}
                content={t("tooltips.short_borrow_desc")}
              />
            </div>
            <Lock className="w-3.5 h-3.5 text-text-3" />
          </div>
          <div className="text-lg font-bold font-mono text-pos">
            3.0% <span className="text-xs font-normal text-text-3">{t("narrative.annualized_lbl")}</span>
          </div>
          <div className="text-[11px] font-mono text-text-3 mt-1">
            {t("narrative.daily_rate_sub")}
          </div>
        </div>
      </div>

      {/* Middle Grid: Symbol Narrative Radar & On-Demand Scoring */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Symbol Narrative Radar */}
        <div className="lg:col-span-2 bg-surface border border-border rounded p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border pb-3">
            <div className="flex items-center gap-2">
              <BarChart2 className="w-4 h-4 text-pos" />
              <h2 className="text-sm font-bold font-mono text-text-1">
                {t("narrative.profile_momentum_title")}
              </h2>
              <InfoTooltip
                title={t("tooltips.narrative_momentum_title")}
                content={t("tooltips.narrative_momentum_desc")}
              />
            </div>

            {/* Symbol Ticker Pills */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
              {["NVDA", "AAPL", "MSFT", "TSLA", "SPY"].map((sym) => (
                <button
                  key={sym}
                  onClick={() => setSelectedSymbol(sym)}
                  className={`px-2.5 py-1 rounded text-xs font-mono transition-all ${
                    selectedSymbol === sym
                      ? "bg-pos text-bg font-bold shadow-sm"
                      : "bg-surface-2 text-text-2 hover:text-text-1 border border-border"
                  }`}
                >
                  {sym}
                </button>
              ))}
            </div>
          </div>

          {symbolSentiment ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="bg-surface-2/60 border border-border rounded p-3">
                  <div className="text-[11px] font-mono text-text-3 flex items-center">
                    <span>{t("narrative.sentiment_24h")}</span>
                    <InfoTooltip
                      title={t("tooltips.decayed_sentiment_title")}
                      content={t("tooltips.decayed_sentiment_desc")}
                    />
                  </div>
                  <div className={`text-xl font-bold font-mono mt-1 ${sentimentColor(symbolSentiment.composite_sentiment)}`}>
                    {symbolSentiment.composite_sentiment > 0 ? "+" : ""}
                    {symbolSentiment.composite_sentiment.toFixed(2)}
                  </div>
                  <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-mono mt-1 border ${sentimentBg(symbolSentiment.composite_sentiment)}`}>
                    {symbolSentiment.sentiment_label}
                  </span>
                </div>

                <div className="bg-surface-2/60 border border-border rounded p-3">
                  <div className="text-[11px] font-mono text-text-3 flex items-center">
                    <span>{t("narrative.momentum_delta")}</span>
                    <InfoTooltip
                      title={t("tooltips.narrative_momentum_title")}
                      content={t("tooltips.narrative_momentum_desc")}
                    />
                  </div>
                  <div className={`text-xl font-bold font-mono mt-1 flex items-center gap-1 ${sentimentColor(symbolSentiment.narrative_momentum)}`}>
                    {symbolSentiment.narrative_momentum >= 0 ? (
                      <TrendingUp className="w-4 h-4 text-pos" />
                    ) : (
                      <TrendingDown className="w-4 h-4 text-neg" />
                    )}
                    {symbolSentiment.narrative_momentum > 0 ? "+" : ""}
                    {symbolSentiment.narrative_momentum.toFixed(2)}
                  </div>
                  <span className="text-[10px] font-mono text-text-3 mt-1 block">
                    {t("narrative.velocity_vs_72h")}
                  </span>
                </div>

                <div className="bg-surface-2/60 border border-border rounded p-3">
                  <div className="text-[11px] font-mono text-text-3">{t("narrative.coverage_density")}</div>
                  <div className="text-xl font-bold font-mono text-text-1 mt-1">
                    {symbolSentiment.article_count_24h}{" "}
                    <span className="text-xs font-normal text-text-3">/ 24h</span>
                  </div>
                  <span className="text-[10px] font-mono text-text-3 mt-1 block">
                    {symbolSentiment.article_count_72h} {t("narrative.in_last_72h")}
                  </span>
                </div>

                <div className="bg-surface-2/60 border border-border rounded p-3">
                  <div className="text-[11px] font-mono text-text-3">{t("narrative.impact_ratio")}</div>
                  <div className="flex items-center gap-2 mt-2">
                    <span className="text-xs font-mono text-pos font-semibold">{symbolSentiment.bullish_count} {t("narrative.bull_count_lbl")}</span>
                    <span className="text-text-3 text-xs">/</span>
                    <span className="text-xs font-mono text-neg font-semibold">{symbolSentiment.bearish_count} {t("narrative.bear_count_lbl")}</span>
                  </div>
                  <div className="w-full bg-surface-2 h-1.5 rounded-full mt-2 overflow-hidden flex">
                    <div
                      className="bg-pos h-full"
                      style={{
                        width: `${
                          (symbolSentiment.bullish_count /
                            Math.max(1, symbolSentiment.bullish_count + symbolSentiment.bearish_count)) *
                          100
                        }%`,
                      }}
                    />
                    <div
                      className="bg-neg h-full"
                      style={{
                        width: `${
                          (symbolSentiment.bearish_count /
                            Math.max(1, symbolSentiment.bullish_count + symbolSentiment.bearish_count)) *
                          100
                        }%`,
                      }}
                    />
                  </div>
                </div>
              </div>

              {/* Latest Institutional Catalyst Rationale */}
              <div className="bg-surface-2 border border-border rounded p-3.5 space-y-1.5">
                <div className="flex items-center gap-1.5 text-xs font-mono text-pos font-semibold">
                  <Sparkles className="w-3.5 h-3.5" />
                  {t("narrative.latest_catalyst_title")}
                </div>
                <p className="text-xs font-mono text-text-1 leading-relaxed">
                  {symbolSentiment.latest_catalyst}
                </p>
              </div>
            </div>
          ) : (
            <div className="p-8 text-center text-xs font-mono text-text-3">
              {t("narrative.loading_narrative_for")} {selectedSymbol}...
            </div>
          )}
        </div>

        {/* Right 1 Col: On-Demand LLM Scoring Sandbox */}
        <div className="bg-surface border border-border rounded p-5 space-y-4">
          <div className="flex items-center gap-2 border-b border-border pb-3">
            <Zap className="w-4 h-4 text-pos" />
            <h2 className="text-sm font-bold font-mono text-text-1">
              {t("narrative.sandbox_title")}
            </h2>
            <InfoTooltip
              title={t("tooltips.interactive_scoring_title")}
              content={t("tooltips.interactive_scoring_desc")}
            />
          </div>

          <form onSubmit={handleTestScore} className="space-y-3">
            <div>
              <label className="text-[11px] font-mono text-text-3 block mb-1">{t("narrative.target_symbol")}</label>
              <input
                type="text"
                value={customSymbol}
                onChange={(e) => setCustomSymbol(e.target.value.toUpperCase())}
                placeholder={t("narrative.symbol_placeholder")}
                className="w-full bg-surface-2 border border-border rounded px-3 py-1.5 text-xs font-mono text-text-1 focus:outline-none focus:border-pos"
              />
            </div>

            <div>
              <label className="text-[11px] font-mono text-text-3 block mb-1">{t("narrative.headline")}</label>
              <input
                type="text"
                value={customTitle}
                onChange={(e) => setCustomTitle(e.target.value)}
                placeholder={t("narrative.headline_placeholder")}
                className="w-full bg-surface-2 border border-border rounded px-3 py-1.5 text-xs font-mono text-text-1 focus:outline-none focus:border-pos"
              />
            </div>

            <div>
              <label className="text-[11px] font-mono text-text-3 block mb-1">{t("narrative.summary_text")}</label>
              <textarea
                value={customSummary}
                onChange={(e) => setCustomSummary(e.target.value)}
                rows={3}
                placeholder={t("narrative.summary_placeholder")}
                className="w-full bg-surface-2 border border-border rounded px-3 py-1.5 text-xs font-mono text-text-1 focus:outline-none focus:border-pos resize-none"
              />
            </div>

            <button
              type="submit"
              disabled={scoringLoading || !customTitle || !customSummary}
              className="w-full bg-pos hover:bg-pos/90 disabled:opacity-50 text-bg font-bold font-mono text-xs py-2 rounded transition-all flex items-center justify-center gap-2"
            >
              {scoringLoading ? (
                <>
                  <Sparkles className="w-3.5 h-3.5 animate-spin" />
                  {t("narrative.inferencing")}
                </>
              ) : (
                <>
                  <Send className="w-3.5 h-3.5" />
                  {t("narrative.score_with_llm")}
                </>
              )}
            </button>
          </form>

          {testScoreResult && (
            <div className="bg-surface-2 border border-pos/40 rounded p-3 space-y-2 mt-3 animate-in fade-in">
              <div className="flex items-center justify-between">
                <span className={`px-2 py-0.5 rounded text-[10px] font-mono border ${sentimentBg(testScoreResult.sentiment_score)}`}>
                  {testScoreResult.impact} ({testScoreResult.sentiment_score > 0 ? "+" : ""}{testScoreResult.sentiment_score.toFixed(2)})
                </span>
                <span className="text-[10px] font-mono text-text-3">
                  {testScoreResult.latency_ms} ms
                </span>
              </div>
              <p className="text-[11px] font-mono text-text-1 leading-relaxed">
                {testScoreResult.rationale}
              </p>
              <div className="grid grid-cols-3 gap-1 pt-1 border-t border-border text-[10px] font-mono text-text-3">
                <div>{t("narrative.rel_lbl")}: {testScoreResult.relevance_score.toFixed(2)}</div>
                <div>{t("narrative.nov_lbl")}: {testScoreResult.novelty_score.toFixed(2)}</div>
                <div>{t("narrative.conf_lbl")}: {testScoreResult.confidence.toFixed(2)}</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Bottom Grid: Institutional News Feed & Article Detail Drawer */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Ingested News Feed */}
        <div className="lg:col-span-2 bg-surface border border-border rounded p-5 space-y-3">
          <div className="flex items-center justify-between border-b border-border pb-3">
            <div className="flex items-center gap-2">
              <Newspaper className="w-4 h-4 text-pos" />
              <h2 className="text-sm font-bold font-mono text-text-1">
                {t("narrative.live_feed_title")}
              </h2>
              <InfoTooltip
                title={t("tooltips.news_blotter_title")}
                content={t("tooltips.news_blotter_desc")}
              />
            </div>
            <span className="text-xs font-mono text-text-3">
              {newsFeed.length} {t("narrative.feed_articles_count")}
            </span>
          </div>

          <div className="space-y-2.5 max-h-[500px] overflow-y-auto pr-1">
            {newsFeed.map((article) => {
              const isSelected = selectedArticle?.id === article.id;
              const sc = article.score;
              return (
                <div
                  key={article.id}
                  onClick={() => setSelectedArticle(article)}
                  className={`p-3 rounded border transition-all cursor-pointer ${
                    isSelected
                      ? "bg-active border-pos/50 shadow-sm"
                      : "bg-surface-2/60 hover:bg-surface-2 border-border"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        {article.symbols.map((sym) => (
                          <span
                            key={sym}
                            className="bg-surface border border-border px-1.5 py-0.5 rounded text-[10px] font-mono text-pos font-bold"
                          >
                            {sym}
                          </span>
                        ))}
                        <span className="text-[10px] font-mono text-text-3">
                          {new Date(article.published_at).toLocaleString("en-US", {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                            timeZone: "UTC",
                          })}{" "}
                          UTC
                        </span>
                        <span className="text-[10px] font-mono text-text-3">
                          • {article.source}
                        </span>
                      </div>
                      <h3 className="text-xs font-bold font-mono text-text-1 hover:text-pos transition-colors">
                        {article.title}
                      </h3>
                      <p className="text-[11px] font-mono text-text-3 line-clamp-2">
                        {article.summary}
                      </p>
                    </div>

                    {sc && (
                      <div className="shrink-0 flex flex-col items-end gap-1">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-mono border font-semibold ${sentimentBg(
                            sc.sentiment_score
                          )}`}
                        >
                          {sc.impact} ({sc.sentiment_score > 0 ? "+" : ""}
                          {sc.sentiment_score.toFixed(2)})
                        </span>
                        <span className="text-[10px] font-mono text-text-3">
                          {sc.horizon}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right 1 Col: Selected Article LLM Rationale Drawer */}
        <div className="bg-surface border border-border rounded p-5 space-y-4">
          <div className="flex items-center gap-2 border-b border-border pb-3">
            <Sparkles className="w-4 h-4 text-pos" />
            <h2 className="text-sm font-bold font-mono text-text-1">
              {t("narrative.structured_eval_title")}
            </h2>
            <InfoTooltip
              title={t("tooltips.structured_json_title")}
              content={t("tooltips.structured_json_desc")}
            />
          </div>

          {selectedArticle ? (
            <div className="space-y-4 text-xs font-mono">
              <div>
                <div className="text-[10px] text-text-3 uppercase">{t("narrative.article_headline_lbl")}</div>
                <div className="text-text-1 font-bold mt-0.5">{selectedArticle.title}</div>
              </div>

              {selectedArticle.score ? (
                <>
                  <div className="bg-surface-2 border border-border rounded p-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-text-3 text-[11px]">{t("narrative.sentiment_impact")}</span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold border ${sentimentBg(
                          selectedArticle.score.sentiment_score
                        )}`}
                      >
                        {selectedArticle.score.impact} ({selectedArticle.score.sentiment_score.toFixed(2)})
                      </span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-text-3 text-[11px]">{t("narrative.catalyst_horizon")}</span>
                      <span className="text-text-1 font-semibold">{selectedArticle.score.horizon}</span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-text-3 text-[11px]">{t("narrative.relevance_score")}</span>
                      <span className="text-text-1 font-semibold">
                        {(selectedArticle.score.relevance_score * 100).toFixed(0)}%
                      </span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-text-3 text-[11px]">{t("narrative.novelty_score")}</span>
                      <span className="text-text-1 font-semibold">
                        {(selectedArticle.score.novelty_score * 100).toFixed(0)}%
                      </span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-text-3 text-[11px]">{t("narrative.model_confidence")}</span>
                      <span className="text-text-1 font-semibold">
                        {(selectedArticle.score.confidence * 100).toFixed(0)}%
                      </span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-text-3 text-[11px]">{t("narrative.inference_latency")}:</span>
                      <span className="text-text-1 font-semibold">{selectedArticle.score.latency_ms} ms</span>
                    </div>
                  </div>

                  <div className="space-y-1">
                    <div className="text-[10px] text-text-3 uppercase">{t("narrative.llm_rationale")}</div>
                    <div className="bg-surface-2/80 border border-border rounded p-3 text-text-1 leading-relaxed">
                      {selectedArticle.score.rationale}
                    </div>
                  </div>

                  <div className="pt-2 border-t border-border space-y-1 text-[10px] text-text-3">
                    <div className="flex justify-between">
                      <span>{t("narrative.model_lbl")}</span>
                      <span className="text-text-2">{selectedArticle.score.model_name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>{t("narrative.prompt_version")}</span>
                      <span className="text-text-2">{selectedArticle.score.prompt_version}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>{t("narrative.prompt_hash")}</span>
                      <span className="text-text-2">{selectedArticle.score.prompt_hash}</span>
                    </div>
                  </div>
                </>
              ) : (
                <div className="p-4 bg-surface-2 rounded text-center text-text-3 text-xs">
                  {t("narrative.not_yet_scored")}
                </div>
              )}
            </div>
          ) : (
            <div className="p-6 text-center text-xs font-mono text-text-3">
              {t("narrative.select_article_to_inspect")}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
