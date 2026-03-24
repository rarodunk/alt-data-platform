"use client";

import { ReactNode } from "react";

interface Props {
  children: ReactNode;
  title: string;
  ticker: string;
  description?: string;
}

export default function CompanyLayout({ children, title, ticker, description }: Props) {
  return (
    <div className="min-h-screen bg-slate-950">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Page header */}
        <div className="mb-8">
          <div className="flex items-baseline gap-3">
            <h1 className="text-3xl font-bold text-white">{title}</h1>
            <span className="text-slate-400 text-lg font-mono">{ticker}</span>
          </div>
          {description && (
            <p className="mt-2 text-slate-400 text-sm max-w-2xl">{description}</p>
          )}
        </div>
        {children}
      </div>
    </div>
  );
}
