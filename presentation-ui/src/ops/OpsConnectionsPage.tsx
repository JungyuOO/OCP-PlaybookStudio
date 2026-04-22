import type { FormEvent } from 'react';
import { useEffect, useMemo, useState } from 'react';
import { createOpsConnection, disconnectOpsConnection, listOpsConnections } from './connectionsApi';
import { listOpsWorkspaces } from './api';
import { OpsShell } from './OpsShell';
import type {
  OpsConnectionProfile,
  OpsConnectionRequest,
  OpsWorkspaceRecord,
} from './types';

const DEFAULT_FORM: OpsConnectionRequest = {
  workspaceId: '',
  clusterUrl: '',
  authMode: 'token',
  verifySsl: false,
  defaultNamespace: 'demo',
  displayName: '',
  saveProfile: true,
  token: '',
  username: '',
  password: '',
};

function formatTimestamp(value: string) {
  if (!value) return 'not recorded';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('ko-KR', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

export default function OpsConnectionsPage() {
  const [workspaces, setWorkspaces] = useState<OpsWorkspaceRecord[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState('');
  const [connections, setConnections] = useState<OpsConnectionProfile[]>([]);
  const [activeConnectionId, setActiveConnectionId] = useState('');
  const [form, setForm] = useState<OpsConnectionRequest>(DEFAULT_FORM);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('Create and store cluster connection profiles per workspace.');

  async function refreshWorkspaces() {
    const next = await listOpsWorkspaces();
    setWorkspaces(next);
    setSelectedWorkspaceId((current) => current || next[0]?.workspaceId || '');
    setForm((current) => ({ ...current, workspaceId: current.workspaceId || next[0]?.workspaceId || '' }));
    return next;
  }

  async function refreshConnections(workspaceId: string) {
    const payload = await listOpsConnections(workspaceId);
    setConnections(payload.items);
    setActiveConnectionId((current) => current || payload.items[0]?.connectionId || '');
  }

  useEffect(() => {
    async function run() {
      setLoading(true);
      setError('');
      try {
        const nextWorkspaces = await refreshWorkspaces();
        await refreshConnections(nextWorkspaces[0]?.workspaceId || '');
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : 'Failed to load connections.');
      } finally {
        setLoading(false);
      }
    }
    void run();
  }, []);

  useEffect(() => {
    if (!selectedWorkspaceId) return;
    setForm((current) => ({ ...current, workspaceId: selectedWorkspaceId }));
    void refreshConnections(selectedWorkspaceId);
  }, [selectedWorkspaceId]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      const status = await createOpsConnection({
        ...form,
        workspaceId: selectedWorkspaceId,
      });
      if (status.connection) {
        setActiveConnectionId(status.connection.connectionId);
      }
      setMessage(status.message || 'Connection profile created.');
      await refreshConnections(selectedWorkspaceId);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Failed to create connection profile.');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDisconnect(connectionId: string) {
    setError('');
    try {
      const status = await disconnectOpsConnection(connectionId);
      setMessage(status.message || 'Connection disconnected.');
      if (activeConnectionId === connectionId) {
        setActiveConnectionId('');
      }
      await refreshConnections(selectedWorkspaceId);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Failed to disconnect connection profile.');
    }
  }

  const activeConnection = useMemo(
    () => connections.find((item) => item.connectionId === activeConnectionId) ?? null,
    [connections, activeConnectionId],
  );

  return (
    <OpsShell
      eyebrow="OCP Ops Connections"
      title="Workspace-scoped cluster connections"
      description="This surface now persists and lists cluster connection profiles inside the PlayBookStudio runtime. For the current cluster, the practical live path is `verify_ssl=false` with the `demo` namespace as the smoke-test baseline."
    >
      {error ? <div className="ops-alert glass-panel">{error}</div> : null}
      <div className="ops-detail-card glass-panel">
        Live note: the current OCP target uses a self-signed certificate chain, so `Verify SSL` should stay off unless the CA is trusted locally. Smoke-test namespace is `demo`.
      </div>

      <div className="ops-two-column">
        <section className="ops-card glass-panel">
          <div className="ops-section-head">
            <div>
              <span className="ops-section-eyebrow">Create connection</span>
              <h2>Register an operational cluster profile</h2>
            </div>
          </div>

          <form className="ops-form" onSubmit={handleSubmit}>
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
              <span>Cluster URL</span>
              <input
                value={form.clusterUrl}
                onChange={(event) => setForm((current) => ({ ...current, clusterUrl: event.target.value }))}
                placeholder="https://api.cluster.example.com:6443"
              />
            </label>

            <div className="ops-inline-grid">
              <label className="ops-field">
                <span>Auth mode</span>
                <select
                  value={form.authMode}
                  onChange={(event) => setForm((current) => ({ ...current, authMode: event.target.value as OpsConnectionRequest['authMode'] }))}
                >
                  <option value="token">token</option>
                  <option value="password">password</option>
                  <option value="oauth_future">oauth_future</option>
                </select>
              </label>
              <label className="ops-field">
                <span>Default namespace</span>
                <input
                  value={form.defaultNamespace ?? ''}
                  onChange={(event) => setForm((current) => ({ ...current, defaultNamespace: event.target.value }))}
                  placeholder="demo"
                />
              </label>
            </div>

            <div className="ops-inline-grid">
              <label className="ops-field">
                <span>Display name</span>
                <input
                  value={form.displayName ?? ''}
                  onChange={(event) => setForm((current) => ({ ...current, displayName: event.target.value }))}
                  placeholder="prod-cluster"
                />
              </label>
              <label className="ops-field">
                <span>Username hint</span>
                <input
                  value={form.username ?? ''}
                  onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))}
                  placeholder="developer"
                />
              </label>
            </div>

            {form.authMode === 'token' ? (
              <label className="ops-field">
                <span>Bearer token</span>
                <input
                  type="password"
                  value={form.token ?? ''}
                  onChange={(event) => setForm((current) => ({ ...current, token: event.target.value }))}
                  placeholder="sha256~..."
                />
              </label>
            ) : null}

            {form.authMode === 'password' ? (
              <label className="ops-field">
                <span>Password</span>
                <input
                  type="password"
                  value={form.password ?? ''}
                  onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
                  placeholder="Password"
                />
              </label>
            ) : null}

            <div className="ops-check-grid">
              <label className="ops-check">
                <input
                  type="checkbox"
                  checked={form.verifySsl}
                  onChange={(event) => setForm((current) => ({ ...current, verifySsl: event.target.checked }))}
                />
                <span>Verify SSL</span>
              </label>
              <label className="ops-check">
                <input
                  type="checkbox"
                  checked={form.saveProfile ?? true}
                  onChange={(event) => setForm((current) => ({ ...current, saveProfile: event.target.checked }))}
                />
                <span>Save profile</span>
              </label>
            </div>

            <button
              type="submit"
              className="ops-primary-action"
              disabled={submitting || !selectedWorkspaceId || !form.clusterUrl.trim()}
            >
              {submitting ? 'Creating connection...' : 'Create connection'}
            </button>
          </form>
        </section>

        <section className="ops-card glass-panel">
          <div className="ops-section-head">
            <div>
              <span className="ops-section-eyebrow">Saved profiles</span>
              <h2>Connection inventory</h2>
            </div>
            <span className="ops-meta-chip">{loading ? 'Loading...' : `${connections.length} profiles`}</span>
          </div>

          <div className="ops-stack">
            {connections.length === 0 ? (
              <div className="ops-empty">No saved profiles for the selected workspace yet.</div>
            ) : (
              connections.map((item) => {
                const active = item.connectionId === activeConnectionId;
                return (
                  <div key={item.connectionId} className={`ops-list-item ${active ? 'is-active' : ''}`}>
                    <button
                      type="button"
                      className="ops-list-main ops-plain-button"
                      onClick={() => setActiveConnectionId(item.connectionId)}
                    >
                      <strong>{item.displayName || item.clusterUrl}</strong>
                      <span>{item.clusterUrl}</span>
                    </button>
                    <div className="ops-list-meta">
                      <span>{item.authMode}</span>
                      <button type="button" className="ops-link-button" onClick={() => void handleDisconnect(item.connectionId)}>
                        Disconnect
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          <div className="ops-detail-card">
            <span className="ops-section-eyebrow">Active profile</span>
            {activeConnection ? (
              <div className="ops-detail-grid">
                <div>
                  <strong>Status</strong>
                  <span>{activeConnection.status}</span>
                </div>
                <div>
                  <strong>Namespace</strong>
                  <span>{activeConnection.defaultNamespace || 'demo'}</span>
                </div>
                <div>
                  <strong>User hint</strong>
                  <span>{activeConnection.usernameHint || 'not set'}</span>
                </div>
                <div>
                  <strong>Expires</strong>
                  <span>{formatTimestamp(activeConnection.expiresAt)}</span>
                </div>
                <div>
                  <strong>Secret ref</strong>
                  <span>{activeConnection.secretRef}</span>
                </div>
                <div>
                  <strong>Message</strong>
                  <span>{message}</span>
                </div>
              </div>
            ) : (
              <div className="ops-empty">Select a connection profile to inspect its metadata.</div>
            )}
          </div>
        </section>
      </div>
    </OpsShell>
  );
}
