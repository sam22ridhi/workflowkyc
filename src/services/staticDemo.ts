/**
 * Preview mode: a recorded, read-only snapshot of the synthetic Sharma Foods case, served from static files (public/demo/) so the app is usable
 * with NO backend (a frontend-only deployment). Everything in the snapshot is real output of the system, recorded by backend/scripts/export_static_snapshot.py.
 *
 * It turns on in two ways: a build with VITE_STATIC_DEMO=true, or automatically when the backend cannot be reached (a network error, never an HTTP error).
 * Reading works (cases, documents with their evidence boxes, the filled MAF form, the Settlements tab, the suggested Ask-this-case questions).
 * Anything that changes data is refused with a clear message.
 */
import { useSyncExternalStore } from 'react';

interface Snapshot {
  generated: string;
  note: string;
  heroCase: string;
  cases: unknown;
  details: Record<string, unknown>;
  documents: Record<string, unknown[]>;
  crm: Record<string, unknown>;
  asks: Record<string, Record<string, unknown>>;
  settlements: Record<string, unknown>;
}

const BASE = (import.meta.env.BASE_URL as string | undefined) ?? '/';
const FORCED = (import.meta.env.VITE_STATIC_DEMO as string | undefined) === 'true';

let active = FORCED;
let snapshot: Promise<Snapshot | null> | null = null;
const listeners = new Set<() => void>();

export const isStaticMode = (): boolean => active;
export const onStaticModeChange = (cb: () => void): (() => void) => { listeners.add(cb); return () => { listeners.delete(cb); }; };

export function activateStaticMode(): void {
  if (active) return;
  active = true;
  listeners.forEach((l) => l());
}

/** For tests. */
export function resetStaticMode(): void {
  active = FORCED;
  snapshot = null;
  listeners.forEach((l) => l());
}

/** React: re-renders when preview mode turns on. */
export function useStaticMode(): boolean {
  return useSyncExternalStore(onStaticModeChange, isStaticMode, isStaticMode);
}

export function loadSnapshot(): Promise<Snapshot | null> {
  snapshot ??= (async () => {
    try {
      const res = await fetch(`${BASE}demo/snapshot.json`);
      if (!res.ok) return null;
      const body = (await res.json()) as Snapshot;
      return body && typeof body === 'object' && body.cases && body.details ? body : null;
    } catch {
      return null;
    }
  })();
  return snapshot;
}

export const staticFileUrl = (docId: string): string => `${BASE}demo/files/${docId}.pdf`;

const REFUSED = 'Preview mode: this needs the backend. You are looking at a recorded snapshot of the synthetic Sharma Foods case, so nothing can be changed here.';

const normalise = (q: string) => q.toLowerCase().split(/\s+/).filter(Boolean).join(' ').replace(/[?. ]+$/, '');

/** Answers an API call from the snapshot. Throws errors shaped like the real ones ("404 ...") so the screens show them the way they already do. */
export async function staticApi<T>(path: string, init?: RequestInit): Promise<T> {
  const snap = await loadSnapshot();
  if (!snap) throw new Error('503 The recorded preview is not available.');
  const method = (init?.method ?? 'GET').toUpperCase();
  const clean = path.split('?')[0];
  const parts = clean.replace(/^\/api\//, '').split('/');                   // ['cases', 'KYB-20814', 'documents']

  if (method === 'POST' && parts[0] === 'cases' && parts[2] === 'ask') {
    const q = normalise(String((JSON.parse(String(init?.body ?? '{}')) as { question?: string }).question ?? ''));
    const hit = snap.asks[parts[1]]?.[q];
    if (hit) return hit as T;
    throw new Error('404 In the recorded preview only the suggested questions are answered. The live app answers any question about the case.');
  }
  if (method !== 'GET') throw new Error(`409 ${REFUSED}`);

  if (parts[0] === 'cases' && parts.length === 1) return snap.cases as T;
  if (parts[0] === 'cases' && parts.length === 2 && snap.details[parts[1]]) return snap.details[parts[1]] as T;
  if (parts[0] === 'cases' && parts[2] === 'documents') return (snap.documents[parts[1]] ?? []) as T;
  if (parts[0] === 'cases' && parts[2] === 'crm-form' && snap.crm[parts[1]]) return snap.crm[parts[1]] as T;
  if (parts[0] === 'cases' && parts[2] === 'settlements' && snap.settlements[parts[1]]) return snap.settlements[parts[1]] as T;
  throw new Error('404 This is not part of the recorded preview.');
}
