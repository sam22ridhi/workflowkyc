import React, { useState } from 'react';
import {
  FileText,
  Search,
  CheckCircle2,
  ExternalLink,
  Sparkles,
  Layers,
  ZoomIn,
  ZoomOut,
  Maximize2,
  FileCheck2,
  ChevronRight,
  ShieldCheck,
  AlertTriangle
} from 'lucide-react';

interface PdfBoundingBox {
  id: string;
  fieldLabel: string;
  fieldKey: string;
  value: string;
  confidence: number;
  sourceDoc: string;
  color: 'yellow' | 'purple' | 'cyan';
  // Percent coordinates for bounding box over PDF canvas
  top: number;
  left: number;
  width: number;
  height: number;
}

const boundingBoxes: PdfBoundingBox[] = [
  {
    id: 'b-legal-name',
    fieldLabel: 'Legal Business Name',
    fieldKey: 'legal_name',
    value: 'SHARMA FOODS PRIVATE LIMITED',
    confidence: 99,
    sourceDoc: 'GST Certificate · Form GST REG-06',
    color: 'purple',
    top: 26,
    left: 32,
    width: 58,
    height: 5.5,
  },
  {
    id: 'b-trade-name',
    fieldLabel: 'Trade Name',
    fieldKey: 'trade_name',
    value: 'Sharma Foods',
    confidence: 98,
    sourceDoc: 'GST Certificate · Form GST REG-06',
    color: 'yellow',
    top: 33,
    left: 32,
    width: 38,
    height: 5,
  },
  {
    id: 'b-gstin',
    fieldLabel: 'GSTIN Registration',
    fieldKey: 'gstin',
    value: '27AABCS4821Q1Z7',
    confidence: 99,
    sourceDoc: 'GST Certificate · Field 1',
    color: 'purple',
    top: 19,
    left: 32,
    width: 42,
    height: 5,
  },
  {
    id: 'b-address',
    fieldLabel: 'Principal Place of Business',
    fieldKey: 'address',
    value: '12 Mahatma Gandhi Marg, Navi Mumbai - 400703',
    confidence: 94,
    sourceDoc: 'GST Certificate · Principal Address Block',
    color: 'yellow',
    top: 48,
    left: 32,
    width: 62,
    height: 7,
  },
  {
    id: 'b-date',
    fieldLabel: 'Date of Liability / Validity',
    fieldKey: 'validity_date',
    value: '04/08/2021 · Regular Taxpayer',
    confidence: 96,
    sourceDoc: 'GST Certificate · Section 4',
    color: 'purple',
    top: 57,
    left: 32,
    width: 48,
    height: 5,
  },
];

