import { studioConfig, type StudioView } from '../config';

export function Sidebar({ active, onSelect }: { active: StudioView; onSelect: (view: StudioView) => void }) {
  const navigation = studioConfig.navigation.filter(item => studioConfig.features.showExperimentalViews || !('experimental' in item && item.experimental));
  const sections = [...new Set(navigation.map(item => item.section))];
  return <aside className="sidebar">
    <div className="brand-block">
      <div className="brand-mark" aria-hidden><span>K</span></div>
      <div className="brand-copy"><div className="brand-line"><strong>{studioConfig.product.name}</strong><span className="version-badge">v{studioConfig.product.version}</span></div><span>{studioConfig.product.subtitle}</span></div>
    </div>
    <nav className="nav-scroll" aria-label="Kater Studio">
      {sections.map(section => <div className="nav-section" key={section}><div className="nav-label">{section}</div>{navigation.filter(item => item.section === section).map(item => {
        const Icon = item.icon;
        return <button className={`nav-item ${active === item.id ? 'active' : ''}`} onClick={() => onSelect(item.id)} key={item.id} aria-current={active === item.id ? 'page' : undefined}><Icon size={15} aria-hidden /><span>{item.label}</span><span className="nav-chevron" aria-hidden>›</span></button>;
      })}</div>)}
    </nav>
    <div className="sidebar-foot"><span className="authority-dot" aria-hidden /><div><strong>Python control plane</strong><span>runtime authority</span></div></div>
  </aside>;
}
