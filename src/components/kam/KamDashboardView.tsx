import { useMemo, useState } from 'react';
import {
  ArrowRight,
  Clock,
  Sparkles,
  AlertCircle,
  CheckCircle2,
  Search,
  TrendingUp,
  ShieldCheck,
  Building2,
  Timer,
  FileWarning,
  Loader2,
} from 'lucide-react';
import { useLiveCases } from '@/services/useLiveCase';
import type { CaseRow, Route } from '@/services/api';

interface KamDashboardViewProps {
  onOpenCase: (caseId: string) => void;
}

export function KamDashboardView({ onOpenCase }: KamDashboardViewProps) {
  const { list, loading, error } = useLiveCases();
  const [filterStage, setFilterStage] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState<string>('');

  const items = useMemo(() => list?.items ?? [], [list]);
  const kpis = list?.kpis;
  const urgentCount = items.filter((c) => c.isUrgent).length;
  const priority = useMemo(
    () => [...items].filter((c) => c.route === 'ESCALATE').sort((a, b) => a.slaMinutes - b.slaMinutes)[0] ?? [...items].sort((a, b) => a.slaMinutes - b.slaMinutes)[0],
    [items],
  );

  const filteredCases = items.filter((c) => {
    const q = searchTerm.toLowerCase();
    const matchesSearch = c.merchantName.toLowerCase().includes(q) || c.id.toLowerCase().includes(q) || c.legalName.toLowerCase().includes(q);
    if (filterStage === 'all') return matchesSearch;
    if (filterStage === 'urgent') return matchesSearch && c.isUrgent;
    return matchesSearch && c.stage === filterStage;
  });

  return (
    <div className="p-6 md:p-8 space-y-8 max-w-7xl mx-auto w-full">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-[10px] font-extrabold uppercase tracking-widest text-[#00BAF2] bg-[#e6f7fc] px-2.5 py-0.5 rounded-full border border-[#cfe9fc]">Real-time Portfolio</span>
            <span className="text-xs text-slate-500 font-medium">{error ? 'Backend unreachable' : loading ? 'Loading…' : 'Live · updates as documents are processed'}</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-extrabold text-[#002970] tracking-tight">Welcome, Priya. Here is your pipeline.</h1>
          <p className="text-xs md:text-sm text-slate-600 mt-1 font-medium">
            Karyakarta AI autonomously parses incoming documents, identifies registry discrepancies, and prepares checker-ready files.
          </p>
        </div>
        {priority && (
          <button
            onClick={() => onOpenCase(priority.id)}
            className="px-4 py-2.5 bg-[#002970] hover:bg-[#001b4c] text-white text-xs font-bold rounded-xl transition-all shadow-sm flex items-center gap-2"
          >
            <Sparkles size={14} className="text-[#00BAF2]" />
            <span>Open Priority Case ({priority.merchantName})</span>
            <ArrowRight size={14} />
          </button>
        )}
      </div>

      {/* 5 KPI cards, from the backend */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3.5 md:gap-4">
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-2xs hover:shadow-xs transition-shadow">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-[11px] font-bold tracking-wide">Total Open Cases</span>
            <div className="w-7 h-7 rounded-lg bg-slate-100 flex items-center justify-center text-slate-700"><Building2 size={15} /></div>
          </div>
          <div className="text-2xl md:text-3xl font-extrabold text-[#002970] tracking-tight">{kpis?.totalOpen ?? '–'}</div>
          <div className="text-[11px] font-semibold text-slate-500 mt-1 flex items-center gap-1">
            <TrendingUp size={12} className="text-emerald-500" />
            <span className="text-emerald-600 font-bold">+{kpis?.newThisWeek ?? 0}</span> new this week
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-[#cfe9fc] bg-gradient-to-br from-white to-[#f0f9fd] shadow-2xs hover:shadow-xs transition-shadow">
          <div className="flex items-center justify-between text-[#002970] mb-2">
            <span className="text-[11px] font-bold tracking-wide">Pending AI Verification</span>
            <div className="w-7 h-7 rounded-lg bg-[#e6f7fc] text-[#00BAF2] flex items-center justify-center"><Sparkles size={15} /></div>
          </div>
          <div className="text-2xl md:text-3xl font-extrabold text-[#00BAF2] tracking-tight">{kpis?.pendingAiVerification ?? '–'}</div>
          <div className="text-[11px] font-semibold text-slate-500 mt-1">Reading &amp; cross-checking documents</div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-amber-200/80 bg-gradient-to-br from-white to-amber-50/30 shadow-2xs hover:shadow-xs transition-shadow">
          <div className="flex items-center justify-between text-amber-700 mb-2">
            <span className="text-[11px] font-bold tracking-wide">Awaiting Merchant</span>
            <div className="w-7 h-7 rounded-lg bg-amber-100/70 text-amber-600 flex items-center justify-center"><Clock size={15} /></div>
          </div>
          <div className="text-2xl md:text-3xl font-extrabold text-amber-600 tracking-tight">{kpis?.awaitingMerchant ?? '–'}</div>
          <div className="text-[11px] font-semibold text-amber-800/80 mt-1">Documents or corrections outstanding</div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-emerald-200/80 bg-gradient-to-br from-white to-emerald-50/30 shadow-2xs hover:shadow-xs transition-shadow">
          <div className="flex items-center justify-between text-emerald-800 mb-2">
            <span className="text-[11px] font-bold tracking-wide">Ready for Submission</span>
            <div className="w-7 h-7 rounded-lg bg-emerald-100/70 text-emerald-600 flex items-center justify-center"><CheckCircle2 size={15} /></div>
          </div>
          <div className="text-2xl md:text-3xl font-extrabold text-emerald-700 tracking-tight">{kpis?.readyForSubmission ?? '–'}</div>
          <div className="text-[11px] font-semibold text-emerald-800/80 mt-1">All checks passed</div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-rose-200 bg-gradient-to-br from-white to-rose-50/40 shadow-2xs hover:shadow-xs transition-shadow col-span-2 lg:col-span-1">
          <div className="flex items-center justify-between text-rose-700 mb-2">
            <span className="text-[11px] font-bold tracking-wide">Escalations (Red)</span>
            <div className="w-7 h-7 rounded-lg bg-rose-100 text-rose-600 flex items-center justify-center"><AlertCircle size={15} /></div>
          </div>
          <div className="text-2xl md:text-3xl font-extrabold text-rose-600 tracking-tight">{kpis?.escalations ?? '–'}</div>
          <div className="text-[11px] font-semibold text-rose-700/80 mt-1">Need human judgement</div>
        </div>
      </div>

      {/* All Cases table */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-2xs overflow-hidden">
        <div className="p-5 border-b border-slate-200/70 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <h2 className="text-base font-extrabold text-[#002970]">All Cases ({filteredCases.length})</h2>
            <div className="flex items-center gap-1.5 bg-slate-100 p-1 rounded-xl text-xs font-bold">
              <button onClick={() => setFilterStage('all')} className={`px-3 py-1 rounded-lg transition-all ${filterStage === 'all' ? 'bg-white text-[#002970] shadow-2xs' : 'text-slate-600 hover:text-slate-900'}`}>All</button>
              <button onClick={() => setFilterStage('urgent')} className={`px-3 py-1 rounded-lg transition-all ${filterStage === 'urgent' ? 'bg-rose-50 text-rose-700 shadow-2xs font-extrabold' : 'text-slate-600 hover:text-slate-900'}`}>Urgent ({urgentCount})</button>
              <button onClick={() => setFilterStage('Ready for Review')} className={`px-3 py-1 rounded-lg transition-all ${filterStage === 'Ready for Review' ? 'bg-emerald-50 text-emerald-700 shadow-2xs font-extrabold' : 'text-slate-600 hover:text-slate-900'}`}>Ready</button>
            </div>
          </div>
          <div className="relative w-full sm:w-72">
            <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search merchant or case ID..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:border-[#00BAF2] focus:bg-white transition-all"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/70 border-b border-slate-200 text-[11px] font-extrabold text-slate-500 uppercase tracking-wider">
                <th className="py-3 px-5">Merchant Name</th>
                <th className="py-3 px-4">Entity Type</th>
                <th className="py-3 px-4">Current Stage</th>
                <th className="py-3 px-4">Docs</th>
                <th className="py-3 px-4">AI Flags</th>
                <th className="py-3 px-4">SLA Timer</th>
                <th className="py-3 px-5 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs">
              {loading && (
                <tr><td colSpan={7} className="py-10 text-center text-slate-500"><Loader2 size={16} className="inline animate-spin mr-2" />Loading cases…</td></tr>
              )}
              {error && !items.length && (
                <tr><td colSpan={7} className="py-10 text-center text-rose-600 font-semibold">Could not load cases: {error}</td></tr>
              )}
              {filteredCases.map((c) => (
                <tr key={c.id} className="hover:bg-slate-50/60 transition-colors group cursor-pointer" onClick={() => onOpenCase(c.id)}>
                  <td className="py-4 px-5">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-[#002970] text-[#00BAF2] font-black text-xs flex items-center justify-center shrink-0">{c.merchantName.slice(0, 2).toUpperCase()}</div>
                      <div>
                        <strong className="block text-xs font-bold text-slate-900 group-hover:text-[#002970]">{c.merchantName}</strong>
                        <small className="block text-[10px] text-slate-500">{c.id} · {c.legalName}</small>
                      </div>
                    </div>
                  </td>
                  <td className="py-4 px-4 font-semibold text-slate-700">
                    <span className="px-2 py-0.5 rounded-md bg-slate-100 text-[11px] font-medium text-slate-600 border border-slate-200">{c.entityType}</span>
                  </td>
                  <td className="py-4 px-4"><StagePill stage={c.stage} route={c.route} /></td>
                  <td className="py-4 px-4 font-mono text-[11px] text-slate-600">{c.docProgress.processed}/{c.docProgress.required}</td>
                  <td className="py-4 px-4"><FlagPills row={c} /></td>
                  <td className="py-4 px-4">
                    <div className="flex items-center gap-1.5 font-bold">
                      <Timer size={14} className={c.slaMinutes < 20 ? 'text-rose-500 animate-pulse' : 'text-slate-400'} />
                      <span className={c.slaMinutes < 20 ? 'text-rose-600 font-extrabold' : 'text-slate-600'}>{c.slaMinutes}m left</span>
                    </div>
                  </td>
                  <td className="py-4 px-5 text-right">
                    <button
                      onClick={(e) => { e.stopPropagation(); onOpenCase(c.id); }}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-white border border-slate-200 hover:border-[#00BAF2] hover:text-[#002970] text-slate-700 text-xs font-bold transition-all shadow-2xs group-hover:bg-[#002970] group-hover:text-white group-hover:border-[#002970]"
                    >
                      <span>View Case</span>
                      <ArrowRight size={13} className="text-[#00BAF2]" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="p-4 bg-slate-50/50 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500 font-medium">
          <span>Showing {filteredCases.length} of {items.length} corporate accounts</span>
          <span className="flex items-center gap-1.5">
            <ShieldCheck size={14} className="text-emerald-600" />
            Registry data in this demo is a labelled mock (MCA21 / GSTN / bank penny-drop).
          </span>
        </div>
      </div>
    </div>
  );
}

const ROUTE_STYLE: Record<Route, string> = {
  AUTO: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  ASK: 'bg-amber-50 text-amber-800 border-amber-200',
  ESCALATE: 'bg-rose-50 text-rose-800 border-rose-200',
};

function StagePill({ stage, route }: { stage: string; route: Route | null }) {
  const base = 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold border';
  const routeChip = route ? <span className={`ml-1 px-1.5 rounded text-[9px] font-extrabold border ${ROUTE_STYLE[route]}`}>{route}</span> : null;
  if (stage === 'Ready for Review') {
    return <span className={`${base} bg-emerald-50 text-emerald-800 border-emerald-200`}><span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />Ready for Review{routeChip}</span>;
  }
  if (stage === 'AI Verifying') {
    return <span className={`${base} bg-[#e6f7fc] text-[#002970] border-[#cfe9fc]`}><Sparkles size={11} className="text-[#00BAF2]" />AI Verifying{routeChip}</span>;
  }
  if (stage === 'Awaiting Merchant Action') {
    return <span className={`${base} bg-amber-50 text-amber-800 border-amber-200`}><Clock size={11} className="text-amber-600" />Awaiting Merchant{routeChip}</span>;
  }
  if (stage === 'Escalated to KAM') {
    return <span className={`${base} bg-rose-50 text-rose-800 border-rose-200`}><AlertCircle size={11} className="text-rose-600" />Escalated to KAM{routeChip}</span>;
  }
  return <span className={`${base} bg-slate-100 text-slate-700 border-slate-200`}><FileWarning size={11} className="text-slate-500" />{stage}{routeChip}</span>;
}

const FLAG_STYLE = {
  critical: 'bg-rose-50 text-rose-800 border-rose-200',
  warning: 'bg-amber-50 text-amber-800 border-amber-200',
  info: 'bg-blue-50 text-blue-800 border-blue-200',
  ok: 'bg-emerald-50 text-emerald-800 border-emerald-200',
} as const;

function FlagPills({ row }: { row: CaseRow }) {
  if (!row.flags.length) {
    return <span className="text-[11px] text-slate-400 font-medium">{row.docProgress.processed === 0 ? 'No documents yet' : 'Checking…'}</span>;
  }
  const shown = row.flags.slice(0, 2);
  const extra = row.flags.length - shown.length;
  return (
    <div className="flex flex-col items-start gap-1">
      {shown.map((f) => (
        <span key={f.label} className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-bold border max-w-[250px] ${FLAG_STYLE[f.severity]}`}>
          {f.severity === 'ok' ? <CheckCircle2 size={12} className="text-emerald-600 shrink-0" /> : <AlertCircle size={12} className="shrink-0" />}
          <span className="truncate">{f.severity === 'ok' ? `Verified${row.aiConfidence ? ` (${row.aiConfidence}%)` : ''}` : f.label}</span>
        </span>
      ))}
      {extra > 0 && <span className="text-[10px] font-semibold text-slate-500">+{extra} more</span>}
    </div>
  );
}
