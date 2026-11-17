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
const GENERIC_CREDENTIAL_KEY = 'api_key';

type CredentialValues = Record<string, string>;

function serverConfigured(server: CatalogServer): boolean {
  return server.env_configured ?? server.configured ?? true;
}

function serverAuthScheme(server: CatalogServer): string {
  return (server.auth_schemes && server.auth_schemes[0]) || 'none';
}

function authText(authScheme: string): string {
  if (authScheme === 'oauth2') return 'OAuth';
  if (authScheme === 'api_key') return 'API key';
  if (authScheme === 'bearer') return 'Bearer';
  return 'No auth';
}

/**
 * `/api/catalog` declares the env keys a server needs. Credentials must be
 * submitted under those exact names, so multi-credential servers need one
 * field per declared key instead of a single generic token field.
 */
function serverCredentialKeys(server: CatalogServer): string[] {
  const required = (server as CatalogServer & { env_required?: string[] }).env_required;
  if (Array.isArray(required) && required.length > 0) return required;
  return serverAuthScheme(server) === 'none' ? [] : [GENERIC_CREDENTIAL_KEY];
}

function errorText(reason: unknown, fallback: string): string {
  return reason instanceof Error ? reason.message : fallback;
}

async function submitCredentials(server: CatalogServer, credentials: Record<string, string>): Promise<void> {
  if (server.enabled) {
    await katerApi.saveCredentials(server.name, credentials);
    return;
  }
  await katerApi.enableIntegration(server.name, credentials);
}

function matchesQuery(server: CatalogServer, needle: string): boolean {
  if (!needle) return true;
  const hay = `${server.name} ${server.description ?? ''} ${server.transport ?? ''} ${(server.profiles ?? []).join(' ')} ${server.category ?? ''}`.toLowerCase();
  if (hay.includes(needle)) return true;
  const tools = server.toolkit_tools ?? [];
  return tools.some(t => String(t.name ?? '').toLowerCase().includes(needle));
}

function filterAndSortServers(servers: CatalogServer[], query: string, category: string, sort: string): CatalogServer[] {
  const needle = query.toLowerCase().trim();
  const filtered = servers.filter(server => {
    if (category !== 'all' && (server.category || 'dev') !== category) return false;
    return matchesQuery(server, needle);
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
}

function catalogBadge(catalog: CatalogResponse | null, loading: boolean) {
  if (loading) return <span className="count-badge">loading</span>;
  if (catalog) return <span className="count-badge">{catalog.total} available</span>;
  return <span className="count-badge">unavailable</span>;
}

function rowStatus(server: CatalogServer): 'ok' | 'error' | 'run' {
  if (!server.enabled) return 'run';
  return serverConfigured(server) ? 'ok' : 'error';
}

function ServerRow({
  server,
  onAdd,
  onSelect,
}: {
  server: CatalogServer;
  onAdd: (server: CatalogServer) => void;
  onSelect: (server: CatalogServer) => void;
}) {
  const configured = serverConfigured(server);
  const authScheme = serverAuthScheme(server);
  const transport = server.transport ?? 'unknown';
  const risk = server.risk ?? 'unknown';
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
      <CodexExec
        command={server.name}
        result={`${transport} · ${risk} · ${authText(authScheme)}${server.enabled ? (configured ? ' · ready' : ' · needs config') : ''}`}
        status={rowStatus(server)}
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
          connectionCount={server.connection_count}
          onSelect={onSelect}
          onAdd={onAdd}
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
          onClick={() => onAdd(server)}
          aria-label={`Add ${server.name}`}
        >
          Add {server.name}
        </button>
      )}
      {server.enabled && !configured && (
        <button
          type="button"
          className="secondary-action"
          style={{ alignSelf: 'flex-start', fontSize: '11px', padding: '2px 8px' }}
          onClick={() => onAdd(server)}
          aria-label={`Connect ${server.name}`}
        >
          Connect {server.name}
        </button>
      )}
      {!server.enabled && (
        <button
          type="button"
          className="secondary-action"
          style={{ alignSelf: 'flex-start', fontSize: '11px', padding: '2px 8px' }}
          onClick={() => onSelect(server)}
          aria-label={`Inspect ${server.name}`}
        >
          Inspect {server.name}
        </button>
      )}
    </div>
  );
}

