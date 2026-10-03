/**
 * Render tests for the screens wired to the backend. fetch is mocked with REAL responses captured from the running
 * backend (src/test/fixtures/*.json: the Sharma Foods hero case after the full pipeline; all data is synthetic).
 */
import { fireEvent, render, renderHook, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import casesFx from './fixtures/cases.json';
import caseHeroFx from './fixtures/case-hero.json';
import caseAutoFx from './fixtures/case-auto.json'; // KYB-20818: demo-seeded AUTO case
import crmFx from './fixtures/crm-hero.json';
import askFx from './fixtures/ask-hero.json';
import caseVoiceFx from './fixtures/case-voice.json'; // KYB-20817 after a (TEST) call went through n8n -> backend -> Cognee
import { CaseDetailOverview } from '@/components/kam/CaseDetailOverview';
import { KamDashboardView } from '@/components/kam/KamDashboardView';
import { MerchantUploadScreen } from '@/components/merchant/MerchantUploadScreen';
import { useLiveCase } from '@/services/useLiveCase';
import type { MerchantCase } from '@/types/case';

// pdf.js cannot run in jsdom; the viewer is covered separately. Here it just reports what it was told to focus.
vi.mock('@/components/kam/PdfEvidenceViewer', () => ({
  PdfEvidenceViewer: (props: { caseId: string; focus?: { docId: string; field: string } | null }) => (
    <div data-testid="viewer" data-case={props.caseId} data-doc={props.focus?.docId ?? ''} data-field={props.focus?.field ?? ''} />
  ),
}));

const hero = caseHeroFx.data as unknown as MerchantCase;
const VOICE_CTX = {
  case_id: 'KYB-20814', should_call: true, contact_phone: null,
  agent_variables: { contact_name: 'Anil Sharma', issue_count: '2', documents_needed_en: '1. a cancelled cheque or bank letter showing the full legal name; 2. confirmation of the business address' },
  initial_bot_message: 'नमस्ते Anil Sharma, मैं पेटीएम से कार्यकर्ता बोल रही हूँ',
  held_back_for_kam: ['Board-resolution signatory is a current director'],
};
const calls: { url: string; method: string; body?: string }[] = [];

type Route = unknown | ((init?: RequestInit) => unknown);
function mockFetch(routes: Record<string, Route>, fail = false) {
  calls.length = 0;
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, method: init?.method ?? 'GET', body: typeof init?.body === 'string' ? init.body : undefined });
    if (fail) throw new TypeError('Failed to fetch');
    const key = Object.keys(routes).find((k) => url.includes(k));
    if (!key) return { ok: false, status: 404, statusText: 'Not Found', json: async () => ({ detail: `no mock for ${url}` }) };
    const r = routes[key];
    const body = typeof r === 'function' ? (r as (i?: RequestInit) => unknown)(init) : r;
    return { ok: true, status: 200, statusText: 'OK', json: async () => body };
  }));
}

