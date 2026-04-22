export type OpsWorkspaceRecord = {
  workspaceId: string;
  name: string;
  slug: string;
  industry: string;
  environment: string;
  createdAt: string;
  updatedAt: string;
};

export type OpsWorkspaceCreateRequest = {
  name: string;
  environment?: string;
};

export type OpsAuthMode = 'token' | 'password' | 'oauth_future';

export type OpsConnectionRequest = {
  workspaceId?: string;
  clusterUrl: string;
  authMode: OpsAuthMode;
  verifySsl: boolean;
  defaultNamespace?: string;
  displayName?: string;
  saveProfile?: boolean;
  token?: string;
  username?: string;
  password?: string;
};

export type OpsConnectionProfile = {
  workspaceId: string;
  connectionId: string;
  displayName: string;
  clusterUrl: string;
  authMode: OpsAuthMode;
  verifySsl: boolean;
  defaultNamespace: string;
  usernameHint: string;
  secretRef: string;
  saveProfile: boolean;
  status: string;
  lastVerifiedAt: string;
  expiresAt: string;
};

export type OpsConnectionStatusResponse = {
  connected: boolean;
  connection: OpsConnectionProfile | null;
  message: string;
};

export type OpsConnectionListResponse = {
  items: OpsConnectionProfile[];
  count: number;
  updatedAt: string;
};

export type OpsLiveResourceKind = 'pods' | 'deployments' | 'services' | 'routes' | 'events';

export type OpsLiveNamespaceListResponse = {
  connectionId: string;
  clusterUrl: string;
  count: number;
  items: string[];
};

export type OpsLiveResourceSummary = {
  name: string;
  namespace: string;
  kind: string;
  createdAt: string;
  phase: string;
  nodeName: string;
  readyReplicas: number;
  replicas: number;
  type: string;
  clusterIp: string;
  host: string;
  to: string;
};

export type OpsLiveResourceListResponse = {
  connectionId: string;
  clusterUrl: string;
  resource: string;
  namespace: string;
  count: number;
  items: OpsLiveResourceSummary[];
};

export type OpsLiveResourceDetailResponse = {
  connectionId: string;
  clusterUrl: string;
  resource: string;
  namespace: string;
  name: string;
  kind: string;
  manifestYaml: string;
  manifestJson: Record<string, unknown>;
};

export type OpsChatHistoryTurn = {
  role: 'user' | 'assistant';
  text: string;
};

export type OpsChatResponse = {
  connectionId: string;
  clusterUrl: string;
  mode: string;
  resource: string;
  namespace: string;
  answer: string;
  items: OpsLiveResourceSummary[];
  detail?: OpsLiveResourceDetailResponse | null;
};

export type OpsActionType = 'scale_deployment' | 'rollout_restart' | 'log_bundle';

export type OpsActionPreview = {
  connectionId: string;
  actionType: OpsActionType;
  namespace: string;
  resourceName: string;
  allowed: boolean;
  riskLevel: string;
  summary: string;
  previewCommand: string;
  breakGlass: boolean;
  breakGlassReason: string;
  breakGlassTicket: string;
  requiredApprovals: number;
  approvalStrategy: string;
  requesterRoles: string[];
  approverRoles: string[];
  executorRoles: string[];
  approvalRules: string[];
  policyChecks: string[];
  blockedReasons: string[];
  validationMessages: string[];
  diffUnified: string;
  dryRunStatus: string;
  dryRunMessages: string[];
  nextStep: string;
};

export type OpsActionRequestRecord = {
  requestId: string;
  status: string;
  preview: OpsActionPreview;
  requestedBy: string;
  requestedRoles: string[];
  requiredApprovals: number;
  approvalCount: number;
  approverIds: string[];
  approverRoleMap: Record<string, string[]>;
  reason: string;
  decisionNote: string;
  createdAt: string;
  updatedAt: string;
};

export type OpsActionExecutionRecord = {
  executionId: string;
  requestId: string;
  status: string;
  executionMode: string;
  simulated: boolean;
  preview: OpsActionPreview;
  summary: string;
  preflightChecks: string[];
  outputLines: string[];
  error: string;
  createdAt: string;
  updatedAt: string;
};

export type OpsActionAuditRecord = {
  eventId: string;
  eventType: string;
  actorId: string;
  requestId: string;
  executionId: string;
  actionType: string;
  namespace: string;
  resourceName: string;
  riskLevel: string;
  decisionNote: string;
  details: Record<string, unknown>;
  createdAt: string;
};

export type OpsScmProvider = 'github' | 'gitlab';

export type OpsScmConnectionRecord = {
  scmConnectionId: string;
  workspaceId: string;
  provider: OpsScmProvider;
  hostUrl: string;
  authType: string;
  accountLabel: string;
  loginName: string;
  scopes: string[];
  secretRef: string;
  status: string;
  createdAt: string;
  updatedAt: string;
};

export type OpsScmRepositoryRecord = {
  repositoryId: string;
  workspaceId: string;
  scmConnectionId: string;
  repoFullName: string;
  defaultBranch: string;
  configPath: string;
  deliveryMode: string;
  manifestKind: string;
  targetClusterUrl: string;
  targetNamespace: string;
  autoDeployEnabled: boolean;
  syncStatus: string;
  createdAt: string;
  updatedAt: string;
};

export type OpsScmDeploymentPlan = {
  repositoryId: string;
  workspaceId: string;
  repoFullName: string;
  defaultBranch: string;
  configPath: string;
  deliveryMode: string;
  manifestKind: string;
  targetClusterUrl: string;
  targetNamespace: string;
  autoDeployEnabled: boolean;
  filesToChange: string[];
  suggestedUpdates: string[];
  triggerKind: string;
  summary: string;
  commitTitle: string;
  commitBody: string;
  requiresPullRequest: boolean;
  nextStep: string;
};

export type OpsScmDiscoveredRepository = {
  provider: string;
  externalId: string;
  fullName: string;
  name: string;
  defaultBranch: string;
  webUrl: string;
  visibility: string;
};

export type OpsScmConfigPathCandidate = {
  path: string;
  manifestKind: string;
  score: number;
  confidence: 'recommended' | 'fallback';
};
