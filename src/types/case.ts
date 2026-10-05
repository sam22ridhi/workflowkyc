export type CaseStatus = 'needs_attention' | 'awaiting_merchant' | 'ready_for_review';
export type DocumentStatus = 'received' | 'missing' | 'processing';
export type FindingStatus = 'exception' | 'verified';

export interface CaseDocument {
  id: string;
  name: string;
  kind: string;
  status: DocumentStatus;
  fieldsExtracted: number;
  sourceLabel: string;
}

export interface CaseFinding {
  id: string;
  title: string;
  status: FindingStatus;
  confidence: number;
  applicationValue: string;
  sourceValue: string;
  explanation: string;
  recommendedAction: string;
}

export interface TimelineEvent {
  id: string;
  timestamp: string;
  title: string;
  detail: string;
  tone: 'neutral' | 'ai' | 'warning' | 'success';
}

export interface LiveStage { id: number; label: string; status: 'done' | 'current' | 'upcoming'; }

export interface MerchantCase {
  id: string;
  merchantName: string;
  legalName: string;
  cin: string;
  gstin: string;
  pan: string;
  registeredAddress: string;
  status: CaseStatus;
  completion: number;
  documents: CaseDocument[];
  findings: CaseFinding[];
  timeline: TimelineEvent[];
  lastUpdated: string;
  // live backend fields (absent on the offline sample)
  entityType?: string;
  contactName?: string | null;
  contactPhone?: string | null;
  accountStatus?: string;
  stage?: number;
  stages?: LiveStage[];
  route?: 'AUTO' | 'ASK' | 'ESCALATE' | null;
  summary?: string | null;
  graphStatus?: 'none' | 'building' | 'ready' | 'failed';
  checks?: import('@/services/api').CaseCheck[];
  uploaded?: import('@/services/api').ChecklistEntry[];
  missing?: import('@/services/api').ChecklistEntry[];
  voiceCalls?: import('@/services/api').VoiceCallRecord[];
  kind?: 'merchant' | 'investigation';
  parentCaseId?: string | null;
  cpv?: import('@/services/api').CpvView | null;
  vcip?: import('@/services/api').VcipView | null;
}
