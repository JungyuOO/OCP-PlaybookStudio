import type {
  OpsConnectionListResponse,
  OpsConnectionProfile,
  OpsConnectionRequest,
  OpsConnectionStatusResponse,
} from './types';

type ApiConnectionProfile = {
  workspace_id: string;
  connection_id: string;
  display_name: string;
  cluster_url: string;
  auth_mode: OpsConnectionProfile['authMode'];
  verify_ssl: boolean;
  default_namespace: string;
  username_hint: string;
  secret_ref: string;
  save_profile: boolean;
  status: string;
  last_verified_at: string;
  expires_at: string;
};

type ApiConnectionStatusResponse = {
  connected: boolean;
  connection: ApiConnectionProfile | null;
  message: string;
};

type ApiConnectionListResponse = {
  items: ApiConnectionProfile[];
  count: number;
  updated_at: string;
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

function mapProfile(input: ApiConnectionProfile): OpsConnectionProfile {
  return {
    workspaceId: input.workspace_id ?? '',
    connectionId: input.connection_id,
    displayName: input.display_name,
    clusterUrl: input.cluster_url,
    authMode: input.auth_mode,
    verifySsl: input.verify_ssl,
    defaultNamespace: input.default_namespace,
    usernameHint: input.username_hint,
    secretRef: input.secret_ref,
    saveProfile: input.save_profile,
    status: input.status,
    lastVerifiedAt: input.last_verified_at,
    expiresAt: input.expires_at,
  };
}

function mapStatus(input: ApiConnectionStatusResponse): OpsConnectionStatusResponse {
  return {
    connected: input.connected,
    connection: input.connection ? mapProfile(input.connection) : null,
    message: input.message,
  };
}

function serializeRequest(request: OpsConnectionRequest) {
  return {
    workspace_id: request.workspaceId ?? '',
    cluster_url: request.clusterUrl,
    auth_mode: request.authMode,
    verify_ssl: request.verifySsl,
    default_namespace: request.defaultNamespace ?? '',
    display_name: request.displayName ?? '',
    save_profile: request.saveProfile ?? false,
    token: request.token ?? '',
    username: request.username ?? '',
    password: request.password ?? '',
  };
}

export async function listOpsConnections(workspaceId = ''): Promise<OpsConnectionListResponse> {
  const query = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : '';
  const response = await fetch(apiUrl(`/api/v1/auth/ocp/profiles${query}`));
  const payload = await readJson<ApiConnectionListResponse>(response);
  return {
    items: (payload.items ?? []).map(mapProfile),
    count: payload.count ?? 0,
    updatedAt: payload.updated_at ?? '',
  };
}

export async function createOpsConnection(request: OpsConnectionRequest): Promise<OpsConnectionStatusResponse> {
  const response = await fetch(apiUrl('/api/v1/auth/ocp/connect'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(serializeRequest(request)),
  });
  return mapStatus(await readJson<ApiConnectionStatusResponse>(response));
}

export async function disconnectOpsConnection(connectionId: string): Promise<OpsConnectionStatusResponse> {
  const response = await fetch(apiUrl('/api/v1/auth/ocp/disconnect'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ connection_id: connectionId }),
  });
  return mapStatus(await readJson<ApiConnectionStatusResponse>(response));
}
