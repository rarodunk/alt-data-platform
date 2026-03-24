"use client";

import { ModelMetrics } from "@/lib/types";
import FeatureImportanceChart from "@/components/charts/FeatureImportanceChart";

interface DataFreshnessItem {
  source: string;
  lastUpdated: string | null;
  records: number;
  status: "ok" | "missing" | "placeholder";
}

interface Props {
  metricName: string;
  modelMetrics: ModelMetrics | null;
  signals: Array<{ source: string; date: string; metric_name: string; value: number }>;
}

export default function ModelDiagnostics({ metricName, modelMetrics, signals }: Props) {
  // Summarize data freshness per source
  const sourceMap: Record<string, { dates: string[]; count: number }> = {};
  for (const s of signals) {
    if (!sourceMap[s.source]) sourceMap[s.source] = { dates: [], count: 0 };
    sourceMap[s.source].dates.push(s.date);
    sourceMap[s.source].count++;
  }

  const freshnessItems: DataFreshnessItem[] = Object.entries(sourceMap).map(
    ([source, info]) => {
      const latestDate = info.dates.sort().at(-1) ?? null;
      const isPlaceholder = source.includes("placeholder");
      return {
        source,
        lastUpdated: latestDate,
        records: info.count,
        status: isPlaceholder ? "placeholder" : latestDate ? "ok" : "missing",
      };
    }
  );

  const fi = modelMetrics?.feature_importance ?? {};

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-6">
      <h2 className="text-white font-semibold text-lg mb-6">Model Diagnostics</h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Feature importance */}
        <div>
          <p className="text-slate-400 text-sm font-medium mb-3">Feature Importance</p>
          {Object.keys(fi).length > 0 ? (
            <FeatureImportanceChart data={fi} topN={10} />
          ) : (
            <div className="text-slate-500 text-sm text-center py-8 bg-slate-900 rounded-lg">
              Run models to see feature importance
            </div>
          )}
        </div>

        {/* Data freshness */}
        <div>
          <p className="text-slate-400 text-sm font-medium mb-3">Data Sources</p>
          {freshnessItems.length > 0 ? (
            <div className="space-y-2">
              {freshnessItems.map((item) => (
                <div
                  key={item.source}
                  className="flex items-center justify-between bg-slate-900 rounded-lg px-4 py-3"
                >
                  <div>
                    <p className="text-slate-200 text-sm">
                      {item.source.replace(/_/g, " ")}
                    </p>
                    <p className="text-slate-500 text-xs">
                      {item.records} records ·{" "}
                      {item.lastUpdated ? `latest ${item.lastUpdated}` : "no data"}
                    </p>
                  </div>
                  <span
                    className={`text-xs px-2 py-1 rounded-full font-medium ${
                      item.status === "ok"
                        ? "bg-emerald-900/50 text-emerald-400"
                        : item.status === "placeholder"
                        ? "bg-amber-900/50 text-amber-400"
                        : "bg-red-900/50 text-red-400"
                    }`}
                  >
                    {item.status}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-2">
              {["google_trends", "reddit"].map((src) => (
                <div
                  key={src}
                  className="flex items-center justify-between bg-slate-900 rounded-lg px-4 py-3"
                >
                  <p className="text-slate-400 text-sm">{src.replace(/_/g, " ")}</p>
                  <span className="text-xs px-2 py-1 rounded-full font-medium bg-slate-700 text-slate-400">
                    not fetched
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Warnings */}
          <div className="mt-4 space-y-2">
            {signals.some((s) => s.source === "reddit_placeholder") && (
              <div className="bg-amber-900/20 border border-amber-700/30 rounded-lg p-3 text-amber-400 text-xs">
                Reddit credentials not configured. Set REDDIT_CLIENT_ID and
                REDDIT_CLIENT_SECRET in .env for live data.
              </div>
            )}
            {signals.some((s) => s.source === "opensky_placeholder") && (
              <div className="bg-amber-900/20 border border-amber-700/30 rounded-lg p-3 text-amber-400 text-xs">
                OpenSky flight data unavailable. Configure TMDX_AIRCRAFT_ICAO24
                with verified FAA ICAO24 codes to enable.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
