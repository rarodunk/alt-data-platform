"use client";
import dynamic from "next/dynamic";

const CompanyPage = dynamic(() => import("@/components/company/CompanyPage"), { ssr: false });

export default function DuolingoPage() {
  return (
    <CompanyPage
      company="duolingo"
      metrics={[
        { key: "revenue_m", label: "Revenue", unit: "M" },
        { key: "dau_m", label: "DAUs", unit: "M" },
      ]}
      note="Duolingo revenue is in USD millions. DAU data available from Q1 2022 onward. Google Trends uses keywords: 'duolingo', 'learn language app', 'duolingo plus'."
    />
  );
}