beforeEach(() => vi.useRealTimers());
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('KAM dashboard (live /api/cases)', () => {
  it('shows the 5 KPIs, case rows, routes and flags from the backend', async () => {
    mockFetch({ '/api/cases': casesFx });
    const open = vi.fn();
    render(<KamDashboardView onOpenCase={open} />);

    expect(await screen.findByText('Sharma Foods Pvt Ltd')).toBeInTheDocument();
    const kpis = casesFx.data.kpis;
    expect(kpis.escalations).toBe(1);
    for (const label of ['Total Open Cases', 'Pending AI Verification', 'Awaiting Merchant', 'Ready for Submission', 'Escalations (Red)']) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.getByText(String(kpis.totalOpen))).toBeInTheDocument();

    const heroRow = screen.getByText('Sharma Foods Pvt Ltd').closest('tr')!;
    expect(within(heroRow).getByText('Escalated to KAM')).toBeInTheDocument();
    expect(within(heroRow).getByText('ESCALATE')).toBeInTheDocument();
    expect(within(heroRow).getByText('8/8')).toBeInTheDocument();
    expect(within(heroRow).getByText(/\+2 more/)).toBeInTheDocument();                 // 4 critical flags, 2 shown

    const autoRow = screen.getByText('Zenith Tech Solutions').closest('tr')!;
    expect(within(autoRow).getByText('AUTO')).toBeInTheDocument();
    expect(within(autoRow).getByText(/Verified/)).toBeInTheDocument();

    fireEvent.click(heroRow);
    expect(open).toHaveBeenCalledWith('KYB-20814');
    fireEvent.click(screen.getByRole('button', { name: /Open Priority Case \(Sharma Foods Pvt Ltd\)/ }));
    expect(open).toHaveBeenLastCalledWith('KYB-20814');
  });

  it('filters by urgency and search', async () => {
    mockFetch({ '/api/cases': casesFx });
    render(<KamDashboardView onOpenCase={vi.fn()} />);
    await screen.findByText('Sharma Foods Pvt Ltd');
    fireEvent.change(screen.getByPlaceholderText(/Search merchant/), { target: { value: 'apex' } });
    expect(screen.queryByText('Sharma Foods Pvt Ltd')).not.toBeInTheDocument();
    expect(screen.getByText('Apex Cloud Telecom')).toBeInTheDocument();
  });

  it('says so when the backend is down instead of showing fake rows', async () => {
    mockFetch({}, true);
    render(<KamDashboardView onOpenCase={vi.fn()} />);
    expect(await screen.findByText(/Could not load cases/)).toBeInTheDocument();
    expect(screen.queryByText('Sharma Foods Pvt Ltd')).not.toBeInTheDocument();
  });
});

