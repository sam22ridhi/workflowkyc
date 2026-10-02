import { useState } from 'react';
import { Check, Mic, Send, Volume2, X } from 'lucide-react';

interface VoiceChasePanelProps {
  merchantName: string;
  onClose: () => void;
  onSend: () => void;
}

export function VoiceChasePanel({ merchantName, onClose, onSend }: VoiceChasePanelProps) {
  const [channel, setChannel] = useState<'voice' | 'whatsapp' | 'email'>('voice');
  const [playing, setPlaying] = useState(false);
  return <div className="drawer-backdrop" onClick={onClose}><aside className="voice-chase-panel" onClick={(event) => event.stopPropagation()}><div className="voice-panel-head"><div><span className="eyebrow-label ai-label"><Mic size={14} /> KARYAKARTA Voice</span><h2>Chase {merchantName} without leaving the case.</h2></div><button className="drawer-close" onClick={onClose}><X size={18} /></button></div><p className="voice-panel-copy">The agent has resolved the case context and drafted the request for address proof.</p><div className="voice-script"><span className="script-label">Hindi voice script</span><p>“नमस्ते, मैं पेटीएम कार्यकर्ता बोल रहा हूँ। आपके जीएसटी और आवेदन के पते में अंतर है। कृपया सही पते का प्रमाण साझा करें।”</p><button className={`audio-control ${playing ? 'audio-control-playing' : ''}`} onClick={() => setPlaying((value) => !value)}><span>{playing ? <Volume2 size={16} /> : <Mic size={16} />}</span><div className="audio-wave">{Array.from({ length: 20 }, (_, index) => <i key={index} style={{ height: `${10 + ((index * 7) % 19)}px` }} />)}</div><small>{playing ? 'Playing preview' : 'Play preview'}</small></button></div><div className="voice-request-summary"><span><small>REQUEST</small><strong>Corrected address proof</strong></span><span><small>CHANNEL</small><div className="channel-buttons">{(['voice', 'whatsapp', 'email'] as const).map((item) => <button key={item} className={channel === item ? 'selected' : ''} onClick={() => setChannel(item)}>{item === 'whatsapp' ? 'WhatsApp' : item[0].toUpperCase() + item.slice(1)}</button>)}</div></span></div><button className="button button-blue button-full" onClick={onSend}><Send size={16} /> Send {channel === 'voice' ? 'voice chase' : `${channel} request`}</button><span className="voice-panel-note"><Check size={14} /> Sending adds the action to the append-only timeline.</span></aside></div>;
}
