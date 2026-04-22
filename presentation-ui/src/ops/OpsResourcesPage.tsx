import { useEffect, useMemo, useState } from 'react';
import { listOpsWorkspaces } from './api';
import { listOpsConnections } from './connectionsApi';
import { OpsShell } from './OpsShell';
import { getOpsNamespaces, getOpsResourceDetail, getOpsResources } from './resourcesApi';
import type {
  OpsConnectionProfile,
  OpsLiveNamespaceListResponse,
  OpsLiveResourceDetailResponse,
  OpsLiveResourceKind,
  OpsLiveResourceListResponse,
  OpsLiveResourceSummary,
  OpsWorkspaceRecord,
} from './types';

const RESOURCE_OPTIONS: OpsLiveResourceKind[] = ['pods', 'deployments', 'services', 'routes', 'events'];

function formatTimestamp(value: string) {
  if (!value) return 'not recorded';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('ko-KR', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

export default function OpsResourcesPage() {
  const [workspaces, setWorkspaces] = useState<OpsWorkspaceRecord[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState('');
  const [connections, setConnections] = useState<OpsConnectionProfile[]>([]);
  const [selectedConnectionId, setSelectedConnectionId] = useState('');
  const [resource, setResource] = useState<OpsLiveResourceKind>('pods');
  const [namespace, setNamespace] = useState('');
  const [namespaces, setNamespaces] = useState<OpsLiveNamespaceListResponse | null>(null);
  const [resourceData, setResourceData] = useState<OpsLiveResourceListResponse | null>(null);
  const [selectedItem, setSelectedItem] = useState<OpsLiveResourceSummary | null>(null);
  const [resourceDetail, setResourceDetail] = useState<OpsLiveResourceDetailResponse | null>(null);
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
        setError(nextError instanceof Error ? nextError.message : 'Failed to bootstrap resources.');
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
      setNamespaces(null);
      setNamespace('');
      return;
    }
    async function loadNamespaces() {
      try {
        const payload = await getOpsNamespaces(selectedConnectionId);
        setNamespaces(payload);
        setNamespace((current) => current || payload.items[0] || '');
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : 'Failed to load namespaces.');
      }
    }
    void loadNamespaces();
  }, [selectedConnectionId]);

  useEffect(() => {
    if (!selectedConnectionId || !namespace) {
      setResourceData(null);
      setSelectedItem(null);
      return;
    }
    async function loadResources() {
      setLoading(true);
      setError('');
      try {
        const payload = await getOpsResources(selectedConnectionId, resource, namespace);
        setResourceData(payload);
        setSelectedItem(payload.items[0] ?? null);
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : 'Failed to load resources.');
      } finally {
        setLoading(false);
      }
    }
    void loadResources();
  }, [selectedConnectionId, resource, namespace]);

  useEffect(() => {
    if (!selectedConnectionId || !selectedItem || !namespace) {
      setResourceDetail(null);
      return;
    }
    const selectedName = selectedItem.name;
    async function loadDetail() {
      try {
        const payload = await getOpsResourceDetail(selectedConnectionId, resource, namespace, selectedName);
        setResourceDetail(payload);
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : 'Failed to load resource detail.');
      }
    }
    void loadDetail();
  }, [selectedConnectionId, selectedItem, resource, namespace]);

  const selectedConnection = useMemo(
    () => connections.find((item) => item.connectionId === selectedConnectionId) ?? null,
    [connections, selectedConnectionId],
  );

  return (
    <OpsShell
      eyebrow="OCP Ops Resources"
      title="Resource explorer"
      description="This page now uses the selected connection profile to browse synthetic namespaces, resources, and manifest detail. The route contract matches the future live OCP surface."
    >
      {error ? <div className="ops-alert glass-panel">{error}</div> : null}

      <div className="ops-card glass-panel">
        <div className="ops-section-head">
          <div>
            <span className="ops-section-eyebrow">Resource context</span>
            <h2>Select workspace, connection, namespace, and resource kind</h2>
          </div>
          <span className="ops-meta-chip">
            {selectedConnection?.displayName || selectedConnection?.clusterUrl || 'No connection selected'}
          </span>
        </div>

        <div className="ops-context-grid">
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
            <span>Connection</span>
            <select value={selectedConnectionId} onChange={(event) => setSelectedConnectionId(event.target.value)}>
              <option value="">Select connection</option>
              {connections.map((item) => (
                <option key={item.connectionId} value={item.connectionId}>
                  {item.displayName || item.clusterUrl}
                </option>
              ))}
            </select>
          </label>
          <label className="ops-field">
            <span>Namespace</span>
            <select value={namespace} onChange={(event) => setNamespace(event.target.value)}>
              <option value="">Select namespace</option>
              {(namespaces?.items ?? []).map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="ops-chip-row">
          {RESOURCE_OPTIONS.map((item) => (
            <button
              key={item}
              type="button"
              className={`ops-chip ${resource === item ? 'is-active' : ''}`}
              onClick={() => setResource(item)}
            >
              {item}
            </button>
          ))}
        </div>
      </div>

      <div className="ops-two-column">
        <section className="ops-card glass-panel">
          <div className="ops-section-head">
            <div>
              <span className="ops-section-eyebrow">Resource list</span>
              <h2>{resourceData?.count ?? 0} items in scope</h2>
            </div>
            <span className="ops-meta-chip">{loading ? 'Refreshing...' : resource}</span>
          </div>

          <div className="ops-stack">
            {(resourceData?.items ?? []).length > 0 ? (
              resourceData?.items.map((item) => {
                const active = selectedItem?.name === item.name;
                return (
                  <button
                    key={item.name}
                    type="button"
                    className={`ops-list-item ${active ? 'is-active' : ''}`}
                    onClick={() => setSelectedItem(item)}
                  >
                    <div className="ops-list-main">
                      <strong>{item.name}</strong>
                      <span>{item.kind} · {item.phase || item.type || 'no status'}</span>
                    </div>
                    <div className="ops-list-meta">
                      <span>{item.namespace}</span>
                      {item.replicas ? <span>{item.readyReplicas}/{item.replicas}</span> : null}
                    </div>
                  </button>
                );
              })
            ) : (
              <div className="ops-empty">Choose a connection and namespace to load resources.</div>
            )}
          </div>
        </section>

        <section className="ops-card glass-panel">
          <div className="ops-section-head">
            <div>
              <span className="ops-section-eyebrow">Manifest detail</span>
              <h2>{resourceDetail?.name || 'No resource selected'}</h2>
            </div>
          </div>

          {resourceDetail ? (
            <>
              <div className="ops-detail-grid">
                <div>
                  <strong>Kind</strong>
                  <span>{resourceDetail.kind}</span>
                </div>
                <div>
                  <strong>Namespace</strong>
                  <span>{resourceDetail.namespace}</span>
                </div>
                <div>
                  <strong>Connection</strong>
                  <span>{resourceDetail.connectionId}</span>
                </div>
                <div>
                  <strong>Generated</strong>
                  <span>{selectedItem?.createdAt ? formatTimestamp(selectedItem.createdAt) : 'n/a'}</span>
                </div>
              </div>
              <pre className="ops-code-block">
                <code>{resourceDetail.manifestYaml}</code>
              </pre>
            </>
          ) : (
            <div className="ops-empty">Select a resource to inspect its manifest payload.</div>
          )}
        </section>
      </div>
    </OpsShell>
  );
}
