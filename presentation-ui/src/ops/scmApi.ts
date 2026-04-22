import type {
  OpsScmConnectionRecord,
  OpsScmDiscoveredRepository,
  OpsScmDeploymentPlan,
  OpsScmProvider,
  OpsScmRepositoryRecord,
} from './types';

type ApiScmConnectionRecord = {
  scm_connection_id: string;
  workspace_id: string;
  provider: OpsScmProvider;
  host_url: string;
  auth_type: string;
  account_label: string;
  login_name: string;
  scopes: string[];
  secret_ref: string;
  status: string;
  created_at: string;
  updated_at: string;
};

type ApiScmRepositoryRecord = {
  repository_id: string;
  workspace_id: string;
  scm_connection_id: string;
  repo_full_name: string;
  default_branch: string;
  config_path: string;
  delivery_mode: string;
  manifest_kind: string;
  target_cluster_url: string;
  target_namespace: string;
  auto_deploy_enabled: boolean;
  sync_status: string;
  created_at: string;
  updated_at: string;
};

type ApiScmDeploymentPlan = {
  repository_id: string;
  workspace_id: string;
  repo_full_name: string;
  default_branch: string;
  config_path: string;
  delivery_mode: string;
  manifest_kind: string;
  target_cluster_url: string;
  target_namespace: string;
  auto_deploy_enabled: boolean;
  files_to_change: string[];
  suggested_updates: string[];
  trigger_kind: string;
  summary: string;
  commit_title: string;
  commit_body: string;
  requires_pull_request: boolean;
  next_step: string;
};

type ApiScmDiscoveredRepository = {
  provider: string;
  external_id: string;
  full_name: string;
  name: string;
  default_branch: string;
  web_url: string;
  visibility: string;
};

function apiUrl(path: string) {
  if (typeof window === 'undefined') return path;
  return `${window.location.origin}${path}`;
}

async function readJson<T>(response: Response): Promise<T> {
  const text = await response.text();
  if (!response.ok) {
    throw new Error(text || `HTTP ${response.status}`);
  }
  return JSON.parse(text) as T;
}

function mapConnection(input: ApiScmConnectionRecord): OpsScmConnectionRecord {
  return {
    scmConnectionId: input.scm_connection_id,
    workspaceId: input.workspace_id,
    provider: input.provider,
    hostUrl: input.host_url,
    authType: input.auth_type,
    accountLabel: input.account_label,
    loginName: input.login_name,
    scopes: input.scopes ?? [],
    secretRef: input.secret_ref,
    status: input.status,
    createdAt: input.created_at,
    updatedAt: input.updated_at,
  };
}

function mapRepository(input: ApiScmRepositoryRecord): OpsScmRepositoryRecord {
  return {
    repositoryId: input.repository_id,
    workspaceId: input.workspace_id,
    scmConnectionId: input.scm_connection_id,
    repoFullName: input.repo_full_name,
    defaultBranch: input.default_branch,
    configPath: input.config_path,
    deliveryMode: input.delivery_mode,
    manifestKind: input.manifest_kind,
    targetClusterUrl: input.target_cluster_url,
    targetNamespace: input.target_namespace,
    autoDeployEnabled: input.auto_deploy_enabled,
    syncStatus: input.sync_status,
    createdAt: input.created_at,
    updatedAt: input.updated_at,
  };
}

function mapPlan(input: ApiScmDeploymentPlan): OpsScmDeploymentPlan {
  return {
    repositoryId: input.repository_id,
    workspaceId: input.workspace_id,
    repoFullName: input.repo_full_name,
    defaultBranch: input.default_branch,
    configPath: input.config_path,
    deliveryMode: input.delivery_mode,
    manifestKind: input.manifest_kind,
    targetClusterUrl: input.target_cluster_url,
    targetNamespace: input.target_namespace,
    autoDeployEnabled: input.auto_deploy_enabled,
    filesToChange: input.files_to_change ?? [],
    suggestedUpdates: input.suggested_updates ?? [],
    triggerKind: input.trigger_kind,
    summary: input.summary,
    commitTitle: input.commit_title,
    commitBody: input.commit_body,
    requiresPullRequest: input.requires_pull_request,
    nextStep: input.next_step,
  };
}

function mapDiscoveredRepository(input: ApiScmDiscoveredRepository): OpsScmDiscoveredRepository {
  return {
    provider: input.provider,
    externalId: input.external_id,
    fullName: input.full_name,
    name: input.name,
    defaultBranch: input.default_branch,
    webUrl: input.web_url,
    visibility: input.visibility,
  };
}

export async function listScmConnections(workspaceId: string): Promise<OpsScmConnectionRecord[]> {
  const response = await fetch(apiUrl(`/api/v1/workspaces/${workspaceId}/scm/connections`));
  const payload = await readJson<{ items: ApiScmConnectionRecord[] }>(response);
  return (payload.items ?? []).map(mapConnection);
}

export async function createScmConnection(workspaceId: string, payload: Record<string, unknown>): Promise<OpsScmConnectionRecord> {
  const response = await fetch(apiUrl(`/api/v1/workspaces/${workspaceId}/scm/connections`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return mapConnection(await readJson<ApiScmConnectionRecord>(response));
}

export async function startScmOauth(provider: OpsScmProvider, workspaceId: string): Promise<{ authorizeUrl: string; state: string }> {
  const response = await fetch(apiUrl(`/api/v1/oauth/${provider}/start?workspace_id=${encodeURIComponent(workspaceId)}`), {
    method: 'POST',
  });
  const payload = await readJson<{ authorize_url: string; state: string }>(response);
  return {
    authorizeUrl: payload.authorize_url,
    state: payload.state,
  };
}

export async function listScmRepositories(workspaceId: string): Promise<OpsScmRepositoryRecord[]> {
  const response = await fetch(apiUrl(`/api/v1/workspaces/${workspaceId}/scm/repositories`));
  const payload = await readJson<{ items: ApiScmRepositoryRecord[] }>(response);
  return (payload.items ?? []).map(mapRepository);
}

export async function createScmRepository(workspaceId: string, payload: Record<string, unknown>): Promise<OpsScmRepositoryRecord> {
  const response = await fetch(apiUrl(`/api/v1/workspaces/${workspaceId}/scm/repositories`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return mapRepository(await readJson<ApiScmRepositoryRecord>(response));
}

export async function updateScmRepository(workspaceId: string, repositoryId: string, payload: Record<string, unknown>): Promise<OpsScmRepositoryRecord> {
  const response = await fetch(apiUrl(`/api/v1/workspaces/${workspaceId}/scm/repositories/${repositoryId}`), {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return mapRepository(await readJson<ApiScmRepositoryRecord>(response));
}

export async function buildScmDeploymentPlan(workspaceId: string, repositoryId: string, payload: Record<string, unknown>): Promise<OpsScmDeploymentPlan> {
  const response = await fetch(apiUrl(`/api/v1/workspaces/${workspaceId}/scm/repositories/${repositoryId}/deployment-plan`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return mapPlan(await readJson<ApiScmDeploymentPlan>(response));
}

export async function discoverScmRepositories(
  workspaceId: string,
  connectionId: string,
  query = '',
  limit = 20,
): Promise<OpsScmDiscoveredRepository[]> {
  const search = new URLSearchParams({ query, limit: String(limit) });
  const response = await fetch(apiUrl(`/api/v1/workspaces/${workspaceId}/scm/connections/${connectionId}/discover-repositories?${search.toString()}`));
  const payload = await readJson<{ items: ApiScmDiscoveredRepository[] }>(response);
  return (payload.items ?? []).map(mapDiscoveredRepository);
}
