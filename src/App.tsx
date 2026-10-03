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
import { Landing } from '@/components/home/Landing';
import { DEMO_MERCHANT_CASE, sendCaseAction, uploadDocuments } from '@/services/api';
import { useLiveCase } from '@/services/useLiveCase';

type Route = 'landing' | 'login' | 'merchant-stage1' | 'merchant-account' | 'merchant-upload' | 'merchant-action' | 'kam' | 'case';
type MerchantView = 'stage1' | 'account' | 'upload' | 'action';
type CaseAction = 'request' | 'voice' | 'approve' | 'send_back' | 'compliance_approve';

function App() {
  const [route, setRoute] = useState<Route>(() => routeFromPath(window.location.pathname));
  const [kamCaseId, setKamCaseId] = useState<string>(() => caseIdFromPath(window.location.pathname) ?? DEMO_MERCHANT_CASE);
  // The signed-in merchant is the Sharma Foods demo case; the KAM can open any case from the queue.
  const merchant = useLiveCase(DEMO_MERCHANT_CASE);
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
      case: `/kam/cases/${id}`,
    };
    if (caseId) setKamCaseId(caseId);
    window.history.pushState({}, '', paths[next]);
    setRoute(next);
  };

  // Merchant uploads real files; the backend stores, hashes and starts the pipeline (202).
  const handleUploadFiles = async (files: File[], slot: string | null) => {
    const report = await uploadDocuments(DEMO_MERCHANT_CASE, files, slot);
    void merchant.reload();
    return report;
  };

  const handleCaseAction = async (action: CaseAction, channel?: string, phone?: string) => {
    await sendCaseAction(kamCaseId, action, { channel, phone, actor: action === 'send_back' || action === 'compliance_approve' ? 'compliance' : 'kam' });
    void kam.reload();
  };

  const offline = merchant.offline || kam.offline;
  const banner = offline ? (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[60] bg-amber-100 text-amber-900 border border-amber-300 rounded-xl px-4 py-2 text-xs font-bold shadow-lg">
      Backend not reachable. Showing sample data. Start it with backend/run.bat (http://localhost:8765).
    </div>
  ) : null;
  const loading = <div className="min-h-screen flex items-center justify-center text-sm text-slate-500">Loading case…</div>;

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
        <KamQueueScreen onOpenCase={(id) => navigate('case', id)} onSwitchRole={() => navigate('merchant-stage1')} />
        {banner}
      </>
    );
  }
  if (route === 'case') {
    if (!kam.caseData) return loading;
    return (
      <>
        <CaseDetailScreen caseData={kam.caseData} onBack={() => navigate('kam')} onSwitchRole={() => navigate('merchant-stage1')} onAction={handleCaseAction} />
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
