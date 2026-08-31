import { studioConfig, type StudioView } from '../config';

export function Sidebar({ active, onSelect }: { active: StudioView; onSelect: (view: StudioView) => void }) {
  const sections = [...new Set(studioConfig.navigation.map(item => item.section))];
  return <aside className="sidebar">
    <div className="brand-block"><div className="brand-mark">K</div><div><strong>{studioConfig.product.name}</strong><span>{studioConfig.product.subtitle}</span></div></div>
    <nav className="nav-scroll">
      {sections.map(section => <div className="nav-section" key={section}><div className="nav-label">{section}</div>{studioConfig.navigation.filter(item => item.section === section).map(item => {
        const Icon = item.icon;
        return <button className={`nav-item ${active === item.id ? 'active' : ''}`} onClick={() => onSelect(item.id)} key={item.id}><Icon size={15} aria-hidden /><span>{item.label}</span></button>;
      })}</div>)}
    </nav>
    <div className="sidebar-foot">Python gateway remains authoritative</div>
  </aside>;
}
