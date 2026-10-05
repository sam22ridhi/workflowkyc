import { useMemo, useState } from 'react';
import {
  ArrowLeft,
  Check,
  Sparkles,
  Layers,
  FileText,
  CheckCircle2,
  Mic,
  AlertTriangle,
  CircleCheck,
  CircleX,
  CircleMinus,
  FileSearch,
  Undo2,
} from 'lucide-react';
import { Activity, RotateCcw, Trash2 } from 'lucide-react';
import { PdfEvidenceViewer, type EvidenceFocus } from '@/components/kam/PdfEvidenceViewer';
import { AutoFilledCrmForm } from '@/components/kam/AutoFilledCrmForm';
import { AskCaseCard } from '@/components/kam/AskCaseCard';
import { SettlementsTab } from '@/components/kam/SettlementsTab';
import { VoiceCallsCard } from '@/components/kam/VoiceCallsCard';
import { DrishtiCard } from '@/components/kam/DrishtiCard';
import { VcipCard } from '@/components/kam/VcipCard';
import { VoiceChasePanel, type ChaseChannel } from '@/components/kam/VoiceChasePanel';
import type { MerchantCase } from '@/types/case';
import { deleteDocument, resetDemoCase, useLiveResource, type CaseCheck, type CrmForm } from '@/services/api';

export type CaseDetailTab = 'overview' | 'evidence' | 'crm-form' | 'settlements';
type Action = 'request' | 'voice' | 'approve' | 'send_back' | 'compliance_approve' | 'cpv_approve' | 'cpv_retake' | 'vcip_call' | 'vcip_signoff' | 'inv_resolve' | 'inv_dismiss';

interface CaseDetailOverviewProps {
  caseData: MerchantCase;
  onBack: () => void;
  onSwitchRole: () => void;
  onOpenAsMerchant?: () => void;
  onAction: (action: Action, channel?: string, phone?: string) => void | Promise<void>;
  isCompliancePersona?: boolean;
}

const FALLBACK_STAGES = ['Invited', 'Docs Upload', 'AI Verifying', 'KAM Review', 'Checker (Compliance)', 'Contact Point Verification', 'V-CIP Sign-off', 'Bank Settlement Test', 'e-Agreement Sign', 'Live Unlimited']
  .map((label, i) => ({ id: i + 1, label, status: (i < 3 ? 'done' : i === 3 ? 'current' : 'upcoming') as 'done' | 'current' | 'upcoming' }));

const ROUTE_CHIP = {
  AUTO: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  ASK: 'bg-amber-50 text-amber-800 border-amber-200',
  ESCALATE: 'bg-rose-50 text-rose-800 border-rose-200',
} as const;

const ROUTE_TEXT = {
  AUTO: 'AUTO · one-click approval',
  ASK: 'ASK · the merchant can fix this',
  ESCALATE: 'ESCALATE · needs human judgement',
} as const;

