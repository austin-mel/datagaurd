import { ref, shallowRef } from 'vue'
import { defineStore } from 'pinia'
import { datasetRepository, type DatasetRepository } from '@/services'
import type { Dataset, DatasetDataSource, DatasetRuleset, RuleEditorCatalog } from '@/types'

export function createDatasetState(repository: DatasetRepository) {
  const records = shallowRef<Dataset[]>([])
  const ruleCatalog = shallowRef<RuleEditorCatalog | null>(null)
  const source = shallowRef<DatasetDataSource | null>(null)
  const status = ref<'idle' | 'loading' | 'ready' | 'error'>('idle')
  const error = ref('')
  let pending: Promise<void> | null = null

  function load(): Promise<void> {
    if (pending) return pending
    if (status.value === 'ready') return Promise.resolve()
    status.value = 'loading'
    error.value = ''
    pending = repository.getWorkspace().then(workspace => {
      records.value = workspace.datasets
      ruleCatalog.value = workspace.ruleCatalog
      source.value = repository.source
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

  async function refreshDataset(datasetId: string) {
    const updated = await repository.getDataset(datasetId)
    records.value = records.value.map(record => record.id === datasetId ? updated : record)
  }

  async function revalidate(datasetId: string, version: string) {
    const previous = records.value.find(record => record.id === datasetId)
    if (!previous || previous.processingStatus === 'running' || !previous.rulesChangedSinceRun) return
    records.value = records.value.map(record => record.id === datasetId ? {
      ...record, processingStatus: 'running', status: 'running', quality: null,
      lastValidatedAt: null, validation: null, columnProfiles: null,
      qualityDimensions: record.qualityDimensions.map(dimension => ({ ...dimension, score: null, passed: null, total: null })),
      qualityNote: 'Validation is running. Results are not available yet.',
    } : record)
    try {
      const updated = await repository.revalidate(datasetId, version)
      records.value = records.value.map(record => record.id === datasetId ? updated : record)
    } catch (cause) {
      // A transport failure can follow a committed run. Reconcile before claiming failure.
      try { await refreshDataset(datasetId) } catch {
        records.value = records.value.map(record => record.id === datasetId ? {
          ...record, processingStatus: 'failed', status: 'failed',
          processingError: 'Unable to confirm validation. Refresh to retrieve the latest attempt.',
          qualityNote: 'Validation results are not available.',
        } : record)
      }
      throw cause
    }
  }

  function download(datasetId: string, version: string) {
    return repository.download(datasetId, version)
  }

  return { datasets: records, ruleCatalog, source, status, error, load, saveRuleset, download, revalidate, refreshDataset }
}

export const useDatasetStore = defineStore('datasets', () => createDatasetState(datasetRepository))
