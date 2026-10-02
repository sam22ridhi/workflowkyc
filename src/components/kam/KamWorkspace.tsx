import { Bell, Building2, ChevronDown, CircleHelp, LayoutDashboard, Plus, Settings, ShieldCheck } from 'lucide-react';
import { Brand } from '@/components/shared/Brand';

type ActiveStep = 'overview' | 'customer' | 'kyc';

interface KamWorkspaceProps {
  children: React.ReactNode;
  activeStep: ActiveStep;
  onSwitchRole: () => void;
}

export function KamWorkspace({ children, activeStep, onSwitchRole }: KamWorkspaceProps) {
  const steps = ['Overview', 'Customer & authority', 'Accounts', 'KYC & documents', 'Review & approval', 'Signing & activation'];
  return <div className="kam-workspace"><aside className="kam-sidebar"><div className="kam-sidebar-brand"><Brand /></div><button className="new-onboarding-button" onClick={onSwitchRole}><Plus size={15} /> New onboarding</button><div className="kam-nav-group"><button className="kam-nav-link"><LayoutDashboard size={16} /> Dashboard</button><button className="kam-nav-link selected"><Building2 size={16} /> Onboarding cases</button><button className="kam-nav-link"><Bell size={16} /> Notifications <span>9+</span></button></div><div className="kam-sidebar-bottom"><button className="kam-nav-link"><CircleHelp size={16} /> Help center</button><button className="kam-nav-link"><Settings size={16} /> Settings</button><button className="kam-user" onClick={onSwitchRole}><span className="kam-user-avatar">AP</span><span><strong>Alex Parker</strong><small>KAM · Acme Payments</small></span><ChevronDown size={14} /></button></div></aside><div className="kam-workspace-main"><header className="kam-workspace-header"><div className="kam-crumb"><span className="kam-product-mark"><ShieldCheck size={16} /></span><strong>Acme Payments</strong><span>/</span><span>Merchant onboarding</span></div><div className="kam-header-actions"><button className="kam-icon-button"><Bell size={17} /><i /></button><button className="kam-profile"><span className="kam-user-avatar">AP</span><span><strong>Alex Parker</strong><small>KAM</small></span><ChevronDown size={14} /></button><button className="kam-mobile-switch" onClick={onSwitchRole}>Merchant view</button></div></header><div className="kam-client-banner"><div className="kam-client-title"><span className="kam-client-icon"><Building2 size={18} /></span><div><h1>Client Onboarding</h1><p>Corporate merchant lifecycle · Acme Payments workspace</p></div></div><span className="kam-client-status">Live queue</span></div><nav className="kam-stepper" aria-label="Onboarding steps">{steps.map((step, index) => { const isActive = (activeStep === 'overview' && index === 0) || (activeStep === 'customer' && index === 1) || (activeStep === 'kyc' && index === 3); const isComplete = index < (activeStep === 'overview' ? 1 : activeStep === 'customer' ? 2 : 4); return <span className={`${isActive ? 'active' : ''} ${isComplete ? 'complete' : ''}`} key={step}><b>{isComplete ? '✓' : index + 1}</b>{step}</span>; })}</nav>{children}</div></div>;
}
