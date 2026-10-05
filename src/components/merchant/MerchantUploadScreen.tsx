import { useEffect, useRef, useState, type ChangeEvent } from 'react';
import { 
  AlertTriangle, ArrowRight, Check, ChevronRight, FileCheck2, ShieldCheck, Trash2, 
  UploadCloud, Play, Pause, AlertCircle, Home, User, Bot, FileText, LockKeyhole, 
  Building2, CreditCard, Landmark, X, Eye, Download, Info, CheckCircle2, 
  FileSignature, ReceiptText, UserCheck, ScrollText, ChevronDown, ChevronUp, FileCode
} from 'lucide-react';
import type { MerchantCase } from '@/types/case';
import type { UploadReport } from '@/services/api';
import { AppLogo } from '@/components/shared/AppLogo';
import { ShopVerificationCard } from '@/components/merchant/ShopVerificationCard';

interface UploadStatus {
  name: string;
  state: 'uploading' | 'done' | 'rejected' | 'error';
  sha?: string;
  label?: string;
  note?: string;
}

type MerchantView = 'stage1' | 'account' | 'upload' | 'action';

interface MerchantUploadScreenProps { 
  caseData: MerchantCase; 
  onUploadFiles: (files: File[], slot: string | null) => Promise<UploadReport>;
  onOpenKAM: () => void; 
  cases?: { id: string; name: string; stage: string }[];
  onChooseCase?: (caseId: string) => void;
  view?: MerchantView; 
  onNavigate?: (view: MerchantView) => void; 
}

export interface DocumentRequirement {
  id: string;
  category: 'business' | 'bank' | 'tax' | 'signatory' | 'governance';
  categoryLabel: string;
  title: string;
  acceptedDocuments: string[];
  mandatoryRules: string[];
  sampleFormats: string;
  required: boolean;
}

const documentChecklist: DocumentRequirement[] = [
  {
    id: 'business_proof',
    category: 'business',
    categoryLabel: '1. Business & Registration Proof',
    title: 'Business Registration / Municipal Proof',
    acceptedDocuments: [
      'Shop Establishment Act Certificate',
      'Regional State Registration',
      'Municipal Corporation License',
      'Utility bills (Electricity, Water, Gas, Telecom) — Max 2 months old',
      'Proprietor Personal Address Proof (Passport, Voter ID, DL, Aadhaar) if address matches'
    ],
    mandatoryRules: [
      'Utility bills must be in the business name and max 2 months old',
      'Proprietor address proof accepted only when personal and business addresses are identical'
    ],
    sampleFormats: 'PDF, JPG or PNG · Max 10 MB',
    required: true
  },
  {
    id: 'bank_details',
    category: 'bank',
    categoryLabel: '2. Settlement Bank Account Details',
    title: 'Corporate Bank Account Proof',
    acceptedDocuments: [
      'Cancelled Cheque with pre-printed business name',
      'Bank-Attested Letter on Bank Letterhead with branch stamp',
      'Signed & stamped Bank Passbook / Latest Bank Statement'
    ],
    mandatoryRules: [
      'Strictly Current accounts only; Savings accounts are not permitted for corporate entities',
      'The bank account holder name must strictly match the legal business name',
      'Business name, account number, and IFSC code must be pre-printed',
      'If business name is not pre-printed, a bank-attested letter on company letterhead is required'
    ],
    sampleFormats: 'PDF or JPG · Max 10 MB',
    required: true
  },
  {
    id: 'tax_gst',
    category: 'tax',
    categoryLabel: '3. Tax & GST Documents',
    title: 'Company PAN & GST Certificate',
    acceptedDocuments: [
      'PAN Card of the company or proprietor',
      'GST Certificate / Provisional GST Certificate',
      'Declaration of GST Non-Enrollment (if exempt)'
    ],
    mandatoryRules: [
      'GSTIN, trade name, and business address must be clearly visible and legible on certificate',
      'PAN number must match official MCA records'
    ],
    sampleFormats: 'PDF, JPG or PNG · Max 10 MB',
    required: true
  },
  {
    id: 'signatory_kyc',
    category: 'signatory',
    categoryLabel: '4. Authorized Signatory KYC (Identity Proof)',
    title: 'Officially Valid Document (OVD)',
    acceptedDocuments: [
      'Passport (Front & Back)',
      'Aadhaar Card (Masked/UIDAI compliant)',
      'Driving License',
      'Voter ID Card',
      'NREGA Card'
    ],
    mandatoryRules: [
      'Authorized signatory must submit an Officially Valid Document (OVD)',
      'Full name and photo must be clear and unobstructed'
    ],
    sampleFormats: 'PDF, JPG or PNG · Max 10 MB',
    required: true
  },
  {
    id: 'corporate_docs',
    category: 'governance',
    categoryLabel: '5. Company & Governance Documents',
    title: 'Incorporation, Board Resolution & Shareholding',
    acceptedDocuments: [
      'Certificate of Incorporation (with CIN)',
      'Board Resolution authorising the signatory, certified by a director',
      'Shareholding / beneficial-owner declaration (list the partners of any company or LLP shareholder)',
      'FSSAI licence (food businesses)'
    ],
    mandatoryRules: [
      'The board resolution must name an authorised signatory who is a current director, or carry valid delegation',
      'Every owner above 10% (directly or through another entity) needs identity proof'
    ],
    sampleFormats: 'PDF, JPG or PNG · Max 25 MB',
    required: true
  }
];

/** Which upload card each stored document type belongs to. */
const SLOT_FOR_TYPE: Record<string, string> = {
  pan: 'tax_gst', gst: 'tax_gst', bank_cheque: 'bank_details', director_kyc: 'signatory_kyc',
  coi: 'corporate_docs', board_resolution: 'corporate_docs', shareholding: 'corporate_docs', fssai: 'corporate_docs',
  electricity_bill: 'business_proof',
};

/** The merchant portal for ONE case. It is remounted (see `key`) when another case is chosen, so no state leaks between merchants. */
export function MerchantUploadScreen(props: MerchantUploadScreenProps) {
  return <MerchantPortal key={props.caseData.id} {...props} />;
}

