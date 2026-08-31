import { EmptyState } from '../components/EmptyState';
import { PageHeader } from '../components/PageHeader';

export function PlaceholderView({ title, description }: { title: string; description: string }) {
  return <section className="view-stack"><PageHeader title={title} description={description} /><EmptyState>Component migration queued. Existing Kater functionality remains available in the current dashboard.</EmptyState></section>;
}
