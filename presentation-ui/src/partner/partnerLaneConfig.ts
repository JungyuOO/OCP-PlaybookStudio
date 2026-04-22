import {
  Boxes,
  FolderTree,
  GitBranch,
  LayoutDashboard,
  Link2,
  MessageSquare,
  MonitorPlay,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react';
import { ROUTES } from '../app/routes';

export type PartnerRouteDefinition = {
  path: string;
  eyebrow: string;
  title: string;
  description: string;
  card?: {
    icon: LucideIcon;
    title: string;
    description: string;
  };
};

export const PARTNER_ROUTE_DEFINITIONS: PartnerRouteDefinition[] = [
  {
    path: ROUTES.opsHome,
    eyebrow: 'OCP Ops',
    title: 'Operations lane bootstrap',
    description: 'This namespace will host the operational surfaces imported from the OCP Ops project.',
    card: {
      icon: Boxes,
      title: 'Ops Home',
      description: 'Shared entry point for workspaces, connections, overview, resources, actions, and SCM.',
    },
  },
  {
    path: ROUTES.opsWorkspaces,
    eyebrow: 'OCP Ops Workspaces',
    title: 'Workspace surface placeholder',
    description: 'Workspace-aware operational state will land here first because the rest of OCP Ops hangs off workspace context.',
    card: {
      icon: Boxes,
      title: 'Workspaces',
      description: 'Reserved route for workspace selection, activation, and workspace-scoped operational state.',
    },
  },
  {
    path: ROUTES.opsConnections,
    eyebrow: 'OCP Ops Connections',
    title: 'Connection surface placeholder',
    description: 'Cluster, credential, and provider connection flows will be mounted here.',
    card: {
      icon: Link2,
      title: 'Connections',
      description: 'Reserved route for OCP cluster, auth, and provider connection management.',
    },
  },
  {
    path: ROUTES.opsOverview,
    eyebrow: 'OCP Ops Overview',
    title: 'Overview surface placeholder',
    description: 'Operational overview and metrics summaries will sit here once the OCP dashboard is ported.',
    card: {
      icon: LayoutDashboard,
      title: 'Overview',
      description: 'Reserved route for cluster overview, metrics summaries, and operational health snapshots.',
    },
  },
  {
    path: ROUTES.opsResources,
    eyebrow: 'OCP Ops Resources',
    title: 'Resource operations placeholder',
    description: 'Live cluster resources, namespace browsing, and action handoff surfaces will mount under this route family.',
    card: {
      icon: FolderTree,
      title: 'Resources',
      description: 'Reserved route for live resource inspection and YAML-oriented operational views.',
    },
  },
  {
    path: ROUTES.opsChat,
    eyebrow: 'OCP Ops Chat',
    title: 'Operational chat placeholder',
    description: 'This lane will host the OCP operations chatbot rather than the official-document knowledge chatbot.',
    card: {
      icon: MessageSquare,
      title: 'Ops Chat',
      description: 'Reserved route for the cluster-aware operational copilot experience.',
    },
  },
  {
    path: ROUTES.opsActions,
    eyebrow: 'OCP Ops Actions',
    title: 'Action workflow placeholder',
    description: 'Approval, audit, and guarded execution flows will be integrated here.',
    card: {
      icon: ShieldCheck,
      title: 'Actions',
      description: 'Reserved route for preview, approval, execution, and audit workflows.',
    },
  },
  {
    path: ROUTES.opsScm,
    eyebrow: 'OCP Ops SCM',
    title: 'SCM surface placeholder',
    description: 'Repository-driven delivery and SCM provider integrations will land here.',
    card: {
      icon: GitBranch,
      title: 'SCM',
      description: 'Reserved route for Git provider connections, repositories, and deployment planning.',
    },
  },
  {
    path: ROUTES.opsDetails,
    eyebrow: 'OCP Ops Details',
    title: 'Integration notes',
    description: 'This page marks the shell boundary where OCP Ops can be layered in without disturbing PlayBookStudio ownership.',
    card: {
      icon: MonitorPlay,
      title: 'Details',
      description: 'Reserved route for merge notes, handoff context, and ops-shell integration guidance.',
    },
  },
];

export const PARTNER_SURFACES = PARTNER_ROUTE_DEFINITIONS.filter(
  (route): route is PartnerRouteDefinition & { card: NonNullable<PartnerRouteDefinition['card']> } => Boolean(route.card),
);
