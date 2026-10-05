import { useMemo } from 'react';
import { ArrowRight, CheckCircle2, ClipboardCheck, Loader2, MapPin, ShieldCheck, Video } from 'lucide-react';
import { useLiveCases } from '@/services/useLiveCase';
import type { CaseRow } from '@/services/api';

interface Props {
  onOpenCase: (caseId: string) => void;
  onOpenAsMerchant: (caseId: string) => void;
}

const CPV_TEXT: Record<string, string> = {
  waiting: 'Waiting for the merchant’s photos',
  captured: 'Photos received',
  analysing: 'Drishti is checking',
  verified: 'CPV_VERIFIED',
  needs_review: 'Needs KAM review',
};
const VCIP_TEXT: Record<string, string> = {
  queued: 'Queued: pre-interview not done',
  interviewed: 'Pre-interview done: ready to sign off',
  signed_off: 'Signed off',
};

/** The checker's desk: what is waiting for Compliance, what Drishti is doing, and the V-CIP sign-off queue. */
export function ComplianceDashboardView({ onOpenCase, onOpenAsMerchant }: Props) {
  const { list, loading, error } = useLiveCases();
  const items = useMemo(() => (list?.items ?? []).filter((c) => c.kind !== 'investigation'), [list]);       // settlement investigations are the KAM's
  const kpis = list?.kpis;
  const checker = items.filter((c) => c.stageNumber === 5);
  const cpv = items.filter((c) => c.stageNumber === 6);
  const vcip = items.filter((c) => c.stageNumber === 7);
  const beyond = items.filter((c) => c.stageNumber >= 8);

  return (
    <div className="p-6 md:p-8 space-y-8 max-w-7xl mx-auto w-full">
      <div>
        <span className="text-[10px] font-extrabold uppercase tracking-widest text-[#00BAF2] bg-[#e6f7fc] px-2.5 py-0.5 rounded-full border border-[#cfe9fc]">Compliance desk</span>
        <h1 className="text-2xl md:text-3xl font-extrabold text-[#002970] tracking-tight mt-2">What needs your decision</h1>
        <p className="text-xs md:text-sm text-slate-600 mt-1 font-medium">
          You approve the KAM&rsquo;s file, then the authorised official signs off V-CIP. Drishti&rsquo;s shop verification runs in between. {error ? 'Backend unreachable.' : loading ? 'Loading…' : 'Live.'}
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5 md:gap-4">
        <Kpi icon={<ClipboardCheck size={15} />} label="Awaiting your approval" value={kpis?.awaitingChecker} hint="Submitted by the KAM" tone="navy" />
        <Kpi icon={<MapPin size={15} />} label="Shop verification" value={kpis?.cpvInProgress} hint="Merchant photos / Drishti / KAM" tone="cyan" />
        <Kpi icon={<Video size={15} />} label="V-CIP sign-off queue" value={kpis?.vcipQueue} hint="One click each" tone="amber" />
        <Kpi icon={<CheckCircle2 size={15} />} label="Past sign-off" value={loading ? undefined : beyond.length} hint="Settlement test onward" tone="green" />
      </div>

      <Queue
        title="1. Awaiting Compliance approval"
        empty="Nothing waiting. Cases appear here when the KAM clicks Approve & Forward."
        rows={checker}
        loading={loading}
        action="Review & decide"
        detail={() => 'KAM-approved file ready for the checker'}
        onOpenCase={onOpenCase}
        onOpenAsMerchant={onOpenAsMerchant}
      />
      <Queue
        title="2. Shop verification in progress (Drishti)"
        empty="No shop verifications running. Approving a case in queue 1 opens one and gives the merchant a secure link."
        rows={cpv}
        loading={loading}
        action="Open case"
        detail={(c) => CPV_TEXT[c.cpvStatus ?? ''] ?? 'Link not opened yet'}
        onOpenCase={onOpenCase}
        onOpenAsMerchant={onOpenAsMerchant}
        merchantButton
      />
      <Queue
        title="3. V-CIP sign-off queue"
        empty="Nobody waiting. Cases arrive here once Drishti has verified the shop."
        rows={vcip}
        loading={loading}
        action="Pre-interview & sign off"
        detail={(c) => VCIP_TEXT[c.vcipStatus ?? ''] ?? 'Queued'}
        onOpenCase={onOpenCase}
        onOpenAsMerchant={onOpenAsMerchant}
      />

      <p className="text-[11px] text-slate-500 flex items-center gap-1.5">
        <ShieldCheck size={14} className="text-emerald-600" />
        Only you can approve at stage 5 and sign off V-CIP. The server refuses these actions from anyone else, and no face-matching is automated.
      </p>
    </div>
  );
}

