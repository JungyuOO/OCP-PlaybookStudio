export type OpsOverviewResponse = {
  connectionId: string;
  clusterUrl: string;
  defaultNamespace: string;
  namespaceCount: number;
  namespaceSample: string[];
  resourceCounts: Record<string, number>;
  message: string;
};

export type OpsMetricPoint = {
  timestamp: number;
  value: number;
};

export type OpsMetricSeries = {
  metricId: string;
  label: string;
  unit: string;
  currentValue: number;
  capacityValue: number;
  availableValue: number;
  points: OpsMetricPoint[];
};

export type OpsDashboardMetricsResponse = {
  connectionId: string;
  clusterUrl: string;
  window: string;
  step: string;
  series: OpsMetricSeries[];
};

type ApiOverviewResponse = {
  connection_id: string;
  cluster_url: string;
  default_namespace: string;
  namespace_count: number;
  namespace_sample: string[];
  resource_counts: Record<string, number>;
  message: string;
};

type ApiMetricPoint = {
  timestamp: number;
  value: number;
};

type ApiMetricSeries = {
  metric_id: string;
  label: string;
  unit: string;
  current_value: number;
  capacity_value: number;
  available_value: number;
  points: ApiMetricPoint[];
};

type ApiMetricsResponse = {
  connection_id: string;
  cluster_url: string;
  window: string;
  step: string;
  series: ApiMetricSeries[];
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

function mapOverview(input: ApiOverviewResponse): OpsOverviewResponse {
  return {
    connectionId: input.connection_id,
    clusterUrl: input.cluster_url,
    defaultNamespace: input.default_namespace,
    namespaceCount: input.namespace_count,
    namespaceSample: input.namespace_sample ?? [],
    resourceCounts: input.resource_counts ?? {},
    message: input.message ?? '',
  };
}

function mapMetrics(input: ApiMetricsResponse): OpsDashboardMetricsResponse {
  return {
    connectionId: input.connection_id,
    clusterUrl: input.cluster_url,
    window: input.window,
    step: input.step,
    series: (input.series ?? []).map((item) => ({
      metricId: item.metric_id,
      label: item.label,
      unit: item.unit,
      currentValue: item.current_value,
      capacityValue: item.capacity_value,
      availableValue: item.available_value,
      points: (item.points ?? []).map((point) => ({
        timestamp: point.timestamp,
        value: point.value,
      })),
    })),
  };
}

export async function getOpsOverview(connectionId: string): Promise<OpsOverviewResponse> {
  const response = await fetch(apiUrl(`/api/v1/ocp/overview/${connectionId}`));
  return mapOverview(await readJson<ApiOverviewResponse>(response));
}

export async function getOpsMetrics(
  connectionId: string,
  options?: { window?: string; step?: string },
): Promise<OpsDashboardMetricsResponse> {
  const search = new URLSearchParams({
    window: options?.window ?? '1h',
    step: options?.step ?? '5m',
  });
  const response = await fetch(apiUrl(`/api/v1/ocp/metrics/${connectionId}?${search.toString()}`));
  return mapMetrics(await readJson<ApiMetricsResponse>(response));
}
