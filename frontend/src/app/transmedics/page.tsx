"use client";
import dynamic from "next/dynamic";

const CompanyPage = dynamic(() => import("@/components/company/CompanyPage"), { ssr: false });

export default function TransMedicsPage() {
  return (
    <CompanyPage
      company="transmedics"
      metrics={[{ key: "revenue_m", label: "Revenue", unit: "M" }]}
      note="TransMedics revenue in USD millions. Note the structural break in Q1 2023 when the aviation logistics segment launched (revenue jumped from ~$17M to ~$40M). Flight tracking requires verified ICAO24 codes — see the signal dashboard for setup instructions."
    />
  );
}