const TONES = {
  navy: 'text-[#002970] border-slate-200/80',
  cyan: 'text-[#00BAF2] border-[#cfe9fc]',
  amber: 'text-amber-600 border-amber-200/80',
  green: 'text-emerald-700 border-emerald-200/80',
} as const;

function Kpi({ icon, label, value, hint, tone }: { icon: React.ReactNode; label: string; value?: number; hint: string; tone: keyof typeof TONES }) {
  return (
    <div className={`bg-white p-5 rounded-2xl border shadow-2xs ${TONES[tone]}`}>
      <div className="flex items-center justify-between mb-2 text-slate-500">
        <span className="text-[11px] font-bold tracking-wide">{label}</span>
        <div className="w-7 h-7 rounded-lg bg-slate-100 flex items-center justify-center">{icon}</div>
      </div>
      <div className="text-2xl md:text-3xl font-extrabold tracking-tight">{value ?? '–'}</div>
      <div className="text-[11px] font-semibold text-slate-500 mt-1">{hint}</div>
    </div>
  );
}

function Queue({ title, empty, rows, loading, action, detail, onOpenCase, onOpenAsMerchant, merchantButton }: {
  title: string; empty: string; rows: CaseRow[]; loading: boolean; action: string; detail: (c: CaseRow) => string;
  onOpenCase: (id: string) => void; onOpenAsMerchant: (id: string) => void; merchantButton?: boolean;
}) {
  return (
    <section className="bg-white rounded-2xl border border-slate-200/80 shadow-2xs overflow-hidden" aria-label={title}>
      <div className="p-5 border-b border-slate-200/70 flex items-center justify-between">
        <h2 className="text-base font-extrabold text-[#002970]">{title} ({rows.length})</h2>
      </div>
      {loading && !rows.length ? (
        <div className="py-8 text-center text-slate-500 text-xs"><Loader2 size={16} className="inline animate-spin mr-2" />Loading…</div>
      ) : rows.length === 0 ? (
        <div className="py-8 px-5 text-center text-slate-500 text-xs">{empty}</div>
      ) : (
        <ul className="divide-y divide-slate-100">
          {rows.map((c) => (
            <li key={c.id} className="p-4 px-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-slate-50/60">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-9 h-9 rounded-lg bg-[#002970] text-[#00BAF2] font-black text-xs flex items-center justify-center shrink-0">{c.merchantName.slice(0, 2).toUpperCase()}</div>
                <div className="min-w-0">
                  <strong className="block text-xs font-bold text-slate-900 truncate">{c.merchantName}</strong>
                  <small className="block text-[11px] text-slate-500 truncate">{c.id} · {c.legalName} · {detail(c)}</small>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {merchantButton && (
                  <button onClick={() => onOpenAsMerchant(c.id)} className="px-3 py-1.5 rounded-lg bg-[#e6f7fc] border border-[#cfe9fc] text-[#002970] text-xs font-bold hover:bg-[#d6f2fa]">
                    View as merchant
                  </button>
                )}
                <button onClick={() => onOpenCase(c.id)} className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[#002970] hover:bg-[#001b4c] text-white text-xs font-bold">
                  {action} <ArrowRight size={13} className="text-[#00BAF2]" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
