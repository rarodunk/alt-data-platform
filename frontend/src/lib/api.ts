import { Company, CompanyOverview } from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${path} → ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export async function getCompanies(): Promise<Company[]> {
  return apiFetch<Company[]>("/companies");
}

export async function getCompanyOverview(
  company: string
): Promise<CompanyOverview> {
  return apiFetch<CompanyOverview>(`/${company}/overview`);
}

export async function refreshCompany(
  company: string
): Promise<{ status: string }> {
  return apiFetch(`/${company}/refresh`, { method: "POST" });
}

export async function getBacktest(company: string, metric?: string) {
  const qs = metric ? `?metric=${metric}` : "";
  return apiFetch(`/${company}/backtest${qs}`);
}

export async function getSignals(company: string) {
  return apiFetch(`/${company}/signals`);
}

export async function getChessTrends() {
  return apiFetch<{
    chess_com: { date: string; interest_value: number }[];
    duolingo_chess: { date: string; interest_value: number }[];
    source: string;
    note: string;
  }>("/chess-tracker/trends");
}

export async function getChessAppstore() {
  return apiFetch<{
    historical: {
      chess_com: { date: string; rating_count: number; avg_rating: number }[];
      duolingo: { date: string; rating_count: number; avg_rating: number }[];
    };
    live: {
      date: string; app: string; app_name: string;
      rating_count: number; avg_rating: number;
    }[];
    note: string;
  }>("/chess-tracker/appstore");
}

export async function getChessSummary() {
  return apiFetch<{
    as_of: string | null;
    trends: {
      chess_com: { latest_interest: number | null; peak_interest: number | null };
      duolingo_chess: { latest_interest: number | null; peak_interest: number | null };
    };
    appstore: {
      chess_com: { rating_count: number; avg_rating: number; app_name: string } | null;
      duolingo: { rating_count: number; avg_rating: number; app_name: string } | null;
    };
  }>("/chess-tracker/summary");
}