export function PdfEvidenceViewer() {
  const [selectedBoxId, setSelectedBoxId] = useState<string>('b-address');
  const [zoomLevel, setZoomLevel] = useState<number>(100);
  const [activeDoc, setActiveDoc] = useState<'gst' | 'pan' | 'coi'>('gst');

  const activeBox = boundingBoxes.find((b) => b.id === selectedBoxId) || boundingBoxes[0];

  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 shadow-2xs overflow-hidden">
      {/* Top Document Selector Bar */}
      <div className="px-6 py-3.5 bg-slate-50 border-b border-slate-200/80 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-slate-700">Source Document:</span>
            <div className="flex items-center bg-white rounded-lg border border-slate-200 p-0.5 shadow-2xs">
              <button
                onClick={() => setActiveDoc('gst')}
                className={`px-3 py-1 rounded-md text-xs font-bold transition-all ${
                  activeDoc === 'gst'
                    ? 'bg-[#002970] text-white shadow-2xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                GST Certificate (REG-06)
              </button>
              <button
                onClick={() => setActiveDoc('pan')}
                className={`px-3 py-1 rounded-md text-xs font-bold transition-all ${
                  activeDoc === 'pan'
                    ? 'bg-[#002970] text-white shadow-2xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Company PAN
              </button>
              <button
                onClick={() => setActiveDoc('coi')}
                className={`px-3 py-1 rounded-md text-xs font-bold transition-all ${
                  activeDoc === 'coi'
                    ? 'bg-[#002970] text-white shadow-2xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Cert. of Incorporation
              </button>
            </div>
          </div>
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-slate-500 mr-1">Zoom: {zoomLevel}%</span>
          <button
            onClick={() => setZoomLevel((z) => Math.max(75, z - 15))}
            className="p-1.5 rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-100"
            title="Zoom Out"
          >
            <ZoomOut size={14} />
          </button>
          <button
            onClick={() => setZoomLevel((z) => Math.min(150, z + 15))}
            className="p-1.5 rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-100"
            title="Zoom In"
          >
            <ZoomIn size={14} />
          </button>
        </div>
      </div>

      {/* Split Screen Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 min-h-[640px]">
        {/* Left Side: Mock PDF Canvas (7 Cols) */}
        <div className="lg:col-span-7 bg-slate-100 p-6 md:p-8 flex items-center justify-center overflow-auto border-b lg:border-b-0 lg:border-r border-slate-200">
          {/* Virtual PDF Sheet */}
          <div
            style={{ transform: `scale(${zoomLevel / 100})`, transformOrigin: 'top center' }}
            className="w-full max-w-[540px] bg-white rounded-lg shadow-md border border-slate-300 p-8 relative select-none transition-transform"
          >
            {/* Government Seal & Official Header */}
            <div className="text-center pb-4 border-b-2 border-slate-800">
              <div className="w-12 h-12 mx-auto mb-2 rounded-full border-2 border-slate-800 flex items-center justify-center font-serif text-[11px] font-black text-slate-800">
                GOI
              </div>
              <h3 className="font-serif font-bold text-xs tracking-wider uppercase text-slate-900">
                Government of India
              </h3>
              <h4 className="font-serif font-extrabold text-sm tracking-wide text-slate-900 mt-0.5">
                Registration Certificate
              </h4>
              <p className="text-[9px] font-mono text-slate-600 uppercase mt-0.5">
                Registration under Goods and Services Tax Act, 2017
              </p>
            </div>

            {/* Document Body Lines */}
            <div className="space-y-4 py-6 text-[10px] font-mono text-slate-800 leading-relaxed relative">
              <div className="flex">
                <span className="w-32 text-slate-500">Registration Number:</span>
                <span className="font-bold text-slate-900">27AABCS4821Q1Z7</span>
              </div>

              <div className="flex">
                <span className="w-32 text-slate-500">Legal Name:</span>
                <span className="font-bold text-slate-900">SHARMA FOODS PRIVATE LIMITED</span>
              </div>

              <div className="flex">
                <span className="w-32 text-slate-500">Trade Name:</span>
                <span className="font-bold text-slate-900">Sharma Foods</span>
              </div>

              <div className="flex">
                <span className="w-32 text-slate-500">Constitution of Business:</span>
                <span className="font-bold text-slate-900">Private Limited Company</span>
              </div>

              <div className="flex items-start">
                <span className="w-32 text-slate-500 shrink-0">Address of Principal:</span>
                <span className="font-bold text-slate-900">
                  12 Mahatma Gandhi Marg, Navi Mumbai - 400703, Maharashtra
                </span>
              </div>

              <div className="flex">
                <span className="w-32 text-slate-500">Date of Liability:</span>
                <span className="font-bold text-slate-900">04/08/2021 · Regular Taxpayer</span>
              </div>

              <div className="flex">
                <span className="w-32 text-slate-500">Period of Validity:</span>
                <span className="font-bold text-slate-900">From 04/08/2021 To: Continuous</span>
              </div>

              {/* Watermark and Signature stamp */}
              <div className="pt-8 flex items-end justify-between text-[9px] text-slate-500">
                <div>
                  <p>State: Maharashtra</p>
                  <p>Jurisdiction: Belapur Ward</p>
                </div>
                <div className="text-right">
                  <div className="w-24 h-10 border border-slate-300 rounded flex items-center justify-center font-serif text-[8px] text-slate-400 mb-1">
                    Digitally Signed
                  </div>
                  <p className="font-bold text-slate-700">Jurisdictional Officer</p>
                </div>
              </div>

              {/* OVERLAID BOUNDING BOXES */}
              {boundingBoxes.map((box) => {
                const isSelected = selectedBoxId === box.id;
                const isPurple = box.color === 'purple';
                return (
                  <div
                    key={box.id}
                    onClick={() => setSelectedBoxId(box.id)}
                    style={{
                      top: `${box.top}%`,
                      left: `${box.left}%`,
                      width: `${box.width}%`,
                      height: `${box.height}%`,
                    }}
                    className={`absolute rounded cursor-pointer transition-all flex items-center justify-between px-1.5 ${
                      isSelected
                        ? isPurple
                          ? 'border-2 border-purple-600 bg-purple-500/25 ring-2 ring-purple-300 z-20'
                          : 'border-2 border-amber-500 bg-amber-400/30 ring-2 ring-amber-300 z-20'
                        : isPurple
                        ? 'border border-dashed border-purple-500 bg-purple-500/10 hover:bg-purple-500/20 z-10'
                        : 'border border-dashed border-amber-500 bg-amber-400/15 hover:bg-amber-400/25 z-10'
                    }`}
                  >
                    <span
                      className={`text-[8px] font-black uppercase tracking-wider px-1 py-0.2 rounded shadow-2xs ${
                        isPurple
                          ? 'bg-purple-700 text-white'
                          : 'bg-amber-600 text-white'
                      }`}
                    >
                      AI: {box.confidence}%
                    </span>
                    <span className="text-[7px] font-extrabold text-slate-800 hidden sm:inline">
                      {box.fieldKey}
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Bounding box legend footer inside canvas */}
            <div className="mt-4 pt-3 border-t border-slate-200 flex items-center justify-between text-[10px] text-slate-500">
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded bg-purple-500/40 border border-purple-600" />
                <span>Purple: Sovereign Verified Entity</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded bg-amber-400/40 border border-amber-500" />
                <span>Yellow: Attention / Exception</span>
              </span>
            </div>
          </div>
        </div>

        {/* Right Side: Extracted Entities & Confidence Scores (5 Cols) */}
        <div className="lg:col-span-5 p-6 md:p-8 flex flex-col justify-between bg-white">
          <div>
            {/* Header of entity panel */}
            <div className="flex items-center justify-between pb-4 border-b border-slate-200/80 mb-6">
              <div>
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="text-[10px] font-extrabold uppercase tracking-widest text-[#00BAF2] bg-[#e6f7fc] px-2 py-0.5 rounded-full border border-[#cfe9fc]">
                    OCR &amp; Entity Extractor
                  </span>
                  <span className="text-xs text-slate-400">· 5 Entities</span>
                </div>
                <h3 className="text-lg font-extrabold text-[#002970]">
                  Extracted Entities &amp; Confidence
                </h3>
              </div>
              <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 border border-emerald-200 flex items-center justify-center font-bold text-xs">
                ✓ AI
              </div>
            </div>

            {/* Active Selected Entity Highlight Card */}
            <div className="p-4 rounded-xl bg-purple-50/60 border border-purple-200 mb-6 shadow-2xs">
              <div className="flex items-center justify-between text-xs mb-1.5">
                <span className="font-extrabold text-purple-900 uppercase tracking-wide text-[10px]">
                  Focused Document Region
                </span>
                <span className="px-2 py-0.5 rounded-full bg-purple-600 text-white font-extrabold text-[10px]">
                  {activeBox.confidence}% Confidence
                </span>
              </div>
              <strong className="block text-sm font-bold text-slate-900 mb-1">
                {activeBox.fieldLabel}
              </strong>
              <div className="p-2.5 bg-white rounded-lg border border-purple-200 font-mono text-xs font-semibold text-slate-800 break-words mb-2">
                &ldquo;{activeBox.value}&rdquo;
              </div>
              <p className="text-[11px] text-purple-900/80 leading-snug">
                Extracted from <strong>{activeBox.sourceDoc}</strong> with bounding coordinates.
              </p>
            </div>

            {/* List of all 5 entities */}
            <div className="space-y-2.5">
              <span className="text-[11px] font-extrabold text-slate-500 uppercase tracking-wider block">
                All Extracted Fields (Click to highlight in viewer)
              </span>

              {boundingBoxes.map((box) => {
                const isSelected = selectedBoxId === box.id;
                const isAddress = box.fieldKey === 'address';

                return (
                  <div
                    key={box.id}
                    onClick={() => setSelectedBoxId(box.id)}
                    className={`p-3.5 rounded-xl border transition-all cursor-pointer flex items-center justify-between gap-3 ${
                      isSelected
                        ? 'border-purple-500 bg-purple-50/40 ring-1 ring-purple-400'
                        : 'border-slate-200 hover:border-slate-300 bg-white hover:bg-slate-50/50'
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-0.5">
                        <strong className="text-xs font-bold text-slate-900 truncate">
                          {box.fieldLabel}
                        </strong>
                        {isAddress && (
                          <span className="text-[9px] font-extrabold px-1.5 py-0.2 rounded bg-amber-100 text-amber-800 border border-amber-300">
                            Drift Flag
                          </span>
                        )}
                      </div>
                      <span className="block text-[11px] font-mono text-slate-600 truncate">
                        {box.value}
                      </span>
                    </div>

                    <div className="text-right shrink-0">
                      <div className="flex items-center gap-1 justify-end font-bold text-xs text-emerald-700">
                        <CheckCircle2 size={13} className="text-emerald-600" />
                        <span>{box.confidence}%</span>
                      </div>
                      <small className="text-[9px] text-slate-400">Score</small>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Verification Badge Footer */}
          <div className="pt-6 mt-6 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span className="flex items-center gap-1.5 font-medium">
              <ShieldCheck size={16} className="text-[#00BAF2]" />
              Cryptographically timestamped by Karyakarta OCR.
            </span>
            <span className="font-bold text-[#002970]">v2.4 Engine</span>
          </div>
        </div>
      </div>
    </div>
  );
}
