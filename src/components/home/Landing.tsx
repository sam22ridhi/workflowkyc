import { ArrowRight, ArrowUpRight, Play, Check, Database, FileText, GitMerge, ScanFace, Mic, Activity, FileDigit, Bot, User, Clock, Sparkles } from 'lucide-react';
import { Brand } from '@/components/shared/Brand';
import { motion } from 'framer-motion';
import React from 'react';

export function Landing({ onAuth, onMerchant, onKAM }: { onAuth: () => void; onMerchant: () => void; onKAM: () => void }) {
  return (
    <div className="site-shell bg-slate-50 text-blue-950 overflow-hidden font-sans">
      
      <header className="h-20 px-6 md:px-12 flex items-center justify-between border-b border-blue-900/10 relative z-50 bg-white/70 backdrop-blur-xl">
        <Brand />
        <nav className="hidden md:flex gap-8 text-sm font-semibold text-blue-950/70">
          <a href="#product" className="hover:text-blue-600 transition-colors">Product</a>
          <a href="#operations" className="hover:text-blue-600 transition-colors">Operations</a>
          <a href="#live-case" className="hover:text-blue-600 transition-colors">Live Case</a>
          <a href="#trust" className="hover:text-blue-600 transition-colors">Trust & Security</a>
        </nav>
        <div className="flex gap-4 items-center">
          <button className="text-sm font-bold text-blue-600 hover:text-blue-700 transition-colors" onClick={onAuth}>Sign in</button>
          <button className="bg-blue-600 text-white text-sm font-bold px-4 py-2.5 rounded-lg hover:bg-blue-700 transition-all shadow-lg shadow-blue-600/25 flex items-center gap-2 hover:-translate-y-0.5" onClick={onAuth}>
            Get started <ArrowUpRight size={16} />
          </button>
        </div>
      </header>

      <main>
        {/* 1. HERO SECTION */}
        <section className="relative pt-16 pb-20 px-6 md:px-12 max-w-[1400px] mx-auto grid grid-cols-1 lg:grid-cols-2 gap-12 items-center min-h-[80vh]" id="product">
          {/* Subtle tech background */}
          <div className="absolute inset-0 bg-[radial-gradient(#3b82f6_1px,transparent_1px)] [background-size:20px_20px] opacity-[0.03] pointer-events-none -z-10" />
          
          <div className="relative z-10">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-100/50 border border-blue-200 text-blue-700 text-[10px] font-extrabold uppercase tracking-widest mb-6 shadow-sm">
              <span className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)] animate-pulse" />
              The intelligent merchant OS
            </div>
            <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight leading-[1.05] text-blue-950 mb-6 drop-shadow-sm">
              Get your business <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-500">onboarded.</span>
              <br />without the wait.
            </h1>
            <p className="text-lg text-blue-950/70 mb-8 max-w-md leading-relaxed font-medium">
              An autonomous AI operations team for merchant onboarding, verification, compliance and ongoing operations.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 mb-10">
              <button className="bg-gradient-to-r from-blue-600 to-blue-500 text-white text-sm font-bold px-7 py-4 rounded-xl hover:from-blue-700 hover:to-blue-600 transition-all shadow-xl shadow-blue-600/30 flex items-center justify-center gap-2 hover:-translate-y-1" onClick={onMerchant}>
                Start onboarding <ArrowRight size={18} />
              </button>
              <button className="bg-white/80 backdrop-blur-sm border border-blue-200 text-blue-950 text-sm font-bold px-7 py-4 rounded-xl hover:border-blue-400 hover:bg-blue-50 transition-all flex items-center justify-center gap-2 hover:-translate-y-1 shadow-sm" onClick={onKAM}>
                <Play size={16} className="text-blue-600" fill="currentColor" /> See how it works
              </button>
            </div>
          </div>

          <div className="relative h-[500px] w-full flex items-center justify-center">
            {/* Animated AI OPERATIONS Visualization */}
            <div className="absolute inset-0 flex items-center justify-center scale-90 md:scale-100">
              {/* Orbits */}
              <motion.div animate={{ rotate: 360 }} transition={{ duration: 40, repeat: Infinity, ease: "linear" }} className="absolute w-[320px] h-[320px] rounded-full border border-dashed border-blue-300/60" />
              <motion.div animate={{ rotate: -360 }} transition={{ duration: 60, repeat: Infinity, ease: "linear" }} className="absolute w-[460px] h-[460px] rounded-full border border-blue-200/40" />
              <div className="absolute w-[460px] h-[460px] rounded-full bg-blue-100/20 blur-3xl -z-10" />
              
              {/* Central Node */}
              <div className="relative z-10 bg-white/90 backdrop-blur-xl border border-blue-200 shadow-2xl shadow-blue-900/10 rounded-3xl p-6 text-center w-48 h-48 flex flex-col items-center justify-center group cursor-pointer hover:border-blue-400 transition-colors">
                <div className="w-14 h-14 bg-gradient-to-br from-blue-100 to-blue-50 rounded-2xl flex items-center justify-center text-blue-600 mb-4 shadow-inner group-hover:scale-110 transition-transform">
                  <Database size={26} strokeWidth={2.5} />
                </div>
                <strong className="text-[13px] text-blue-950 block leading-tight font-extrabold tracking-wide">MERCHANT<br/>DIGITAL TWIN</strong>
                <span className="text-[9px] text-emerald-600 font-extrabold tracking-widest uppercase mt-3 flex items-center gap-1.5 bg-emerald-50 px-2 py-1 rounded-full"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" /> Active</span>
              </div>

              {/* Orbital Nodes */}
              <OrbitalNode radius={160} angle={0} icon={<FileText size={16} />} title="Document Intel" color="text-blue-500" />
              <OrbitalNode radius={160} angle={72} icon={<GitMerge size={16} />} title="Orchestrator" color="text-emerald-500" />
              <OrbitalNode radius={160} angle={144} icon={<ScanFace size={16} />} title="Physical Check" color="text-indigo-500" />
              <OrbitalNode radius={230} angle={216} icon={<Mic size={16} />} title="Voice Agent" color="text-orange-500" />
              <OrbitalNode radius={230} angle={288} icon={<Activity size={16} />} title="Monitoring" color="text-rose-500" />
            </div>
          </div>
        </section>

        {/* ─── DISTINCT ARCHITECTURAL BOUNDARY / DIVIDER ─── */}
        <div className="relative w-full overflow-hidden select-none py-4">
          {/* Subtle multi-layer gradient glow lines */}
          <div className="max-w-[1280px] mx-auto px-6 relative flex items-center justify-between">
            {/* Left technical trace line */}
            <div className="flex-1 h-px bg-gradient-to-r from-transparent via-blue-200/80 to-blue-400" />
            
            {/* Center Distinction Badge / Status Node */}
            <div className="px-5 py-2 mx-4 rounded-full bg-gradient-to-r from-blue-900 via-indigo-950 to-blue-900 border border-blue-400/30 text-white shadow-xl shadow-blue-950/15 flex items-center gap-3 backdrop-blur-md">
              <span className="flex h-2 w-2 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-400" />
              </span>
              <span className="text-[11px] font-mono tracking-widest uppercase font-bold text-blue-100 flex items-center gap-2">
                <span>SYSTEM INTERFACE</span>
                <span className="text-blue-400/60">•</span>
                <span className="text-cyan-300">LIVE ORCHESTRATION PIPELINE</span>
              </span>
              <span className="hidden sm:inline-block px-1.5 py-0.5 text-[9px] font-mono font-semibold bg-blue-800/80 rounded text-cyan-200 border border-blue-600/40">
                v2.4
              </span>
            </div>

            {/* Right technical trace line */}
            <div className="flex-1 h-px bg-gradient-to-l from-transparent via-blue-200/80 to-blue-400" />
          </div>

          {/* Soft ambient back-glow behind the line */}
          <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-10 bg-gradient-to-r from-transparent via-blue-500/5 to-transparent blur-xl pointer-events-none -z-10" />
        </div>

        {/* 2. AUTONOMOUS OPERATIONS SECTION (REDESIGNED) */}
        <section className="bg-gradient-to-b from-slate-50/80 via-white to-blue-50/30 py-24 px-6 md:px-12 border-b border-blue-100/60 relative overflow-hidden" id="operations">
          {/* Subtle grid pattern to give technical texture and prevent plain white flatness */}
          <div className="absolute inset-0 bg-[linear-gradient(to_right,#3b82f608_1px,transparent_1px),linear-gradient(to_bottom,#3b82f608_1px,transparent_1px)] bg-[size:32px_32px] pointer-events-none -z-10" />
          {/* Decorative gradients */}
          <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-blue-100/30 rounded-full blur-3xl pointer-events-none -z-10 translate-x-1/3 -translate-y-1/3" />
          <div className="absolute bottom-0 left-0 w-[600px] h-[600px] bg-emerald-100/20 rounded-full blur-3xl pointer-events-none -z-10 -translate-x-1/3 translate-y-1/3" />
          
          <div className="max-w-[1200px] mx-auto relative z-10">
            <div className="mb-20 text-center max-w-3xl mx-auto flex flex-col items-center">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-100 text-indigo-600 text-[10px] font-extrabold uppercase tracking-widest mb-4 shadow-sm">
                <Sparkles size={12} /> The Autonomous Operations Department
              </div>
              <h2 className="text-3xl md:text-5xl font-extrabold tracking-tight text-blue-950 mb-5 leading-tight">
                Not another KYC tool.<br />
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-500 to-indigo-400">An AI team that works the case.</span>
              </h2>
            </div>

            {/* AI TEAM HUB (ORCHESTRATOR VISUAL) */}
            <div className="relative w-full max-w-5xl mx-auto h-[750px] md:h-[550px] flex items-center justify-center mb-16 mt-10">
               
               {/* SVG Connection Lines with CSS Animation */}
               <svg className="absolute inset-0 w-full h-full pointer-events-none z-0 text-blue-200 hidden md:block opacity-60" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 4">
                 <style>
                   {`
                     @keyframes dashFlow { to { stroke-dashoffset: -24; } }
                     .animate-flow { animation: dashFlow 2s linear infinite; }
                     .animate-flow-reverse { animation: dashFlow 2s linear infinite reverse; }
                     @keyframes pulse-ring { 0% { transform: scale(0.8); opacity: 0.5; } 100% { transform: scale(1.5); opacity: 0; } }
                   `}
                 </style>
                 {/* Diagonal connectors */}
                 <line x1="20%" y1="20%" x2="50%" y2="50%" className="animate-flow" />
                 <line x1="80%" y1="20%" x2="50%" y2="50%" className="animate-flow-reverse" />
                 <line x1="20%" y1="80%" x2="50%" y2="50%" className="animate-flow" />
                 <line x1="80%" y1="80%" x2="50%" y2="50%" className="animate-flow-reverse" />
               </svg>

               {/* Center Hub */}
               <div className="absolute z-10 w-48 h-48 bg-white/95 backdrop-blur-xl border-2 border-blue-100 shadow-2xl shadow-blue-900/15 rounded-full flex flex-col items-center justify-center text-center group cursor-default hidden md:flex">
                 {/* Radar sweep ring */}
                 <div className="absolute inset-0 border border-blue-400/30 rounded-full animate-[pulse-ring_3s_cubic-bezier(0.215,0.61,0.355,1)_infinite]" />
                 
                 <div className="w-14 h-14 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-2xl text-white flex items-center justify-center mb-3 shadow-lg shadow-blue-600/30 relative z-10">
                   <Database size={26} />
                 </div>
                 <h3 className="text-[12px] font-extrabold text-blue-950 tracking-widest uppercase relative z-10">KARYAKARTA<br />AI TEAM</h3>
                 <div className="mt-3 bg-emerald-50 text-emerald-600 text-[10px] px-3 py-1.5 rounded-full font-bold flex items-center gap-1.5 border border-emerald-100 relative z-10 shadow-sm">
                   <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.5)]" /> 1 Case Active
                 </div>
                 <div className="absolute -inset-6 border border-blue-100/50 rounded-full -z-10 group-hover:scale-110 transition-transform duration-700 bg-blue-50/20" />
               </div>

               {/* Mobile layout requires a different positioning logic for smaller screens */}
               <div className="flex md:hidden flex-col gap-6 w-full px-4 relative z-20">
                 <AgentHubNode position="relative" icon={<FileDigit size={20} />} title="Document Intelligence" desc="Extracts structured information from documents and builds connected merchant context." tech="SARVAM • COGNEE • LANCEDB" status="Analyzing..." color="blue" />
                 <AgentHubNode position="relative" icon={<GitMerge size={20} />} title="Workflow Orchestrator" desc="Coordinates checks, decisions, escalations and next actions automatically." tech="n8n" status="Running" color="emerald" />
                 <AgentHubNode position="relative" icon={<ScanFace size={20} />} title="Physical Verification" desc="Verifies storefront, business details and location using vision." tech="KŪZU" status="Verified" color="indigo" />
                 <AgentHubNode position="relative" icon={<Mic size={20} />} title="Voice Agent" desc="Calls merchants, collects missing information and follows up automatically." tech="SARVAM • TWILIO" status="Waiting" color="orange" />
               </div>

               {/* Agent Nodes (Desktop) */}
               <div className="hidden md:block w-full h-full relative">
                 <AgentHubNode position="absolute top-0 left-[5%] xl:left-[10%]" icon={<FileDigit size={20} />} title="Document Intelligence" desc="Extracts structured information from documents and builds connected merchant context." tech="SARVAM • COGNEE • LANCEDB" status="Analyzing..." color="blue" />
                 <AgentHubNode position="absolute top-0 right-[5%] xl:right-[10%]" icon={<GitMerge size={20} />} title="Workflow Orchestrator" desc="Coordinates checks, decisions, escalations and next actions automatically." tech="n8n" status="Running" color="emerald" />
                 <AgentHubNode position="absolute bottom-0 left-[5%] xl:left-[10%]" icon={<ScanFace size={20} />} title="Physical Verification" desc="Verifies storefront, business details and location using vision." tech="KŪZU" status="Verified" color="indigo" />
                 <AgentHubNode position="absolute bottom-0 right-[5%] xl:right-[10%]" icon={<Mic size={20} />} title="Voice Agent" desc="Calls merchants, collects missing information and follows up automatically." tech="SARVAM • TWILIO" status="Waiting" color="orange" />
               </div>
            </div>
            
            {/* VISUAL FLOW */}
            <div className="max-w-4xl mx-auto bg-white/60 backdrop-blur-md border border-slate-200/60 rounded-2xl p-6 flex flex-col md:flex-row justify-between items-center gap-4 text-[11px] font-extrabold uppercase tracking-widest text-slate-500 shadow-xl shadow-blue-900/5 mt-8 relative z-20">
              <span className="text-blue-950 flex items-center gap-2"><span className="w-7 h-7 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center border border-blue-100"><FileText size={14} /></span> DOCUMENTS</span>
              <ArrowRight size={16} className="text-slate-300 hidden md:block" />
              <ArrowRight size={16} className="text-slate-300 md:hidden rotate-90" />
              <span className="text-blue-600 flex items-center gap-2"><span className="w-7 h-7 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center border border-blue-100"><FileDigit size={14} /></span> UNDERSTAND</span>
              <ArrowRight size={16} className="text-slate-300 hidden md:block" />
              <ArrowRight size={16} className="text-slate-300 md:hidden rotate-90" />
              <span className="text-indigo-600 flex items-center gap-2"><span className="w-7 h-7 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center border border-indigo-100"><ScanFace size={14} /></span> VERIFY</span>
              <ArrowRight size={16} className="text-slate-300 hidden md:block" />
              <ArrowRight size={16} className="text-slate-300 md:hidden rotate-90" />
              <span className="text-orange-500 flex items-center gap-2"><span className="w-7 h-7 rounded-lg bg-orange-50 text-orange-500 flex items-center justify-center border border-orange-100"><Mic size={14} /></span> FOLLOW UP</span>
              <ArrowRight size={16} className="text-slate-300 hidden md:block" />
              <ArrowRight size={16} className="text-slate-300 md:hidden rotate-90" />
              <span className="text-emerald-600 flex items-center gap-2"><span className="w-7 h-7 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center border border-emerald-100"><Check size={14} /></span> DECIDE</span>
            </div>
          </div>
        </section>

        {/* 3. ONE LIVE CASE VISUAL */}
        <section className="py-20 px-6 md:px-12 bg-slate-50 relative" id="live-case">
          <div className="max-w-[1200px] mx-auto grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-100 text-emerald-600 text-[10px] font-extrabold uppercase tracking-widest mb-4">
                Real-time tracking
              </div>
              <h2 className="text-3xl md:text-5xl font-extrabold tracking-tight text-blue-950 mb-5">Watch Karyakarta work.</h2>
              <p className="text-blue-950/60 text-base mb-10">
                Every action is tracked in real-time. Watch as specialized agents collaborate on a single case, moving it from submission to readiness.
              </p>
              
              <div className="grid gap-4">
                <div className="bg-white border border-blue-100/50 rounded-2xl p-5 flex items-start gap-4 hover:shadow-lg hover:shadow-blue-900/5 transition-all">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-100 to-blue-50 text-blue-600 flex items-center justify-center shrink-0 border border-blue-100">
                    <Bot size={20} />
                  </div>
                  <div>
                    <h4 className="text-[13px] font-extrabold text-blue-950 mb-1">5 AI agents active</h4>
                    <p className="text-[11px] text-blue-950/60 leading-relaxed">Handling extraction, cross-referencing, and communication.</p>
                  </div>
                </div>
                
                <div className="bg-white border border-emerald-100/50 rounded-2xl p-5 flex items-start gap-4 hover:shadow-lg hover:shadow-emerald-900/5 transition-all">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-100 to-emerald-50 text-emerald-600 flex items-center justify-center shrink-0 border border-emerald-100">
                    <User size={20} />
                  </div>
                  <div>
                    <h4 className="text-[13px] font-extrabold text-blue-950 mb-1">Human intervention when required</h4>
                    <p className="text-[11px] text-blue-950/60 leading-relaxed">KAMs step in for high-stakes decisions and escalations.</p>
                  </div>
                </div>
              </div>
            </div>
            
            {/* Dark cool card */}
            <div className="bg-blue-950 rounded-3xl p-8 md:p-10 shadow-2xl shadow-blue-900/30 text-blue-100 relative overflow-hidden border border-blue-800">
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-400 via-indigo-400 to-blue-400" />
              
              {/* Decorative inner glow */}
              <div className="absolute -top-24 -right-24 w-64 h-64 bg-indigo-500/20 rounded-full blur-3xl pointer-events-none" />
              
              <div className="flex justify-between items-start border-b border-blue-800/50 pb-6 mb-8 relative z-10">
                <div>
                  <div className="text-[9px] font-bold text-indigo-300 mb-1.5 tracking-widest uppercase flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 shadow-[0_0_8px_rgba(129,140,248,0.8)] animate-pulse" />
                    AI OPERATIONS ACTIVE
                  </div>
                  <div className="text-xl font-bold text-white tracking-wide">SHARMA FOODS PVT. LTD.</div>
                </div>
              </div>
              
              <div className="space-y-7 relative pl-2 z-10">
                <div className="absolute left-4 top-2 bottom-4 w-px bg-blue-800/60" />
                <TimelineItem text="Documents received" done />
                <TimelineItem text="Fields extracted" done />
                <TimelineItem text="Ownership mapped" done />
                <TimelineItem text="Registry checks" done />
                <TimelineItem text="Physical Verification" done />
                <TimelineItem text="Clarification requested" pending />
                <TimelineItem text="Human review" future />
              </div>
            </div>
          </div>
        </section>

        {/* 4. MAKER-CHECKER SECTION */}
        <section className="bg-gradient-to-b from-blue-950 to-[#0a1128] py-24 px-6 md:px-12 text-center relative overflow-hidden" id="trust">
          {/* Cool grid background */}
          <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e3a8a_1px,transparent_1px),linear-gradient(to_bottom,#1e3a8a_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] opacity-20" />

          <div className="max-w-[1000px] mx-auto relative z-10">
            <h2 className="text-3xl md:text-5xl font-extrabold mb-16 tracking-tight text-white drop-shadow-lg">Autonomous doesn't mean unsupervised.</h2>
            
            <div className="flex flex-col md:flex-row items-stretch justify-center gap-6 mb-12 relative">
              {/* AI Card */}
              <div className="flex-1 bg-white/5 backdrop-blur-md border border-white/10 rounded-3xl p-8 hover:bg-white/10 transition-colors shadow-2xl relative overflow-hidden">
                <div className="absolute -top-20 -left-20 w-40 h-40 bg-blue-500/20 rounded-full blur-3xl pointer-events-none" />
                <div className="w-14 h-14 bg-blue-500/20 text-blue-300 rounded-2xl flex items-center justify-center mx-auto mb-6 border border-blue-500/20">
                  <Bot size={24} />
                </div>
                <h3 className="text-lg font-extrabold mb-6 text-white tracking-widest uppercase">AI MAKER</h3>
                <ul className="text-[13px] text-blue-100/70 space-y-4 font-semibold text-left mx-auto w-fit">
                  <li className="flex items-center gap-3"><Check size={16} className="text-blue-400" /> Extract</li>
                  <li className="flex items-center gap-3"><Check size={16} className="text-blue-400" /> Verify</li>
                  <li className="flex items-center gap-3"><Check size={16} className="text-blue-400" /> Investigate</li>
                  <li className="flex items-center gap-3"><Check size={16} className="text-blue-400" /> Communicate</li>
                  <li className="flex items-center gap-3"><Check size={16} className="text-blue-400" /> Monitor</li>
                </ul>
              </div>
              
              <div className="flex items-center justify-center text-blue-500/50 md:rotate-0 my-2 md:my-0">
                <ArrowRight size={28} className="hidden md:block" />
                <ArrowRight size={28} className="md:hidden rotate-90" />
              </div>

              {/* Human Card */}
              <div className="flex-1 bg-white/5 backdrop-blur-md border border-white/10 rounded-3xl p-8 hover:bg-white/10 transition-colors shadow-2xl relative overflow-hidden">
                <div className="absolute -top-20 -right-20 w-40 h-40 bg-emerald-500/20 rounded-full blur-3xl pointer-events-none" />
                <div className="w-14 h-14 bg-emerald-500/20 text-emerald-300 rounded-2xl flex items-center justify-center mx-auto mb-6 border border-emerald-500/20">
                  <User size={24} />
                </div>
                <h3 className="text-lg font-extrabold mb-6 text-white tracking-widest uppercase">HUMAN CHECKER</h3>
                <ul className="text-[13px] text-emerald-100/70 space-y-4 font-semibold text-left mx-auto w-fit">
                  <li className="flex items-center gap-3"><Check size={16} className="text-emerald-400" /> Review</li>
                  <li className="flex items-center gap-3"><Check size={16} className="text-emerald-400" /> Approve</li>
                  <li className="flex items-center gap-3"><Check size={16} className="text-emerald-400" /> Resolve ambiguity</li>
                </ul>
              </div>
            </div>
            <p className="text-blue-300/60 text-sm font-semibold tracking-wide">AI handles execution. Humans retain control over consequential decisions.</p>
          </div>
        </section>

        {/* 5. FINAL CTA */}
        <section className="bg-gradient-to-br from-blue-600 to-indigo-600 text-white py-24 px-6 md:px-12 text-center relative overflow-hidden">
          {/* Stylish overlapping circles */}
          <div className="absolute top-1/2 left-0 -translate-y-1/2 w-[400px] h-[400px] border-[40px] border-white/5 rounded-full -translate-x-1/2" />
          <div className="absolute top-1/2 right-0 -translate-y-1/2 w-[600px] h-[600px] border-[60px] border-white/5 rounded-full translate-x-1/3" />
          
          <div className="max-w-2xl mx-auto relative z-10">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 border border-white/20 text-white text-[10px] font-extrabold uppercase tracking-widest mb-6">
              Ready when you are
            </div>
            <h2 className="text-4xl md:text-6xl font-extrabold tracking-tight mb-6 leading-tight drop-shadow-md">From onboarding <br/>to ongoing operations.</h2>
            <p className="text-blue-100 text-lg mb-10 font-medium">One merchant. One connected system. From Day 1 to Day 100.</p>
            <button className="bg-white text-blue-600 text-sm font-extrabold px-8 py-4 rounded-xl hover:bg-blue-50 hover:scale-105 transition-all duration-300 shadow-2xl flex items-center justify-center gap-2 mx-auto" onClick={onAuth}>
              Create your account <ArrowRight size={18} />
            </button>
          </div>
        </section>
      </main>
      
      <footer className="py-8 px-6 md:px-12 bg-slate-50 border-t border-slate-200 text-blue-950/40 text-[11px] flex flex-col md:flex-row justify-between items-center gap-6">
        <div className="opacity-70"><Brand compact /></div>
        <div className="font-semibold tracking-wide">&copy; 2026 KARYAKARTA INC.</div>
        <div className="flex gap-8 font-bold uppercase tracking-wider">
          <a href="#trust" className="hover:text-blue-600 transition-colors">Privacy</a>
          <a href="#trust" className="hover:text-blue-600 transition-colors">Security</a>
          <a href="#trust" className="hover:text-blue-600 transition-colors">Contact</a>
        </div>
      </footer>
    </div>
  );
}

