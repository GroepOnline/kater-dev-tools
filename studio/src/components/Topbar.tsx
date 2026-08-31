import { Plus, Radio } from 'lucide-react';
import { StatusPill } from './StatusPill';

export function Topbar({ connected, profile }: { connected: boolean; profile: string }) {
  return <header className="topbar"><div><span className="eyebrow">Kater Studio</span><strong>Operator workspace</strong></div><div className="topbar-actions"><StatusPill state={connected ? 'healthy' : 'offline'} label={connected ? 'gateway live' : 'gateway offline'} /><span className="profile-chip"><Radio size={13} aria-hidden />{profile}</span><button className="primary-action" disabled><Plus size={14} aria-hidden />Add MCP</button></div></header>;
}
