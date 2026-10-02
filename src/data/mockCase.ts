import type { MerchantCase } from '@/types/case';

export const seedCase: MerchantCase = {
  id: 'KYB-20814',
  merchantName: 'Sharma Foods',
  legalName: 'Sharma Foods Private Limited',
  cin: 'U74999MH2021PTC123456',
  gstin: '27AABCS4821Q1Z7',
  pan: 'AABCS4821Q',
  registeredAddress: '12 MG Road, Mumbai',
  status: 'needs_attention',
  completion: 72,
  lastUpdated: '12 min ago',
  documents: [
    { id: 'coi', name: 'Certificate of Incorporation', kind: 'COI', status: 'received', fieldsExtracted: 6, sourceLabel: 'COI.pdf · Page 1' },
    { id: 'pan', name: 'Company PAN', kind: 'PAN', status: 'received', fieldsExtracted: 4, sourceLabel: 'Company_PAN.pdf · Page 1' },
    { id: 'gst', name: 'GST Certificate', kind: 'GST', status: 'received', fieldsExtracted: 8, sourceLabel: 'GST_Certificate.pdf · Page 1' },
    { id: 'board', name: 'Board Resolution', kind: 'BOARD', status: 'received', fieldsExtracted: 5, sourceLabel: 'Board_Resolution.pdf · Page 2' },
    { id: 'cheque', name: 'Cancelled Cheque', kind: 'BANK', status: 'missing', fieldsExtracted: 0, sourceLabel: 'Awaiting upload' },
    { id: 'address', name: 'Address Proof', kind: 'ADDRESS', status: 'missing', fieldsExtracted: 0, sourceLabel: 'Awaiting correction' },
  ],
  findings: [{
    id: 'address-drift',
    title: 'Address mismatch',
    status: 'exception',
    confidence: 91,
    applicationValue: '12 MG Road, Mumbai',
    sourceValue: '12 Mahatma Gandhi Marg, Navi Mumbai',
    explanation: 'The registered address differs between the submitted application and GST Certificate.',
    recommendedAction: 'Request corrected address proof',
  }],
  timeline: [
    { id: 'submitted', timestamp: '09:12:04', title: 'Application submitted', detail: 'Merchant submitted onboarding details and initial documents.', tone: 'neutral' },
    { id: 'parsed', timestamp: '09:12:19', title: 'GST Certificate parsed', detail: 'AI extracted 8 fields with high confidence.', tone: 'ai' },
    { id: 'contradiction', timestamp: '09:12:26', title: 'Contradiction detected', detail: 'Address mismatch found across application and GST Certificate.', tone: 'warning' },
  ],
};

export function cloneSeedCase(): MerchantCase {
  return structuredClone(seedCase);
}
