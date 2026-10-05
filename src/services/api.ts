import { useCallback, useEffect, useRef, useState } from 'react';

export const API_URL: string = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8765';

// ---------- types (mirror backend/app/schemas_api.py and crm_form.py) ----------
export interface EvidenceBox {
  page: number;
  x: number; // 0-1 relative to the page
  y: number;
  w: number;
  h: number;
  row?: number;
  precision?: 'table';
}

export interface ExtractedField {
  value: unknown;
  confidence: number | null; // 0-100
  page: number | null;
  box: EvidenceBox | null;
  box_source: 'sarvam' | 'pdf_text_layer' | 'digitise' | 'none';
  box_precision: 'block' | 'table';
  boxes: EvidenceBox[] | null;
}

export interface DocumentCheck {
  id: string;
  label: string;
  status: 'pass' | 'fail' | 'warn' | 'skip';
  detail: string;
}

export interface CaseDocumentRecord {
  doc_id: string;
  case_id: string;
  doc_type: string;
  doc_type_label: string;
  filename: string;
  mime: string;
  size_bytes: number;
  sha256: string;
  status: 'received' | 'extracting' | 'extracted' | 'needs_attention' | 'error';
  memory_status: 'pending' | 'stored' | 'failed';
  error: string | null;
  page_count: number | null;
  fields: Record<string, ExtractedField> | null;
  checks: DocumentCheck[] | null;
  file_url: string;
}

export interface CrmField {
  key: string;
  label: string;
  value: string | null;
  ai_value: string | null;
  overridden: boolean;
  source: string;
  doc_id: string | null;
  doc_type: string | null;
  field: string | null;
  page: number | null;
  confidence: number | null;
  has_box: boolean;
  status: 'ok' | 'conflict' | 'missing';
  conflict_note: string | null;
}

export interface CrmForm {
  case_id: string;
  sections: { id: string; title: string; fields: CrmField[] }[];
  summary: {
    source_documents: number;
    fields_total: number;
    fields_filled: number;
    fill_percent: number;
    conflicts: number;
    avg_confidence: number | null;
    missing_documents: string[];
  };
}

export interface AuditEventMsg {
  id: number;
  case_id: string;
  ts: string;
  actor: string;
  action: string;
  detail: string;
  tone: string;
  doc_id: string | null;
}

// ---------- fetch helper (unwraps the {ok, data} envelope) ----------
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(`${res.status} ${detail}`);
  }
  const body = await res.json();
  return (body && typeof body === 'object' && 'data' in body ? body.data : body) as T;
}

export const postJson = <T,>(path: string, body: unknown) =>
  api<T>(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

export function documentUrl(doc: Pick<CaseDocumentRecord, 'file_url'>): string {
  return `${API_URL}${doc.file_url}`;
}

// ---------- live updates: SSE with a polling safety net ----------
export const ALL_CASES = '*';

// One server-sent-events stream per browser tab, shared by every hook. Browsers allow only ~6 connections per address
// (shared across tabs), and a stream per hook used them all up, so uploads and other requests waited forever.
// The stream is closed while the tab is hidden and reopened (with a refresh) when it is shown again.
type Listener = { caseId: string; cb: (e: AuditEventMsg | null) => void };   // null = "the stream was down, reload"
const listeners = new Set<Listener>();
let hub: EventSource | null = null;

function openHub() {
  if (hub || typeof EventSource === 'undefined' || listeners.size === 0 || (typeof document !== 'undefined' && document.hidden)) return;
  hub = new EventSource(`${API_URL}/api/events`);
  hub.addEventListener('audit', (m) => {
    const ev = JSON.parse((m as MessageEvent).data) as AuditEventMsg;
    listeners.forEach((l) => { if (l.caseId === ALL_CASES || l.caseId === ev.case_id) l.cb(ev); });
  });
}

function closeHub() {
  hub?.close();
  hub = null;
}

if (typeof document !== 'undefined') {
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { closeHub(); return; }
    openHub();
    listeners.forEach((l) => l.cb(null));
  });
}

