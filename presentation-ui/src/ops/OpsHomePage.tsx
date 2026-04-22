import { ArrowRight, Boxes, FolderTree, GitBranch, Link2, MessageSquare, ShieldCheck, Waypoints } from 'lucide-react';
import { Link } from 'react-router-dom';
import { ROUTES } from '../app/routes';
import { OpsShell } from './OpsShell';

const SURFACES = [
  {
    href: ROUTES.opsWorkspaces,
    icon: Boxes,
    title: 'Workspaces',
    description: 'Workspace-scoped operational state, model ownership, and cluster context.',
  },
  {
    href: ROUTES.opsConnections,
    icon: Link2,
    title: 'Connections',
    description: 'Cluster credentials, verification, and connection posture for each workspace.',
  },
  {
    href: ROUTES.opsOverview,
    icon: Waypoints,
    title: 'Overview',
    description: 'Cluster density, posture, and operational health summaries.',
  },
  {
    href: ROUTES.opsResources,
    icon: FolderTree,
    title: 'Resources',
    description: 'Live resource browsing, namespace inspection, and YAML-driven operations.',
  },
  {
    href: ROUTES.opsChat,
    icon: MessageSquare,
    title: 'Ops Chat',
    description: 'Cluster-aware operational chat, separate from PlayBookStudio document chat.',
  },
  {
    href: ROUTES.opsActions,
    icon: ShieldCheck,
    title: 'Actions',
    description: 'Preview, approval, execution, and audit workflow surfaces.',
  },
  {
    href: ROUTES.opsScm,
    icon: GitBranch,
    title: 'SCM',
    description: 'Repository-driven delivery, Git provider setup, and deployment planning.',
  },
] as const;

export default function OpsHomePage() {
  return (
    <OpsShell
      eyebrow="OCP Ops"
      title="Operational control lane"
      description="This lane will host the workspace-aware OpenShift operations experience. It stays separate from PlayBookStudio document retrieval and turns cluster operations into an explicitly bounded product surface."
      actions={
        <Link to={ROUTES.opsWorkspaces} className="ops-primary-action">
          <span>Start with workspaces</span>
          <ArrowRight size={18} />
        </Link>
      }
    >
      <div className="ops-grid">
        {SURFACES.map(({ href, icon: Icon, title, description }) => (
          <Link key={href} to={href} className="ops-card glass-panel">
            <div className="ops-card-icon">
              <Icon size={24} />
            </div>
            <h3>{title}</h3>
            <p>{description}</p>
          </Link>
        ))}
      </div>
    </OpsShell>
  );
}
