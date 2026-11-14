import { Save } from 'lucide-react';
import { Fragment, useEffect, useMemo, useState } from 'react';
import { ClaudeMessage } from '../components/brainless/claude/ClaudeMessage';
import { PageHeader } from '../components/PageHeader';
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

  const rows = useMemo(() => {
    if (!data) return [] as Array<{ key: string; value: string }>;
    const overrideCount = Object.values(data.server_overrides).length;
    return [
      { key: 'Default profile', value: data.default_profile },
      { key: 'Storage backend', value: data.storage_backend },
      { key: 'Authentication mode', value: data.auth.mode },
      { key: 'Configured API keys', value: String(data.auth.api_keys ?? 0) },
      { key: 'CORS origins', value: data.cors_origins.join(', ') || '—' },
      { key: 'Rate limit per minute', value: String(data.rate_limit_per_min) },
      { key: 'Host', value: data.host },
      { key: 'API port', value: String(data.api_port) },
      { key: 'MCP port', value: String(data.mcp_port) },
      { key: 'WebSocket port', value: String(data.ws_port) },
      { key: 'Connector mode', value: data.connector_invocation_mode },
      { key: 'Connector pool TTL (s)', value: String(data.connector_pool_ttl_seconds) },
      { key: 'High-risk default disabled', value: data.high_risk_default_disabled ? 'yes' : 'no' },
      { key: 'Proxy failure threshold', value: String(data.proxy_failure_threshold) },
      { key: 'Proxy recovery timeout', value: String(data.proxy_recovery_timeout) },
      { key: 'Body size limit', value: String(data.body_size_limit) },
      { key: 'Server overrides', value: `${overrideCount} total` },
      { key: 'Settings version', value: String(data.version) },
    ];
  }, [data]);

  if (loading && !data) {
    return (
      <section className="view-stack">
        <PageHeader title="Settings" description="Safe Kater runtime configuration." />
        <ClaudeMessage role="assistant">Loading settings…</ClaudeMessage>
      </section>
    );
  }
  if (!data) {
    return (
      <section className="view-stack">
        <PageHeader title="Settings" description="Safe Kater runtime configuration." />
        <ClaudeMessage role="assistant">{`Settings unavailable: ${error ?? 'No settings data returned.'}`}</ClaudeMessage>
        <button className="secondary-action" type="button" onClick={() => void refresh()}>Retry</button>
      </section>
    );
  }

  const changed = profile.trim() !== data.default_profile || storage !== data.storage_backend;
  const canSave = studioConfig.features.allowSafeSettingsMutations && changed && profile.trim().length > 0 && !saving;

  return (
    <section className="view-stack">
      <PageHeader
        title="Settings"
        description="Safe fields are writable through the existing Kater settings policy. Sensitive auth/CORS/rate-limit fields remain read-only here."
        aside={<span className="count-badge">config v{data.version}</span>}
      />
      {error && <div className="error-strip inline-error">Settings mutation blocked: {error}</div>}
      <div className="settings-panel component-card">
        {rows.map(row => (
          <Fragment key={row.key}>
            <ClaudeMessage role="user">{row.key}</ClaudeMessage>
            <ClaudeMessage role="assistant">{row.value}</ClaudeMessage>
          </Fragment>
        ))}
        <Fragment key="mutable-profile">
          <ClaudeMessage role="user">Default profile (mutable)</ClaudeMessage>
          <ClaudeMessage role="assistant">
            <input className="setting-input" value={profile} onChange={event => setProfile(event.target.value)} />
          </ClaudeMessage>
        </Fragment>
        <Fragment key="mutable-storage">
          <ClaudeMessage role="user">Storage backend (mutable)</ClaudeMessage>
          <ClaudeMessage role="assistant">
            <select className="setting-input" value={storage} onChange={event => setStorage(event.target.value as 'jsonl' | 'sqlite')}>
              <option value="jsonl">jsonl</option>
              <option value="sqlite">sqlite</option>
            </select>
          </ClaudeMessage>
        </Fragment>
      </div>
      <div className="settings-actions">
        <button className="primary-action" disabled={!canSave} onClick={() => void update({ default_profile: profile.trim(), storage_backend: storage })}>
          <Save size={14} aria-hidden />{saving ? 'Saving…' : 'Save safe settings'}
        </button>
        <span>403 means the runtime requires an admin credential; Studio never asks for or stores that secret.</span>
      </div>
    </section>
  );
}