import { useState } from 'react';
import { studioConfig, type StudioView } from './config';
import { Sidebar } from './components/Sidebar';
import { Topbar } from './components/Topbar';
import { useKaterData } from './hooks/useKaterData';
import { ControlRoomView } from './views/ControlRoomView';
import { IntegrationsView } from './views/IntegrationsView';
import { PlaceholderView } from './views/PlaceholderView';
import { PrGateView } from './views/PrGateView';

const placeholderCopy: Partial<Record<StudioView, [string, string]>> = {
  browser: ['Browser Workspace', 'Browser sessions and actions will bind to the existing /api/browser routes.'],
  automations: ['Automations', 'Scheduled and event-driven Kater automations, without fake sample runs.'],
  telemetry: ['Telemetry', 'Live Kater events and WebSocket state, using authoritative runtime data only.'],
  settings: ['Settings', 'Gateway configuration with server-side ownership of secrets and policy.'],
};

export function App() {
  const [view, setView] = useState<StudioView>(studioConfig.defaults.view);
  const { status, catalog, error, loading } = useKaterData();
  return <div className="app-shell"><Sidebar active={view} onSelect={setView} /><main className="workspace"><Topbar connected={!error} profile={String(status?.profile ?? studioConfig.defaults.profile)} />{error && <div className="error-strip">Gateway data unavailable: {error}</div>}<div className="workspace-scroll">{view === 'integrations' ? <IntegrationsView catalog={catalog} loading={loading} /> : view === 'control' ? <ControlRoomView status={status} /> : view === 'pr' ? <PrGateView /> : <PlaceholderView title={placeholderCopy[view]?.[0] ?? view} description={placeholderCopy[view]?.[1] ?? ''} />}</div></main></div>;
}
