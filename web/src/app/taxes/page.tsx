"use client";

import { useEffect, useState } from "react";
import {
  Receipt,
  Download,
  Calendar,
  Percent,
  TrendingUp,
  TrendingDown,
  ShieldCheck,
  RefreshCw,
  Landmark,
  Scale,
  FileSpreadsheet,
} from "lucide-react";
import { InfoTooltip } from "@/components/Tooltip";
import { useTranslation } from "@/i18n";
import {
  AnnualTaxReportDTO,
  TaxEventDTO,
  TaxLotDTO,
  ECBRateDTO,
  fetchAnnualTaxReport,
  fetchTaxLots,
  fetchTaxEvents,
  fetchECBRates,
} from "@/lib/api";

export default function TaxesPage() {
  const { t } = useTranslation();
  const currentYear = new Date().getFullYear();

  const [selectedYear, setSelectedYear] = useState<number>(currentYear);
  const [churchTaxRate, setChurchTaxRate] = useState<number>(0.0);
  const [sparerpauschbetrag, setSparerpauschbetrag] = useState<number>(1000.0);
  const [activeTab, setActiveTab] = useState<"lots" | "events" | "ecb" | "kap">("lots");

  const [report, setReport] = useState<AnnualTaxReportDTO | null>(null);
  const [lots, setLots] = useState<TaxLotDTO[]>([]);
  const [events, setEvents] = useState<TaxEventDTO[]>([]);
  const [ecbRates, setEcbRates] = useState<ECBRateDTO[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [statusMsg, setStatusMsg] = useState<string>("");

  useEffect(() => {
    loadTaxData();
  }, [selectedYear, churchTaxRate, sparerpauschbetrag]);

  async function loadTaxData() {
    setLoading(true);
    try {
      const [repData, lotsData, eventsData, ecbData] = await Promise.all([
        fetchAnnualTaxReport(selectedYear, churchTaxRate, sparerpauschbetrag).catch(() => null),
        fetchTaxLots().catch(() => []),
        fetchTaxEvents(selectedYear).catch(() => []),
        fetchECBRates(15).catch(() => []),
      ]);
      setReport(repData);
      setLots(lotsData || []);
      setEvents(eventsData || []);
      setEcbRates(ecbData || []);
    } catch (err) {
      console.error("Failed to load tax data:", err);
    } finally {
      setLoading(false);
    }
  }

  function exportCSV() {
    if (!events.length) return;
    const headers = [
      "ID",
      "Symbol",
      "Category",
      "SellDate",
      "Quantity",
      "CostBasisEUR",
      "ProceedsEUR",
      "GainLossEUR",
      "KEStEUR",
      "SoliEUR",
      "TotalTaxEUR",
    ];
    const rows = events.map((e) => [
      e.id,
      e.symbol,
      e.asset_category,
      e.sell_date,
      e.quantity,
      e.cost_basis_eur.toFixed(2),
      e.proceeds_eur.toFixed(2),
      e.gain_loss_eur.toFixed(2),
      e.kest_amount_eur.toFixed(2),
      e.soli_amount_eur.toFixed(2),
      e.total_tax_eur.toFixed(2),
    ]);
    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `atlas_tax_report_${selectedYear}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setStatusMsg(`Downloaded tax CSV for ${selectedYear}`);
    setTimeout(() => setStatusMsg(""), 3000);
  }

  function exportJSON() {
    if (!report) return;
    const jsonStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify({ report, events, lots }, null, 2));
    const link = document.createElement("a");
    link.setAttribute("href", jsonStr);
    link.setAttribute("download", `atlas_tax_declaration_${selectedYear}.json`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setStatusMsg(`Downloaded JSON tax filing report for ${selectedYear}`);
    setTimeout(() => setStatusMsg(""), 3000);
  }

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold font-mono text-text-1 flex items-center gap-2">
              <Receipt className="w-5 h-5 text-pos" />
              {t("taxes.page_title")}
            </h1>
            <InfoTooltip content={t("taxes.page_subtitle")} />
          </div>
          <p className="text-xs text-text-3 font-mono mt-0.5">{t("taxes.page_subtitle")}</p>
        </div>

        {/* Controls & Export */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Year Selector */}
          <div className="flex items-center gap-1.5 bg-surface-2 border border-border px-2.5 py-1.5 rounded">
            <Calendar className="w-3.5 h-3.5 text-text-3" />
            <span className="text-[11px] font-mono text-text-3">{t("taxes.tax_year_label")}:</span>
            <select
              value={selectedYear}
              onChange={(e) => setSelectedYear(Number(e.target.value))}
              className="bg-surface text-text-1 text-xs font-mono px-1.5 py-0.5 rounded border border-border focus:outline-none"
            >
              <option value={2026}>2026</option>
              <option value={2025}>2025</option>
              <option value={2024}>2024</option>
            </select>
          </div>

          {/* Church Tax Selector */}
          <div className="flex items-center gap-1.5 bg-surface-2 border border-border px-2.5 py-1.5 rounded">
            <Landmark className="w-3.5 h-3.5 text-text-3" />
            <span className="text-[11px] font-mono text-text-3">Kirchensteuer:</span>
            <select
              value={churchTaxRate}
              onChange={(e) => setChurchTaxRate(Number(e.target.value))}
              className="bg-surface text-text-1 text-xs font-mono px-1.5 py-0.5 rounded border border-border focus:outline-none"
            >
              <option value={0.0}>0% (Keine)</option>
              <option value={0.08}>8% (BY / BW)</option>
              <option value={0.09}>9% (Übrige)</option>
            </select>
          </div>

          {/* Action Buttons */}
          <button
            onClick={exportCSV}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-surface border border-border hover:bg-surface-2 text-text-1 text-xs font-mono font-medium transition-all"
          >
            <Download className="w-3.5 h-3.5 text-pos" />
            <span>{t("taxes.export_csv")}</span>
          </button>
          <button
            onClick={exportJSON}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-surface border border-border hover:bg-surface-2 text-text-1 text-xs font-mono font-medium transition-all"
          >
            <FileSpreadsheet className="w-3.5 h-3.5 text-pos" />
            <span>{t("taxes.export_json")}</span>
          </button>
        </div>
      </div>

      {statusMsg && (
        <div className="p-2.5 rounded bg-pos/10 border border-pos/40 text-pos text-xs font-mono flex items-center gap-2">
          <ShieldCheck className="w-4 h-4" />
          <span>{statusMsg}</span>
        </div>
      )}

      {/* Main KPI Summary Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Tax Liability */}
        <div className="bg-surface border border-border rounded p-3.5 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-text-3">{t("taxes.total_tax_liability")}</span>
            <InfoTooltip content="Total statutory withholding: KESt (25%) + Solidaritätszuschlag (5.5% of KESt = 1.375%) + optional Kirchensteuer." />
          </div>
          <div className="mt-2 text-xl font-bold font-mono text-neg">
            €{report ? report.total_tax_liability_eur.toLocaleString("de-DE", { minimumFractionDigits: 2 }) : "0,00"}
          </div>
          <div className="text-[10px] font-mono text-text-3 mt-1 flex justify-between">
            <span>KESt: €{report ? report.total_kest_eur.toFixed(2) : "0.00"}</span>
            <span>Soli: €{report ? report.total_soli_eur.toFixed(2) : "0.00"}</span>
          </div>
        </div>

        {/* Net Taxable Capital Income */}
        <div className="bg-surface border border-border rounded p-3.5 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-text-3">{t("taxes.net_taxable")}</span>
            <InfoTooltip content="Realized capital gains after offsetting allowable losses and subtracting Sparerpauschbetrag allowance." />
          </div>
          <div className="mt-2 text-xl font-bold font-mono text-pos">
            €{report ? report.net_taxable_income_eur.toLocaleString("de-DE", { minimumFractionDigits: 2 }) : "0,00"}
          </div>
          <div className="text-[10px] font-mono text-text-3 mt-1">
            Gains: +€{report ? report.total_realized_gains_eur.toFixed(2) : "0.00"} · Losses: -€{report ? report.total_realized_losses_eur.toFixed(2) : "0.00"}
          </div>
        </div>

        {/* Effective Tax Rate */}
        <div className="bg-surface border border-border rounded p-3.5 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-text-3">{t("taxes.effective_rate")}</span>
            <InfoTooltip content="Effective percentage of net taxable capital gains paid in taxes (statutory rate 26.375%)." />
          </div>
          <div className="mt-2 text-xl font-bold font-mono text-text-1">
            {report && report.net_taxable_income_eur > 0 ? `${report.effective_tax_rate_pct.toFixed(2)}%` : "0.00%"}
          </div>
          <div className="text-[10px] font-mono text-text-3 mt-1">
            Statutory rate: 26.375% (KESt + Soli)
          </div>
        </div>

        {/* Sparerpauschbetrag Gauge */}
        <div className="bg-surface border border-border rounded p-3.5 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-text-3">{t("taxes.sparerpauschbetrag")}</span>
            <InfoTooltip content={t("taxes.sparerpauschbetrag_desc")} />
          </div>
          <div className="mt-2 text-xl font-bold font-mono text-text-1">
            €{report ? report.sparerpauschbetrag_used_eur.toFixed(2) : "0.00"} <span className="text-xs font-normal text-text-3">/ €{sparerpauschbetrag.toFixed(0)}</span>
          </div>
          <div className="w-full bg-surface-2 rounded-full h-1.5 mt-1 overflow-hidden">
            <div
              className="bg-pos h-full transition-all"
              style={{
                width: `${report ? Math.min(100, (report.sparerpauschbetrag_used_eur / sparerpauschbetrag) * 100) : 0}%`,
              }}
            />
          </div>
        </div>
      </div>

      {/* Loss Offset Pots (§ 20 Abs. 6 EStG) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Aktientopf */}
        <div className="bg-surface border border-border rounded p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-border pb-2">
            <div className="flex items-center gap-2">
              <Scale className="w-4 h-4 text-pos" />
              <span className="text-xs font-bold font-mono text-text-1">{t("taxes.aktien_pot")}</span>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-surface-2 text-text-3">§ 20 Abs. 6 Satz 4 EStG</span>
          </div>
          <p className="text-[11px] font-mono text-text-3">{t("taxes.aktien_pot_desc")}</p>
          <div className="grid grid-cols-3 gap-2 pt-1 font-mono text-xs">
            <div className="p-2 rounded bg-surface-2">
              <div className="text-[10px] text-text-3">{t("taxes.realized_gains")}</div>
              <div className="font-bold text-pos mt-0.5">+€{report ? report.aktien_gains_eur.toFixed(2) : "0.00"}</div>
            </div>
            <div className="p-2 rounded bg-surface-2">
              <div className="text-[10px] text-text-3">{t("taxes.realized_losses")}</div>
              <div className="font-bold text-neg mt-0.5">-€{report ? report.aktien_losses_eur.toFixed(2) : "0.00"}</div>
            </div>
            <div className="p-2 rounded bg-surface-2">
              <div className="text-[10px] text-text-3">{t("taxes.loss_carryforward")}</div>
              <div className="font-bold text-text-1 mt-0.5">€{report ? report.aktien_loss_carryforward_eur.toFixed(2) : "0.00"}</div>
            </div>
          </div>
        </div>

        {/* Sonstiger Topf */}
        <div className="bg-surface border border-border rounded p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-border pb-2">
            <div className="flex items-center gap-2">
              <Scale className="w-4 h-4 text-pos" />
              <span className="text-xs font-bold font-mono text-text-1">{t("taxes.sonstige_pot")}</span>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-surface-2 text-text-3">§ 20 Abs. 6 Satz 1 EStG</span>
          </div>
          <p className="text-[11px] font-mono text-text-3">{t("taxes.sonstige_pot_desc")}</p>
          <div className="grid grid-cols-3 gap-2 pt-1 font-mono text-xs">
            <div className="p-2 rounded bg-surface-2">
              <div className="text-[10px] text-text-3">{t("taxes.realized_gains")}</div>
              <div className="font-bold text-pos mt-0.5">+€{report ? report.sonstige_gains_eur.toFixed(2) : "0.00"}</div>
            </div>
            <div className="p-2 rounded bg-surface-2">
              <div className="text-[10px] text-text-3">{t("taxes.realized_losses")}</div>
              <div className="font-bold text-neg mt-0.5">-€{report ? report.sonstige_losses_eur.toFixed(2) : "0.00"}</div>
            </div>
            <div className="p-2 rounded bg-surface-2">
              <div className="text-[10px] text-text-3">{t("taxes.loss_carryforward")}</div>
              <div className="font-bold text-text-1 mt-0.5">€{report ? report.sonstige_loss_carryforward_eur.toFixed(2) : "0.00"}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="border-b border-border flex gap-2">
        <button
          onClick={() => setActiveTab("lots")}
          className={`px-3 py-2 text-xs font-mono font-medium border-b-2 transition-all ${
            activeTab === "lots"
              ? "border-pos text-pos font-bold bg-surface-2"
              : "border-transparent text-text-3 hover:text-text-1"
          }`}
        >
          {t("taxes.tax_lots_title")} ({lots.length})
        </button>
        <button
          onClick={() => setActiveTab("events")}
          className={`px-3 py-2 text-xs font-mono font-medium border-b-2 transition-all ${
            activeTab === "events"
              ? "border-pos text-pos font-bold bg-surface-2"
              : "border-transparent text-text-3 hover:text-text-1"
          }`}
        >
          {t("taxes.tax_events_title")} ({events.length})
        </button>
        <button
          onClick={() => setActiveTab("ecb")}
          className={`px-3 py-2 text-xs font-mono font-medium border-b-2 transition-all ${
            activeTab === "ecb"
              ? "border-pos text-pos font-bold bg-surface-2"
              : "border-transparent text-text-3 hover:text-text-1"
          }`}
        >
          EZB Wechselkurse ({ecbRates.length})
        </button>
        <button
          onClick={() => setActiveTab("kap")}
          className={`px-3 py-2 text-xs font-mono font-medium border-b-2 transition-all ${
            activeTab === "kap"
              ? "border-pos text-pos font-bold bg-surface-2"
              : "border-transparent text-text-3 hover:text-text-1"
          }`}
        >
          {t("taxes.anlage_kap_title")}
        </button>
      </div>

      {/* Tab 1: FIFO Tax Lots */}
      {activeTab === "lots" && (
        <div className="bg-surface border border-border rounded overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse font-mono text-xs">
              <thead>
                <tr className="bg-surface-2 border-b border-border text-text-3 text-[11px]">
                  <th className="py-2.5 px-3">{t("taxes.col_lot_id")}</th>
                  <th className="py-2.5 px-3">{t("common.symbol")}</th>
                  <th className="py-2.5 px-3">{t("taxes.col_buy_date")}</th>
                  <th className="py-2.5 px-3 text-right">{t("common.qty")}</th>
                  <th className="py-2.5 px-3 text-right">{t("taxes.col_buy_price_usd")}</th>
                  <th className="py-2.5 px-3 text-right">{t("taxes.col_fx_rate")}</th>
                  <th className="py-2.5 px-3 text-right">{t("taxes.col_buy_price_eur")}</th>
                  <th className="py-2.5 px-3 text-right">{t("taxes.col_total_cost_eur")}</th>
                  <th className="py-2.5 px-3 text-center">{t("taxes.col_status")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {lots.map((lot) => (
                  <tr key={lot.id} className="hover:bg-surface-2/50 transition-colors">
                    <td className="py-2.5 px-3 text-text-3 font-mono">{lot.id}</td>
                    <td className="py-2.5 px-3 font-bold text-text-1">{lot.symbol}</td>
                    <td className="py-2.5 px-3 text-text-2">{lot.buy_date}</td>
                    <td className="py-2.5 px-3 text-right text-text-1">{lot.quantity_remaining} / {lot.quantity_initial}</td>
                    <td className="py-2.5 px-3 text-right text-text-2">${lot.buy_price_usd.toFixed(2)}</td>
                    <td className="py-2.5 px-3 text-right text-text-3">{lot.buy_fx_rate_eur_usd.toFixed(4)}</td>
                    <td className="py-2.5 px-3 text-right font-medium text-text-1">€{lot.buy_price_eur.toFixed(2)}</td>
                    <td className="py-2.5 px-3 text-right font-bold text-text-1">€{lot.total_cost_eur.toFixed(2)}</td>
                    <td className="py-2.5 px-3 text-center">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                          lot.status === "OPEN"
                            ? "bg-pos/15 text-pos border border-pos/30"
                            : "bg-surface-2 text-text-3"
                        }`}
                      >
                        {lot.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 2: Taxable Disposition Events */}
      {activeTab === "events" && (
        <div className="bg-surface border border-border rounded overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse font-mono text-xs">
              <thead>
                <tr className="bg-surface-2 border-b border-border text-text-3 text-[11px]">
                  <th className="py-2.5 px-3">{t("common.symbol")}</th>
                  <th className="py-2.5 px-3">{t("taxes.col_sell_date")}</th>
                  <th className="py-2.5 px-3 text-right">{t("common.qty")}</th>
                  <th className="py-2.5 px-3 text-right">{t("taxes.col_buy_price_eur")}</th>
                  <th className="py-2.5 px-3 text-right">{t("taxes.col_sell_price_eur")}</th>
                  <th className="py-2.5 px-3 text-right">{t("taxes.col_proceeds_eur")}</th>
                  <th className="py-2.5 px-3 text-right">{t("taxes.col_gain_loss_eur")}</th>
                  <th className="py-2.5 px-3 text-right">{t("taxes.col_kest")}</th>
                  <th className="py-2.5 px-3 text-right">{t("taxes.col_soli")}</th>
                  <th className="py-2.5 px-3 text-right">{t("taxes.col_total_tax")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {events.map((ev) => (
                  <tr key={ev.id} className="hover:bg-surface-2/50 transition-colors">
                    <td className="py-2.5 px-3 font-bold text-text-1">{ev.symbol}</td>
                    <td className="py-2.5 px-3 text-text-2">{ev.sell_date}</td>
                    <td className="py-2.5 px-3 text-right text-text-1">{ev.quantity}</td>
                    <td className="py-2.5 px-3 text-right text-text-2">€{ev.buy_price_eur.toFixed(2)}</td>
                    <td className="py-2.5 px-3 text-right text-text-2">€{ev.sell_price_eur.toFixed(2)}</td>
                    <td className="py-2.5 px-3 text-right font-medium text-text-1">€{ev.proceeds_eur.toFixed(2)}</td>
                    <td className={`py-2.5 px-3 text-right font-bold ${ev.is_gain ? "text-pos" : "text-neg"}`}>
                      {ev.gain_loss_eur >= 0 ? `+€${ev.gain_loss_eur.toFixed(2)}` : `-€${Math.abs(ev.gain_loss_eur).toFixed(2)}`}
                    </td>
                    <td className="py-2.5 px-3 text-right text-text-2">€{ev.kest_amount_eur.toFixed(2)}</td>
                    <td className="py-2.5 px-3 text-right text-text-3">€{ev.soli_amount_eur.toFixed(2)}</td>
                    <td className="py-2.5 px-3 text-right font-bold text-neg">€{ev.total_tax_eur.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 3: ECB Reference Rates */}
      {activeTab === "ecb" && (
        <div className="bg-surface border border-border rounded overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse font-mono text-xs">
              <thead>
                <tr className="bg-surface-2 border-b border-border text-text-3 text-[11px]">
                  <th className="py-2.5 px-3">{t("common.date")}</th>
                  <th className="py-2.5 px-3">Base Currency</th>
                  <th className="py-2.5 px-3">Target Currency</th>
                  <th className="py-2.5 px-3 text-right">ECB Reference Rate</th>
                  <th className="py-2.5 px-3 text-right">Inversion (EUR per USD)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {ecbRates.map((r, i) => (
                  <tr key={i} className="hover:bg-surface-2/50 transition-colors">
                    <td className="py-2.5 px-3 font-medium text-text-1">{r.rate_date}</td>
                    <td className="py-2.5 px-3 text-text-2">{r.base_currency}</td>
                    <td className="py-2.5 px-3 text-text-2">{r.target_currency}</td>
                    <td className="py-2.5 px-3 text-right font-bold text-text-1">{r.rate.toFixed(4)} USD</td>
                    <td className="py-2.5 px-3 text-right text-text-3">€{(1.0 / r.rate).toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 4: Anlage KAP Declaration Form Mapping */}
      {activeTab === "kap" && (
        <div className="bg-surface border border-border rounded p-4 space-y-4 font-mono text-xs">
          <div className="border-b border-border pb-3">
            <h3 className="text-sm font-bold text-text-1 flex items-center gap-2">
              <FileSpreadsheet className="w-4 h-4 text-pos" />
              Einkommensteuererklärung — Anlage KAP Formularzuordnung ({selectedYear})
            </h3>
            <p className="text-[11px] text-text-3 mt-0.5">
              Direkte Zuordnung der ermittelten Beträge zu den offiziellen Zeilen der Anlage KAP (§ 20 EStG).
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="p-3 rounded bg-surface-2 border border-border space-y-1">
              <div className="text-[10px] text-text-3">Zeile 18 (Inländische/Ausländische Kapitalerträge)</div>
              <div className="text-base font-bold text-pos">
                €{report ? report.total_realized_gains_eur.toFixed(2) : "0.00"}
              </div>
              <div className="text-[10px] text-text-3">Summe aller realisierten Bruttogewinne aus Aktien und ETFs</div>
            </div>

            <div className="p-3 rounded bg-surface-2 border border-border space-y-1">
              <div className="text-[10px] text-text-3">Zeile 19 (Gewinne aus Aktienveräußerungen)</div>
              <div className="text-base font-bold text-pos">
                €{report ? report.aktien_gains_eur.toFixed(2) : "0.00"}
              </div>
              <div className="text-[10px] text-text-3">Darin enthaltene Veräußerungsgewinne aus Aktien</div>
            </div>

            <div className="p-3 rounded bg-surface-2 border border-border space-y-1">
              <div className="text-[10px] text-text-3">Zeile 20 (Veräußerungsverluste ohne Aktien)</div>
              <div className="text-base font-bold text-neg">
                €{report ? report.sonstige_losses_eur.toFixed(2) : "0.00"}
              </div>
              <div className="text-[10px] text-text-3">Verluste aus ETFs, Fonds und Derivaten</div>
            </div>

            <div className="p-3 rounded bg-surface-2 border border-border space-y-1">
              <div className="text-[10px] text-text-3">Zeile 23 (Veräußerungsverluste aus Aktien)</div>
              <div className="text-base font-bold text-neg">
                €{report ? report.aktien_losses_eur.toFixed(2) : "0.00"}
              </div>
              <div className="text-[10px] text-text-3">Strikter Aktientopf-Verlustvortrag (§ 20 Abs. 6 Satz 4 EStG)</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
