import type {
  OpsLiveNamespaceListResponse,
  OpsLiveResourceDetailResponse,
  OpsLiveResourceKind,
  OpsLiveResourceListResponse,
  OpsLiveResourceSummary,
} from './types';

type ApiOcpLiveResourceSummary = {
  name: string;
  namespace: string;
  kind: string;
  created_at: string;
  phase: string;
  node_name: string;
  ready_replicas: number;
  replicas: number;
  type: string;
  cluster_ip: string;
  host: string;
  to: string;
};

type ApiOcpNamespaceListResponse = {
  connection_id: string;
  cluster_url: string;
  count: number;
  items: string[];
};

type ApiOcpResourceListResponse = {
  connection_id: string;
  cluster_url: string;
  resource: string;
  namespace: string;
  count: number;
  items: ApiOcpLiveResourceSummary[];
};

type ApiOcpResourceDetailResponse = {
  connection_id: string;
  cluster_url: string;
  resource: string;
  namespace: string;
  name: string;
  kind: string;
  manifest_yaml: string;
  manifest_json: Record<string, unknown>;
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

function mapResourceSummary(input: ApiOcpLiveResourceSummary): OpsLiveResourceSummary {
  return {
    name: input.name,
    namespace: input.namespace,
    kind: input.kind,
    createdAt: input.created_at,
    phase: input.phase,
    nodeName: input.node_name,
    readyReplicas: input.ready_replicas,
    replicas: input.replicas,
    type: input.type,
    clusterIp: input.cluster_ip,
    host: input.host,
    to: input.to,
  };
}

export async function getOpsNamespaces(connectionId: string): Promise<OpsLiveNamespaceListResponse> {
  const response = await fetch(apiUrl(`/api/v1/ocp/namespaces/${connectionId}`));
  const input = await readJson<ApiOcpNamespaceListResponse>(response);
  return {
    connectionId: input.connection_id,
    clusterUrl: input.cluster_url,
    count: input.count,
    items: input.items ?? [],
  };
}

export async function getOpsResources(
  connectionId: string,
  resource: OpsLiveResourceKind,
  namespace: string,
): Promise<OpsLiveResourceListResponse> {
  const search = new URLSearchParams({ resource, namespace });
  const response = await fetch(apiUrl(`/api/v1/ocp/resources/${connectionId}?${search.toString()}`));
  const input = await readJson<ApiOcpResourceListResponse>(response);
  return {
    connectionId: input.connection_id,
    clusterUrl: input.cluster_url,
    resource: input.resource,
    namespace: input.namespace,
    count: input.count,
    items: (input.items ?? []).map(mapResourceSummary),
  };
}

export async function getOpsResourceDetail(
  connectionId: string,
  resource: OpsLiveResourceKind,
  namespace: string,
  name: string,
): Promise<OpsLiveResourceDetailResponse> {
  const search = new URLSearchParams({ resource, namespace, name });
  const response = await fetch(apiUrl(`/api/v1/ocp/resource-detail/${connectionId}?${search.toString()}`));
  const input = await readJson<ApiOcpResourceDetailResponse>(response);
  return {
    connectionId: input.connection_id,
    clusterUrl: input.cluster_url,
    resource: input.resource,
    namespace: input.namespace,
    name: input.name,
    kind: input.kind,
    manifestYaml: input.manifest_yaml,
    manifestJson: input.manifest_json ?? {},
  };
}
