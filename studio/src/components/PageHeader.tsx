import type { ReactNode } from 'react';

export function PageHeader({ title, description, aside }: { title: string; description: string; aside?: ReactNode }) {
  return <header className="view-header"><div><h1>{title}</h1><p>{description}</p></div>{aside}</header>;
}
