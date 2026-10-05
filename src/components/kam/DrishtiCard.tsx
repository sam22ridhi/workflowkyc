import { useState } from 'react';
import { AlertTriangle, Camera, CheckCircle2, CircleMinus, CircleX, Eye, Loader2, MapPin, RefreshCw, ShieldCheck } from 'lucide-react';
import { cpvImageUrl, postJson, type CpvCheck, type CpvKind, type CpvView } from '@/services/api';

const STATUS: Record<CpvView['status'], { text: string; tone: string }> = {
  waiting: { text: 'Waiting for the merchant', tone: 'bg-amber-50 text-amber-800 border-amber-200' },
  captured: { text: 'Photos received', tone: 'bg-[#e6f7fc] text-[#002970] border-[#cfe9fc]' },
  analysing: { text: 'Drishti is checking', tone: 'bg-[#e6f7fc] text-[#002970] border-[#cfe9fc]' },
  verified: { text: 'CPV_VERIFIED', tone: 'bg-emerald-50 text-emerald-800 border-emerald-200' },
  needs_review: { text: 'NEEDS_REVIEW', tone: 'bg-rose-50 text-rose-800 border-rose-200' },
};

function CheckRow({ c }: { c: CpvCheck }) {
  const Icon = c.status === 'pass' ? CheckCircle2 : c.status === 'fail' ? CircleX : c.status === 'warn' ? AlertTriangle : CircleMinus;
  const tone = c.status === 'pass' ? 'text-emerald-600' : c.status === 'fail' ? 'text-rose-600' : c.status === 'warn' ? 'text-amber-600' : 'text-slate-400';
  return (
    <li className={`p-3 rounded-xl border flex items-start gap-3 ${c.status === 'fail' ? 'border-rose-200 bg-rose-50/30' : 'border-slate-200 bg-slate-50/40'}`}>
      <Icon size={17} className={`${tone} shrink-0 mt-0.5`} />
      <div className="min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <strong className="text-xs font-bold text-slate-900">{c.label}</strong>
          {c.assistive && <span className="text-[9px] font-extrabold px-1.5 rounded bg-slate-100 text-slate-600 border border-slate-200">Assistive</span>}
          {c.status === 'fail' && <span className="text-[9px] font-extrabold px-1.5 rounded bg-rose-100 text-rose-800 border border-rose-300">Needs a look</span>}
        </div>
        <p className="text-[11px] text-slate-600 mt-0.5 leading-snug break-words">{c.detail}</p>
      </div>
    </li>
  );
}

/** DEMO ONLY: where the shop 'is', so a synthetic address can be tested from a laptop. The server refuses unless CPV_ALLOW_DEMO_REFERENCE=true. */
function DemoReferenceBox({ caseId }: { caseId: string }) {
  const [lat, setLat] = useState('');
  const [lon, setLon] = useState('');
  const [msg, setMsg] = useState<{ text: string; error: boolean } | null>(null);
  const here = () => {
    if (!navigator.geolocation) { setMsg({ text: 'This browser has no location support.', error: true }); return; }
    navigator.geolocation.getCurrentPosition(
      (p) => { setLat(p.coords.latitude.toFixed(6)); setLon(p.coords.longitude.toFixed(6)); setMsg(null); },
      (e) => setMsg({ text: `Could not read the location: ${e.message}`, error: true }),
      { enableHighAccuracy: true, timeout: 15000 },
    );
  };
  const save = async () => {
    try {
      await postJson(`/api/cases/${caseId}/cpv/demo-reference`, { lat: Number(lat), lon: Number(lon), label: 'demo reference point' });
      setMsg({ text: 'Demo reference point saved. It is written to the timeline.', error: false });
    } catch (e) {
      setMsg({ text: e instanceof Error ? e.message : 'Could not save', error: true });
    }
  };
  const valid = lat.trim() !== '' && lon.trim() !== '' && Number.isFinite(Number(lat)) && Number.isFinite(Number(lon));
  return (
    <div className="p-3 rounded-xl border border-dashed border-slate-300 bg-slate-50 text-xs space-y-2" aria-label="Demo reference point">
      <strong className="block text-[11px] uppercase tracking-wide text-slate-600">Demo only: set where the shop is</strong>
      <p className="text-[11px] text-slate-500">For a synthetic address. Stand where the merchant will take the photos, use this device&rsquo;s location, then save.</p>
      <div className="flex flex-wrap gap-2 items-center">
        <input aria-label="Latitude" value={lat} onChange={(e) => setLat(e.target.value)} placeholder="Latitude" className="w-32 px-2 py-1.5 border border-slate-300 rounded-lg" />
        <input aria-label="Longitude" value={lon} onChange={(e) => setLon(e.target.value)} placeholder="Longitude" className="w-32 px-2 py-1.5 border border-slate-300 rounded-lg" />
        <button onClick={here} className="px-3 py-1.5 rounded-lg bg-white border border-slate-300 font-bold text-slate-700">Use this device&rsquo;s location</button>
        <button onClick={() => void save()} disabled={!valid} className="px-3 py-1.5 rounded-lg bg-[#002970] text-white font-bold disabled:opacity-40">Save</button>
      </div>
      {msg && <p className={`text-[11px] font-semibold ${msg.error ? 'text-rose-700' : 'text-emerald-700'}`}>{msg.text}</p>}
    </div>
  );
}

interface DrishtiCardProps {
  caseId: string;
  cpv: CpvView;
  isCompliancePersona: boolean;
  onAct: (action: 'cpv_approve' | 'cpv_retake', success: string) => void;
}

