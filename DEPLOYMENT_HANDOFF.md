# OCP-PlaybookStudio Deployment Handoff

Date: 2026-04-22

## Current Status

### Product surfaces now present
- `PlayBookStudio` document lane is bootstrapped and runs inside this repository.
- `OCP Ops` sibling lane is mounted under `/ops`.
- The current `/ops` route family includes:
  - `/ops/workspaces`
  - `/ops/connections`
  - `/ops/overview`
  - `/ops/resources`
  - `/ops/chat`
  - `/ops/actions`
  - `/ops/scm`

### Current integration maturity
- `workspaces`: implemented and persisted locally.
- `connections`: implemented and persisted locally.
- `overview`: implemented; currently synthetic metrics/summary layered on top of a real connection contract.
- `resources`: real OCP read path works when the target cluster/token allow it.
- `chat`: uses the OCP connection/resource layer and returns operational answers; still lightweight planner behavior.
- `actions`: preview path is partially grounded in live resource reads; request/execution/audit storage remains synthetic.
- `scm`: OAuth start is real, callback path is ready, GitHub repo validation/repo fetch/config-path discovery are real; GitLab remains only partially real.

### Verified live findings
- The currently tested OCP cluster requires `verify_ssl=false` because the certificate chain is self-signed.
- The currently tested token can access the `demo` namespace successfully.
- Cluster-wide namespace listing returns `403`, so the backend falls back to the configured default namespace when needed.
- GitHub OAuth start works and generated a real authorize URL.
- Saved GitHub OAuth connections can fetch real repositories.
- Config-path discovery now separates strong recommendations from weaker fallback matches.

## Remaining Work

### OCP lane
- Replace synthetic overview metrics with real Prometheus-backed metrics.
- Make operational chat planner/tool flow more robust.
- Keep `actions` execution behind a guarded real mutation gate.
- Decide which action types can ever execute live and which should stay repo-driven only.

### SCM lane
- Complete real browser-tested OAuth callback verification for both GitHub and GitLab in shared environments.
- Validate GitLab repository discovery against a real token.
- Add PR/MR creation flow after repository profile and config-path selection are stable.
- Validate config-file preview against more real repositories and both providers.

### Platform / deployment
- Normalize environment-variable naming and ownership.
- Reduce local-only assumptions in Docker/Compose.
- Decide how large corpus/data assets are distributed outside normal git history.
- Define team-safe `.env` handling for shared development and deployed environments.

## Current Deployment Reality

### Current backend image
- The repo is moving to a single root `Dockerfile`.
- That root file now owns both backend and frontend build targets.
- The backend target serves the PlayBookStudio backend and now also hosts the `/ops` backend contract.
- This remains the correct high-level direction: one backend service, not two separate Python apps.

### Current compose file
- `docker-compose.yml` is now intended to be the single root compose contract.
- It currently runs:
  - `backend`
  - `frontend`
  - `qdrant`
  - `postgres`
- `postgres` is part of the default contract because DB-backed runtime state is needed for the integrated product.
- Embedding/chat are expected to come from external servers rather than local Ollama containers.

### Current environment file
- `.env` now contains a mix of:
  - runtime/corpus settings
  - local graph/Qdrant settings
  - local DB/runtime state settings
  - live OCP test settings
  - GitHub token
  - SCM OAuth client credentials
- This is fine for one-person development but is too mixed for team collaboration and deployment.

## Recommended Docker Strategy

### Target posture
- Keep **one root Dockerfile** with multiple targets.
- Keep **one compose file for local dev**.
- Use env overrides inside that single compose file instead of splitting compose contracts too early.

### Backend image contract
- Continue using the root `Dockerfile` backend target as the single backend image.
- Do not split PlayBookStudio and OCP Ops into separate Python containers yet.
- The backend is already a single runtime surface with multiple route families; the container model should match that.

### Frontend image contract
- Continue using the root `Dockerfile` frontend target as the single frontend image.
- The frontend should continue to serve both:
  - PlayBookStudio document lane
  - OCP Ops lane

