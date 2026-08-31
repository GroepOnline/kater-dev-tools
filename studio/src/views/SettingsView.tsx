import { EmptyState } from '../components/EmptyState';
import { PageHeader } from '../components/PageHeader';
import { SettingRow } from '../components/SettingRow';
import { useSettingsData } from '../hooks/useSettingsData';

export function SettingsView() {
  const { data, error, loading } = useSettingsData();
  if (error) return <section className="view-stack"><PageHeader title="Settings" description="Safe Kater runtime configuration summary." /><EmptyState>Settings unavailable: {error}</EmptyState></section>;
  if (loading || !data) return <section className="view-stack"><PageHeader title="Settings" description="Safe Kater runtime configuration summary." /><EmptyState>Loading settings…</EmptyState></section>;
  const overrides = Object.values(data.server_overrides);
  const explicitDisabled = overrides.filter(item => item.enabled === false).length;
  return <section className="view-stack">
    <PageHeader title="Settings" description="Read-only safe summary. Secret-bearing override env maps are never rendered in Studio." aside={<span className="count-badge">config v{data.version}</span>} />
    <div className="settings-panel component-card">
      <SettingRow label="Default profile" value={data.default_profile} detail="runtime profile fallback" />
      <SettingRow label="Authentication" value={data.auth.mode} detail={`${data.auth.api_keys ?? 0} configured API keys`} />
      <SettingRow label="Ports" value={`API ${data.api_port} · MCP ${data.mcp_port} · WS ${data.ws_port}`} />
      <SettingRow label="Storage" value={data.storage_backend} detail={data.db_path} />
      <SettingRow label="Connector mode" value={data.connector_invocation_mode} detail={`pool TTL ${data.connector_pool_ttl_seconds}s`} />
      <SettingRow label="High-risk default" value={data.high_risk_default_disabled ? 'disabled' : 'enabled'} />
      <SettingRow label="Server overrides" value={`${overrides.length} total · ${explicitDisabled} disabled`} detail="env values intentionally hidden" />
      <SettingRow label="Rate limit" value={data.rate_limit_per_min ? `${data.rate_limit_per_min}/min` : 'off'} />
    </div>
    <EmptyState>Editing stays disabled until Studio mutations are bound to the existing Kater policy and audit path.</EmptyState>
  </section>;
}
