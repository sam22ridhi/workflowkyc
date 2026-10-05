/** Drishti screens: the camera-only capture page, the merchant's link card, the KAM evidence card and the V-CIP sign-off card. */
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import caseHeroFx from './fixtures/case-hero.json';
import crmFx from './fixtures/crm-hero.json';
import { CaseDetailOverview } from '@/components/kam/CaseDetailOverview';
import { CpvCapturePage } from '@/components/merchant/CpvCapturePage';
import { ShopVerificationCard } from '@/components/merchant/ShopVerificationCard';
import type { CpvCaptureState, CpvView, VcipView } from '@/services/api';
import type { MerchantCase } from '@/types/case';

vi.mock('qrcode', () => ({ default: { toDataURL: vi.fn(async (text: string) => `data:image/png;base64,QR(${text.length})`) } }));
vi.mock('@/components/kam/PdfEvidenceViewer', () => ({ PdfEvidenceViewer: () => <div data-testid="viewer" /> }));

const hero = caseHeroFx.data as unknown as MerchantCase;
const calls: { url: string; method: string; body?: BodyInit | null }[] = [];

function mockFetch(handler: (url: string, init?: RequestInit) => { status?: number; body: unknown }) {
  calls.length = 0;
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, method: init?.method ?? 'GET', body: init?.body });
    const { status = 200, body } = handler(url, init);
    return { ok: status < 300, status, statusText: 'x', json: async () => body };
  }));
}

const STATE: CpvCaptureState = {
  merchantName: 'Sharma Foods Pvt Ltd', status: 'waiting', required: ['exterior', 'counter'], optional: ['selfie'], captured: {},
  expiresAt: '2026-10-04T10:00:00Z', verdict: null, summary: null, maxAccuracyM: 100,
};

// ---------------------------------------------------------------- browser APIs jsdom does not have
let accuracy = 12;
let getUserMedia: ReturnType<typeof vi.fn>;
let stopTrack: ReturnType<typeof vi.fn>;

