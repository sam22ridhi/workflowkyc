import { useState } from 'react';
import { Brain, ChevronDown, ChevronUp, Mic, PhoneOff } from 'lucide-react';
import type { VoiceCallRecord } from '@/services/api';

const TONE: Record<string, string> = {
  promised_upload: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  reached: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  callback_requested: 'bg-amber-50 text-amber-800 border-amber-200',
  no_answer: 'bg-amber-50 text-amber-800 border-amber-200',
  busy: 'bg-amber-50 text-amber-800 border-amber-200',
  wrong_number: 'bg-rose-50 text-rose-800 border-rose-200',
  failed: 'bg-rose-50 text-rose-800 border-rose-200',
  not_configured: 'bg-slate-100 text-slate-600 border-slate-200',
};

const MEMORY: Record<string, { text: string; tone: string }> = {
  stored: { text: 'In case memory', tone: 'text-purple-700' },
  pending: { text: 'Saving to memory…', tone: 'text-slate-500' },
  failed: { text: 'Memory unavailable', tone: 'text-amber-700' },
  'n/a': { text: '', tone: '' },
};

/** Voice Chase history: what the agent said, what the merchant answered, and the outcome. Newest first. */
export function VoiceCallsCard({ calls }: { calls: VoiceCallRecord[] }) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 shadow-2xs p-6 space-y-4">
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-xl bg-[#e6f7fc] text-[#00BAF2] flex items-center justify-center shrink-0"><Mic size={18} /></div>
        <div>
          <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Voice chase history</h3>
          <p className="text-[11px] text-slate-500 font-medium">Calls by the Karyakarta voice agent. Completed calls are added to the case memory.</p>
        </div>
      </div>

      {calls.length === 0 && <p className="text-xs text-slate-500">No voice chase yet. Use Voice Chase to contact the merchant about open items.</p>}

      <ol className="space-y-3">
        {calls.map((c) => {
          const mem = MEMORY[c.memoryStatus] ?? MEMORY.pending;
          const expanded = open === c.id;
          return (
            <li key={c.id} className="rounded-xl border border-slate-200 p-3.5">
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`text-[10px] font-extrabold px-2 py-0.5 rounded-full border inline-flex items-center gap-1 ${TONE[c.outcome] ?? TONE.not_configured}`}>
                    {c.outcome === 'not_configured' && <PhoneOff size={10} />}
                    {c.title.replace('Voice call: ', '').replace('Voice call ', '')}
                  </span>
                  <span className="font-mono text-[10px] text-slate-400">{c.timestamp}</span>
                  {mem.text && <span className={`text-[10px] font-semibold inline-flex items-center gap-1 ${mem.tone}`}><Brain size={10} />{mem.text}</span>}
                </div>
                {c.transcript.length > 0 && (
                  <button onClick={() => setOpen(expanded ? null : c.id)} className="text-[11px] font-bold text-[#002970] inline-flex items-center gap-1" aria-expanded={expanded}>
                    {expanded ? 'Hide transcript' : `Transcript (${c.transcript.length})`}{expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                  </button>
                )}
              </div>
              {c.summary && <p className="text-xs text-slate-700 mt-2 leading-relaxed">{c.summary}</p>}
              {expanded && (
                <ul className="mt-3 space-y-1.5 border-t border-slate-100 pt-3">
                  {c.transcript.map((t, i) => (
                    <li key={i} className={`text-xs flex gap-2 ${t.role === 'agent' ? '' : 'flex-row-reverse text-right'}`}>
                      <span className={`px-2.5 py-1.5 rounded-xl max-w-[85%] ${t.role === 'agent' ? 'bg-[#e6f7fc] text-[#002970]' : 'bg-slate-100 text-slate-800'}`}>
                        <b className="block text-[9px] uppercase tracking-wide opacity-60">{t.role}</b>{t.text}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              {c.callId && <small className="block mt-2 font-mono text-[10px] text-slate-400">Call id {c.callId}</small>}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
