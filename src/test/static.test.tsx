/** Preview mode: the recorded snapshot is served when the backend cannot be reached, reads work, changes are refused, HTTP errors are not hidden. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api, askCase, documentUrl, sendCaseAction } from '@/services/api';
import { isStaticMode, resetStaticMode } from '@/services/staticDemo';

const SNAP = {
  generated: '2026-10-05T00:00:00Z', note: 'test', heroCase: 'KYB-1',
  cases: { kpis: { totalOpen: 1 }, items: [{ id: 'KYB-1', merchantName: 'Sharma Foods Pvt Ltd' }] },
  details: { 'KYB-1': { id: 'KYB-1', merchantName: 'Sharma Foods Pvt Ltd' } },
  documents: { 'KYB-1': [{ doc_id: 'd1', file_url: '/api/documents/d1/file' }] },
  crm: { 'KYB-1': { sections: [{ key: 'business' }] } },
  asks: { 'KYB-1': { 'who owns more than 10% of this company, directly or indirectly': { answer: 'Rakesh Sharma holds 18% indirectly.', sources: [] } } },
  settlements: { 'KYB-2': { merchantName: 'Annapurna' } },
};

function backend(opts: { down?: boolean; status?: number; snapshot?: boolean }) {
  const calls: string[] = [];
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    calls.push(url);
    if (url.includes('/demo/snapshot.json')) {
      return opts.snapshot === false ? { ok: false, status: 404, statusText: 'Not Found', json: async () => ({}) } : { ok: true, status: 200, statusText: 'OK', json: async () => SNAP };
    }
    if (opts.down) throw new TypeError('Failed to fetch');
    return { ok: (opts.status ?? 200) < 400, status: opts.status ?? 200, statusText: 'x', json: async () => ({ ok: true, data: { live: true }, detail: 'boom' }) };
  }));
  return calls;
}

beforeEach(() => resetStaticMode());
afterEach(() => { vi.unstubAllGlobals(); resetStaticMode(); });

describe('preview mode (no backend)', () => {
  it('serves the recorded case when the backend cannot be reached, and says it is in preview mode', async () => {
    backend({ down: true });
    expect(isStaticMode()).toBe(false);
    const detail = await api<{ merchantName: string }>('/api/cases/KYB-1');
    expect(detail.merchantName).toBe('Sharma Foods Pvt Ltd');
    expect(isStaticMode()).toBe(true);
    expect((await api<{ items: unknown[] }>('/api/cases')).items).toHaveLength(1);
    expect(await api('/api/cases/KYB-1/documents')).toHaveLength(1);
    expect(await api('/api/cases/KYB-1/crm-form')).toEqual({ sections: [{ key: 'business' }] });
    expect(await api('/api/cases/KYB-2/settlements')).toEqual({ merchantName: 'Annapurna' });
  });

  it('refuses anything that changes data, with a clear reason, and without calling the network again', async () => {
    const calls = backend({ down: true });
    await api('/api/cases');
    const before = calls.length;
    await expect(sendCaseAction('KYB-1', 'approve', { actor: 'kam' })).rejects.toThrow(/Preview mode: this needs the backend/);
    await expect(api('/api/documents/d1?actor=kam', { method: 'DELETE' })).rejects.toThrow(/Preview mode/);
    expect(calls.length).toBe(before);
  });

  it('answers the recorded Ask-this-case questions (case and punctuation do not matter) and says so for others', async () => {
    backend({ down: true });
    const a = await askCase('KYB-1', 'WHO OWNS MORE THAN 10% OF THIS COMPANY,  directly or indirectly?');
    expect(a.answer).toMatch(/18% indirectly/);
    await expect(askCase('KYB-1', 'What is the weather?')).rejects.toThrow(/only the suggested questions are answered/);
  });

  it('points document files at the bundled copies', async () => {
    backend({ down: true });
    await api('/api/cases');
    expect(documentUrl({ file_url: '/api/documents/d1/file' })).toBe('/demo/files/d1.pdf');
  });

  it('does not hide a real server error: an HTTP error is shown, not replaced by the snapshot', async () => {
    backend({ status: 500 });
    await expect(api('/api/cases')).rejects.toThrow(/500/);
    expect(isStaticMode()).toBe(false);
  });

  it('with the backend up, nothing changes: live data is used and the snapshot is never needed', async () => {
    const calls = backend({});
    expect(await api('/api/cases')).toEqual({ live: true });
    expect(isStaticMode()).toBe(false);
    expect(calls.some((u) => u.includes('/demo/snapshot.json'))).toBe(false);
  });

  it('without a snapshot, a down backend is reported as before', async () => {
    backend({ down: true, snapshot: false });
    await expect(api('/api/cases')).rejects.toThrow(/Failed to fetch/);
    expect(isStaticMode()).toBe(false);
  });
});

describe('the recorded snapshot file (public/demo)', () => {
  it('is complete and consistent: every document has its PDF, every cited source is a document of the snapshot, the filled form and the checks are there', async () => {
    const fs = await import('node:fs');
    const snap = JSON.parse(fs.readFileSync('public/demo/snapshot.json', 'utf-8'));
    const hero = snap.heroCase as string;
    const docs = snap.documents[hero] as { doc_id: string; file_url: string; fields: Record<string, unknown> }[];
    expect(docs.length).toBe(9);
    for (const d of docs) {
      expect(fs.existsSync(`public/demo/files/${d.doc_id}.pdf`)).toBe(true);
      expect(d.file_url).toBe(`/api/documents/${d.doc_id}/file`);
    }
    const ids = new Set(docs.map((d) => d.doc_id));
    const answers = Object.values(snap.asks[hero]) as { answer: string; from_cache: boolean; sources: { doc_id: string }[] }[];
    expect(answers.length).toBeGreaterThanOrEqual(3);
    for (const a of answers) {
      expect(a.from_cache).toBe(false);
      expect(a.sources.every((s) => ids.has(s.doc_id))).toBe(true);
    }
    expect(snap.details[hero].route).toBe('ESCALATE');
    expect((snap.details[hero].checks as { status: string }[]).filter((c) => c.status === 'fail')).toHaveLength(4);
    expect(snap.crm[hero].summary.fill_percent).toBe(100);
    expect(Object.keys(snap.details)).toEqual(expect.arrayContaining(['KYB-20814', 'KYB-20815', 'KYB-20816', 'KYB-20817', 'KYB-20818']));
  });
});
