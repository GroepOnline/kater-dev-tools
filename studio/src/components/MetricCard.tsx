import type { LucideIcon } from 'lucide-react';

export function MetricCard({ icon: Icon, label, value, detail }: { icon: LucideIcon; label: string; value: string | number; detail?: string }) {
  return <article className="metric-card component-card">
    <span className="metric-icon"><Icon size={17} aria-hidden /></span>
    <div><div className="metric-label">{label}</div><div className="metric-value">{value}</div>{detail && <div className="metric-detail">{detail}</div>}</div>
  </article>;
}
