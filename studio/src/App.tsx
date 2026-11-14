import { useState } from 'react';
import { studioConfig, type StudioView } from './config';
import { Sidebar } from './components/Sidebar';
import { Topbar } from './components/Topbar';
import { ClaudeHeader } from './components/brainless/claude/ClaudeHeader';
import { useKaterData } from './hooks/useKaterData';
import type { CatalogResponse, StatusResponse } from './types';
import { AgentsView } from './views/AgentsView';
import { AutomationsView } from './views/AutomationsView';
import { BrowserWorkspaceView } from './views/BrowserWorkspaceView';
import { ControlRoomView } from './views/ControlRoomView';
import { IntegrationsView } from './views/IntegrationsView';
import { PrGateView } from './views/PrGateView';
import { SettingsView } from './views/SettingsView';
import { TelemetryView } from './views/TelemetryView';

function ActiveView({ view, status, catalog, loading, onRefresh }: { view: StudioView; status: StatusResponse | null; catalog: CatalogResponse | null; loading: boolean; onRefresh?: () => void }) {
  switch (view) {
    case 'integrations': return <IntegrationsView catalog={catalog} loading={loading} onRefresh={onRefresh} />;
    case 'control': return <ControlRoomView status={status} />;
    case 'agents': return <AgentsView status={status} />;
    case 'browser': return <BrowserWorkspaceView />;
    case 'pr': return <PrGateView />;
    case 'automations': return <AutomationsView />;
    case 'telemetry': return <TelemetryView />;
    case 'settings': return <SettingsView />;
  }
}

export function App() {
  const [view, setView] = useState<StudioView>(studioConfig.defaults.view);
  const data = useKaterData();
  const profile = String(data.status?.profile ?? studioConfig.defaults.profile);
  const version = String(data.status?.version ?? studioConfig.product.version);
  return (
    <div className="app-shell">
      <Sidebar active={view} onSelect={setView} />
      <main className="workspace">
        <ClaudeHeader profile={profile} version={version} />
        <Topbar connected={!data.loading && !data.error && data.status !== null} profile={profile} />
        {data.error && <div className="error-strip">Gateway data unavailable: {data.error}</div>}
        <div className="workspace-scroll">
          <ActiveView view={view} status={data.status} catalog={data.catalog} loading={data.loading} onRefresh={data.refresh} />
        </div>
      </main>
    </div>
  );
}