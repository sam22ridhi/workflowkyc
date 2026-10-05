import { useState } from 'react';
import { FileSearch, Loader2, MessageSquareText, Network, Send } from 'lucide-react';
import { askCase, type AskResult } from '@/services/api';

const SUGGESTIONS = [
  'Who owns more than 10% of this company, directly or indirectly?',
  'Who is the authorised signatory and are they a director?',
  'Which address does each document give?',
];

const GRAPH_LABEL = {
  none: { text: 'Memory not built yet', tone: 'bg-slate-100 text-slate-600 border-slate-200' },
  building: { text: 'Building knowledge graph…', tone: 'bg-[#e6f7fc] text-[#002970] border-[#cfe9fc]' },
  ready: { text: 'Knowledge graph ready', tone: 'bg-emerald-50 text-emerald-800 border-emerald-200' },
  failed: { text: 'Memory unavailable', tone: 'bg-amber-50 text-amber-800 border-amber-200' },
} as const;

interface AskCaseCardProps {
  caseId: string;
  graphStatus: 'none' | 'building' | 'ready' | 'failed';
  onOpenSource: (docId: string) => void;
}

/** Case Q&A over the Cognee knowledge graph. The answer explains; the pass/fail checks stay rule-based. */
export function AskCaseCard({ caseId, graphStatus, onOpenSource }: AskCaseCardProps) {
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<AskResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const ask = async (q: string) => {
    if (q.trim().length < 3 || busy) return;
    setQuestion(q);
    setBusy(true);
    setError(null);
    try {
      setResult(await askCase(caseId, q.trim()));
    } catch (e) {
      setResult(null);
      setError(e instanceof Error ? e.message.replace(/^\d+\s*/, '') : String(e));
    } finally {
      setBusy(false);
    }
  };

  const status = GRAPH_LABEL[graphStatus];
  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 shadow-2xs p-6 space-y-4">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex items-start gap-3">
          <div className="w-9 h-9 rounded-xl bg-[#e6f7fc] text-[#002970] flex items-center justify-center shrink-0"><MessageSquareText size={18} /></div>
          <div>
            <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Ask this case</h3>
            <p className="text-[11px] text-slate-500 font-medium">Answers come from the case&rsquo;s documents via Cognee memory, with sources.</p>
          </div>
        </div>
        <span className={`text-[10px] font-extrabold px-2.5 py-1 rounded-full border inline-flex items-center gap-1.5 ${status.tone}`}>
          <Network size={11} /> {status.text}
        </span>
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); void ask(question); }}
        className="flex items-center gap-2"
      >
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. Who owns more than 10%?"
          className="flex-1 px-3.5 py-2.5 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:border-[#00BAF2] focus:bg-white"
        />
        <button type="submit" disabled={busy || question.trim().length < 3} className="px-4 py-2.5 bg-[#002970] hover:bg-[#001b4c] text-white text-xs font-bold rounded-xl flex items-center gap-2 disabled:opacity-50">
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} className="text-[#00BAF2]" />} Ask
        </button>
      </form>

      <div className="flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <button key={s} onClick={() => void ask(s)} disabled={busy} className="text-[11px] font-semibold text-[#002970] bg-[#e6f7fc] hover:bg-[#d6f2fa] border border-[#cfe9fc] rounded-full px-3 py-1 disabled:opacity-50">{s}</button>
        ))}
      </div>

      {error && <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 font-semibold">{error} Everything else on this case keeps working.</div>}

      {result && (
        <div className="p-4 rounded-xl bg-[#e6f7fc]/50 border border-[#cfe9fc] space-y-3">
          <div className="text-xs text-slate-800 leading-relaxed whitespace-pre-wrap">{result.answer.replace(/\*\*/g, '')}</div>
          {result.note && <p className="text-[11px] text-amber-800 font-semibold">{result.note}</p>}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] font-extrabold uppercase tracking-wide text-slate-500">Sources</span>
            {result.sources.length === 0 && <span className="text-[11px] text-slate-500">No source document identified.</span>}
            {result.sources.map((s) => (
              <button key={s.doc_id} onClick={() => onOpenSource(s.doc_id)} className="text-[11px] font-bold text-[#002970] bg-white hover:bg-[#e6f7fc] border border-[#cfe9fc] rounded-lg px-2.5 py-1 inline-flex items-center gap-1.5">
                <FileSearch size={11} /> {s.doc_type_label} · {s.filename}
              </button>
            ))}
            {result.from_cache && <span className="text-[10px] font-semibold text-slate-500 bg-slate-100 border border-slate-200 rounded px-1.5">saved answer</span>}
          </div>
        </div>
      )}
    </div>
  );
}
