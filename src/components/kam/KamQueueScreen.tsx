import { useState } from 'react';
import { KamWorkspaceShell, type KamSidebarTab, type Persona } from '@/components/kam/KamWorkspaceShell';
import { KamDashboardView } from '@/components/kam/KamDashboardView';
import { ComplianceDashboardView } from '@/components/kam/ComplianceDashboardView';

interface KamQueueScreenProps {
  onOpenCase: (caseId: string) => void;
  onOpenAsMerchant: (caseId: string) => void;
  onSwitchRole: () => void;
  persona: Persona;
  onSwitchPersona: (persona: Persona) => void;
}

export function KamQueueScreen({ onOpenCase, onOpenAsMerchant, onSwitchRole, persona, onSwitchPersona }: KamQueueScreenProps) {
  const [activeTab, setActiveTab] = useState<KamSidebarTab>('dashboard');

  return (
    <KamWorkspaceShell
      activeTab={activeTab}
      onSelectTab={setActiveTab}
      persona={persona}
      onSwitchPersona={onSwitchPersona}
      onSwitchToMerchant={onSwitchRole}
    >
      {persona === 'Compliance' && activeTab === 'dashboard' ? (
        <ComplianceDashboardView onOpenCase={onOpenCase} onOpenAsMerchant={onOpenAsMerchant} />
      ) : (
        // key: remounting applies the tab's filter (All Cases = everything, Risk Alerts = urgent / escalated)
        <KamDashboardView key={activeTab} onOpenCase={onOpenCase} onOpenAsMerchant={onOpenAsMerchant} initialFilter={activeTab === 'risk' ? 'urgent' : 'all'} />
      )}
    </KamWorkspaceShell>
  );
}
