interface AppLogoProps {
  /** Small line under the product name. */
  subtitle?: string;
  /** Text after KARYAKARTA, e.g. "·AI" or "·Drishti". */
  suffix?: string;
  /** Show the logo on a white chip, for dark backgrounds (the navy "pay" letters need a light ground). */
  onDark?: boolean;
  size?: 'sm' | 'md' | 'lg';
  /** Hide the product name and show the logo only. */
  logoOnly?: boolean;
}

const HEIGHT = { sm: 'h-5', md: 'h-6', lg: 'h-8' } as const;

/** The Paytm logo as the app mark, with the product name next to it. */
export function AppLogo({ subtitle, suffix = '·AI', onDark = false, size = 'md', logoOnly = false }: AppLogoProps) {
  const img = <img src="/paytm-logo.png" alt="Paytm" className={`${HEIGHT[size]} w-auto select-none`} draggable={false} />;
  return (
    <span className="inline-flex items-center gap-3 leading-tight">
      {onDark ? <span className="inline-flex items-center rounded-lg bg-white px-2.5 py-1.5 shadow-sm">{img}</span> : img}
      {!logoOnly && (
        <>
          <span className={`h-6 w-px ${onDark ? 'bg-white/25' : 'bg-slate-200'}`} aria-hidden />
          <span className="flex flex-col items-start">
            <strong className={`text-[13px] font-extrabold tracking-widest ${onDark ? 'text-white' : 'text-[#002970]'}`}>
              KARYAKARTA<span className="text-[#00BAF2] font-black ml-0.5">{suffix}</span>
            </strong>
            {subtitle && <span className={`text-[10px] font-bold uppercase tracking-wider ${onDark ? 'text-sky-200/80' : 'text-slate-400'}`}>{subtitle}</span>}
          </span>
        </>
      )}
    </span>
  );
}