function CategoryChips({ category, onSelect }: { category: string; onSelect: (category: string) => void }) {
  return (
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
          onClick={() => onSelect(cat)}
        >
          {cat}
        </button>
      ))}
    </div>
  );
}

function CatalogBody({
  loading,
  catalog,
  total,
  servers,
  hasQuery,
  onClearFilters,
  onAdd,
  onSelect,
}: {
  loading: boolean;
  catalog: CatalogResponse | null;
  total: number;
  servers: CatalogServer[];
  hasQuery: boolean;
  onClearFilters: () => void;
  onAdd: (server: CatalogServer) => void;
  onSelect: (server: CatalogServer) => void;
}) {
  if (loading) return <EmptyState>Loading catalog…</EmptyState>;
  if (!catalog) return <EmptyState>Catalog unavailable. Gateway status may still be available.</EmptyState>;
  if (total === 0) return <EmptyState>No integrations are registered in the live catalog.</EmptyState>;
  if (servers.length === 0) {
    if (!hasQuery) return <EmptyState>No integrations are available.</EmptyState>;
    return <EmptyState><div className="empty-state-stack"><strong>No matching integrations</strong><span>Clear filters to return to the live catalog.</span><button className="secondary-action" type="button" onClick={onClearFilters}>Clear filters</button></div></EmptyState>;
  }
  return <div className="integration-grid">
    {servers.map(server => (
      <ServerRow key={server.name} server={server} onAdd={onAdd} onSelect={onSelect} />
    ))}
  </div>;
}

function DetailDisclosure({ server }: { server: CatalogServer }) {
  return <div style={{ marginBottom: '20px' }}>
    <CodexMessage role="user">tools · {server.toolkit_tools?.length ?? 0}</CodexMessage>
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      {(server.toolkit_tools ?? []).map(t => (
        <div key={t.name} style={{ background: 'var(--surface-2)', padding: '8px 12px', borderRadius: '4px' }}>
          <div style={{ fontFamily: 'var(--mono)', fontSize: '12px', fontWeight: 600 }}>{t.name}</div>
          {t.description && <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{t.description}</div>}
        </div>
      ))}
    </div>
  </div>;
}

