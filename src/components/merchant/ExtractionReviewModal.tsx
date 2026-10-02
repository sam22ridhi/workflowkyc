import { useState } from 'react';
import { Check, ChevronLeft, ChevronRight, FileText, Sparkles, X } from 'lucide-react';
import type { MerchantCase } from '@/types/case';

interface ExtractionReviewModalProps {
  caseData: MerchantCase;
  onClose: () => void;
}

export function ExtractionReviewModal({ caseData, onClose }: ExtractionReviewModalProps) {
  const [mode, setMode] = useState<'preview' | 'json'>('preview');
  const finding = caseData.findings[0];
  return <div className="extraction-backdrop" onClick={onClose}><section className="extraction-modal" onClick={(event) => event.stopPropagation()}><header className="extraction-modal-head"><div><span className="eyebrow-label ai-label"><Sparkles size={14} /> Document intelligence</span><h2>KYC document extraction</h2><p>Review the fields KARYAKARTA found before they become part of your application.</p></div><button className="modal-close" onClick={onClose}><X size={20} /></button></header><div className="extraction-toolbar"><span>Sample document</span><div className="page-controls"><button><ChevronLeft size={15} /></button><b>1 / 4</b><button><ChevronRight size={15} /></button></div><span>Fields we’ll extract</span><div className="mode-switch"><button className={mode === 'preview' ? 'active' : ''} onClick={() => setMode('preview')}>Preview</button><button className={mode === 'json' ? 'active' : ''} onClick={() => setMode('json')}>JSON</button></div></div><div className="extraction-modal-body"><div className="document-preview-panel"><span className="document-tag">GST certificate</span><div className="fictional-document"><div className="fictional-doc-brand">GOODS AND SERVICES TAX</div><div className="fictional-doc-title">REGISTRATION CERTIFICATE</div><div className="fictional-seal"><Sparkles size={17} /></div><div className="fictional-doc-line wide" /><div className="fictional-doc-line" /><div className="fictional-highlight">27AABCS4821Q1Z7</div><div className="fictional-doc-line wide" /><div className="fictional-doc-line short" /><div className="fictional-address">12 Mahatma Gandhi Marg, Navi Mumbai</div><div className="fictional-doc-footer">GOVERNMENT OF INDIA · SAMPLE PREVIEW</div></div><small className="preview-caption"><FileText size={13} /> GST_Certificate.pdf · Page 1</small></div><div className="extraction-field-panel">{mode === 'preview' ? <><ExtractionGroup title="Business details"><ExtractionRow label="Document type" value="gst_certificate" /><ExtractionRow label="Legal business name" value={caseData.legalName} confidence="98% confidence" /><ExtractionRow label="GSTIN" value={caseData.gstin} confidence="98% confidence" /></ExtractionGroup><ExtractionGroup title="Registration details"><ExtractionRow label="Registered address" value={finding.sourceValue} confidence={`${finding.confidence}% confidence`} exception={finding.status === 'exception'} /><ExtractionRow label="Registration date" value="18 March 2021" confidence="96% confidence" /></ExtractionGroup><div className="extraction-source"><FileText size={13} /> Source: <strong>GST_Certificate.pdf · Page 1</strong></div></> : <pre className="json-output">{JSON.stringify({ document_type: 'gst_certificate', legal_name: caseData.legalName, gstin: caseData.gstin, registered_address: finding.sourceValue }, null, 2)}</pre>}</div></div><footer className="extraction-modal-footer"><span><Sparkles size={14} /> AI extracted 8 fields from this document</span><button className="button button-blue" onClick={onClose}><Check size={15} /> Use extracted information</button></footer></section></div>;
}

function ExtractionGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className="extraction-group"><h3>{title}</h3>{children}</div>;
}

function ExtractionRow({ label, value, confidence, exception = false }: { label: string; value: string; confidence?: string; exception?: boolean }) {
  return <div className={`extraction-row ${exception ? 'extraction-row-exception' : ''}`}><span>{label}</span><strong>{value}</strong>{confidence && <small>{confidence}</small>}</div>;
}
