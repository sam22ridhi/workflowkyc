import { AppLogo } from '@/components/shared/AppLogo';

interface BrandProps {
  compact?: boolean;
}

/** Product mark (the Paytm logo with the product name), used on the public pages. */
export function Brand({ compact = false }: BrandProps) {
  return <AppLogo size={compact ? 'sm' : 'md'} />;
}