function DetailPanel({
  server,
  onClose,
  onConnect,
  onDisable,
}: {
  server: CatalogServer;
  onClose: () => void;
  onConnect: (server: CatalogServer) => void;
  onDisable: (server: CatalogServer) => Promise<void>;
}) {
  const configured = serverConfigured(server);
  return (
    <div className="modal-backdrop" onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 100, display: 'flex', justifyContent: 'flex-end' }}>
      <div
        className="component-card"
        onClick={e => e.stopPropagation()}
        style={{ width: '420px', height: '100%', borderRadius: 0, padding: '24px', overflowY: 'auto', background: 'var(--surface)' }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <strong style={{ fontSize: '16px' }}>{server.name}</strong>
          <button type="button" className="secondary-action" onClick={onClose}>✕</button>
        </div>
        <CodexMessage role="user">name</CodexMessage>
        <CodexMessage role="assistant">{server.name}</CodexMessage>
        {server.description && (
          <>
            <CodexMessage role="user">description</CodexMessage>
            <CodexMessage role="assistant">{server.description}</CodexMessage>
          </>
        )}
        <CodexMessage role="user">transport</CodexMessage>
        <CodexMessage role="assistant">{server.transport ?? 'unknown'}</CodexMessage>
        <CodexMessage role="user">risk</CodexMessage>
        <CodexMessage role="assistant">{server.risk ?? 'unknown'}</CodexMessage>
        {server.category && (
          <>
            <CodexMessage role="user">category</CodexMessage>
            <CodexMessage role="assistant">{server.category}</CodexMessage>
          </>
        )}
        {server.trigger_count ? (
          <>
            <CodexMessage role="user">triggers</CodexMessage>
            <CodexMessage role="assistant">{server.trigger_count}</CodexMessage>
          </>
        ) : null}
        {server.triggers && server.triggers.length > 0 && (
          <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', margin: '8px 0' }}>
            <CodexMessage role="user">triggers · cadence</CodexMessage>
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
        {server.docs_url && (
          <div style={{ marginBottom: '16px' }}>
            <a href={server.docs_url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)', fontSize: '12px' }}>
              Documentation ↗
            </a>
          </div>
        )}
        {server.toolkit_tools && server.toolkit_tools.length > 0 && <DetailDisclosure server={server} />}
        <div style={{ marginTop: 'auto', display: 'flex', gap: '8px' }}>
          {!server.enabled ? (
            <button
              type="button"
              className="primary-action"
              style={{ flex: 1 }}
              onClick={() => onConnect(server)}
            >
              Add integration
            </button>
          ) : (
            <>
              {!configured && (
                <button
                  type="button"
                  className="primary-action"
                  style={{ flex: 1 }}
                  onClick={() => onConnect(server)}
                >
                  Connect
                </button>
              )}
              <button
                type="button"
                className="secondary-action"
                style={{ flex: 1 }}
                onClick={async () => { await onDisable(server); }}
              >
                Disable
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function CredentialModal({
  server,
  values,
  error,
  busy,
  onValueChange,
  onSubmit,
  onClose,
}: {
  server: CatalogServer;
  values: CredentialValues;
  error: string | null;
  busy: boolean;
  onValueChange: (key: string, value: string) => void;
  onSubmit: (event: React.FormEvent) => void;
  onClose: () => void;
}) {
  const keys = Object.keys(values);
  const action = server.enabled ? 'connect' : 'enable';
  return (
    <div className="modal-backdrop" onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 110, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <form
        className="component-card"
        onSubmit={onSubmit}
        onClick={e => e.stopPropagation()}
        style={{ width: '400px', padding: '24px', background: 'var(--surface)' }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <strong style={{ fontSize: '15px' }}>Connect {server.name}</strong>
          <button type="button" className="secondary-action" onClick={onClose}>✕</button>
        </div>
        <CodexMessage role="user">toolkit</CodexMessage>
        <CodexMessage role="assistant">{server.name}</CodexMessage>
        <CodexMessage role="assistant">Enter credentials for {server.name} to {action} this toolkit.</CodexMessage>
        {error && (
          <div style={{ color: 'var(--err)', fontSize: '12px', marginBottom: '12px', background: 'var(--err-dim)', padding: '8px', borderRadius: '4px' }}>
            {error}
          </div>
        )}
        {keys.map((key, index) => (
          <div key={key} style={{ marginBottom: '16px' }}>
            <label htmlFor={`integration-credential-${key}`} style={{ display: 'block', fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '6px' }}>
              {key === GENERIC_CREDENTIAL_KEY ? 'API Key / Access Token' : key}
            </label>
            <input
              id={`integration-credential-${key}`}
              type="password"
              className="form-input"
              style={{ width: '100%', padding: '8px 10px', background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: '4px', color: 'var(--text)' }}
              value={values[key] ?? ''}
              onChange={e => onValueChange(key, e.target.value)}
              placeholder="paste credential value"
              autoFocus={index === 0}
            />
          </div>
        ))}
        <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
          <button type="button" className="secondary-action" onClick={onClose}>Cancel</button>
          <button type="submit" className="primary-action" disabled={busy}>
            {busy ? 'Connecting…' : server.enabled ? 'Save & Connect' : 'Save & Enable'}
          </button>
        </div>
      </form>
    </div>
  );
}

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
  const [credentialValues, setCredentialValues] = useState<CredentialValues>({});
  const [enabling, setEnabling] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query]);

  const allServers = catalog?.servers ?? [];
  const servers = useMemo(
    () => filterAndSortServers(allServers, debouncedQuery, category, sort),
    [allServers, debouncedQuery, category, sort],
  );
  const active = allServers.filter(server => server.enabled).length;
  const needs = allServers.filter(server => server.enabled && !serverConfigured(server)).length;
  const hasQuery = debouncedQuery.trim().length > 0 || category !== 'all';

  const enableWithoutCredentials = async (server: CatalogServer) => {
    setEnabling(true);
    setActionError(null);
    try {
      await katerApi.enableIntegration(server.name);
      onRefresh?.();
    } catch (err) {
      setActionError(errorText(err, 'Failed to enable'));
    } finally {
      setEnabling(false);
    }
  };

  const openCredentialModal = (server: CatalogServer) => {
    const values: CredentialValues = {};
    serverCredentialKeys(server).forEach(key => { values[key] = ''; });
    setAuthModalServer(server);
    setCredentialValues(values);
    setActionError(null);
  };

  const handleQuickAdd = (server: CatalogServer) => {
    const keys = serverCredentialKeys(server);
    if (!server.enabled && (keys.length === 0 || serverConfigured(server))) {
      void enableWithoutCredentials(server);
      return;
    }
    if (keys.length === 0) {
      setActionError(`${server.name} is enabled but declares no credential fields; check the gateway configuration.`);
      return;
    }
    openCredentialModal(server);
  };

  const handleAuthSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!authModalServer) return;
    const auth: Record<string, string> = {};
    Object.entries(credentialValues).forEach(([key, value]) => {
      const trimmed = value.trim();
      if (trimmed) auth[key] = trimmed;
    });
    if (Object.keys(auth).length === 0) {
      setActionError('Enter at least one credential value.');
      return;
    }
    const server = authModalServer;
    setEnabling(true);
    setActionError(null);
    try {
      await submitCredentials(server, auth);
      setAuthModalServer(null);
      setCredentialValues({});
      onRefresh?.();
    } catch (err) {
      setActionError(errorText(err, server.enabled ? 'Failed to connect' : 'Authentication failed'));
      onRefresh?.();
    } finally {
      setEnabling(false);
    }
  };

  const handleDisable = async (server: CatalogServer) => {
    await katerApi.toggleServer(server.name, 'disable');
    setSelectedServer(null);
    onRefresh?.();
  };

  const openCredentialModalFromDetail = (server: CatalogServer) => {
    setSelectedServer(null);
    handleQuickAdd(server);
  };

  return <section className="view-stack">
    <div className="component-card" style={{ padding: '14px 18px' }}>
      <strong style={{ fontSize: '15px' }}>Integrations</strong>
      <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>Live MCP catalog from Kater. Search and inspect the real control-plane state without a parallel frontend runtime.</span>
      <div style={{ marginLeft: 'auto' }}>{catalogBadge(catalog, loading)}</div>
    </div>
    <div className="metrics-grid">
      <CodexMessage role="assistant">Catalog · {catalog?.total ?? '—'}</CodexMessage>
      <CodexMessage role="assistant">Enabled · {catalog ? active : '—'}</CodexMessage>
      <CodexMessage role="assistant">Needs config · {catalog ? needs : '—'}</CodexMessage>
    </div>
    {catalog && allServers.length > 0 && (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        <IntegrationToolbar query={query} onQueryChange={setQuery} shown={servers.length} total={allServers.length} sort={sort} onSortChange={setSort} />
        <CategoryChips category={category} onSelect={setCategory} />
      </div>
    )}
    {actionError && !authModalServer && !selectedServer && (
      <div className="error-strip inline-error" role="alert" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <span>{actionError}</span>
        <button type="button" className="secondary-action" style={{ marginLeft: 'auto', padding: '2px 8px', fontSize: '11px' }} onClick={() => setActionError(null)}>Dismiss</button>
      </div>
    )}
    <CatalogBody
      loading={loading}
      catalog={catalog}
      total={allServers.length}
      servers={servers}
      hasQuery={hasQuery}
      onClearFilters={() => { setQuery(''); setCategory('all'); }}
      onAdd={handleQuickAdd}
      onSelect={setSelectedServer}
    />

    {selectedServer && (
      <DetailPanel
        server={selectedServer}
        onClose={() => setSelectedServer(null)}
        onConnect={openCredentialModalFromDetail}
        onDisable={handleDisable}
      />
    )}

    {authModalServer && (
      <CredentialModal
        server={authModalServer}
        values={credentialValues}
        error={actionError}
        busy={enabling}
        onValueChange={(key, value) => setCredentialValues(current => ({ ...current, [key]: value }))}
        onSubmit={handleAuthSubmit}
        onClose={() => { setAuthModalServer(null); setCredentialValues({}); }}
      />
    )}
  </section>;
}
