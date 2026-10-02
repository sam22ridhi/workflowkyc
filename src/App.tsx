import { useEffect, useState, type ReactNode } from 'react';
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  CloudUpload,
  FileText,
  Play,
  ShieldCheck,
  Sparkles,
  Zap,
} from 'lucide-react';
import { CaseDetailScreen } from '@/components/kam/CaseDetailScreen';
import { KamQueueScreen } from '@/components/kam/KamQueueScreen';
import { MerchantAuthScreen } from '@/components/merchant/MerchantAuthScreen';
import { MerchantUploadScreen } from '@/components/merchant/MerchantUploadScreen';
import { Brand } from '@/components/shared/Brand';
import { cloneSeedCase } from '@/data/mockCase';
import type { MerchantCase, TimelineEvent } from '@/types/case';

type Route = 'landing' | 'login' | 'merchant-stage1' | 'merchant-account' | 'merchant-upload' | 'merchant-action' | 'kam' | 'case';
type MerchantView = 'stage1' | 'account' | 'upload' | 'action';
type CaseAction = 'request' | 'voice' | 'approve';

function App() {
  const [route, setRoute] = useState<Route>(() => routeFromPath(window.location.pathname));
  const [caseData, setCaseData] = useState<MerchantCase>(() => cloneSeedCase());

  useEffect(() => {
    const handler = () => setRoute(routeFromPath(window.location.pathname));
    window.addEventListener('popstate', handler);
    return () => window.removeEventListener('popstate', handler);
  }, []);

  const navigate = (next: Route) => {
    const paths: Record<Route, string> = { 
      landing: '/', 
      login: '/login', 
      'merchant-stage1': '/dashboard/stage-1', 
      'merchant-account': '/dashboard/account-center',
      'merchant-upload': '/dashboard/upload', 
      'merchant-action': '/dashboard/action-required', 
      kam: '/kam', 
      case: `/kam/cases/${caseData.id}` 
    };
    window.history.pushState({}, '', paths[next]);
    setRoute(next);
  };

  const appendEvent = (current: MerchantCase, event: Omit<TimelineEvent, 'id' | 'timestamp'>): MerchantCase => ({
    ...current,
    lastUpdated: 'just now',
    timeline: [...current.timeline, { ...event, id: `${event.title}-${Date.now()}`, timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) }],
  });

  const handleUpload = (documentId: string) => {
    setCaseData((current) => {
      const documents = current.documents.map((document) => document.id === documentId ? { ...document, status: 'received' as const, fieldsExtracted: documentId === 'address' ? 4 : 3, sourceLabel: `${document.name.replace(/ /g, '_')}.pdf · Page 1` } : document);
      const addressCorrected = documentId === 'address';
      const withUpload = appendEvent({ ...current, documents, completion: addressCorrected ? 100 : Math.min(88, current.completion + 10), status: addressCorrected ? 'ready_for_review' : current.status }, { title: 'Merchant re-uploaded', detail: `${current.documents.find((document) => document.id === documentId)?.name ?? 'Document'} was added to the case.`, tone: 'neutral' });
      if (!addressCorrected) return withUpload;
      return appendEvent({ ...withUpload, findings: withUpload.findings.map((finding) => ({ ...finding, status: 'verified' as const })), status: 'ready_for_review' }, { title: 'AI re-verified', detail: 'Corrected address proof now matches the submitted application.', tone: 'success' });
    });
  };

  const handleCaseAction = (action: CaseAction) => {
    setCaseData((current) => {
      if (action === 'approve') return appendEvent({ ...current, status: 'ready_for_review' }, { title: 'KAM approved application', detail: 'All AI findings are verified and the case is ready to move forward.', tone: 'success' });
      if (action === 'voice') return appendEvent({ ...current, status: 'awaiting_merchant' }, { title: 'KAM chased via Voice', detail: 'Voice agent requested corrected address proof from the merchant.', tone: 'ai' });
      return appendEvent({ ...current, status: 'awaiting_merchant' }, { title: 'Information requested', detail: 'KAM requested corrected address proof from the merchant.', tone: 'neutral' });
    });
  };

  if (route === 'login') return <MerchantAuthScreen onBack={() => navigate('landing')} onSuccess={() => navigate('merchant-stage1')} />;
  if (route === 'merchant-stage1' || route === 'merchant-account' || route === 'merchant-upload' || route === 'merchant-action') {
    const currentMerchantView: MerchantView = 
      route === 'merchant-stage1' ? 'stage1' : 
      route === 'merchant-account' ? 'account' : 
      route === 'merchant-upload' ? 'upload' : 'action';

    return (
      <MerchantUploadScreen 
        view={currentMerchantView} 
        caseData={caseData} 
        onUpload={handleUpload} 
        onOpenKAM={() => navigate('kam')} 
        onNavigate={(view: MerchantView) => {
          const targetRoute: Route = 
            view === 'stage1' ? 'merchant-stage1' : 
            view === 'account' ? 'merchant-account' : 
            view === 'upload' ? 'merchant-upload' : 'merchant-action';
          navigate(targetRoute);
        }} 
      />
    );
  }
  if (route === 'kam') return <KamQueueScreen caseData={caseData} onOpenCase={() => navigate('case')} onSwitchRole={() => navigate('merchant-stage1')} onVoiceChase={() => navigate('case')} />;
  if (route === 'case') return <CaseDetailScreen caseData={caseData} onBack={() => navigate('kam')} onSwitchRole={() => navigate('merchant-stage1')} onAction={handleCaseAction} />;
  return <Landing onAuth={() => navigate('login')} onMerchant={() => navigate('login')} onKAM={() => navigate('kam')} />;
}

