import { Search, X } from 'lucide-react';

export type AgentAuditOutcomeFilter = 'all' | 'allowed' | 'denied' | 'other';
const filters: Array<{ value: AgentAuditOutcomeFilter; label: string }> = [
  { value: 'all', label: 'All' }, { value: 'allowed', label: 'Allowed' },
  { value: 'denied', label: 'Denied' }, { value: 'other', label: 'Other' },
];

export function AgentAuditFilters({ query, onQueryChange, outcome, onOutcomeChange, shown, total }: {
  query: string; onQueryChange: (value: string) => void; outcome: AgentAuditOutcomeFilter;
  onOutcomeChange: (value: AgentAuditOutcomeFilter) => void; shown: number; total: number;
}) {
  return <div className="agent-audit-filters">
    <label className="search-field agent-filter-search">
      <Search size={13} aria-hidden />
      <input value={query} onChange={event => onQueryChange(event.target.value)} placeholder="Filter capability, reason or profile" aria-label="Filter capability audit" />
      {query && <button type="button" className="search-clear" onClick={() => onQueryChange('')} aria-label="Clear audit filter"><X size={12} aria-hidden /></button>}
    </label>
    <div className="agent-filter-group" aria-label="Filter audit outcome">
      {filters.map(filter => <button type="button" key={filter.value} className={`agent-filter-chip ${outcome === filter.value ? 'active' : ''}`} aria-pressed={outcome === filter.value} onClick={() => onOutcomeChange(filter.value)}>{filter.label}</button>)}
    </div>
    <span className="agent-filter-count">{shown}/{total}</span>
  </div>;
}
