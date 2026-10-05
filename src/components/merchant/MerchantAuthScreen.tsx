import { AppLogo } from '@/components/shared/AppLogo';
import { useState, type FormEvent } from 'react';
import { ArrowRight, Check, LockKeyhole, MessageCircle, ShieldCheck } from 'lucide-react';
import { Brand } from '@/components/shared/Brand';

interface MerchantAuthScreenProps {
  onSuccess: () => void;
  onBack: () => void;
}

export function MerchantAuthScreen({ onSuccess, onBack }: MerchantAuthScreenProps) {
  const [mobile, setMobile] = useState('');
  const [otp, setOtp] = useState('');
  const [otpSent, setOtpSent] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const sendOtp = () => { 
    if (mobile.replace(/\D/g, '').length === 10) {
      setOtpSent(true);
    }
  };

  const handleFillDemo = () => {
    setMobile('9876543210');
    setOtpSent(true);
    setOtp('123456');
  };

  const submit = (event: FormEvent) => { 
    event.preventDefault(); 
    if (otp.length === 6) {
      setSubmitted(true); 
      setTimeout(onSuccess, 450); 
    }
  };

  const canSubmit = otp.length === 6;

  return (
    <div className="min-h-screen bg-[#f4f7fb] flex flex-col font-sans text-slate-900 selection:bg-[#00BAF2]/20">
      <header className="flex items-center justify-between px-6 py-4 bg-white border-b border-slate-200 sticky top-0 z-10 shadow-2xs">
        <button className="hover:opacity-80 transition-opacity flex items-center gap-2.5" onClick={onBack}>
          <AppLogo subtitle="Paytm Corporate Gateway" size="md" />
        </button>
        <div className="hidden sm:flex items-center gap-2 text-xs font-semibold text-emerald-800 bg-emerald-50 px-3.5 py-1.5 rounded-full border border-emerald-200 shadow-2xs">
          <ShieldCheck size={15} className="text-emerald-600" /> Secure Paytm Business Merchant Onboarding
        </div>
        <button className="text-xs font-semibold text-slate-500 hover:text-[#002970] transition-colors flex items-center gap-1.5">
          Need help? <MessageCircle size={14} className="text-slate-400" /> Talk to us
        </button>
      </header>

      <main className="flex-1 flex flex-col items-center justify-center p-6 sm:p-12">
        <div className="max-w-md w-full">
          <div className="mb-6 text-center sm:text-left">
            <div className="inline-flex items-center gap-2 text-[10px] font-extrabold uppercase tracking-widest text-[#002970] bg-[#e6f7fc] px-3 py-1.5 rounded-lg mb-3 border border-[#b8e8f8]">
              <span className="w-2 h-2 rounded-full bg-[#00BAF2] animate-pulse"></span>
              Paytm Business × Karyakarta AI
            </div>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900 mb-2">
              Log in to your <em className="text-[#002970] not-italic underline decoration-[#00BAF2] decoration-4 underline-offset-4">portal</em>
            </h1>
            <p className="text-sm text-slate-600 leading-relaxed">
              Enter your authorized mobile number to access your Karyakarta corporate onboarding dashboard.
            </p>
            <div className="flex items-center justify-center sm:justify-start gap-4 mt-4 text-xs font-medium text-slate-600">
              <span className="flex items-center gap-1.5">
                <div className="bg-emerald-100 text-emerald-600 p-0.5 rounded-full"><Check size={12} strokeWidth={3} /></div> Bank-grade 256-bit encryption
              </span>
              <span className="flex items-center gap-1.5">
                <div className="bg-[#e6f7fc] text-[#002970] p-0.5 rounded-full"><Check size={12} strokeWidth={3} /></div> DPDP 2023 compliant
              </span>
            </div>
          </div>

          <form className="bg-white rounded-2xl shadow-xl shadow-slate-200/60 border border-slate-200 overflow-hidden" onSubmit={submit}>
            <div className="p-6 sm:p-8">
              {/* Mobile and OTP verification */}
              <div className="flex gap-4">
                <span className="flex-none bg-[#002970] text-white font-extrabold w-8 h-8 rounded-xl flex items-center justify-center text-xs shadow-2xs">01</span>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <h2 className="text-base font-bold text-slate-900">Verify your mobile</h2>
                    <button 
                      type="button" 
                      onClick={handleFillDemo} 
                      className="text-xs text-[#002970] hover:text-[#00BAF2] font-bold hover:underline"
                    >
                      Fill Demo Data
                    </button>
                  </div>
                  <p className="text-xs text-slate-500 mt-1 mb-4">We'll send a one-time password to your authorised phone number.</p>
                  
                  <div className="flex items-center gap-2">
                    <div className="relative flex-1 flex items-center">
                      <span className="absolute left-3 text-slate-400 text-sm font-semibold">+91</span>
                      <input 
                        className="w-full pl-11 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-[#00BAF2]/30 focus:border-[#00BAF2] transition-all"
                        inputMode="numeric" maxLength={10} value={mobile} 
                        onChange={(event) => setMobile(event.target.value.replace(/\D/g, ''))} 
                        placeholder="10-digit mobile number" required 
                      />
                    </div>
                    <button 
                      type="button" 
                      onClick={sendOtp} 
                      disabled={mobile.length !== 10}
                      className="px-4 py-2.5 bg-[#002970] hover:bg-[#001b4c] text-white text-sm font-bold rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-all whitespace-nowrap shadow-2xs"
                    >
                      {otpSent ? 'Resend OTP' : 'Send OTP'}
                    </button>
                  </div>

                  {otpSent && (
                    <div className="mt-4 p-4 bg-[#f8fbfe] border border-[#d6ecf8] rounded-xl">
                      <div className="flex justify-between items-center mb-2">
                        <span className="text-xs font-bold text-slate-800">Enter 6-digit OTP</span>
                        <small className="text-[10px] text-slate-500 font-medium">Sent to +91 {mobile.slice(0, 2)}••••••{mobile.slice(-2)}</small>
                      </div>
                      <input 
                        className="w-full text-center tracking-[0.5em] font-mono font-bold py-3 bg-white border border-[#b8e8f8] rounded-xl text-lg text-[#002970] focus:outline-none focus:ring-2 focus:ring-[#00BAF2]/30 focus:border-[#00BAF2] transition-all shadow-inner"
                        inputMode="numeric" maxLength={6} value={otp} 
                        onChange={(event) => setOtp(event.target.value.replace(/\D/g, ''))} 
                        placeholder="••••••" required 
                      />
                      <div className="mt-2 text-center">
                        <small className="text-[10px] text-slate-500">
                          Use 123456 for this demo · <button type="button" className="text-[#002970] font-bold hover:underline" onClick={() => setOtp('123456')}>Fill OTP</button>
                        </small>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Footer Action */}
            <div className="p-6 bg-slate-50/80 border-t border-slate-100 flex flex-col items-center">
              <button 
                type="submit"
                className="w-full flex items-center justify-center gap-2 bg-[#002970] hover:bg-[#001b4c] text-white font-extrabold py-3.5 px-6 rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-md hover:shadow-lg hover:-translate-y-0.5 disabled:hover:translate-y-0"
                disabled={!canSubmit || submitted}
              >
                {submitted ? 'Logging in to Karyakarta...' : otp.length !== 6 ? 'Enter OTP to continue' : 'Log in to Merchant Portal'} 
                <ArrowRight size={17} className={submitted ? "animate-pulse" : ""} />
              </button>
              <div className="mt-4 flex items-center gap-1.5 text-[10px] font-medium text-slate-400">
                <LockKeyhole size={12} /> Powered by Karyakarta AI · Officially partnered with Paytm Business
              </div>
            </div>
          </form>
        </div>
      </main>

      <footer className="py-6 text-center text-[11px] font-medium text-slate-500 flex items-center justify-center gap-4">
        <span>© 2026 KARYAKARTA Technologies (Paytm Business Partner)</span>
        <div className="w-1 h-1 bg-slate-300 rounded-full" />
        <button className="hover:text-[#002970] transition-colors">Privacy Notice</button>
        <button className="hover:text-[#002970] transition-colors">DPDP Terms</button>
        <button className="hover:text-[#002970] transition-colors">Security</button>
      </footer>
    </div>
  );
}