function MerchantPortal({ caseData, onUploadFiles, onOpenKAM, cases = [], onChooseCase, view = 'upload', onNavigate }: MerchantUploadScreenProps) {
  // start from what this case already holds on the server (the case's own uploaded documents)
  const stored = (caseData.uploaded ?? []).filter((d) => d.status === 'uploaded');
  const [uploadedMap, setUploadedMap] = useState<Record<string, string[]>>(() => {
    const m: Record<string, string[]> = {};
    for (const d of stored) { const slot = SLOT_FOR_TYPE[d.doc_type]; if (slot) m[slot] = [...(m[slot] ?? []), d.label]; }
    return m;
  });
  const [allFiles, setAllFiles] = useState<string[]>(() => stored.map((d) => d.label));
  // a file the KAM deleted (or a reset case) disappears here too, so the merchant can upload it again
  const storedSig = stored.map((d) => `${d.doc_type}:${d.label}`).join('|');
  const knownStored = useRef<Map<string, string>>(new Map(stored.map((d) => [d.doc_type, d.label])));
  useEffect(() => {
    const now = new Map(stored.map((d) => [d.doc_type, d.label] as [string, string]));
    const gone = [...knownStored.current].filter(([type]) => !now.has(type));
    if (gone.length) {
      const labels = new Set(gone.map(([, label]) => label));
      setAllFiles((files) => files.filter((f) => !labels.has(f)));
      setUploadedMap((m) => Object.fromEntries(Object.entries(m).map(([slot, files]) => [slot, files.filter((f) => !labels.has(f))])));
    }
    knownStored.current = now;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storedSig]);
  const [playing, setPlaying] = useState(false);
  const [showDpdpModal, setShowDpdpModal] = useState(false);
  const [activeCategoryFilter, setActiveCategoryFilter] = useState<string>('all');
  const fileRef = useRef<HTMLInputElement>(null);
  const [activeUploadTarget, setActiveUploadTarget] = useState<string | null>(null);
  const [uploads, setUploads] = useState<UploadStatus[]>([]);

  // Real upload: store + hash + start the pipeline on the backend. The UI keeps its optimistic per-slot list
  // and drops any file the backend rejected (wrong type, too large, empty).
  const ingest = (selected: File[], target: string | null) => {
    if (selected.length === 0) return;
    const slot = target ?? (documentChecklist.find((r) => !uploadedMap[r.id] || uploadedMap[r.id].length === 0) || documentChecklist[0]).id;
    const names = selected.map((file) => file.name);
    setAllFiles((current) => [...current, ...names]);
    setUploadedMap((prev) => ({ ...prev, [slot]: [...(prev[slot] || []), ...names] }));
    setUploads((prev) => [...names.map((name) => ({ name, state: 'uploading' as const })), ...prev]);

    const settle = (name: string, patch: Partial<UploadStatus>) =>
      setUploads((prev) => prev.map((u) => (u.name === name && u.state === 'uploading' ? { ...u, ...patch } : u)));
    const forget = (name: string) => {
      setAllFiles((prev) => { const i = prev.indexOf(name); return i < 0 ? prev : prev.filter((_, j) => j !== i); });
      setUploadedMap((prev) => ({ ...prev, [slot]: (prev[slot] || []).filter((f) => f !== name) }));
    };

    onUploadFiles(selected, slot).then(
      (report) => {
        report.documents.forEach((d) => settle(d.filename, { state: 'done', sha: d.sha256, label: d.doc_type_label }));
        report.rejected.forEach((r) => { settle(r.filename, { state: 'rejected', note: r.reason }); forget(r.filename); });
      },
      (err) => names.forEach((name) => { settle(name, { state: 'error', note: err instanceof Error ? err.message : String(err) }); forget(name); }),
    );
  };

  const receiveFiles = (event: ChangeEvent<HTMLInputElement>) => {
    ingest(Array.from(event.target.files ?? []), activeUploadTarget);
    event.target.value = '';
    setActiveUploadTarget(null);
  };

  const go = (next: MerchantView) => {
    onNavigate?.(next);
  };

  return (
    <div className="h-screen bg-slate-50 flex flex-col font-sans text-slate-900 selection:bg-[#cfe9fc] overflow-hidden">
      {/* Global Header */}
      <header className="flex-none flex items-center justify-between px-6 py-3.5 bg-white border-b border-slate-200/80 z-20 shadow-2xs">
        <div className="flex items-center gap-8">
          <button className="flex items-center gap-3 hover:opacity-85 transition-opacity" onClick={onOpenKAM}>
            <AppLogo subtitle="Paytm Corporate Gateway" />
          </button>
          
          <div className="hidden md:flex items-center gap-3">
            <div className="w-px h-6 bg-slate-200"></div>
            <div className="flex flex-col justify-center">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-[#00BAF2]"></span>
                <strong className="text-xs font-bold text-slate-800">Corporate Payment Gateway</strong>
              </div>
              <span className="text-[10px] text-slate-500 font-medium">Merchant Account Onboarding</span>
            </div>
          </div>
        </div>

        {onChooseCase && cases.length > 0 && (
          <label className="hidden md:flex items-center gap-2 text-[11px] font-bold text-slate-500">
            Testing as
            <select
              aria-label="Open this merchant case"
              value={caseData.id}
              onChange={(e) => onChooseCase(e.target.value)}
              className="text-xs font-semibold text-slate-800 bg-slate-50 border border-slate-200 rounded-lg px-2 py-1.5 max-w-[260px]"
            >
              {cases.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.id}){c.stage ? ` · ${c.stage}` : ''}</option>)}
            </select>
          </label>
        )}
        <button 
          onClick={() => go('account')} 
          className="flex items-center gap-3 hover:bg-[#e6f7fc]/50 px-3 py-1.5 rounded-xl transition-all border border-transparent hover:border-[#cfe9fc]"
        >
          <div className="w-8 h-8 rounded-full bg-[#002970] text-[#00BAF2] font-black text-xs flex items-center justify-center ring-2 ring-[#00BAF2]/20">
            {caseData.merchantName.split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase()}
          </div>
          <div className="text-left hidden sm:block">
            <strong className="block text-xs font-bold text-slate-900">{caseData.merchantName}</strong>
            <small className="block text-[10px] text-slate-500 font-medium mt-0.5">Authorized Signatory</small>
          </div>
          <ChevronRight size={16} className="text-slate-400" />
        </button>
      </header>

      <div className="flex-1 flex overflow-hidden">
        {/* Modern Sidebar with Paytm Deep Navy accents */}
        <aside className="w-64 bg-white border-r border-slate-200/80 hidden md:flex flex-col shrink-0 z-10 shadow-[4px_0_24px_rgba(0,41,112,0.03)]">
          <div className="p-5 border-b border-slate-100 flex items-center justify-between">
            <div>
              <span className="text-[10px] font-extrabold uppercase tracking-widest text-[#00BAF2] block mb-0.5">Merchant Portal</span>
              <strong className="text-sm font-extrabold text-[#002970]">Main Workspace</strong>
            </div>
            <span className="w-2 h-2 rounded-full bg-[#00BAF2] animate-pulse"></span>
          </div>
          <nav className="p-3 space-y-1.5 flex-1 overflow-y-auto">
            <SidebarItem 
              icon={<Home size={18} />} 
              label="Home" 
              active={view === 'stage1'} 
              onClick={() => go('stage1')} 
            />
            <SidebarItem 
              icon={<User size={18} />} 
              label="Account Center" 
              active={view === 'account'} 
              onClick={() => go('account')} 
            />
            <SidebarItem 
              icon={<FileText size={18} />} 
              label="Documents Upload" 
              active={view === 'upload'} 
              onClick={() => go('upload')} 
            />
            <SidebarItem 
              icon={<Bot size={18} />} 
              label="AI Communication Center" 
              active={view === 'action'} 
              onClick={() => go('action')} 
              badge="1"
            />
          </nav>
          
          <div className="p-4 border-t border-slate-100 bg-[#f8fbfe]">
            <div className="bg-white p-4 rounded-xl border border-[#cfe9fc] shadow-2xs">
              <div className="flex items-center gap-2 mb-1.5">
                <div className="w-6 h-6 rounded-lg bg-[#e6f7fc] text-[#002970] flex items-center justify-center">
                  <ShieldCheck size={14} className="text-[#00BAF2]" />
                </div>
                <strong className="text-xs font-bold text-[#002970]">Dedicated Support</strong>
              </div>
              <p className="text-[10px] text-slate-600 mb-3 leading-relaxed">
                Connect directly with your Karyakarta Key Account Manager.
              </p>
              <button 
                onClick={onOpenKAM} 
                className="w-full bg-[#002970] hover:bg-[#001b4c] text-[#00BAF2] text-xs font-bold py-2 rounded-lg transition-colors shadow-2xs flex items-center justify-center gap-1.5"
              >
                Contact KAM Support
              </button>
            </div>
          </div>
        </aside>

        {/* Dynamic Views in Scrollable Content Area */}
        <div className="flex-1 overflow-y-auto relative bg-slate-50/50">
          {caseData.cpv && view !== 'action' && (
            <div className="max-w-3xl w-full mx-auto px-6 sm:px-10 pt-6"><ShopVerificationCard cpv={caseData.cpv} /></div>
          )}
          {view === 'stage1' && <StageOne onNavigate={go} caseData={caseData} />}
          {view === 'account' && (
            <AccountCenter 
              caseData={caseData}
              onNavigate={go} 
              onOpenDpdp={() => setShowDpdpModal(true)} 
            />
          )}
          {view === 'upload' && (
            <UploadPortal 
              uploadedMap={uploadedMap}
              allFiles={allFiles}
              onSelectCategory={(id) => {
                setActiveUploadTarget(id);
                fileRef.current?.click();
              }}
              onFiles={receiveFiles}
              onDropFiles={(files) => ingest(files, null)}
              uploads={uploads}
              onRemove={(reqId, file) => {
                setUploadedMap((prev) => ({
                  ...prev,
                  [reqId]: (prev[reqId] || []).filter((f) => f !== file)
                }));
                setAllFiles((prev) => prev.filter((f) => f !== file));
              }} 
              onSubmit={() => go('action')} 
              fileRef={fileRef} 
              onNavigate={go} 
              onOpenDpdp={() => setShowDpdpModal(true)}
            />
          )}
          {view === 'action' && (
            <ActionRequired
              onNavigate={go}
              caseData={caseData}
              onPickFiles={(files) => { ingest(files, 'business_proof'); go('upload'); }}  
              playing={playing} 
              onPlay={() => setPlaying(!playing)} 
            />
          )}
        </div>
      </div>

      {/* DPDP Act 2023 Official Statutory Agreement Modal */}
      {showDpdpModal && (
        <DpdpAgreementModal caseData={caseData} onClose={() => setShowDpdpModal(false)} />
      )}
    </div>
  );
}

