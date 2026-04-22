import type { FormEvent } from 'react';
import { useEffect, useState } from 'react';
import { listOpsWorkspaces } from './api';
import {
  buildScmDeploymentPlan,
  createScmConnection,
  createScmRepository,
  discoverScmConfigPaths,
  discoverScmRepositories,
  listScmConnections,
  listScmRepositories,
  startScmOauth,
  updateScmRepository,
} from './scmApi';
import { OpsShell } from './OpsShell';
import type {
  OpsScmConfigPathCandidate,
  OpsScmConnectionRecord,
  OpsScmDeploymentPlan,
  OpsScmDiscoveredRepository,
  OpsScmProvider,
  OpsScmRepositoryRecord,
  OpsWorkspaceRecord,
} from './types';

export default function OpsScmPage() {
  const [workspaces, setWorkspaces] = useState<OpsWorkspaceRecord[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState('');
  const [connections, setConnections] = useState<OpsScmConnectionRecord[]>([]);
  const [repositories, setRepositories] = useState<OpsScmRepositoryRecord[]>([]);
  const [provider, setProvider] = useState<OpsScmProvider>('github');
  const [hostUrl, setHostUrl] = useState('https://github.com');
  const [accountLabel, setAccountLabel] = useState('');
  const [connectionId, setConnectionId] = useState('');
  const [repoFullName, setRepoFullName] = useState('');
  const [configPath, setConfigPath] = useState('config.yaml');
  const [deliveryMode, setDeliveryMode] = useState('gitops_commit');
  const [manifestKind, setManifestKind] = useState('config_yaml');
  const [targetClusterUrl, setTargetClusterUrl] = useState('');
  const [targetNamespace, setTargetNamespace] = useState('default');
  const [repoQuery, setRepoQuery] = useState('');
  const [discoveredRepositories, setDiscoveredRepositories] = useState<OpsScmDiscoveredRepository[]>([]);
  const [configCandidates, setConfigCandidates] = useState<OpsScmConfigPathCandidate[]>([]);
  const [plan, setPlan] = useState<OpsScmDeploymentPlan | null>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  async function refresh(workspaceId: string) {
    const [nextConnections, nextRepositories] = await Promise.all([
      listScmConnections(workspaceId),
      listScmRepositories(workspaceId),
    ]);
    setConnections(nextConnections);
    setRepositories(nextRepositories);
    setConnectionId((current) => current || nextConnections[0]?.scmConnectionId || '');
  }

  useEffect(() => {
    async function bootstrap() {
      try {
        const nextWorkspaces = await listOpsWorkspaces();
        setWorkspaces(nextWorkspaces);
        const workspaceId = nextWorkspaces[0]?.workspaceId || '';
        setSelectedWorkspaceId(workspaceId);
        if (workspaceId) {
          await refresh(workspaceId);
        }
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : 'Failed to load SCM context.');
      }
    }
    void bootstrap();
  }, []);

  useEffect(() => {
    if (!selectedWorkspaceId) return;
    void refresh(selectedWorkspaceId);
  }, [selectedWorkspaceId]);

  useEffect(() => {
    setHostUrl(provider === 'gitlab' ? 'https://gitlab.com' : 'https://github.com');
  }, [provider]);

  async function handleOauthConnect(providerName: OpsScmProvider) {
    if (!selectedWorkspaceId || typeof window === 'undefined') return;
    try {
      const started = await startScmOauth(providerName, selectedWorkspaceId);
      window.location.assign(started.authorizeUrl);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : `Failed to start ${providerName} OAuth.`);
    }
  }

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const search = new URLSearchParams(window.location.search);
    const oauthStatus = search.get('oauth_status')?.trim() ?? '';
    const providerValue = search.get('provider')?.trim() ?? '';
    const oauthMessage = search.get('message')?.trim() ?? '';
    if (!oauthStatus) return;
    if (oauthStatus === 'connected') {
      setMessage(providerValue ? `${providerValue} account connected.` : 'SCM account connected.');
      setError('');
      if (selectedWorkspaceId) {
        void refresh(selectedWorkspaceId);
      }
    } else {
      setError(oauthMessage || 'SCM OAuth failed.');
      setMessage('');
    }
    window.history.replaceState(null, '', '/ops/scm');
  }, [selectedWorkspaceId]);

  async function handleCreateConnection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedWorkspaceId) return;
    setLoading(true);
    setError('');
    try {
      await createScmConnection(selectedWorkspaceId, {
        provider,
        host_url: hostUrl,
        auth_type: 'token',
        account_label: accountLabel,
      });
      setMessage('SCM connection saved.');
      await refresh(selectedWorkspaceId);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Failed to create SCM connection.');
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateRepository(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedWorkspaceId || !connectionId) return;
    setLoading(true);
    setError('');
    try {
      await createScmRepository(selectedWorkspaceId, {
        scm_connection_id: connectionId,
        repo_full_name: repoFullName,
        default_branch: 'main',
        config_path: configPath,
        delivery_mode: deliveryMode,
        manifest_kind: manifestKind,
        target_cluster_url: targetClusterUrl,
        target_namespace: targetNamespace,
        auto_deploy_enabled: true,
      });
      setMessage('Repository delivery profile saved.');
      await refresh(selectedWorkspaceId);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Failed to create repository.');
    } finally {
      setLoading(false);
    }
  }

  async function handleDiscoverRepositories() {
    if (!selectedWorkspaceId || !connectionId) return;
    setLoading(true);
    setError('');
    try {
      const items = await discoverScmRepositories(selectedWorkspaceId, connectionId, repoQuery, 20);
      setDiscoveredRepositories(items);
      setMessage(items.length > 0 ? `Fetched ${items.length} repositories from provider.` : 'No repositories matched the current query.');
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Failed to fetch repositories.');
    } finally {
      setLoading(false);
    }
  }

  async function handleDiscoverConfigPaths() {
    if (!selectedWorkspaceId || !connectionId || !repoFullName.trim()) return;
    setLoading(true);
    setError('');
    try {
      const items = await discoverScmConfigPaths(selectedWorkspaceId, connectionId, repoFullName, 'main', 20);
      setConfigCandidates(items);
      setMessage(items.length > 0 ? `Found ${items.length} config path candidates.` : 'No config path candidates found.');
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Failed to discover config paths.');
    } finally {
      setLoading(false);
    }
  }

  async function handleBuildPlan(repositoryId: string) {
    if (!selectedWorkspaceId) return;
    setLoading(true);
    setError('');
    try {
      const nextPlan = await buildScmDeploymentPlan(selectedWorkspaceId, repositoryId, {
        resource_kind: 'Deployment',
        resource_name: 'ops-deployment-01',
        target_namespace: targetNamespace,
        replicas: 3,
        image_tag: 'v2.0.0',
        config_key: 'replicas',
        reason: 'Synthetic deployment update',
      });
      setPlan(nextPlan);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Failed to build deployment plan.');
    } finally {
      setLoading(false);
    }
  }

  async function handleTouchRepository(repository: OpsScmRepositoryRecord) {
    if (!selectedWorkspaceId) return;
    setLoading(true);
    setError('');
    try {
      await updateScmRepository(selectedWorkspaceId, repository.repositoryId, {
        target_namespace: repository.targetNamespace,
        config_path: repository.configPath,
      });
      await refresh(selectedWorkspaceId);
      setMessage('Repository delivery settings updated.');
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Failed to update repository.');
    } finally {
      setLoading(false);
    }
  }

  const recommendedConfigCandidates = configCandidates.filter((item) => item.confidence === 'recommended');
  const fallbackConfigCandidates = configCandidates.filter((item) => item.confidence === 'fallback');

  return (
    <OpsShell
      eyebrow="OCP Ops SCM"
      title="Repository-driven delivery"
      description="This page now stores SCM connections, repository delivery profiles, OAuth bootstrap redirects, and deployment plans. GitHub repositories can be validated against the real provider API when a local GitHub token is configured."
    >
      {error ? <div className="ops-alert glass-panel">{error}</div> : null}
      {message ? <div className="ops-detail-card glass-panel">{message}</div> : null}
      <div className="ops-detail-card glass-panel">
        Live note: GitHub repository validation uses the local GitHub token from the environment when available. GitLab remains synthetic in this stage unless a real provider path is added next.
      </div>
      <div className="ops-detail-card glass-panel">
        OAuth config keys:
        <br />
        GitHub: <code>SCM_GITHUB_CLIENT_ID</code>, <code>SCM_GITHUB_CLIENT_SECRET</code>
        <br />
        GitLab: <code>SCM_GITLAB_CLIENT_ID</code>, <code>SCM_GITLAB_CLIENT_SECRET</code>
      </div>

      <div className="ops-two-column">
        <section className="ops-card glass-panel">
          <div className="ops-section-head">
            <div>
              <span className="ops-section-eyebrow">Workspace and OAuth</span>
              <h2>Connect Git provider</h2>
            </div>
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
          </div>
          <div className="ops-button-row">
            <button type="button" className="ops-primary-action" onClick={() => void handleOauthConnect('github')} disabled={!selectedWorkspaceId}>
              Connect GitHub
            </button>
            <button type="button" className="ops-secondary-action" onClick={() => void handleOauthConnect('gitlab')} disabled={!selectedWorkspaceId}>
              Connect GitLab
            </button>
          </div>
          <form className="ops-form" onSubmit={handleCreateConnection}>
            <div className="ops-inline-grid">
              <label className="ops-field">
                <span>Provider</span>
                <select value={provider} onChange={(event) => setProvider(event.target.value as OpsScmProvider)}>
                  <option value="github">github</option>
                  <option value="gitlab">gitlab</option>
                </select>
              </label>
              <label className="ops-field">
                <span>Host URL</span>
                <input value={hostUrl} onChange={(event) => setHostUrl(event.target.value)} />
              </label>
            </div>
            <label className="ops-field">
              <span>Account label</span>
              <input value={accountLabel} onChange={(event) => setAccountLabel(event.target.value)} />
            </label>
            <button type="submit" className="ops-primary-action" disabled={loading || !selectedWorkspaceId}>
              Save connection
            </button>
          </form>
        </section>

        <section className="ops-card glass-panel">
          <div className="ops-section-head">
            <div>
              <span className="ops-section-eyebrow">Repository profile</span>
              <h2>Register delivery repository</h2>
            </div>
          </div>
          <div className="ops-form">
            <label className="ops-field">
              <span>Discover repositories from selected connection</span>
              <input value={repoQuery} onChange={(event) => setRepoQuery(event.target.value)} placeholder="search repositories" />
            </label>
            <div className="ops-button-row">
              <button type="button" className="ops-secondary-action" disabled={loading || !selectedWorkspaceId || !connectionId} onClick={() => void handleDiscoverRepositories()}>
                Fetch repositories
              </button>
              <button type="button" className="ops-secondary-action" disabled={loading || !selectedWorkspaceId || !connectionId || !repoFullName.trim()} onClick={() => void handleDiscoverConfigPaths()}>
                Discover config paths
              </button>
            </div>
          </div>

          <div className="ops-stack">
            {discoveredRepositories.map((item) => (
              <button
                key={`${item.provider}:${item.externalId}`}
                type="button"
                className="ops-list-item"
                onClick={() => {
                  setRepoFullName(item.fullName);
                  setConfigCandidates([]);
                }}
              >
                <div className="ops-list-main">
                  <strong>{item.fullName}</strong>
                  <span>{item.defaultBranch} · {item.visibility}</span>
                </div>
              </button>
            ))}
          </div>

          {recommendedConfigCandidates.length > 0 ? (
            <div className="ops-discovery-group">
              <div className="ops-discovery-head">
                <span className="ops-section-eyebrow">Recommended matches</span>
                <span className="ops-meta-chip">{recommendedConfigCandidates.length}</span>
              </div>
              <div className="ops-stack">
                {recommendedConfigCandidates.map((item) => (
                  <button
                    key={`${item.path}:${item.manifestKind}`}
                    type="button"
                    className="ops-list-item"
                    onClick={() => {
                      setConfigPath(item.path);
                      setManifestKind(item.manifestKind);
                    }}
                  >
                    <div className="ops-list-main">
                      <strong>{item.path}</strong>
                      <span>{item.manifestKind} · score {item.score}</span>
                    </div>
                    <div className="ops-list-meta">
                      <span className="ops-badge">Recommended</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {fallbackConfigCandidates.length > 0 ? (
            <div className="ops-discovery-group">
              <div className="ops-discovery-head">
                <span className="ops-section-eyebrow">Fallback matches</span>
                <span className="ops-meta-chip">{fallbackConfigCandidates.length}</span>
              </div>
              <div className="ops-stack">
                {fallbackConfigCandidates.map((item) => (
                  <button
                    key={`${item.path}:${item.manifestKind}`}
                    type="button"
                    className="ops-list-item"
                    onClick={() => {
                      setConfigPath(item.path);
                      setManifestKind(item.manifestKind);
                    }}
                  >
                    <div className="ops-list-main">
                      <strong>{item.path}</strong>
                      <span>{item.manifestKind} · score {item.score}</span>
                    </div>
                    <div className="ops-list-meta">
                      <span className="ops-badge">Weak match</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          <form className="ops-form" onSubmit={handleCreateRepository}>
            <label className="ops-field">
              <span>SCM connection</span>
              <select value={connectionId} onChange={(event) => setConnectionId(event.target.value)}>
                <option value="">Select connection</option>
                {connections.map((item) => (
                  <option key={item.scmConnectionId} value={item.scmConnectionId}>
                    {item.provider} · {item.accountLabel}
                  </option>
                ))}
              </select>
            </label>
            <label className="ops-field">
              <span>Repository full name</span>
              <input value={repoFullName} onChange={(event) => setRepoFullName(event.target.value)} placeholder="org/repo" />
            </label>
            <div className="ops-inline-grid">
              <label className="ops-field">
                <span>Config path</span>
                <input value={configPath} onChange={(event) => setConfigPath(event.target.value)} />
              </label>
              <label className="ops-field">
                <span>Target namespace</span>
                <input value={targetNamespace} onChange={(event) => setTargetNamespace(event.target.value)} />
              </label>
            </div>
            <div className="ops-inline-grid">
              <label className="ops-field">
                <span>Delivery mode</span>
                <select value={deliveryMode} onChange={(event) => setDeliveryMode(event.target.value)}>
                  <option value="gitops_commit">gitops_commit</option>
                  <option value="cicd_pipeline">cicd_pipeline</option>
                </select>
              </label>
              <label className="ops-field">
                <span>Manifest kind</span>
                <select value={manifestKind} onChange={(event) => setManifestKind(event.target.value)}>
                  <option value="config_yaml">config_yaml</option>
                  <option value="helm_values">helm_values</option>
                  <option value="kustomize">kustomize</option>
                </select>
              </label>
            </div>
            <label className="ops-field">
              <span>Target cluster URL</span>
              <input value={targetClusterUrl} onChange={(event) => setTargetClusterUrl(event.target.value)} />
            </label>
            <button type="submit" className="ops-primary-action" disabled={loading || !selectedWorkspaceId || !connectionId || !repoFullName.trim()}>
              Save repository
            </button>
          </form>
        </section>
      </div>

      <div className="ops-two-column">
        <section className="ops-card glass-panel">
          <div className="ops-section-head">
            <div><span className="ops-section-eyebrow">Connections</span><h2>Saved SCM accounts</h2></div>
          </div>
          <div className="ops-stack">
            {connections.length > 0 ? connections.map((item) => (
              <div key={item.scmConnectionId} className="ops-list-item is-static">
                <div className="ops-list-main">
                  <strong>{item.provider} · {item.accountLabel}</strong>
                  <span>{item.hostUrl} · {item.authType} · {item.status}</span>
                </div>
              </div>
            )) : <div className="ops-empty">No SCM connections yet.</div>}
          </div>
        </section>

        <section className="ops-card glass-panel">
          <div className="ops-section-head">
            <div><span className="ops-section-eyebrow">Repositories</span><h2>Delivery profiles</h2></div>
          </div>
          <div className="ops-stack">
            {repositories.length > 0 ? repositories.map((item) => (
              <div key={item.repositoryId} className="ops-list-item is-static">
                <div className="ops-list-main">
                  <strong>{item.repoFullName}</strong>
                  <span>{item.deliveryMode} · {item.defaultBranch} · {item.configPath} · {item.syncStatus}</span>
                </div>
                <div className="ops-action-links">
                  <button type="button" className="ops-link-button" onClick={() => void handleTouchRepository(item)}>Save</button>
                  <button type="button" className="ops-link-button" onClick={() => void handleBuildPlan(item.repositoryId)}>Plan</button>
                </div>
              </div>
            )) : <div className="ops-empty">No repository profiles yet.</div>}
          </div>
        </section>
      </div>

      {plan ? (
        <section className="ops-card glass-panel">
          <div className="ops-section-head">
            <div><span className="ops-section-eyebrow">Deployment plan</span><h2>{plan.summary}</h2></div>
          </div>
          <div className="ops-detail-grid">
            <div><strong>Repo</strong><span>{plan.repoFullName}</span></div>
            <div><strong>Trigger</strong><span>{plan.triggerKind}</span></div>
            <div><strong>Config path</strong><span>{plan.configPath}</span></div>
            <div><strong>Next step</strong><span>{plan.nextStep}</span></div>
          </div>
          <div className="ops-stack">
            {plan.suggestedUpdates.map((item) => (
              <div key={item} className="ops-list-item is-static">
                <div className="ops-list-main"><strong>{item}</strong></div>
              </div>
            ))}
          </div>
          <pre className="ops-code-block"><code>{plan.commitTitle}{'\n\n'}{plan.commitBody}</code></pre>
        </section>
      ) : null}
    </OpsShell>
  );
}
