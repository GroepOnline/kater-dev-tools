import { useState } from 'react';
import { studioConfig, type StudioView } from './config';
import { Sidebar } from './components/Sidebar';
import { Topbar } from './components/Topbar';
import { useKaterData } from './hooks/useKaterData';
import { AutomationsView } from './views/AutomationsView';
import { BrowserWorkspaceView } from './views/BrowserWorkspaceView';
import { ControlRoomView } from './views/ControlRoomView';
import { IntegrationsView } from './views/IntegrationsView';
import { PlaceholderView } from './views/PlaceholderView';
import { PrGateView } from './views/PrGateView';
import { TelemetryView } from './views/TelemetryView';

const placeholderCopy: Partial<Record<StudioView, [string, string]>> = {
  settings: ['Settings', 'Gateway configuration with server-side ownership of secrets and policy.'],
};

function ActiveView({ view, status, catalog, loading }: { view: StudioView; status: ReturnType<typeof useKaterData>['status']; catalog: ReturnType<typeof useKaterData>['catalog']; loading: boolean }) {
  if (view === 'integrations') return <IntegrationsView catalog={catalog} loading={loading} />;
  if (view === 'control') return <ControlRoomView status={status} />;
  if (view === 'browser') return <BrowserWorkspaceView />;
  if (view === 'pr') return <PrGateView />;
  if (view === 'automations') return <AutomationsView />;
  if (view === 'telemetry') return <TelemetryView />;
  return <PlaceholderView title={placeholderCopy[view]?.[0] ?? view} description={placeholderCopy[view]?.[1] ?? ''} />;
}

export function App() {
  const [view, setView] = useState<StudioView>(studioConfig.defaults.view);
  const data = useKaterData();
  return <div className="app-shell"><Sidebar active={view} onSelect={setView} /><main className="workspace"><Topbar connected={!data.error} profile={String(data.status?.profile ?? studioConfig.defaults.profile)} />{data.error && <div className="error-strip">Gateway data unavailable: {data.error}</div>}<div className="workspace-scroll"><ActiveView view={view} status={data.status} catalog={data.catalog} loading={data.loading} /></div></main></div>;
}
