import { Landing } from '@/components/home/PaytmLanding';
import { CaseDetailScreen } from '@/components/kam/CaseDetailScreen';
import { KamQueueScreen } from '@/components/kam/KamQueueScreen';
import type { Persona } from '@/components/kam/KamWorkspaceShell';
import { CpvCapturePage } from '@/components/merchant/CpvCapturePage';
import { MerchantAuthScreen } from '@/components/merchant/MerchantAuthScreen';
import { MerchantUploadScreen } from '@/components/merchant/MerchantUploadScreen';
import { DEMO_MERCHANT_CASE, sendCaseAction, uploadDocuments } from '@/services/api';
import { useLiveCase, useLiveCases } from '@/services/useLiveCase';
import { useStaticMode } from '@/services/staticDemo';
import { useEffect, useState } from 'react';

type Route = 'landing' | 'login' | 'merchant-stage1' | 'merchant-account' | 'merchant-upload' | 'merchant-action' | 'kam' | 'case' | 'cpv';
type MerchantView = 'stage1' | 'account' | 'upload' | 'action';
type CaseAction = 'request' | 'voice' | 'approve' | 'send_back' | 'compliance_approve' | 'cpv_approve' | 'cpv_retake' | 'vcip_call' | 'vcip_signoff' | 'inv_resolve' | 'inv_dismiss';
const COMPLIANCE_ACTIONS = new Set<CaseAction>(['send_back', 'compliance_approve', 'vcip_call', 'vcip_signoff']);

const store = {
  get(key: string): string | null {
    try { return window.localStorage.getItem(key); } catch { return null; }
  },
  set(key: string, value: string) {
    try { window.localStorage.setItem(key, value); } catch { /* the choice just is not remembered */ }
  },
};

