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
