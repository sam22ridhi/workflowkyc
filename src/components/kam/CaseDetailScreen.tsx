import React, { useState } from 'react';
import { KamWorkspaceShell, type KamSidebarTab, type Persona } from '@/components/kam/KamWorkspaceShell';
import { CaseDetailOverview } from '@/components/kam/CaseDetailOverview';
import type { MerchantCase } from '@/types/case';

interface CaseDetailScreenProps {
  caseData: MerchantCase;
  onBack: () => void;
  onSwitchRole: () => void;
  onAction: (action: 'request' | 'voice' | 'approve') => void;
}

export function CaseDetailScreen({ caseData, onBack, onSwitchRole, onAction }: CaseDetailScreenProps) {
  const [activeTab, setActiveTab] = useState<KamSidebarTab>('cases');
  const [persona, setPersona] = useState<Persona>('KAM');

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
      onSwitchPersona={setPersona}
      onSwitchToMerchant={onSwitchRole}
    >
      <CaseDetailOverview
        caseData={caseData}
        onBack={onBack}
        onSwitchRole={onSwitchRole}
        onAction={onAction}
        isCompliancePersona={persona === 'Compliance'}
      />
    </KamWorkspaceShell>
  );
}

