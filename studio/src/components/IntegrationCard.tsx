import { Cable, ShieldCheck } from 'lucide-react';
import type { CatalogServer } from '../types';
import { StatusPill } from './StatusPill';

export function IntegrationCard({
  server,
  onSelect,
  onAdd,
  connectionCount,
}: {
  server: CatalogServer;
  onSelect?: (server: CatalogServer) => void;
  onAdd?: (server: CatalogServer) => void;
  connectionCount?: number;
}) {
  const configured = server.env_configured ?? server.configured ?? true;
  const healthy = server.enabled && configured;
  const authScheme = (server.auth_schemes && server.auth_schemes[0]) || 'none';
  const authLabel = authScheme === 'oauth2' ? 'OAuth' : authScheme === 'api_key' ? 'API key' : authScheme === 'bearer' ? 'Bearer' : 'No auth';

  return <article
    className="integration-card component-card"
    style={{ cursor: onSelect ? 'pointer' : 'default', display: 'flex', flexDirection: 'column' }}
    onClick={() => onSelect?.(server)}
  >
    <header className="integration-head">
      <span className="integration-mark"><Cable size={18} aria-hidden /></span>
      <div className="integration-title"><strong>{server.name}</strong><span>{server.transport ?? 'unknown'} · {server.risk ?? 'unknown'} risk</span></div>
      <StatusPill state={healthy ? 'healthy' : server.enabled ? 'degraded' : 'unknown'} label={healthy ? 'active' : server.enabled ? 'needs config' : 'ready'} />
    </header>
    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', margin: '4px 0 8px 0' }}>
      <span className="tag" style={{ textTransform: 'lowercase' }}>{authLabel}</span>
      {server.category && <span className="tag" style={{ textTransform: 'lowercase' }}>{server.category}</span>}
      {Boolean(server.trigger_count) && <span className="tag" style={{ opacity: 0.8 }}>{server.trigger_count} triggers</span>}
      {server.triggers && server.triggers.length > 0 && (
        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', margin: '4px 0', width: '100%' }}>
          {server.triggers.map(t => (
            <span
              key={t.name}
              className={`tag trigger-pill trigger-${t.cadence || 'realtime'}`}
              title={t.description || t.name}
              style={{ fontSize: '10px', padding: '2px 6px' }}
            >
              {t.cadence === 'poll' ? '◔' : '⚡'} {t.name}
            </span>
          ))}
        </div>
      )}
      {connectionCount !== undefined && connectionCount > 0 && (
        <span className="tag connection-pill" style={{ color: 'var(--accent)', borderColor: 'var(--accent)' }}>🔗 {connectionCount} connected</span>
      )}
    </div>
    <p>{server.description || 'Kater integration.'}</p>
    {server.toolkit_tools && server.toolkit_tools.length > 0 && (
      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', margin: '8px 0' }}>
        {server.toolkit_tools.slice(0, 4).map(t => (
          <span key={t.name} className="tag" style={{ fontSize: '10px', padding: '2px 6px' }}>{t.name}</span>
        ))}
        {server.toolkit_tools.length > 4 && (
          <span className="tag" style={{ fontSize: '10px', padding: '2px 6px', opacity: 0.6 }}>+{server.toolkit_tools.length - 4}</span>
        )}
      </div>
    )}
    <footer style={{ marginTop: 'auto', paddingTop: '10px', borderTop: '1px solid var(--border)' }}>
      <span className="tag"><ShieldCheck size={12} aria-hidden />cost {server.context_cost ?? '—'}</span>
      {(server.profiles ?? []).slice(0, 3).map(profile => <span className="tag" key={profile}>{profile}</span>)}
      {!server.enabled && onAdd && (
        <button
          type="button"
          className="secondary-action"
          style={{ marginLeft: 'auto', padding: '3px 10px', fontSize: '11px', borderRadius: '4px' }}
          onClick={(e) => {
            e.stopPropagation();
            onAdd(server);
          }}
        >
          Add
        </button>
      )}
    </footer>
  </article>;
}
