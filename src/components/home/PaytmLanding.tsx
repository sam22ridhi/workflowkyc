import { ArrowRight, ArrowUpRight, CloudUpload, Play, ShieldCheck, Sparkles } from 'lucide-react';
import { AppLogo } from '@/components/shared/AppLogo';
import './landing.css';

interface LandingProps {
  onAuth: () => void;
  onMerchant: () => void;
  onKAM: () => void;
}

const FEATURES = [
  { icon: <CloudUpload size={22} />, title: 'Drop it in.', text: 'Upload what you have. We understand the rest, from board resolutions to GST certificates.' },
  { icon: <Sparkles size={22} />, title: 'We make sense of it.', text: 'Our AI reads, extracts, and cross-checks every detail so nothing gets lost in the fine print.' },
  { icon: <ShieldCheck size={22} />, title: 'Move forward, confidently.', text: 'See exactly what is verified, what needs attention, and what to do next, in plain English.' },
];

/** The public front door: Paytm navy background, Paytm cyan accents, a clip-art scene instead of a product mock-up. */
export function Landing({ onAuth, onMerchant, onKAM }: LandingProps) {
  return (
    <div className="lp">
      <header className="lp-nav">
        <AppLogo onDark suffix="·AI" />
        <nav className="lp-links" aria-label="Sections">
          <a href="#product">Product</a>
          <a href="#solutions">Solutions</a>
          <a href="#trust">Trust &amp; security</a>
          <a href="#resources">Resources</a>
        </nav>
        <div className="lp-actions">
          <button className="lp-btn lp-btn-ghost" onClick={onAuth}>Sign in</button>
          <button className="lp-btn lp-btn-primary" onClick={onAuth}>Get started <ArrowUpRight size={15} /></button>
        </div>
      </header>

      <main>
        <section className="lp-hero" id="product">
          <div className="lp-copy">
            <div className="lp-eyebrow"><span className="lp-dot" />The intelligent merchant onboarding system</div>
            <h1>Get your business <em>onboarded.</em></h1>
            <p className="lp-lead">Tell us about your business. We&rsquo;ll handle the paperwork, verification, and everything in between.</p>
            <div className="lp-hero-actions">
              <button className="lp-btn lp-btn-primary lp-btn-lg" onClick={onMerchant}>Start onboarding <ArrowRight size={18} /></button>
              <button className="lp-btn lp-btn-ghost lp-btn-lg" onClick={onKAM}><Play size={16} fill="currentColor" /> See how it works</button>
            </div>
            <div className="lp-proof">
              <div className="lp-avatars" aria-hidden><span>RS</span><span>AS</span><span>MK</span><span>+</span></div>
              <span>Trusted by teams building India&rsquo;s next economy</span>
            </div>
          </div>
          <div className="lp-art">
            <img src="/landing-illustration.svg" alt="A reviewer and a merchant looking at business profiles that the AI has verified" />
          </div>
        </section>

        <section className="lp-trust" id="trust">
          <span>BUILT FOR THE WAY BUSINESS MOVES</span>
          <strong>Fast onboarding</strong>
          <strong>Bank-grade security</strong>
          <strong>Intelligent by default</strong>
          <strong>Human when it matters</strong>
        </section>

        <section className="lp-story" id="solutions">
          <div className="lp-story-head">
            <div>
              <div className="lp-label">A better way to begin</div>
              <h2 className="lp-h2">The hard part of starting <em>shouldn&rsquo;t be paperwork.</em></h2>
            </div>
            <p>KARYAKARTA turns corporate onboarding from a process to endure into a journey that moves at the speed of your business.</p>
          </div>
          <div className="lp-cards">
            {FEATURES.map((f, i) => (
              <article className="lp-card" key={f.title}>
                <div className="lp-card-top"><span className="lp-icon">{f.icon}</span><span className="lp-num">0{i + 1}</span></div>
                <h3>{f.title}</h3>
                <p>{f.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="lp-quote" id="resources">
          <div className="lp-quote-mark">&ldquo;</div>
          <blockquote>Onboarding shouldn&rsquo;t feel like a test of patience. It should feel like the first step in a great partnership.</blockquote>
          <div className="lp-by"><span className="lp-by-avatar">K</span><span><strong>KARYAKARTA</strong><small>Built for better business banking</small></span></div>
        </section>

        <section className="lp-cta">
          <div>
            <div className="lp-eyebrow"><span className="lp-dot" />Ready when you are</div>
            <h2>Let&rsquo;s get your business <em>moving.</em></h2>
          </div>
          <button className="lp-btn lp-btn-white lp-btn-lg" onClick={onAuth}>Create your account <ArrowRight size={18} /></button>
        </section>
      </main>

      <footer className="lp-footer">
        <AppLogo onDark logoOnly size="sm" />
        <span>&copy; 2026 KARYAKARTA</span>
        <div><a href="#trust">Privacy</a><a href="#trust">Security</a><a href="#trust">Contact</a></div>
      </footer>
    </div>
  );
}
