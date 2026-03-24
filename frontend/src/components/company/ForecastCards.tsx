"use client";

import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { Prediction, ActualMetric } from "@/lib/types";

interface Props {
  metricName: string;
  metricLabel: string;
  unit: string;
  latestPrediction: Prediction | null;
  previousPrediction: Prediction | null;
  actuals: ActualMetric[];
}

function formatValue(v: number | null | undefined, unit: string): string {
  if (v == null) return "—";
  return `${v.toFixed(1)}${unit}`;
}

function GrowthBadge({ value }: { value: number | null }) {
  if (value == null) return <span className="text-slate-500 text-xs">—</span>;
  const abs = Math.abs(value);
  const isPos = value > 0;
  const isNeutral = abs < 0.5;

  return (
    <span
      className={`flex items-center gap-1 text-sm font-semibold ${
        isNeutral
          ? "text-slate-400"
          : isPos
          ? "text-emerald-400"
          : "text-red-400"
      }`}
    >
      {isNeutral ? (
        <Minus className="h-4 w-4" />
      ) : isPos ? (
        <TrendingUp className="h-4 w-4" />
      ) : (
        <TrendingDown className="h-4 w-4" />
      )}
      {isPos && "+"}
      {value.toFixed(1)}%
    </span>
  );
}

function Card({
  label,
  value,
  subValue,
  accent,
  children,
}: {
  label: string;
  value: string;
  subValue?: string;
  accent?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 flex flex-col gap-1">
      <p className="text-slate-400 text-xs font-medium uppercase tracking-wide">{label}</p>
      <p className={`text-2xl font-bold ${accent ?? "text-white"}`}>{value}</p>
      {subValue && <p className="text-slate-500 text-xs">{subValue}</p>}
      {children}
    </div>
  );
}

export default function ForecastCards({
  metricName,
  metricLabel,
  unit,
  latestPrediction,
  previousPrediction,
  actuals,
}: Props) {
  const metricActuals = actuals
    .filter((a) => a.metric_name === metricName)
    .sort((a, b) => a.period_end.localeCompare(b.period_end));

  const lastActual = metricActuals.at(-1);
  const prevActual = metricActuals.at(-2);
  const prevYearActual = metricActuals.at(-5);

  // QoQ and YoY from actuals
  const qoqActual =
    lastActual && prevActual
      ? ((lastActual.value - prevActual.value) / prevActual.value) * 100
      : null;

  const yoyActual =
    lastActual && prevYearActual
      ? ((lastActual.value - prevYearActual.value) / prevYearActual.value) * 100
      : null;

  // Implied QoQ from forecast vs last actual
  const impliedQoQ =
    latestPrediction && lastActual
      ? ((latestPrediction.predicted_value - lastActual.value) / lastActual.value) * 100
      : null;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      {/* Next Quarter Forecast */}
      <div className="bg-slate-800 border border-blue-500/40 rounded-xl p-4 flex flex-col gap-1 col-span-2 sm:col-span-1">
        <p className="text-slate-400 text-xs font-medium uppercase tracking-wide">
          Next Quarter Forecast
        </p>
        <p className="text-2xl font-bold text-blue-400">
          {latestPrediction
            ? formatValue(latestPrediction.predicted_value, unit)
            : "—"}
        </p>
        {latestPrediction && (
          <p className="text-slate-500 text-xs">
            {latestPrediction.quarter}
            {latestPrediction.confidence_lower != null &&
              latestPrediction.confidence_upper != null && (
                <span className="block">
                  CI: [{formatValue(latestPrediction.confidence_lower, unit)} –{" "}
                  {formatValue(latestPrediction.confidence_upper, unit)}]
                </span>
              )}
          </p>
        )}
      </div>

      {/* Previous Estimate */}
      <Card
        label="Previous Estimate"
        value={
          previousPrediction
            ? formatValue(previousPrediction.predicted_value, unit)
            : "—"
        }
        subValue={previousPrediction?.quarter}
      />

      {/* Last Actual */}
      <Card
        label="Last Actual"
        value={lastActual ? formatValue(lastActual.value, unit) : "—"}
        subValue={lastActual ? `${lastActual.quarter} · ${lastActual.source}` : undefined}
      />

      {/* YoY Change */}
      <Card label="YoY Change (actual)" value="">
        <GrowthBadge value={yoyActual} />
        {prevYearActual && (
          <p className="text-slate-500 text-xs">vs {prevYearActual.quarter}</p>
        )}
      </Card>

      {/* Implied QoQ */}
      <Card label="Implied QoQ (forecast)" value="">
        <GrowthBadge value={impliedQoQ} />
        {lastActual && (
          <p className="text-slate-500 text-xs">vs {lastActual.quarter} actual</p>
        )}
      </Card>
    </div>
  );
}
