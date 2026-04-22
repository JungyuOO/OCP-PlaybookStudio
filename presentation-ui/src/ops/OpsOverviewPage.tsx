import { useEffect, useMemo, useState } from 'react';
import { listOpsWorkspaces } from './api';
import { listOpsConnections } from './connectionsApi';
import { OpsShell } from './OpsShell';
import { getOpsMetrics, getOpsOverview, type OpsDashboardMetricsResponse, type OpsOverviewResponse } from './overviewApi';
import type { OpsConnectionProfile, OpsWorkspaceRecord } from './types';

function formatMetricValue(value: number, unit: string) {
  if (unit === '%') return `${Math.round(value)}%`;
  return `${Math.round(value)} ${unit}`.trim();
}

export default function OpsOverviewPage() {
  const [workspaces, setWorkspaces] = useState<OpsWorkspaceRecord[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState('');
  const [connections, setConnections] = useState<OpsConnectionProfile[]>([]);
  const [selectedConnectionId, setSelectedConnectionId] = useState('');
  const [overview, setOverview] = useState<OpsOverviewResponse | null>(null);
  const [metrics, setMetrics] = useState<OpsDashboardMetricsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    async function bootstrap() {
      setLoading(true);
      setError('');
      try {
        const nextWorkspaces = await listOpsWorkspaces();
        setWorkspaces(nextWorkspaces);
        setSelectedWorkspaceId(nextWorkspaces[0]?.workspaceId || '');
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : 'Failed to load overview context.');
      } finally {
        setLoading(false);
      }
    }
    void bootstrap();
  }, []);

  useEffect(() => {
    if (!selectedWorkspaceId) {
      setConnections([]);
      setSelectedConnectionId('');
      return;
    }
    async function loadConnections() {
      try {
        const payload = await listOpsConnections(selectedWorkspaceId);
        setConnections(payload.items);
        setSelectedConnectionId((current) => current || payload.items[0]?.connectionId || '');
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : 'Failed to load connection profiles.');
      }
    }
    void loadConnections();
  }, [selectedWorkspaceId]);

  useEffect(() => {
    if (!selectedConnectionId) {
      setOverview(null);
      setMetrics(null);
      return;
    }
    async function loadOverview() {
      setLoading(true);
      setError('');
      try {
        const [nextOverview, nextMetrics] = await Promise.all([
          getOpsOverview(selectedConnectionId),
          getOpsMetrics(selectedConnectionId),
        ]);
        setOverview(nextOverview);
        setMetrics(nextMetrics);
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : 'Failed to load overview payload.');
      } finally {
        setLoading(false);
      }
    }
    void loadOverview();
  }, [selectedConnectionId]);

  const selectedConnection = useMemo(
    () => connections.find((item) => item.connectionId === selectedConnectionId) ?? null,
    [connections, selectedConnectionId],
  );

  const statCards = useMemo(() => {
    if (!overview) return [];
    return [
      { label: 'Nodes', value: overview.resourceCounts.nodes ?? 0 },
      { label: 'Namespaces', value: overview.namespaceCount },
      { label: 'Pods', value: overview.resourceCounts.pods ?? 0 },
      { label: 'Services', value: overview.resourceCounts.services ?? 0 },
      { label: 'Deployments', value: overview.resourceCounts.deployments ?? 0 },
      { label: 'Routes', value: overview.resourceCounts.routes ?? 0 },
    ];
  }, [overview]);

  return (
    <OpsShell
      eyebrow="OCP Ops Overview"
      title="Operational overview"
      description="This page now binds the selected workspace and stored connection profile to an overview contract. The payload is synthetic for now, but the `/api/v1/ocp/*` surface is now route-stable."
    >
      {error ? <div className="ops-alert glass-panel">{error}</div> : null}

      <div className="ops-card glass-panel">
        <div className="ops-section-head">
          <div>
            <span className="ops-section-eyebrow">Overview context</span>
            <h2>Select workspace and connection</h2>
          </div>
          <span className="ops-meta-chip">
            {loading ? 'Refreshing...' : selectedConnection?.displayName || selectedConnection?.clusterUrl || 'No connection selected'}
          </span>
        </div>

        <div className="ops-inline-grid">
          <label className="ops-field">
            <span>Workspace</span>
            <select value={selectedWorkspaceId} onChange={(event) => setSelectedWorkspaceId(event.target.value)}>
              <option value="">Select workspace</option>
              {workspaces.map((item) => (
                <option key={item.workspaceId} value={item.workspaceId}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <label className="ops-field">
            <span>Connection profile</span>
            <select value={selectedConnectionId} onChange={(event) => setSelectedConnectionId(event.target.value)}>
              <option value="">Select connection</option>
              {connections.map((item) => (
                <option key={item.connectionId} value={item.connectionId}>
                  {item.displayName || item.clusterUrl}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {overview ? (
        <>
          <div className="ops-stat-grid">
            {statCards.map((item) => (
              <div key={item.label} className="ops-stat-card glass-panel">
                <span className="ops-section-eyebrow">{item.label}</span>
                <strong>{item.value}</strong>
              </div>
            ))}
          </div>

          <div className="ops-two-column">
            <section className="ops-card glass-panel">
              <div className="ops-section-head">
                <div>
                  <span className="ops-section-eyebrow">Connection posture</span>
                  <h2>Stored connection context</h2>
                </div>
              </div>
              <div className="ops-detail-grid">
                <div>
                  <strong>Cluster URL</strong>
                  <span>{overview.clusterUrl}</span>
                </div>
                <div>
                  <strong>Default namespace</strong>
                  <span>{overview.defaultNamespace || 'not set'}</span>
                </div>
                <div>
                  <strong>Profile status</strong>
                  <span>{selectedConnection?.status || 'unknown'}</span>
                </div>
                <div>
                  <strong>Message</strong>
                  <span>{overview.message}</span>
                </div>
              </div>
            </section>

            <section className="ops-card glass-panel">
              <div className="ops-section-head">
                <div>
                  <span className="ops-section-eyebrow">Namespace sample</span>
                  <h2>Visible namespace window</h2>
                </div>
              </div>
              <div className="ops-pill-row">
                {overview.namespaceSample.map((item) => (
                  <span key={item} className="ops-pill">
                    {item}
                  </span>
                ))}
              </div>
            </section>
          </div>
        </>
      ) : (
        <div className="ops-empty glass-panel">Select a workspace and connection profile to load the overview.</div>
      )}

      {metrics ? (
        <div className="ops-metric-grid">
          {metrics.series.map((series) => {
            const usage = series.capacityValue > 0 ? Math.min((series.currentValue / series.capacityValue) * 100, 100) : 0;
            return (
              <section key={series.metricId} className="ops-card glass-panel">
                <div className="ops-section-head">
                  <div>
                    <span className="ops-section-eyebrow">{series.metricId}</span>
                    <h2>{series.label}</h2>
                  </div>
                  <span className="ops-meta-chip">{formatMetricValue(series.currentValue, series.unit)}</span>
                </div>
                <div className="ops-meter">
                  <div className="ops-meter-fill" style={{ width: `${Math.max(usage, 8)}%` }} />
                </div>
                <div className="ops-detail-grid">
                  <div>
                    <strong>Current</strong>
                    <span>{formatMetricValue(series.currentValue, series.unit)}</span>
                  </div>
                  <div>
                    <strong>Capacity</strong>
                    <span>{formatMetricValue(series.capacityValue, series.unit)}</span>
                  </div>
                  <div>
                    <strong>Available</strong>
                    <span>{formatMetricValue(series.availableValue, series.unit)}</span>
                  </div>
                  <div>
                    <strong>Samples</strong>
                    <span>{series.points.length}</span>
                  </div>
                </div>
              </section>
            );
          })}
        </div>
      ) : null}
    </OpsShell>
  );
}