describe('Case overview (live case)', () => {
  const setup = (over: Partial<Parameters<typeof CaseDetailOverview>[0]> = {}) => {
    mockFetch({
      '/crm-form': crmFx,
      '/api/cases/KYB-20814/ask': askFx,
      '/voice-chase/context': { ok: true, data: VOICE_CTX },
    });
    const onAction = vi.fn().mockResolvedValue(undefined);
    render(<CaseDetailOverview caseData={hero} onBack={vi.fn()} onSwitchRole={vi.fn()} onAction={onAction} {...over} />);
    return { onAction };
  };

  it('renders the header, live stage tracker and the 10 checks with their actions', () => {
    setup();
    expect(screen.getByRole('heading', { name: 'Sharma Foods Pvt Ltd' })).toBeInTheDocument();
    expect(screen.getByText(/Sharma Foods Private Limited · CIN: U56101MH2021PTC123456/)).toBeInTheDocument();
    expect(screen.getByText(/Cap reached/i)).toBeInTheDocument();
    expect(screen.getByText(/ESCALATE · needs human judgement/)).toBeInTheDocument();
    expect(screen.getByText(/Stage 4 of 8/)).toBeInTheDocument();
    expect(screen.getAllByText('KAM Review').length).toBeGreaterThan(0);

    expect(screen.getByText('6/10 passed')).toBeInTheDocument();
    expect(screen.getAllByText('Needs human judgement')).toHaveLength(2);           // signatory + beneficial owners
    expect(screen.getAllByText('Merchant can fix').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText(/Ravish Sahay is not a current director/).length).toBeGreaterThan(0);   // check detail + timeline
    expect(screen.getAllByText(/Rakesh Sharma 18% effective/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Navi Mumbai/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/4 issues found, 6 checks passed/).length).toBeGreaterThan(0);
  });

  it('lists uploaded documents live and has nothing missing for the hero case', () => {
    setup();
    expect(screen.getByText('Uploaded Documents (8/8)')).toBeInTheDocument();
    expect(screen.getByText('Missing & Action Required (2)')).toBeInTheDocument();   // the two merchant-fixable issues
  });

  it('opens the source document with the field focused when an evidence chip is clicked', () => {
    setup();
    const chip = screen.getAllByRole('button').find((b) => /GST Cert p\.1: 12 Mahatma Gandhi Marg/.test(b.textContent ?? ''))!;
    fireEvent.click(chip);
    const viewer = screen.getByTestId('viewer');
    expect(viewer).toHaveAttribute('data-case', 'KYB-20814');
    expect(viewer.getAttribute('data-doc')).toBeTruthy();
    expect(viewer).toHaveAttribute('data-field', 'principal_place_address');
  });

  it('answers a question about the case with sources, and a source opens its document', async () => {
    setup();
    fireEvent.change(screen.getByPlaceholderText(/Who owns more than 10%/), { target: { value: 'Who owns more than 10%?' } });
    fireEvent.click(screen.getByRole('button', { name: /^Ask$/ }));
    expect(await screen.findByText(/Rakesh Sharma/, { selector: 'div.whitespace-pre-wrap' })).toBeInTheDocument();
    const ask = calls.find((c) => c.url.endsWith('/ask'))!;
    expect(ask.method).toBe('POST');
    expect(JSON.parse(ask.body!)).toEqual({ question: 'Who owns more than 10%?' });
    const source = await screen.findByRole('button', { name: /Shareholding.*Shareholding_Declaration\.pdf/ });
    fireEvent.click(source);
    expect(screen.getByTestId('viewer').getAttribute('data-doc')).toBeTruthy();
  });

  it('shows a clear message (and keeps working) when case memory is unavailable', async () => {
    mockFetch({ '/crm-form': crmFx });   // /ask falls through to 404 -> error path
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => String(input).includes('/ask')
      ? { ok: false, status: 503, statusText: 'x', json: async () => ({ detail: 'Case memory is unavailable right now: Cognee Cloud rejected the credentials (401).' }) }
      : { ok: true, status: 200, statusText: 'OK', json: async () => crmFx }));
    render(<CaseDetailOverview caseData={hero} onBack={vi.fn()} onSwitchRole={vi.fn()} onAction={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /Who is the authorised signatory/ }));
    expect(await screen.findByText(/Case memory is unavailable/)).toBeInTheDocument();
    expect(screen.getByText(/Everything else on this case keeps working/)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Sharma Foods Pvt Ltd' })).toBeInTheDocument();
  });

  it('asks before forwarding an escalated case, then submits the approval', async () => {
    const { onAction } = setup();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true);
    fireEvent.click(screen.getByRole('button', { name: /Approve & Forward/ }));
    expect(onAction).not.toHaveBeenCalled();                                        // declined
    fireEvent.click(screen.getByRole('button', { name: /Approve & Forward/ }));
    await waitFor(() => expect(onAction).toHaveBeenCalledWith('approve', undefined, undefined));
    expect(confirm).toHaveBeenCalledTimes(2);
    expect(await screen.findByText(/Submitted to the Compliance/)).toBeInTheDocument();
  });

  it('sends the voice chase on the chosen channel with the real open issue as the request', async () => {
    const { onAction } = setup();
    fireEvent.click(screen.getByRole('button', { name: /^Voice Chase$/ }));
    expect(await screen.findByText(/The agent will call Anil Sharma and raise 2 item/)).toBeInTheDocument();
    expect(screen.getByText(/नमस्ते Anil Sharma/)).toBeInTheDocument();
    expect(screen.getByText('a cancelled cheque or bank letter showing the full legal name')).toBeInTheDocument();
    expect(screen.getByText(/NOT RAISED ON THE CALL/)).toBeInTheDocument();             // escalations stay with the KAM
    fireEvent.click(screen.getByRole('button', { name: 'WhatsApp' }));
    fireEvent.click(screen.getByRole('button', { name: /Send whatsapp request/ }));
    await waitFor(() => expect(onAction).toHaveBeenCalledWith('voice', 'whatsapp', undefined));        // no number for non-voice channels
    expect(await screen.findByText(/WhatsApp request recorded/)).toBeInTheDocument();
  });

  it('calls the number entered in the drawer, and only when it is valid', async () => {
    const { onAction } = setup();
    fireEvent.click(screen.getByRole('button', { name: /^Voice Chase$/ }));
    await screen.findByText(/The agent will call Anil Sharma/);
    const call = screen.getByRole('button', { name: /^Call now$/ });
    expect(call).toBeDisabled();                                                                      // no number yet
    const input = screen.getByLabelText(/PHONE NUMBER TO CALL/);
    fireEvent.change(input, { target: { value: '12345' } });
    expect(screen.getByText(/does not look like a valid number/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Call now$/ })).toBeDisabled();
    fireEvent.change(input, { target: { value: '98123 45678' } });
    expect(screen.getByText('Will call +919812345678.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Call +919812345678 now' }));
    await waitFor(() => expect(onAction).toHaveBeenCalledWith('voice', 'voice', '+919812345678'));
    expect(await screen.findByText(/Calling now/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/PHONE NUMBER TO CALL/)).not.toBeInTheDocument();                  // drawer closed after success
  });

  it('keeps the drawer open and shows the reason when the call is refused', async () => {
    const onAction = vi.fn().mockRejectedValue(new Error('409 A voice call for this case is still in progress. Wait for it to finish before calling again.'));
    setup({ onAction });
    fireEvent.click(screen.getByRole('button', { name: /^Voice Chase$/ }));
    await screen.findByText(/The agent will call Anil Sharma/);
    fireEvent.change(screen.getByLabelText(/PHONE NUMBER TO CALL/), { target: { value: '+919812345678' } });
    fireEvent.click(screen.getByRole('button', { name: 'Call +919812345678 now' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('A voice call for this case is still in progress.');
    expect(screen.getByRole('alert')).not.toHaveTextContent('409');
    expect(screen.getByLabelText(/PHONE NUMBER TO CALL/)).toBeInTheDocument();                         // still open
  });

  it('prefills the number stored on the case', async () => {
    mockFetch({ '/crm-form': crmFx, '/voice-chase/context': { ok: true, data: VOICE_CTX } });
    render(<CaseDetailOverview caseData={{ ...hero, contactPhone: '+918888877777' }} onBack={vi.fn()} onSwitchRole={vi.fn()} onAction={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /^Voice Chase$/ }));
    await screen.findByText(/The agent will call/);
    expect(screen.getByLabelText(/PHONE NUMBER TO CALL/)).toHaveValue('+918888877777');
    expect(screen.getByRole('button', { name: 'Call +918888877777 now' })).toBeEnabled();
  });

  it('shows checker actions for the Compliance persona and reports a failed action', async () => {
    const onAction = vi.fn().mockRejectedValue(new Error('500 boom'));
    setup({ isCompliancePersona: true, onAction });
    expect(screen.queryByRole('button', { name: /Approve & Forward/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Send back/ }));
    await waitFor(() => expect(onAction).toHaveBeenCalledWith('send_back', undefined, undefined));
    expect(await screen.findByText(/Action failed: 500 boom/)).toBeInTheDocument();
  });

  it('an AUTO case has no issues to chase', () => {
    mockFetch({ '/crm-form': crmFx });
    render(<CaseDetailOverview caseData={caseAutoFx.data as unknown as MerchantCase} onBack={vi.fn()} onSwitchRole={vi.fn()} onAction={vi.fn()} />);
    expect(screen.getByText(/AUTO · one-click approval/)).toBeInTheDocument();
    expect(screen.getByText('Nothing outstanding.')).toBeInTheDocument();
    expect(screen.queryByText('Voice Chase Now')).not.toBeInTheDocument();
  });
});

