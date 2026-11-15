import { Filter, Search, X } from 'lucide-react';

export function AgentSessionFilters({ query, onQueryChange, activeOnly, onActiveOnlyChange, shown, total }: {
  query: string; onQueryChange: (value: string) => void; activeOnly: boolean;
  onActiveOnlyChange: (value: boolean) => void; shown: number; total: number;
}) {
  return <div className="agent-filter-panel component-card">
    <label className="agent-filter-label" htmlFor="agent-session-search">Search agent sessions</label>
    <div className="search-field agent-filter-search">
      <Search size={13} aria-hidden />
      <input id="agent-session-search" value={query} onChange={event => onQueryChange(event.target.value)} placeholder="Find session, repo, profile or principal" />
      {query && <button type="button" className="search-clear" onClick={() => onQueryChange('')} aria-label="Clear session search"><X size={12} aria-hidden /></button>}
    </div>
    <button type="button" className={`agent-filter-chip ${activeOnly ? 'active' : ''}`} aria-pressed={activeOnly} onClick={() => onActiveOnlyChange(!activeOnly)}><Filter size={11} aria-hidden />Active only</button>
    <span className="agent-filter-count">{shown}/{total}</span>
  </div>;
}
