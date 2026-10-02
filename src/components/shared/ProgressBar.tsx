interface ProgressBarProps {
  value: number;
  label?: string;
}

export function ProgressBar({ value, label = 'Application completion' }: ProgressBarProps) {
  return <div className="progress-meter"><div className="progress-meter-head"><span>{label}</span><strong>{value}%</strong></div><div className="progress-meter-track"><span style={{ width: `${value}%` }} /></div></div>;
}
