import { useEffect, useState } from 'react';
import { Check, Lock, Loader2, Mic, PhoneCall, Send, X } from 'lucide-react';
import { api, type VoiceChaseContext } from '@/services/api';

export type ChaseChannel = 'voice' | 'whatsapp' | 'email';

interface VoiceChasePanelProps {
  caseId?: string;
  merchantName: string;
  contactName?: string;
  /** Number stored on the case (the merchant's contact). The KAM can change it before calling. */
  defaultPhone?: string;
  /** Fallback request text when the agent context can't be loaded. */
  request?: string;
  onClose: () => void;
  /** Resolve when the action succeeded; reject with the reason to keep the drawer open and show it. */
  onSend: (channel: ChaseChannel, phone?: string) => Promise<void> | void;
}

const split = (list?: string) => (list && list !== 'none' && list !== 'कोई नहीं' ? list.split(/;\s*/).map((x) => x.replace(/^\d+\.\s*/, '')) : []);

/** Same rules as the backend: 10 digits are Indian numbers; otherwise the international format with a leading +. */
export function normalisePhone(raw: string): string | null {
  let s = raw.trim().replace(/[\s\-().]/g, '');
  if (s.startsWith('00')) s = '+' + s.slice(2);
  if (/^\d{10}$/.test(s)) s = '+91' + s;
  else if (/^0\d{10}$/.test(s)) s = '+91' + s.slice(1);
  else if (/^\d{11,15}$/.test(s)) s = '+' + s;
  return /^\+[1-9]\d{7,14}$/.test(s) ? s : null;
}

export function VoiceChasePanel({ caseId, merchantName, contactName, defaultPhone = '', request = 'Missing documents', onClose, onSend }: VoiceChasePanelProps) {
  const [channel, setChannel] = useState<ChaseChannel>('voice');
  const [ctx, setCtx] = useState<VoiceChaseContext | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [phone, setPhone] = useState(defaultPhone);
  const [busy, setBusy] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  useEffect(() => {
    if (!caseId) return;
    api<VoiceChaseContext>(`/api/cases/${caseId}/voice-chase/context`).then(setCtx, (e) => setError(e instanceof Error ? e.message : String(e)));
  }, [caseId]);

  const docs = split(ctx?.agent_variables.documents_needed_en);
  const nothing = ctx && !ctx.should_call;
  const normalised = normalisePhone(phone);
  const needsNumber = channel === 'voice';
  const canSend = !busy && !nothing && (!needsNumber || !!normalised);

  const send = async () => {
    setBusy(true);
    setSendError(null);
    try {
      await onSend(channel, needsNumber ? normalised ?? undefined : undefined);
    } catch (e) {
      setSendError((e instanceof Error ? e.message : String(e)).replace(/^\d{3}\s/, ''));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="voice-chase-panel" onClick={(event) => event.stopPropagation()}>
        <div className="voice-panel-head">
          <div>
            <span className="eyebrow-label ai-label"><Mic size={14} /> KARYAKARTA Voice · Sarvam agent</span>
            <h2>Chase {merchantName} without leaving the case.</h2>
          </div>
          <button className="drawer-close" onClick={onClose} aria-label="Close"><X size={18} /></button>
        </div>

        <p className="voice-panel-copy">
          {ctx
            ? nothing
              ? 'Nothing on this case needs the merchant right now, so there is nothing to chase.'
              : `The agent will call ${contactName ?? ctx.agent_variables.contact_name} and raise ${ctx.agent_variables.issue_count} item(s) the merchant can fix.`
            : error ? `Could not load the agent context (${error}). Request: ${request}.` : 'Preparing the agent context…'}
        </p>

        {ctx && !nothing && (
          <div className="voice-script">
            <span className="script-label">Opening line (Hindi)</span>
            <p>“{ctx.initial_bot_message}”</p>
          </div>
        )}

        {docs.length > 0 && (
          <div className="voice-request-summary" style={{ display: 'block' }}>
            <small>THE AGENT WILL ASK FOR</small>
            <ol style={{ margin: '6px 0 0 18px', fontSize: 12, lineHeight: 1.5 }}>{docs.map((d) => <li key={d}>{d}</li>)}</ol>
          </div>
        )}

        {ctx && ctx.held_back_for_kam.length > 0 && (
          <div className="voice-request-summary" style={{ display: 'block' }}>
            <small><Lock size={11} style={{ display: 'inline', marginRight: 4 }} />NOT RAISED ON THE CALL (YOUR DECISION)</small>
            <ul style={{ margin: '6px 0 0 18px', fontSize: 12, lineHeight: 1.5 }}>{ctx.held_back_for_kam.map((d) => <li key={d}>{d}</li>)}</ul>
          </div>
        )}

        <div className="voice-request-summary">
          <span><small>CHANNEL</small>
            <div className="channel-buttons">
              {(['voice', 'whatsapp', 'email'] as const).map((item) => (
                <button key={item} className={channel === item ? 'selected' : ''} onClick={() => setChannel(item)}>
                  {item === 'whatsapp' ? 'WhatsApp' : item[0].toUpperCase() + item.slice(1)}
                </button>
              ))}
            </div>
          </span>
        </div>

        {needsNumber && (
          <div className="voice-request-summary" style={{ display: 'block' }}>
            <label htmlFor="voice-phone"><small>PHONE NUMBER TO CALL</small></label>
            <input
              id="voice-phone"
              type="tel"
              inputMode="tel"
              autoComplete="off"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+91 98123 45678"
              aria-invalid={phone.length > 0 && !normalised}
              style={{ width: '100%', marginTop: 6, padding: '9px 12px', borderRadius: 10, border: '1px solid #cfe9fc', fontSize: 14, fontFamily: 'inherit' }}
            />
            <small style={{ display: 'block', marginTop: 6 }}>
              {phone.length === 0 ? 'Enter the merchant’s number. Ten digits are taken as an Indian number.'
                : normalised ? `Will call ${normalised}.` : 'That does not look like a valid number. Use the international format, for example +919812345678.'}
            </small>
          </div>
        )}

        {sendError && <div role="alert" className="voice-request-summary" style={{ display: 'block', color: '#a3262a', fontWeight: 600, fontSize: 13 }}>{sendError}</div>}

        <button className="button button-blue button-full" disabled={!canSend} onClick={() => void send()}>
          {busy ? <Loader2 size={16} className="animate-spin" /> : channel === 'voice' ? <PhoneCall size={16} /> : <Send size={16} />}
          {' '}{channel === 'voice' ? (normalised ? `Call ${normalised} now` : 'Call now') : `Send ${channel} request`}
        </button>
        <span className="voice-panel-note">
          <Check size={14} /> {channel === 'voice' ? 'This places a real phone call. The outcome and transcript are added to the case.' : 'Recorded on the append-only timeline; nothing is sent on this channel yet.'}
        </span>
      </aside>
    </div>
  );
}