/** `caseId` = one case's audit events; ALL_CASES = every case (KAM dashboard). */
export function useCaseEvents(caseId: string | undefined, onEvent: (e: AuditEventMsg | null) => void) {
  const handler = useRef(onEvent);
  handler.current = onEvent;
  useEffect(() => {
    if (!caseId) return;
    const l: Listener = { caseId, cb: (e) => handler.current(e) };
    listeners.add(l);
    openHub();
    return () => {
      listeners.delete(l);
      if (listeners.size === 0) closeHub();
    };
  }, [caseId]);
}

/** Loads a resource and reloads it (debounced) on every audit event for the case, plus every `pollMs`. */
export function useLiveResource<T>(caseId: string | undefined, path: string | null, pollMs = 15000) {
  const [held, setHeld] = useState<{ path: string | null; data: T | null }>({ path, data: null });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const timer = useRef<number | undefined>(undefined);
  // data belongs to the path it was loaded from: switching case must never show the previous case's data
  const data = held.path === path ? held.data : null;
  const setData = useCallback((d: T | null) => setHeld({ path, data: d }), [path]);

  const load = useCallback(async () => {
    if (!path) return;
    try {
      const fresh = await api<T>(path);
      setHeld({ path, data: fresh });
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    void load();
    const poll = window.setInterval(() => void load(), pollMs);
    return () => window.clearInterval(poll);
  }, [load, pollMs]);

  useCaseEvents(caseId, () => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => void load(), 400);
  });

  return { data, error, loading, reload: load, setData };
}


// ---------- case-level types (mirror backend CaseRow / CaseDetail) ----------
export type Route = 'AUTO' | 'ASK' | 'ESCALATE';

export interface CaseRow {
  id: string;
  merchantName: string;
  legalName: string;
  entityType: string;
  stage: string;
  stageNumber: number;
  accountStatus: string;
  route: Route | null;
  flags: { label: string; severity: 'info' | 'warning' | 'critical' | 'ok' }[];
  aiConfidence: number;
  slaMinutes: number;
  isUrgent: boolean;
  docProgress: { uploaded: number; required: number; processed: number };
  lastUpdated: string;
  stageName?: string;
  kind?: 'merchant' | 'investigation';
  parentCaseId?: string | null;
  cpvStatus?: string | null;
  vcipStatus?: string | null;
}

export interface CaseList {
  kpis: {
    totalOpen: number;
    newThisWeek: number;
    pendingAiVerification: number;
    awaitingMerchant: number;
    readyForSubmission: number;
    escalations: number;
    awaitingChecker?: number;
    cpvInProgress?: number;
    vcipQueue?: number;
  };
  items: CaseRow[];
}

export interface CaseCheck {
  id: string;
  label: string;
  status: 'pass' | 'fail' | 'warn' | 'skip';
  detail: string;
  action: 'ask' | 'escalate' | null;
  evidence: { doc_id: string | null; doc_type: string | null; field: string | null; page: number | null; value: unknown; source: string }[];
}

export interface ChecklistEntry {
  doc_type: string;
  label: string;
  status: 'uploaded' | 'missing';
  doc_id: string | null;
}

export interface UploadReport {
  doc_ids: string[];
  documents: Pick<CaseDocumentRecord, 'doc_id' | 'filename' | 'sha256' | 'doc_type_label' | 'status'>[];
  rejected: { filename: string; reason: string }[];
}

export interface AskResult {
  question: string;
  answer: string;
  sources: { doc_id: string; filename: string; doc_type: string; doc_type_label: string }[];
  from_cache: boolean;
  note?: string;
}

export const DEMO_MERCHANT_CASE = 'KYB-20814';

export async function uploadDocuments(caseId: string, files: File[], slot: string | null): Promise<UploadReport> {
  const form = new FormData();
  files.forEach((f) => form.append('files', f, f.name));
  if (slot) form.append('slot', slot);
  return api<UploadReport>(`/api/cases/${caseId}/documents`, { method: 'POST', body: form });
}