### Compose recommendation
- Keep one root `docker-compose.yml`.
- Current intended split:
  - `backend`
  - `frontend`
  - `qdrant`
  - `postgres`
- External embedding/chat infrastructure should stay external and be referenced by env vars instead of bundling local Ollama services.

## Recommended `.env` Strategy

### Goal
Separate variables by ownership instead of by convenience.

### Recommended files
- `.env.example`
  - committed
  - complete variable inventory
  - no secrets
- `.env.local`
  - ignored
  - one developer's machine-specific values
- `.env.team`
  - ignored or managed separately
  - shared internal environment values for team deployment/dev
- `.env.prod`
  - never committed
  - deployment-secret source or injected by infra

### Variable grouping

#### 1. Core runtime
- `ARTIFACTS_DIR`
- `SOURCE_MANIFEST_PATH`
- `LLM_ENDPOINT`
- `LLM_MODEL`
- `EMBEDDING_BASE_URL`
- `EMBEDDING_MODEL`
- `QDRANT_*`
- `GRAPH_*`

#### 2. OCP live integration
- `OCP_API_BASE_URL`
- `OCP_API_TOKEN`
- `OCP_DEFAULT_NAMESPACE`

These are development/test-only values right now.
They should not become the deployment contract for the app.
The app should store connection profiles per workspace instead.

#### 3. SCM validation
- `GITHUB_CLASSIC_TOKEN`
- optional future GitLab personal token if needed for non-OAuth fallback

These are helper credentials for validation/discovery.
They should be optional, not required for core app boot.

#### 4. SCM OAuth
- `SCM_GITHUB_CLIENT_ID`
- `SCM_GITHUB_CLIENT_SECRET`
- `SCM_GITHUB_SCOPE`
- `SCM_GITHUB_AUTHORIZE_URL`
- `SCM_GITHUB_TOKEN_URL`
- `SCM_GITHUB_USER_URL`
- `SCM_GITLAB_CLIENT_ID`
- `SCM_GITLAB_CLIENT_SECRET`
- `SCM_GITLAB_SCOPE`
- `SCM_GITLAB_AUTHORIZE_URL`
- `SCM_GITLAB_TOKEN_URL`
- `SCM_GITLAB_USER_URL`

These belong to deployment/shared environment configuration, not per-developer feature work.

## Recommended Immediate Refactor For Team Work

### 1. Keep `.env.example` as the committed contract
- It should include every required variable name.
- It should contain comments for:
  - local dev only
  - optional
  - team deployment
  - secret/injected

### 2. Treat current `.env` as temporary local bootstrap only
- Do not use the current `.env` as the team source of truth.
- Split actual secret-bearing values into non-committed env files or deployment secrets.

### 3. Add one deployment handoff doc
- This document is that handoff seed.
- It should be kept with the repo until infra conventions are finalized.

### 4. Avoid hardcoding local assumptions in deployment docs
- `127.0.0.1`
- local Neo4j
- local Qdrant ports
- local self-signed OCP verification guidance

Those are valid for current testing but should not be treated as company deployment defaults.

## Recommended Near-Term Implementation Order

1. Finalize the root `Dockerfile` and root `docker-compose.yml` as the single deployment contract.
2. Finalize `.env.example` as the canonical variable inventory.
3. Add `.env.local` to `.gitignore` guidance and use it for developer-specific values.
4. Keep local-only OCP test credentials out of team deployment config.
5. Move large data/corpus assets to an explicit distribution path if the team will clone this repository routinely.
6. Continue real integration work only after the deployment/env contract is understandable to collaborators.

## Practical Decision

For the next handoff:
- **Do not** split the app into multiple backend containers yet.
- **Do** keep a single backend + single frontend architecture.
- **Do** standardize env ownership now before more real integrations land.
- **Do** treat this repository as the shared product home going forward.

## Suggested Next Work Item

If deployment/collaboration is the immediate priority, the next concrete task should be:

`Finalize the single root Dockerfile/docker-compose.yml/.env.example contract and document profile-based local infra usage`

That gives collaborators one stable way to boot the merged product before more runtime behavior changes land.