// ----------------------------------------------------------------------
// Sidebar Item Component
// ----------------------------------------------------------------------
function SidebarItem({ icon, label, active, onClick, badge }: { icon: React.ReactNode, label: string, active: boolean, onClick: () => void, badge?: string }) {
  return (
    <button 
      onClick={onClick}
      className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl transition-all text-left group relative overflow-hidden ${
        active 
          ? 'bg-[#002970] text-white shadow-sm font-bold' 
          : 'text-slate-600 hover:bg-[#e6f7fc]/50 hover:text-[#002970] font-semibold border border-transparent'
      }`}
    >
      {active && (
        <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-[#00BAF2] rounded-r-full"></span>
      )}
      <div className="flex items-center gap-3">
        <span className={`${active ? 'text-[#00BAF2]' : 'text-slate-400 group-hover:text-[#002970] transition-colors'}`}>{icon}</span>
        <span className="text-sm tracking-tight">{label}</span>
      </div>
      {badge && (
        <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-extrabold shrink-0 ${active ? 'bg-[#00BAF2] text-[#002970]' : 'bg-red-100 text-red-600 group-hover:bg-red-200'}`}>
          {badge}
        </span>
      )}
    </button>
  );
}

// ----------------------------------------------------------------------
// Tracker Component
// ----------------------------------------------------------------------
function PortalTracker({ current }: { current: number }) { 
  const steps = [
    { label: 'Basic Details', status: 'done' },
    { label: 'Document Upload', status: current === 1 ? 'current' : current > 1 ? 'done' : 'pending' },
    { label: 'AI Verification', status: current === 2 ? 'current' : current > 2 ? 'done' : 'pending' },
    { label: 'Unlimited Access', status: current === 3 ? 'current' : 'pending' }
  ];

  return (
    <div className="flex items-center gap-2 mb-10 overflow-x-auto pb-2 -mx-6 px-6 sm:mx-0 sm:px-0 sm:overflow-visible sm:pb-0">
      {steps.map((step, index) => (
        <div key={step.label} className="flex items-center gap-2 shrink-0">
          <div className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-full border border-slate-200 shadow-sm">
            {step.status === 'done' ? (
               <div className="w-4 h-4 rounded-full bg-emerald-500 text-white flex items-center justify-center">
                 <Check size={10} strokeWidth={3} />
               </div>
            ) : step.status === 'current' ? (
               <div className="w-4 h-4 rounded-full bg-[#002970] text-white flex items-center justify-center text-[9px] font-bold">
                 {index + 1}
               </div>
            ) : (
               <div className="w-4 h-4 rounded-full bg-slate-100 text-slate-500 flex items-center justify-center text-[9px] font-bold">
                 {index + 1}
               </div>
            )}
            <span className={`text-[11px] font-bold ${step.status === 'current' ? 'text-slate-900' : step.status === 'done' ? 'text-slate-700' : 'text-slate-400'}`}>
              {step.label} {step.status === 'current' && <span className="font-medium text-slate-400 ml-1 hidden sm:inline">(Current)</span>}
            </span>
          </div>
          {index < steps.length - 1 && <div className="w-6 h-px bg-slate-200"></div>}
        </div>
      ))}
    </div>
  );
}

// ----------------------------------------------------------------------
// 2. View: Stage-1 Dashboard
// ----------------------------------------------------------------------
function StageOne({ onNavigate, caseData }: { onNavigate: (view: MerchantView) => void; caseData: MerchantCase }) {
  const merchantName = caseData.merchantName;
  const docsTotal = (caseData.uploaded?.length ?? 0) + (caseData.missing?.length ?? 0);
  const docsOpen = caseData.missing?.length ?? 0;
  const stageLabel = caseData.stages?.find((s) => s.status === 'current')?.label;
  return (
    <main className="flex-1 max-w-5xl w-full mx-auto p-6 sm:p-10">
      <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 mb-8">
        Merchant dashboard <span className="text-slate-300">/</span> <span className="text-slate-900">Account overview</span>
      </div>

      {/* Success Banner */}
      <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 flex items-start gap-4 mb-8 shadow-sm">
        <div className="mt-0.5 w-6 h-6 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center shrink-0">
          <Check size={14} strokeWidth={3} />
        </div>
        <div className="flex-1">
          <h2 className="text-sm font-bold text-emerald-900">Account Live (Stage 1)</h2>
          <p className="text-xs text-emerald-700 mt-1 font-medium">Your payment gateway is active and ready to accept transactions.</p>
        </div>
        <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-600 bg-white px-2.5 py-1 rounded-md border border-emerald-100 shadow-sm hidden sm:block">
          Activated today
        </span>
      </div>

      <div className="grid lg:grid-cols-[1fr_300px] gap-8">
        <section className="space-y-6">
          {/* Account Overview Card */}
          <div className="bg-white rounded-2xl border border-slate-200 p-8 shadow-sm relative overflow-hidden">
            <div className="absolute top-0 right-0 w-80 h-80 bg-gradient-to-bl from-[#e6f7fc] via-[#f0f7ff] to-transparent rounded-full -mr-20 -mt-20 opacity-70"></div>
            
            <div className="relative z-10 flex flex-col sm:flex-row sm:items-start justify-between gap-6">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span className="w-2 h-2 rounded-full bg-[#00BAF2] animate-pulse"></span>
                  <span className="text-[10px] font-extrabold uppercase tracking-widest text-[#002970]">
                    Karyakarta Merchant Gateway · Live State
                  </span>
                </div>
                <h1 className="text-3xl font-extrabold text-[#002970] tracking-tight mb-2">Welcome, {merchantName}</h1>
                <p className="text-sm text-slate-600 leading-relaxed max-w-md">
                  Your Stage 1 corporate account is active. Complete Stage 2 Corporate KYC to unlock unlimited settlements and remove restrictions.
                </p>
              </div>
              
              {/* Account Status Pill */}
              <div className="inline-flex items-center gap-2 bg-[#fff8eb] text-amber-800 px-3.5 py-1.5 rounded-full border border-amber-200 shadow-2xs whitespace-nowrap text-xs font-bold">
                <AlertCircle size={14} className="text-amber-600" /> {caseData.accountStatus ?? 'Capped · ₹50,000/month limit'}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mt-10 pt-8 border-t border-slate-100 relative z-10">
              <div className="p-3 rounded-xl bg-slate-50/80 border border-slate-100">
                <span className="block text-2xl font-black text-[#002970] mb-0.5">₹50,000</span>
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Monthly settlement cap</span>
              </div>
              <div className="p-3 rounded-xl bg-slate-50/80 border border-slate-100">
                <span className="block text-2xl font-black text-slate-900 mb-0.5">₹0</span>
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Settled this month</span>
              </div>
              <div className="p-3 rounded-xl bg-[#e6f7fc]/60 border border-[#cfe9fc]">
                <span className="inline-flex items-center gap-1.5 text-sm font-black text-[#002970] bg-white px-2.5 py-1 rounded-md mb-1.5 border border-[#b8e8f8] shadow-2xs">
                  <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div> Active (Stage 1)
                </span>
                <span className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider">Gateway status</span>
              </div>
            </div>
          </div>

          {/* Upgrade CTA Card with Paytm Deep Navy */}
          <div className="bg-[#002970] text-white rounded-2xl p-8 shadow-xl shadow-[#002970]/15 relative overflow-hidden group">
            <div className="absolute top-0 right-0 w-96 h-96 bg-gradient-to-bl from-[#00BAF2]/30 via-transparent to-transparent rounded-full -mr-24 -mt-24 pointer-events-none"></div>
            <div className="relative z-10 flex flex-col sm:flex-row gap-6 items-start sm:items-center">
              <div className="w-14 h-14 bg-white/10 backdrop-blur rounded-2xl border border-white/20 flex items-center justify-center shrink-0 text-[#00BAF2] group-hover:scale-110 transition-transform">
                <ShieldCheck size={30} strokeWidth={1.75} />
              </div>
              <div className="flex-1">
                <div className="inline-flex items-center gap-2 text-[10px] font-extrabold uppercase tracking-widest text-[#00BAF2] bg-white/10 px-2.5 py-1 rounded-md mb-2 border border-white/10">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#00BAF2]"></span>
                  Stage 2 · Corporate KYC
                </div>
                <h2 className="text-xl font-extrabold text-white mb-1.5 tracking-tight">Unlock unlimited settlements.</h2>
                <p className="text-sm text-slate-200 leading-relaxed max-w-xl font-medium">
                  To unlock unlimited daily settlements and remove the ₹50k cap, please complete your Corporate KYC verification with Karyakarta AI.
                </p>
              </div>
              <button 
                onClick={() => onNavigate('upload')}
                className="w-full sm:w-auto shrink-0 bg-[#00BAF2] hover:bg-[#00a3d4] text-[#002970] px-6 py-3.5 rounded-xl font-black text-xs flex items-center justify-center gap-2 transition-all shadow-lg hover:shadow-[#00BAF2]/20 hover:-translate-y-0.5"
              >
                Upload Stage-2 Documents <ArrowRight size={16} />
              </button>
            </div>
          </div>
        </section>

        <aside>
          <div className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-sm sticky top-24">
            <div className="flex items-center justify-between mb-6">
              <span className="text-[10px] font-extrabold uppercase tracking-widest text-slate-400 block">Activation Journey</span>
              <span className="text-[10px] font-bold text-[#00BAF2] bg-[#e6f7fc] px-2 py-0.5 rounded border border-[#b8e8f8]">Karyakarta AI</span>
            </div>
            
            <div className="space-y-6">
              <div className="flex gap-4">
                <div className="w-6 h-6 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center shrink-0 z-10 ring-4 ring-white">
                  <Check size={12} strokeWidth={3} />
                </div>
                <div className="pt-0.5">
                  <strong className="block text-sm font-bold text-slate-900 line-through opacity-70">Basic details</strong>
                  <small className="text-xs font-medium text-slate-500 mt-0.5 block">Mobile OTP verified</small>
                </div>
              </div>

              <div className="flex gap-4 relative">
                <div className="absolute top-[-30px] left-3 w-px h-[30px] bg-slate-200 -z-10"></div>
                <div className="w-6 h-6 rounded-full bg-[#002970] text-[#00BAF2] flex items-center justify-center shrink-0 z-10 ring-4 ring-white font-extrabold text-xs shadow-2xs">
                  2
                </div>
                <div className="pt-0.5">
                  <strong className="block text-sm font-bold text-[#002970]">Corporate KYC</strong>
                  <small className="text-xs font-semibold text-[#00BAF2] mt-0.5 block">{docsTotal ? (docsOpen ? `${docsOpen} of ${docsTotal} documents still needed` : `All ${docsTotal} documents received`) : 'Documents required'}{stageLabel ? ` · Now: ${stageLabel}` : ''}</small>
                </div>
              </div>

              <div className="flex gap-4 relative">
                <div className="absolute top-[-30px] left-3 w-px h-[30px] bg-slate-200 -z-10"></div>
                <div className="w-6 h-6 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center shrink-0 z-10 ring-4 ring-white font-bold text-xs">
                  3
                </div>
                <div className="pt-0.5">
                  <strong className="block text-sm font-bold text-slate-400">Unlimited access</strong>
                  <small className="text-xs font-medium text-slate-400 mt-0.5 block">Unlocks after AI validation</small>
                </div>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </main>
  );
}

