import React, { useState } from 'react';
import {
  Sparkles,
  ExternalLink,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  FileCheck,
  Edit3,
  Send,
  Lock,
  Building,
  CreditCard,
  Users
} from 'lucide-react';
import type { MerchantCase } from '@/types/case';

interface AutoFilledCrmFormProps {
  caseData: MerchantCase;
  onSubmitToCompliance: () => void;
  onEditOverride: () => void;
  isCompliancePersona?: boolean;
}

export function AutoFilledCrmForm({
  caseData,
  onSubmitToCompliance,
  onEditOverride,
  isCompliancePersona = false,
}: AutoFilledCrmFormProps) {
  const [submitted, setSubmitted] = useState(false);
  const [overrideMode, setOverrideMode] = useState(false);

  const handleSubmit = () => {
    setSubmitted(true);
    onSubmitToCompliance();
  };

  return (
    <div className="space-y-6">
      {/* Prominent Purple AI Banner */}
      <div className="bg-gradient-to-r from-purple-900 via-indigo-900 to-[#002970] text-white p-5 md:p-6 rounded-2xl shadow-sm border border-purple-500/30 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-purple-500/20 border border-purple-400/40 text-purple-300 flex items-center justify-center shrink-0">
            <Sparkles size={22} className="text-purple-300 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] font-extrabold uppercase tracking-widest text-purple-200 bg-purple-800/60 px-2.5 py-0.5 rounded-full border border-purple-400/30">
                Zero Manual Data Entry
              </span>
              <span className="text-xs text-purple-200/80 font-medium">
                Verified against 3 Sovereign Registries
              </span>
            </div>
            <h2 className="text-base md:text-lg font-extrabold text-white tracking-tight">
              ✨ Form 100% Auto-Populated by Karyakarta Agent from 11 source documents.
            </h2>
            <p className="text-xs text-purple-100/80 mt-0.5 leading-relaxed font-medium">
              Every entity has been extracted from legal proofs, cross-referenced against MCA &amp; GSTN records, and cited with provenance lines.
            </p>
          </div>
        </div>

        {/* Status chip */}
        <div className="shrink-0 flex items-center gap-2 bg-white/10 backdrop-blur-xs px-3.5 py-2 rounded-xl border border-white/20">
          <ShieldCheck size={16} className="text-emerald-400" />
          <span className="text-xs font-bold text-white">Compliance Ready</span>
        </div>
      </div>

      {/* Main CRM Form Card */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-2xs overflow-hidden">
        {/* Form Title & Context */}
        <div className="p-6 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <span className="text-[10px] font-extrabold uppercase tracking-widest text-[#00BAF2] block mb-0.5">
              Corporate Onboarding Master Form
            </span>
            <h3 className="text-lg font-extrabold text-[#002970]">
              Paytm Business Enterprise Merchant Application
            </h3>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-500 font-semibold bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-200">
            <Lock size={13} className="text-slate-400" />
            <span>Maker Mode · Read Only</span>
          </div>
        </div>

        <form onSubmit={(e) => e.preventDefault()} className="p-6 md:p-8 space-y-8">
          {/* Section 1: Business Details */}
          <div>
            <div className="flex items-center gap-2 pb-3 mb-4 border-b border-slate-100">
              <div className="w-7 h-7 rounded-lg bg-indigo-50 text-indigo-700 flex items-center justify-center">
                <Building size={16} />
              </div>
              <h4 className="text-sm font-extrabold text-slate-900 uppercase tracking-wide">
                1. Business &amp; Entity Details
              </h4>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              <AiField
                label="Legal Entity Name"
                value="Sharma Foods Private Limited"
                sourceLabel="Source: COI p.1"
                editable={overrideMode}
              />
              <AiField
                label="Corporate Identity Number (CIN)"
                value="U74999MH2021PTC123456"
                sourceLabel="Source: MCA21 Registry"
                editable={overrideMode}
              />
              <AiField
                label="Date of Incorporation"
                value="14 August 2021"
                sourceLabel="Source: COI p.1"
                editable={overrideMode}
              />
              <AiField
                label="Registered Office Address"
                value="12 MG Road, Fort, Mumbai - 400001, Maharashtra"
                sourceLabel="Source: COI & MCA Registry"
                editable={overrideMode}
              />
              <AiField
                label="Operating / Principal Address"
                value="12 Mahatma Gandhi Marg, Navi Mumbai - 400703"
                sourceLabel="Source: GST Cert p.1"
                editable={overrideMode}
                warningNote="Exception: Mismatch flagged vs submitted application"
              />
              <AiField
                label="Company Classification"
                value="Private Limited Company (Indian Non-Govt)"
                sourceLabel="Source: MCA Master Data"
                editable={overrideMode}
              />
            </div>
          </div>

          {/* Section 2: Tax & Banking */}
          <div>
            <div className="flex items-center gap-2 pb-3 mb-4 border-b border-slate-100">
              <div className="w-7 h-7 rounded-lg bg-emerald-50 text-emerald-700 flex items-center justify-center">
                <CreditCard size={16} />
              </div>
              <h4 className="text-sm font-extrabold text-slate-900 uppercase tracking-wide">
                2. Tax &amp; Settlement Banking
              </h4>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              <AiField
                label="Permanent Account Number (PAN)"
                value="AABCS4821Q"
                sourceLabel="Source: Company PAN Card p.1"
                editable={overrideMode}
              />
              <AiField
                label="GSTIN Identifier"
                value="27AABCS4821Q1Z7"
                sourceLabel="Source: GST Cert p.1"
                editable={overrideMode}
              />
              <AiField
                label="Settlement Bank Account Number"
                value="50200034928174"
                sourceLabel="Source: Bank Passbook p.1"
                editable={overrideMode}
              />
              <AiField
                label="Bank IFSC Code"
                value="HDFC0000128"
                sourceLabel="Source: Pre-printed Cheque"
                editable={overrideMode}
              />
              <AiField
                label="Beneficiary / Account Holder Name"
                value="Sharma Foods Private Limited"
                sourceLabel="Source: Attested Bank Letter"
                editable={overrideMode}
              />
              <AiField
                label="Account Type"
                value="Corporate Current Account"
                sourceLabel="Source: Bank Statement p.1"
                editable={overrideMode}
              />
            </div>
          </div>

          {/* Section 3: Stakeholders & Governance */}
          <div>
            <div className="flex items-center gap-2 pb-3 mb-4 border-b border-slate-100">
              <div className="w-7 h-7 rounded-lg bg-purple-50 text-purple-700 flex items-center justify-center">
                <Users size={16} />
              </div>
              <h4 className="text-sm font-extrabold text-slate-900 uppercase tracking-wide">
                3. Stakeholders &amp; Beneficial Owners (KBO)
              </h4>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              <AiField
                label="Managing Director / Signatory"
                value="Rajesh Kumar Sharma"
                sourceLabel="Source: Board Resolution p.2"
                editable={overrideMode}
              />
              <AiField
                label="Director Identification Number (DIN)"
                value="DIN-08492019"
                sourceLabel="Source: MCA Registry"
                editable={overrideMode}
              />
              <AiField
                label="Equity Shareholding Percentage"
                value="68.50% (Majority Stakeholder)"
                sourceLabel="Source: Annual Return (MGT-7)"
                editable={overrideMode}
              />
              <AiField
                label="Joint Director"
                value="Anjali Rajesh Sharma"
                sourceLabel="Source: Board Resolution p.2"
                editable={overrideMode}
              />
              <AiField
                label="Director Identification Number (DIN)"
                value="DIN-08492020"
                sourceLabel="Source: MCA Registry"
                editable={overrideMode}
              />
              <AiField
                label="Equity Shareholding Percentage"
                value="31.50%"
                sourceLabel="Source: Annual Return (MGT-7)"
                editable={overrideMode}
              />
            </div>
          </div>
        </form>

        {/* Bottom Action Bar */}
        <div className="p-5 md:p-6 bg-slate-50 border-t border-slate-200/80 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-xs text-slate-600 font-medium">
            <CheckCircle2 size={16} className="text-emerald-600 shrink-0" />
            <span>
              All mandatory statutory fields populated with 98.4% aggregated AI confidence.
            </span>
          </div>

          <div className="flex items-center gap-3">
            {/* Override Button */}
            <button
              type="button"
              onClick={() => {
                setOverrideMode(!overrideMode);
                onEditOverride();
              }}
              className={`px-4 py-2.5 rounded-xl border text-xs font-bold transition-all flex items-center gap-2 ${
                overrideMode
                  ? 'bg-amber-100 text-amber-900 border-amber-300'
                  : 'bg-white hover:bg-slate-100 text-slate-700 border-slate-300'
              }`}
            >
              <Edit3 size={14} className="text-slate-500" />
              <span>{overrideMode ? 'Lock AI Fields' : 'Edit Field (Override AI)'}</span>
            </button>

            {/* Primary CTA: Submit to Compliance */}
            <button
              type="button"
              onClick={handleSubmit}
              disabled={submitted}
              className="px-6 py-2.5 bg-[#002970] hover:bg-[#001b4c] active:bg-[#001438] text-white text-xs font-bold rounded-xl transition-all shadow-sm flex items-center gap-2 disabled:opacity-50"
            >
              <Send size={14} className="text-[#00BAF2]" />
              <span>
                {submitted
                  ? 'Submitted to Compliance Desk ✓'
                  : 'Submit to Compliance (Checker) →'}
              </span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function AiField({
  label,
  value,
  sourceLabel,
  editable,
  warningNote,
}: {
  label: string;
  value: string;
  sourceLabel: string;
  editable: boolean;
  warningNote?: string;
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2">
        <label className="text-[11px] font-bold text-slate-700 block truncate">
          {label}
        </label>
        <span className="text-[9px] font-semibold text-purple-700 bg-purple-50 px-1.5 py-0.2 rounded border border-purple-200 shrink-0 inline-flex items-center gap-1">
          <Sparkles size={9} className="text-purple-600" />
          {sourceLabel}
        </span>
      </div>

      <div className="relative">
        <input
          type="text"
          defaultValue={value}
          readOnly={!editable}
          className={`w-full px-3.5 py-2.5 text-xs font-medium rounded-xl transition-all outline-none ${
            editable
              ? 'bg-white border-2 border-amber-400 text-slate-900 shadow-2xs'
              : warningNote
              ? 'bg-amber-50/50 border border-amber-300 text-slate-900 font-semibold pl-8'
              : 'bg-purple-50/20 border border-purple-200/90 text-slate-900 font-semibold pl-8 focus:border-purple-400'
          }`}
        />

        {/* Sparkle icon inside input indicating AI-filled */}
        {!editable && (
          <div className="absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none text-purple-500">
            <Sparkles size={13} />
          </div>
        )}
      </div>

      {warningNote && (
        <span className="text-[10px] text-amber-700 font-bold block mt-0.5">
          ⚠️ {warningNote}
        </span>
      )}
    </div>
  );
}
