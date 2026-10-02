import { Check } from 'lucide-react';

export function ActivityTimeline() {
  return <section className="case-panel activity-timeline"><div className="panel-heading"><div><span className="section-label">Live case history</span><h3>Activity timeline</h3></div><span className="agent-complete"><span className="status-dot" /> Real-time updates</span></div><div className="activity-list"><Activity time="10:42 AM">Merchant uploaded <strong>GST certificate</strong></Activity><Activity time="10:43 AM">AI extracted <strong>8 fields</strong></Activity><Activity time="10:43 AM">Compliance Agent detected <strong>address mismatch</strong></Activity><Activity time="10:45 AM">KAM opened case</Activity></div></section>;
}

function Activity({ time, children }: { time: string; children: React.ReactNode }) {
  return <div className="activity-item"><span className="activity-time-label">{time}</span><span><Check size={5} /></span><span>{children}</span></div>;
}
