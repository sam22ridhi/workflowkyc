import { useCallback } from 'react';
import { cloneSeedCase } from '@/data/mockCase';
import type { MerchantCase } from '@/types/case';
import { ALL_CASES, useLiveResource, type CaseList } from '@/services/api';

/** One case, live: loads from the backend and refreshes on every audit event.
 *  While the backend is unreachable it shows the bundled sample so the UI still renders, flagged as `offline`. */
export function useLiveCase(caseId: string) {
  const res = useLiveResource<MerchantCase>(caseId, `/api/cases/${caseId}`);
  const sample = useCallback(() => cloneSeedCase(), []);
  const offline = !!res.error && !res.data;
  return { caseData: res.data ?? (offline ? sample() : null), loading: res.loading, offline, error: res.error, reload: res.reload };
}

/** The KAM pipeline: KPIs + case rows, live across all cases. */
export function useLiveCases() {
  const res = useLiveResource<CaseList>(ALL_CASES, '/api/cases');
  return { list: res.data, loading: res.loading, error: res.error, reload: res.reload };
}
