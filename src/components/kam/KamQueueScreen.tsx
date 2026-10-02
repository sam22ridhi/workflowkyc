import React, { useState } from 'react';
import { KamWorkspaceShell, type KamSidebarTab, type Persona } from '@/components/kam/KamWorkspaceShell';
import { KamDashboardView } from '@/components/kam/KamDashboardView';

interface KamQueueScreenProps {
  onOpenCase: (caseId: string) => void;
  onSwitchRole: () => void;
}

export function KamQueueScreen({ onOpenCase, onSwitchRole }: KamQueueScreenProps) {
  const [activeTab, setActiveTab] = useState<KamSidebarTab>('dashboard');
  const [persona, setPersona] = useState<Persona>('KAM');

  return (
    <KamWorkspaceShell
      activeTab={activeTab}
      onSelectTab={(tab) => {
        setActiveTab(tab);
        if (tab === 'cases') {
          // If all cases is chosen, stay on dashboard or open case
        }
      }}
      persona={persona}
      onSwitchPersona={setPersona}
      onSwitchToMerchant={onSwitchRole}
    >
      <KamDashboardView onOpenCase={onOpenCase} />
    </KamWorkspaceShell>
  );
}

