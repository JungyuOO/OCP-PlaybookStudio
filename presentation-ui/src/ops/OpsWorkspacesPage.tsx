import type { FormEvent } from 'react';
import { useEffect, useMemo, useState } from 'react';
import { createOpsWorkspace, listOpsWorkspaces } from './api';
import { OpsShell } from './OpsShell';
import type { OpsWorkspaceCreateRequest, OpsWorkspaceRecord } from './types';

const DEFAULT_FORM: OpsWorkspaceCreateRequest = {
  name: '',
  environment: 'dev',
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

export default function OpsWorkspacesPage() {
  const [items, setItems] = useState<OpsWorkspaceRecord[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState('');
  const [form, setForm] = useState<OpsWorkspaceCreateRequest>(DEFAULT_FORM);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  async function refresh() {
    setLoading(true);
    setError('');
    try {
      const next = await listOpsWorkspaces();
      setItems(next);
      setSelectedWorkspaceId((current) => current || next[0]?.workspaceId || '');
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Failed to load workspaces.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      const created = await createOpsWorkspace(form);
      setForm(DEFAULT_FORM);
      await refresh();
      setSelectedWorkspaceId(created.workspaceId);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Failed to create workspace.');
    } finally {
      setSubmitting(false);
    }
  }

  const selectedWorkspace = useMemo(
    () => items.find((item) => item.workspaceId === selectedWorkspaceId) ?? null,
    [items, selectedWorkspaceId],
  );

  return (
    <OpsShell
      eyebrow="OCP Ops Workspaces"
      title="Workspace-scoped operational state"
      description="Workspaces are the anchor for cluster connections, models, resources, actions, and SCM delivery. This page already uses the existing `/api/v1/workspaces` contract from the OCP Ops project."
    >
      {error ? <div className="ops-alert glass-panel">{error}</div> : null}

      <div className="ops-two-column">
        <section className="ops-card glass-panel">
          <div className="ops-section-head">
            <div>
              <span className="ops-section-eyebrow">Workspace list</span>
              <h2>Available workspaces</h2>
            </div>
            <button type="button" className="ops-secondary-action" onClick={() => void refresh()} disabled={loading}>
              {loading ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>

          <div className="ops-stack">
            {items.length === 0 ? (
              <div className="ops-empty">No workspaces are visible yet. Create the first workspace to start the OCP Ops lane.</div>
            ) : (
              items.map((item) => {
                const active = item.workspaceId === selectedWorkspaceId;
                return (
                  <button
                    key={item.workspaceId}
                    type="button"
                    className={`ops-list-item ${active ? 'is-active' : ''}`}
                    onClick={() => setSelectedWorkspaceId(item.workspaceId)}
                  >
                    <div className="ops-list-main">
                      <strong>{item.name}</strong>
                      <span>{item.environment || 'environment not set'}</span>
                    </div>
                    <div className="ops-list-meta">
                      <span>{item.slug}</span>
                      {active ? <span className="ops-badge">Active</span> : null}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </section>

        <section className="ops-card glass-panel">
          <div className="ops-section-head">
            <div>
              <span className="ops-section-eyebrow">Create workspace</span>
              <h2>Bootstrap a customer context</h2>
            </div>
          </div>

          <form className="ops-form" onSubmit={handleSubmit}>
            <label className="ops-field">
              <span>Name</span>
              <input
                value={form.name ?? ''}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                placeholder="Production Cluster Workspace"
              />
            </label>

            <label className="ops-field">
              <span>Environment</span>
              <select
                value={form.environment ?? 'dev'}
                onChange={(event) => setForm((current) => ({ ...current, environment: event.target.value }))}
              >
                <option value="dev">dev</option>
                <option value="staging">staging</option>
                <option value="prod">prod</option>
              </select>
            </label>

            <button type="submit" className="ops-primary-action" disabled={submitting || !form.name.trim()}>
              {submitting ? 'Creating workspace...' : 'Create workspace'}
            </button>
          </form>

          <div className="ops-detail-card">
            <span className="ops-section-eyebrow">Selected workspace</span>
            {selectedWorkspace ? (
              <div className="ops-detail-grid">
                <div>
                  <strong>Name</strong>
                  <span>{selectedWorkspace.name}</span>
                </div>
                <div>
                  <strong>Slug</strong>
                  <span>{selectedWorkspace.slug}</span>
                </div>
                <div>
                  <strong>Environment</strong>
                  <span>{selectedWorkspace.environment || 'not set'}</span>
                </div>
                <div>
                  <strong>Updated</strong>
                  <span>{formatTimestamp(selectedWorkspace.updatedAt)}</span>
                </div>
              </div>
            ) : (
              <div className="ops-empty">No active workspace selected yet.</div>
            )}
          </div>
        </section>
      </div>
    </OpsShell>
  );
}
