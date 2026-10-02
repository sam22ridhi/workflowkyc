import { Check } from 'lucide-react';

export type MerchantScreen = 'home' | 'business' | 'authorization' | 'documents' | 'intelligence' | 'verification' | 'review' | 'submitted';
export type Stage = 'Business' | 'Authorization' | 'Documents' | 'Verification' | 'Ready';

const stages: Stage[] = ['Business', 'Authorization', 'Documents', 'Verification', 'Ready'];

interface ProgressStepperProps {
  screen: MerchantScreen;
  onNavigate: (screen: MerchantScreen) => void;
}

export function ProgressStepper({ screen, onNavigate }: ProgressStepperProps) {
  const current = screen === 'home' || screen === 'business' ? 0 : screen === 'authorization' ? 1 : screen === 'documents' || screen === 'intelligence' ? 2 : screen === 'verification' ? 3 : 4;
  const destinations: MerchantScreen[] = ['business', 'authorization', 'documents', 'verification', 'review'];
  return <div className="progress-rail merchant-progress">{stages.map((item, index) => <button key={item} onClick={() => index <= current && onNavigate(destinations[index])} className={`progress-step ${index <= current ? 'progress-complete' : ''} ${index === current ? 'progress-current' : ''}`}><span>{index < current ? <Check size={14} /> : index + 1}</span><strong>{item}</strong></button>)}</div>;
}