// ----------------------------------------------------------------------
// Account Center: Company Details & Verification (Relocated from Login)
// ----------------------------------------------------------------------
function AccountCenter({ caseData, onNavigate, onOpenDpdp }: { caseData: MerchantCase; onNavigate: (view: MerchantView) => void; onOpenDpdp: () => void }) {
  const [legalName, setLegalName] = useState(caseData.legalName ?? '');
  const [pan, setPan] = useState(caseData.pan ?? '');
  const [account, setAccount] = useState('');
  const [consent, setConsent] = useState({ extraction: true, registries: true });
  const [isSaved, setIsSaved] = useState(false);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 3000);
  };

  const handleFillDemo = () => {
    setLegalName(caseData.legalName ?? '');
    setPan(caseData.pan ?? '');
    setConsent({ extraction: true, registries: true });
  };

  return (
    <main className="flex-1 max-w-4xl w-full mx-auto p-6 sm:p-10">
      <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 mb-6">
        Merchant dashboard <span className="text-slate-300">/</span> <span className="text-slate-900">Account Center</span>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8">
        <div>
          <div className="inline-flex items-center gap-2 text-[10px] font-extrabold uppercase tracking-widest text-[#002970] bg-[#e6f7fc] px-3 py-1.5 rounded-lg mb-2 border border-[#b8e8f8]">
            <span className="w-2 h-2 rounded-full bg-[#00BAF2]"></span>
            Karyakarta AI · Corporate Profile Center
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Tell us about your company</h1>
          <p className="text-sm text-slate-500 mt-1">These details help us create and maintain your corporate payment gateway account.</p>
        </div>
        <button 
          type="button" 
          onClick={handleFillDemo} 
          className="text-xs text-[#002970] font-bold hover:text-[#00BAF2] hover:underline self-start sm:self-auto bg-[#e6f7fc] px-3.5 py-2 rounded-xl border border-[#b8e8f8] shadow-2xs transition-colors"
        >
          Fill Demo Data
        </button>
      </div>

      {isSaved && (
        <div className="mb-6 p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 text-xs font-bold flex items-center gap-2 shadow-2xs">
          <div className="w-5 h-5 rounded-full bg-emerald-500 text-white flex items-center justify-center shrink-0">
            <Check size={12} strokeWidth={3} />
          </div>
          Company profile details updated and synced with Karyakarta registry index!
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        {/* Main Entity Card */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="p-6 sm:p-8 border-b border-slate-100">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-[#002970] text-[#00BAF2] flex items-center justify-center shrink-0 shadow-2xs">
                <Building2 size={20} />
              </div>
              <div>
                <h2 className="text-base font-bold text-slate-900">Company & Banking Information</h2>
                <p className="text-xs text-slate-500">Official registration and settlement account numbers.</p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              <div className="sm:col-span-1">
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Legal entity name
                </label>
                <div className="relative">
                  <input 
                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-[#00BAF2]/30 focus:border-[#00BAF2] transition-all"
                    value={legalName} 
                    onChange={(e) => setLegalName(e.target.value)} 
                    placeholder="As registered with MCA" 
                    required 
                  />
                </div>
                <small className="text-[10px] text-slate-400 mt-1 block">Must match certificate of incorporation</small>
              </div>

              <div className="sm:col-span-1">
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Company PAN
                </label>
                <div className="relative">
                  <input 
                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm uppercase font-mono font-semibold focus:outline-none focus:ring-2 focus:ring-[#00BAF2]/30 focus:border-[#00BAF2] transition-all"
                    value={pan} 
                    onChange={(e) => setPan(e.target.value.toUpperCase())} 
                    placeholder="e.g. AABCU9603R" 
                    maxLength={10} 
                    required 
                  />
                </div>
                <small className="text-[10px] text-slate-400 mt-1 block">10-character alphanumeric PAN</small>
              </div>

              <div className="sm:col-span-2">
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Bank account number
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                    <Landmark size={16} />
                  </div>
                  <input 
                    className="w-full pl-10 pr-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#00BAF2]/30 focus:border-[#00BAF2] transition-all"
                    value={account} 
                    onChange={(e) => setAccount(e.target.value.replace(/\D/g, ''))} 
                    placeholder="Enter your settlement account number" 
                    inputMode="numeric" 
                    required 
                  />
                </div>
                <small className="text-[10px] text-slate-400 mt-1 block">Used for daily automated settlement disbursements</small>
              </div>
            </div>
          </div>

          {/* DPDP Act 2023 Consent Section */}
          <div className="p-6 sm:p-8 bg-[#f8fbfe] border-t border-slate-100">
            <div className="bg-white border border-[#cfe9fc] rounded-2xl p-6 shadow-2xs">
              <div className="flex items-start gap-3 mb-4">
                <div className="mt-0.5 text-[#002970] bg-[#e6f7fc] p-2 rounded-xl border border-[#b8e8f8] shadow-2xs">
                  <LockKeyhole size={18} className="text-[#00BAF2]" />
                </div>
                <div>
                  <strong className="block text-sm font-bold text-[#002970]">DPDP Act 2023 Statutory Consent</strong>
                  <p className="text-xs text-slate-500 font-medium leading-relaxed mt-0.5">
                    Your data is used only to activate and verify your corporate account.
                  </p>
                </div>
              </div>

              <div className="space-y-4 pt-2 border-t border-slate-100">
                <label className="flex items-start gap-3 cursor-pointer group">
                  <input 
                    type="checkbox" 
                    className="mt-1 w-4 h-4 rounded border-[#b8e8f8] text-[#002970] focus:ring-[#00BAF2] cursor-pointer transition-colors"
                    checked={consent.extraction} 
                    onChange={(e) => setConsent({ ...consent, extraction: e.target.checked })} 
                  />
                  <span className="text-xs text-slate-600 leading-relaxed group-hover:text-slate-900 transition-colors">
                    I authorise Karyakarta AI to extract and organise information from the documents I upload for account verification.
                  </span>
                </label>

                <label className="flex items-start gap-3 cursor-pointer group">
                  <input 
                    type="checkbox" 
                    className="mt-1 w-4 h-4 rounded border-[#b8e8f8] text-[#002970] focus:ring-[#00BAF2] cursor-pointer transition-colors"
                    checked={consent.registries} 
                    onChange={(e) => setConsent({ ...consent, registries: e.target.checked })} 
                  />
                  <span className="text-xs text-slate-600 leading-relaxed group-hover:text-slate-900 transition-colors">
                    I consent to Karyakarta AI querying official government registries, including MCA and GSTN, to validate my company details.
                  </span>
                </label>
              </div>

              <div className="mt-5 pt-3 border-t border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <small className="text-[11px] text-slate-500">
                  You can withdraw this consent at any time. Read our <button type="button" onClick={onOpenDpdp} className="text-[#002970] font-bold hover:underline">statutory DPDP privacy notice &amp; PDF agreement</button>.
                </small>
                <button 
                  type="button" 
                  onClick={onOpenDpdp}
                  className="flex items-center gap-1.5 text-[10px] font-bold text-emerald-800 bg-emerald-50 hover:bg-emerald-100 px-3 py-1.5 rounded-lg border border-emerald-200 w-fit transition-colors shadow-2xs"
                >
                  <ShieldCheck size={13} className="text-emerald-600" /> View Statutory Terms
                </button>
              </div>
            </div>
          </div>

          <div className="p-6 bg-slate-50/80 border-t border-slate-100 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <ShieldCheck size={16} className="text-emerald-600" />
              <span>Registry queries run securely through encrypted endpoints with Karyakarta AI.</span>
            </div>

            <div className="flex items-center gap-3 w-full sm:w-auto">
              <button 
                type="button" 
                onClick={() => onNavigate('upload')} 
                className="w-full sm:w-auto px-5 py-2.5 bg-white border border-slate-200 text-slate-700 font-bold text-xs rounded-xl hover:bg-slate-50 transition-colors shadow-2xs"
              >
                Go to Documents Upload
              </button>
              <button 
                type="submit" 
                disabled={!legalName || !pan || !account || !consent.extraction || !consent.registries}
                className="w-full sm:w-auto px-6 py-2.5 bg-[#002970] hover:bg-[#001b4c] disabled:opacity-50 text-white font-bold text-xs rounded-xl transition-all shadow-sm hover:shadow"
              >
                Save Details
              </button>
            </div>
          </div>
        </div>
      </form>
    </main>
  );
}

// ----------------------------------------------------------------------
// 3. View: Structured Universal Document Checklist & Dropzone
// ----------------------------------------------------------------------
interface UploadPortalProps {
  uploadedMap: Record<string, string[]>;
  allFiles: string[];
  onSelectCategory: (id: string) => void;
  onFiles: (event: ChangeEvent<HTMLInputElement>) => void;
  onDropFiles: (files: File[]) => void;
  uploads: UploadStatus[];
  onRemove: (reqId: string, file: string) => void;
  onSubmit: () => void;
  fileRef: React.RefObject<HTMLInputElement>;
  onNavigate: (view: MerchantView) => void;
  onOpenDpdp: () => void;
}

function UploadPortal({ 
  uploadedMap, 
  allFiles, 
  onSelectCategory, 
  onFiles, 
  onDropFiles,
  uploads,
  onRemove,  
  onSubmit, 
  fileRef, 
  onNavigate,
  onOpenDpdp 
}: UploadPortalProps) {
  const [filter, setFilter] = useState<'all' | 'business' | 'bank' | 'tax' | 'signatory' | 'governance'>('all');
  const [expandedReq, setExpandedReq] = useState<string | null>('business_proof');

  const filteredRequirements = filter === 'all' 
    ? documentChecklist 
    : documentChecklist.filter(r => r.category === filter);

  const completedCount = documentChecklist.filter(r => (uploadedMap[r.id] || []).length > 0).length;
  const isAllComplete = completedCount === documentChecklist.length;

  return (
    <main className="flex-1 max-w-5xl w-full mx-auto p-6 sm:p-10 flex flex-col">
      <PortalTracker current={1} />
      
      {/* Header with Navigation and DPDP Quick Link */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-6 mb-8">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[10px] font-bold uppercase tracking-widest text-[#0a5fb8] bg-[#e6f7fc] px-2.5 py-1 rounded-md border border-[#cfe9fc]">
              Stage 2 · Corporate KYC Verification
            </span>
            <button 
              onClick={onOpenDpdp}
              className="text-[10px] font-bold text-slate-600 hover:text-[#0a5fb8] bg-white border border-slate-200 hover:border-[#cfe9fc] px-2.5 py-1 rounded-md shadow-2xs flex items-center gap-1 transition-all"
            >
              <ScrollText size={12} className="text-[#0a5fb8]" /> DPDP Act Agreement
            </button>
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Upload KYC Documents</h1>
          <p className="text-sm text-slate-500 mt-1 max-w-xl">
            Please submit the {documentChecklist.length} required regulatory document proofs to activate unlimited corporate settlements.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button 
            onClick={() => onNavigate('account')}
            className="text-xs font-bold text-slate-600 bg-white border border-slate-200 px-4 py-2.5 rounded-xl shadow-2xs hover:bg-slate-50 transition-colors"
          >
            Account Center
          </button>
          <button 
            onClick={() => onNavigate('stage1')}
            className="text-xs font-bold text-slate-600 bg-white border border-slate-200 px-4 py-2.5 rounded-xl shadow-2xs hover:bg-slate-50 transition-colors"
          >
            Overview
          </button>
        </div>
      </div>

      {/* Progress & Category Filter Tabs */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 mb-6 pb-4 border-b border-slate-200">
        <div className="flex items-center gap-2 overflow-x-auto pb-2 sm:pb-0">
          <button 
            onClick={() => setFilter('all')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all whitespace-nowrap ${filter === 'all' ? 'bg-[#002970] text-white shadow-xs' : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'}`}
          >
            All Categories ({documentChecklist.length})
          </button>
          <button 
            onClick={() => setFilter('business')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all whitespace-nowrap ${filter === 'business' ? 'bg-[#002970] text-white shadow-xs' : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'}`}
          >
            1. Registration Proof
          </button>
          <button 
            onClick={() => setFilter('bank')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all whitespace-nowrap ${filter === 'bank' ? 'bg-[#002970] text-white shadow-xs' : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'}`}
          >
            2. Bank Details
          </button>
          <button 
            onClick={() => setFilter('tax')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all whitespace-nowrap ${filter === 'tax' ? 'bg-[#002970] text-white shadow-xs' : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'}`}
          >
            3. Tax & GST
          </button>
          <button 
            onClick={() => setFilter('signatory')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all whitespace-nowrap ${filter === 'signatory' ? 'bg-[#002970] text-white shadow-xs' : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'}`}
          >
            4. Signatory KYC
          </button>
          <button
            onClick={() => setFilter('governance')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all whitespace-nowrap ${filter === 'governance' ? 'bg-[#002970] text-white shadow-xs' : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'}`}
          >
            5. Company &amp; Governance
          </button>
        </div>

        <div className="flex items-center gap-3 shrink-0 self-end sm:self-auto">
          <div className="text-right">
            <span className="text-[11px] font-bold text-slate-700">{completedCount} of 4 categories ready</span>
            <div className="w-32 h-1.5 bg-slate-200 rounded-full mt-1 overflow-hidden">
              <div 
                className="h-full bg-emerald-500 transition-all duration-300"
                style={{ width: `${(completedCount / 4) * 100}%` }}
              ></div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid lg:grid-cols-[1fr_320px] gap-8 flex-1 mb-28">
        {/* Left Column: Categorized Document Cards */}
        <section className="space-y-4">
          {filteredRequirements.map((req, index) => {
            const uploadedFiles = uploadedMap[req.id] || [];
            const isCompleted = uploadedFiles.length > 0;
            const isExpanded = expandedReq === req.id;

            return (
              <div 
                key={req.id} 
                className={`bg-white rounded-2xl border transition-all overflow-hidden ${isCompleted ? 'border-emerald-200 shadow-2xs' : 'border-slate-200 shadow-2xs'}`}
              >
                {/* Card Header Bar */}
                <div className="p-5 sm:p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="flex items-start gap-4">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 border ${isCompleted ? 'bg-emerald-50 text-emerald-600 border-emerald-200' : 'bg-[#e6f7fc] text-[#0a5fb8] border-[#cfe9fc]'}`}>
                      {req.category === 'business' && <Building2 size={20} />}
                      {req.category === 'bank' && <Landmark size={20} />}
                      {req.category === 'tax' && <ReceiptText size={20} />}
                      {req.category === 'signatory' && <UserCheck size={20} />}
                      {req.category === 'governance' && <FileSignature size={20} />}
                    </div>

                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                          {req.categoryLabel}
                        </span>
                        {isCompleted && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                            <Check size={10} strokeWidth={3} /> Uploaded
                          </span>
                        )}
                      </div>
                      <h2 className="text-base font-bold text-slate-900 mt-0.5">{req.title}</h2>
                      <p className="text-xs text-slate-500 mt-0.5">{req.sampleFormats}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2.5 self-end sm:self-center">
                    <button 
                      type="button"
                      onClick={() => setExpandedReq(isExpanded ? null : req.id)}
                      className="px-3 py-2 text-xs font-semibold text-slate-600 hover:text-slate-900 bg-slate-50 hover:bg-slate-100 rounded-lg border border-slate-200 flex items-center gap-1 transition-colors"
                    >
                      {isExpanded ? <>Hide Rules <ChevronUp size={14} /></> : <>Accepted Formats <ChevronDown size={14} /></>}
                    </button>
                    
                    <button 
                      type="button"
                      onClick={() => onSelectCategory(req.id)}
                      className={`px-4 py-2 text-xs font-bold rounded-lg flex items-center gap-1.5 transition-all shadow-2xs ${isCompleted ? 'bg-slate-100 text-slate-700 hover:bg-slate-200' : 'bg-[#002970] text-white hover:bg-[#001b4c] active:bg-[#001438]'}`}
                    >
                      <UploadCloud size={14} className="text-[#00BAF2]" />
                      {isCompleted ? 'Add More' : 'Upload'}
                    </button>
                  </div>
                </div>

                {/* Uploaded Files List for this Category */}
                {uploadedFiles.length > 0 && (
                  <div className="px-5 sm:px-6 py-3 bg-emerald-50/40 border-t border-emerald-100 flex flex-wrap items-center gap-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-800 mr-1">Attached:</span>
                    {uploadedFiles.map((file) => (
                      <span key={file} className="inline-flex items-center gap-1.5 bg-white border border-emerald-200 text-slate-800 text-xs font-medium px-2.5 py-1 rounded-md shadow-2xs">
                        <FileCheck2 size={13} className="text-emerald-600" />
                        <span className="truncate max-w-[180px]">{file}</span>
                        <button 
                          onClick={() => onRemove(req.id, file)}
                          className="hover:text-red-600 p-0.5 rounded transition-colors text-slate-400"
                          title="Remove file"
                        >
                          <Trash2 size={12} />
                        </button>
                      </span>
                    ))}
                  </div>
                )}

                {/* Detailed Criteria & Accepted Documents Drawer */}
                {isExpanded && (
                  <div className="p-5 sm:p-6 bg-slate-50/70 border-t border-slate-100 space-y-4">
                    <div>
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600 mb-2 flex items-center gap-1.5">
                        <FileText size={13} className="text-[#0a5fb8]" /> Accepted Documents (Choose any one)
                      </h4>
                      <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-slate-700">
                        {req.acceptedDocuments.map((doc, idx) => (
                          <li key={idx} className="flex items-start gap-2 bg-white p-2.5 rounded-lg border border-slate-200/80">
                            <span className="w-4 h-4 rounded-full bg-[#e6f7fc] text-[#0a5fb8] text-[10px] font-bold flex items-center justify-center shrink-0 mt-0.5">
                              {idx + 1}
                            </span>
                            <span className="leading-snug">{doc}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="bg-amber-50/60 border border-amber-200/80 rounded-xl p-3.5">
                      <h4 className="text-[11px] font-bold uppercase tracking-wider text-amber-900 mb-1.5 flex items-center gap-1.5">
                        <AlertCircle size={13} className="text-amber-700" /> Mandatory Compliance Rules
                      </h4>
                      <ul className="space-y-1 text-xs text-amber-800">
                        {req.mandatoryRules.map((rule, idx) => (
                          <li key={idx} className="flex items-start gap-2">
                            <span className="text-amber-500 font-bold">•</span>
                            <span>{rule}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </section>

        {/* Right Column: Universal Quick Dropzone & DPDP Callout */}
        <aside className="space-y-6">
          {/* Universal Quick Dropzone */}
          <div 
            className="bg-white border-2 border-dashed border-slate-300 hover:border-[#00BAF2] hover:bg-[#e6f7fc]/20 transition-all rounded-2xl p-6 text-center cursor-pointer group flex flex-col items-center justify-center min-h-[260px] shadow-2xs"
            onClick={() => fileRef.current?.click()} 
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); onDropFiles(Array.from(e.dataTransfer.files)); }}
          >
            <input 
              ref={fileRef} 
              className="hidden" 
              type="file" 
              multiple 
              accept=".pdf,.png,.jpg,.jpeg" 
              onChange={onFiles} 
            />
            
            <div className="w-14 h-14 bg-[#e6f7fc] text-[#0a5fb8] rounded-2xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform border border-[#cfe9fc] shadow-2xs">
              <UploadCloud size={28} strokeWidth={1.5} />
            </div>
            <h2 className="text-base font-bold text-slate-900 mb-1">Quick Batch Upload</h2>
            <p className="text-xs text-slate-500 mb-4 max-w-[200px]">
              Drag and drop any of your documents here, or click to browse files.
            </p>
            <span className="text-[10px] font-semibold text-slate-500 bg-slate-50 border border-slate-200 px-2.5 py-1 rounded-full">
              PDF, JPG or PNG · Up to 25 MB
            </span>
          </div>

          {uploads.length > 0 && (
            <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-2xs space-y-2" aria-live="polite">
              <strong className="block text-[11px] font-extrabold uppercase tracking-wider text-slate-500">Uploads</strong>
              {uploads.slice(0, 12).map((u, i) => (
                <div key={`${u.name}-${i}`} className="flex items-start gap-2 text-xs">
                  <span className={`mt-0.5 w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold shrink-0 ${u.state === 'done' ? 'bg-emerald-100 text-emerald-700' : u.state === 'uploading' ? 'bg-[#cfe9fc] text-[#0a5fb8]' : 'bg-red-100 text-red-700'}`}>
                    {u.state === 'done' ? '✓' : u.state === 'uploading' ? '…' : '!'}
                  </span>
                  <div className="min-w-0">
                    <span className="block font-semibold text-slate-800 truncate">{u.name}</span>
                    {u.state === 'done' && <span className="block text-[10px] text-slate-500 font-mono truncate">SHA-256 {u.sha?.slice(0, 16)}… · read as {u.label}</span>}
                    {u.state === 'uploading' && <span className="block text-[10px] text-slate-500">Securing and hashing…</span>}
                    {(u.state === 'rejected' || u.state === 'error') && <span className="block text-[10px] text-red-700">{u.note}</span>}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* DPDP Act 2023 Statutory Card */}
          <div className="bg-gradient-to-br from-[#e6f7fc]/50 to-slate-50 border border-[#cfe9fc] rounded-2xl p-5 shadow-2xs">
            <div className="flex items-start gap-3 mb-3">
              <div className="p-2 rounded-lg bg-[#002970] text-[#00BAF2] shrink-0 shadow-2xs">
                <ScrollText size={18} />
              </div>
              <div>
                <strong className="block text-xs font-bold text-[#002970]">DPDP Act 2023 Compliant</strong>
                <small className="block text-[11px] text-slate-600 mt-0.5 leading-snug">
                  Data fiduciary consent &amp; sovereign registry verification.
                </small>
              </div>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed mb-4">
              Your uploaded KYC proofs are cryptographically protected and processed in compliance with the Digital Personal Data Protection Act, 2023.
            </p>
            <button 
              type="button"
              onClick={onOpenDpdp}
              className="w-full bg-white hover:bg-[#e6f7fc]/50 text-[#0a5fb8] border border-[#cfe9fc] font-bold text-xs py-2 px-3 rounded-xl transition-colors flex items-center justify-center gap-1.5 shadow-2xs"
            >
              <Eye size={13} /> View Statutory PDF Agreement
            </button>
          </div>

          <div className="flex items-center gap-2 text-[11px] text-slate-400 justify-center">
            <ShieldCheck size={14} className="text-emerald-600" />
            <span>256-bit SSL encrypted transfer</span>
          </div>
        </aside>
      </div>

      {/* Persistent Bottom Submission Bar */}
      <div className="fixed bottom-0 left-0 right-0 bg-white/95 backdrop-blur border-t border-slate-200 shadow-[0_-10px_30px_rgba(0,0,0,0.06)] p-4 sm:p-5 z-20">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-[#e6f7fc] text-[#0a5fb8] flex items-center justify-center font-bold text-xs">
              {allFiles.length}
            </div>
            <div>
              <strong className="block text-xs font-bold text-slate-900">
                {allFiles.length === 0 ? 'No documents uploaded yet' : `${allFiles.length} files attached across ${completedCount} categories`}
              </strong>
              <small className="text-[11px] text-slate-500">
                {isAllComplete ? `All ${documentChecklist.length} statutory KYC categories fulfilled.` : 'Please provide at least 1 document for each category.'}
              </small>
            </div>
          </div>

          <div className="flex items-center gap-3 w-full sm:w-auto">
            <button 
              onClick={onOpenDpdp}
              className="hidden sm:flex text-xs font-semibold text-slate-500 hover:text-slate-800 px-3 py-2"
            >
              Consent Terms
            </button>
            <button 
              className="w-full sm:w-auto shrink-0 bg-[#002970] hover:bg-[#001d52] text-white px-7 py-3 rounded-xl font-bold text-xs flex items-center justify-center gap-2 transition-all shadow-md disabled:opacity-50 disabled:cursor-not-allowed hover:-translate-y-0.5 disabled:hover:translate-y-0"
              onClick={onSubmit} 
              disabled={allFiles.length === 0}
            >
              Submit for AI Verification <ArrowRight size={15} />
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}

// ----------------------------------------------------------------------
// 4. View: Action Required / Resolution Center
// ----------------------------------------------------------------------
function ActionRequired({ onNavigate, caseData, onPickFiles, playing, onPlay }: { onNavigate: (view: MerchantView) => void; caseData: MerchantCase; onPickFiles: (files: File[]) => void; playing: boolean; onPlay: () => void }) { 
  const pickRef = useRef<HTMLInputElement>(null);
  const issues = (caseData.checks ?? []).filter((c) => (c.status === 'fail' || c.status === 'warn') && c.action !== 'escalate');
  const open = issues.length + (caseData.missing?.length ?? 0);
  const first = issues[0];
  return (
    <main className="flex-1 max-w-3xl w-full mx-auto p-6 sm:p-10">
      <PortalTracker current={2} />
      
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-6 mb-8">
        <div>
          <span className="text-[10px] font-bold uppercase tracking-widest text-[#0a5fb8] mb-3 block">Stage 2 · AI verification</span>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight mb-2">One small correction needed</h1>
          <p className="text-sm text-slate-500 leading-relaxed max-w-md">We found a difference while checking your documents. Resolve it to continue.</p>
        </div>
        <button 
          onClick={() => onNavigate('upload')}
          className="text-xs font-bold text-slate-600 bg-white border border-slate-200 px-4 py-2.5 rounded-lg shadow-sm hover:bg-slate-50 transition-colors"
        >
          View documents
        </button>
      </div>

      {caseData.cpv && <ShopVerificationCard cpv={caseData.cpv} />}

      {/* Status Banner */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center gap-4 mb-8 shadow-sm">
        <div className="relative flex items-center justify-center w-8 h-8 shrink-0">
           <div className="absolute inset-0 bg-amber-400 rounded-full animate-ping opacity-30"></div>
           <div className="relative w-8 h-8 rounded-full bg-amber-100 text-amber-600 flex items-center justify-center border border-amber-200">
             <AlertTriangle size={16} strokeWidth={2.5} />
           </div>
        </div>
        <div>
          <strong className="block text-sm font-bold text-amber-900">{open > 0 ? `⚠ Action Required: ${open} item${open === 1 ? '' : 's'} pending` : '✓ Nothing needs your action right now'}</strong>
          <p className="text-xs text-amber-700 mt-0.5 font-medium">Your application is almost complete.</p>
        </div>
      </div>

      {/* AI Clarification Card */}
      <section className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden relative">
        {/* Header */}
        <div className="p-6 sm:p-8 border-b border-slate-100 flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-red-50 text-red-600 flex items-center justify-center shrink-0 border border-red-100 shadow-sm mt-1">
            <AlertTriangle size={20} strokeWidth={2} />
          </div>
          <div>
            <span className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-[#0a5fb8] bg-[#e6f7fc] px-2.5 py-1 rounded-md mb-3 border border-[#cfe9fc]">
              <ShieldCheck size={12} /> AI Clarification
            </span>
            <h2 className="text-xl font-extrabold text-slate-900 mb-2">{first ? first.label : 'No corrections needed'}</h2>
            <p className="text-sm text-slate-600 leading-relaxed font-medium">
              {first ? first.detail : 'Karyakarta has not found anything for you to fix yet. If you have just uploaded documents, give it a minute.'}
            </p>
          </div>
        </div>

        {/* Voice Element */}
        <div className="px-6 sm:px-8 py-5 bg-slate-50 border-b border-slate-100 flex items-center gap-4">
          <button 
            className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 transition-all shadow-sm ${playing ? 'bg-[#002970] text-[#00BAF2] shadow-[#cfe9fc]' : 'bg-white text-[#002970] border border-slate-200 hover:border-[#00BAF2]'}`}
            onClick={onPlay}
          >
            {playing ? <Pause size={16} strokeWidth={3} /> : <Play size={16} strokeWidth={3} className="ml-0.5" />}
          </button>
          <div className="flex-1 min-w-0">
            <strong className="block text-xs font-bold text-slate-900 truncate">Karyakarta AI · Hindi voice note</strong>
            <span className="block text-[11px] text-slate-500 mt-0.5 font-medium truncate">
              {playing ? 'Playing voice note...' : 'नमस्ते, कृपया अपना नया पते का प्रमाण अपलोड करें...'}
            </span>
          </div>
          {playing && (
            <div className="flex items-center gap-1 shrink-0 h-4">
              <div className="w-1 bg-[#00BAF2] rounded-full animate-[bounce_1s_infinite] h-full"></div>
              <div className="w-1 bg-[#00BAF2] rounded-full animate-[bounce_1s_infinite_0.2s] h-2/3"></div>
              <div className="w-1 bg-[#00BAF2] rounded-full animate-[bounce_1s_infinite_0.4s] h-full"></div>
            </div>
          )}
          <small className="text-[10px] font-bold text-slate-400 shrink-0">0:18</small>
        </div>

        {/* Resolution Box */}
        <div className="p-6 sm:p-8">
          <div 
            className="group cursor-pointer bg-[#e6f7fc]/40 border-2 border-dashed border-[#cfe9fc] hover:border-[#00BAF2] hover:bg-[#e6f7fc]/70 rounded-xl p-6 transition-all flex items-center justify-between gap-4"
            onClick={() => pickRef.current?.click()}
          >
            <input
              ref={pickRef}
              className="hidden"
              type="file"
              multiple
              accept=".pdf,.png,.jpg,.jpeg"
              onChange={(e) => { onPickFiles(Array.from(e.target.files ?? [])); e.target.value = ''; }}
            />
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-white rounded-lg border border-[#cfe9fc] text-[#002970] flex items-center justify-center shadow-sm group-hover:scale-110 group-hover:text-[#00BAF2] transition-all shrink-0">
                <UploadCloud size={24} strokeWidth={1.5} />
              </div>
              <div>
                <strong className="block text-sm font-bold text-[#002970] mb-1">Upload recent utility bill here</strong>
                <small className="block text-xs font-medium text-slate-600">Electricity bill, rent agreement, or property tax receipt</small>
              </div>
            </div>
            <div className="w-8 h-8 rounded-full bg-[#002970] text-white flex items-center justify-center shrink-0 group-hover:bg-[#00BAF2] group-hover:text-[#002970] transition-colors">
              <ArrowRight size={16} strokeWidth={2.5} />
            </div>
          </div>
          
          <div className="mt-4 flex items-center justify-center gap-1.5 text-[10px] font-bold text-slate-400">
            <ShieldCheck size={14} /> AI will re-check the new address automatically.
          </div>
        </div>
      </section>
    </main>
  );
}

// ----------------------------------------------------------------------
// 5. Official DPDP Act 2023 Statutory Consent & PDF Agreement Modal
// ----------------------------------------------------------------------
function DpdpAgreementModal({ onClose, caseData }: { onClose: () => void; caseData: MerchantCase }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 backdrop-blur-xs p-4 sm:p-6 overflow-y-auto animate-in fade-in duration-200">
      <div className="bg-white w-full max-w-3xl rounded-2xl shadow-2xl border border-slate-200 flex flex-col max-h-[90vh] overflow-hidden">
        {/* PDF Viewer Top Action Bar */}
        <div className="bg-slate-900 text-white px-6 py-4 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-red-500/20 text-red-400 flex items-center justify-center border border-red-500/30">
              <FileText size={18} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <strong className="text-sm font-bold text-white tracking-wide">DPDP_Consent_Agreement_2026.pdf</strong>
                <span className="text-[10px] bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded font-mono border border-emerald-500/30">
                  SIGNED &amp; ENCRYPTED
                </span>
              </div>
              <p className="text-[11px] text-slate-400">Digital Personal Data Protection Act, 2023 · Standard Contractual Clauses</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button 
              onClick={() => window.print()}
              title="Print document"
              className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors hidden sm:block"
            >
              <Download size={16} />
            </button>
            <button 
              onClick={onClose}
              title="Close modal"
              className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Paper Document Canvas with Official Styling */}
        <div className="flex-1 overflow-y-auto p-6 sm:p-10 bg-slate-100/70 font-serif text-slate-800 space-y-6">
          <div className="bg-white border border-slate-300 shadow-md rounded-xl p-8 sm:p-12 relative max-w-2xl mx-auto">
            {/* Watermark */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-[0.03] select-none">
              <span className="text-8xl font-black text-slate-900 rotate-[-30deg]">DPDP 2023</span>
            </div>

            {/* Document Header & Seal */}
            <div className="border-b-2 border-slate-900 pb-6 mb-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-center sm:text-left">
              <div>
                <span className="text-[10px] font-sans font-bold tracking-[0.2em] text-slate-500 uppercase block mb-1">
                  Statutory Consent Instrument
                </span>
                <h2 className="text-xl font-bold font-sans text-slate-900">
                  CONSENT &amp; AUTHORISATION AGREEMENT
                </h2>
                <p className="text-xs font-sans text-slate-600 mt-1">
                  Pursuant to Section 6 of the Digital Personal Data Protection Act, 2023 (DPDP Act, 2023)
                </p>
              </div>

              <div className="shrink-0 flex flex-col items-center">
                <div className="w-16 h-16 rounded-full border-2 border-[#002970]/40 p-1 flex items-center justify-center">
                  <div className="w-full h-full rounded-full border border-dashed border-[#002970]/40 flex flex-col items-center justify-center text-[8px] font-sans font-extrabold text-[#002970] uppercase tracking-tighter text-center leading-none">
                    <span>GOV. OF INDIA</span>
                    <ShieldCheck size={12} className="my-0.5 text-[#002970]" />
                    <span>DPDP 2023</span>
                  </div>
                </div>
                <span className="text-[9px] font-sans text-slate-400 mt-1">Ref: DPDP-REG-2026</span>
              </div>
            </div>

            {/* Parties Summary */}
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 font-sans text-xs mb-6 grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Data Fiduciary:</span>
                <strong className="text-slate-900">Paytm Payments Services Limited / Karyakarta AI</strong>
                <p className="text-slate-500 text-[11px] mt-0.5">Licensed Payment Aggregator</p>
              </div>
              <div>
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Data Principal (Merchant):</span>
                <strong className="text-slate-900">{caseData.legalName}</strong>
                <p className="text-slate-500 text-[11px] mt-0.5">Corporate PAN: {caseData.pan || 'not provided yet'}</p>
              </div>
            </div>

            {/* Clauses */}
            <div className="space-y-5 text-xs font-serif leading-relaxed text-slate-700">
              <section>
                <h3 className="font-sans font-bold text-slate-900 uppercase text-[11px] tracking-wide mb-1">
                  1. Scope of Purpose &amp; Processing
                </h3>
                <p>
                  The Data Principal hereby grants explicit, informed, and unambiguous consent to the Data Fiduciary to collect, store, extract, organize, and process digital personal and commercial data solely for corporate merchant onboarding, customer due diligence (CDD), and anti-money laundering (AML) verification under Reserve Bank of India (RBI) Payment Aggregator guidelines.
                </p>
              </section>

              <section>
                <h3 className="font-sans font-bold text-slate-900 uppercase text-[11px] tracking-wide mb-1">
                  2. Official Government Registry Interoperability
                </h3>
                <p>
                  The Data Principal expressly authorizes automated API queries to sovereign registries including the Ministry of Corporate Affairs (MCA21), Goods and Services Tax Network (GSTN), Central Board of Direct Taxes (CBDT), and Public Financial Management System (PFMS) to authenticate certificates, directors, tax statuses, and bank accounts.
                </p>
              </section>

              <section>
                <h3 className="font-sans font-bold text-slate-900 uppercase text-[11px] tracking-wide mb-1">
                  3. Retention, Security &amp; Encryption Standard
                </h3>
                <p>
                  All uploaded documents and extracted fields are protected using AES-256 at rest and TLS 1.3 in transit within sovereign Indian data centers. Data shall not be utilized for targeted marketing, secondary profiling, or shared with unauthorized commercial intermediaries.
                </p>
              </section>

              <section>
                <h3 className="font-sans font-bold text-slate-900 uppercase text-[11px] tracking-wide mb-1">
                  4. Right to Withdraw Consent &amp; Grievance Redressal
                </h3>
                <p>
                  The Data Principal reserves the right to withdraw this consent or request data erasure under Section 12 of the DPDP Act, 2023 via the Merchant Account Center or by contacting the Data Protection Officer (DPO) at <span className="font-sans font-semibold text-[#002970]">dpo@karyakarta.ai</span>.
                </p>
              </section>
            </div>

            {/* Digital Signature Execution Box */}
            <div className="mt-8 pt-6 border-t-2 border-slate-200 font-sans flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700 flex items-center justify-center shrink-0">
                  <CheckCircle2 size={20} />
                </div>
                <div>
                  <strong className="block text-xs font-bold text-slate-900">Digitally Executed by Principal</strong>
                  <span className="block text-[11px] text-slate-500">Timestamp: {new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })} · Aadhaar OTP e-Sign</span>
                </div>
              </div>

              <div className="text-right">
                <span className="inline-block px-3 py-1 bg-slate-100 text-slate-600 rounded font-mono text-[10px] font-bold border border-slate-200">
                  HASH: 7C83-9E2B-DPDP-OK
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Modal Footer Controls */}
        <div className="bg-white border-t border-slate-200 px-6 py-4 flex flex-col sm:flex-row items-center justify-between gap-4 shrink-0">
          <div className="flex items-center gap-2 text-xs text-slate-600">
            <ShieldCheck size={16} className="text-emerald-600" />
            <span>Valid and legally binding statutory consent record under IT Act, 2000 &amp; DPDP Act, 2023.</span>
          </div>

          <div className="flex items-center gap-3 w-full sm:w-auto">
            <button 
              type="button"
              onClick={onClose}
              className="w-full sm:w-auto px-6 py-2.5 bg-[#002970] hover:bg-[#001b4c] active:bg-[#001438] text-white font-bold text-xs rounded-xl transition-all shadow-sm"
            >
              Acknowledged &amp; Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

