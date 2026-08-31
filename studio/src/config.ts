import { AppWindow, Boxes, Bot, Gauge, GitPullRequest, Globe2, RadioTower, Settings2, Workflow } from 'lucide-react';

export type StudioView = 'integrations' | 'control' | 'agents' | 'browser' | 'pr' | 'automations' | 'telemetry' | 'settings';

export const studioConfig = {
  product: { name: 'KATER', subtitle: 'Dev Tools & Integrations Hub', version: '1.1.x' },
  api: { baseUrl: import.meta.env.VITE_KATER_API_BASE ?? '' },
  navigation: [
    { section: 'Connect & discover', id: 'integrations' as const, label: 'Integrations', icon: Boxes },
    { section: 'Workspace & control', id: 'control' as const, label: 'Control Room', icon: Gauge },
    { section: 'Workspace & control', id: 'agents' as const, label: 'Agent Activity', icon: Bot },
    { section: 'Workspace & control', id: 'browser' as const, label: 'Browser Workspace', icon: Globe2 },
    { section: 'Workspace & control', id: 'pr' as const, label: 'PR Gate & CI', icon: GitPullRequest },
    { section: 'Workspace & control', id: 'automations' as const, label: 'Automations', icon: Workflow },
    { section: 'Workspace & control', id: 'telemetry' as const, label: 'Telemetry', icon: RadioTower },
    { section: 'System', id: 'settings' as const, label: 'Settings', icon: Settings2 },
  ],
  defaults: { view: 'integrations' as StudioView, profile: 'core' },
  features: {
    showExperimentalViews: true,
    allowAutomationMutations: true,
    allowSafeSettingsMutations: true,
  },
  marks: { app: AppWindow },
};
