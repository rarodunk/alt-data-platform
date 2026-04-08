"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getCompanies } from "@/lib/api";
import { Company } from "@/lib/types";

const COMPANIES = [
  { id: "duolingo",    ticker: "DUOL", metric: "Revenue + DAU",      color: "#61aff4" },
  { id: "lemonade",    ticker: "LMND", metric: "Customer Count",     color: "#61aff4" },
  { id: "nu",          ticker: "NU",   metric: "Customer Count",     color: "#61aff4" },
  { id: "transmedics", ticker: "TMDX", metric: "Revenue + Flights",  color: "#61aff4" },
];

export default function HomePage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCompanies().then(setCompanies).catch(e => setError(e.message));
  }, []);

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "40px 16px" }}>
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 30, fontWeight: 700, letterSpacing: 0.2, margin: 0 }}>
          Alt Data Platform
        </h1>
        <p style={{ fontSize: 14, color: "var(--muted)", marginTop: 6 }}>
          Alternative signal forecasting — Google Trends, flight tracking, social data mapped to quarterly KPIs.
        </p>
      </div>

      {error && (
        <div className="panel" style={{ padding: "12px 16px", marginBottom: 24, color: "var(--bad)", fontSize: 13 }}>
          Unable to reach backend — please try again in a moment.
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12 }}>
        {COMPANIES.map(c => {
          const co = companies.find(x => x.id === c.id);
          return (
            <Link key={c.id} href={`/${c.id}`} style={{ textDecoration: "none" }}>
              <div className="panel" style={{ padding: 20, cursor: "pointer", transition: "box-shadow 0.15s" }}
                onMouseEnter={e => (e.currentTarget.style.boxShadow = "0 12px 28px rgba(0,0,0,0.08)")}
                onMouseLeave={e => (e.currentTarget.style.boxShadow = "")}>
                <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--muted)", marginBottom: 4 }}>
                  {c.ticker}
                </div>
                <div style={{ fontSize: 18, fontWeight: 700, color: "var(--ink)", marginBottom: 2 }}>
                  {co?.name ?? c.id}
                </div>
                <div style={{ fontSize: 12, color: "var(--muted)" }}>{c.metric}</div>
                {co?.hasModels && (
                  <div style={{ marginTop: 12, fontSize: 11, color: "var(--accent)", fontWeight: 600 }}>
                    ● Models ready
                  </div>
                )}
              </div>
            </Link>
          );
        })}

        {/* Chess tracker card */}
        <Link href="/chess-tracker" style={{ textDecoration: "none" }}>
          <div className="panel" style={{ padding: 20, cursor: "pointer", transition: "box-shadow 0.15s" }}
            onMouseEnter={e => (e.currentTarget.style.boxShadow = "0 12px 28px rgba(0,0,0,0.08)")}
            onMouseLeave={e => (e.currentTarget.style.boxShadow = "")}>
            <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--muted)", marginBottom: 4 }}>
              Tracker
            </div>
            <div style={{ fontSize: 18, fontWeight: 700, color: "var(--ink)", marginBottom: 2 }}>
              Chess Head-to-Head
            </div>
            <div style={{ fontSize: 12, color: "var(--muted)" }}>Duolingo Chess vs Chess.com</div>
            <div style={{ marginTop: 12, fontSize: 11, color: "#4a90e2", fontWeight: 600 }}>
              ● Visits + Downloads
            </div>
          </div>
        </Link>
      </div>
    </div>
  );
}
