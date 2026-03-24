"use client";
import dynamic from "next/dynamic";

const CompanyPage = dynamic(() => import("@/components/company/CompanyPage"), { ssr: false });

export default function LemonadePage() {
  return (
    <CompanyPage
      company="lemonade"
      metrics={[{ key: "customers_k", label: "Customers", unit: "k" }]}
      note="Lemonade customer count in thousands. Google Trends uses: 'lemonade insurance', 'lemonade renters insurance'."
    />
  );
}
