export const ROUTES = {
  sharedHome: '/',
  pbsDetails: '/details',
  pbsStudio: '/studio',
  pbsWorkspaceAlias: '/workspace',
  pbsWikiBook: '/llmwikibook',
  pbsWikiBookAlias: '/studio-v2',
  pbsPlaybookLibrary: '/playbook-library',
  pbsControlTower: '/playbook-library/control-tower',
  pbsRepository: '/playbook-library/repository',
  opsHome: '/ops',
  opsWorkspaces: '/ops/workspaces',
  opsConnections: '/ops/connections',
  opsOverview: '/ops/overview',
  opsResources: '/ops/resources',
  opsChat: '/ops/chat',
  opsActions: '/ops/actions',
  opsScm: '/ops/scm',
  opsDetails: '/ops/details',
  partnerHome: '/ops',
  partnerWorkspace: '/ops/workspaces',
  partnerLibrary: '/ops/resources',
  partnerViewer: '/ops/chat',
  partnerDetails: '/ops/details',
} as const;

export type SharedLandingTab = 'pbs' | 'ops';

export const RESERVED_PBS_PATH_PREFIXES = [
  ROUTES.pbsPlaybookLibrary,
  ROUTES.pbsStudio,
  ROUTES.pbsWikiBook,
] as const;

export const PARTNER_NAMESPACE_PATHS = [
  ROUTES.opsHome,
  ROUTES.opsWorkspaces,
  ROUTES.opsConnections,
  ROUTES.opsOverview,
  ROUTES.opsResources,
  ROUTES.opsChat,
  ROUTES.opsActions,
  ROUTES.opsScm,
  ROUTES.opsDetails,
] as const;

export function normalizeSharedLandingTab(value: string | null | undefined): SharedLandingTab {
  return value === 'ops' ? 'ops' : 'pbs';
}

export function buildSharedLandingHref(tab: SharedLandingTab = 'pbs'): string {
  return tab === 'pbs' ? ROUTES.sharedHome : `${ROUTES.sharedHome}?tab=${tab}`;
}
