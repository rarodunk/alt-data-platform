"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3 } from "lucide-react";

const NAV = [
  { href: "/duolingo",    label: "DUOL" },
  { href: "/lemonade",    label: "LMND" },
  { href: "/nu",          label: "NU"   },
  { href: "/transmedics", label: "TMDX" },
];

export default function Navbar() {
  const path = usePathname();
  return (
    <nav className="border-b border-slate-800 bg-slate-950/90 backdrop-blur sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 h-12 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 text-white font-semibold text-sm">
          <BarChart3 className="h-4 w-4 text-blue-400" />
          Alt Data
        </Link>
        <div className="flex items-center gap-1">
          {NAV.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold transition-colors ${
                path.startsWith(href)
                  ? "bg-slate-800 text-white"
                  : "text-slate-500 hover:text-slate-300 hover:bg-slate-800/50"
              }`}
            >
              {label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
}
