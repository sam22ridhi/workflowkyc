import { useState } from 'react';
import { Activity, AlertTriangle, BadgeCheck, BrainCircuit, Loader2, Play, RotateCcw, ShieldAlert, Sparkles, TrendingUp } from 'lucide-react';
import { inr } from '@/services/format';
import {
  ALL_CASES, runSettlementScan, settlementDemo, useLiveResource,
  type FlaggedTxn, type SettlementDetection, type SettlementView,
} from '@/services/api';

const HEALTH = {
  healthy: { text: 'Healthy', tone: 'bg-emerald-50 text-emerald-800 border-emerald-200', dot: 'bg-emerald-500' },
  watch: { text: 'Watch', tone: 'bg-amber-50 text-amber-800 border-amber-200', dot: 'bg-amber-500' },
  critical: { text: 'Critical', tone: 'bg-rose-50 text-rose-800 border-rose-200', dot: 'bg-rose-500' },
  unknown: { text: 'No baseline yet', tone: 'bg-slate-100 text-slate-700 border-slate-200', dot: 'bg-slate-400' },
} as const;

interface Props {
  caseId: string;
  onToast?: (text: string, error?: boolean) => void;
}

/** Post-onboarding monitoring of the merchant's settlements, on the same Case Detail. Everything here is computed by the backend from a synthetic ledger. */
export function SettlementsTab({ caseId, onToast }: Props) {
  const res = useLiveResource<SettlementView>(ALL_CASES, `/api/cases/${caseId}/settlements`);
  const [busy, setBusy] = useState<string | null>(null);
  const v = res.data;

  const act = async (what: 'scan' | 'spike' | 'reset') => {
    if (!v) return;
    setBusy(what);
    try {
      if (what === 'scan') {
        const r = await runSettlementScan(v.merchantCaseId);
        onToast?.(r.via === 'n8n' ? 'Settlement Agent started in n8n. Watch the timeline.' : 'Settlement Agent started in the backend. Watch the timeline.');
      } else {
        await settlementDemo(v.merchantCaseId, what);
        onToast?.(what === 'spike' ? 'Demo: a 48-hour spike and a settlement mismatch were injected. Run the settlement check.' : 'Demo: the ledger is healthy again.');
      }
      void res.reload();
    } catch (e) {
      onToast?.(e instanceof Error ? e.message : String(e), true);
    } finally {
      setBusy(null);
    }
  };

  if (!v) return <div className="p-8 text-center text-xs text-slate-500">{res.error ? `Could not load settlements: ${res.error}` : <><Loader2 size={14} className="inline animate-spin mr-2" />Loading settlements…</>}</div>;
  const d = v.detection;
  const health = HEALTH[d.health];
  const rec = v.reconciliation;
  const inv = v.investigation;

  if (!v.monitored && !inv) {
    return (
      <div className="bg-white p-8 rounded-2xl border border-slate-200/80 shadow-2xs text-center space-y-2">
        <Activity size={22} className="mx-auto text-slate-400" />
        <h3 className="text-sm font-extrabold text-slate-900">Settlement monitoring starts after activation</h3>
        <p className="text-xs text-slate-500 max-w-md mx-auto">The Settlement Agent is a post-onboarding teammate. Once this merchant is live and has 30 days of settlement history, it compares every 48 hours with the baseline.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Settlements · {v.merchantName}</h3>
            <span className="text-[10px] font-extrabold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200" title="No real payments are involved">Synthetic ledger</span>
            <span className={`text-[10px] font-extrabold px-2.5 py-0.5 rounded-full border inline-flex items-center gap-1.5 ${health.tone}`}><span className={`w-1.5 h-1.5 rounded-full ${health.dot}`} />{health.text}</span>
          </div>
          <p className="text-[11px] text-slate-500 font-medium mt-1">
            {d.eligible
              ? `Last 48 hours (${d.window.from} to ${d.window.to}) against the trailing ${d.baseline_days}-day baseline. Thresholds: volume above ${d.thresholds.velocity_pct}% of baseline, or expected vs actual more than ${d.thresholds.mismatch_pct}% apart.`
              : d.note}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button onClick={() => void act('scan')} disabled={!!busy} className="px-3.5 py-2 rounded-xl bg-[#002970] hover:bg-[#001b4c] text-white text-xs font-bold flex items-center gap-1.5 disabled:opacity-50">
            {busy === 'scan' ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} className="text-[#00BAF2]" />} Run settlement check
          </button>
          {v.demoControls && (
            <>
              <button onClick={() => void act('spike')} disabled={!!busy} className="px-3 py-2 rounded-xl bg-white border border-dashed border-slate-300 text-slate-700 text-xs font-bold flex items-center gap-1.5 disabled:opacity-50" title="Demo only: adds a synthetic 48-hour spike and a settlement mismatch">
                <Play size={12} /> Inject 48-hour spike (demo)
              </button>
              <button onClick={() => void act('reset')} disabled={!!busy} className="px-3 py-2 rounded-xl bg-white border border-dashed border-slate-300 text-slate-700 text-xs font-bold flex items-center gap-1.5 disabled:opacity-50" title="Demo only: healthy ledger, open investigations closed">
                <RotateCcw size={12} /> Reset
              </button>
            </>
          )}
        </div>
      </div>

      {d.eligible && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3.5">
          <Metric label="Expected settlement" value={inr(d.expected)} hint="Captured − MDR − refunds, last 48 h" />
          <Metric label="Actual settlement" value={inr(d.actual)} hint="What the bank credited" />
          <Metric label="Difference" value={`${inr(d.difference)} · ${d.difference_pct}%`} hint={`Threshold ${d.thresholds.mismatch_pct}%`} bad={d.settlement_anomaly} />
          <Metric label="Transaction velocity" value={`${d.velocity_pct}% of baseline`} hint={`${inr(d.window_daily)}/day vs ${inr(d.baseline_daily)}/day · ${d.txns_per_day_window} vs ${d.txns_per_day_baseline} payments a day`} bad={d.velocity_anomaly} />
          <Metric label="Settlement health" value={health.text} hint={d.anomaly ? `${[d.velocity_anomaly && 'velocity', d.settlement_anomaly && 'settlement'].filter(Boolean).join(' + ')} anomaly` : 'Both within thresholds'} bad={d.health === 'critical'} warn={d.health === 'watch'} />
        </div>
      )}

      {d.eligible && <VolumeChart d={d} />}

      {inv && (
        <div className="bg-white p-6 rounded-2xl border border-rose-200 bg-gradient-to-br from-white to-rose-50/30 shadow-2xs space-y-4" aria-label="Investigation">
          <div className="flex items-start justify-between gap-3 flex-wrap pb-3 border-b border-rose-100">
            <div className="flex items-start gap-3">
              <div className="w-9 h-9 rounded-xl bg-rose-100 text-rose-700 flex items-center justify-center shrink-0"><ShieldAlert size={18} /></div>
              <div>
                <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Investigation {inv.id} · {inv.status}</h3>
                <p className="text-[11px] text-slate-500 font-medium">Opened by the Settlement Agent. It recommends; a person (KAM) decides. The agent has not moved or held any money.</p>
              </div>
            </div>
            <span className="text-[10px] font-extrabold px-2 py-1 rounded-full border bg-rose-50 text-rose-800 border-rose-200 uppercase">{inv.recommended.severity} severity</span>
          </div>
          <p className="text-xs text-slate-800 leading-relaxed">{inv.brief}</p>
          <p className="text-[10px] text-slate-500 font-semibold">
            {inv.briefSource === 'sarvam' ? 'Brief written by Sarvam; every number was checked against the ledger.' : 'Brief generated from the computed facts.'}
          </p>
          <div className="grid md:grid-cols-2 gap-4">
            <div className="rounded-xl border border-slate-200 p-4 bg-white">
              <strong className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-[#002970] mb-2"><BadgeCheck size={13} className="text-emerald-600" /> Recommended action: {inv.recommended.title}</strong>
              <ol className="list-decimal pl-4 space-y-1 text-xs text-slate-700">{inv.recommended.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
            </div>
            <div className="rounded-xl border border-slate-200 p-4 bg-white">
              <strong className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-[#002970] mb-2"><BrainCircuit size={13} className="text-[#0099cc]" /> What the merchant twin (Cognee) holds</strong>
              {inv.context.source === 'cognee'
                ? <p className="text-xs text-slate-700 leading-relaxed">{inv.context.answer}</p>
                : <p className="text-xs text-amber-800 font-semibold">The merchant twin could not be read ({inv.context.note ?? inv.context.source}). The ledger evidence below is unaffected.</p>}
              <p className="text-[10px] text-slate-400 mt-2">Retrieved via {inv.context.via ?? 'Cognee'} · finding stored back in memory: {inv.memoryStatus}</p>
            </div>
          </div>
        </div>
      )}

      {rec && (
        <div className="grid md:grid-cols-2 gap-4">
          <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-2xs space-y-2">
            <h4 className="text-[11px] font-extrabold uppercase tracking-wider text-slate-500">Reconciliation: why expected ≠ actual</h4>
            <ul className="space-y-1.5 text-xs text-slate-800">
              {rec.causes.map((c, i) => (
                <li key={i} className="flex items-start gap-2"><AlertTriangle size={13} className="text-amber-600 mt-0.5 shrink-0" />
                  <span><strong>{inr(c.amount)}</strong> {c.kind === 'held_batch' ? `sits in held batch ${c.batches?.join(', ')} (${c.txn_count} payments). ${c.reason ?? ''}` : c.kind === 'chargebacks' ? `debited as ${c.count} chargebacks` : 'is unexplained'}</span></li>
              ))}
              {rec.causes.length === 0 && <li className="text-slate-500">Nothing to explain.</li>}
            </ul>
            <table className="w-full text-[11px] mt-2"><thead><tr className="text-left text-slate-400"><th>Day</th><th className="text-right">Expected</th><th className="text-right">Actual</th><th className="text-right">Gap</th></tr></thead>
              <tbody>{rec.days.map((x) => <tr key={x.day} className="border-t border-slate-100"><td>{x.day}</td><td className="text-right">{inr(x.expected)}</td><td className="text-right">{inr(x.actual)}</td><td className="text-right font-bold">{inr(x.difference)}</td></tr>)}</tbody></table>
          </div>
          <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-2xs space-y-2">
            <h4 className="text-[11px] font-extrabold uppercase tracking-wider text-slate-500">What changed in the traffic</h4>
            <div className="flex flex-wrap gap-2 text-[11px] font-bold">
              <Chip label="From a new terminal" value={`${rec.shifts.new_terminal_share_pct}%`} sub={rec.new_terminals.join(', ')} hot={rec.shifts.new_terminal_share_pct >= 30} />
              <Chip label="From a new city" value={`${rec.shifts.new_city_share_pct}%`} sub={rec.new_cities.join(', ')} hot={rec.shifts.new_city_share_pct >= 30} />
              <Chip label="Midnight to 6 am" value={`${rec.shifts.night_share_pct}%`} hot={rec.shifts.night_share_pct >= 40} />
              <Chip label="Top 3 payers" value={`${rec.shifts.top3_payer_share_pct}%`} hot={rec.shifts.top3_payer_share_pct >= 50} />
              <Chip label="Unusually large tickets" value={`${rec.shifts.big_ticket_share_pct}%`} sub={`usual ${inr(rec.shifts.usual_ticket)}`} hot={rec.shifts.big_ticket_share_pct >= 30} />
            </div>
            <p className="text-[10px] text-slate-400">These are evidence for the investigator. Only the two thresholds above start the agent.</p>
          </div>
        </div>
      )}

      {rec && rec.flagged.length > 0 && (
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-2xs space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-[11px] font-extrabold uppercase tracking-wider text-slate-500">Payments attached as evidence ({rec.flagged_total}{rec.flagged_total > rec.flagged.length ? `, top ${rec.flagged.length} shown` : ''}) · {inr(rec.flagged_amount)}</h4>
          </div>
          <div className="overflow-x-auto max-h-96 overflow-y-auto">
            <table className="w-full text-[11px] text-left">
              <thead className="text-slate-400 sticky top-0 bg-white"><tr><th className="py-1.5 pr-2">Payment</th><th className="pr-2">Time (IST)</th><th className="pr-2 text-right">Amount</th><th className="pr-2">Where</th><th className="pr-2">Payer</th><th>Why it is flagged</th></tr></thead>
              <tbody className="divide-y divide-slate-100">{rec.flagged.map((t) => <TxnRow key={t.id} t={t} />)}</tbody>
            </table>
          </div>
        </div>
      )}

      {!rec && d.eligible && (
        <p className="text-xs text-slate-500 flex items-center gap-2"><TrendingUp size={14} className="text-emerald-600" /> Nothing to investigate. The agent keeps comparing every 48 hours with the trailing baseline.</p>
      )}
    </div>
  );
}

function Metric({ label, value, hint, bad, warn }: { label: string; value: string; hint: string; bad?: boolean; warn?: boolean }) {
  return (
    <div className={`p-4 rounded-2xl border shadow-2xs bg-white ${bad ? 'border-rose-200 bg-rose-50/40' : warn ? 'border-amber-200 bg-amber-50/40' : 'border-slate-200/80'}`}>
      <div className="text-[11px] font-bold text-slate-500">{label}</div>
      <div className={`text-lg font-extrabold tracking-tight mt-1 ${bad ? 'text-rose-700' : 'text-[#002970]'}`}>{value}</div>
      <div className="text-[10px] font-semibold text-slate-500 mt-1 leading-snug">{hint}</div>
    </div>
  );
}

function Chip({ label, value, sub, hot }: { label: string; value: string; sub?: string; hot?: boolean }) {
  return (
    <span className={`px-2.5 py-1.5 rounded-lg border ${hot ? 'bg-rose-50 border-rose-200 text-rose-800' : 'bg-slate-50 border-slate-200 text-slate-700'}`}>
      {label}: <strong>{value}</strong>{sub ? <span className="font-medium text-[10px] opacity-80"> · {sub}</span> : null}
    </span>
  );
}

function TxnRow({ t }: { t: FlaggedTxn }) {
  return (
    <tr className="align-top">
      <td className="py-1.5 pr-2 font-mono">{t.ref}<span className={`ml-1 text-[9px] font-extrabold px-1 rounded ${t.status === 'chargeback' ? 'bg-rose-100 text-rose-800' : 'bg-slate-100 text-slate-600'}`}>{t.status}</span></td>
      <td className="pr-2 whitespace-nowrap">{t.ts}</td>
      <td className="pr-2 text-right font-bold whitespace-nowrap">{inr(t.amount)}</td>
      <td className="pr-2 whitespace-nowrap">{t.terminal} · {t.city}</td>
      <td className="pr-2 whitespace-nowrap">{t.payer}</td>
      <td className="text-slate-600 leading-snug">{t.reasons.join('; ')}</td>
    </tr>
  );
}

/** Daily volume for the baseline and the 48-hour window, with the baseline average as a line. Plain SVG, no chart library. */
function VolumeChart({ d }: { d: SettlementDetection }) {
  const W = 760, H = 150, pad = 8;
  const series = d.series;
  const max = Math.max(...series.map((s) => s.volume), d.baseline_daily ?? 1, 1);
  const bw = (W - pad * 2) / series.length;
  const y = (v: number) => H - 18 - (v / max) * (H - 30);
  return (
    <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-2xs">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-[11px] font-extrabold uppercase tracking-wider text-slate-500">Daily volume · 30-day baseline and the last 48 hours</h4>
        <span className="text-[10px] text-slate-400">Dashed line: baseline average {inr(d.baseline_daily)}/day</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-40" role="img" aria-label="Daily settlement volume">
        {series.map((s, i) => {
          const x = pad + i * bw;
          const top = y(s.volume);
          return <rect key={s.day} x={x + 1} y={top} width={Math.max(bw - 2, 1)} height={H - 18 - top} rx={2} className={s.window ? (d.velocity_anomaly ? 'fill-rose-500' : 'fill-[#00BAF2]') : 'fill-slate-300'}><title>{`${s.day}: ${inr(s.volume)}`}</title></rect>;
        })}
        <line x1={pad} x2={W - pad} y1={y(d.baseline_daily ?? 0)} y2={y(d.baseline_daily ?? 0)} className="stroke-[#002970]" strokeDasharray="4 3" strokeWidth={1} />
        <text x={pad} y={H - 4} className="fill-slate-400" fontSize={9}>{series[0]?.day}</text>
        <text x={W - pad} y={H - 4} textAnchor="end" className="fill-slate-400" fontSize={9}>{series[series.length - 1]?.day}</text>
      </svg>
    </div>
  );
}
