import { useEffect, useMemo, useState } from 'react';
import type { CatalogResponse, CatalogServer } from '../types';
import { CodexExec } from '../components/brainless/codex/codex-exec';
import { CodexMessage } from '../components/brainless/codex/codex-message';
import { CodexToolCall } from '../components/brainless/codex/CodexToolCall';
import { ClaudeToolCall } from '../components/brainless/claude/claude-tool-call';
import { EmptyState } from '../components/EmptyState';
import { IntegrationCard } from '../components/IntegrationCard';
import { IntegrationToolbar } from '../components/IntegrationToolbar';
import { katerApi } from '../api/client';

const CATEGORIES = ['all', 'dev', 'ai', 'data', 'infra', 'comms', 'productivity', 'crm'];
const SEARCH_DEBOUNCE_MS = 300;

export function IntegrationsView({
  catalog,
  loading,
  onRefresh,
}: {
  catalog: CatalogResponse | null;
  loading: boolean;
  onRefresh?: () => void;
}) {
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [category, setCategory] = useState('all');
  const [sort, setSort] = useState('popularity');
  const [selectedServer, setSelectedServer] = useState<CatalogServer | null>(null);
  const [authModalServer, setAuthModalServer] = useState<CatalogServer | null>(null);
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [enabling, setEnabling] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query]);

  const allServers = catalog?.servers ?? [];
  const servers = useMemo(() => {
    const needle = debouncedQuery.toLowerCase().trim();
    const filtered = allServers.filter(server => {
      if (category !== 'all' && (server.category || 'dev') !== category) return false;
      if (!needle) return true;
      const hay = `${server.name} ${server.description ?? ''} ${server.transport ?? ''} ${(server.profiles ?? []).join(' ')} ${server.category ?? ''}`.toLowerCase();
      if (hay.includes(needle)) return true;
      const tools = server.toolkit_tools ?? [];
      return tools.some(t => String(t.name ?? '').toLowerCase().includes(needle));
    });
    const sorted = filtered.slice();
    if (sort === 'popularity') {
      sorted.sort((a, b) => {
        const ta = Number(a.trigger_count || 0);
        const tb = Number(b.trigger_count || 0);
        if (tb !== ta) return tb - ta;
        return String(a.name).localeCompare(String(b.name));
      });
    } else if (sort === 'recent') {
      sorted.sort((a, b) => String(b.name).localeCompare(String(a.name)));
    } else {
      sorted.sort((a, b) => String(a.name).localeCompare(String(b.name)));
    }
    return sorted;
  }, [allServers, debouncedQuery, category, sort]);

  const active = allServers.filter(server => server.enabled).length;
  const needs = allServers.filter(server => server.enabled && (server.env_configured ?? server.configured) === false).length;

  const hasQuery = debouncedQuery.trim().length > 0 || category !== 'all';
  const catalogAside = loading
    ? <span className="count-badge">loading</span>
    : catalog
      ? <span className="count-badge">{catalog.total} available</span>
      : <span className="count-badge">unavailable</span>;

  const handleQuickAdd = async (server: CatalogServer) => {
    const authScheme = (server.auth_schemes && server.auth_schemes[0]) || 'none';
    if (authScheme === 'none') {
      setEnabling(true);
      try {
        await katerApi.enableIntegration(server.name);
        onRefresh?.();
      } catch (err) {
        setActionError(err instanceof Error ? err.message : 'Failed to enable');
      } finally {
        setEnabling(false);
      }
    } else {
      setAuthModalServer(server);
      setApiKeyInput('');
      setActionError(null);
    }
  };

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!authModalServer) return;
    setEnabling(true);
    setActionError(null);
    try {
      await katerApi.enableIntegration(authModalServer.name, apiKeyInput ? { api_key: apiKeyInput } : undefined);
      setAuthModalServer(null);
      onRefresh?.();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Authentication failed');
    } finally {
      setEnabling(false);
    }
  };

  const renderRow = (server: CatalogServer) => {
    const configured = server.env_configured ?? server.configured ?? true;
    const authScheme = (server.auth_schemes && server.auth_schemes[0]) || 'none';
    const transport = server.transport ?? 'unknown';
    const risk = server.risk ?? 'unknown';
    const status = server.enabled
      ? configured ? 'ok' : 'error'
      : 'run';
    const authLabel = authScheme === 'oauth2' ? 'OAuth' : authScheme === 'api_key' ? 'API key' : authScheme === 'bearer' ? 'Bearer' : 'No auth';
    return (
      <div key={server.name} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <CodexExec
          command={server.name}
          result={`${transport} · ${risk} · ${authLabel}${server.enabled ? (configured ? ' · ready' : ' · needs config') : ''}`}
          status={status}
        >
          <CodexMessage role="user">{server.name}</CodexMessage>
          <CodexMessage role="assistant">{server.description || 'Kater integration.'}</CodexMessage>
          {server.toolkit_tools && server.toolkit_tools.length > 0 && (
            <CodexMessage role="assistant">
              tools: {server.toolkit_tools.slice(0, 4).map(t => t.name).join(', ')}
              {server.toolkit_tools.length > 4 ? ` (+${server.toolkit_tools.length - 4})` : ''}
            </CodexMessage>
          )}
          <CodexMessage role="assistant">
            {server.enabled ? `enabled${configured ? ' · healthy' : ' · needs config'}` : 'disabled · ready to add'}
            {server.category ? ` · ${server.category}` : ''}
            {server.trigger_count ? ` · ${server.trigger_count} triggers` : ''}
          </CodexMessage>
          <IntegrationCard
            server={server}
            onSelect={setSelectedServer}
            onAdd={handleQuickAdd}
          />
        </CodexExec>
        <CodexToolCall
          command="select"
          arg={server.name}
          result="open detail"
          status="ok"
        />
        {!server.enabled && (
          <ClaudeToolCall
            tool="add"
            arg={server.name}
            result="open modal"
            status="pending"
          />
        )}
        {!server.enabled && (
          <button
            type="button"
            className="secondary-action"
            style={{ alignSelf: 'flex-start', fontSize: '11px', padding: '2px 8px' }}
            onClick={() => handleQuickAdd(server)}
            aria-label={`Add ${server.name}`}
          >
            Add {server.name}
          </button>
        )}
        {!server.enabled && (
          <button
            type="button"
            className="secondary-action"
            style={{ alignSelf: 'flex-start', fontSize: '11px', padding: '2px 8px' }}
            onClick={() => setSelectedServer(server)}
            aria-label={`Inspect ${server.name}`}
          >
            Inspect {server.name}
          </button>
        )}
      </div>
    );
  };

  return <section className="view-stack">
    <div className="component-card" style={{ padding: '14px 18px' }}>
      <strong style={{ fontSize: '15px' }}>Integrations</strong>
      <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>Live MCP catalog from Kater. Search and inspect the real control-plane state without a parallel frontend runtime.</span>
      <div style={{ marginLeft: 'auto' }}>{catalogAside}</div>
    </div>
    <div className="metrics-grid">
      <CodexMessage role="assistant">Catalog · {catalog?.total ?? '—'}</CodexMessage>
      <CodexMessage role="assistant">Enabled · {catalog ? active : '—'}</CodexMessage>
      <CodexMessage role="assistant">Needs config · {catalog ? needs : '—'}</CodexMessage>
    </div>
    {catalog && allServers.length > 0 && (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        <IntegrationToolbar query={query} onQueryChange={setQuery} shown={servers.length} total={allServers.length} sort={sort} onSortChange={setSort} />
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {CATEGORIES.map(cat => (
            <button
              key={cat}
              type="button"
              className={`secondary-action ${category === cat ? 'active' : ''}`}
              style={{
                fontSize: '11px',
                padding: '4px 10px',
                borderRadius: '999px',
                background: category === cat ? 'var(--accent-dim)' : 'transparent',
                borderColor: category === cat ? 'var(--accent-line)' : 'var(--border)',
                color: category === cat ? 'var(--accent)' : 'var(--text-muted)',
              }}
              onClick={() => setCategory(cat)}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>
    )}
    {loading ? <EmptyState>Loading catalog…</EmptyState>
      : !catalog ? <EmptyState>Catalog unavailable. Gateway status may still be available.</EmptyState>
      : allServers.length === 0 ? <EmptyState>No integrations are registered in the live catalog.</EmptyState>
      : servers.length ? <div className="integration-grid">
          {servers.map(renderRow)}
        </div>
      : hasQuery ? <EmptyState><div className="empty-state-stack"><strong>No matching integrations</strong><span>Clear filters to return to the live catalog.</span><button className="secondary-action" type="button" onClick={() => { setQuery(''); setCategory('all'); }}>Clear filters</button></div></EmptyState>
      : <EmptyState>No integrations are available.</EmptyState>}

    {/* Detail Slide-over / Modal */}
    {selectedServer && (
      <div className="modal-backdrop" onClick={() => setSelectedServer(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 100, display: 'flex', justifyContent: 'flex-end' }}>
        <div
          className="component-card"
          onClick={e => e.stopPropagation()}
          style={{ width: '420px', height: '100%', borderRadius: 0, padding: '24px', overflowY: 'auto', background: 'var(--surface)' }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <strong style={{ fontSize: '16px' }}>{selectedServer.name}</strong>
            <button type="button" className="secondary-action" onClick={() => setSelectedServer(null)}>✕</button>
          </div>
          <CodexMessage role="user">name</CodexMessage>
          <CodexMessage role="assistant">{selectedServer.name}</CodexMessage>
          {selectedServer.description && (
            <>
              <CodexMessage role="user">description</CodexMessage>
              <CodexMessage role="assistant">{selectedServer.description}</CodexMessage>
            </>
          )}
          <CodexMessage role="user">transport</CodexMessage>
          <CodexMessage role="assistant">{selectedServer.transport ?? 'unknown'}</CodexMessage>
          <CodexMessage role="user">risk</CodexMessage>
          <CodexMessage role="assistant">{selectedServer.risk ?? 'unknown'}</CodexMessage>
          {selectedServer.category && (
            <>
              <CodexMessage role="user">category</CodexMessage>
              <CodexMessage role="assistant">{selectedServer.category}</CodexMessage>
            </>
          )}
          {selectedServer.trigger_count ? (
            <>
              <CodexMessage role="user">triggers</CodexMessage>
              <CodexMessage role="assistant">{selectedServer.trigger_count}</CodexMessage>
            </>
          ) : null}
          {selectedServer.triggers && selectedServer.triggers.length > 0 && (
            <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', margin: '8px 0' }}>
              <CodexMessage role="user">triggers · cadence</CodexMessage>
              {selectedServer.triggers.map(t => (
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
          {selectedServer.docs_url && (
            <div style={{ marginBottom: '16px' }}>
              <a href={selectedServer.docs_url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)', fontSize: '12px' }}>
                Documentation ↗
              </a>
            </div>
          )}
          {selectedServer.toolkit_tools && selectedServer.toolkit_tools.length > 0 && (
            <div style={{ marginBottom: '20px' }}>
              <CodexMessage role="user">tools · {selectedServer.toolkit_tools.length}</CodexMessage>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {selectedServer.toolkit_tools.map(t => (
                  <div key={t.name} style={{ background: 'var(--surface-2)', padding: '8px 12px', borderRadius: '4px' }}>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: '12px', fontWeight: 600 }}>{t.name}</div>
                    {t.description && <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{t.description}</div>}
                  </div>
                ))}
              </div>
            </div>
          )}
          <div style={{ marginTop: 'auto', display: 'flex', gap: '8px' }}>
            {!selectedServer.enabled ? (
              <button
                type="button"
                className="primary-action"
                style={{ flex: 1 }}
                onClick={() => {
                  const s = selectedServer;
                  setSelectedServer(null);
                  handleQuickAdd(s);
                }}
              >
                Add integration
              </button>
            ) : (
              <button
                type="button"
                className="secondary-action"
                style={{ flex: 1 }}
                onClick={async () => {
                  await katerApi.toggleServer(selectedServer.name, 'disable');
                  setSelectedServer(null);
                  onRefresh?.();
                }}
              >
                Disable
              </button>
            )}
          </div>
        </div>
      </div>
    )}

    {/* Auth Modal */}
    {authModalServer && (
      <div className="modal-backdrop" onClick={() => setAuthModalServer(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 110, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <form
          className="component-card"
          onSubmit={handleAuthSubmit}
          onClick={e => e.stopPropagation()}
          style={{ width: '400px', padding: '24px', background: 'var(--surface)' }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <strong style={{ fontSize: '15px' }}>Connect {authModalServer.name}</strong>
            <button type="button" className="secondary-action" onClick={() => setAuthModalServer(null)}>✕</button>
          </div>
          <CodexMessage role="user">toolkit</CodexMessage>
          <CodexMessage role="assistant">{authModalServer.name}</CodexMessage>
          <CodexMessage role="assistant">Enter credentials for {authModalServer.name} to enable this toolkit.</CodexMessage>
          {actionError && (
            <div style={{ color: 'var(--err)', fontSize: '12px', marginBottom: '12px', background: 'var(--err-dim)', padding: '8px', borderRadius: '4px' }}>
              {actionError}
            </div>
          )}
          <div style={{ marginBottom: '16px' }}>
            <label htmlFor="integration-api-key-input" style={{ display: 'block', fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '6px' }}>
              API Key / Access Token
            </label>
            <input
              id="integration-api-key-input"
              type="text"
              className="form-input"
              style={{ width: '100%', padding: '8px 10px', background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: '4px', color: 'var(--text)' }}
              value={apiKeyInput}
              onChange={e => setApiKeyInput(e.target.value)}
              placeholder="paste credential value"
              autoFocus
            />
          </div>
          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
            <button type="button" className="secondary-action" onClick={() => setAuthModalServer(null)}>Cancel</button>
            <button type="submit" className="primary-action" disabled={enabling}>
              {enabling ? 'Connecting…' : 'Save & Enable'}
            </button>
          </div>
        </form>
      </div>
    )}
  </section>;
}