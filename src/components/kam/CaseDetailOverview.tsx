import React, { useState } from 'react';
import {
  ArrowLeft,
  Check,
  ChevronRight,
  FileCheck2,
  FileText,
  AlertTriangle,
  Clock,
  Sparkles,
  Building2,
  Share2,
  ShieldCheck,
  Layers,
  FileCode,
  CheckCircle2,
  Mic,
  MessageSquare
} from 'lucide-react';
import { PdfEvidenceViewer } from '@/components/kam/PdfEvidenceViewer';
import { AutoFilledCrmForm } from '@/components/kam/AutoFilledCrmForm';
import { VoiceChasePanel } from '@/components/kam/VoiceChasePanel';
import type { MerchantCase } from '@/types/case';

export type CaseDetailTab = 'overview' | 'evidence' | 'crm-form';

interface CaseDetailOverviewProps {
  caseData: MerchantCase;
  onBack: () => void;
  onSwitchRole: () => void;
  onAction: (action: 'request' | 'voice' | 'approve') => void;
  isCompliancePersona?: boolean;
}

const eightStages = [
  { id: 1, label: 'Invited', status: 'done' },
  { id: 2, label: 'Docs Upload', status: 'done' },
  { id: 3, label: 'AI Verifying', status: 'done' },
  { id: 4, label: 'KAM Review', status: 'current' },
  { id: 5, label: 'Checker (Compliance)', status: 'upcoming' },
  { id: 6, label: 'Bank Settlement Test', status: 'upcoming' },
  { id: 7, label: 'e-Agreement Sign', status: 'upcoming' },
  { id: 8, label: 'Live Unlimited', status: 'upcoming' },
];

