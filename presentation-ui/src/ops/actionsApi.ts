import type {
  OpsActionAuditRecord,
  OpsActionExecutionRecord,
  OpsActionPreview,
  OpsActionRequestRecord,
  OpsActionType,
} from './types';

type ApiPreview = {
  connection_id: string;
  action_type: OpsActionType;
  namespace: string;
  resource_name: string;
  allowed: boolean;
  risk_level: string;
  summary: string;
  preview_command: string;
  break_glass: boolean;
  break_glass_reason: string;
  break_glass_ticket: string;
  required_approvals: number;
  approval_strategy: string;
  requester_roles: string[];
  approver_roles: string[];
  executor_roles: string[];
  approval_rules: string[];
  policy_checks: string[];
  blocked_reasons: string[];
  validation_messages: string[];
  diff_unified: string;
  dry_run_status: string;
  dry_run_messages: string[];
  next_step: string;
};

type ApiRequest = {
  request_id: string;
  status: string;
  preview: ApiPreview;
  requested_by: string;
  requested_roles: string[];
  required_approvals: number;
  approval_count: number;
  approver_ids: string[];
  approver_role_map: Record<string, string[]>;
  reason: string;
  decision_note: string;
  created_at: string;
  updated_at: string;
};

type ApiExecution = {
  execution_id: string;
  request_id: string;
  status: string;
  execution_mode: string;
  simulated: boolean;
  preview: ApiPreview;
  summary: string;
  preflight_checks: string[];
  output_lines: string[];
  error: string;
  created_at: string;
  updated_at: string;
};

type ApiAudit = {
  event_id: string;
  event_type: string;
  actor_id: string;
  request_id: string;
  execution_id: string;
  action_type: string;
  namespace: string;
  resource_name: string;
  risk_level: string;
  decision_note: string;
  details: Record<string, unknown>;
  created_at: string;
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

function mapPreview(input: ApiPreview): OpsActionPreview {
  return {
    connectionId: input.connection_id,
    actionType: input.action_type,
    namespace: input.namespace,
    resourceName: input.resource_name,
    allowed: input.allowed,
    riskLevel: input.risk_level,
    summary: input.summary,
    previewCommand: input.preview_command,
    breakGlass: input.break_glass,
    breakGlassReason: input.break_glass_reason,
    breakGlassTicket: input.break_glass_ticket,
    requiredApprovals: input.required_approvals,
    approvalStrategy: input.approval_strategy,
    requesterRoles: input.requester_roles ?? [],
    approverRoles: input.approver_roles ?? [],
    executorRoles: input.executor_roles ?? [],
    approvalRules: input.approval_rules ?? [],
    policyChecks: input.policy_checks ?? [],
    blockedReasons: input.blocked_reasons ?? [],
    validationMessages: input.validation_messages ?? [],
    diffUnified: input.diff_unified,
    dryRunStatus: input.dry_run_status,
    dryRunMessages: input.dry_run_messages ?? [],
    nextStep: input.next_step,
  };
}

function mapRequest(input: ApiRequest): OpsActionRequestRecord {
  return {
    requestId: input.request_id,
    status: input.status,
    preview: mapPreview(input.preview),
    requestedBy: input.requested_by,
    requestedRoles: input.requested_roles ?? [],
    requiredApprovals: input.required_approvals,
    approvalCount: input.approval_count,
    approverIds: input.approver_ids ?? [],
    approverRoleMap: input.approver_role_map ?? {},
    reason: input.reason,
    decisionNote: input.decision_note,
    createdAt: input.created_at,
    updatedAt: input.updated_at,
  };
}

function mapExecution(input: ApiExecution): OpsActionExecutionRecord {
  return {
    executionId: input.execution_id,
    requestId: input.request_id,
    status: input.status,
    executionMode: input.execution_mode,
    simulated: input.simulated,
    preview: mapPreview(input.preview),
    summary: input.summary,
    preflightChecks: input.preflight_checks ?? [],
    outputLines: input.output_lines ?? [],
    error: input.error,
    createdAt: input.created_at,
    updatedAt: input.updated_at,
  };
}

function mapAudit(input: ApiAudit): OpsActionAuditRecord {
  return {
    eventId: input.event_id,
    eventType: input.event_type,
    actorId: input.actor_id,
    requestId: input.request_id,
    executionId: input.execution_id,
    actionType: input.action_type,
    namespace: input.namespace,
    resourceName: input.resource_name,
    riskLevel: input.risk_level,
    decisionNote: input.decision_note,
    details: input.details ?? {},
    createdAt: input.created_at,
  };
}

export async function previewAction(payload: Record<string, unknown>): Promise<OpsActionPreview> {
  const response = await fetch(apiUrl('/api/v1/actions/preview'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return mapPreview(await readJson<ApiPreview>(response));
}

export async function createActionRequest(payload: Record<string, unknown>): Promise<OpsActionRequestRecord> {
  const response = await fetch(apiUrl('/api/v1/actions/requests'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return mapRequest(await readJson<ApiRequest>(response));
}

export async function listActionRequests(limit = 20): Promise<OpsActionRequestRecord[]> {
  const response = await fetch(apiUrl(`/api/v1/actions/requests?limit=${limit}`));
  const payload = await readJson<{ items: ApiRequest[] }>(response);
  return (payload.items ?? []).map(mapRequest);
}

export async function approveActionRequest(requestId: string, payload: Record<string, unknown>): Promise<OpsActionRequestRecord> {
  const response = await fetch(apiUrl(`/api/v1/actions/requests/${requestId}/approve`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return mapRequest(await readJson<ApiRequest>(response));
}

export async function rejectActionRequest(requestId: string, payload: Record<string, unknown>): Promise<OpsActionRequestRecord> {
  const response = await fetch(apiUrl(`/api/v1/actions/requests/${requestId}/reject`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return mapRequest(await readJson<ApiRequest>(response));
}

export async function executeActionRequest(requestId: string, payload: Record<string, unknown>): Promise<OpsActionExecutionRecord> {
  const response = await fetch(apiUrl(`/api/v1/actions/requests/${requestId}/execute`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return mapExecution(await readJson<ApiExecution>(response));
}

export async function listActionExecutions(limit = 20): Promise<OpsActionExecutionRecord[]> {
  const response = await fetch(apiUrl(`/api/v1/actions/executions?limit=${limit}`));
  const payload = await readJson<{ items: ApiExecution[] }>(response);
  return (payload.items ?? []).map(mapExecution);
}

export async function listActionAudit(limit = 20): Promise<OpsActionAuditRecord[]> {
  const response = await fetch(apiUrl(`/api/v1/actions/audit?limit=${limit}`));
  const payload = await readJson<{ items: ApiAudit[] }>(response);
  return (payload.items ?? []).map(mapAudit);
}
