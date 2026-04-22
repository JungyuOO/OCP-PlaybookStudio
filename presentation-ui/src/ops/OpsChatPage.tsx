import type { FormEvent } from 'react';
import { useEffect, useState } from 'react';
import { listOpsWorkspaces } from './api';
import { sendOpsChat } from './chatApi';
import { listOpsConnections } from './connectionsApi';
import { getOpsNamespaces } from './resourcesApi';
import { OpsShell } from './OpsShell';
import type {
  OpsChatHistoryTurn,
  OpsConnectionProfile,
  OpsLiveResourceDetailResponse,
  OpsLiveResourceSummary,
  OpsWorkspaceRecord,
} from './types';

type ChatEntry = {
  role: 'user' | 'assistant';
  text: string;
  items?: OpsLiveResourceSummary[];
  detail?: OpsLiveResourceDetailResponse | null;
};

export default function OpsChatPage() {
  const [workspaces, setWorkspaces] = useState<OpsWorkspaceRecord[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState('');
  const [connections, setConnections] = useState<OpsConnectionProfile[]>([]);
  const [selectedConnectionId, setSelectedConnectionId] = useState('');
  const [namespaces, setNamespaces] = useState<string[]>([]);
  const [namespace, setNamespace] = useState('');
  const [message, setMessage] = useState('');
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    async function bootstrap() {
      try {
        const nextWorkspaces = await listOpsWorkspaces();
        setWorkspaces(nextWorkspaces);
        setSelectedWorkspaceId(nextWorkspaces[0]?.workspaceId || '');
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : 'Failed to load chat context.');
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
      setNamespaces([]);
      setNamespace('');
      return;
    }
    async function loadNamespaces() {
      try {
        const payload = await getOpsNamespaces(selectedConnectionId);
        setNamespaces(payload.items);
        setNamespace((current) => current || payload.items[0] || '');
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : 'Failed to load namespaces.');
      }
    }
    void loadNamespaces();
  }, [selectedConnectionId]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed || !selectedConnectionId) return;

    const history: OpsChatHistoryTurn[] = entries.map((item) => ({
      role: item.role,
      text: item.text,
    }));
    setEntries((current) => [...current, { role: 'user', text: trimmed }]);
    setMessage('');
    setLoading(true);
    setError('');

    try {
      const response = await sendOpsChat(selectedConnectionId, trimmed, namespace, history);
      setEntries((current) => [
        ...current,
        {
          role: 'assistant',
          text: response.answer,
          items: response.items,
          detail: response.detail,
        },
      ]);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Failed to send operational chat request.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <OpsShell
      eyebrow="OCP Ops Chat"
      title="Operational chat"
      description="This chat is separate from PlayBookStudio document chat. It uses the selected connection profile and namespace to produce operational answers tied to the synthetic cluster surface."
    >
      {error ? <div className="ops-alert glass-panel">{error}</div> : null}

      <div className="ops-card glass-panel">
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
              {namespaces.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="ops-chat-layout">
        <section className="ops-card glass-panel">
          <div className="ops-section-head">
            <div>
              <span className="ops-section-eyebrow">Transcript</span>
              <h2>Operational conversation</h2>
            </div>
            <span className="ops-meta-chip">{loading ? 'Thinking...' : `${entries.length} turns`}</span>
          </div>

          <div className="ops-chat-transcript">
            {entries.length > 0 ? (
              entries.map((entry, index) => (
                <article key={`${entry.role}-${index}`} className={`ops-chat-bubble ${entry.role === 'assistant' ? 'is-assistant' : 'is-user'}`}>
                  <span className="ops-section-eyebrow">{entry.role === 'assistant' ? 'Assistant' : 'You'}</span>
                  <p>{entry.text}</p>
                  {entry.items && entry.items.length > 0 ? (
                    <div className="ops-stack">
                      {entry.items.map((item) => (
                        <div key={item.name} className="ops-list-item is-static">
                          <div className="ops-list-main">
                            <strong>{item.name}</strong>
                            <span>{item.kind} · {item.phase || item.type || 'no status'}</span>
                          </div>
                          <div className="ops-list-meta">
                            <span>{item.namespace}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </article>
              ))
            ) : (
              <div className="ops-empty">Ask about pods, deployments, services, routes, events, or namespaces.</div>
            )}
          </div>

          <form className="ops-chat-composer" onSubmit={handleSubmit}>
            <textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              placeholder="예: openshift-monitoring namespace의 pod 보여줘"
            />
            <button
              type="submit"
              className="ops-primary-action"
              disabled={loading || !selectedConnectionId || !message.trim()}
            >
              {loading ? 'Sending...' : 'Send'}
            </button>
          </form>
        </section>

        <section className="ops-card glass-panel">
          <div className="ops-section-head">
            <div>
              <span className="ops-section-eyebrow">Detail sidecar</span>
              <h2>Last manifest detail</h2>
            </div>
          </div>

          {entries.findLast((item) => item.detail)?.detail ? (
            <pre className="ops-code-block">
              <code>{entries.findLast((item) => item.detail)?.detail?.manifestYaml}</code>
            </pre>
          ) : (
            <div className="ops-empty">Ask for a manifest or detail-oriented question to populate this panel.</div>
          )}
        </section>
      </div>
    </OpsShell>
  );
}
