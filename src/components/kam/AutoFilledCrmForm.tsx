import { useState } from 'react';
import {
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  Edit3,
  Send,
  Lock,
  Building,
  CreditCard,
  Users,
  Loader2,
  FileSearch,
} from 'lucide-react';
import { postJson, type CrmField, type CrmForm } from '@/services/api';

interface AutoFilledCrmFormProps {
  caseId: string;
  form: CrmForm | null;
  error?: string | null;
  reload: () => void | Promise<void>;
  onSubmitToCompliance: () => void;
  onEditOverride: () => void;
  onViewEvidence?: (docId: string, field: string) => void;
  isCompliancePersona?: boolean;
}

const SECTION_ICON: Record<string, { icon: typeof Building; tone: string }> = {
  business: { icon: Building, tone: 'bg-[#e6f7fc] text-[#002970]' },
  tax_bank: { icon: CreditCard, tone: 'bg-emerald-50 text-emerald-700' },
  stakeholders: { icon: Users, tone: 'bg-[#e6f7fc] text-[#002970]' },
};

export function AutoFilledCrmForm({
  caseId, form, error, reload, onSubmitToCompliance, onEditOverride, onViewEvidence, isCompliancePersona = false,
}: AutoFilledCrmFormProps) {
  const [submitted, setSubmitted] = useState(false);
  const [overrideMode, setOverrideMode] = useState(false);
  const [saving, setSaving] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const summary = form?.summary;
  const allFilled = summary ? summary.fields_filled === summary.fields_total : false;

  const saveOverride = async (field: CrmField, value: string) => {
    if (!value.trim() || value === field.value) return;
    setSaving(field.key);
    setSaveError(null);
    try {
      await postJson(`/api/cases/${caseId}/crm-form/override`, { key: field.key, value, note: 'Edited in CRM form' });
      await reload();
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-r from-[#001b4c] via-[#002970] to-[#002970] text-white p-5 md:p-6 rounded-2xl shadow-sm border border-[#00BAF2]/30 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-[#00BAF2]/20 border border-[#00BAF2]/40 text-[#7fdcf8] flex items-center justify-center shrink-0">
            <Sparkles size={22} className="text-[#7fdcf8] animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] font-extrabold uppercase tracking-widest text-sky-200 bg-[#002970]/60 px-2.5 py-0.5 rounded-full border border-[#00BAF2]/30">Zero Manual Data Entry</span>
              {summary?.avg_confidence != null && <span className="text-xs text-[#bae6fd]/80 font-medium">Avg. extraction confidence {summary.avg_confidence}%</span>}
            </div>
            <h2 className="text-base md:text-lg font-extrabold text-white tracking-tight">
              {summary
                ? `✨ Form ${summary.fill_percent}% auto-populated by Karyakarta Agent from ${summary.source_documents} source document${summary.source_documents === 1 ? '' : 's'}.`
                : '✨ Karyakarta Agent is preparing the form…'}
            </h2>
            <p className="text-xs text-[#e0f2fe]/80 mt-0.5 leading-relaxed font-medium">
              Every value is extracted from the uploaded documents and cited to its source. Where two sources disagree, the field is flagged for you.
            </p>
          </div>
        </div>
        <div className="shrink-0 flex items-center gap-2 bg-white/10 px-3.5 py-2 rounded-xl border border-white/20">
          <ShieldCheck size={16} className={summary && summary.conflicts === 0 && allFilled ? 'text-emerald-400' : 'text-amber-300'} />
          <span className="text-xs font-bold text-white">
            {!summary ? 'Loading' : summary.conflicts > 0 ? `${summary.conflicts} conflict${summary.conflicts === 1 ? '' : 's'} to review` : allFilled ? 'Compliance Ready' : `${summary.fields_total - summary.fields_filled} field(s) missing`}
          </span>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-2xs overflow-hidden">
        <div className="p-6 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <span className="text-[10px] font-extrabold uppercase tracking-widest text-[#00BAF2] block mb-0.5">Corporate Onboarding Master Form</span>
            <h3 className="text-lg font-extrabold text-[#002970]">Paytm Business Enterprise Merchant Application</h3>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-500 font-semibold bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-200">
            <Lock size={13} className="text-slate-400" />
            <span>{overrideMode ? 'Maker Mode · Editing (overrides are audited)' : 'Maker Mode · Read Only'}</span>
          </div>
        </div>

        <form onSubmit={(e) => e.preventDefault()} className="p-6 md:p-8 space-y-8">
          {!form && !error && <div className="text-xs text-slate-500 flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> Loading form…</div>}
          {error && <div className="text-xs text-rose-600 font-semibold">Could not load the CRM form: {error}</div>}
          {form?.sections.map((section) => {
            const { icon: Icon, tone } = SECTION_ICON[section.id] ?? SECTION_ICON.business;
            return (
              <div key={section.id}>
                <div className="flex items-center gap-2 pb-3 mb-4 border-b border-slate-100">
                  <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${tone}`}><Icon size={16} /></div>
                  <h4 className="text-sm font-extrabold text-slate-900 uppercase tracking-wide">{section.title}</h4>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                  {section.fields.map((f) => (
                    <AiField key={`${f.key}:${f.value}`} field={f} editable={overrideMode} saving={saving === f.key} onCommit={(v) => saveOverride(f, v)} onViewEvidence={onViewEvidence} />
                  ))}
                </div>
              </div>
            );
          })}
          {saveError && <p className="text-xs text-rose-600 font-semibold">Could not save override: {saveError}</p>}
        </form>

        <div className="p-5 md:p-6 bg-slate-50 border-t border-slate-200/80 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-xs text-slate-600 font-medium">
            <CheckCircle2 size={16} className={allFilled ? 'text-emerald-600 shrink-0' : 'text-slate-400 shrink-0'} />
            <span>
              {summary
                ? `${summary.fields_filled}/${summary.fields_total} fields populated${summary.avg_confidence != null ? ` with ${summary.avg_confidence}% average AI confidence` : ''}.${summary.missing_documents.length ? ` Still missing: ${summary.missing_documents.join(', ')}.` : ''}`
                : 'Waiting for data…'}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => { setOverrideMode(!overrideMode); onEditOverride(); }}
              className={`px-4 py-2.5 rounded-xl border text-xs font-bold transition-all flex items-center gap-2 ${overrideMode ? 'bg-amber-100 text-amber-900 border-amber-300' : 'bg-white hover:bg-slate-100 text-slate-700 border-slate-300'}`}
            >
              <Edit3 size={14} className="text-slate-500" />
              <span>{overrideMode ? 'Lock AI Fields' : 'Edit Field (Override AI)'}</span>
            </button>
            <button
              type="button"
              onClick={() => { setSubmitted(true); onSubmitToCompliance(); }}
              disabled={submitted || isCompliancePersona}
              className="px-6 py-2.5 bg-[#002970] hover:bg-[#001b4c] active:bg-[#001438] text-white text-xs font-bold rounded-xl transition-all shadow-sm flex items-center gap-2 disabled:opacity-50"
            >
              <Send size={14} className="text-[#00BAF2]" />
              <span>{submitted ? 'Submitted to Compliance Desk ✓' : 'Submit to Compliance (Checker) →'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function AiField({
  field, editable, saving, onCommit, onViewEvidence,
}: { field: CrmField; editable: boolean; saving: boolean; onCommit: (value: string) => void; onViewEvidence?: (docId: string, field: string) => void }) {
  const [draft, setDraft] = useState(field.value ?? '');
  const conflict = field.status === 'conflict';
  const missing = field.status === 'missing';
  const canJump = !!(field.doc_id && field.field && onViewEvidence);

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2">
        <label className="text-[11px] font-bold text-slate-700 block truncate">{field.label}</label>
        <button
          type="button"
          disabled={!canJump}
          onClick={() => canJump && onViewEvidence!(field.doc_id!, field.field!)}
          title={canJump ? 'Open the source document with this field highlighted' : undefined}
          className={`text-[9px] font-semibold px-1.5 rounded border shrink-0 inline-flex items-center gap-1 ${
            missing ? 'text-slate-500 bg-slate-50 border-slate-200' : field.overridden ? 'text-amber-800 bg-amber-50 border-amber-300' : 'text-[#002970] bg-[#e6f7fc] border-[#cfe9fc] hover:bg-[#d6f2fa]'
          }`}
        >
          {canJump ? <FileSearch size={9} /> : <Sparkles size={9} className="text-[#0099cc]" />}
          {field.source}
        </button>
      </div>
      <div className="relative">
        <input
          type="text"
          value={editable ? draft : field.value ?? ''}
          placeholder={missing ? 'Awaiting document' : undefined}
          readOnly={!editable}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={() => editable && onCommit(draft)}
          className={`w-full px-3.5 py-2.5 text-xs font-medium rounded-xl transition-all outline-none ${
            editable ? 'bg-white border-2 border-amber-400 text-slate-900 shadow-2xs'
              : missing ? 'bg-slate-50 border border-dashed border-slate-300 text-slate-500 pl-8'
              : conflict ? 'bg-amber-50/50 border border-amber-300 text-slate-900 font-semibold pl-8'
              : 'bg-[#e6f7fc]/20 border border-[#cfe9fc]/90 text-slate-900 font-semibold pl-8 focus:border-[#00BAF2]'
          }`}
        />
        {!editable && <div className="absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none text-[#0099cc]"><Sparkles size={13} /></div>}
        {saving && <Loader2 size={13} className="absolute right-3 top-1/2 -translate-y-1/2 animate-spin text-slate-400" />}
      </div>
      {conflict && <span className="text-[10px] text-amber-700 font-bold block mt-0.5">⚠️ Conflict: {field.conflict_note}</span>}
      {field.overridden && <span className="text-[10px] text-slate-500 block mt-0.5">AI read “{field.ai_value}”; overridden by KAM.</span>}
    </div>
  );
}