export const sendCaseAction = (caseId: string, action: string, extra: { channel?: string; note?: string; actor?: string; phone?: string } = {}) =>
  postJson(`/api/cases/${caseId}/action`, { action, actor: 'kam', ...extra });

export const askCase = (caseId: string, question: string) => postJson<AskResult>(`/api/cases/${caseId}/ask`, { question });

export interface VoiceChaseContext {
  case_id: string;
  should_call: boolean;
  contact_phone: string | null;
  agent_variables: Record<string, string>;
  initial_bot_message: string;
  held_back_for_kam: string[];
}

export interface VoiceCallRecord {
  id: string;
  outcome: string;
  title: string;
  summary: string | null;
  transcript: { role: string; text: string }[];
  callId: string | null;
  memoryStatus: 'pending' | 'stored' | 'failed' | 'n/a';
  timestamp: string;
}

// ---------- Drishti: contact point verification ----------
export type CpvKind = 'exterior' | 'counter' | 'selfie';

export interface CpvCheck {
  id: string;
  label: string;
  status: 'pass' | 'fail' | 'warn' | 'skip';
  detail: string;
  assistive?: boolean;
  soft?: boolean;
}

export interface CpvView {
  sessionId: string;
  status: 'waiting' | 'captured' | 'analysing' | 'verified' | 'needs_review';
  link: string | null;
  expiresAt: string;
  required: CpvKind[];
  optional: CpvKind[];
  captured: Partial<Record<CpvKind, { lat: number; lon: number; accuracy_m: number; heading: number | null; client_ts: string; width: number; height: number }>>;
  verdict: 'CPV_VERIFIED' | 'NEEDS_REVIEW' | null;
  summary: string | null;
  checks: CpvCheck[];
  distanceM: number | null;
  reference: { address?: string; address_source?: string; source?: string; note?: string } | null;
  tradeName: string | null;
  ocr: { exterior?: string; counter?: string } | null;
  decidedBy: string | null;
}

export interface CpvCaptureState {
  merchantName: string;
  status: CpvView['status'];
  required: CpvKind[];
  optional: CpvKind[];
  captured: CpvView['captured'];
  expiresAt: string;
  verdict: CpvView['verdict'];
  summary: string | null;
  maxAccuracyM: number;
  demoUpload?: boolean;
}

export interface VcipView {
  status: 'queued' | 'interviewed' | 'signed_off';
  questions: { id: number; kind: string; hi: string; en: string; expected: string }[];
  transcript: { role: string; text: string }[];
  outcome: string | null;
  summary: string | null;
  callId: string | null;
  interviewedAt: string | null;
  signedOffBy: string | null;
  agentConfigured: boolean;
  contactPhone: string | null;
  referenceDocument: { docId: string; filename: string; label: string } | null;
  selfie: boolean;
  shopVerdict: string | null;
  faceMatch: { performed: boolean; note: string };
}

export const getCpvCapture = (token: string) => api<CpvCaptureState>(`/api/cpv/${encodeURIComponent(token)}`);

export interface CaptureMeta {
  kind: CpvKind;
  lat: number;
  lon: number;
  accuracyM: number;
  heading: number | null;
  source?: 'camera_stream' | 'demo_upload';
}

/** Uploads one live-camera frame. The page has no file picker: this is the only way a photo reaches the server. */
export async function postCpvCapture(token: string, blob: Blob, meta: CaptureMeta) {
  const form = new FormData();
  form.append('kind', meta.kind);
  form.append('lat', String(meta.lat));
  form.append('lon', String(meta.lon));
  form.append('accuracy_m', String(meta.accuracyM));
  if (meta.heading !== null) form.append('heading', String(meta.heading));
  form.append('client_ts', String(Date.now()));
  form.append('source', meta.source ?? 'camera_stream');
  form.append('image', blob, `${meta.kind}.jpg`);
  const ctl = new AbortController();
  const timer = window.setTimeout(() => ctl.abort(), 45000);
  try {
    return await api<{ captured: CpvKind[] }>(`/api/cpv/${encodeURIComponent(token)}/capture`, { method: 'POST', body: form, signal: ctl.signal });
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw new Error('The upload took too long. Check that the backend is running and try again.');
    throw e;
  } finally {
    window.clearTimeout(timer);
  }
}

