import type { FormEvent } from 'react';
import { useEffect, useState } from 'react';
import { listOpsWorkspaces } from './api';
import {
  approveActionRequest,
  createActionRequest,
  executeActionRequest,
  listActionAudit,
  listActionExecutions,
  listActionRequests,
  previewAction,
  rejectActionRequest,
} from './actionsApi';
import { listOpsConnections } from './connectionsApi';
import { OpsShell } from './OpsShell';
import type {
  OpsActionAuditRecord,
  OpsActionExecutionRecord,
  OpsActionPreview,
  OpsActionRequestRecord,
  OpsActionType,
  OpsConnectionProfile,
  OpsWorkspaceRecord,
} from './types';

function formatTimestamp(value: string) {
  if (!value) return 'not recorded';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('ko-KR', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

export default function OpsActionsPage() {
  const [workspaces, setWorkspaces] = useState<OpsWorkspaceRecord[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState('');
  const [connections, setConnections] = useState<OpsConnectionProfile[]>([]);
  const [selectedConnectionId, setSelectedConnectionId] = useState('');
  const [actorId, setActorId] = useState('ui-local');
  const [actorRoles, setActorRoles] = useState('operator');
  const [actionType, setActionType] = useState<OpsActionType>('scale_deployment');
  const [namespace, setNamespace] = useState('openshift-monitoring');
  const [resourceName, setResourceName] = useState('');
  const [replicas, setReplicas] = useState(1);
  const [reason, setReason] = useState('');
  const [preview, setPreview] = useState<OpsActionPreview | null>(null);
  const [requests, setRequests] = useState<OpsActionRequestRecord[]>([]);
  const [executions, setExecutions] = useState<OpsActionExecutionRecord[]>([]);
  const [audit, setAudit] = useState<OpsActionAuditRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function refreshLists() {
    const [nextRequests, nextExecutions, nextAudit] = await Promise.all([
      listActionRequests(),
      listActionExecutions(),
      listActionAudit(),
    ]);
    setRequests(nextRequests);
    setExecutions(nextExecutions);
    setAudit(nextAudit);
  }

  useEffect(() => {
    async function bootstrap() {
      try {
        const nextWorkspaces = await listOpsWorkspaces();
        setWorkspaces(nextWorkspaces);
        setSelectedWorkspaceId(nextWorkspaces[0]?.workspaceId || '');
        await refreshLists();
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : 'Failed to load actions context.');
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
        if (payload.items[0]?.defaultNamespace) {
          setNamespace(payload.items[0].defaultNamespace);
        }
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : 'Failed to load connection profiles.');
      }
    }
    void loadConnections();
  }, [selectedWorkspaceId]);

  async function handlePreview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedConnectionId) return;
    setLoading(true);
    setError('');
    try {
      const nextPreview = await previewAction({
        connection_id: selectedConnectionId,
        actor_id: actorId,
        actor_roles: actorRoles.split(',').map((item) => item.trim()).filter(Boolean),
        action_type: actionType,
        namespace,
        resource_name: resourceName,
        replicas,
        reason,
      });
      setPreview(nextPreview);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Failed to preview action.');
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateRequest() {
    if (!selectedConnectionId) return;
    setLoading(true);
    setError('');
    try {
      const nextRequest = await createActionRequest({
        connection_id: selectedConnectionId,
        actor_id: actorId,
        actor_roles: actorRoles.split(',').map((item) => item.trim()).filter(Boolean),
        action_type: actionType,
        namespace,
        resource_name: resourceName,
        replicas,
        reason,
      });
      setPreview(nextRequest.preview);
      await refreshLists();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Failed to create request.');
    } finally {
      setLoading(false);
    }
  }

  async function handleApprove(requestId: string) {
    setLoading(true);
    setError('');
    try {
      await approveActionRequest(requestId, {
        actor_id: actorId,
        actor_roles: actorRoles.split(',').map((item) => item.trim()).filter(Boolean),
        decision_note: 'approved from ops ui',
      });
      await refreshLists();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Failed to approve request.');
    } finally {
      setLoading(false);
    }
  }

  async function handleReject(requestId: string) {
    setLoading(true);
    setError('');
    try {
      await rejectActionRequest(requestId, {
        actor_id: actorId,
        actor_roles: actorRoles.split(',').map((item) => item.trim()).filter(Boolean),
        decision_note: 'rejected from ops ui',
      });
      await refreshLists();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Failed to reject request.');
    } finally {
      setLoading(false);
    }
  }

  async function handleExecute(requestId: string) {
    setLoading(true);
    setError('');
    try {
      await executeActionRequest(requestId, {
        actor_id: actorId,
        actor_roles: actorRoles.split(',').map((item) => item.trim()).filter(Boolean),
        force: false,
      });
      await refreshLists();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Failed to execute request.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <OpsShell
      eyebrow="OCP Ops Actions"
      title="Guarded action workflow"
      description="This page now runs a synthetic preview/request/approval/execution workflow. It establishes the action contract and UI choreography before live mutation is wired."
    >
      {error ? <div className="ops-alert glass-panel">{error}</div> : null}

      <div className="ops-card glass-panel">
        <div className="ops-section-head">
          <div>
            <span className="ops-section-eyebrow">Action builder</span>
            <h2>Create preview and approval request</h2>
          </div>
        </div>

        <form className="ops-form" onSubmit={handlePreview}>
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
              <span>Action type</span>
              <select value={actionType} onChange={(event) => setActionType(event.target.value as OpsActionType)}>
                <option value="scale_deployment">scale_deployment</option>
                <option value="rollout_restart">rollout_restart</option>
                <option value="log_bundle">log_bundle</option>
              </select>
            </label>
          </div>

          <div className="ops-context-grid">
            <label className="ops-field">
              <span>Namespace</span>
              <input value={namespace} onChange={(event) => setNamespace(event.target.value)} />
            </label>
            <label className="ops-field">
              <span>Resource name</span>
              <input value={resourceName} onChange={(event) => setResourceName(event.target.value)} />
            </label>
            <label className="ops-field">
              <span>Replicas</span>
              <input type="number" min={0} value={replicas} onChange={(event) => setReplicas(Number(event.target.value) || 0)} />
            </label>
          </div>

          <div className="ops-inline-grid">
            <label className="ops-field">
              <span>Actor ID</span>
              <input value={actorId} onChange={(event) => setActorId(event.target.value)} />
            </label>
            <label className="ops-field">
              <span>Actor roles</span>
              <input value={actorRoles} onChange={(event) => setActorRoles(event.target.value)} placeholder="operator,admin" />
            </label>
          </div>

          <label className="ops-field">
            <span>Reason</span>
            <textarea className="ops-chat-composer-textarea" value={reason} onChange={(event) => setReason(event.target.value)} />
          </label>

          <div className="ops-button-row">
            <button type="submit" className="ops-primary-action" disabled={loading || !selectedConnectionId || !resourceName.trim()}>
              {loading ? 'Previewing...' : 'Create preview'}
            </button>
            <button type="button" className="ops-secondary-action" disabled={loading || !preview} onClick={() => void handleCreateRequest()}>
              Create approval request
            </button>
          </div>
        </form>
      </div>

      {preview ? (
        <section className="ops-card glass-panel">
          <div className="ops-section-head">
            <div>
              <span className="ops-section-eyebrow">Latest preview</span>
              <h2>{preview.summary}</h2>
            </div>
            <span className="ops-meta-chip">{preview.riskLevel}</span>
          </div>
          <div className="ops-detail-grid">
            <div>
              <strong>Allowed</strong>
              <span>{String(preview.allowed)}</span>
            </div>
            <div>
              <strong>Required approvals</strong>
              <span>{preview.requiredApprovals}</span>
            </div>
            <div>
              <strong>Preview command</strong>
              <span>{preview.previewCommand}</span>
            </div>
            <div>
              <strong>Next step</strong>
              <span>{preview.nextStep}</span>
            </div>
          </div>
          <pre className="ops-code-block"><code>{preview.diffUnified}</code></pre>
        </section>
      ) : null}

      <div className="ops-three-column">
        <section className="ops-card glass-panel">
          <div className="ops-section-head"><div><span className="ops-section-eyebrow">Requests</span><h2>Approval queue</h2></div></div>
          <div className="ops-stack">
            {requests.length > 0 ? requests.map((item) => (
              <div key={item.requestId} className="ops-list-item is-static">
                <div className="ops-list-main">
                  <strong>{item.preview.summary}</strong>
                  <span>{item.status} · approvals {item.approvalCount}/{item.requiredApprovals}</span>
                </div>
                <div className="ops-action-links">
                  <button type="button" className="ops-link-button" onClick={() => void handleApprove(item.requestId)}>Approve</button>
                  <button type="button" className="ops-link-button" onClick={() => void handleReject(item.requestId)}>Reject</button>
                  <button type="button" className="ops-link-button" onClick={() => void handleExecute(item.requestId)}>Execute</button>
                </div>
              </div>
            )) : <div className="ops-empty">No action requests yet.</div>}
          </div>
        </section>

        <section className="ops-card glass-panel">
          <div className="ops-section-head"><div><span className="ops-section-eyebrow">Executions</span><h2>Execution history</h2></div></div>
          <div className="ops-stack">
            {executions.length > 0 ? executions.map((item) => (
              <div key={item.executionId} className="ops-list-item is-static">
                <div className="ops-list-main">
                  <strong>{item.summary}</strong>
                  <span>{item.status} · {formatTimestamp(item.createdAt)}</span>
                </div>
              </div>
            )) : <div className="ops-empty">No executions yet.</div>}
          </div>
        </section>

        <section className="ops-card glass-panel">
          <div className="ops-section-head"><div><span className="ops-section-eyebrow">Audit</span><h2>Event trail</h2></div></div>
          <div className="ops-stack">
            {audit.length > 0 ? audit.map((item) => (
              <div key={item.eventId} className="ops-list-item is-static">
                <div className="ops-list-main">
                  <strong>{item.eventType}</strong>
                  <span>{item.actionType} · {formatTimestamp(item.createdAt)}</span>
                </div>
              </div>
            )) : <div className="ops-empty">No audit events yet.</div>}
          </div>
        </section>
      </div>
    </OpsShell>
  );
}
