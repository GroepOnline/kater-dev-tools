import { Radio, ShieldCheck } from 'lucide-react';
import { StatusPill } from './StatusPill';

export function Topbar({ connected, profile, section, viewLabel }: { connected: boolean; profile: string; section: string; viewLabel: string }) {
  return <header className="topbar">
    <div className="topbar-title">
      <span className="topbar-context"><span>Kater Studio</span><span aria-hidden>/</span><span>{section}</span></span>
      <strong>{viewLabel}</strong>
    </div>
    <div className="topbar-actions">
      <StatusPill state={connected ? 'healthy' : 'offline'} label={connected ? 'gateway live' : 'gateway offline'} />
      <span className="profile-chip"><span className="chip-label">profile</span><Radio size={12} aria-hidden />{profile}</span>
      <span className="authority-chip" title="Connection management stays in the authoritative Python Kater runtime"><ShieldCheck size={13} aria-hidden />Runtime managed</span>
    </div>
  </header>;
}