export const submitCpv = (token: string) => postJson(`/api/cpv/${encodeURIComponent(token)}/submit`, {});
export const cpvImageUrl = (caseId: string, kind: CpvKind) => `${API_URL}/api/cases/${caseId}/cpv/images/${kind}`;
export const documentFileUrl = (docId: string) => `${API_URL}/api/documents/${docId}/file`;


// ---------- Settlement Agent (post-onboarding monitoring) ----------
export interface SettlementDay { day: string; volume: number; expected: number; actual: number; window: boolean }
export interface SettlementDetection {
  eligible: boolean;
  history_days: number;
  baseline_days: number;
  window: { from: string; to: string };
  thresholds: { velocity_pct: number; mismatch_pct: number };
  series: SettlementDay[];
  health: 'healthy' | 'watch' | 'critical' | 'unknown';
  note?: string;
  baseline_daily?: number;
  window_volume?: number;
  window_daily?: number;
  velocity_ratio?: number;
  velocity_pct?: number;
  txns_per_day_baseline?: number;
  txns_per_day_window?: number;
  expected?: number;
  actual?: number;
  difference?: number;
  difference_pct?: number;
  velocity_anomaly: boolean;
  settlement_anomaly: boolean;
  anomaly: boolean;
}
export interface FlaggedTxn {
  id: number; ref: string; ts: string; amount: number; status: 'captured' | 'refund' | 'chargeback'; channel: string; terminal: string; city: string;
  payer: string; batch: string | null; reasons: string[];
}
export interface SettlementCause { kind: 'held_batch' | 'chargebacks' | 'unexplained'; amount: number; batches?: string[]; count?: number; txn_count?: number; reason?: string }
export interface SettlementReconciliation {
  window: { from: string; to: string };
  expected: number; actual: number; difference: number; difference_pct: number;
  days: { day: string; expected: number; actual: number; difference: number }[];
  causes: SettlementCause[];
  shifts: { new_terminal_share_pct: number; new_city_share_pct: number; night_share_pct: number; top3_payer_share_pct: number; big_ticket_share_pct: number; usual_ticket: number };
  flagged: FlaggedTxn[]; flagged_total: number; flagged_amount: number; new_terminals: string[]; new_cities: string[];
}
export interface SettlementInvestigation {
  id: string; status: 'open' | 'resolved' | 'dismissed'; brief: string; briefSource: 'sarvam' | 'template';
  recommended: { title: string; severity: 'high' | 'medium' | 'low'; steps: string[]; decided_by: string };
  context: { source: 'cognee' | 'unavailable' | 'empty'; answer?: string; via?: string; note?: string };
  memoryStatus: 'pending' | 'stored' | 'failed'; createdAt: string;
}
export interface SettlementView {
  merchantCaseId: string; merchantName: string; synthetic: boolean;
  detection: SettlementDetection; reconciliation: SettlementReconciliation | null; investigation: SettlementInvestigation | null;
  demoControls: boolean; monitored: boolean;
}
export const runSettlementScan = (caseId: string) => postJson<{ status: string; via: string }>(`/api/cases/${caseId}/settlements/scan`, {});
export const settlementDemo = (caseId: string, what: 'spike' | 'reset') => postJson(`/api/cases/${caseId}/settlements/demo/${what}`, {});

// ---------- KAM housekeeping (delete a submitted file; reset a demo case) ----------
export interface DeleteResult { deleted: string; doc_id: string; memory: string; remaining: number; outcome: string }
export const deleteDocument = (docId: string) => api<DeleteResult>(`/api/documents/${docId}?actor=kam`, { method: 'DELETE' });
export const resetDemoCase = (caseId: string) => postJson<{ case_id: string; memory: string }>(`/api/cases/${caseId}/demo/reset`, {});
