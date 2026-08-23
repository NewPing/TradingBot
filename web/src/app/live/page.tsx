"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Radio,
  AlertTriangle,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  ShieldAlert,
  ShieldCheck,
  Zap,
  ArrowUpRight,
  ArrowDownRight,
  Clock,
  Layers,
} from "lucide-react";
import {
  api,
  LiveState,
  LivePosition,
  LiveOrder,
  LiveFill,
  RiskStatus,
  ShadowTelemetryDTO,
  fetchShadowTelemetry,
  verifyTOTPCode,
} from "@/lib/api";
import { MetricCard } from "@/components/MetricCard";
import { InfoTooltip } from "@/components/Tooltip";
import { useTranslation } from "@/i18n";

export default function LivePaperTradingPage() {
  const { t } = useTranslation();
  const [state, setState] = useState<LiveState | null>(null);
  const [positions, setPositions] = useState<LivePosition[]>([]);
  const [orders, setOrders] = useState<LiveOrder[]>([]);
  const [fills, setFills] = useState<LiveFill[]>([]);
  const [risk, setRisk] = useState<RiskStatus | null>(null);
  const [shadow, setShadow] = useState<ShadowTelemetryDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [wsConnected, setWsConnected] = useState(false);
  const [flattening, setFlattening] = useState(false);
  const [totpModalOpen, setTotpModalOpen] = useState(false);
  const [totpCode, setTotpCode] = useState("");
  const [totpError, setTotpError] = useState("");

  const fetchData = useCallback(async () => {
    try {
      const [liveState, livePositions, liveOrders, liveFills, riskStatus, shadowData] =
        await Promise.all([
          api.getLiveState(),
          api.getLivePositions(),
          api.getLiveOrders(),
          api.getLiveFills(),
          api.getRiskStatus(),
          fetchShadowTelemetry().catch(() => null),
        ]);
      setState(liveState);
      setPositions(livePositions);
      setOrders(liveOrders);
      setFills(liveFills);
      setRisk(riskStatus);
      setShadow(shadowData);
    } catch (err) {
      console.error("Failed to fetch live data:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);

    // WebSocket connection for real-time updates
    const wsUrl = (
      process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8001/api/v1/ws/live"
    ).replace(/^http/, "ws");

    let ws: WebSocket | null = null;
    try {
      ws = new WebSocket(wsUrl);
      ws.onopen = () => {
        setWsConnected(true);
      };
      ws.onmessage = () => {
        fetchData();
      };
      ws.onclose = () => {
        setWsConnected(false);
      };
      ws.onerror = () => {
        setWsConnected(false);
      };
    } catch {
      setWsConnected(false);
    }

    return () => {
      clearInterval(interval);
      if (ws) ws.close();
    };
  }, [fetchData]);

  const handleResetKillSwitch = async (trigger: string) => {
    try {
      const updated = await api.resetKillSwitch(trigger);
      if (updated) {
        setRisk(updated);
        await fetchData();
      }
    } catch (err) {
      console.error("Reset error:", err);
    }
  };

  const handleEmergencyFlattenClick = () => {
    setTotpCode("");
    setTotpError("");
    setTotpModalOpen(true);
  };

  const handleConfirmEmergencyFlatten = async () => {
    try {
      const res = await verifyTOTPCode(totpCode, "EMERGENCY_FLATTEN");
      if (!res.valid) {
        setTotpError(t("shadow.totp_invalid") || "Invalid 2FA code");
        return;
      }
      setTotpModalOpen(false);
      setFlattening(true);
      await api.emergencyFlatten(undefined, "Operator manual dashboard action (TOTP verified)");
      await fetchData();
    } catch (err) {
      setTotpError("Verification failed");
    } finally {
      setFlattening(false);
    }
  };

  const bucketInfo: Record<string, { title: string; desc: string; horizon: string; stops: string }> = {
    CORE: {
      title: t("live.bucket_core_title"),
      desc: t("live.bucket_core_desc"),
      horizon: "1-12M",
      stops: t("live.bucket_core_stops"),
    },
    SWING: {
      title: t("live.bucket_swing_title"),
      desc: t("live.bucket_swing_desc"),
      horizon: "2-20D",
      stops: t("live.bucket_swing_stops"),
    },
    MOONSHOT: {
      title: t("live.bucket_moon_title"),
      desc: t("live.bucket_moon_desc"),
      horizon: "H-5D",
      stops: t("live.bucket_moon_stops"),
    },
    CASH: {
      title: t("live.bucket_cash_title"),
      desc: t("live.bucket_cash_desc"),
      horizon: "Cont.",
      stops: t("live.bucket_cash_stops"),
    },
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border pb-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold tracking-tight text-text-1 font-mono">
              {t("live.title")}
            </h1>
            <span className="terminal-badge border-pos/40 text-pos bg-pos/10 flex items-center gap-1.5">
              <span className={`w-1.5 h-1.5 rounded-full ${wsConnected ? "bg-pos animate-pulse" : "bg-warn"}`} />
              {wsConnected ? t("live.ws_connected") : t("live.ws_disconnected")}
            </span>
            <span className="terminal-badge border-border text-text-2 bg-surface-2 font-mono flex items-center gap-1">
              <span>{t("live.mode_alpaca_paper")}</span>
              <InfoTooltip
                title={t("tooltips.parity_title")}
                content={t("tooltips.alpaca_paper_desc")}
              />
            </span>
          </div>
          <p className="text-xs text-text-2 font-mono mt-1">
            {t("live.subtitle")}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchData}
            className="px-3 py-1.5 rounded bg-surface border border-border text-xs font-mono text-text-2 hover:text-text-1 hover:border-border transition-colors flex items-center gap-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>{t("common.refresh")}</span>
          </button>
          <button
            onClick={handleEmergencyFlattenClick}
            disabled={flattening}
            className="px-3 py-1.5 rounded bg-neg/10 border border-neg/40 text-xs font-mono text-neg hover:bg-neg/20 transition-colors flex items-center gap-1.5 font-semibold"
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>{flattening ? t("live.flattening") : t("live.emergency_flatten")}</span>
          </button>
        </div>
      </div>

      {/* Kill Switch Alert Banner */}
      {risk && risk.active_switches.length > 0 && (
        <div className="p-4 rounded border border-neg/60 bg-neg/10 space-y-3">
          <div className="flex items-center gap-2 text-neg font-mono text-xs font-semibold">
            <AlertTriangle className="w-4 h-4" />
            <span>{t("live.circuit_breaker_banner")}</span>
          </div>
          <div className="space-y-2">
            {risk.active_switches.map((sw, idx) => (
              <div
                key={idx}
                className="flex flex-col md:flex-row md:items-center justify-between gap-2 p-2.5 rounded bg-surface border border-border text-xs font-mono"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-neg font-bold">[{sw.trigger}]</span>
                    <span className="text-text-1">{sw.detail}</span>
                  </div>
                  <div className="text-[10px] text-text-3 mt-0.5">
                    {t("live.action_lbl")}: {sw.action} • {t("live.triggered_lbl")}: {new Date(sw.triggered_at).toLocaleTimeString()} • {t("live.reset_lbl")}: {sw.reset_type}
                  </div>
                </div>
                <button
                  onClick={() => handleResetKillSwitch(sw.trigger)}
                  className="px-2.5 py-1 rounded bg-surface-2 border border-border text-[11px] text-pos hover:border-pos transition-colors font-semibold self-start md:self-auto"
                >
                  {t("live.reset_switch")}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label={t("live.account_equity")}
          value={state ? `$${state.total_equity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "—"}
          subValue={state ? `${state.today_pnl >= 0 ? "+" : ""}$${state.today_pnl.toFixed(2)}` : undefined}
          direction={state ? (state.today_pnl >= 0 ? "pos" : "neg") : "neutral"}
          tooltipTitle={t("live.account_equity")}
          tooltip={t("live.subtitle")}
        />
        <MetricCard
          label={t("live.daily_pnl")}
          value={state ? `${state.today_pnl_pct >= 0 ? "+" : ""}${(state.today_pnl_pct * 100).toFixed(2)}%` : "—"}
          direction={state ? (state.today_pnl_pct >= 0 ? "pos" : "neg") : "neutral"}
          tooltipTitle={t("live.daily_pnl")}
          tooltip={t("tooltips.killswitch_desc")}
        />
        <MetricCard
          label={t("live.cash_balance")}
          value={state ? `$${state.cash.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "—"}
          subValue={t("live.buying_power")}
          tooltipTitle={t("live.cash_balance")}
          tooltip={t("tooltips.bucket_ledger_desc")}
        />
        <MetricCard
          label={t("live.risk_limits_status")}
          value={risk ? (risk.is_halted ? t("common.locked") : t("common.active")) : "—"}
          subValue={risk && risk.is_halted ? `${risk.active_switches.length} ${t("live.active_switches_count")}` : t("live.all_rules_green")}
          direction={risk ? (!risk.is_halted ? "pos" : "neg") : "neutral"}
          tooltipTitle={t("live.risk_limits_status")}
          tooltip={t("tooltips.killswitch_desc")}
        />
      </div>

      {/* Per-Bucket Sub-Account Cards */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <span className="terminal-label">{t("live.bucket_allocation")}</span>
            <InfoTooltip
              title={t("tooltips.bucket_ledger_title")}
              content={t("tooltips.bucket_ledger_desc")}
            />
          </div>
          <span className="text-[11px] font-mono text-text-3">{t("live.rebalance_bands_lbl")}</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {state?.buckets.map((b) => {
            const info = bucketInfo[b.bucket] || {
              title: b.bucket,
              desc: "",
              horizon: "—",
              stops: "—",
            };
            const allocPct = b.current_allocation_pct * 100;
            const targetPct = b.target_allocation_pct * 100;
            const isBandOk = Math.abs(allocPct - targetPct) <= 5.0;

            return (
              <div key={b.bucket} className="p-3.5 rounded bg-surface border border-border space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-bold font-mono text-text-1">{b.bucket}</span>
                    <InfoTooltip title={info.title} content={info.desc} />
                  </div>
                  <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${isBandOk ? "bg-pos/10 text-pos" : "bg-warn/10 text-warn"}`}>
                    {allocPct.toFixed(1)}% / {targetPct.toFixed(0)}%
                  </span>
                </div>

                {/* Progress bar */}
                <div className="w-full bg-surface-2 rounded-full h-1.5 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${isBandOk ? "bg-pos" : "bg-warn"}`}
                    style={{ width: `${Math.min(allocPct, 100)}%` }}
                  />
                </div>

                <div className="space-y-1.5 text-xs font-mono">
                  <div className="flex justify-between text-text-2">
                    <span>{t("live.equity_lbl")}</span>
                    <span className="text-text-1 font-semibold">${b.equity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                  </div>
                  <div className="flex justify-between text-text-2">
                    <span>{t("live.cash_lbl")}</span>
                    <span className="text-text-1">${b.cash.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                  </div>
                  <div className="flex justify-between text-text-2">
                    <span>{t("live.positions_lbl")}</span>
                    <span className="text-text-1">{b.positions_count} {t("live.open_lbl")}</span>
                  </div>
                  <div className="flex justify-between text-text-2">
                    <span>{t("live.horizon_lbl")}</span>
                    <span className="text-text-3 text-[11px]">{info.horizon}</span>
                  </div>
                  <div className="flex justify-between text-text-2">
                    <span>{t("live.stop_policy_lbl")}</span>
                    <span className="text-text-3 text-[11px]">{info.stops}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Open Positions Table */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <span className="terminal-label">{t("live.open_positions")} ({positions.length})</span>
            <InfoTooltip
              title={t("live.open_positions")}
              content={t("live.open_positions_desc")}
            />
          </div>
        </div>

        <div className="rounded border border-border bg-surface overflow-hidden">
          {positions.length === 0 ? (
            <div className="p-8 text-center text-xs font-mono text-text-3">
              {t("live.no_positions")}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="border-b border-border bg-surface-2 text-text-3 text-left">
                    <th className="p-2.5">{t("common.symbol")}</th>
                    <th className="p-2.5">
                      <span className="inline-flex items-center">
                        {t("live.col_bucket")}
                        <InfoTooltip title={t("tooltips.bucket_ledger_title")} content={t("tooltips.bucket_ledger_desc")} />
                      </span>
                    </th>
                    <th className="p-2.5 text-right">{t("common.qty")}</th>
                    <th className="p-2.5 text-right">{t("live.col_avg_cost")}</th>
                    <th className="p-2.5 text-right">{t("common.price")}</th>
                    <th className="p-2.5 text-right">{t("live.col_market_val")}</th>
                    <th className="p-2.5 text-right">{t("live.col_unrealized_pnl")}</th>
                    <th className="p-2.5 text-right">
                      <span className="inline-flex items-center justify-end w-full">
                        {t("live.col_stop")}
                        <InfoTooltip
                          title={t("tooltips.stop_loss_title")}
                          content={t("tooltips.stop_loss_desc")}
                        />
                      </span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {positions.map((p, idx) => (
                    <tr key={idx} className="hover:bg-surface-2/60 transition-colors">
                      <td className="p-2.5 font-bold text-text-1">{p.symbol}</td>
                      <td className="p-2.5 text-text-2">{p.bucket}</td>
                      <td className="p-2.5 text-right text-text-1">{p.qty.toLocaleString()}</td>
                      <td className="p-2.5 text-right text-text-2">${p.avg_price.toFixed(2)}</td>
                      <td className="p-2.5 text-right text-text-1">${p.current_price.toFixed(2)}</td>
                      <td className="p-2.5 text-right font-semibold text-text-1">
                        ${p.market_value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      <td className={`p-2.5 text-right font-semibold ${p.unrealized_pnl >= 0 ? "text-pos" : "text-neg"}`}>
                        {p.unrealized_pnl >= 0 ? "+" : ""}${p.unrealized_pnl.toFixed(2)} ({(p.unrealized_pnl_pct * 100).toFixed(2)}%)
                      </td>
                      <td className="p-2.5 text-right text-text-3">
                        {p.stop_px ? `$${p.stop_px.toFixed(2)}` : t("common.none")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Bottom Grid: Order Blotter & Execution Fills */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Order Blotter */}
        <div className="space-y-3">
          <div className="flex items-center gap-1.5">
            <span className="terminal-label">{t("live.active_orders")}</span>
            <InfoTooltip
              title={t("live.active_orders")}
              content={t("live.active_orders_desc")}
            />
          </div>

          <div className="rounded border border-border bg-surface overflow-hidden max-h-80 overflow-y-auto">
            {orders.length === 0 ? (
              <div className="p-6 text-center text-xs font-mono text-text-3">
                {t("live.no_orders")}
              </div>
            ) : (
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="border-b border-border bg-surface-2 text-text-3 text-left sticky top-0">
                    <th className="p-2">{t("common.time")}</th>
                    <th className="p-2">{t("common.symbol")}</th>
                    <th className="p-2">{t("common.side")}</th>
                    <th className="p-2 text-right">{t("common.qty")}</th>
                    <th className="p-2">{t("live.col_order_type")}</th>
                    <th className="p-2 text-right">{t("common.status")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {orders.map((o) => (
                    <tr key={o.id} className="hover:bg-surface-2/60 transition-colors">
                      <td className="p-2 text-text-3">{new Date(o.created_ts).toLocaleTimeString()}</td>
                      <td className="p-2 font-bold text-text-1">{o.symbol}</td>
                      <td className={`p-2 font-semibold ${o.side === "BUY" ? "text-pos" : "text-neg"}`}>
                        {o.side}
                      </td>
                      <td className="p-2 text-right text-text-1">{o.qty}</td>
                      <td className="p-2 text-text-2">{o.order_type}</td>
                      <td className="p-2 text-right">
                        <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                          o.status === "FILLED"
                            ? "bg-pos/10 text-pos"
                            : o.status === "REJECTED"
                            ? "bg-neg/10 text-neg"
                            : "bg-surface-2 text-text-2"
                        }`}>
                          {o.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Fills Log */}
        <div className="space-y-3">
          <div className="flex items-center gap-1.5">
            <span className="terminal-label">{t("live.recent_fills")}</span>
            <InfoTooltip
              title={t("live.recent_fills")}
              content={t("live.recent_fills_desc")}
            />
          </div>

          <div className="rounded border border-border bg-surface overflow-hidden max-h-80 overflow-y-auto">
            {fills.length === 0 ? (
              <div className="p-6 text-center text-xs font-mono text-text-3">
                {t("live.no_fills")}
              </div>
            ) : (
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="border-b border-border bg-surface-2 text-text-3 text-left sticky top-0">
                    <th className="p-2">{t("common.time")}</th>
                    <th className="p-2">{t("live.col_order_id")}</th>
                    <th className="p-2 text-right">{t("common.qty")}</th>
                    <th className="p-2 text-right">{t("common.price")}</th>
                    <th className="p-2 text-right">{t("live.col_fee")}</th>
                    <th className="p-2 text-right">{t("live.col_venue")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {fills.map((f) => (
                    <tr key={f.id} className="hover:bg-surface-2/60 transition-colors">
                      <td className="p-2 text-text-3">{new Date(f.ts).toLocaleTimeString()}</td>
                      <td className="p-2 font-mono text-text-2">{f.order_id.slice(0, 8)}...</td>
                      <td className="p-2 text-right font-semibold text-text-1">{f.qty}</td>
                      <td className="p-2 text-right font-semibold text-text-1">${f.price.toFixed(2)}</td>
                      <td className="p-2 text-right text-text-3">
                        ${(f.commission + f.fees).toFixed(2)}
                      </td>
                      <td className="p-2 text-right text-[10px] text-text-3">{f.venue}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      {/* Shadow Mode & Broker Divergence Telemetry (Phase 9) */}
      <div className="space-y-3 border-t border-border pt-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="terminal-label">{t("shadow.telemetry_title")}</span>
            <span className="terminal-badge border-pos/40 text-pos bg-pos/10 text-[10px]">IBKR Gateway / Shadow Sim</span>
            <InfoTooltip
              title={t("shadow.title")}
              content={t("tooltips.shadow_telemetry_desc")}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-surface border border-border rounded p-3">
            <div className="text-xs font-mono text-text-3">{t("shadow.mean_slippage")}</div>
            <div className="text-lg font-bold font-mono text-text-1 mt-1">
              {shadow ? `${shadow.mean_slippage_bps.toFixed(2)} bps` : "0.00 bps"}
            </div>
            <div className="text-[10px] font-mono text-text-3 mt-0.5">
              Max: {shadow ? `${shadow.max_slippage_bps.toFixed(2)} bps` : "0.00 bps"}
            </div>
          </div>

          <div className="bg-surface border border-border rounded p-3">
            <div className="text-xs font-mono text-text-3">{t("shadow.p95_slippage")}</div>
            <div className="text-lg font-bold font-mono text-text-1 mt-1">
              {shadow ? `${shadow.p95_slippage_bps.toFixed(2)} bps` : "0.00 bps"}
            </div>
            <div className="text-[10px] font-mono text-text-3 mt-0.5">
              95% of fills within this slippage
            </div>
          </div>

          <div className="bg-surface border border-border rounded p-3">
            <div className="text-xs font-mono text-text-3">{t("shadow.quote_latency")}</div>
            <div className="text-lg font-bold font-mono text-pos mt-1">
              {shadow ? `${shadow.mean_quote_latency_ms.toFixed(1)} ms` : "0.0 ms"}
            </div>
            <div className="text-[10px] font-mono text-text-3 mt-0.5">
              p95 latency: {shadow ? `${shadow.p95_quote_latency_ms.toFixed(1)} ms` : "0.0 ms"}
            </div>
          </div>

          <div className="bg-surface border border-border rounded p-3">
            <div className="text-xs font-mono text-text-3">{t("shadow.zero_or_improved")}</div>
            <div className="text-lg font-bold font-mono text-pos mt-1">
              {shadow && shadow.total_shadow_trades > 0
                ? `${((shadow.zero_or_better_trades / shadow.total_shadow_trades) * 100).toFixed(1)}%`
                : "100.0%"}
            </div>
            <div className="text-[10px] font-mono text-text-3 mt-0.5">
              {shadow ? shadow.total_shadow_trades : 0} shadow trades recorded
            </div>
          </div>
        </div>
      </div>

      {/* 2FA TOTP Modal */}
      {totpModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-surface border border-border rounded-lg shadow-2xl max-w-md w-full p-6 space-y-4 font-mono">
            <div className="flex items-center gap-3 border-b border-border pb-3 text-neg">
              <ShieldAlert className="w-5 h-5" />
              <h3 className="text-sm font-bold text-text-1">{t("shadow.totp_modal_title")}</h3>
            </div>

            <p className="text-xs text-text-2">
              {t("shadow.totp_modal_desc")}
            </p>

            <div className="space-y-2">
              <label className="text-[11px] text-text-3 block">TOTP Code (6 Digits)</label>
              <input
                type="text"
                maxLength={6}
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value)}
                placeholder="000000"
                className="w-full bg-surface-2 border border-border rounded px-3 py-2 text-center text-lg tracking-widest font-bold text-text-1 focus:outline-none focus:border-pos"
              />
              {totpError && <div className="text-xs text-neg font-bold mt-1">{totpError}</div>}
              <div className="text-[10px] text-text-3">
                Tip: Enter your Google Authenticator code or test code <span className="font-bold text-pos">000000</span> for local sandbox.
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setTotpModalOpen(false)}
                className="px-3 py-1.5 rounded bg-surface-2 hover:bg-surface border border-border text-xs text-text-2"
              >
                {t("common.cancel")}
              </button>
              <button
                onClick={handleConfirmEmergencyFlatten}
                disabled={totpCode.length < 6}
                className="px-4 py-1.5 rounded bg-neg text-white text-xs font-bold hover:bg-neg/80 disabled:opacity-50"
              >
                {t("shadow.totp_verify_btn")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