beforeEach(() => {
  accuracy = 12;
  stopTrack = vi.fn();
  getUserMedia = vi.fn(async () => ({ getTracks: () => [{ stop: stopTrack }] }));
  Object.defineProperty(navigator, 'mediaDevices', { value: { getUserMedia }, configurable: true });
  Object.defineProperty(navigator, 'geolocation', {
    configurable: true,
    value: {
      watchPosition: (ok: PositionCallback) => { ok({ coords: { latitude: 19.0332, longitude: 73.0297, accuracy } } as GeolocationPosition); return 7; },
      clearWatch: vi.fn(),
    },
  });
  HTMLMediaElement.prototype.play = vi.fn(async () => undefined);
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({ drawImage: vi.fn() })) as unknown as typeof HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.toBlob = function toBlob(cb: BlobCallback) { cb(new Blob(['jpeg-bytes'], { type: 'image/jpeg' })); };
  URL.createObjectURL = vi.fn(() => 'blob:thumb');
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

// ---------------------------------------------------------------- the capture page
describe('Capture page (merchant, camera only)', () => {
  it('explains the steps, then opens the rear camera and location only after the merchant taps Start', async () => {
    mockFetch(() => ({ body: { ok: true, data: STATE } }));
    const { container } = render(<CpvCapturePage token="tok123" />);
    expect(await screen.findByText('Verify Sharma Foods Pvt Ltd')).toBeInTheDocument();
    expect(screen.getByText('Shop front with the signboard')).toBeInTheDocument();
    expect(screen.getByText('Billing counter or QR stand')).toBeInTheDocument();
    expect(screen.getByText(/Gallery uploads are not accepted/)).toBeInTheDocument();
    expect(container.querySelector('input[type="file"]')).toBeNull();                                     // no way to pick a file
    expect(getUserMedia).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /Start verification/ }));
    await waitFor(() => expect(getUserMedia).toHaveBeenCalledTimes(1));
    expect(getUserMedia.mock.calls[0][0]).toMatchObject({ video: { facingMode: { ideal: 'environment' } }, audio: false });
    expect(await screen.findByText('GPS accuracy 12 m')).toBeInTheDocument();
    expect(container.querySelector('input[type="file"]')).toBeNull();
  });

  it('will not take a photo until the GPS fix is precise enough', async () => {
    accuracy = 480;
    mockFetch(() => ({ body: { ok: true, data: STATE } }));
    render(<CpvCapturePage token="tok123" />);
    fireEvent.click(await screen.findByRole('button', { name: /Start verification/ }));
    expect(await screen.findByText('GPS accuracy 480 m')).toBeInTheDocument();
    expect(screen.getByText(/Waiting for a more precise location \(need 100 m or better\)/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Take photo/ })).toBeDisabled();
  });

  it('uploads each frame with GPS, accuracy, a timestamp and the camera-stream source, then submits and shows the verdict', async () => {
    let status: CpvCaptureState['status'] = 'waiting';
    let verdict: CpvCaptureState['verdict'] = null;
    mockFetch((url, init) => {
      if (url.endsWith('/capture')) return { body: { ok: true, data: { captured: ['exterior'] } } };
      if (url.endsWith('/submit')) { status = 'captured'; return { body: { ok: true, data: { status: 'captured' } } }; }
      return { body: { ok: true, data: { ...STATE, status, verdict, summary: verdict ? 'Drishti verified the shop.' : null } } };
    });
    render(<CpvCapturePage token="tok123" />);
    fireEvent.click(await screen.findByRole('button', { name: /Start verification/ }));
    const take = await screen.findByRole('button', { name: /Take photo/ });
    await waitFor(() => expect(take).toBeEnabled());

    fireEvent.click(take);
    await waitFor(() => expect(calls.filter((c) => c.url.endsWith('/capture')).length).toBe(1));
    const form = calls.find((c) => c.url.endsWith('/capture'))!.body as FormData;
    expect(form.get('kind')).toBe('exterior');
    expect(Number(form.get('lat'))).toBeCloseTo(19.0332, 4);
    expect(Number(form.get('lon'))).toBeCloseTo(73.0297, 4);
    expect(form.get('accuracy_m')).toBe('12');
    expect(form.get('source')).toBe('camera_stream');
    expect(Math.abs(Date.now() - Number(form.get('client_ts')))).toBeLessThan(5000);
    expect((form.get('image') as File).type).toBe('image/jpeg');
    expect(screen.getByText('Billing counter or QR stand', { selector: 'h2' })).toBeInTheDocument();          // moved on to step 2
    expect(screen.queryByRole('button', { name: /Send for verification/ })).not.toBeInTheDocument();           // one photo is not enough

    fireEvent.click(screen.getByRole('button', { name: /Take photo/ }));
    const send = await screen.findByRole('button', { name: /Send for verification/ });
    expect((() => { const caps = calls.filter((c) => c.url.endsWith('/capture')); return caps[caps.length - 1].body as FormData; })().get('kind')).toBe('counter');

    fireEvent.click(send);
    expect(await screen.findByText('Checking your photos…')).toBeInTheDocument();
    expect(stopTrack).toHaveBeenCalled();                                                                       // camera released after submit

    verdict = 'CPV_VERIFIED';
    status = 'verified';
    await act(async () => { await new Promise((r) => setTimeout(r, 4200)); });
    expect(await screen.findByText('Your shop is verified')).toBeInTheDocument();
  }, 15000);

  it('shows the server reason when a photo is refused and keeps the camera for a retry', async () => {
    mockFetch((url) => (url.endsWith('/capture')
      ? { status: 422, body: { detail: "The photo's time does not match the current time. Capture the photo again now." } }
      : { body: { ok: true, data: STATE } }));
    render(<CpvCapturePage token="tok123" />);
    fireEvent.click(await screen.findByRole('button', { name: /Start verification/ }));
    const take = await screen.findByRole('button', { name: /Take photo/ });
    await waitFor(() => expect(take).toBeEnabled());
    fireEvent.click(take);
    expect(await screen.findByText(/does not match the current time/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Take photo/ })).toBeEnabled();
  });

  it('says clearly when the link is expired, replaced or invalid', async () => {
    mockFetch(() => ({ status: 410, body: { detail: 'This verification link has expired. Ask your account manager for a new one.' } }));
    render(<CpvCapturePage token="old" />);
    expect(await screen.findByRole('alert')).toHaveTextContent('This verification link has expired');
  });

  it('warns on a non-secure page where phones block the camera and location', async () => {
    Object.defineProperty(window, 'isSecureContext', { value: false, configurable: true });
    mockFetch(() => ({ body: { ok: true, data: STATE } }));
    render(<CpvCapturePage token="tok123" />);
    expect(await screen.findByText(/not on a secure \(https\) address/)).toBeInTheDocument();
    Object.defineProperty(window, 'isSecureContext', { value: true, configurable: true });
  });

  it('reports a blocked camera instead of a blank screen', async () => {
    getUserMedia.mockRejectedValueOnce(Object.assign(new Error('denied'), { name: 'NotAllowedError' }));
    mockFetch(() => ({ body: { ok: true, data: STATE } }));
    render(<CpvCapturePage token="tok123" />);
    fireEvent.click(await screen.findByRole('button', { name: /Start verification/ }));
    expect(await screen.findByText(/Camera access was blocked/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Take photo/ })).toBeDisabled();
  });
});

