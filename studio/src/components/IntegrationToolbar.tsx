import { Search, X } from 'lucide-react';

export function IntegrationToolbar({
  query,
  onQueryChange,
  shown,
  total,
  sort,
  onSortChange,
}: {
  query: string;
  onQueryChange: (value: string) => void;
  shown: number;
  total: number;
  sort: string;
  onSortChange: (value: string) => void;
}) {
  return <div className="integration-toolbar component-card">
    <label className="search-field">
      <Search size={15} aria-hidden />
      <input
        value={query}
        onChange={event => onQueryChange(event.target.value)}
        placeholder="Search MCP servers, transports and profiles"
        aria-label="Search integrations"
      />
      {query && <button className="search-clear" type="button" onClick={() => onQueryChange('')} aria-label="Clear integration search"><X size={13} aria-hidden /></button>}
    </label>
    <select
      className="catalog-sort-select"
      value={sort}
      onChange={event => onSortChange(event.target.value)}
      aria-label="Sort integrations"
    >
      <option value="popularity">Popularity</option>
      <option value="name">Name (A-Z)</option>
      <option value="recent">Name (Z-A)</option>
    </select>
    <div className="toolbar-meta"><span className="live-pulse" aria-hidden />Showing <strong>{shown}</strong> of {total}</div>
  </div>;
}