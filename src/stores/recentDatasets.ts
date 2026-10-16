import { computed, shallowRef, watch } from 'vue'
import { defineStore } from 'pinia'
import { canonicalDatasetId } from '@/data/datasetIds'

export interface RecentDatasetVisit {
  datasetId: string
  openedAt: number
}

export const RECENT_DATASETS_KEY = 'dataguard.recentDatasets.v1'
const MAX_RECENT = 3
type HistoryStorage = Pick<Storage, 'getItem' | 'setItem'>

function browserLocalStorage(): HistoryStorage | undefined {
  try { return typeof window === 'undefined' ? undefined : window.localStorage } catch { return undefined }
}

export function createRecentDatasetHistory(storage = browserLocalStorage()) {
  const visits = shallowRef<RecentDatasetVisit[]>([])
  try {
    const stored: unknown = JSON.parse(storage?.getItem(RECENT_DATASETS_KEY) ?? '[]')
    if (Array.isArray(stored)) {
      const seen = new Set<string>()
      visits.value = stored.filter((entry): entry is RecentDatasetVisit =>
        typeof entry === 'object' && entry !== null
        && typeof entry.datasetId === 'string' && entry.datasetId.trim().length > 0
        && typeof entry.openedAt === 'number' && entry.openedAt >= 0 && !Number.isNaN(new Date(entry.openedAt).getTime()),
      ).map(entry => ({ ...entry, datasetId: canonicalDatasetId(entry.datasetId) }))
        .sort((a, b) => b.openedAt - a.openedAt).filter(entry => {
        if (seen.has(entry.datasetId)) return false
        seen.add(entry.datasetId)
        return true
      }).slice(0, MAX_RECENT).map(({ datasetId, openedAt }) => ({ datasetId, openedAt }))
    }
  } catch { /* A blocked or malformed storage entry must not prevent navigation. */ }

  function persist() {
    try { storage?.setItem(RECENT_DATASETS_KEY, JSON.stringify(visits.value)) } catch { /* Keep recents in memory when storage is unavailable. */ }
  }

  function record(datasetId: string, openedAt = Date.now()) {
    if (!datasetId.trim() || openedAt < 0 || Number.isNaN(new Date(openedAt).getTime())) return
    visits.value = [{ datasetId, openedAt }, ...visits.value.filter(visit => visit.datasetId !== datasetId)].slice(0, MAX_RECENT)
  }

  function reconcile(availableIds: readonly string[]) {
    const available = new Set(availableIds)
    visits.value = visits.value.filter(visit => available.has(visit.datasetId))
  }

  watch(visits, persist, { deep: true, flush: 'sync' })
  persist()
  return { visits, lastOpenedId: computed(() => visits.value[0]?.datasetId), record, reconcile }
}

export const useRecentDatasetStore = defineStore('recent-datasets', () => createRecentDatasetHistory())
