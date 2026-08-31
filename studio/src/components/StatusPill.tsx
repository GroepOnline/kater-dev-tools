import type { HealthState } from '../types';

export function StatusPill({ state, label }: { state: HealthState; label: string }) {
  return <span className={`status-pill status-${state}`}><span className="status-dot" aria-hidden />{label}</span>;
}
