import { useState } from 'react';
import { Check, ChevronLeft, ChevronRight, FileText, Sparkles, X } from 'lucide-react';

interface DocumentExtractionPanelProps {
  onBack: () => void;
}

interface ExtractedValueProps {
  label: string;
  value: string;
  confidence?: string;
  issue?: boolean;
}

export function DocumentExtractionPanel({ onBack }: DocumentExtractionPanelProps) {
  const [mode, setMode] = useState<'preview' | 'json'>('preview');
  const [confirmed, setConfirmed] = useState(false);
  return <div className="extraction-modal-shell"><div className="extraction-modal-header"><div><h3>KYC Document Extraction</h3><p>Review what KARYAKARTA found in your business document.</p></div><button className="close-extraction" onClick={onBack}><X size={21} /></button></div><div className="extraction-modal-toolbar"><span>SAMPLE DOCUMENT</span><div className="document-pager"><button><ChevronLeft size={16} /></button><span>1 / 4</span><button><ChevronRight size={16} /></button></div><span>FIELDS WE'LL EXTRACT</span><div className="preview-toggle"><button className={mode === 'preview' ? 'active' : ''} onClick={() => setMode('preview')}>Preview</button><button className={mode === 'json' ? 'active' : ''} onClick={() => setMode('json')}>JSON</button></div></div><div className="extraction-modal-grid"><div className="sample-document-large"><span className="sample-tag">GST certificate</span><div className="sample-paper-large"><div className="sample-paper-top"><span>GOODS AND SERVICES TAX</span><span>REGISTRATION CERTIFICATE</span></div><div className="certificate-emblem"><Sparkles size={18} /></div><h4>GST REGISTRATION</h4><div className="sample-lines"><span className="sample-line long" /><span className="sample-line medium" /><span className="sample-line short" /></div><div className="certificate-highlight">27AAECA1234F1Z5</div><div className="sample-lines"><span className="sample-line long" /><span className="sample-line medium" /><span className="sample-line short" /></div><div className="certificate-address">12, Mahatma Gandhi Road, Mumbai 400050</div><div className="sample-paper-bottom">GOVERNMENT OF INDIA</div></div></div><div className="extraction-fields-large">{mode === 'preview' ? <><div className="extraction-group"><h4>Business details</h4><ExtractedValue label="Document type" value="gst_certificate" /><ExtractedValue label="Business name" value="ABC Enterprises Pvt Ltd" confidence="98% confidence" /><ExtractedValue label="GSTIN" value="27AAECA1234F1Z5" confidence="98% confidence" /></div><div className="extraction-group"><h4>Registration details</h4><ExtractedValue label="Registered address" value="12, Mahatma Gandhi Road, Mumbai" confidence="91% confidence" issue /><ExtractedValue label="Registration date" value="14 January 2018" confidence="96% confidence" /></div><div className="extraction-source"><FileText size={14} /> Source: <strong>GST_Certificate.pdf · Page 1</strong></div></> : <pre className="json-preview">{JSON.stringify({ document_type: 'gst_certificate', business_name: 'ABC Enterprises Pvt Ltd', gstin: '27AAECA1234F1Z5', registered_address: '12, Mahatma Gandhi Road, Mumbai' }, null, 2)}</pre>}</div></div><div className="extraction-modal-footer"><span><Sparkles size={14} /> AI extracted 8 fields from this document</span><button className="button button-blue" onClick={() => setConfirmed(true)}>{confirmed ? <><Check size={16} /> Extraction confirmed</> : <>Use extracted information <ChevronRight size={16} /></>}</button></div></div>;
}

function ExtractedValue({ label, value, confidence, issue }: ExtractedValueProps) {
  return <div className={`extracted-value-row ${issue ? 'extracted-value-issue' : ''}`}><span><strong>{label}</strong>{issue && <span className="attention-mini">!</span>}</span><b>{value}</b>{confidence && <small>{confidence}</small>}</div>;
}
