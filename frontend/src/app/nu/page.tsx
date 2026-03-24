"use client";
import dynamic from "next/dynamic";

const CompanyPage = dynamic(() => import("@/components/company/CompanyPage"), { ssr: false });

export default function NuPage() {
  return (
    <CompanyPage
      company="nu"
      metrics={[{ key: "customers_m", label: "Customers", unit: "M" }]}
      note="Nu Holdings customer count in millions. Growth has been exceptional — from 33M in Q4 2021 to over 109M by Q3 2024. Google Trends uses: 'nubank', 'nu bank', 'cartão nubank'."
    />
  );
}
