import { Save } from 'lucide-react';
import { useEffect, useState } from 'react';
import { EmptyState } from '../components/EmptyState';
import { PageHeader } from '../components/PageHeader';
import { SettingRow } from '../components/SettingRow';
import { studioConfig } from '../config';
import { useSettingsData } from '../hooks/useSettingsData';

export function SettingsView() {
  const { data, error, loading, saving, refresh, update } = useSettingsData();
  const [profile, setProfile] = useState('core');
  const [storage, setStorage] = useState<'jsonl' | 'sqlite'>('jsonl');
  useEffect(() => {
    if (!data) return;
    setProfile(data.default_profile);
    setStorage(data.storage_backend === 'sqlite' ? 'sqlite' : 'jsonl');
  }, [data]);
  if (loading && !data) return <section className="view-stack"><PageHeader title="Settings" description="Safe Kater runtime configuration." /><EmptyState>Loading settings…</EmptyState></section>;
  if (!data) return <section className="view-stack"><PageHeader title="Settings" description="Safe Kater runtime configuration." /><EmptyState><div className="empty-state-stack"><strong>Settings unavailable</strong><span>{error ?? 'No settings data returned.'}</span><button className="secondary-action" type="button" onClick={() => void refresh()}>Retry</button></div></EmptyState></section>;
  const changed = profile.trim() !== data.default_profile || storage !== data.storage_backend;
  const canSave = studioConfig.features.allowSafeSettingsMutations && changed && profile.trim().length > 0 && !saving;
  const overrides = Object.values(data.server_overrides);
  return <section className="view-stack">
    <PageHeader title="Settings" description="Safe fields are writable through the existing Kater settings policy. Sensitive auth/CORS/rate-limit fields remain read-only here." aside={<span className="count-badge">config v{data.version}</span>} />
    {error && <div className="error-strip inline-error">Settings mutation blocked: {error}</div>}
    <div className="settings-panel component-card">
      <SettingRow label="Default profile" value={<input className="setting-input" value={profile} onChange={event => setProfile(event.target.value)} />} detail="safe mutable field" />
      <SettingRow label="Storage" value={<select className="setting-input" value={storage} onChange={event => setStorage(event.target.value as 'jsonl' | 'sqlite')}><option value="jsonl">jsonl</option><option value="sqlite">sqlite</option></select>} detail="safe mutable field" />
      <SettingRow label="Authentication" value={data.auth.mode} detail={`${data.auth.api_keys ?? 0} configured API keys · read-only in Studio`} />
      <SettingRow label="Ports" value={`API ${data.api_port} · MCP ${data.mcp_port} · WS ${data.ws_port}`} />
      <SettingRow label="Connector mode" value={data.connector_invocation_mode} detail={`pool TTL ${data.connector_pool_ttl_seconds}s`} />
      <SettingRow label="High-risk default" value={data.high_risk_default_disabled ? 'disabled' : 'enabled'} />
      <SettingRow label="Server overrides" value={`${overrides.length} total`} detail="secret-bearing env maps intentionally hidden" />
    </div>
    <div className="settings-actions"><button className="primary-action" disabled={!canSave} onClick={() => void update({ default_profile: profile.trim(), storage_backend: storage })}><Save size={14} aria-hidden />{saving ? 'Saving…' : 'Save safe settings'}</button><span>403 means the runtime requires an admin credential; Studio never asks for or stores that secret.</span></div>
  </section>;
}
