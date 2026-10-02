import { Network } from 'lucide-react';

interface BrandProps {
  compact?: boolean;
}

export function Brand({ compact = false }: BrandProps) {
  return <div className={`brand ${compact ? 'brand-compact' : ''}`}><span className="brand-mark"><Network size={compact ? 17 : 19} strokeWidth={2.5} /></span><span>KARYAKARTA</span></div>;
}
