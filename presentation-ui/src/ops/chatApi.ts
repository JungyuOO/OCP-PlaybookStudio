import type {
  OpsChatHistoryTurn,
  OpsChatResponse,
  OpsLiveResourceDetailResponse,
  OpsLiveResourceSummary,
} from './types';

type ApiResourceSummary = {
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

type ApiResourceDetail = {
  connection_id: string;
  cluster_url: string;
  resource: string;
  namespace: string;
  name: string;
  kind: string;
  manifest_yaml: string;
  manifest_json: Record<string, unknown>;
};

type ApiOpsChatResponse = {
  connection_id: string;
  cluster_url: string;
  mode: string;
  resource: string;
  namespace: string;
  answer: string;
  items: ApiResourceSummary[];
  detail?: ApiResourceDetail;
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

function mapResourceSummary(input: ApiResourceSummary): OpsLiveResourceSummary {
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

function mapDetail(input?: ApiResourceDetail): OpsLiveResourceDetailResponse | null {
  if (!input) return null;
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

export async function sendOpsChat(
  connectionId: string,
  message: string,
  namespace = '',
  history: OpsChatHistoryTurn[] = [],
): Promise<OpsChatResponse> {
  const response = await fetch(apiUrl('/api/v1/ops/chat'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      connection_id: connectionId,
      message,
      namespace,
      history: history.map((item) => ({ role: item.role, text: item.text })),
    }),
  });
  const input = await readJson<ApiOpsChatResponse>(response);
  return {
    connectionId: input.connection_id,
    clusterUrl: input.cluster_url,
    mode: input.mode,
    resource: input.resource,
    namespace: input.namespace,
    answer: input.answer,
    items: (input.items ?? []).map(mapResourceSummary),
    detail: mapDetail(input.detail),
  };
}
