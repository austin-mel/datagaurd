import { ref, shallowRef } from 'vue'
import { defineStore } from 'pinia'
import { datasetRepository, type DatasetRepository, clearValidationResults, hasPendingValidation } from '@/services'
import type {
  CellReviewRequest,
  Dataset,
  DatasetDataSource,
  DatasetRuleset,
  RuleEditorCatalog,
  UploadPolicy,
} from '@/types'
import type { DatasetUploadSelection } from '@/services'

export function createDatasetState(repository: DatasetRepository) {
  const records = shallowRef<Dataset[]>([])
  const ruleCatalog = shallowRef<RuleEditorCatalog | null>(null)
  const source = shallowRef<DatasetDataSource | null>(null)
  const status = ref<'idle' | 'loading' | 'ready' | 'error'>('idle')
  const error = ref('')
  const uploadPolicy = shallowRef<UploadPolicy | null>(null)
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
    }).catch(cause => {
      error.value = cause instanceof Error ? cause.message : 'Unable to load datasets. Please try again.'
      status.value = 'error'
    }).finally(() => { pending = null })
    return pending
  }

  function replaceDataset(datasetId: string, updated: Dataset) {
    records.value = records.value.map(record => record.id === datasetId ? updated : record)
  }

  async function saveRuleset(datasetId: string, ruleset: DatasetRuleset) {
    const updated = await repository.updateRuleset(datasetId, ruleset)
    replaceDataset(datasetId, updated)
  }

  async function refreshDataset(datasetId: string) {
    const updated = await repository.getDataset(datasetId)
    replaceDataset(datasetId, updated)
  }

  async function applyCellReview(datasetId: string, request: CellReviewRequest) {
    const updated = await repository.applyCellReview(datasetId, request)
    replaceDataset(datasetId, updated)
  }

  async function revalidate(datasetId: string, version: string) {
    const previous = records.value.find(record => record.id === datasetId)
    if (!previous || !hasPendingValidation(previous)) return
    records.value = records.value.map(record => record.id === datasetId ? {
      ...clearValidationResults(record), processingStatus: 'running', status: 'running', cellReview: null,
      qualityNote: 'Validation is running. Results are not available yet.',
    } : record)
    try {
      const updated = await repository.revalidate(datasetId, version)
      replaceDataset(datasetId, updated)
    } catch (cause) {
      // A transport failure can follow a committed run. Reconcile before claiming failure.
      try { await refreshDataset(datasetId) } catch {
        records.value = records.value.map(record => record.id === datasetId ? {
          ...record, processingStatus: 'failed', status: 'failed', validationPending: true,
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

  async function loadUploadPolicy() {
    uploadPolicy.value = null
    if (source.value?.kind !== 'api' || !repository.getUploadPolicy) throw new Error('Uploads require a live backend connection.')
    uploadPolicy.value = await repository.getUploadPolicy()
  }
  async function upload(selection: DatasetUploadSelection) {
    if (source.value?.kind !== 'api' || !repository.upload) throw new Error('Uploads require a live backend connection.')
    const dataset = await repository.upload(selection)
    records.value = [dataset, ...records.value.filter(record => record.id !== dataset.id)]
    return dataset
  }

  return { datasets: records, ruleCatalog, source, status, error, uploadPolicy, load, saveRuleset, download, revalidate, refreshDataset, applyCellReview, loadUploadPolicy, upload }
}

export const useDatasetStore = defineStore('datasets', () => createDatasetState(datasetRepository))
