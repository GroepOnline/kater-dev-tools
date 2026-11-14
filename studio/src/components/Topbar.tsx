export function Topbar({ connected, profile }: { connected: boolean; profile: string }) {
  return (
    <div className="border-b border-border px-4 py-2 font-mono text-[12px] flex items-center gap-3">
      <span style={{ color: connected ? 'var(--bn-green)' : 'var(--bn-pink)' }}>{connected ? '●' : '○'}</span>
      <span style={{ color: 'var(--bn-fg)' }}>connected</span>
      <span style={{ color: 'var(--bn-muted)' }}>·</span>
      <span style={{ color: 'var(--bn-fg)' }}>profile: {profile}</span>
    </div>
  );
}