describe('Voice chase history', () => {
  const voiceCase = caseVoiceFx.data as unknown as MerchantCase;

  it('shows the call outcome, summary, memory status and an expandable transcript', () => {
    mockFetch({ '/crm-form': crmFx });
    render(<CaseDetailOverview caseData={voiceCase} onBack={vi.fn()} onSwitchRole={vi.fn()} onAction={vi.fn()} />);
    expect(screen.getByText('Voice chase history')).toBeInTheDocument();
    expect(screen.getByText('merchant will upload')).toBeInTheDocument();
    const card = screen.getByText('Voice chase history').closest('div.bg-white')!;
    expect(within(card as HTMLElement).getByText(/TEST CALL \(not a real call\)/)).toBeInTheDocument();
    expect(screen.getByText('In case memory')).toBeInTheDocument();
    expect(screen.getByText('Call id test-call-001')).toBeInTheDocument();

    expect(screen.queryByText('Kal shaam tak bhej dunga.')).not.toBeInTheDocument();      // collapsed by default
    fireEvent.click(screen.getByRole('button', { name: /Transcript \(4\)/ }));
    expect(screen.getByText('Kal shaam tak bhej dunga.')).toBeInTheDocument();
    expect(screen.getAllByText('agent').length).toBe(2);
    fireEvent.click(screen.getByRole('button', { name: /Hide transcript/ }));
    expect(screen.queryByText('Kal shaam tak bhej dunga.')).not.toBeInTheDocument();
  });

  it('has a clear empty state and marks a not-placed call without a memory badge', () => {
    mockFetch({ '/crm-form': crmFx });
    const none = { ...voiceCase, voiceCalls: [] };
    const { unmount } = render(<CaseDetailOverview caseData={none} onBack={vi.fn()} onSwitchRole={vi.fn()} onAction={vi.fn()} />);
    expect(screen.getByText(/No voice chase yet/)).toBeInTheDocument();
    unmount();
    const notPlaced = { ...voiceCase, voiceCalls: [{ id: 'x', outcome: 'not_configured', title: 'Voice call not placed', summary: 'Phone calling is not configured yet.', transcript: [], callId: null, memoryStatus: 'n/a' as const, timestamp: '02 Oct 22:10' }] };
    render(<CaseDetailOverview caseData={notPlaced as unknown as MerchantCase} onBack={vi.fn()} onSwitchRole={vi.fn()} onAction={vi.fn()} />);
    expect(screen.getByText('not placed')).toBeInTheDocument();
    expect(screen.queryByText('In case memory')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Transcript/ })).not.toBeInTheDocument();
  });
});

