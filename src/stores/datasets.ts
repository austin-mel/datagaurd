import { ref, shallowRef } from 'vue'
import { defineStore } from 'pinia'
import { datasetRepository, type DatasetRepository } from '@/services'
import type { Dataset } from '@/types'
import type { DatasetRuleset } from '@/data'

export function createDatasetState(repository: DatasetRepository) {
  const records = shallowRef<Dataset[]>([])
  const status = ref<'idle' | 'loading' | 'ready' | 'error'>('idle')
  const error = ref('')
  let pending: Promise<void> | null = null

  function load(): Promise<void> {
    if (pending) return pending
    if (status.value === 'ready') return Promise.resolve()
    status.value = 'loading'
    error.value = ''
    pending = repository.list().then(data => {
      records.value = data
      status.value = 'ready'
    }).catch(() => {
      error.value = 'Unable to load datasets. Please try again.'
      status.value = 'error'
    }).finally(() => { pending = null })
    return pending
  }

  async function saveRuleset(datasetId: string, ruleset: DatasetRuleset) {
    const updated = await repository.updateRuleset(datasetId, ruleset)
    records.value = records.value.map(record => record.id === datasetId ? updated : record)
  }

  function download(datasetId: string, version: string) {
    return repository.download(datasetId, version)
  }

  return { datasets: records, status, error, load, saveRuleset, download }
}

export const useDatasetStore = defineStore('datasets', () => createDatasetState(datasetRepository))
