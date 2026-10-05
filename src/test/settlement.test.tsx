/** Settlement Agent UI. fetch is mocked with REAL responses captured from the backend (src/test/fixtures/settlements-*.json, case-investigation.json). Synthetic data. */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import settlementFx from './fixtures/settlements-merchant.json';
import invCaseFx from './fixtures/case-investigation.json';
import merchantCaseFx from './fixtures/case-merchant-live.json';
import casesFx from './fixtures/cases-with-investigation.json';
import { CaseDetailOverview } from '@/components/kam/CaseDetailOverview';
import { KamDashboardView } from '@/components/kam/KamDashboardView';
import { ComplianceDashboardView } from '@/components/kam/ComplianceDashboardView';
import { SettlementsTab } from '@/components/kam/SettlementsTab';
import { inr } from '@/services/format';
import type { MerchantCase } from '@/types/case';

vi.mock('@/components/kam/PdfEvidenceViewer', () => ({ PdfEvidenceViewer: () => <div /> }));

const calls: { url: string; method: string; body?: string }[] = [];
function mockFetch(routes: Record<string, unknown>) {
  calls.length = 0;
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, method: init?.method ?? 'GET', body: typeof init?.body === 'string' ? init.body : undefined });
    const key = Object.keys(routes).find((k) => url.includes(k));
    if (!key) return { ok: false, status: 404, statusText: 'Not Found', json: async () => ({ detail: `no mock for ${url}` }) };
    return { ok: true, status: 200, statusText: 'OK', json: async () => routes[key] };
  }));
}
afterEach(() => vi.unstubAllGlobals());

const invCase = invCaseFx.data as unknown as MerchantCase;
const merchantCase = merchantCaseFx.data as unknown as MerchantCase;
const noop = vi.fn();

describe('Indian rupee formatting', () => {
  it('groups digits the Indian way', () => {
    expect(inr(1500000)).toBe('₹15,00,000');
    expect(inr(42584)).toBe('₹42,584');
    expect(inr(-624780)).toBe('-₹6,24,780');
    expect(inr(undefined)).toBe('–');
  });
});

describe('Settlements tab', () => {
  it('shows expected, actual, difference, velocity and health from the backend', async () => {
    mockFetch({ '/settlements': settlementFx });
    render(<SettlementsTab caseId="KYB-20820" />);
    expect(await screen.findByText('Expected settlement')).toBeInTheDocument();
    const d = settlementFx.data.detection;
    expect(screen.getByText('Actual settlement')).toBeInTheDocument();
    expect(screen.getByText('Transaction velocity')).toBeInTheDocument();
    expect(screen.getByText(inr(d.expected))).toBeInTheDocument();
    expect(screen.getByText(inr(d.actual))).toBeInTheDocument();
    expect(screen.getByText(`${inr(d.difference)} · ${d.difference_pct}%`)).toBeInTheDocument();
    expect(screen.getByText(`${d.velocity_pct}% of baseline`)).toBeInTheDocument();
    expect(screen.getAllByText('Critical').length).toBeGreaterThan(0);
    expect(screen.getByText('Synthetic ledger')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Daily settlement volume' })).toBeInTheDocument();
  });

  it('shows the investigation, its recommendation, what the twin holds and the attached payments', async () => {
    mockFetch({ '/settlements': settlementFx });
    render(<SettlementsTab caseId="KYB-20820" />);
    const panel = await screen.findByLabelText('Investigation');
    const inv = settlementFx.data.investigation!;
    expect(within(panel).getByText(new RegExp(inv.id))).toBeInTheDocument();
    expect(within(panel).getByText(inv.brief)).toBeInTheDocument();
    expect(within(panel).getByText(new RegExp(`Recommended action: ${inv.recommended.title}`))).toBeInTheDocument();
    expect(within(panel).getByText(/What the merchant twin \(Cognee\) holds/)).toBeInTheDocument();
    expect(within(panel).getByText(/The agent has not moved or held any money/)).toBeInTheDocument();
    expect(within(panel).getByText(/every number was checked against the ledger/)).toBeInTheDocument();
    const first = settlementFx.data.reconciliation!.flagged[0];
    expect(screen.getByText(first.ref)).toBeInTheDocument();
    expect(screen.getAllByText(/T-09 · Jaipur/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Reconciliation: why expected/)).toBeInTheDocument();
    expect(screen.getAllByText(/held batch/).length).toBeGreaterThan(0);
  });

  it('starts the agent and offers the demo controls only when the backend allows them', async () => {
    mockFetch({ '/settlements/scan': { ok: true, data: { status: 'started', via: 'n8n' } }, '/settlements': settlementFx });
    const toast = vi.fn();
    const { unmount } = render(<SettlementsTab caseId="KYB-20820" onToast={toast} />);
    fireEvent.click(await screen.findByRole('button', { name: /Run settlement check/ }));
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.url.endsWith('/api/cases/KYB-20820/settlements/scan'))).toBe(true));
    await waitFor(() => expect(toast).toHaveBeenCalledWith(expect.stringMatching(/started in n8n/)));
    expect(screen.getByRole('button', { name: /Inject 48-hour spike/ })).toBeInTheDocument();
    unmount();

    mockFetch({ '/settlements': { ok: true, data: { ...settlementFx.data, demoControls: false } } });
    render(<SettlementsTab caseId="KYB-20820" />);
    await screen.findByText('Expected settlement');
    expect(screen.queryByRole('button', { name: /Inject 48-hour spike/ })).not.toBeInTheDocument();
  });

  it('says so when the merchant twin could not be read', async () => {
    const down = { ...settlementFx.data, investigation: { ...settlementFx.data.investigation!, context: { source: 'unavailable', note: 'Cognee unreachable', via: 'n8n recall' } } };
    mockFetch({ '/settlements': { ok: true, data: down } });
    render(<SettlementsTab caseId="KYB-20820" />);
    expect(await screen.findByText(/could not be read \(Cognee unreachable\)/)).toBeInTheDocument();
  });

  it('makes no claims without a baseline and says why', async () => {
    const none = { ...settlementFx.data, investigation: null, reconciliation: null, detection: { ...settlementFx.data.detection, eligible: false, health: 'unknown', anomaly: false, note: 'Only 4 days of history: the agent needs 30 to set a baseline, so it makes no anomaly claims yet.' } };
    mockFetch({ '/settlements': { ok: true, data: none } });
    render(<SettlementsTab caseId="KYB-20820" />);
    expect(await screen.findByText(/makes no anomaly claims yet/)).toBeInTheDocument();
    expect(screen.queryByText('Expected settlement')).not.toBeInTheDocument();
  });

  it('is explained, not empty, for a merchant that is not live yet', async () => {
    mockFetch({ '/settlements': { ok: true, data: { ...settlementFx.data, monitored: false, investigation: null, reconciliation: null } } });
    render(<SettlementsTab caseId="KYB-20814" />);
    expect(await screen.findByText(/starts after activation/)).toBeInTheDocument();
  });
});

