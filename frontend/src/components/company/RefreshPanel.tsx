"use client";

import { useState } from "react";
import { RefreshCw, ChevronDown, ChevronUp, CheckCircle2, XCircle } from "lucide-react";
import { refreshCompany } from "@/lib/api";
import { RefreshLogEntry } from "@/lib/types";

interface Props {
  company: string;
  lastRefreshed: string | null;
  refreshLog: RefreshLogEntry[];
  onRefreshComplete?: () => void;
}

export default function RefreshPanel({
  company,
  lastRefreshed,
  refreshLog,
  onRefreshComplete,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const [showLogs, setShowLogs] = useState(false);

  async function handleRefresh() {
    setLoading(true);
    setToast(null);
    try {
      await refreshCompany(company);
      setToast({ type: "success", message: "Refresh started — data will update in the background." });
      // Poll once after 8s to let background task complete
      setTimeout(() => {
        onRefreshComplete?.();
      }, 8000);
    } catch (err) {
      setToast({ type: "error", message: String(err) });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-5">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <p className="text-white font-medium text-sm">Data Refresh</p>
          <p className="text-slate-500 text-xs mt-1">
            {lastRefreshed
              ? `Last updated: ${new Date(lastRefreshed).toLocaleString()}`
              : "Never refreshed — click to fetch signals and run models"}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleRefresh}
            disabled={loading}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-900 disabled:text-blue-400 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            {loading ? "Refreshing..." : "Refresh Data"}
          </button>

          {refreshLog.length > 0 && (
            <button
              onClick={() => setShowLogs(!showLogs)}
              className="flex items-center gap-1 text-slate-400 hover:text-slate-200 text-xs transition-colors"
            >
              Logs
              {showLogs ? (
                <ChevronUp className="h-3 w-3" />
              ) : (
                <ChevronDown className="h-3 w-3" />
              )}
            </button>
          )}
        </div>
      </div>

      {/* Toast */}
      {toast && (
        <div
          className={`mt-4 flex items-start gap-2 p-3 rounded-lg text-sm ${
            toast.type === "success"
              ? "bg-emerald-900/30 border border-emerald-700/50 text-emerald-400"
              : "bg-red-900/30 border border-red-700/50 text-red-400"
          }`}
        >
          {toast.type === "success" ? (
            <CheckCircle2 className="h-4 w-4 mt-0.5 flex-shrink-0" />
          ) : (
            <XCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
          )}
          <span>{toast.message}</span>
        </div>
      )}

      {/* Refresh logs */}
      {showLogs && refreshLog.length > 0 && (
        <div className="mt-4 space-y-1">
          <p className="text-slate-400 text-xs font-medium mb-2">Recent Refresh Logs</p>
          <div className="max-h-40 overflow-y-auto space-y-1">
            {refreshLog.map((log, i) => (
              <div
                key={i}
                className="flex items-center justify-between text-xs bg-slate-900 rounded px-3 py-2"
              >
                <div className="flex items-center gap-2">
                  {log.success ? (
                    <CheckCircle2 className="h-3 w-3 text-emerald-500" />
                  ) : (
                    <XCircle className="h-3 w-3 text-red-500" />
                  )}
                  <span className="text-slate-300">
                    {log.source_name.replace(/_/g, " ")}
                  </span>
                  {log.records_fetched > 0 && (
                    <span className="text-slate-500">{log.records_fetched} records</span>
                  )}
                </div>
                <div className="text-right">
                  <span className="text-slate-600">
                    {new Date(log.started_at).toLocaleString()}
                  </span>
                  {log.error_message && (
                    <p className="text-red-400 text-xs truncate max-w-48">
                      {log.error_message}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
