import { useEffect, useState } from 'react';
import { Check, Lock, Mic, Send, X } from 'lucide-react';
import { api, type VoiceChaseContext } from '@/services/api';

export type ChaseChannel = 'voice' | 'whatsapp' | 'email';

interface VoiceChasePanelProps {
  caseId?: string;
  merchantName: string;
  /** Fallback request text when the agent context can't be loaded. */
  request?: string;
  onClose: () => void;
  onSend: (channel: ChaseChannel) => void;
}

const split = (list?: string) => (list && list !== 'none' && list !== 'कोई नहीं' ? list.split(/;\s*/).map((x) => x.replace(/^\d+\.\s*/, '')) : []);

export function VoiceChasePanel({ caseId, merchantName, request = 'Missing documents', onClose, onSend }: VoiceChasePanelProps) {
  const [channel, setChannel] = useState<ChaseChannel>('voice');
  const [ctx, setCtx] = useState<VoiceChaseContext | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!caseId) return;
    api<VoiceChaseContext>(`/api/cases/${caseId}/voice-chase/context`).then(setCtx, (e) => setError(e instanceof Error ? e.message : String(e)));
  }, [caseId]);

  const docs = split(ctx?.agent_variables.documents_needed_en);
  const nothing = ctx && !ctx.should_call;

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="voice-chase-panel" onClick={(event) => event.stopPropagation()}>
        <div className="voice-panel-head">
          <div>
            <span className="eyebrow-label ai-label"><Mic size={14} /> KARYAKARTA Voice · Sarvam agent</span>
            <h2>Chase {merchantName} without leaving the case.</h2>
          </div>
          <button className="drawer-close" onClick={onClose}><X size={18} /></button>
        </div>

        <p className="voice-panel-copy">
          {ctx
            ? nothing
              ? 'Nothing on this case needs the merchant right now, so there is nothing to chase.'
              : `The agent will call ${ctx.agent_variables.contact_name} and raise ${ctx.agent_variables.issue_count} item(s) the merchant can fix.`
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

        <button className="button button-blue button-full" disabled={!!nothing} onClick={() => onSend(channel)}>
          <Send size={16} /> Send {channel === 'voice' ? 'voice chase' : `${channel} request`}
        </button>
        <span className="voice-panel-note"><Check size={14} /> Sending is recorded on the append-only timeline, with the call outcome.</span>
      </aside>
    </div>
  );
}