function routeFromPath(path: string): Route {
  if (path.startsWith('/kam/cases/')) return 'case';
  if (path.startsWith('/kam')) return 'kam';
  if (path.startsWith('/dashboard/stage-1')) return 'merchant-stage1';
  if (path.startsWith('/dashboard/account-center')) return 'merchant-account';
  if (path.startsWith('/dashboard/upload')) return 'merchant-upload';
  if (path.startsWith('/dashboard/action-required')) return 'merchant-action';
  if (path.startsWith('/merchant')) return 'merchant-upload';
  if (path.startsWith('/login') || path.startsWith('/auth')) return 'login';
  return 'landing';
}

function Landing({ onAuth, onMerchant, onKAM }: { onAuth: () => void; onMerchant: () => void; onKAM: () => void }) {
  return <div className="site-shell"><header className="marketing-nav"><Brand /><nav className="nav-links"><a href="#product">Product</a><a href="#solutions">Solutions</a><a href="#trust">Trust &amp; security</a><a href="#resources">Resources</a></nav><div className="nav-actions"><button className="button button-quiet" onClick={onAuth}>Sign in</button><button className="button button-blue button-small" onClick={onAuth}>Get started <ArrowUpRight size={15} /></button></div></header><main><section className="hero-section" id="product"><div className="hero-copy"><div className="hero-eyebrow"><span className="hero-eyebrow-dot" />The intelligent merchant operating system</div><h1>Get your business <em>onboarded.</em></h1><p>Tell us about your business. We&rsquo;ll handle the paperwork, verification, and everything in between.</p><div className="hero-actions"><button className="button button-blue button-large" onClick={onMerchant}>Start onboarding <ArrowRight size={18} /></button><button className="button button-outline button-large" onClick={onKAM}><Play size={16} fill="currentColor" /> See how it works</button></div><div className="hero-proof"><div className="avatar-stack"><span>RS</span><span>AS</span><span>MK</span><span>+</span></div><span>Trusted by teams building India&rsquo;s next economy</span></div></div><div className="hero-visual"><div className="hero-orbit orbit-one" /><div className="hero-orbit orbit-two" /><div className="hero-panel"><div className="hero-panel-top"><span>New onboarding</span><span className="live-dot">Live</span></div><div className="hero-card-title">Your journey to<br /><strong>ready to transact.</strong></div><div className="journey-list"><JourneyStep icon={<FileText size={16} />} title="Business details" subtitle="Tell us about your company" done /><JourneyStep icon={<ShieldCheck size={16} />} title="Authorization" subtitle="Verify who can operate" done /><JourneyStep icon={<CloudUpload size={16} />} title="Documents" subtitle="We&rsquo;ll read the fine print" active /><JourneyStep icon={<Check size={16} />} title="AI verification" subtitle="A final, intelligent check" /></div><div className="hero-panel-footer"><span><Sparkles size={15} /> AI-powered verification</span><ArrowUpRight size={16} /></div></div><div className="floating-chip chip-green"><span className="chip-icon"><Check size={13} /></span> 7 fields extracted</div><div className="floating-chip chip-blue"><span className="chip-icon"><Zap size={13} /></span> AI is on it</div></div></section><section className="trust-strip" id="trust"><span>BUILT FOR THE WAY BUSINESS MOVES</span><strong>Fast onboarding</strong><strong>Bank-grade security</strong><strong>Intelligent by default</strong><strong>Human when it matters</strong></section><section className="story-section" id="solutions"><div className="section-label">A better way to begin</div><div className="story-heading"><h2>The hard part of starting<br /><span>shouldn&rsquo;t be paperwork.</span></h2><p>KARYAKARTA turns corporate onboarding from a process to endure into a journey that moves at the speed of your business.</p></div><div className="feature-grid"><FeatureCard icon={<CloudUpload />} number="01" title="Drop it in." text="Upload what you have. We understand the rest &mdash; from board resolutions to GST certificates." /><FeatureCard icon={<Sparkles />} number="02" title="We make sense of it." text="Our AI reads, extracts, and cross-checks every detail so nothing gets lost in the fine print." /><FeatureCard icon={<ShieldCheck />} number="03" title="Move forward, confidently." text="See exactly what&rsquo;s verified, what needs attention, and what to do next &mdash; in plain English." /></div></section><section className="quote-section" id="resources"><div className="quote-mark">&ldquo;</div><blockquote>Onboarding shouldn&rsquo;t feel like a test of patience. It should feel like the first step in a great partnership.</blockquote><div className="quote-byline"><div className="mini-avatar">K</div><span><strong>KARYAKARTA</strong><small>Built for better business banking</small></span></div></section><section className="cta-section"><div><div className="hero-eyebrow hero-eyebrow-light"><span className="hero-eyebrow-dot" />Ready when you are</div><h2>Let&rsquo;s get your business<br /><em>moving.</em></h2></div><button className="button button-white button-large" onClick={onAuth}>Create your account <ArrowRight size={18} /></button></section></main><footer className="marketing-footer"><Brand compact /><span>&copy; 2026 KARYAKARTA</span><div><a href="#trust">Privacy</a><a href="#trust">Security</a><a href="#trust">Contact</a></div></footer></div>;
}

function JourneyStep({ icon, title, subtitle, done, active }: { icon: ReactNode; title: string; subtitle: string; done?: boolean; active?: boolean }) {
  return <div className={`journey-step ${active ? 'journey-active' : ''}`}><span className={`journey-icon ${done ? 'journey-done' : ''}`}>{done ? <Check size={15} /> : icon}</span><span><strong>{title}</strong><small>{subtitle}</small></span>{done && <span className="step-status">Done</span>}{active && <span className="step-status active-status">In progress</span>}</div>;
}

function FeatureCard({ icon, number, title, text }: { icon: ReactNode; number: string; title: string; text: string }) {
  return <article className="feature-card"><div className="feature-top"><span className="feature-icon">{icon}</span><span className="feature-number">{number}</span></div><h3>{title}</h3><p>{text}</p><ArrowUpRight className="feature-arrow" size={19} /></article>;
}

export default App;