export function CaseDetailOverview({ caseData, onBack, onAction, onOpenAsMerchant, isCompliancePersona = false }: CaseDetailOverviewProps) {
  const isInvestigation = caseData.kind === 'investigation';
  const showSettlements = isInvestigation || (caseData.stage ?? 0) >= 10;       // post-onboarding: a live merchant, or a settlement investigation
  const [activeTab, setActiveTab] = useState<CaseDetailTab>(isInvestigation ? 'settlements' : 'overview');
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [toast, setToast] = useState<{ text: string; error?: boolean } | null>(null);
  const [evidenceFocus, setEvidenceFocus] = useState<EvidenceFocus | null>(null);
  const crm = useLiveResource<CrmForm>(caseData.id, `/api/cases/${caseData.id}/crm-form`);
  const crmSummary = crm.data?.summary;

  const stages = caseData.stages ?? FALLBACK_STAGES;
  const current = stages.find((s) => s.status === 'current') ?? stages[3];
  const checks: CaseCheck[] = caseData.checks ?? [];
  const failing = checks.filter((c) => c.status === 'fail' || c.status === 'warn');
  const askIssues = failing.filter((c) => c.action !== 'escalate');
  const uploaded = caseData.uploaded ?? [];
  const missing = caseData.missing ?? [];
  const route = caseData.route ?? null;
  const initials = caseData.merchantName.split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase();
  const chaseRequest = askIssues[0]?.label ?? missing[0]?.label ?? 'Missing documents';

  const canEditFiles = !isCompliancePersona && !isInvestigation && (caseData.stage ?? 0) <= 4;     // files lock once the case is with Compliance

  const showToast = (text: string, error = false) => {
    setToast({ text, error });
    window.setTimeout(() => setToast(null), 4500);
  };

  const run = async (action: Action, success: string, channel?: string, phone?: string) => {
    try {
      await onAction(action, channel, phone);
      showToast(success);
    } catch (e) {
      showToast(`Action failed: ${e instanceof Error ? e.message : String(e)}`, true);
    }
  };

  const removeFile = async (docId: string, label: string) => {
    if (!window.confirm(`Delete ${label} from this case? The file is removed, the checks are re-run on what is left, and its copy in the merchant memory is removed.`)) return;
    try {
      const r = await deleteDocument(docId);
      showToast(`Deleted ${r.deleted}. ${r.outcome}`);
      void crm.reload();
    } catch (e) {
      showToast(`Could not delete: ${e instanceof Error ? e.message : String(e)}`, true);
    }
  };

  const resetCase = async () => {
    if (!window.confirm('Demo reset: remove every file, check, call and verification from this case and clear its merchant memory, so the demo can be run again?')) return;
    try {
      await resetDemoCase(caseData.id);
      setActiveTab('overview');
      showToast('Case reset to its starting state.');
      void crm.reload();
    } catch (e) {
      showToast(`Could not reset: ${e instanceof Error ? e.message : String(e)}`, true);
    }
  };

  const handleApprove = () => {
    if (route === 'ESCALATE' && !window.confirm('This case has issues that need human judgement. Submit it to Compliance anyway?')) return;
    void run('approve', 'Submitted to the Compliance (Checker) desk.');
  };

  const openEvidence = (docId: string | null, field?: string | null) => {
    if (!docId) return;
    setEvidenceFocus({ docId, field: field ?? '' });
    setActiveTab('evidence');
  };

  const firstEvidence = useMemo(() => {
    for (const c of failing) {
      const e = c.evidence.find((x) => x.doc_id);
      if (e) return { check: c, ev: e };
    }
    return null;
  }, [failing]);

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-7xl mx-auto w-full">
      {toast && (
        <div className={`fixed top-5 right-5 z-50 text-white px-5 py-3 rounded-xl shadow-lg border flex items-center gap-3 ${toast.error ? 'bg-rose-700 border-rose-300' : 'bg-[#002970] border-[#00BAF2]'}`}>
          <CheckCircle2 size={18} className={toast.error ? 'text-rose-200' : 'text-[#00BAF2]'} />
          <span className="text-xs font-bold">{toast.text}</span>
        </div>
      )}

      <div className="flex items-center justify-between">
        <button onClick={onBack} className="flex items-center gap-2 text-xs font-bold text-slate-600 hover:text-[#002970] transition-colors">
          <ArrowLeft size={14} />
          <span>Back to All Cases</span>
        </button>
        <div className="flex items-center gap-2 text-xs font-semibold text-slate-500">
          {onOpenAsMerchant && (
            <button onClick={onOpenAsMerchant} className="px-3 py-1.5 rounded-lg bg-[#e6f7fc] border border-[#cfe9fc] text-[#002970] font-bold hover:bg-[#d6f2fa] mr-2">
              View as merchant
            </button>
          )}
          {canEditFiles && (
            <button onClick={() => void resetCase()} className="px-3 py-1.5 rounded-lg bg-white border border-dashed border-slate-300 text-slate-600 font-bold hover:bg-slate-50 mr-2 inline-flex items-center gap-1.5" title="Demo only: put this case back to its starting state">
              <RotateCcw size={12} /> Reset demo case
            </button>
          )}
          <span>Case ID:</span>
          <span className="font-mono font-bold text-[#002970] bg-[#e6f7fc] px-2 py-0.5 rounded border border-[#cfe9fc]">{caseData.id}</span>
        </div>
      </div>

      {/* Header: merchant, account status, 8-stage tracker */}
      <div className="bg-white p-6 md:p-8 rounded-2xl border border-slate-200/80 shadow-2xs space-y-6">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-xl bg-[#002970] text-[#00BAF2] font-black text-lg flex items-center justify-center shrink-0 shadow-sm ring-2 ring-[#00BAF2]/30">{initials}</div>
            <div>
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <span className="text-[10px] font-extrabold uppercase tracking-widest text-[#00BAF2] bg-[#e6f7fc] px-2.5 py-0.5 rounded-full border border-[#cfe9fc]">Corporate Account</span>
                <span className="px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-200 font-extrabold text-[11px] inline-flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                  {caseData.accountStatus ?? 'Cap Reached · ₹50k Limit'}
                </span>
                {route && <span className={`px-2.5 py-0.5 rounded-full border font-extrabold text-[11px] ${ROUTE_CHIP[route]}`}>{ROUTE_TEXT[route]}</span>}
              </div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-[#002970] tracking-tight">{caseData.merchantName}</h1>
              <p className="text-xs text-slate-500 font-medium mt-0.5">
                {caseData.legalName}{caseData.cin ? ` · CIN: ${caseData.cin}` : ''}{caseData.entityType ? ` · ${caseData.entityType}` : ''}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5 self-start lg:self-center">
            <button onClick={() => setVoiceOpen(true)} className="px-3.5 py-2 rounded-xl bg-white border border-slate-200 hover:border-[#00BAF2] text-xs font-bold text-slate-700 hover:text-[#002970] transition-all shadow-2xs flex items-center gap-1.5">
              <Mic size={14} className="text-[#00BAF2]" />
              <span>Voice Chase</span>
            </button>
            {isInvestigation ? (
              !isCompliancePersona && caseData.status === 'needs_attention' && (
                <>
                  <button onClick={() => void run('inv_dismiss', 'Investigation dismissed as a false positive.')} className="px-3.5 py-2 rounded-xl bg-white border border-slate-300 text-slate-800 hover:bg-slate-50 text-xs font-bold transition-all">Dismiss (false positive)</button>
                  <button onClick={() => void run('inv_resolve', 'Investigation resolved.')} className="px-4 py-2 rounded-xl bg-[#002970] hover:bg-[#001b4c] text-white text-xs font-bold transition-all shadow-2xs flex items-center gap-1.5"><Check size={14} className="text-[#00BAF2]" /><span>Resolve</span></button>
                </>
              )
            ) : (showSettlements ? null : isCompliancePersona) ? (
              <>
                <button onClick={() => void run('send_back', 'Sent back to the KAM.')} className="px-3.5 py-2 rounded-xl bg-white border border-amber-300 text-amber-900 hover:bg-amber-50 text-xs font-bold transition-all shadow-2xs flex items-center gap-1.5">
                  <Undo2 size={14} /> <span>Send back</span>
                </button>
                <button onClick={() => void run('compliance_approve', 'Compliance approved. Drishti opens the shop verification and the merchant receives a secure link.')} className="px-4 py-2 rounded-xl bg-[#002970] hover:bg-[#001b4c] text-white text-xs font-bold transition-all shadow-2xs flex items-center gap-1.5">
                  <Check size={14} className="text-[#00BAF2]" /> <span>Approve (Compliance)</span>
                </button>
              </>
            ) : showSettlements ? null : (
              <button onClick={handleApprove} className="px-4 py-2 rounded-xl bg-[#002970] hover:bg-[#001b4c] text-white text-xs font-bold transition-all shadow-2xs flex items-center gap-1.5">
                <Check size={14} className="text-[#00BAF2]" />
                <span>Approve &amp; Forward</span>
              </button>
            )}
          </div>
        </div>

        <div className="pt-4 border-t border-slate-100">
          <div className="flex items-center justify-between mb-3 text-xs font-bold text-slate-700">
            <span className="text-[11px] uppercase tracking-wider text-slate-400">{stages.length}-Stage Corporate Lifecycle</span>
            <span className="text-[#002970]">Stage {current.id} of {stages.length}: <strong className="text-[#00BAF2]">{current.label}</strong></span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-5 lg:grid-cols-10 gap-2">
            {stages.map((stage) => {
              const isDone = stage.status === 'done';
              const isCurrent = stage.status === 'current';
              return (
                <div key={stage.id} className={`p-2.5 rounded-xl border text-center transition-all ${isCurrent ? 'bg-[#002970] text-white border-[#002970] shadow-xs ring-2 ring-[#00BAF2]/30' : isDone ? 'bg-emerald-50/60 border-emerald-200 text-emerald-900' : 'bg-slate-50 border-slate-200 text-slate-400'}`}>
                  <div className="flex items-center justify-center gap-1 mb-1">
                    {isDone ? (
                      <span className="w-4 h-4 rounded-full bg-emerald-500 text-white flex items-center justify-center text-[9px] font-bold">✓</span>
                    ) : (
                      <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold ${isCurrent ? 'bg-[#00BAF2] text-[#002970]' : 'bg-slate-200 text-slate-600'}`}>{stage.id}</span>
                    )}
                  </div>
                  <strong className="block text-[11px] truncate leading-tight">{stage.label}</strong>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-1">
        <button onClick={() => setActiveTab('overview')} className={`px-4 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${activeTab === 'overview' ? 'bg-[#002970] text-white shadow-2xs' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'}`}>
          <Layers size={14} /><span>Overview &amp; Checklist</span>
        </button>
        {!isInvestigation && (
          <>
        <button onClick={() => setActiveTab('evidence')} className={`px-4 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${activeTab === 'evidence' ? 'bg-[#002970] text-white shadow-2xs' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'}`}>
          <FileText size={14} /><span>Interactive PDF Evidence</span>
          {failing.length > 0 && <span className="w-2 h-2 rounded-full bg-amber-400" />}
        </button>
        <button onClick={() => setActiveTab('crm-form')} className={`px-4 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${activeTab === 'crm-form' ? 'bg-[#002970] text-white shadow-2xs' : 'text-[#002970] bg-[#e6f7fc] hover:bg-[#d6f2fa] border border-[#cfe9fc]'}`}>
          <Sparkles size={14} className="text-[#0099cc]" /><span>MAF (Merchant Application Form)</span>
          <span className="text-[10px] font-extrabold px-1.5 py-0.2 rounded bg-[#00BAF2] text-[#002970]">{crmSummary ? `${crmSummary.fill_percent}% Filled` : '…'}</span>
        </button>
          </>
        )}
        {showSettlements && (
          <button onClick={() => setActiveTab('settlements')} className={`px-4 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${activeTab === 'settlements' ? 'bg-[#002970] text-white shadow-2xs' : 'text-slate-600 hover:bg-slate-100'}`}>
            <Activity size={14} className={activeTab === 'settlements' ? 'text-[#00BAF2]' : 'text-slate-400'} /><span>Settlements</span>
            {isInvestigation && <span className="w-2 h-2 rounded-full bg-rose-500" />}
          </button>
        )}
      </div>

      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* Assessment */}
          <div className="bg-gradient-to-br from-[#e6f7fc]/60 to-white p-5 rounded-2xl border border-[#cfe9fc] shadow-2xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-start gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-[#002970] text-[#00BAF2] flex items-center justify-center shrink-0"><Sparkles size={18} /></div>
              <div>
                <strong className="block text-sm font-bold text-[#002970]">Karyakarta Autonomous Assessment</strong>
                <p className="text-xs text-slate-600 mt-0.5 leading-relaxed font-medium">
                  {caseData.summary ?? (checks.length ? 'All applicable checks passed.' : 'Waiting for documents. The agent reads, cross-checks and summarises as soon as they arrive.')}
                </p>
              </div>
            </div>
            {firstEvidence && (
              <button onClick={() => openEvidence(firstEvidence.ev.doc_id, firstEvidence.ev.field)} className="px-3.5 py-2 rounded-lg bg-white border border-[#cfe9fc] text-xs font-bold text-[#002970] hover:bg-[#e6f7fc] transition-all shrink-0">
                Inspect first issue →
              </button>
            )}
          </div>

          {/* The 10 cross-document checks */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-2xs space-y-3">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div>
                <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">{isInvestigation ? 'Exception cards (rule-based signals)' : 'Cross-document checks'}</h3>
                <p className="text-[11px] text-slate-500 font-medium">Rule-based, repeatable. Each result lists its evidence; click to open the source.</p>
              </div>
              <span className="text-[11px] font-bold text-slate-500">{checks.filter((c) => c.status === 'pass').length}/{checks.length} passed</span>
            </div>
            {checks.length === 0 && <p className="text-xs text-slate-500">No checks yet. They run after the merchant&rsquo;s documents have been read.</p>}
            {checks.map((c) => <CheckRow key={c.id} check={c} onOpen={openEvidence} />)}
          </div>

          {/* Two-column checklist (onboarding cases only) */}
          {!isInvestigation && <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-2xs space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <div>
                  <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Uploaded Documents ({uploaded.length}/{uploaded.length + missing.length})</h3>
                  <p className="text-[11px] text-slate-500 font-medium">Read by Sarvam Document Intelligence; checked by rules.</p>
                </div>
                <span className="w-7 h-7 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold text-xs">✓</span>
              </div>
              <div className="space-y-3">
                {uploaded.length === 0 && <p className="text-xs text-slate-500">Nothing uploaded yet.</p>}
                {uploaded.map((u) => {
                  const doc = caseData.documents.find((d) => d.id === u.doc_id);
                  return (
                    <ChecklistItem
                      key={u.doc_type}
                      title={u.label}
                      subtitle={doc ? `${doc.fieldsExtracted} fields extracted` : 'Uploaded'}
                      source={doc?.sourceLabel ?? ''}
                      status="completed"
                      onViewEvidence={u.doc_id ? () => openEvidence(u.doc_id) : undefined}
                      onDelete={canEditFiles && u.doc_id ? () => void removeFile(u.doc_id as string, u.label) : undefined}
                    />
                  );
                })}
              </div>
            </div>

            <div className="bg-white p-6 rounded-2xl border border-amber-200/80 bg-gradient-to-br from-white to-amber-50/20 shadow-2xs space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-amber-200/60">
                <div>
                  <h3 className="text-sm font-extrabold text-amber-900 uppercase tracking-wider">Missing &amp; Action Required ({missing.length + askIssues.length})</h3>
                  <p className="text-[11px] text-amber-700/80 font-medium">Pending merchant correction before Stage 5 Checker submission.</p>
                </div>
                <span className="w-7 h-7 rounded-lg bg-amber-100 text-amber-700 flex items-center justify-center font-bold text-xs">!</span>
              </div>
              <div className="space-y-3">
                {missing.length + askIssues.length === 0 && <p className="text-xs text-slate-500">Nothing outstanding.</p>}
                {askIssues.map((c) => (
                  <ChecklistItem key={c.id} title={c.label} subtitle={c.detail} source="Merchant can fix this" status="action-required" onChase={() => setVoiceOpen(true)} />
                ))}
                {missing.map((m) => (
                  <ChecklistItem key={m.doc_type} title={`Awaiting ${m.label}`} subtitle="Required for this entity type." source="Document not uploaded" status="action-required" onChase={() => setVoiceOpen(true)} />
                ))}
              </div>
              {(missing.length > 0 || askIssues.length > 0) && (
                <div className="p-4 rounded-xl bg-amber-100/60 border border-amber-200/90 text-xs flex items-center justify-between gap-3 mt-4">
                  <div className="flex items-center gap-2.5">
                    <Mic size={16} className="text-amber-800 shrink-0" />
                    <span className="font-semibold text-amber-900 leading-snug">Send an automated Hindi voice reminder for the open items.</span>
                  </div>
                  <button onClick={() => setVoiceOpen(true)} className="px-3 py-1.5 bg-[#002970] text-[#00BAF2] hover:bg-[#001b4c] text-xs font-bold rounded-lg transition-all shrink-0">Voice Chase Now</button>
                </div>
              )}
            </div>
          </div>}

          {!isInvestigation && caseData.cpv && <DrishtiCard caseId={caseData.id} cpv={caseData.cpv} isCompliancePersona={isCompliancePersona} onAct={(action, success) => void run(action, success)} />}
          {!isInvestigation && caseData.vcip && (
            <VcipCard
              caseId={caseData.id}
              vcip={caseData.vcip}
              defaultPhone={caseData.vcip.contactPhone ?? caseData.contactPhone ?? ''}
              isCompliancePersona={isCompliancePersona}
              onCall={async (phone) => { await onAction('vcip_call', undefined, phone); showToast('Calling for the V-CIP pre-interview. The transcript appears here when it ends.'); }}
              onSignOff={async () => { await onAction('vcip_signoff'); showToast('V-CIP signed off. The case moves to the bank settlement test.'); }}
            />
          )}

          <AskCaseCard caseId={caseData.id} graphStatus={caseData.graphStatus ?? 'none'} onOpenSource={(docId) => openEvidence(docId)} />

          <VoiceCallsCard calls={caseData.voiceCalls ?? []} />

          {/* Timeline */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-2xs">
            <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-4">Append-only timeline</h3>
            <ol className="space-y-3 max-h-80 overflow-y-auto pr-2">
              {[...caseData.timeline].reverse().map((t) => (
                <li key={t.id} className="flex items-start gap-3 text-xs">
                  <span className={`mt-1 w-2 h-2 rounded-full shrink-0 ${t.tone === 'warning' ? 'bg-amber-500' : t.tone === 'success' ? 'bg-emerald-500' : t.tone === 'ai' ? 'bg-[#00BAF2]' : 'bg-slate-400'}`} />
                  <div className="min-w-0">
                    <div className="flex items-baseline gap-2"><strong className="text-slate-900">{t.title}</strong><span className="font-mono text-[10px] text-slate-400">{t.timestamp}</span></div>
                    <p className="text-slate-600 leading-snug break-words">{t.detail}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </div>
      )}

      {activeTab === 'settlements' && showSettlements && <SettlementsTab caseId={caseData.id} onToast={showToast} />}

      {activeTab === 'evidence' && <PdfEvidenceViewer caseId={caseData.id} focus={evidenceFocus} />}

      {activeTab === 'crm-form' && (
        <AutoFilledCrmForm
          caseId={caseData.id}
          form={crm.data}
          error={crm.error}
          reload={crm.reload}
          isCompliancePersona={isCompliancePersona}
          onViewEvidence={(docId, field) => openEvidence(docId, field)}
          onSubmitToCompliance={handleApprove}
          onEditOverride={() => showToast('Override mode toggled. Edits are saved and audited.')}
        />
      )}

      {voiceOpen && (
        <VoiceChasePanel
          caseId={caseData.id}
          merchantName={caseData.merchantName}
          contactName={caseData.contactName ?? undefined}
          defaultPhone={caseData.contactPhone ?? ''}
          request={chaseRequest}
          onClose={() => setVoiceOpen(false)}
          onSend={async (channel: ChaseChannel, phone?: string) => {
            await onAction('voice', channel, phone);          // a refusal (bad number, call in progress) rejects and keeps the drawer open
            setVoiceOpen(false);
            showToast(channel === 'voice' ? 'Calling now. Progress and the transcript appear in Voice chase history and the timeline.' : `${channel === 'whatsapp' ? 'WhatsApp' : 'Email'} request recorded on the timeline.`);
          }}
        />
      )}
    </div>
  );
}

function CheckRow({ check, onOpen }: { check: CaseCheck; onOpen: (docId: string | null, field?: string | null) => void }) {
  const Icon = check.status === 'pass' ? CircleCheck : check.status === 'fail' ? CircleX : check.status === 'warn' ? AlertTriangle : CircleMinus;
  const tone = check.status === 'pass' ? 'text-emerald-600' : check.status === 'fail' ? 'text-rose-600' : check.status === 'warn' ? 'text-amber-600' : 'text-slate-400';
  const bad = check.status === 'fail' || check.status === 'warn';
  return (
    <div className={`p-3.5 rounded-xl border ${bad ? 'border-rose-200 bg-rose-50/30' : 'border-slate-200 bg-slate-50/40'}`}>
      <div className="flex items-start gap-3">
        <Icon size={18} className={`${tone} shrink-0 mt-0.5`} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <strong className="text-xs font-bold text-slate-900">{check.label}</strong>
            {check.action === 'escalate' && <span className="text-[9px] font-extrabold px-1.5 rounded bg-rose-100 text-rose-800 border border-rose-300">Needs human judgement</span>}
            {check.action === 'ask' && <span className="text-[9px] font-extrabold px-1.5 rounded bg-amber-100 text-amber-800 border border-amber-300">Merchant can fix</span>}
          </div>
          <p className="text-[11px] text-slate-600 mt-0.5 leading-snug">{check.detail}</p>
          {bad && check.evidence.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {check.evidence.slice(0, 6).map((e, i) => (
                <button
                  key={i}
                  disabled={!e.doc_id}
                  onClick={() => onOpen(e.doc_id, e.field)}
                  className={`text-[10px] font-semibold px-2 py-0.5 rounded-md border inline-flex items-center gap-1 max-w-[320px] ${e.doc_id ? 'bg-white text-[#002970] border-[#cfe9fc] hover:bg-[#e6f7fc]' : 'bg-slate-100 text-slate-500 border-slate-200 cursor-default'}`}
                >
                  {e.doc_id && <FileSearch size={10} className="shrink-0" />}
                  <span className="truncate">{e.source}{e.page ? ` p.${e.page}` : ''}: {String(e.value ?? '').slice(0, 60)}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ChecklistItem({
  title, subtitle, source, status, onViewEvidence, onChase, onDelete,
}: { title: string; subtitle: string; source: string; status: 'completed' | 'action-required'; onViewEvidence?: () => void; onChase?: () => void; onDelete?: () => void }) {
  const isComplete = status === 'completed';
  return (
    <div className={`p-3.5 rounded-xl border transition-all flex items-start justify-between gap-3 ${isComplete ? 'bg-slate-50/50 border-slate-200 hover:border-slate-300' : 'bg-white border-amber-200 shadow-2xs hover:border-amber-300'}`}>
      <div className="flex items-start gap-3 min-w-0">
        <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5 text-xs font-bold ${isComplete ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>{isComplete ? '✓' : '!'}</div>
        <div className="min-w-0">
          <strong className="block text-xs font-bold text-slate-900 leading-tight">{title}</strong>
          <p className="text-[11px] text-slate-500 mt-0.5 leading-snug break-words">{subtitle}</p>
          {source && <span className="block text-[10px] font-mono text-slate-400 mt-1 truncate">{source}</span>}
        </div>
      </div>
      <div className="shrink-0 flex items-center gap-1.5 self-center">
        {onDelete && <button onClick={onDelete} aria-label={`Delete ${title}`} title="Delete this file (demo: so it can be uploaded again)" className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg border border-transparent hover:border-rose-200 transition-colors"><Trash2 size={14} /></button>}
        {onViewEvidence && <button onClick={onViewEvidence} className="px-2.5 py-1 text-[11px] font-bold text-[#002970] bg-[#e6f7fc] hover:bg-[#d6f2fa] rounded-lg border border-[#cfe9fc] transition-colors">Evidence →</button>}
        {onChase && <button onClick={onChase} className="px-2.5 py-1 text-[11px] font-bold text-amber-900 bg-amber-100 hover:bg-amber-200 rounded-lg border border-amber-300 transition-colors">Chase</button>}
      </div>
    </div>
  );
}
