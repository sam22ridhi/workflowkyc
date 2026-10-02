import { ArrowRight } from 'lucide-react';

interface NeedsAttentionPanelProps {
  onOpenCase: () => void;
}

export function NeedsAttentionPanel({ onOpenCase }: NeedsAttentionPanelProps) {
  return <aside className="attention-panel"><div className="panel-heading"><div><span className="section-label">Priority queue</span><h3>Needs your attention</h3></div><span className="attention-count">8</span></div><div className="attention-case" onClick={onOpenCase}><span className="attention-symbol">!</span><span><strong>ABC Enterprises</strong><small>Address mismatch</small></span><ArrowRight size={15} /></div><div className="attention-case"><span className="attention-symbol">!</span><span><strong>Nova Retail</strong><small>Missing bank proof</small></span><ArrowRight size={15} /></div><div className="attention-case"><span className="status-dot" /><span><strong>Zenith Technologies</strong><small>Awaiting merchant response</small></span><ArrowRight size={15} /></div><button className="text-button">View all attention items <ArrowRight size={14} /></button></aside>;
}
