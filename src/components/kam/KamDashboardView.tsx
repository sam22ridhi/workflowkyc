import React, { useState } from 'react';
import {
  ArrowRight,
  Clock,
  Sparkles,
  AlertCircle,
  CheckCircle2,
  FileCheck2,
  Search,
  Filter,
  ArrowUpRight,
  TrendingUp,
  ShieldCheck,
  Building2,
  Timer,
  ChevronRight,
  FileWarning
} from 'lucide-react';
import type { MerchantCase } from '@/types/case';

export interface CasePipelineItem {
  id: string;
  merchantName: string;
  legalName: string;
  entityType: 'Private Limited' | 'Public Limited' | 'LLP' | 'Proprietorship';
  stage: 'Documents Pending' | 'AI Verifying' | 'Awaiting Merchant Action' | 'Ready for Review' | 'Live / Approved';
  aiFlag: 'No Issues' | 'Address Drift' | 'Missing Signatory' | 'Registry Match (MCA)' | 'Low OCR Confidence';
  aiConfidence: number;
  slaMinutes: number;
  isUrgent?: boolean;
}

export const mockPipelineCases: CasePipelineItem[] = [
  {
    id: 'KYB-20814',
    merchantName: 'Sharma Foods Pvt Ltd',
    legalName: 'Sharma Foods Private Limited',
    entityType: 'Private Limited',
    stage: 'Awaiting Merchant Action',
    aiFlag: 'Address Drift',
    aiConfidence: 91,
    slaMinutes: 18,
    isUrgent: true,
  },
  {
    id: 'KYB-20815',
    merchantName: 'Bharat Agri Logistics',
    legalName: 'Bharat Agri Logistics LLP',
    entityType: 'LLP',
    stage: 'AI Verifying',
    aiFlag: 'Registry Match (MCA)',
    aiConfidence: 98,
    slaMinutes: 45,
  },
  {
    id: 'KYB-20816',
    merchantName: 'Zenith Tech Solutions',
    legalName: 'Zenith Technologies Pvt Ltd',
    entityType: 'Private Limited',
    stage: 'Ready for Review',
    aiFlag: 'No Issues',
    aiConfidence: 99,
    slaMinutes: 12,
  },
  {
    id: 'KYB-20817',
    merchantName: 'Royal Rajasthan Spices',
    legalName: 'Royal Rajasthan Spices Proprietorship',
    entityType: 'Proprietorship',
    stage: 'Documents Pending',
    aiFlag: 'Missing Signatory',
    aiConfidence: 84,
    slaMinutes: 8,
    isUrgent: true,
  },
  {
    id: 'KYB-20818',
    merchantName: 'Apex Cloud Telecom',
    legalName: 'Apex Cloud Telecom Limited',
    entityType: 'Public Limited',
    stage: 'Ready for Review',
    aiFlag: 'No Issues',
    aiConfidence: 97,
    slaMinutes: 52,
  },
];

interface KamDashboardViewProps {
  caseData: MerchantCase;
  onOpenCase: (caseId?: string) => void;
}