function OrbitalNode({ radius, angle, icon, title, color }: { radius: number, angle: number, icon: React.ReactNode, title: string, color: string }) {
  const x = Math.cos(angle * (Math.PI / 180)) * radius;
  const y = Math.sin(angle * (Math.PI / 180)) * radius;
  
  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: 0.2 + (angle / 360), duration: 0.6, type: "spring" }}
      className="absolute z-20 group cursor-default"
      style={{ left: `calc(50% + ${x}px)`, top: `calc(50% + ${y}px)`, transform: 'translate(-50%, -50%)' }}
    >
      <div className="bg-white/80 backdrop-blur-md border border-blue-100 shadow-xl rounded-xl p-2.5 flex items-center gap-2.5 whitespace-nowrap group-hover:scale-105 group-hover:border-blue-300 transition-all">
        <div className={`bg-slate-50 p-2 rounded-lg border border-slate-100 shadow-inner ${color}`}>
          {icon}
        </div>
        <span className="text-[10px] font-extrabold text-blue-950 pr-1 tracking-wide">{title}</span>
      </div>
    </motion.div>
  );
}

function AgentHubNode({ position, icon, title, desc, tech, status, color }: { position: string, icon: React.ReactNode, title: string, desc: string, tech: string, status: string, color: 'blue' | 'emerald' | 'indigo' | 'orange' }) {
  const styles = {
    blue: {
      border: 'border-blue-100 group-hover:border-blue-300',
      shadow: 'shadow-blue-900/5 hover:shadow-blue-900/15',
      iconBg: 'bg-blue-50 border-blue-100 text-blue-600',
      statusBg: 'bg-blue-50 border-blue-100 text-blue-600',
      statusDot: 'bg-blue-500',
      techText: 'text-blue-500'
    },
    emerald: {
      border: 'border-emerald-100 group-hover:border-emerald-300',
      shadow: 'shadow-emerald-900/5 hover:shadow-emerald-900/15',
      iconBg: 'bg-emerald-50 border-emerald-100 text-emerald-600',
      statusBg: 'bg-emerald-50 border-emerald-100 text-emerald-600',
      statusDot: 'bg-emerald-500',
      techText: 'text-emerald-500'
    },
    indigo: {
      border: 'border-indigo-100 group-hover:border-indigo-300',
      shadow: 'shadow-indigo-900/5 hover:shadow-indigo-900/15',
      iconBg: 'bg-indigo-50 border-indigo-100 text-indigo-600',
      statusBg: 'bg-emerald-50 border-emerald-100 text-emerald-600', // Verified is emerald
      statusDot: 'bg-emerald-500',
      techText: 'text-indigo-500'
    },
    orange: {
      border: 'border-orange-100 group-hover:border-orange-300',
      shadow: 'shadow-orange-900/5 hover:shadow-orange-900/15',
      iconBg: 'bg-orange-50 border-orange-100 text-orange-500',
      statusBg: 'bg-orange-50 border-orange-100 text-orange-600',
      statusDot: 'bg-orange-500',
      techText: 'text-orange-500'
    }
  };

  const s = styles[color];
  const isVerified = status === "Verified";
  const isRunning = status.includes("Running") || status.includes("...");

  return (
    <div className={`${position} z-20 group`}>
      <div className={`w-full md:w-[260px] bg-white/90 backdrop-blur-xl border ${s.border} rounded-2xl p-5 shadow-xl ${s.shadow} transition-all duration-300 group-hover:scale-[1.03] overflow-hidden`}>
        {/* Top row: Icon + Status */}
        <div className="flex justify-between items-start mb-4">
          <div className={`w-11 h-11 rounded-xl flex items-center justify-center border ${s.iconBg} shadow-sm group-hover:scale-110 transition-transform`}>
            {icon}
          </div>
          <div className={`text-[9px] font-bold px-2.5 py-1.5 rounded-full border flex items-center gap-1.5 ${s.statusBg}`}>
            {isRunning ? (
               <span className={`w-1.5 h-1.5 rounded-full ${s.statusDot} animate-pulse`} />
            ) : isVerified ? (
               <Check size={10} strokeWidth={3} />
            ) : (
               <div className={`w-1.5 h-1.5 rounded-full ${s.statusDot}`} />
            )}
            {status}
          </div>
        </div>
        
        {/* Title */}
        <h4 className="text-[12px] font-extrabold text-blue-950 uppercase tracking-widest mb-1">{title}</h4>
        
        {/* Hidden on default, shown on hover via grid-rows */}
        <div className="grid grid-rows-[0fr] md:group-hover:grid-rows-[1fr] transition-all duration-300 ease-out">
          <div className="overflow-hidden">
             <p className="text-[11.5px] text-blue-950/70 font-medium leading-relaxed mt-2">{desc}</p>
             <div className={`text-[9px] font-extrabold ${s.techText} tracking-widest uppercase mt-4 pt-4 border-t border-slate-100`}>{tech}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function TimelineItem({ text, done, pending, future }: { text: string, done?: boolean, pending?: boolean, future?: boolean }) {
  return (
    <motion.div 
      initial={{ opacity: 0, x: -10 }}
      whileInView={{ opacity: 1, x: 0 }}
      viewport={{ once: true, margin: "-50px" }}
      transition={{ duration: 0.4 }}
      className="flex items-center gap-4 relative z-10"
    >
      <div className={`w-6 h-6 rounded-full flex items-center justify-center relative shrink-0 ${
        done ? 'bg-indigo-500 text-white shadow-[0_0_10px_rgba(99,102,241,0.4)]' : 
        pending ? 'bg-blue-500 text-white shadow-[0_0_15px_rgba(59,130,246,0.6)] animate-pulse' : 
        'bg-blue-900 text-blue-700 border border-blue-800'
      }`}>
        {done ? <Check size={12} strokeWidth={4} /> : pending ? <Clock size={10} strokeWidth={4} /> : <div className="w-1 h-1 rounded-full bg-blue-700" />}
      </div>
      <span className={`text-xs font-bold tracking-wide ${done ? 'text-indigo-200' : pending ? 'text-white' : 'text-blue-800'}`}>{text}</span>
    </motion.div>
  );
}
