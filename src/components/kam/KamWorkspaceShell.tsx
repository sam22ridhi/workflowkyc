import React from 'react';
import { 
  Building2, 
  ChevronDown, 
  Layers, 
  AlertTriangle, 
  Settings, 
  LogOut, 
  ArrowLeftRight,
  ShieldCheck,
  Zap,
  Sparkles,
  Search,
  Bell
} from 'lucide-react';

export type KamSidebarTab = 'dashboard' | 'cases' | 'risk' | 'settings';
export type Persona = 'KAM' | 'Compliance';

interface KamWorkspaceShellProps {
  children: React.ReactNode;
  activeTab: KamSidebarTab;
  onSelectTab: (tab: KamSidebarTab) => void;
  persona: Persona;
  onSwitchPersona: (persona: Persona) => void;
  onSwitchToMerchant: () => void;
  title?: string;
  subtitle?: string;
}

export function KamWorkspaceShell({
  children,
  activeTab,
  onSelectTab,
  persona,
  onSwitchPersona,
  onSwitchToMerchant,
}: KamWorkspaceShellProps) {
  return (
    <div className="h-screen bg-slate-50 flex flex-col font-sans text-slate-900 overflow-hidden">
      {/* Top Bar */}
      <header className="flex-none flex items-center justify-between px-6 py-3 bg-white border-b border-slate-200/80 z-20 shadow-2xs">
        <div className="flex items-center gap-6">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-[#002970] text-[#00BAF2] flex items-center justify-center font-black text-base shadow-sm ring-2 ring-[#00BAF2]/30">
              K
            </div>
            <div className="flex flex-col items-start leading-tight">
              <strong className="text-[14px] font-extrabold tracking-widest text-[#002970]">
                KARYAKARTA<span className="text-[#00BAF2] font-black ml-0.5">·AI</span>
              </strong>
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                Paytm Corporate Gateway
              </span>
            </div>
          </div>

          <div className="h-5 w-px bg-slate-200 hidden md:block" />

          {/* Welcome Message */}
          <div className="hidden sm:flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-700">
              Welcome back, <strong className="text-slate-900 font-bold">Priya</strong>
            </span>
            <span className="text-slate-300">·</span>
            <span className="text-xs text-slate-500 font-medium">
              Enterprise Merchant Onboarding
            </span>
          </div>
        </div>

        {/* Right Section: Persona Switcher, AI Status, Merchant Mode Switch */}
        <div className="flex items-center gap-3.5">
          {/* AI Status Indicator */}
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200/80 shadow-2xs">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-[11px] font-extrabold text-emerald-800 tracking-wide">
              Karyakarta AI: <span className="font-bold text-emerald-700">● Online</span>
            </span>
          </div>

          {/* Persona Switcher (KAM / Compliance) */}
          <div className="flex items-center bg-slate-100 p-0.5 rounded-lg border border-slate-200 text-xs font-bold">
            <button
              onClick={() => onSwitchPersona('KAM')}
              className={`px-3 py-1 rounded-md transition-all ${
                persona === 'KAM'
                  ? 'bg-[#002970] text-white shadow-2xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              KAM (Maker)
            </button>
            <button
              onClick={() => onSwitchPersona('Compliance')}
              className={`px-3 py-1 rounded-md transition-all ${
                persona === 'Compliance'
                  ? 'bg-[#002970] text-white shadow-2xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Compliance (Checker)
            </button>
          </div>

          {/* Switch to Merchant View */}
          <button
            onClick={onSwitchToMerchant}
            className="hidden lg:flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-[#002970] bg-[#e6f7fc] border border-[#cfe9fc] hover:bg-[#d6f2fa] transition-all shadow-2xs"
            title="Preview merchant onboarding view"
          >
            <ArrowLeftRight size={13} className="text-[#00BAF2]" />
            <span>Merchant Portal</span>
          </button>
        </div>
      </header>

      {/* Main Workspace Layout with Sidebar */}
      <div className="flex-1 flex overflow-hidden">
        {/* Modern Sidebar */}
        <aside className="w-64 bg-white border-r border-slate-200/80 hidden md:flex flex-col shrink-0 z-10 shadow-[4px_0_24px_rgba(0,41,112,0.03)]">
          <div className="p-5 border-b border-slate-100 flex items-center justify-between">
            <div>
              <span className="text-[10px] font-extrabold uppercase tracking-widest text-[#00BAF2] block mb-0.5">
                Internal Portal
              </span>
              <strong className="text-sm font-extrabold text-[#002970]">
                {persona === 'KAM' ? 'KAM Command Center' : 'Compliance Desk'}
              </strong>
            </div>
            <span className="w-2 h-2 rounded-full bg-[#00BAF2]" />
          </div>

          {/* Sidebar Nav */}
          <nav className="p-3 space-y-1 flex-1 overflow-y-auto">
            <SidebarNavBtn
              active={activeTab === 'dashboard'}
              onClick={() => onSelectTab('dashboard')}
              icon={<Building2 size={18} />}
              label="Dashboard (Home)"
              badge="Live"
              badgeTone="cyan"
            />
            <SidebarNavBtn
              active={activeTab === 'cases'}
              onClick={() => onSelectTab('cases')}
              icon={<Layers size={18} />}
              label="All Cases"
              badge="42"
            />
            <SidebarNavBtn
              active={activeTab === 'risk'}
              onClick={() => onSelectTab('risk')}
              icon={<AlertTriangle size={18} />}
              label="Risk Alerts"
              badge="3"
              badgeTone="critical"
            />
            <SidebarNavBtn
              active={activeTab === 'settings'}
              onClick={() => onSelectTab('settings')}
              icon={<Settings size={18} />}
              label="Settings"
            />
          </nav>

          {/* AI Engine Status Card in Sidebar */}
          <div className="p-4 border-t border-slate-100 bg-[#f8fbfe]">
            <div className="bg-white p-3.5 rounded-xl border border-[#cfe9fc] shadow-2xs">
              <div className="flex items-center gap-2 mb-1.5">
                <div className="w-6 h-6 rounded-lg bg-[#e6f7fc] text-[#002970] flex items-center justify-center">
                  <Sparkles size={13} className="text-[#00BAF2]" />
                </div>
                <strong className="text-xs font-bold text-[#002970]">Karyakarta Agent</strong>
              </div>
              <p className="text-[10px] text-slate-600 mb-2 leading-relaxed">
                Autonomous OCR extraction &amp; MCA registry cross-checks active.
              </p>
              <div className="flex items-center justify-between text-[10px] font-bold text-slate-500 pt-1 border-t border-slate-100">
                <span>Confidence SLA</span>
                <span className="text-emerald-600 font-extrabold">98.4%</span>
              </div>
            </div>
          </div>

          {/* User Footer */}
          <div className="p-3.5 border-t border-slate-200/70 flex items-center justify-between bg-slate-50/60">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-8 h-8 rounded-full bg-[#002970] text-[#00BAF2] font-black text-xs flex items-center justify-center shrink-0">
                PS
              </div>
              <div className="min-w-0">
                <strong className="block text-xs font-bold text-slate-900 truncate">Priya Sharma</strong>
                <small className="block text-[10px] text-slate-500 truncate">Senior KAM · Mumbai</small>
              </div>
            </div>
            <button
              onClick={onSwitchToMerchant}
              className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-200/50 rounded-lg transition-colors"
              title="Switch role"
            >
              <LogOut size={15} />
            </button>
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col min-w-0 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}

function SidebarNavBtn({
  active,
  onClick,
  icon,
  label,
  badge,
  badgeTone = 'default',
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  badge?: string;
  badgeTone?: 'default' | 'cyan' | 'critical';
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-bold transition-all relative ${
        active
          ? 'bg-[#e6f7fc] text-[#002970] shadow-2xs font-extrabold border-l-4 border-[#00BAF2]'
          : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
      }`}
    >
      <div className="flex items-center gap-3">
        <span className={active ? 'text-[#00BAF2]' : 'text-slate-400'}>
          {icon}
        </span>
        <span>{label}</span>
      </div>
      {badge && (
        <span
          className={`text-[10px] font-extrabold px-1.5 py-0.5 rounded-md ${
            badgeTone === 'cyan'
              ? 'bg-[#00BAF2] text-white'
              : badgeTone === 'critical'
              ? 'bg-rose-100 text-rose-700'
              : active
              ? 'bg-[#002970] text-white'
              : 'bg-slate-200 text-slate-700'
          }`}
        >
          {badge}
        </span>
      )}
    </button>
  );
}
