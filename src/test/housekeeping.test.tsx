/** KAM housekeeping: delete a submitted file, reset a demo case; and the merchant portal following a deletion. Real captured case, mocked fetch. */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import caseHeroFx from './fixtures/case-hero.json';
import { CaseDetailOverview } from '@/components/kam/CaseDetailOverview';
import { MerchantUploadScreen } from '@/components/merchant/MerchantUploadScreen';
import type { MerchantCase } from '@/types/case';

vi.mock('@/components/kam/PdfEvidenceViewer', () => ({ PdfEvidenceViewer: () => <div /> }));

const hero = caseHeroFx.data as unknown as MerchantCase;
const calls: { url: string; method: string }[] = [];
function mockFetch(routes: Record<string, { status?: number; body: unknown }>) {
  calls.length = 0;
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, method: init?.method ?? 'GET' });
    const key = Object.keys(routes).find((k) => url.includes(k));
    if (!key) return { ok: true, status: 200, statusText: 'OK', json: async () => ({ ok: true, data: null }) };
    const { status = 200, body } = routes[key];
    return { ok: status < 400, status, statusText: status < 400 ? 'OK' : 'Error', json: async () => body };
  }));
}
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

const noop = vi.fn();

describe('Delete a submitted file (KAM)', () => {
  it('shows a delete button per uploaded file, confirms, calls the API and says what happened', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    mockFetch({ '/api/documents/': { body: { ok: true, data: { deleted: 'GST.pdf', doc_id: 'd1', memory: 'Removed 2 item(s)', remaining: 7, outcome: 'The checks were re-run on the 7 remaining document(s): route ESCALATE.' } } } });
    render(<CaseDetailOverview caseData={{ ...hero, stage: 4 }} onBack={noop} onSwitchRole={noop} onAction={noop} />);
    const buttons = screen.getAllByRole('button', { name: /^Delete / });
    expect(buttons.length).toBe((hero.uploaded ?? []).filter((u) => u.doc_id).length);
    fireEvent.click(buttons[0]);
    await waitFor(() => expect(calls.some((c) => c.method === 'DELETE' && /\/api\/documents\/[^?]+\?actor=kam$/.test(c.url))).toBe(true));
    expect(await screen.findByText(/Deleted GST\.pdf\. The checks were re-run/)).toBeInTheDocument();
  });

  it('does nothing when the KAM cancels the confirmation', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    mockFetch({});
    render(<CaseDetailOverview caseData={{ ...hero, stage: 4 }} onBack={noop} onSwitchRole={noop} onAction={noop} />);
    fireEvent.click(screen.getAllByRole('button', { name: /^Delete / })[0]);
    expect(calls.some((c) => c.method === 'DELETE')).toBe(false);
  });

  it('is not offered to Compliance, or once the case is with Compliance', () => {
    mockFetch({});
    const { unmount } = render(<CaseDetailOverview caseData={{ ...hero, stage: 4 }} onBack={noop} onSwitchRole={noop} onAction={noop} isCompliancePersona />);
    expect(screen.queryByRole('button', { name: /^Delete / })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Reset demo case/ })).not.toBeInTheDocument();
    unmount();
    render(<CaseDetailOverview caseData={{ ...hero, stage: 5 }} onBack={noop} onSwitchRole={noop} onAction={noop} />);
    expect(screen.queryByRole('button', { name: /^Delete / })).not.toBeInTheDocument();
  });

  it('shows the server reason when a delete is refused', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    mockFetch({ '/api/documents/': { status: 409, body: { detail: 'This case has already been submitted to Compliance, so its files are locked.' } } });
    render(<CaseDetailOverview caseData={{ ...hero, stage: 4 }} onBack={noop} onSwitchRole={noop} onAction={noop} />);
    fireEvent.click(screen.getAllByRole('button', { name: /^Delete / })[0]);
    expect(await screen.findByText(/files are locked/)).toBeInTheDocument();
  });
});

describe('Reset demo case', () => {
  it('asks first, then resets, and shows the server refusal when demo controls are off', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    mockFetch({ '/demo/reset': { body: { ok: true, data: { case_id: 'KYB-20814', memory: 'The merchant twin was deleted.' } } } });
    const { unmount } = render(<CaseDetailOverview caseData={{ ...hero, stage: 4 }} onBack={noop} onSwitchRole={noop} onAction={noop} />);
    fireEvent.click(screen.getByRole('button', { name: /Reset demo case/ }));
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.url.endsWith('/api/cases/KYB-20814/demo/reset'))).toBe(true));
    expect(await screen.findByText(/Case reset to its starting state/)).toBeInTheDocument();
    unmount();

    mockFetch({ '/demo/reset': { status: 403, body: { detail: 'Demo controls are disabled. Set CPV_ALLOW_DEMO_REFERENCE=true' } } });
    render(<CaseDetailOverview caseData={{ ...hero, stage: 4 }} onBack={noop} onSwitchRole={noop} onAction={noop} />);
    fireEvent.click(screen.getByRole('button', { name: /Reset demo case/ }));
    expect(await screen.findByText(/Demo controls are disabled/)).toBeInTheDocument();
  });
});

describe('Merchant portal follows a deletion', () => {
  const props = { onUploadFiles: vi.fn(), onOpenKAM: vi.fn(), onNavigate: vi.fn() };

  it('drops a deleted file from the upload page so it can be uploaded again', () => {
    const { rerender } = render(<MerchantUploadScreen view="upload" caseData={hero} {...props} />);
    const full = screen.queryAllByText('Uploaded').length;
    expect(full).toBeGreaterThan(0);
    const without = { ...hero, uploaded: (hero.uploaded ?? []).filter((u) => u.doc_type !== 'bank_cheque') };
    rerender(<MerchantUploadScreen view="upload" caseData={without} {...props} />);
    expect(screen.queryAllByText('Uploaded').length).toBe(full - 1);
  });

  it('is empty again after a reset', () => {
    const { rerender } = render(<MerchantUploadScreen view="upload" caseData={hero} {...props} />);
    rerender(<MerchantUploadScreen view="upload" caseData={{ ...hero, uploaded: [], missing: [] }} {...props} />);
    expect(screen.queryAllByText('Uploaded').length).toBe(0);
    expect(screen.getByText('No documents uploaded yet')).toBeInTheDocument();
  });
});
