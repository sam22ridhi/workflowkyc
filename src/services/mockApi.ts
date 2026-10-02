export type OnboardingStage = 'business' | 'authorization' | 'documents' | 'verification' | 'review';

export interface MockOnboarding {
  id: string;
  businessName: string;
  stage: OnboardingStage;
  status: 'draft' | 'under_review' | 'attention';
}

export interface ComplianceFinding {
  code: 'address_mismatch';
  title: string;
  explanation: string;
  confidence: number;
  evidence: string[];
}

const onboarding: MockOnboarding = {
  id: 'KYB-20481',
  businessName: 'ABC Enterprises Private Limited',
  stage: 'documents',
  status: 'attention',
};

export async function createOnboarding(businessName: string): Promise<MockOnboarding> {
  return { ...onboarding, businessName, stage: 'business', status: 'draft' };
}

export async function getOnboarding(): Promise<MockOnboarding> {
  return onboarding;
}

export async function verifyOnboarding(): Promise<ComplianceFinding> {
  return {
    code: 'address_mismatch',
    title: 'Address mismatch',
    explanation: 'The registered address differs between the merchant application and GST certificate.',
    confidence: 94,
    evidence: ['Application: 12 MG Road, Mumbai', 'GST Certificate: 12 Mahatma Gandhi Road, Mumbai'],
  };
}

export async function requestCaseAction(action: string): Promise<{ status: 'queued'; action: string }> {
  return { status: 'queued', action };
}
