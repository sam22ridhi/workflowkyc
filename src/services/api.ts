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

/** `caseId` = one case's audit stream; ALL_CASES = every case (KAM dashboard). */
export function useCaseEvents(caseId: string | undefined, onEvent: (e: AuditEventMsg) => void) {
  const handler = useRef(onEvent);
  handler.current = onEvent;
  useEffect(() => {
    if (!caseId) return;
    const source = new EventSource(`${API_URL}${caseId === ALL_CASES ? '/api/events' : `/api/cases/${caseId}/events`}`);
    source.addEventListener('audit', (m) => handler.current(JSON.parse((m as MessageEvent).data) as AuditEventMsg));
    return () => source.close();
  }, [caseId]);
}

/** Loads a resource and reloads it (debounced) on every audit event for the case, plus every `pollMs`. */
export function useLiveResource<T>(caseId: string | undefined, path: string | null, pollMs = 15000) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const timer = useRef<number | undefined>(undefined);

  const load = useCallback(async () => {
    if (!path) return;
    try {
      setData(await api<T>(path));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => {
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
}

export interface CaseList {
  kpis: {
    totalOpen: number;
    newThisWeek: number;
    pendingAiVerification: number;
    awaitingMerchant: number;
    readyForSubmission: number;
    escalations: number;
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