export function KamDashboardView({ caseData, onOpenCase }: KamDashboardViewProps) {
  const [filterStage, setFilterStage] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState<string>('');

  const filteredCases = mockPipelineCases.filter((c) => {
    const matchesSearch =
      c.merchantName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.id.toLowerCase().includes(searchTerm.toLowerCase());
    if (filterStage === 'all') return matchesSearch;
    if (filterStage === 'urgent') return matchesSearch && c.isUrgent;
    return matchesSearch && c.stage === filterStage;
  });

  return (
    <div className="p-6 md:p-8 space-y-8 max-w-7xl mx-auto w-full">
      {/* Welcome & Pipeline Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-[10px] font-extrabold uppercase tracking-widest text-[#00BAF2] bg-[#e6f7fc] px-2.5 py-0.5 rounded-full border border-[#cfe9fc]">
              Real-time Portfolio
            </span>
            <span className="text-xs text-slate-500 font-medium">Updated 30s ago</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-extrabold text-[#002970] tracking-tight">
            Welcome, Priya. Here is your pipeline.
          </h1>
          <p className="text-xs md:text-sm text-slate-600 mt-1 font-medium">
            Karyakarta AI autonomously parses incoming documents, identifies registry discrepancies, and prepares checker-ready files.
          </p>
        </div>

        {/* Global Action Button */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => onOpenCase('KYB-20814')}
            className="px-4 py-2.5 bg-[#002970] hover:bg-[#001b4c] text-white text-xs font-bold rounded-xl transition-all shadow-sm flex items-center gap-2"
          >
            <Sparkles size={14} className="text-[#00BAF2]" />
            <span>Open Priority Case (Sharma Foods)</span>
            <ArrowRight size={14} />
          </button>
        </div>
      </div>

      {/* Grid of 5 KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3.5 md:gap-4">
        {/* Card 1: Total Open Cases */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-2xs hover:shadow-xs transition-shadow">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-[11px] font-bold tracking-wide">Total Open Cases</span>
            <div className="w-7 h-7 rounded-lg bg-slate-100 flex items-center justify-center text-slate-700">
              <Building2 size={15} />
            </div>
          </div>
          <div className="text-2xl md:text-3xl font-extrabold text-[#002970] tracking-tight">
            42
          </div>
          <div className="text-[11px] font-semibold text-slate-500 mt-1 flex items-center gap-1">
            <TrendingUp size={12} className="text-emerald-500" />
            <span className="text-emerald-600 font-bold">+8</span> new this week
          </div>
        </div>

        {/* Card 2: Pending AI Verification */}
        <div className="bg-white p-5 rounded-2xl border border-[#cfe9fc] bg-gradient-to-br from-white to-[#f0f9fd] shadow-2xs hover:shadow-xs transition-shadow">
          <div className="flex items-center justify-between text-[#002970] mb-2">
            <span className="text-[11px] font-bold tracking-wide">Pending AI Verification</span>
            <div className="w-7 h-7 rounded-lg bg-[#e6f7fc] text-[#00BAF2] flex items-center justify-center">
              <Sparkles size={15} />
            </div>
          </div>
          <div className="text-2xl md:text-3xl font-extrabold text-[#00BAF2] tracking-tight">
            14
          </div>
          <div className="text-[11px] font-semibold text-slate-500 mt-1">
            Avg processing: <strong className="text-slate-800">42 sec</strong>
          </div>
        </div>

        {/* Card 3: Awaiting Merchant Action */}
        <div className="bg-white p-5 rounded-2xl border border-amber-200/80 bg-gradient-to-br from-white to-amber-50/30 shadow-2xs hover:shadow-xs transition-shadow">
          <div className="flex items-center justify-between text-amber-700 mb-2">
            <span className="text-[11px] font-bold tracking-wide">Awaiting Merchant</span>
            <div className="w-7 h-7 rounded-lg bg-amber-100/70 text-amber-600 flex items-center justify-center">
              <Clock size={15} />
            </div>
          </div>
          <div className="text-2xl md:text-3xl font-extrabold text-amber-600 tracking-tight">
            8
          </div>
          <div className="text-[11px] font-semibold text-amber-800/80 mt-1">
            Voice Chase queued: <strong className="font-bold">3</strong>
          </div>
        </div>

        {/* Card 4: Ready for Submission */}
        <div className="bg-white p-5 rounded-2xl border border-emerald-200/80 bg-gradient-to-br from-white to-emerald-50/30 shadow-2xs hover:shadow-xs transition-shadow">
          <div className="flex items-center justify-between text-emerald-800 mb-2">
            <span className="text-[11px] font-bold tracking-wide">Ready for Submission</span>
            <div className="w-7 h-7 rounded-lg bg-emerald-100/70 text-emerald-600 flex items-center justify-center">
              <CheckCircle2 size={15} />
            </div>
          </div>
          <div className="text-2xl md:text-3xl font-extrabold text-emerald-700 tracking-tight">
            17
          </div>
          <div className="text-[11px] font-semibold text-emerald-800/80 mt-1">
            100% pre-filled &amp; validated
          </div>
        </div>

        {/* Card 5: Escalations (Red) */}
        <div className="bg-white p-5 rounded-2xl border border-rose-200 bg-gradient-to-br from-white to-rose-50/40 shadow-2xs hover:shadow-xs transition-shadow col-span-2 lg:col-span-1">
          <div className="flex items-center justify-between text-rose-700 mb-2">
            <span className="text-[11px] font-bold tracking-wide">Escalations (Red)</span>
            <div className="w-7 h-7 rounded-lg bg-rose-100 text-rose-600 flex items-center justify-center">
              <AlertCircle size={15} />
            </div>
          </div>
          <div className="text-2xl md:text-3xl font-extrabold text-rose-600 tracking-tight">
            3
          </div>
          <div className="text-[11px] font-semibold text-rose-700/80 mt-1">
            SLA breach risk &lt; 20m
          </div>
        </div>
      </div>

      {/* All Cases Table Section */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-2xs overflow-hidden">
        {/* Table Toolbar */}
        <div className="p-5 border-b border-slate-200/70 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <h2 className="text-base font-extrabold text-[#002970]">
              All Cases ({filteredCases.length})
            </h2>
            <div className="flex items-center gap-1.5 bg-slate-100 p-1 rounded-xl text-xs font-bold">
              <button
                onClick={() => setFilterStage('all')}
                className={`px-3 py-1 rounded-lg transition-all ${
                  filterStage === 'all'
                    ? 'bg-white text-[#002970] shadow-2xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                All
              </button>
              <button
                onClick={() => setFilterStage('urgent')}
                className={`px-3 py-1 rounded-lg transition-all ${
                  filterStage === 'urgent'
                    ? 'bg-rose-50 text-rose-700 shadow-2xs font-extrabold'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Urgent (2)
              </button>
              <button
                onClick={() => setFilterStage('Ready for Review')}
                className={`px-3 py-1 rounded-lg transition-all ${
                  filterStage === 'Ready for Review'
                    ? 'bg-emerald-50 text-emerald-700 shadow-2xs font-extrabold'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Ready
              </button>
            </div>
          </div>

          {/* Search Input */}
          <div className="relative w-full sm:w-72">
            <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search merchant or case ID..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:border-[#00BAF2] focus:bg-white transition-all"
            />
          </div>
        </div>

        {/* Data Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/70 border-b border-slate-200 text-[11px] font-extrabold text-slate-500 uppercase tracking-wider">
                <th className="py-3 px-5">Merchant Name</th>
                <th className="py-3 px-4">Entity Type</th>
                <th className="py-3 px-4">Current Stage</th>
                <th className="py-3 px-4">AI Flag</th>
                <th className="py-3 px-4">SLA Timer</th>
                <th className="py-3 px-5 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs">
              {filteredCases.map((c) => (
                <tr
                  key={c.id}
                  className="hover:bg-slate-50/60 transition-colors group cursor-pointer"
                  onClick={() => onOpenCase(c.id)}
                >
                  {/* Merchant Name */}
                  <td className="py-4 px-5">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-[#002970] text-[#00BAF2] font-black text-xs flex items-center justify-center shrink-0">
                        {c.merchantName.slice(0, 2).toUpperCase()}
                      </div>
                      <div>
                        <strong className="block text-xs font-bold text-slate-900 group-hover:text-[#002970]">
                          {c.merchantName}
                        </strong>
                        <small className="block text-[10px] text-slate-500">
                          {c.id} · {c.legalName}
                        </small>
                      </div>
                    </div>
                  </td>

                  {/* Entity Type */}
                  <td className="py-4 px-4 font-semibold text-slate-700">
                    <span className="px-2 py-0.5 rounded-md bg-slate-100 text-[11px] font-medium text-slate-600 border border-slate-200">
                      {c.entityType}
                    </span>
                  </td>

                  {/* Current Stage */}
                  <td className="py-4 px-4">
                    <StagePill stage={c.stage} />
                  </td>

                  {/* AI Flag */}
                  <td className="py-4 px-4">
                    <AiFlagPill flag={c.aiFlag} confidence={c.aiConfidence} />
                  </td>

                  {/* SLA Timer */}
                  <td className="py-4 px-4">
                    <div className="flex items-center gap-1.5 font-bold">
                      <Timer
                        size={14}
                        className={c.slaMinutes < 20 ? 'text-rose-500 animate-pulse' : 'text-slate-400'}
                      />
                      <span className={c.slaMinutes < 20 ? 'text-rose-600 font-extrabold' : 'text-slate-600'}>
                        {c.slaMinutes}m left
                      </span>
                    </div>
                  </td>

                  {/* Action Link */}
                  <td className="py-4 px-5 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onOpenCase(c.id);
                      }}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-white border border-slate-200 hover:border-[#00BAF2] hover:text-[#002970] text-slate-700 text-xs font-bold transition-all shadow-2xs group-hover:bg-[#002970] group-hover:text-white group-hover:border-[#002970]"
                    >
                      <span>View Case</span>
                      <ArrowRight size={13} className="text-[#00BAF2]" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Table Footer */}
        <div className="p-4 bg-slate-50/50 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500 font-medium">
          <span>Showing 5 of 42 corporate accounts</span>
          <span className="flex items-center gap-1.5">
            <ShieldCheck size={14} className="text-emerald-600" />
            Registry synchronization active across MCA21, GSTN, and CBDT.
          </span>
        </div>
      </div>
    </div>
  );
}

function StagePill({ stage }: { stage: CasePipelineItem['stage'] }) {
  if (stage === 'Ready for Review') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
        Ready for Review
      </span>
    );
  }
  if (stage === 'AI Verifying') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold bg-[#e6f7fc] text-[#002970] border border-[#cfe9fc]">
        <Sparkles size={11} className="text-[#00BAF2]" />
        AI Verifying
      </span>
    );
  }
  if (stage === 'Awaiting Merchant Action') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold bg-amber-50 text-amber-800 border border-amber-200">
        <Clock size={11} className="text-amber-600" />
        Awaiting Merchant
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold bg-slate-100 text-slate-700 border border-slate-200">
      <FileWarning size={11} className="text-slate-500" />
      {stage}
    </span>
  );
}

function AiFlagPill({
  flag,
  confidence,
}: {
  flag: CasePipelineItem['aiFlag'];
  confidence: number;
}) {
  if (flag === 'Address Drift') {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-bold bg-rose-50 text-rose-800 border border-rose-200">
        <AlertCircle size={12} className="text-rose-600" />
        <span>Address Drift</span>
        <span className="text-rose-500 font-normal">({confidence}%)</span>
      </span>
    );
  }
  if (flag === 'Missing Signatory') {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-bold bg-amber-50 text-amber-800 border border-amber-200">
        <AlertCircle size={12} className="text-amber-600" />
        <span>Missing Signatory</span>
      </span>
    );
  }
  if (flag === 'Registry Match (MCA)') {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-bold bg-blue-50 text-blue-800 border border-blue-200">
        <ShieldCheck size={12} className="text-blue-600" />
        <span>MCA Matched ({confidence}%)</span>
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
      <CheckCircle2 size={12} className="text-emerald-600" />
      <span>Verified ({confidence}%)</span>
    </span>
  );
}
