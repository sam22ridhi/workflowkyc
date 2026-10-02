import { ArrowRight, CircleHelp, Network } from 'lucide-react';

interface ProductHeaderProps {
  role: 'merchant' | 'kam';
  onSwitchRole: () => void;
}

export function ProductHeader({ role, onSwitchRole }: ProductHeaderProps) {
  return <header className="product-header"><button className="product-brand" onClick={onSwitchRole}><span className="product-brand-mark"><Network size={17} /></span><span>KARYAKARTA</span></button><div className="header-context"><span className="header-context-label">{role === 'merchant' ? 'Merchant workspace' : 'KAM cockpit'}</span><span className="header-context-divider" /><span>{role === 'merchant' ? 'Sharma Foods' : 'Acme Payments'}</span></div><div className="header-actions"><button className="header-help"><CircleHelp size={15} /> Help</button><button className="role-switch" onClick={onSwitchRole}>Switch to {role === 'merchant' ? 'KAM' : 'Merchant'} <ArrowRight size={14} /></button><span className="header-avatar">{role === 'merchant' ? 'SF' : 'AP'}</span></div></header>;
}