function App() {
  const [route, setRoute] = useState<Route>(() => routeFromPath(window.location.pathname));
  const [kamCaseId, setKamCaseId] = useState<string>(() => caseIdFromPath(window.location.pathname) ?? DEMO_MERCHANT_CASE);
  // The merchant portal opens the Sharma Foods demo case by default; "View as merchant" (or the picker in the portal header)
  // opens any case, so the whole lifecycle, including the shop-verification link, can be tested from the merchant side.
  const [merchantCaseId, setMerchantCaseId] = useState<string>(
    () => new URLSearchParams(window.location.search).get('case') ?? store.get('kk.merchantCase') ?? DEMO_MERCHANT_CASE,
  );
  const [persona, setPersonaState] = useState<Persona>(() => (store.get('kk.persona') === 'Compliance' ? 'Compliance' : 'KAM'));
  const setPersona = (p: Persona) => { setPersonaState(p); store.set('kk.persona', p); };
  const chooseMerchantCase = (id: string) => { setMerchantCaseId(id); store.set('kk.merchantCase', id); };
  const merchant = useLiveCase(merchantCaseId);
  const allCases = useLiveCases();
  const kam = useLiveCase(kamCaseId);

  useEffect(() => {
    const handler = () => {
      setRoute(routeFromPath(window.location.pathname));
      const id = caseIdFromPath(window.location.pathname);
      if (id) setKamCaseId(id);
    };
    window.addEventListener('popstate', handler);
    return () => window.removeEventListener('popstate', handler);
  }, []);

  const navigate = (next: Route, caseId?: string) => {
    const id = caseId ?? kamCaseId;
    const paths: Record<Route, string> = {
      landing: '/',
      login: '/login',
      'merchant-stage1': '/dashboard/stage-1',
      'merchant-account': '/dashboard/account-center',
      'merchant-upload': '/dashboard/upload',
      'merchant-action': '/dashboard/action-required',
      kam: '/kam',
      cpv: window.location.pathname,
      case: `/kam/cases/${id}`,
    };
    if (caseId) setKamCaseId(caseId);
    window.history.pushState({}, '', paths[next]);
    setRoute(next);
  };

  // Merchant uploads real files; the backend stores, hashes and starts the pipeline (202).
  const handleUploadFiles = async (files: File[], slot: string | null) => {
    const report = await uploadDocuments(merchantCaseId, files, slot);
    void merchant.reload();
    return report;
  };

  const openAsMerchant = (id: string) => {
    chooseMerchantCase(id);
    navigate('merchant-action');
  };

  const handleCaseAction = async (action: CaseAction, channel?: string, phone?: string) => {
    await sendCaseAction(kamCaseId, action, { channel, phone, actor: COMPLIANCE_ACTIONS.has(action) ? 'compliance' : 'kam' });
    void kam.reload();
  };

  const preview = useStaticMode();
  const offline = !preview && (merchant.offline || kam.offline);
  const banner = preview ? (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[60] max-w-[92vw] bg-[#e6f7fc] text-[#002970] border border-[#cfe9fc] rounded-xl px-4 py-2 text-xs font-bold shadow-lg text-center">
      Preview mode: a recorded snapshot of the synthetic Sharma Foods case. You can browse the documents, the checks and the filled MAF; uploads and actions need the backend.
    </div>
  ) : offline ? (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[60] bg-amber-100 text-amber-900 border border-amber-300 rounded-xl px-4 py-2 text-xs font-bold shadow-lg">
      Backend not reachable. Showing sample data. Start it with backend/run.bat (http://localhost:8765).
    </div>
  ) : null;
  const loading = <div className="min-h-screen flex items-center justify-center text-sm text-slate-500">Loading case…</div>;

  if (route === 'cpv') return <CpvCapturePage token={decodeURIComponent(window.location.pathname.split('/')[2] ?? '')} />;
  if (route === 'login') return <MerchantAuthScreen onBack={() => navigate('landing')} onSuccess={() => navigate('merchant-stage1')} />;
  if (route === 'merchant-stage1' || route === 'merchant-account' || route === 'merchant-upload' || route === 'merchant-action') {
    const currentMerchantView: MerchantView =
      route === 'merchant-stage1' ? 'stage1' :
        route === 'merchant-account' ? 'account' :
          route === 'merchant-upload' ? 'upload' : 'action';
    if (!merchant.caseData) return loading;
    return (
      <>
        <MerchantUploadScreen
          view={currentMerchantView}
          caseData={merchant.caseData}
          onUploadFiles={handleUploadFiles}
          onOpenKAM={() => navigate('kam')}
          cases={(allCases.list?.items ?? []).map((c) => ({ id: c.id, name: c.merchantName, stage: c.stageName ?? '' }))}
          onChooseCase={chooseMerchantCase}
          onNavigate={(view: MerchantView) => {
            const targetRoute: Route =
              view === 'stage1' ? 'merchant-stage1' :
                view === 'account' ? 'merchant-account' :
                  view === 'upload' ? 'merchant-upload' : 'merchant-action';
            navigate(targetRoute);
          }}
        />
        {banner}
      </>
    );
  }
  if (route === 'kam') {
    return (
      <>
        <KamQueueScreen onOpenCase={(id) => navigate('case', id)} onOpenAsMerchant={openAsMerchant} onSwitchRole={() => navigate('merchant-stage1')} persona={persona} onSwitchPersona={setPersona} />
        {banner}
      </>
    );
  }
  if (route === 'case') {
    if (!kam.caseData) return loading;
    return (
      <>
        <CaseDetailScreen caseData={kam.caseData} onBack={() => navigate('kam')} onSwitchRole={() => navigate('merchant-stage1')} onOpenAsMerchant={openAsMerchant} persona={persona} onSwitchPersona={setPersona} onAction={handleCaseAction} />
        {banner}
      </>
    );
  }
  return <Landing onAuth={() => navigate('login')} onMerchant={() => navigate('login')} onKAM={() => navigate('kam')} />;
}

function caseIdFromPath(path: string): string | null {
  const m = path.match(/^\/kam\/cases\/([^/]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}

function routeFromPath(path: string): Route {
  if (path.startsWith('/cpv/')) return 'cpv';
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

export default App;