describe('Case Detail for the settlement investigation (the existing Exception Card, Needs Attention queue and Timeline)', () => {
  it('opens on Settlements, shows the exception cards, the timeline steps, and lets only the KAM resolve or dismiss', async () => {
    mockFetch({ '/settlements': settlementFx, '/crm-form': { ok: true, data: null } });
    const onAction = vi.fn().mockResolvedValue(undefined);
    render(<CaseDetailOverview caseData={invCase} onBack={noop} onSwitchRole={noop} onAction={onAction} />);
    expect(await screen.findByText('Expected settlement')).toBeInTheDocument();                       // opens on the Settlements tab
    expect(screen.queryByText(/Interactive PDF Evidence/)).not.toBeInTheDocument();                   // onboarding-only tabs are hidden
    fireEvent.click(screen.getByRole('button', { name: /Overview/ }));
    expect(screen.getByText('Exception cards (rule-based signals)')).toBeInTheDocument();
    for (const t of ['Transaction velocity', 'Settlement mismatch', 'New terminal in another city']) expect(screen.getAllByText(t).length).toBeGreaterThan(0);
    for (const step of ['MONITOR', 'RECONCILE', 'INVESTIGATE', 'CREATE CASE', 'ESCALATE']) expect(screen.getAllByText(new RegExp(`Settlement Agent · ${step}`)).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Uploaded Documents/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Approve & Forward/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Resolve/ }));
    await waitFor(() => expect(onAction).toHaveBeenCalledWith('inv_resolve', undefined, undefined));
    fireEvent.click(screen.getByRole('button', { name: /Dismiss/ }));
    await waitFor(() => expect(onAction).toHaveBeenCalledWith('inv_dismiss', undefined, undefined));
  });

  it('gives Compliance no resolve or dismiss', async () => {
    mockFetch({ '/settlements': settlementFx });
    render(<CaseDetailOverview caseData={invCase} onBack={noop} onSwitchRole={noop} onAction={noop} isCompliancePersona />);
    await screen.findByText('Expected settlement');
    expect(screen.queryByRole('button', { name: /^Resolve/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Dismiss/ })).not.toBeInTheDocument();
  });

  it('a live merchant gets a Settlements tab next to its onboarding tabs, and no approval buttons', async () => {
    mockFetch({ '/settlements': settlementFx, '/crm-form': { ok: true, data: null } });
    render(<CaseDetailOverview caseData={merchantCase} onBack={noop} onSwitchRole={noop} onAction={noop} />);
    expect(screen.getByText(/Interactive PDF Evidence/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Settlements/ }));
    expect(await screen.findByText('Expected settlement')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Approve & Forward/ })).not.toBeInTheDocument();
  });
});

describe('Queues', () => {
  it('the investigation sits in the existing KAM pipeline as an escalated, tagged case, and opens its merchant as the merchant', async () => {
    mockFetch({ '/api/cases': casesFx });
    const asMerchant = vi.fn();
    render(<KamDashboardView onOpenCase={noop} onOpenAsMerchant={asMerchant} />);
    const row = (await screen.findAllByText(/Settlement investigation/))[0].closest('tr')!;
    expect(within(row).getByText('ESCALATE')).toBeInTheDocument();
    fireEvent.click(within(row).getByRole('button', { name: 'View as merchant' }));
    expect(asMerchant).toHaveBeenCalledWith('KYB-20820');
  });

  it('the Compliance desk leaves settlement investigations to the KAM', async () => {
    mockFetch({ '/api/cases': casesFx });
    render(<ComplianceDashboardView onOpenCase={noop} onOpenAsMerchant={noop} />);
    await screen.findByText('What needs your decision');
    expect(screen.queryByText(/INV-3000/)).not.toBeInTheDocument();
  });
});