describe('Merchant upload (real files)', () => {
  const file = (name: string, type = 'application/pdf') => new File([`%PDF ${name}`], name, { type });
  const report = (names: string[], rejected: { filename: string; reason: string }[] = []) => ({
    doc_ids: names.map((_, i) => `d${i}`),
    documents: names.map((n) => ({ doc_id: n, filename: n, sha256: 'a'.repeat(64), doc_type_label: 'GST Certificate (REG-06)', status: 'received' })),
    rejected,
  });

  it('uploads a batch through the backend, shows the hash and detected type, and drops rejected files', async () => {
    const onUploadFiles = vi.fn().mockResolvedValue(report(['GST_Certificate.pdf'], [{ filename: 'notes.exe', reason: "Unsupported type '.exe'. Allowed: pdf, jpg, png." }]));
    const { container } = render(<MerchantUploadScreen view="upload" caseData={hero} onUploadFiles={onUploadFiles} onOpenKAM={vi.fn()} onNavigate={vi.fn()} />);
    expect(screen.getByText('5. Company & Governance')).toBeInTheDocument();       // the new slot for COI / board resolution / shareholding
    expect(screen.getByText(/Please submit the 5 required/)).toBeInTheDocument();

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const files = [file('GST_Certificate.pdf'), file('notes.exe', 'application/octet-stream')];
    fireEvent.change(input, { target: { files } });

    expect(onUploadFiles).toHaveBeenCalledTimes(1);
    expect(onUploadFiles.mock.calls[0][0]).toEqual(files);
    expect(onUploadFiles.mock.calls[0][1]).toBe('business_proof');                // first incomplete slot
    expect(await screen.findByText(/SHA-256 aaaaaaaaaaaaaaaa… · read as GST Certificate/)).toBeInTheDocument();
    expect(await screen.findByText(/Unsupported type '\.exe'/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('1 files attached across 1 categories')).toBeInTheDocument());   // rejected one dropped
  });

  it('supports drag and drop', async () => {
    const onUploadFiles = vi.fn().mockResolvedValue(report(['Board_Resolution.pdf']));
    render(<MerchantUploadScreen view="upload" caseData={hero} onUploadFiles={onUploadFiles} onOpenKAM={vi.fn()} onNavigate={vi.fn()} />);
    const zone = screen.getByText('Quick Batch Upload').closest('div[class*="border-dashed"]')!;
    fireEvent.drop(zone, { dataTransfer: { files: [file('Board_Resolution.pdf')] } });
    await waitFor(() => expect(onUploadFiles).toHaveBeenCalledTimes(1));
    expect((onUploadFiles.mock.calls[0][0] as File[])[0].name).toBe('Board_Resolution.pdf');
  });

  it('reports an upload failure instead of pretending the file arrived', async () => {
    const onUploadFiles = vi.fn().mockRejectedValue(new Error('Failed to fetch'));
    const { container } = render(<MerchantUploadScreen view="upload" caseData={hero} onUploadFiles={onUploadFiles} onOpenKAM={vi.fn()} onNavigate={vi.fn()} />);
    fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [file('PAN.pdf')] } });
    expect(await screen.findByText('Failed to fetch')).toBeInTheDocument();
    expect(screen.getByText('No documents uploaded yet')).toBeInTheDocument();
  });

  it('the AI communication centre shows the live merchant-fixable issue, not a hard-coded one', () => {
    render(<MerchantUploadScreen view="action" caseData={hero} onUploadFiles={vi.fn()} onOpenKAM={vi.fn()} onNavigate={vi.fn()} />);
    expect(screen.getByText(/Action Required: 2 items pending/)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Bank account holder matches legal name' })).toBeInTheDocument();
    expect(screen.getByText(/pre-prints/)).toBeInTheDocument();
    expect(screen.getAllByText('Sharma Foods Pvt Ltd').length).toBeGreaterThan(0);   // header uses the live merchant name
  });

  it('uploads corrected files picked from the communication centre against the address-proof slot', async () => {
    const onUploadFiles = vi.fn().mockResolvedValue(report(['Utility_Bill.pdf']));
    const onNavigate = vi.fn();
    const { container } = render(<MerchantUploadScreen view="action" caseData={hero} onUploadFiles={onUploadFiles} onOpenKAM={vi.fn()} onNavigate={onNavigate} />);
    fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [file('Utility_Bill.pdf')] } });
    await waitFor(() => expect(onUploadFiles).toHaveBeenCalledWith([expect.any(File)], 'business_proof'));
    expect(onNavigate).toHaveBeenCalledWith('upload');
  });
});

describe('useLiveCase', () => {
  it('loads the case from the backend', async () => {
    mockFetch({ '/api/cases/KYB-20814': caseHeroFx });
    const { result } = renderHook(() => useLiveCase('KYB-20814'));
    await waitFor(() => expect(result.current.caseData?.merchantName).toBe('Sharma Foods Pvt Ltd'));
    expect(result.current.offline).toBe(false);
    expect(result.current.caseData?.route).toBe('ESCALATE');
  });

  it('falls back to the bundled sample, flagged offline, when the backend is unreachable', async () => {
    mockFetch({}, true);
    const { result } = renderHook(() => useLiveCase('KYB-20814'));
    await waitFor(() => expect(result.current.offline).toBe(true));
    expect(result.current.caseData?.legalName).toBe('Sharma Foods Private Limited');
    expect(result.current.caseData?.cin).toBe('U56101MH2021PTC123456');            // sample now uses the brief's hero values
  });
});