// ---------------------------------------------------------------- the merchant's card
const CPV_WAITING: CpvView = {
  sessionId: 's1', status: 'waiting', link: 'https://shop.example/cpv/abc123', expiresAt: '2026-10-04T10:00:00Z', required: ['exterior', 'counter'], optional: ['selfie'],
  captured: {}, verdict: null, summary: null, checks: [], distanceM: null, reference: null, tradeName: null, ocr: null, decidedBy: null,
};

describe('Shop verification card (AI Communication Center)', () => {
  it('shows the secure link, a QR code and the two photos to take, instead of a WhatsApp message', async () => {
    render(<ShopVerificationCard cpv={CPV_WAITING} />);
    expect(screen.getByRole('heading', { name: 'Verify your shop' })).toBeInTheDocument();
    expect(screen.getByText('Waiting for your photos')).toBeInTheDocument();
    expect(screen.getByLabelText('Your secure link')).toHaveValue('https://shop.example/cpv/abc123');
    expect(await screen.findByAltText('QR code for your secure link')).toHaveAttribute('src', expect.stringContaining('data:image/png'));
    expect(screen.getByText('Shop front with signboard')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Open on this device/ })).toHaveAttribute('href', 'https://shop.example/cpv/abc123');
  });

  it('copies the link', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    render(<ShopVerificationCard cpv={CPV_WAITING} />);
    fireEvent.click(screen.getByRole('button', { name: /Copy link/ }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('https://shop.example/cpv/abc123'));
    expect(await screen.findByRole('button', { name: 'Copied' })).toBeInTheDocument();
  });

  it('shows progress, then the outcome, and no link once the photos are in', () => {
    const { rerender } = render(<ShopVerificationCard cpv={{ ...CPV_WAITING, status: 'captured', link: 'https://shop.example/cpv/abc123', captured: { exterior: { lat: 1, lon: 2, accuracy_m: 5, heading: null, client_ts: '', width: 1, height: 1 } } }} />);
    expect(screen.getByText('Photos received, checking…')).toBeInTheDocument();
    expect(screen.queryByLabelText('Your secure link')).not.toBeInTheDocument();                              // the link is for taking photos, not for sharing around
    rerender(<ShopVerificationCard cpv={{ ...CPV_WAITING, status: 'verified', link: null }} />);
    expect(screen.getByText('Shop verified')).toBeInTheDocument();
    rerender(<ShopVerificationCard cpv={{ ...CPV_WAITING, status: 'needs_review', link: null }} />);
    expect(screen.getByText(/A person will look at them/)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------- the KAM and Compliance cards
const CHECKS: CpvView['checks'] = [
  { id: 'capture_integrity', label: 'Live camera capture, fresh clock, accurate GPS', status: 'pass', detail: 'Both photos came from the live camera.' },
  { id: 'signboard_name', label: 'Signboard shows the trade name', status: 'pass', detail: 'The signboard reads “शर्मा फूडस” (transliterated: “Sharma Foods”).' },
  { id: 'proximity', label: 'Shop is within 100 m of the declared address', status: 'fail', detail: 'The exterior photo was taken 301 m from the declared address.' },
  { id: 'screen_replay', label: 'Photos are not pictures of a screen or a print', status: 'pass', detail: 'No screen-replay pattern was found.', assistive: true },
  { id: 'mcc_inventory', label: 'Counter fits the declared category (MCC 5812)', status: 'warn', detail: 'None of the words expected were read.', assistive: true, soft: true },
];
const CPV_REVIEW: CpvView = {
  ...CPV_WAITING, status: 'needs_review', link: null, verdict: 'NEEDS_REVIEW', summary: 'A person needs to look: Shop is within 100 m of the declared address.', checks: CHECKS, distanceM: 301,
  reference: { address: '12 MG Road', address_source: 'GST certificate', source: 'osm' }, tradeName: 'Sharma Foods', ocr: { exterior: 'शर्मा फूडस' },
  captured: { exterior: { lat: 19.0332, lon: 73.0297, accuracy_m: 9, heading: 112, client_ts: '2026-10-03T10:00:00Z', width: 1280, height: 900 }, counter: { lat: 19.0332, lon: 73.0297, accuracy_m: 9, heading: null, client_ts: '2026-10-03T10:00:30Z', width: 1280, height: 900 } },
};

function renderCase(patch: Partial<MerchantCase>, opts: { compliance?: boolean; onAction?: ReturnType<typeof vi.fn> } = {}) {
  mockFetch((url) => (url.includes('crm-form') ? { body: crmFx } : { body: { ok: true, data: {} } }));
  const onAction = opts.onAction ?? vi.fn().mockResolvedValue(undefined);
  render(<CaseDetailOverview caseData={{ ...hero, ...patch }} onBack={vi.fn()} onSwitchRole={vi.fn()} onAction={onAction} isCompliancePersona={opts.compliance} />);
  return { onAction };
}

describe('Drishti card (KAM)', () => {
  it('shows the photos with their GPS, the five checks, the distance and the signboard text', () => {
    renderCase({ cpv: CPV_REVIEW });
    const card = screen.getByText('Drishti · Contact point verification').closest('div.bg-white') as HTMLElement;
    expect(within(card).getByText('NEEDS_REVIEW')).toBeInTheDocument();
    expect(within(card).getByAltText('exterior photo')).toHaveAttribute('src', expect.stringMatching(/\/api\/cases\/KYB-20814\/cpv\/images\/exterior$/));
    expect(within(card).getAllByText(/19\.03320, 73\.02970 · ±9 m/)).toHaveLength(2);                          // one line per photo
    expect(within(card).getByText(/Bearing 112°/)).toBeInTheDocument();
    expect(within(card).getByText('Shop is within 100 m of the declared address')).toBeInTheDocument();
    expect(within(card).getAllByText('Needs a look')).toHaveLength(1);                                         // only the failed hard check
    expect(within(card).getAllByText('Assistive')).toHaveLength(2);                                            // replay and MCC are marked as heuristics
    expect(within(card).getByText('301 m')).toBeInTheDocument();
    expect(within(card).getByText('Sharma Foods')).toBeInTheDocument();
    expect(within(card).getByText('शर्मा फूडस')).toBeInTheDocument();
  });

  it('lets the KAM approve a flagged verification or ask for new photos', async () => {
    const { onAction } = renderCase({ cpv: CPV_REVIEW });
    fireEvent.click(screen.getByRole('button', { name: /Approve after review/ }));
    await waitFor(() => expect(onAction).toHaveBeenCalledWith('cpv_approve', undefined, undefined));
    fireEvent.click(screen.getByRole('button', { name: /Ask for new photos/ }));
    await waitFor(() => expect(onAction).toHaveBeenCalledWith('cpv_retake', undefined, undefined));
  });

  it('gives Compliance no CPV actions and a verified shop needs none', () => {
    renderCase({ cpv: CPV_REVIEW }, { compliance: true });
    expect(screen.queryByRole('button', { name: /Approve after review/ })).not.toBeInTheDocument();
  });

  it('while waiting, tells the KAM the link is with the merchant and offers a fresh one', () => {
    renderCase({ cpv: CPV_WAITING });
    expect(screen.getByText(/has not sent the photos yet/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Create a fresh link/ })).toBeInTheDocument();
  });

  it('is absent when the case has no verification yet', () => {
    renderCase({ cpv: null });
    expect(screen.queryByText('Drishti · Contact point verification')).not.toBeInTheDocument();
  });
});

const VCIP: VcipView = {
  status: 'queued', outcome: null, summary: null, callId: null, interviewedAt: null, signedOffBy: null, agentConfigured: true, contactPhone: null, shopVerdict: 'CPV_VERIFIED', selfie: false,
  questions: [
    { id: 1, kind: 'weekday', hi: 'आज कौन सा दिन है?', en: 'What day of the week is it today?', expected: 'Saturday (शनिवार)' },
    { id: 2, kind: 'repeat_number', hi: 'मैं एक संख्या बोलूँगी: चार सात दो नौ।', en: 'I will say a number: 4 7 2 9. Please repeat it exactly.', expected: '4 7 2 9' },
    { id: 3, kind: 'legal_name', hi: 'आपकी कंपनी का पूरा नाम क्या है?', en: 'What is the full name of your company?', expected: 'Sharma Foods Private Limited' },
  ],
  transcript: [], referenceDocument: { docId: 'd-pan', filename: 'Company_PAN.pdf', label: 'pan' },
  faceMatch: { performed: false, note: 'No face-matching model is integrated. The authorised official compares the live face with the ID photo.' },
};

describe('V-CIP card (Compliance)', () => {
  it('lists the randomized questions with the expected answers and says face matching is a human job', () => {
    renderCase({ vcip: VCIP }, { compliance: true });
    expect(screen.getByText('V-CIP · Video KYC sign-off')).toBeInTheDocument();
    expect(screen.getByText('Pre-interview not done yet')).toBeInTheDocument();
    expect(screen.getByText(/2\. I will say a number: 4 7 2 9/)).toBeInTheDocument();
    expect(screen.getAllByText(/Expected:/)).toHaveLength(3);
    expect(screen.getByText('4 7 2 9', { selector: 'span.font-semibold' })).toBeInTheDocument();
    expect(screen.getByText(/No face-matching model is integrated/)).toBeInTheDocument();
    expect(screen.getByText('No selfie was sent')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Open Company_PAN\.pdf/ })).toHaveAttribute('href', expect.stringContaining('/api/documents/d-pan/file'));
  });

  it('starts the pre-interview call only with a valid number, and signs off in one click', async () => {
    const { onAction } = renderCase({ vcip: VCIP }, { compliance: true });
    const call = screen.getByRole('button', { name: /Start pre-interview call/ });
    expect(call).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Phone number for the pre-interview/), { target: { value: '98123 45678' } });
    expect(call).toBeEnabled();
    fireEvent.click(call);
    await waitFor(() => expect(onAction).toHaveBeenCalledWith('vcip_call', undefined, '+919812345678'));
    expect(screen.getByText(/No completed pre-interview is on record/)).toBeInTheDocument();                   // honest warning before sign-off
    fireEvent.click(screen.getByRole('button', { name: /Sign off V-CIP \(one click\)/ }));
    await waitFor(() => expect(onAction).toHaveBeenCalledWith('vcip_signoff'));
  });

  it('shows the transcript after a pre-interview and no warning', () => {
    renderCase({ vcip: { ...VCIP, status: 'interviewed', transcript: [{ role: 'agent', text: 'नमस्ते' }, { role: 'merchant', text: 'जी, बोलिए' }], summary: 'The merchant picked up (48 s).' } }, { compliance: true });
    expect(screen.getByText('Ready for your sign-off')).toBeInTheDocument();
    expect(screen.queryByText('जी, बोलिए')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Pre-interview transcript \(2\)/ }));
    expect(screen.getByText('जी, बोलिए')).toBeInTheDocument();
    expect(screen.queryByText(/No completed pre-interview is on record/)).not.toBeInTheDocument();
  });

  it('asks the officer to set up the second agent instead of failing silently', () => {
    renderCase({ vcip: { ...VCIP, agentConfigured: false } }, { compliance: true });
    expect(screen.getByText(/SARVAM_VCIP_AGENT_ID/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Start pre-interview call/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Sign off V-CIP/ })).toBeEnabled();
  });

  it('shows a refusal from the server and stays actionable', async () => {
    const onAction = vi.fn().mockRejectedValue(new Error('409 V-CIP opens after the contact point verification is approved.'));
    renderCase({ vcip: VCIP }, { compliance: true, onAction });
    fireEvent.click(screen.getByRole('button', { name: /Sign off V-CIP/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent('V-CIP opens after the contact point verification is approved.');
    expect(screen.getByRole('button', { name: /Sign off V-CIP/ })).toBeEnabled();
  });

  it('is read-only for the KAM, and a signed-off case shows who signed', () => {
    renderCase({ vcip: VCIP }, { compliance: false });
    expect(screen.queryByRole('button', { name: /Sign off V-CIP/ })).not.toBeInTheDocument();
    expect(screen.getByText(/Only the Compliance officer can start the pre-interview and sign off/)).toBeInTheDocument();
    cleanupAndRender();
  });
});

function cleanupAndRender() {
  document.body.innerHTML = '';
  renderCase({ vcip: { ...VCIP, status: 'signed_off', signedOffBy: 'compliance' } }, { compliance: true });
  expect(screen.getByText(/Signed off by compliance/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Sign off V-CIP/ })).not.toBeInTheDocument();
}
