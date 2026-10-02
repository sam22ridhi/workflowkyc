import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import * as pdfjs from 'pdfjs-dist';
import workerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  FileSearch,
  Loader2,
  ShieldCheck,
  TriangleAlert,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import {
  documentUrl,
  useLiveResource,
  type CaseDocumentRecord,
  type CrmForm,
  type EvidenceBox,
  type ExtractedField,
} from '@/services/api';

pdfjs.GlobalWorkerOptions.workerSrc = workerSrc;

export interface EvidenceFocus {
  docId: string;
  field: string;
}

interface PdfEvidenceViewerProps {
  caseId: string;
  focus?: EvidenceFocus | null;
}

interface OverlayBox {
  id: string; // `${field}` or `${field}#${row}`
  field: string;
  label: string;
  box: EvidenceBox;
  confidence: number | null;
  flagged: boolean;
}

const BASE_WIDTH = 600;

const prettify = (key: string) => key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  if (Array.isArray(value)) {
    return value
      .map((row) => (row && typeof row === 'object' ? Object.values(row as Record<string, unknown>).filter(Boolean).join(' · ') : String(row)))
      .join('  |  ');
  }
  return String(value);
}

/** The real uploaded file: a PDF page rendered with pdf.js, or an image, with the overlay on top. */
function DocumentPage({
  doc, page, width, children, onPageCount,
}: { doc: CaseDocumentRecord; page: number; width: number; children: ReactNode; onPageCount: (n: number) => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const isPdf = doc.mime === 'application/pdf';

  useEffect(() => {
    if (!isPdf) return;
    let cancelled = false;
    setState('loading');
    const task = pdfjs.getDocument({ url: documentUrl(doc) });
    (async () => {
      try {
        const pdf = await task.promise;
        if (cancelled) return;
        onPageCount(pdf.numPages);
        const pg = await pdf.getPage(Math.min(Math.max(page, 1), pdf.numPages));
        const viewport = pg.getViewport({ scale: (BASE_WIDTH * 2) / pg.getViewport({ scale: 1 }).width });
        const canvas = canvasRef.current;
        if (!canvas || cancelled) return;
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        await pg.render({ canvasContext: canvas.getContext('2d')!, viewport }).promise;
        if (!cancelled) setState('ready');
      } catch {
        if (!cancelled) setState('error');
      }
    })();
    return () => {
      cancelled = true;
      void task.destroy();
    };
  }, [doc.doc_id, doc.file_url, page, isPdf]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="relative bg-white shadow-md border border-slate-300 rounded-sm select-none" style={{ width }}>
      {isPdf ? (
        <canvas ref={canvasRef} className="block w-full h-auto" />
      ) : (
        <img src={documentUrl(doc)} alt={doc.filename} className="block w-full h-auto" onLoad={() => setState('ready')} onError={() => setState('error')} />
      )}
      {state === 'loading' && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/70 text-slate-500 text-xs gap-2">
          <Loader2 size={16} className="animate-spin" /> Loading document…
        </div>
      )}
      {state === 'error' && (
        <div className="absolute inset-0 flex items-center justify-center bg-white text-rose-600 text-xs font-semibold p-6 text-center">
          The stored file could not be displayed.
        </div>
      )}
      {state === 'ready' && <div className="absolute inset-0">{children}</div>}
    </div>
  );
}

