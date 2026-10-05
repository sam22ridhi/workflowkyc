/** Branding: the Paytm logo, the MAF tab and its Paytm-blue colours, and the dark-navy landing page with its illustration. */
import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import caseHeroFx from './fixtures/case-hero.json';
import { Landing } from '@/components/home/PaytmLanding';
import { AutoFilledCrmForm } from '@/components/kam/AutoFilledCrmForm';
import { CaseDetailOverview } from '@/components/kam/CaseDetailOverview';
import { AppLogo } from '@/components/shared/AppLogo';
import type { MerchantCase } from '@/types/case';

vi.mock('@/components/kam/PdfEvidenceViewer', () => ({ PdfEvidenceViewer: () => <div /> }));
afterEach(() => vi.unstubAllGlobals());

const hero = caseHeroFx.data as unknown as MerchantCase;
const noop = vi.fn();

describe('Paytm logo', () => {
  it('is the app mark, next to the product name', () => {
    render(<AppLogo subtitle="Paytm Corporate Gateway" />);
    expect(screen.getByAltText('Paytm')).toHaveAttribute('src', '/paytm-logo.png');
    expect(screen.getByText('KARYAKARTA')).toBeInTheDocument();
    expect(screen.getByText('Paytm Corporate Gateway')).toBeInTheDocument();
  });

  it('sits on a white chip on dark backgrounds so the navy letters stay visible', () => {
    const { container } = render(<AppLogo onDark />);
    expect(container.querySelector('.bg-white img[alt="Paytm"]')).not.toBeNull();
  });
});

describe('Landing page', () => {
  it('uses the Paytm logo, an illustration on the right and the navy theme, and its buttons work', () => {
    const onAuth = vi.fn(), onMerchant = vi.fn(), onKAM = vi.fn();
    const { container } = render(<Landing onAuth={onAuth} onMerchant={onMerchant} onKAM={onKAM} />);
    expect(container.querySelector('.lp')).not.toBeNull();
    expect(screen.getAllByAltText('Paytm').length).toBeGreaterThan(0);
    expect(screen.getByAltText(/business profiles that the AI has verified/)).toHaveAttribute('src', '/landing-illustration.svg');
    expect(screen.queryByText('7 fields extracted')).not.toBeInTheDocument();          // the old product mock-up is gone
    expect(container.innerHTML).not.toMatch(/purple|indigo|violet/);
    fireEvent.click(screen.getByRole('button', { name: /Start onboarding/ }));
    fireEvent.click(screen.getByRole('button', { name: /See how it works/ }));
    fireEvent.click(screen.getByRole('button', { name: /Create your account/ }));
    fireEvent.click(screen.getAllByRole('button', { name: /Sign in/ })[0]);
    expect(onMerchant).toHaveBeenCalledTimes(1);
    expect(onKAM).toHaveBeenCalledTimes(1);
    expect(onAuth).toHaveBeenCalledTimes(2);
  });
});

describe('MAF tab', () => {
  it('is called MAF (Merchant Application Form), not "Auto-Filled CRM Form (Magic)", and is not purple', () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200, statusText: 'OK', json: async () => ({ ok: true, data: null }) })));
    const { container } = render(<CaseDetailOverview caseData={hero} onBack={noop} onSwitchRole={noop} onAction={noop} />);
    expect(screen.getByRole('button', { name: /MAF \(Merchant Application Form\)/ })).toBeInTheDocument();
    expect(screen.queryByText(/Magic/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Auto-Filled CRM Form/)).not.toBeInTheDocument();
    expect(container.innerHTML).not.toMatch(/purple|indigo|violet/);
  });

  it('the form itself is in the Paytm blues', () => {
    const { container } = render(<AutoFilledCrmForm caseId="KYB-20814" form={null} error={null} reload={noop} isCompliancePersona={false} onViewEvidence={noop} onSubmitToCompliance={noop} onEditOverride={noop} />);
    expect(container.innerHTML).not.toMatch(/purple|indigo|violet/);
  });
});
