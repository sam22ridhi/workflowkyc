import { useEffect, useState } from 'react';
import QRCode from 'qrcode';
import { Camera, CheckCircle2, Copy, ExternalLink, Loader2, ShieldCheck } from 'lucide-react';
import type { CpvKind, CpvView } from '@/services/api';

const LABEL: Record<CpvKind, string> = { exterior: 'Shop front with signboard', counter: 'Billing counter or QR stand', selfie: 'Owner selfie' };

const STATUS: Record<CpvView['status'], { text: string; tone: string }> = {
  waiting: { text: 'Waiting for your photos', tone: 'bg-amber-50 text-amber-800 border-amber-200' },
  captured: { text: 'Photos received, checking…', tone: 'bg-[#e6f7fc] text-[#002970] border-[#cfe9fc]' },
  analysing: { text: 'Drishti is checking your shop…', tone: 'bg-[#e6f7fc] text-[#002970] border-[#cfe9fc]' },
  verified: { text: 'Shop verified', tone: 'bg-emerald-50 text-emerald-800 border-emerald-200' },
  needs_review: { text: 'With your account manager', tone: 'bg-amber-50 text-amber-800 border-amber-200' },
};

/** Where the merchant finds the shop-verification link (instead of a WhatsApp message). */
export function ShopVerificationCard({ cpv }: { cpv: CpvView }) {
  const [qr, setQr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const status = STATUS[cpv.status];
  const active = cpv.status === 'waiting' && !!cpv.link;

  useEffect(() => {
    if (!cpv.link) { setQr(null); return; }
    QRCode.toDataURL(cpv.link, { margin: 1, width: 168, color: { dark: '#002970', light: '#ffffff' } }).then(setQr, () => setQr(null));
  }, [cpv.link]);

  const copy = async () => {
    if (!cpv.link) return;
    try {
      await navigator.clipboard.writeText(cpv.link);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2500);
    } catch {
      /* the link stays selectable in the field */
    }
  };

  const expires = new Date(cpv.expiresAt);
  return (
    <section aria-labelledby="shop-verification" className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden mb-8">
      <div className="p-6 sm:p-8 space-y-5">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 rounded-xl bg-[#e6f7fc] text-[#00BAF2] flex items-center justify-center border border-[#cfe9fc] shrink-0"><Camera size={20} /></div>
            <div>
              <span className="text-[10px] font-extrabold uppercase tracking-widest text-[#00BAF2]">Stage 6 · Drishti</span>
              <h2 id="shop-verification" className="text-xl font-extrabold text-slate-900">Verify your shop</h2>
              <p className="text-sm text-slate-600 mt-1 max-w-md">Take two live photos at your shop from your phone. This replaces a visit by a field agent and takes about two minutes.</p>
            </div>
          </div>
          <span className={`text-[11px] font-extrabold px-2.5 py-1 rounded-full border inline-flex items-center gap-1.5 ${status.tone}`}>
            {(cpv.status === 'captured' || cpv.status === 'analysing') ? <Loader2 size={12} className="animate-spin" /> : cpv.status === 'verified' ? <CheckCircle2 size={12} /> : <ShieldCheck size={12} />}
            {status.text}
          </span>
        </div>

        <ol className="grid sm:grid-cols-2 gap-3">
          {cpv.required.map((k) => (
            <li key={k} className={`rounded-xl border p-3 flex items-center gap-3 text-sm font-semibold ${cpv.captured[k] ? 'border-emerald-200 bg-emerald-50 text-emerald-900' : 'border-slate-200 bg-slate-50 text-slate-700'}`}>
              {cpv.captured[k] ? <CheckCircle2 size={16} className="text-emerald-600 shrink-0" /> : <Camera size={16} className="text-slate-400 shrink-0" />}
              {LABEL[k]}
            </li>
          ))}
        </ol>

        {active && cpv.link && (
          <div className="grid sm:grid-cols-[1fr_auto] gap-5 items-center">
            <div className="space-y-3 min-w-0">
              <label htmlFor="cpv-link" className="text-[11px] font-extrabold uppercase tracking-wider text-slate-500">Your secure link</label>
              <input id="cpv-link" readOnly value={cpv.link} onFocus={(e) => e.currentTarget.select()} className="w-full px-3 py-2.5 text-xs font-mono rounded-lg border border-slate-200 bg-slate-50 text-slate-800" />
              <div className="flex flex-wrap gap-2">
                <button onClick={() => void copy()} className="px-3.5 py-2 rounded-lg bg-[#002970] text-white text-xs font-bold inline-flex items-center gap-1.5"><Copy size={13} />{copied ? 'Copied' : 'Copy link'}</button>
                <a href={cpv.link} target="_blank" rel="noreferrer" className="px-3.5 py-2 rounded-lg bg-white border border-slate-200 text-xs font-bold text-slate-700 inline-flex items-center gap-1.5"><ExternalLink size={13} />Open on this device</a>
              </div>
              <p className="text-[11px] text-slate-500">Open it on your phone, standing at the shop. It works once and expires on {expires.toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}.</p>
            </div>
            {qr && <img src={qr} alt="QR code for your secure link" width={168} height={168} className="rounded-xl border border-slate-200 mx-auto" />}
          </div>
        )}

        {cpv.status === 'verified' && <p className="text-sm text-emerald-800 font-semibold">Thank you. Your shop is verified and we will contact you for the next step.</p>}
        {cpv.status === 'needs_review' && <p className="text-sm text-amber-900 font-semibold">Your photos were received. A person will look at them and get back to you. You do not need to do anything now.</p>}
      </div>
    </section>
  );
}
