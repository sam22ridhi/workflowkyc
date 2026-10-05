import { useState } from 'react';
import { KamWorkspaceShell, type KamSidebarTab, type Persona } from '@/components/kam/KamWorkspaceShell';
import { CaseDetailOverview } from '@/components/kam/CaseDetailOverview';
import type { MerchantCase } from '@/types/case';

interface CaseDetailScreenProps {
  caseData: MerchantCase;
  onBack: () => void;
  onSwitchRole: () => void;
  onOpenAsMerchant: (caseId: string) => void;
  persona: Persona;
  onSwitchPersona: (persona: Persona) => void;
  onAction: (action: 'request' | 'voice' | 'approve' | 'send_back' | 'compliance_approve' | 'cpv_approve' | 'cpv_retake' | 'vcip_call' | 'vcip_signoff' | 'inv_resolve' | 'inv_dismiss', channel?: string, phone?: string) => void | Promise<void>;
}

export function CaseDetailScreen({ caseData, onBack, onSwitchRole, onOpenAsMerchant, persona, onSwitchPersona, onAction }: CaseDetailScreenProps) {
  const [activeTab, setActiveTab] = useState<KamSidebarTab>('cases');

  return (
    <KamWorkspaceShell
      activeTab={activeTab}
      onSelectTab={(tab) => {
        setActiveTab(tab);
        if (tab === 'dashboard') {
          onBack();
        }
      }}
      persona={persona}
      onSwitchPersona={onSwitchPersona}
      onSwitchToMerchant={onSwitchRole}
    >
      <CaseDetailOverview
        caseData={caseData}
        onBack={onBack}
        onSwitchRole={onSwitchRole}
        onOpenAsMerchant={() => onOpenAsMerchant(caseData.parentCaseId ?? caseData.id)}
        onAction={onAction}
        isCompliancePersona={persona === 'Compliance'}
      />
    </KamWorkspaceShell>
  );
}

