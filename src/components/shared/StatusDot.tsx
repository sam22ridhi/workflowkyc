import type { FindingStatus } from '@/types/case';

export function StatusDot({ status }: { status: FindingStatus }) {
  return <span className={`status-dot status-dot-${status}`} aria-label={status === 'verified' ? 'Verified' : 'Exception'} />;
}
