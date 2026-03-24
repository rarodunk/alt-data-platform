"use client";

import { BacktestPoint, ModelMetrics } from "@/lib/types";
import ActualVsPredicted from "@/components/charts/ActualVsPredicted";
import ErrorChart from "@/components/charts/ErrorChart";

interface Props {
  metricName: string;
  metricLabel: string;
  unit: string;
  backtestResults: BacktestPoint[];
  modelMetrics: ModelMetrics | null;
}

function MetricCard({
  label,
  value,
  sublabel,
  color,
}: {
  label: string;
  value: string;
  sublabel?: string;
  color?: string;
}) {
  return (
    <div className="bg-slate-900 rounded-lg p-4 text-center">
      <p className="text-slate-400 text-xs uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-xl font-bold ${color ?? "text-white"}`}>{value}</p>
      {sublabel && <p className="text-slate-500 text-xs mt-1">{sublabel}</p>}
    </div>
  );
}

function dirColor(v: number | null): string {
  if (v == null) return "text-white";
  if (v >= 70) return "text-emerald-400";
  if (v >= 50) return "text-amber-400";
  return "text-red-400";
}

function mapeColor(v: number | null): string {
  if (v == null) return "text-white";
  if (v < 5) return "text-emerald-400";
  if (v < 15) return "text-amber-400";
  return "text-red-400";
}

export default function BacktestSection({
  metricName,
  metricLabel,
  unit,
  backtestResults,
  modelMetrics,
}: Props) {
  const filteredResults = backtestResults.filter(
    (r) => r.metric_name === metricName
  );

  // Build chart data
  const chartData = filteredResults.map((r) => ({
    quarter: r.quarter,
    actual: r.actual_value,
    predicted: r.predicted_value,
  }));

  const errorData = filteredResults.map((r) => ({
    quarter: r.quarter,
    pct_error: r.pct_error,
  }));

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-white font-semibold text-lg">Backtest Performance</h2>
        {modelMetrics?.run_at && (
          <span className="text-slate-500 text-xs">
            Last run: {new Date(modelMetrics.run_at).toLocaleDateString()}
          </span>
        )}
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <MetricCard
          label="MAE"
          value={modelMetrics?.mae != null ? modelMetrics.mae.toFixed(2) : "—"}
          sublabel={unit ? `${unit} avg abs error` : "avg abs error"}
        />
        <MetricCard
          label="MAPE"
          value={modelMetrics?.mape != null ? `${modelMetrics.mape.toFixed(1)}%` : "—"}
          sublabel="mean abs % error"
          color={mapeColor(modelMetrics?.mape ?? null)}
        />
        <MetricCard
          label="RMSE"
          value={modelMetrics?.rmse != null ? modelMetrics.rmse.toFixed(2) : "—"}
          sublabel={unit ? `${unit} root mean sq error` : "root mean sq error"}
        />
        <MetricCard
          label="Directional Accuracy"
          value={
            modelMetrics?.directional_accuracy != null
              ? `${modelMetrics.directional_accuracy.toFixed(0)}%`
              : "—"
          }
          sublabel={`${modelMetrics?.n_quarters ?? filteredResults.length} quarters`}
          color={dirColor(modelMetrics?.directional_accuracy ?? null)}
        />
      </div>

      {/* Actual vs Predicted chart */}
      <div className="mb-2">
        <p className="text-slate-400 text-xs font-medium uppercase tracking-wide mb-3">
          Actual vs Predicted — {metricLabel}
        </p>
        <ActualVsPredicted data={chartData} metricLabel={metricLabel} unit={unit} />
      </div>

      {/* Error chart */}
      <div className="mt-6">
        <p className="text-slate-400 text-xs font-medium uppercase tracking-wide mb-3">
          Forecast Error by Quarter (%)
        </p>
        <p className="text-slate-500 text-xs mb-2">
          Green &lt;5% · Yellow 5–15% · Red &gt;15%
        </p>
        <ErrorChart data={errorData} />
      </div>
    </div>
  );
}
