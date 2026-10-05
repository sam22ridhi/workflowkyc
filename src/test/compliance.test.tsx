/** The Compliance desk and the merchant-side case picker (fetch mocked with a synthetic case list). */
import { fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import casesFx from './fixtures/cases.json';
import caseHeroFx from './fixtures/case-hero.json';
import { ComplianceDashboardView } from '@/components/kam/ComplianceDashboardView';
import { KamDashboardView } from '@/components/kam/KamDashboardView';
import { MerchantUploadScreen } from '@/components/merchant/MerchantUploadScreen';
import type { MerchantCase } from '@/types/case';

const base = casesFx.data.items[0];
const row = (id: string, name: string, stageNumber: number, extra: object = {}) => ({ ...base, id, merchantName: name, legalName: `${name} Pvt Ltd`, stageNumber, ...extra });
const LIST = {
  data: {
    kpis: { ...casesFx.data.kpis, awaitingChecker: 1, cpvInProgress: 1, vcipQueue: 1 },
    items: [
      row('KYB-1', 'Alpha Traders', 5),
      row('KYB-2', 'Beta Stores', 6, { cpvStatus: 'waiting' }),
      row('KYB-3', 'Gamma Foods', 7, { vcipStatus: 'interviewed' }),
      row('KYB-4', 'Delta Works', 3),
    ],
  },
};

afterEach(() => { vi.unstubAllGlobals(); });
const mock = () => vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200, statusText: 'OK', json: async () => LIST })));

describe('Compliance dashboard', () => {
  it('sorts cases into the three queues a checker works from', async () => {
    mock();
    const open = vi.fn();
    const asMerchant = vi.fn();
    render(<ComplianceDashboardView onOpenCase={open} onOpenAsMerchant={asMerchant} />);

    const checker = await screen.findByRole('region', { name: /Awaiting Compliance approval/ });
    expect(within(checker).getByText('Alpha Traders')).toBeInTheDocument();
    const cpv = screen.getByRole('region', { name: /Shop verification in progress/ });
    expect(within(cpv).getByText('Beta Stores')).toBeInTheDocument();
    expect(within(cpv).getByText(/Waiting for the merchant/)).toBeInTheDocument();
    const vcip = screen.getByRole('region', { name: /V-CIP sign-off queue/ });
    expect(within(vcip).getByText('Gamma Foods')).toBeInTheDocument();
    expect(within(vcip).getByText(/ready to sign off/)).toBeInTheDocument();
    expect(screen.queryByText('Delta Works')).not.toBeInTheDocument();

    fireEvent.click(within(checker).getByRole('button', { name: /Review & decide/ }));
    expect(open).toHaveBeenCalledWith('KYB-1');
    fireEvent.click(within(cpv).getByRole('button', { name: 'View as merchant' }));
    expect(asMerchant).toHaveBeenCalledWith('KYB-2');
  });
});

describe('KAM pipeline', () => {
  it('can open any case in the merchant portal', async () => {
    mock();
    const asMerchant = vi.fn();
    render(<KamDashboardView onOpenCase={vi.fn()} onOpenAsMerchant={asMerchant} />);
    const rowEl = (await screen.findByText('Beta Stores')).closest('tr')!;
    fireEvent.click(within(rowEl).getByRole('button', { name: 'View as merchant' }));
    expect(asMerchant).toHaveBeenCalledWith('KYB-2');
  });
});

describe('Merchant portal case picker', () => {
  it('lets the tester switch to any case', () => {
    const choose = vi.fn();
    render(
      <MerchantUploadScreen
        view="stage1" caseData={caseHeroFx.data as unknown as MerchantCase} onUploadFiles={vi.fn()} onOpenKAM={vi.fn()}
        cases={[{ id: 'KYB-20814', name: 'Sharma Foods', stage: 'AI Verifying' }, { id: 'KYB-2', name: 'Beta Stores', stage: 'Contact Point Verification' }]}
        onChooseCase={choose}
      />,
    );
    fireEvent.change(screen.getByLabelText('Open this merchant case'), { target: { value: 'KYB-2' } });
    expect(choose).toHaveBeenCalledWith('KYB-2');
  });
});


describe('Merchant portal shows the selected case, not the previous one', () => {
  const other = { ...(caseHeroFx.data as unknown as MerchantCase), id: 'KYB-2', merchantName: 'Beta Stores', legalName: 'Beta Stores Private Limited', pan: 'BBBBB1111B',
    uploaded: [{ doc_type: 'pan', label: 'Company PAN', status: 'uploaded' as const, doc_id: 'd1' }], missing: [] };
  const hero = caseHeroFx.data as unknown as MerchantCase;
  const props = { onUploadFiles: vi.fn(), onOpenKAM: vi.fn(), onNavigate: vi.fn() };

  it('Account Center and the agreement use the chosen merchants own legal name and PAN', () => {
    const { rerender } = render(<MerchantUploadScreen view="account" caseData={hero} {...props} />);
    expect(screen.getByDisplayValue(hero.legalName)).toBeInTheDocument();
    rerender(<MerchantUploadScreen view="account" caseData={other} {...props} />);
    expect(screen.getByDisplayValue('Beta Stores Private Limited')).toBeInTheDocument();
    expect(screen.getByDisplayValue('BBBBB1111B')).toBeInTheDocument();
    expect(screen.queryByDisplayValue(hero.legalName)).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue('AABCU9603R')).not.toBeInTheDocument();
  });

  it('the upload page starts from the cases own stored documents and drops the previous merchants', () => {
    const { rerender } = render(<MerchantUploadScreen view="upload" caseData={hero} {...props} />);
    const before = screen.queryAllByText('Uploaded').length;
    rerender(<MerchantUploadScreen view="upload" caseData={{ ...other, id: 'KYB-3', uploaded: [], missing: [] }} {...props} />);
    expect(screen.queryAllByText('Uploaded').length).toBe(0);
    rerender(<MerchantUploadScreen view="upload" caseData={other} {...props} />);
    expect(screen.queryAllByText('Uploaded').length).toBe(1);
    expect(before).toBeGreaterThan(0);
  });
});
