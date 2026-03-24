"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

interface Props {
  data: Record<string, number>;
  topN?: number;
}

export default function FeatureImportanceChart({ data, topN = 10 }: Props) {
  if (!data || Object.keys(data).length === 0) {
    return (
      <div className="flex items-center justify-center h-40 text-slate-500 text-sm">
        No feature importance data
      </div>
    );
  }

  const sorted = Object.entries(data)
    .sort((a, b) => b[1] - a[1])
    .slice(0, topN)
    .map(([feature, importance]) => ({
      feature: feature.replace(/_/g, " ").replace(/lag(\d)/g, "lag $1"),
      importance: Math.round(importance * 10) / 10,
    }))
    .reverse(); // bottom-to-top for readability

  const maxImportance = Math.max(...sorted.map((d) => d.importance));

  return (
    <div style={{ height: Math.max(200, sorted.length * 28 + 40) }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          layout="vertical"
          data={sorted}
          margin={{ top: 5, right: 30, left: 10, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
          <XAxis
            type="number"
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#334155" }}
            tickFormatter={(v) => `${v}%`}
            domain={[0, maxImportance * 1.1]}
          />
          <YAxis
            type="category"
            dataKey="feature"
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={140}
          />
          <Tooltip
            formatter={(value: number) => [`${value.toFixed(1)}%`, "Importance"]}
            contentStyle={{
              backgroundColor: "#1e293b",
              border: "1px solid #334155",
              borderRadius: "8px",
              color: "#f1f5f9",
              fontSize: 12,
            }}
          />
          <Bar dataKey="importance" radius={[0, 3, 3, 0]}>
            {sorted.map((_, index) => (
              <Cell
                key={`cell-${index}`}
                fill={`hsl(${220 + index * 8}, 70%, ${55 - index * 2}%)`}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