export function CaseDetailOverview({
  caseData,
  onBack,
  onSwitchRole,
  onAction,
  isCompliancePersona = false,
}: CaseDetailOverviewProps) {
  const [activeTab, setActiveTab] = useState<CaseDetailTab>('overview');
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const finding = caseData.findings[0];
  const isResolved = finding?.status === 'verified';

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  const handleApprove = () => {
    onAction('approve');
    showToast('Case successfully approved and forwarded to Compliance Desk.');
  };

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-7xl mx-auto w-full">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed top-5 right-5 z-50 bg-[#002970] text-white px-5 py-3 rounded-xl shadow-lg border border-[#00BAF2] flex items-center gap-3 animate-in fade-in duration-200">
          <CheckCircle2 size={18} className="text-[#00BAF2]" />
          <span className="text-xs font-bold">{toastMessage}</span>
        </div>
      )}

      {/* Breadcrumb & Back */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-xs font-bold text-slate-600 hover:text-[#002970] transition-colors"
        >
          <ArrowLeft size={14} />
          <span>Back to All Cases</span>
        </button>

        <div className="flex items-center gap-2 text-xs font-semibold text-slate-500">
          <span>Case ID:</span>
          <span className="font-mono font-bold text-[#002970] bg-[#e6f7fc] px-2 py-0.5 rounded border border-[#cfe9fc]">
            {caseData.id}
          </span>
        </div>
      </div>

      {/* Screen 2 Header: Merchant Name, Account Status, 8-Stage Tracker */}
      <div className="bg-white p-6 md:p-8 rounded-2xl border border-slate-200/80 shadow-2xs space-y-6">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-xl bg-[#002970] text-[#00BAF2] font-black text-lg flex items-center justify-center shrink-0 shadow-sm ring-2 ring-[#00BAF2]/30">
              SF
            </div>
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] font-extrabold uppercase tracking-widest text-[#00BAF2] bg-[#e6f7fc] px-2.5 py-0.5 rounded-full border border-[#cfe9fc]">
                  Corporate Account
                </span>
                {/* Account Status Pill */}
                <span className="px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-200 font-extrabold text-[11px] inline-flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                  Cap Reached · ₹50k Limit
                </span>
              </div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-[#002970] tracking-tight">
                Sharma Foods Pvt Ltd
              </h1>
              <p className="text-xs text-slate-500 font-medium mt-0.5">
                Sharma Foods Private Limited · CIN: U74999MH2021PTC123456 · Fort, Mumbai
              </p>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="flex items-center gap-2.5 self-start lg:self-center">
            <button
              onClick={() => setVoiceOpen(true)}
              className="px-3.5 py-2 rounded-xl bg-white border border-slate-200 hover:border-[#00BAF2] text-xs font-bold text-slate-700 hover:text-[#002970] transition-all shadow-2xs flex items-center gap-1.5"
            >
              <Mic size={14} className="text-[#00BAF2]" />
              <span>Voice Chase</span>
            </button>
            <button
              onClick={handleApprove}
              className="px-4 py-2 rounded-xl bg-[#002970] hover:bg-[#001b4c] text-white text-xs font-bold transition-all shadow-2xs flex items-center gap-1.5"
            >
              <Check size={14} className="text-[#00BAF2]" />
              <span>Approve &amp; Forward</span>
            </button>
          </div>
        </div>

        {/* 8-Stage Tracker */}
        <div className="pt-4 border-t border-slate-100">
          <div className="flex items-center justify-between mb-3 text-xs font-bold text-slate-700">
            <span className="text-[11px] uppercase tracking-wider text-slate-400">
              8-Stage Corporate Lifecycle
            </span>
            <span className="text-[#002970]">
              Stage 4 of 8: <strong className="text-[#00BAF2]">KAM Review Active</strong>
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
            {eightStages.map((stage) => {
              const isDone = stage.status === 'done';
              const isCurrent = stage.status === 'current';
              return (
                <div
                  key={stage.id}
                  className={`p-2.5 rounded-xl border text-center transition-all ${
                    isCurrent
                      ? 'bg-[#002970] text-white border-[#002970] shadow-xs ring-2 ring-[#00BAF2]/30'
                      : isDone
                      ? 'bg-emerald-50/60 border-emerald-200 text-emerald-900'
                      : 'bg-slate-50 border-slate-200 text-slate-400'
                  }`}
                >
                  <div className="flex items-center justify-center gap-1 mb-1">
                    {isDone ? (
                      <span className="w-4 h-4 rounded-full bg-emerald-500 text-white flex items-center justify-center text-[9px] font-bold">
                        ✓
                      </span>
                    ) : (
                      <span
                        className={`w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold ${
                          isCurrent
                            ? 'bg-[#00BAF2] text-[#002970]'
                            : 'bg-slate-200 text-slate-600'
                        }`}
                      >
                        {stage.id}
                      </span>
                    )}
                  </div>
                  <strong className="block text-[11px] truncate leading-tight">
                    {stage.label}
                  </strong>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Navigation Tabs Inside Case */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-1">
        <button
          onClick={() => setActiveTab('overview')}
          className={`px-4 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${
            activeTab === 'overview'
              ? 'bg-[#002970] text-white shadow-2xs'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          <Layers size={14} />
          <span>Overview &amp; Checklist</span>
        </button>

        <button
          onClick={() => setActiveTab('evidence')}
          className={`px-4 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${
            activeTab === 'evidence'
              ? 'bg-[#002970] text-white shadow-2xs'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          <FileText size={14} />
          <span>Interactive PDF Evidence</span>
          <span className="w-2 h-2 rounded-full bg-amber-400" />
        </button>

        <button
          onClick={() => setActiveTab('crm-form')}
          className={`px-4 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${
            activeTab === 'crm-form'
              ? 'bg-purple-900 text-white shadow-2xs'
              : 'text-purple-700 bg-purple-50 hover:bg-purple-100 border border-purple-200'
          }`}
        >
          <Sparkles size={14} className="text-purple-500" />
          <span>Auto-Filled CRM Form (Magic)</span>
          <span className="text-[10px] font-extrabold px-1.5 py-0.2 rounded bg-purple-600 text-white">
            100% Filled
          </span>
        </button>
      </div>

      {/* TAB CONTENT */}

      {/* Tab 1: Overview & Two-Column Checklist */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* AI Case Summary Alert */}
          <div className="bg-gradient-to-br from-[#e6f7fc]/60 to-white p-5 rounded-2xl border border-[#cfe9fc] shadow-2xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-start gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-[#002970] text-[#00BAF2] flex items-center justify-center shrink-0">
                <Sparkles size={18} />
              </div>
              <div>
                <strong className="block text-sm font-bold text-[#002970]">
                  Karyakarta Autonomous Assessment
                </strong>
                <p className="text-xs text-slate-600 mt-0.5 leading-relaxed font-medium">
                  {isResolved
                    ? 'All legal proofs match official sovereign records. Case is verified and checker-ready.'
                    : '1 address mismatch detected across GST Certificate and application. Re-verification flow ready.'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={() => setActiveTab('evidence')}
                className="px-3.5 py-2 rounded-lg bg-white border border-[#cfe9fc] text-xs font-bold text-[#002970] hover:bg-[#e6f7fc] transition-all"
              >
                Inspect GST Discrepancy →
              </button>
            </div>
          </div>

          {/* Checklist: Clear Two-Column Layout */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Left Column: Uploaded Documents (Green Checkmarks) */}
            <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-2xs space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <div>
                  <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">
                    Uploaded Documents (4/6)
                  </h3>
                  <p className="text-[11px] text-slate-500 font-medium">
                    Verified through Karyakarta OCR &amp; MCA registry.
                  </p>
                </div>
                <span className="w-7 h-7 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold text-xs">
                  ✓
                </span>
              </div>

              <div className="space-y-3">
                <ChecklistItem
                  title="Certificate of Incorporation"
                  subtitle="CIN: U74999MH2021PTC123456 · 6 fields extracted"
                  source="COI.pdf · MCA Registry Confirmed"
                  status="completed"
                />
                <ChecklistItem
                  title="Company PAN Card"
                  subtitle="AABCS4821Q · Verified with NSDL database"
                  source="Company_PAN.pdf · 4 fields extracted"
                  status="completed"
                />
                <ChecklistItem
                  title="GST Registration Certificate"
                  subtitle="27AABCS4821Q1Z7 · Active Regular Taxpayer"
                  source="GST_Certificate.pdf · 8 fields extracted"
                  status="completed"
                  onViewEvidence={() => setActiveTab('evidence')}
                />
                <ChecklistItem
                  title="Board Resolution & Authorization"
                  subtitle="Rajesh Kumar Sharma authorized signatory"
                  source="Board_Resolution.pdf · Page 2"
                  status="completed"
                />
              </div>
            </div>

            {/* Right Column: Missing / Action Required */}
            <div className="bg-white p-6 rounded-2xl border border-amber-200/80 bg-gradient-to-br from-white to-amber-50/20 shadow-2xs space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-amber-200/60">
                <div>
                  <h3 className="text-sm font-extrabold text-amber-900 uppercase tracking-wider">
                    Missing &amp; Action Required (2)
                  </h3>
                  <p className="text-[11px] text-amber-700/80 font-medium">
                    Pending merchant correction before Stage 5 Checker submission.
                  </p>
                </div>
                <span className="w-7 h-7 rounded-lg bg-amber-100 text-amber-700 flex items-center justify-center font-bold text-xs">
                  !
                </span>
              </div>

              <div className="space-y-3">
                <ChecklistItem
                  title="Awaiting Fresh Address Proof (Utility Bill)"
                  subtitle="GST Cert states Navi Mumbai; Application stated Mumbai."
                  source="Urgent · Merchant action required"
                  status="action-required"
                  onChase={() => setVoiceOpen(true)}
                />
                <ChecklistItem
                  title="Cancelled Cheque / Attested Bank Statement"
                  subtitle="Pre-printed business name & IFSC required for settlements."
                  source="Bank proof pending upload"
                  status="action-required"
                  onChase={() => setVoiceOpen(true)}
                />
              </div>

              {/* One-click voice chase nudge */}
              <div className="p-4 rounded-xl bg-amber-100/60 border border-amber-200/90 text-xs flex items-center justify-between gap-3 mt-4">
                <div className="flex items-center gap-2.5">
                  <Mic size={16} className="text-amber-800 shrink-0" />
                  <span className="font-semibold text-amber-900 leading-snug">
                    Send automated Hindi voice reminder for missing documents.
                  </span>
                </div>
                <button
                  onClick={() => setVoiceOpen(true)}
                  className="px-3 py-1.5 bg-[#002970] text-[#00BAF2] hover:bg-[#001b4c] text-xs font-bold rounded-lg transition-all shrink-0"
                >
                  Voice Chase Now
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Interactive PDF & Entity Viewer */}
      {activeTab === 'evidence' && <PdfEvidenceViewer />}

      {/* Tab 3: Auto-Filled CRM Form (The Core Magic Screen) */}
      {activeTab === 'crm-form' && (
        <AutoFilledCrmForm
          caseData={caseData}
          onSubmitToCompliance={() => {
            handleApprove();
          }}
          onEditOverride={() => {
            showToast('Override mode activated. You can modify pre-filled fields.');
          }}
        />
      )}

      {/* Voice Chase Panel Drawer */}
      {voiceOpen && (
        <VoiceChasePanel
          merchantName={caseData.merchantName}
          onClose={() => setVoiceOpen(false)}
          onSend={() => {
            setVoiceOpen(false);
            onAction('voice');
            showToast('Voice Chase initiated! Hindi voice call queued for merchant.');
          }}
        />
      )}
    </div>
  );
}

function ChecklistItem({
  title,
  subtitle,
  source,
  status,
  onViewEvidence,
  onChase,
}: {
  title: string;
  subtitle: string;
  source: string;
  status: 'completed' | 'action-required';
  onViewEvidence?: () => void;
  onChase?: () => void;
}) {
  const isComplete = status === 'completed';

  return (
    <div
      className={`p-3.5 rounded-xl border transition-all flex items-start justify-between gap-3 ${
        isComplete
          ? 'bg-slate-50/50 border-slate-200 hover:border-slate-300'
          : 'bg-white border-amber-200 shadow-2xs hover:border-amber-300'
      }`}
    >
      <div className="flex items-start gap-3">
        <div
          className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5 text-xs font-bold ${
            isComplete
              ? 'bg-emerald-100 text-emerald-700'
              : 'bg-amber-100 text-amber-700'
          }`}
        >
          {isComplete ? '✓' : '!'}
        </div>
        <div>
          <strong className="block text-xs font-bold text-slate-900 leading-tight">
            {title}
          </strong>
          <p className="text-[11px] text-slate-500 mt-0.5 leading-snug">{subtitle}</p>
          <span className="block text-[10px] font-mono text-slate-400 mt-1">
            {source}
          </span>
        </div>
      </div>

      <div className="shrink-0 flex items-center gap-1.5 self-center">
        {onViewEvidence && (
          <button
            onClick={onViewEvidence}
            className="px-2.5 py-1 text-[11px] font-bold text-[#002970] bg-[#e6f7fc] hover:bg-[#d6f2fa] rounded-lg border border-[#cfe9fc] transition-colors"
          >
            Evidence →
          </button>
        )}
        {onChase && (
          <button
            onClick={onChase}
            className="px-2.5 py-1 text-[11px] font-bold text-amber-900 bg-amber-100 hover:bg-amber-200 rounded-lg border border-amber-300 transition-colors"
          >
            Chase
          </button>
        )}
      </div>
    </div>
  );
}