export function PdfEvidenceViewer({ caseId, focus }: PdfEvidenceViewerProps) {
  const docs = useLiveResource<CaseDocumentRecord[]>(caseId, `/api/cases/${caseId}/documents`);
  const crm = useLiveResource<CrmForm>(caseId, `/api/cases/${caseId}/crm-form`);

  const [activeDocId, setActiveDocId] = useState<string | null>(null);
  const [selectedField, setSelectedField] = useState<string | null>(null);
  const [zoom, setZoom] = useState(100);
  const [page, setPage] = useState(1);
  const [pageCount, setPageCount] = useState(1);

  const documents = docs.data ?? [];
  const readable = documents.filter((d) => d.fields);
  const activeDoc = documents.find((d) => d.doc_id === activeDocId) ?? readable[0] ?? documents[0] ?? null;

  // Jump here from the CRM form ("view evidence") or pick the first readable doc.
  useEffect(() => {
    if (focus) {
      setActiveDocId(focus.docId);
      setSelectedField(focus.field);
    }
  }, [focus]);

  useEffect(() => {
    setPage(1);
    setPageCount(1);
  }, [activeDoc?.doc_id]);

  const flaggedFields = useMemo(() => {
    const set = new Set<string>();
    crm.data?.sections.forEach((s) => s.fields.forEach((f) => {
      if (f.status === 'conflict' && f.doc_id && f.field) set.add(`${f.doc_id}:${f.field}`);
    }));
    return set;
  }, [crm.data]);

  const fields = useMemo(() => Object.entries(activeDoc?.fields ?? {}), [activeDoc]);
  const isFlagged = (key: string) => !!activeDoc && flaggedFields.has(`${activeDoc.doc_id}:${key}`);

  const overlay: OverlayBox[] = useMemo(() => {
    const out: OverlayBox[] = [];
    for (const [key, f] of fields) {
      const boxes: EvidenceBox[] = f.boxes?.length ? f.boxes : f.box ? [f.box] : [];
      // list fields at table precision all share one table box: draw it once
      const unique = f.box_precision === 'table' ? boxes.slice(0, 1) : boxes;
      unique.forEach((b, i) => out.push({ id: `${key}#${i}`, field: key, label: prettify(key), box: b, confidence: f.confidence, flagged: isFlagged(key) }));
    }
    return out.filter((o) => o.box.page === page);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fields, page, flaggedFields]);

  const select = (key: string) => {
    setSelectedField(key);
    const f = activeDoc?.fields?.[key];
    const target = f?.box?.page ?? f?.boxes?.[0]?.page ?? f?.page;
    if (target) setPage(target);
  };

  const selected: [string, ExtractedField] | undefined = fields.find(([k]) => k === selectedField) ?? fields[0];
  const located = fields.filter(([, f]) => f.box || f.boxes?.length).length;

  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 shadow-2xs overflow-hidden">
      {/* Document selector + zoom */}
      <div className="px-6 py-3.5 bg-slate-50 border-b border-slate-200/80 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-bold text-slate-700">Source Document:</span>
          <div className="flex items-center flex-wrap bg-white rounded-lg border border-slate-200 p-0.5 shadow-2xs">
            {documents.length === 0 && <span className="px-3 py-1 text-xs text-slate-400">No documents yet</span>}
            {documents.map((d) => (
              <button
                key={d.doc_id}
                onClick={() => { setActiveDocId(d.doc_id); setSelectedField(null); }}
                title={d.filename}
                className={`px-3 py-1 rounded-md text-xs font-bold transition-all flex items-center gap-1.5 ${
                  activeDoc?.doc_id === d.doc_id ? 'bg-[#002970] text-white shadow-2xs' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {d.status === 'extracting' || d.status === 'received' ? <Loader2 size={11} className="animate-spin" /> : d.status === 'error' ? <TriangleAlert size={11} className="text-rose-500" /> : null}
                {d.doc_type_label}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {pageCount > 1 && (
            <div className="flex items-center gap-1 mr-2 text-xs text-slate-600">
              <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="p-1.5 rounded-lg border border-slate-200 bg-white disabled:opacity-40"><ChevronLeft size={14} /></button>
              <span>Page {page} / {pageCount}</span>
              <button disabled={page >= pageCount} onClick={() => setPage((p) => p + 1)} className="p-1.5 rounded-lg border border-slate-200 bg-white disabled:opacity-40"><ChevronRight size={14} /></button>
            </div>
          )}
          <span className="text-xs font-medium text-slate-500 mr-1">Zoom: {zoom}%</span>
          <button onClick={() => setZoom((z) => Math.max(60, z - 15))} className="p-1.5 rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-100" title="Zoom Out"><ZoomOut size={14} /></button>
          <button onClick={() => setZoom((z) => Math.min(180, z + 15))} className="p-1.5 rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-100" title="Zoom In"><ZoomIn size={14} /></button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 min-h-[640px]">
        {/* Left: the real uploaded file */}
        <div className="lg:col-span-7 bg-slate-100 p-6 md:p-8 overflow-auto border-b lg:border-b-0 lg:border-r border-slate-200 max-h-[820px]">
          {docs.loading && <div className="text-xs text-slate-500 flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> Loading documents…</div>}
          {docs.error && <div className="text-xs text-rose-600 font-semibold">Could not reach the backend: {docs.error}</div>}
          {!docs.loading && !docs.error && !activeDoc && (
            <div className="text-center text-slate-500 text-sm py-24"><FileSearch className="mx-auto mb-3 text-slate-400" /> The merchant hasn&rsquo;t uploaded any documents yet.</div>
          )}
          {activeDoc && (
            <div className="flex justify-center">
              <DocumentPage doc={activeDoc} page={page} width={(BASE_WIDTH * zoom) / 100} onPageCount={setPageCount}>
                {overlay.map((o) => {
                  const isSelected = selected?.[0] === o.field;
                  const tone = o.flagged ? 'amber' : 'purple';
                  return (
                    <div
                      key={o.id}
                      onClick={() => select(o.field)}
                      title={`${o.label}${o.box.precision === 'table' ? ' (table region)' : ''}`}
                      style={{ left: `${o.box.x * 100}%`, top: `${o.box.y * 100}%`, width: `${o.box.w * 100}%`, height: `${o.box.h * 100}%` }}
                      className={`absolute rounded cursor-pointer transition-all flex items-start justify-between px-1 ${
                        isSelected
                          ? tone === 'purple' ? 'border-2 border-purple-600 bg-purple-500/25 ring-2 ring-purple-300 z-20' : 'border-2 border-amber-500 bg-amber-400/30 ring-2 ring-amber-300 z-20'
                          : tone === 'purple' ? 'border border-dashed border-purple-500 bg-purple-500/10 hover:bg-purple-500/20 z-10' : 'border border-dashed border-amber-500 bg-amber-400/15 hover:bg-amber-400/25 z-10'
                      }`}
                    >
                      {isSelected && o.confidence !== null && (
                        <span className={`-mt-3 text-[8px] font-black uppercase tracking-wider px-1 rounded shadow-2xs ${tone === 'purple' ? 'bg-purple-700 text-white' : 'bg-amber-600 text-white'}`}>
                          AI: {Math.round(o.confidence)}%
                        </span>
                      )}
                    </div>
                  );
                })}
              </DocumentPage>
            </div>
          )}
          {activeDoc && (
            <div className="mt-4 pt-3 border-t border-slate-200 flex items-center justify-between text-[10px] text-slate-500 max-w-[640px] mx-auto">
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded bg-purple-500/40 border border-purple-600" /> Extracted field</span>
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded bg-amber-400/40 border border-amber-500" /> Conflict with another source</span>
            </div>
          )}
        </div>

        {/* Right: extracted entities */}
        <div className="lg:col-span-5 p-6 md:p-8 flex flex-col justify-between bg-white">
          <div>
            <div className="flex items-center justify-between pb-4 border-b border-slate-200/80 mb-6">
              <div>
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="text-[10px] font-extrabold uppercase tracking-widest text-[#00BAF2] bg-[#e6f7fc] px-2 py-0.5 rounded-full border border-[#cfe9fc]">OCR &amp; Entity Extractor</span>
                  <span className="text-xs text-slate-400">· {fields.length} Entities</span>
                </div>
                <h3 className="text-lg font-extrabold text-[#002970]">Extracted Entities &amp; Confidence</h3>
                {activeDoc && <p className="text-[11px] text-slate-500 mt-0.5 font-mono truncate max-w-[320px]">{activeDoc.filename} · SHA-256 {activeDoc.sha256.slice(0, 12)}…</p>}
              </div>
              <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 border border-emerald-200 flex items-center justify-center font-bold text-xs">✓ AI</div>
            </div>

            {activeDoc?.status === 'error' && <div className="mb-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 font-semibold">Extraction failed: {activeDoc.error}</div>}
            {activeDoc && !activeDoc.fields && activeDoc.status !== 'error' && (
              <div className="mb-4 p-3 rounded-xl bg-[#e6f7fc] border border-[#cfe9fc] text-xs text-[#002970] font-semibold flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> Karyakarta is reading this document…</div>
            )}

            {selected && (
              <div className="p-4 rounded-xl bg-purple-50/60 border border-purple-200 mb-6 shadow-2xs">
                <div className="flex items-center justify-between text-xs mb-1.5">
                  <span className="font-extrabold text-purple-900 uppercase tracking-wide text-[10px]">Focused Document Region</span>
                  {selected[1].confidence !== null && <span className="px-2 py-0.5 rounded-full bg-purple-600 text-white font-extrabold text-[10px]">{Math.round(selected[1].confidence)}% Confidence</span>}
                </div>
                <strong className="block text-sm font-bold text-slate-900 mb-1">{prettify(selected[0])}</strong>
                <div className="p-2.5 bg-white rounded-lg border border-purple-200 font-mono text-xs font-semibold text-slate-800 break-words mb-2">&ldquo;{displayValue(selected[1].value)}&rdquo;</div>
                <p className="text-[11px] text-purple-900/80 leading-snug">
                  Extracted from <strong>{activeDoc?.doc_type_label}</strong>{selected[1].page ? <> · page {selected[1].page}</> : null}
                  {selected[1].box || selected[1].boxes?.length
                    ? selected[1].box_precision === 'table' ? ' · highlighted at table level (Sarvam does not localise individual rows).' : ' with bounding coordinates.'
                    : ' · no position available for this field on the page.'}
                </p>
              </div>
            )}

            <div className="space-y-2.5">
              <span className="text-[11px] font-extrabold text-slate-500 uppercase tracking-wider block">All Extracted Fields (Click to highlight in viewer)</span>
              {fields.map(([key, f]) => {
                const isSelected = selected?.[0] === key;
                const flagged = isFlagged(key);
                const hasBox = !!(f.box || f.boxes?.length);
                return (
                  <div
                    key={key}
                    onClick={() => select(key)}
                    className={`p-3.5 rounded-xl border transition-all cursor-pointer flex items-center justify-between gap-3 ${
                      isSelected ? 'border-purple-500 bg-purple-50/40 ring-1 ring-purple-400' : 'border-slate-200 hover:border-slate-300 bg-white hover:bg-slate-50/50'
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-0.5">
                        <strong className="text-xs font-bold text-slate-900 truncate">{prettify(key)}</strong>
                        {flagged && <span className="text-[9px] font-extrabold px-1.5 rounded bg-amber-100 text-amber-800 border border-amber-300">Conflict</span>}
                        {!hasBox && f.value ? <span className="text-[9px] font-semibold px-1.5 rounded bg-slate-100 text-slate-500 border border-slate-200">not located</span> : null}
                      </div>
                      <span className="block text-[11px] font-mono text-slate-600 truncate">{displayValue(f.value)}</span>
                    </div>
                    <div className="text-right shrink-0">
                      {f.confidence !== null && (
                        <div className="flex items-center gap-1 justify-end font-bold text-xs text-emerald-700"><CheckCircle2 size={13} className="text-emerald-600" /><span>{Math.round(f.confidence)}%</span></div>
                      )}
                      <small className="text-[9px] text-slate-400">Score</small>
                    </div>
                  </div>
                );
              })}
              {activeDoc?.fields && <p className="text-[10px] text-slate-400">{located}/{fields.length} fields located on the page.</p>}
            </div>
          </div>

          <div className="pt-6 mt-6 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span className="flex items-center gap-1.5 font-medium"><ShieldCheck size={16} className="text-[#00BAF2]" /> Extracted by Sarvam Document Intelligence; checked by rules.</span>
            <span className="font-bold text-[#002970]">{activeDoc?.page_count ?? '–'} pg</span>
          </div>
        </div>
      </div>
    </div>
  );
}
