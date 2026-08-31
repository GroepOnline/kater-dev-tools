import type { ReactNode } from 'react';

export function SettingRow({ label, value, detail }: { label: string; value: ReactNode; detail?: string }) {
  return <div className="setting-row">
    <div><strong>{label}</strong>{detail && <span>{detail}</span>}</div>
    <div className="setting-value">{value}</div>
  </div>;
}
