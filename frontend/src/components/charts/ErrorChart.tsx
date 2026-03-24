"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";

interface DataPoint {
  quarter: string;
  pct_error: number;
}

interface Props {
  data: DataPoint[];
}

function errorColor(pct: number): string {
  const abs = Math.abs(pct);
  if (abs < 5) return "#34d399"; // emerald
  if (abs < 15) return "#fbbf24"; // amber
  return "#f87171"; // red
}

const CustomTooltip = ({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
}) => {
  if (!active || !payload?.length) return null;
  const val = payload[0].value;
  return (
    <div className="bg-slate-800 border border-slate-600 rounded-lg p-3 text-sm shadow-xl">
      <p className="text-slate-300 font-medium">{label}</p>
      <p className="text-white">
        Error:{" "}
        <span style={{ color: errorColor(val) }}>
          {val > 0 ? "+" : ""}
          {val.toFixed(1)}%
        </span>
      </p>
    </div>
  );
};

export default function ErrorChart({ data }: Props) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-slate-500 text-sm">
        No backtest data available
      </div>
    );
  }

  return (
    <div className="w-full h-56">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis
            dataKey="quarter"
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#334155" }}
          />
          <YAxis
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#334155" }}
            tickFormatter={(v) => `${v}%`}
            width={50}
          />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine y={0} stroke="#64748b" strokeWidth={1} />
          <ReferenceLine
            y={5}
            stroke="#34d399"
            strokeDasharray="3 3"
            strokeOpacity={0.4}
          />
          <ReferenceLine
            y={-5}
            stroke="#34d399"
            strokeDasharray="3 3"
            strokeOpacity={0.4}
          />
          <Bar dataKey="pct_error" radius={[2, 2, 0, 0]}>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={errorColor(entry.pct_error)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
