import { useState } from 'react';
import { CheckCircle2, ChevronDown, ChevronUp, FileText, Loader2, PhoneCall, UserCheck, UserRoundX } from 'lucide-react';
import { cpvImageUrl, documentFileUrl, type VcipView } from '@/services/api';
import { normalisePhone } from '@/components/kam/VoiceChasePanel';

const STATUS: Record<VcipView['status'], { text: string; tone: string }> = {
  queued: { text: 'Pre-interview not done yet', tone: 'bg-amber-50 text-amber-800 border-amber-200' },
  interviewed: { text: 'Ready for your sign-off', tone: 'bg-emerald-50 text-emerald-800 border-emerald-200' },
  signed_off: { text: 'Signed off', tone: 'bg-emerald-50 text-emerald-800 border-emerald-200' },
};

interface VcipCardProps {
  caseId: string;
  vcip: VcipView;
  defaultPhone?: string;
  isCompliancePersona: boolean;
  onCall: (phone: string) => Promise<void>;
  onSignOff: () => Promise<void>;
}

/** The authorised official's V-CIP view. RBI requires a person to do the identification and sign it off; this makes their part about 30 seconds. */
export function VcipCard({ caseId, vcip, defaultPhone = '', isCompliancePersona, onCall, onSignOff }: VcipCardProps) {
  const [phone, setPhone] = useState(defaultPhone);
  const [busy, setBusy] = useState<'call' | 'sign' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showTranscript, setShowTranscript] = useState(false);
  const number = normalisePhone(phone);
  const status = STATUS[vcip.status];
  const signed = vcip.status === 'signed_off';

  const run = async (kind: 'call' | 'sign', fn: () => Promise<void>) => {
    setBusy(kind);
    setError(null);
    try { await fn(); } catch (e) { setError((e instanceof Error ? e.message : String(e)).replace(/^\d{3}\s/, '')); } finally { setBusy(null); }
  };

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-2xs space-y-4" aria-labelledby="vcip-title">
      <div className="flex items-start justify-between gap-3 flex-wrap pb-3 border-b border-slate-100">
        <div className="flex items-start gap-3">
          <div className="w-9 h-9 rounded-xl bg-[#e6f7fc] text-[#002970] flex items-center justify-center shrink-0"><UserCheck size={18} /></div>
          <div>
            <h3 id="vcip-title" className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">V-CIP · Video KYC sign-off</h3>
            <p className="text-[11px] text-slate-500 font-medium">The voice agent runs a short Hindi pre-interview. An authorised official signs off. The agent cannot.</p>
          </div>
        </div>
        <span className={`text-[10px] font-extrabold px-2.5 py-1 rounded-full border ${status.tone}`}>{status.text}</span>
      </div>

      <div>
        <h4 className="text-[11px] font-extrabold uppercase tracking-wider text-slate-500 mb-2">Randomized liveness questions</h4>
        <ol className="space-y-2">
          {vcip.questions.map((q) => (
            <li key={q.id} className="rounded-xl border border-slate-200 p-3 text-xs">
              <p className="font-semibold text-slate-900">{q.id}. {q.en}</p>
              <p className="text-slate-500 mt-0.5">{q.hi}</p>
              <p className="mt-1 text-[11px]"><span className="font-extrabold text-slate-500 uppercase tracking-wide">Expected: </span><span className="font-semibold text-slate-800">{q.expected}</span></p>
            </li>
          ))}
        </ol>
      </div>

      {vcip.transcript.length > 0 && (
        <div>
          <button onClick={() => setShowTranscript((v) => !v)} aria-expanded={showTranscript} className="text-[11px] font-bold text-[#002970] inline-flex items-center gap-1">
            {showTranscript ? 'Hide pre-interview transcript' : `Pre-interview transcript (${vcip.transcript.length})`}{showTranscript ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
          {showTranscript && (
            <ul className="mt-2 space-y-1.5 border-t border-slate-100 pt-2">
              {vcip.transcript.map((t, i) => (
                <li key={i} className="text-xs"><b className="uppercase text-[9px] tracking-wide text-slate-400 mr-1.5">{t.role}</b>{t.text}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      {vcip.summary && <p className="text-xs text-slate-700">{vcip.summary}</p>}

      <div className="rounded-xl border border-slate-200 p-3 space-y-3">
        <h4 className="text-[11px] font-extrabold uppercase tracking-wider text-slate-500">Compare the face yourself</h4>
        <div className="grid sm:grid-cols-2 gap-3">
          <div className="rounded-lg bg-slate-50 border border-slate-200 p-2 text-center">
            {vcip.selfie ? <img src={cpvImageUrl(caseId, 'selfie')} alt="Owner selfie" className="w-full aspect-[4/3] object-cover rounded-md" />
              : <div className="aspect-[4/3] flex flex-col items-center justify-center text-slate-500 text-[11px] gap-1"><UserRoundX size={20} />No selfie was sent</div>}
            <span className="block text-[10px] font-bold text-slate-600 mt-1">Owner selfie</span>
          </div>
          <div className="rounded-lg bg-slate-50 border border-slate-200 p-3 flex flex-col items-center justify-center text-center gap-2">
            <FileText size={22} className="text-slate-500" />
            {vcip.referenceDocument
              ? <a href={documentFileUrl(vcip.referenceDocument.docId)} target="_blank" rel="noreferrer" className="text-xs font-bold text-[#002970] underline">Open {vcip.referenceDocument.filename}</a>
              : <span className="text-[11px] text-slate-500">No PAN or ID document on file</span>}
            <span className="text-[10px] font-bold text-slate-600">ID photo</span>
          </div>
        </div>
        <p className="text-[11px] text-amber-900 bg-amber-50 border border-amber-200 rounded-lg p-2 font-semibold">{vcip.faceMatch.note}</p>
      </div>

      {error && <p role="alert" className="text-xs text-rose-700 font-semibold">{error}</p>}

      {isCompliancePersona && !signed && (
        <div className="space-y-3 pt-1">
          <div className="flex flex-wrap items-end gap-2">
            <div className="grow min-w-[200px]">
              <label htmlFor="vcip-phone" className="text-[10px] font-extrabold uppercase tracking-wide text-slate-500">Phone number for the pre-interview</label>
              <input id="vcip-phone" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+91 98123 45678" aria-invalid={phone.length > 0 && !number}
                className="w-full mt-1 px-3 py-2 text-sm rounded-lg border border-slate-300" />
            </div>
            <button onClick={() => void run('call', () => onCall(number!))} disabled={!number || busy !== null || !vcip.agentConfigured}
              className="px-4 py-2 rounded-xl bg-white border border-slate-300 text-xs font-bold text-slate-800 inline-flex items-center gap-1.5 disabled:opacity-50">
              {busy === 'call' ? <Loader2 size={14} className="animate-spin" /> : <PhoneCall size={14} />} Start pre-interview call
            </button>
          </div>
          {!vcip.agentConfigured && <p className="text-[11px] text-amber-800 font-semibold">The V-CIP voice agent is not set up yet (SARVAM_VCIP_AGENT_ID). You can still sign off, and it will be recorded without a pre-interview.</p>}
          {vcip.status !== 'interviewed' && vcip.agentConfigured && <p className="text-[11px] text-amber-800 font-semibold">No completed pre-interview is on record. Signing off now will be flagged on the timeline.</p>}
          <button onClick={() => void run('sign', onSignOff)} disabled={busy !== null}
            className="px-5 py-2.5 rounded-xl bg-[#002970] hover:bg-[#001b4c] text-white text-xs font-bold inline-flex items-center gap-2 disabled:opacity-60">
            {busy === 'sign' ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} className="text-[#00BAF2]" />} Sign off V-CIP (one click)
          </button>
        </div>
      )}
      {!isCompliancePersona && !signed && <p className="text-[11px] text-slate-500">Only the Compliance officer can start the pre-interview and sign off. Switch persona to Compliance to act.</p>}
      {signed && <p className="text-xs text-emerald-800 font-semibold">Signed off by {vcip.signedOffBy}. The case moves to the bank settlement test.</p>}
    </div>
  );
}