/** Drishti's contact point verification: the evidence, the checks, and the two things a person can do about a flagged one. */
export function DrishtiCard({ caseId, cpv, isCompliancePersona, onAct }: DrishtiCardProps) {
  const status = STATUS[cpv.status];
  const kinds = (Object.keys(cpv.captured) as CpvKind[]);
  const review = cpv.status === 'needs_review';
  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-2xs space-y-4" aria-labelledby="drishti-title">
      <div className="flex items-start justify-between gap-3 flex-wrap pb-3 border-b border-slate-100">
        <div className="flex items-start gap-3">
          <div className="w-9 h-9 rounded-xl bg-[#e6f7fc] text-[#00BAF2] flex items-center justify-center shrink-0"><Eye size={18} /></div>
          <div>
            <h3 id="drishti-title" className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Drishti · Contact point verification</h3>
            <p className="text-[11px] text-slate-500 font-medium">Replaces a field visit. Drishti never fails a shop on its own: anything doubtful goes to a person.</p>
          </div>
        </div>
        <span className={`text-[10px] font-extrabold px-2.5 py-1 rounded-full border inline-flex items-center gap-1.5 ${status.tone}`}>
          {(cpv.status === 'captured' || cpv.status === 'analysing') && <Loader2 size={11} className="animate-spin" />}
          {cpv.status === 'verified' && <ShieldCheck size={11} />}
          {status.text}
        </span>
      </div>

      {cpv.summary && <p className="text-xs text-slate-800 leading-relaxed">{cpv.summary}</p>}

      {cpv.status === 'waiting' && (
        <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 font-semibold">
          The merchant has not sent the photos yet. The link is in their AI Communication Center{cpv.link ? '' : ' (no active link)'}.
          {cpv.link && <span className="block mt-1 font-mono text-[11px] break-all font-normal">{cpv.link}</span>}
        </div>
      )}

      {cpv.status === 'waiting' && !isCompliancePersona && <DemoReferenceBox caseId={caseId} />}

      {kinds.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {kinds.map((k) => {
            const c = cpv.captured[k]!;
            return (
              <figure key={k} className="rounded-xl border border-slate-200 overflow-hidden bg-slate-50">
                <img src={cpvImageUrl(caseId, k)} alt={`${k} photo`} loading="lazy" className="w-full aspect-[4/3] object-cover bg-slate-200" />
                <figcaption className="p-2 text-[10px] text-slate-600 space-y-0.5">
                  <strong className="block capitalize text-slate-800 text-[11px]">{k}</strong>
                  <span className="flex items-center gap-1"><MapPin size={10} />{c.lat.toFixed(5)}, {c.lon.toFixed(5)} · ±{Math.round(c.accuracy_m)} m</span>
                  <span className="block">{c.heading !== null && c.heading !== undefined ? `Bearing ${Math.round(c.heading)}° · ` : ''}{new Date(c.client_ts).toLocaleTimeString()}</span>
                </figcaption>
              </figure>
            );
          })}
        </div>
      )}

      {cpv.checks.length > 0 && <ul className="space-y-2">{cpv.checks.map((c) => <CheckRow key={c.id} c={c} />)}</ul>}

      {(cpv.distanceM !== null || cpv.ocr?.exterior) && (
        <dl className="grid sm:grid-cols-3 gap-3 text-xs">
          {cpv.distanceM !== null && <div className="rounded-xl border border-slate-200 p-3"><dt className="text-[10px] font-extrabold uppercase tracking-wide text-slate-500">Distance from declared address</dt><dd className="font-bold text-slate-900 mt-1">{Math.round(cpv.distanceM)} m</dd>{cpv.reference?.note && <dd className="text-[10px] text-amber-800 mt-1">{cpv.reference.note}</dd>}</div>}
          {cpv.tradeName && <div className="rounded-xl border border-slate-200 p-3"><dt className="text-[10px] font-extrabold uppercase tracking-wide text-slate-500">Trade name on file</dt><dd className="font-bold text-slate-900 mt-1">{cpv.tradeName}</dd></div>}
          {cpv.ocr?.exterior && <div className="rounded-xl border border-slate-200 p-3"><dt className="text-[10px] font-extrabold uppercase tracking-wide text-slate-500">Read on the signboard</dt><dd className="font-bold text-slate-900 mt-1 break-words">{cpv.ocr.exterior}</dd></div>}
        </dl>
      )}

      {cpv.decidedBy && <p className="text-[11px] text-slate-500">Decided by a person ({cpv.decidedBy}).</p>}

      {review && !isCompliancePersona && (
        <div className="flex flex-wrap gap-2 pt-1">
          <button onClick={() => onAct('cpv_approve', 'You approved the contact point verification. V-CIP sign-off is next.')} className="px-4 py-2 rounded-xl bg-[#002970] hover:bg-[#001b4c] text-white text-xs font-bold inline-flex items-center gap-1.5">
            <CheckCircle2 size={14} className="text-[#00BAF2]" /> Approve after review
          </button>
          <button onClick={() => onAct('cpv_retake', 'The merchant has a fresh link for new photos.')} className="px-4 py-2 rounded-xl bg-white border border-slate-300 text-slate-800 text-xs font-bold inline-flex items-center gap-1.5">
            <RefreshCw size={14} /> Ask for new photos
          </button>
        </div>
      )}
      {cpv.status === 'waiting' && !isCompliancePersona && (
        <button onClick={() => onAct('cpv_retake', 'A fresh link was created for the merchant.')} className="px-3.5 py-2 rounded-xl bg-white border border-slate-300 text-slate-700 text-xs font-bold inline-flex items-center gap-1.5">
          <Camera size={13} /> Create a fresh link
        </button>
      )}
    </div>
  );
}
