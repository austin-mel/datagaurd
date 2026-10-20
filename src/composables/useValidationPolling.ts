import { onUnmounted, watch, type Ref } from 'vue'
import { useDatasetStore } from '@/stores'
import type { Dataset } from '@/types'

export function useValidationPolling(selectedDataset: Readonly<Ref<Dataset | undefined>>, validationError: Ref<string>) {
  const datasetStore = useDatasetStore()
  // Future repositories may return a persisted running attempt before it completes.
  let refreshTimer: ReturnType<typeof setTimeout> | undefined
  let disposed = false
  function scheduleRefresh() {
    clearTimeout(refreshTimer)
    if (disposed || selectedDataset.value?.processingStatus !== 'running') return
    const id = selectedDataset.value.id
    refreshTimer = setTimeout(async () => {
      try { await datasetStore.refreshDataset(id) }
      catch { validationError.value = 'Unable to refresh validation status. Retrying…' }
      scheduleRefresh()
    }, 3000)
  }
  watch(() => [selectedDataset.value?.id, selectedDataset.value?.processingStatus], scheduleRefresh)
  onUnmounted(() => { disposed = true; clearTimeout(refreshTimer) })
}
