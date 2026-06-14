import type { ReactNode } from "react";

type Props = {
  icon: ReactNode;
  label: string;
  value: string;
  detail: string;
  tone?: "blue" | "green" | "purple" | "cyan";
};

export function KpiCard({ icon, label, value, detail, tone = "blue" }: Props) {
  return (
    <article className="kpi-card">
      <div className={`kpi-icon ${tone}`}>{icon}</div>
      <div>
        <span className="kpi-label">{label}</span>
        <strong className="kpi-value">{value}</strong>
        <small className={tone === "green" ? "positive" : ""}>{detail}</small>
      </div>
    </article>
  );
}

