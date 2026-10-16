import { createSeededDatasetRepository } from './seededDatasetRepository'
import { BackendUnavailableError, type DatasetRepository } from './datasetRepositoryContract'
import type { DatasetDataSource, DatasetWorkspace } from '@/types'
import { createHttpDatasetRepository } from './httpDatasetRepository'

export type { DatasetRepository } from './datasetRepositoryContract'

// Select one complete workspace source. Never replay a failed live write against seeds.
export function createDatasetRepository(primary?: DatasetRepository, fallback = createSeededDatasetRepository()): DatasetRepository {
  let active: DatasetRepository | undefined
  let pending: Promise<DatasetWorkspace> | undefined
  let source: DatasetDataSource = fallback.source

  async function selectSource(): Promise<DatasetWorkspace> {
    if (primary) {
      try {
        const workspace = await primary.getWorkspace()
        active = primary
        source = primary.source
        return workspace
      } catch (cause) {
        if (!(cause instanceof BackendUnavailableError)) throw cause
      }
    }
    const workspace = await fallback.getWorkspace()
    active = fallback
    source = primary ? { kind: 'seeded', reason: 'backend-unavailable' } : fallback.source
    return workspace
  }

  async function selectedRepository() {
    if (!active) await repository.getWorkspace()
    if (!active) throw new Error('No dataset source is available')
    return active
  }

  const repository: DatasetRepository = {
    get source() { return source },
    getWorkspace() {
      if (active) return active.getWorkspace()
      pending ??= selectSource().finally(() => { pending = undefined })
      return pending
    },
    async download(datasetId, version) {
      return (await selectedRepository()).download(datasetId, version)
    },
    async updateRuleset(datasetId, ruleset) {
      return (await selectedRepository()).updateRuleset(datasetId, ruleset)
    },
    async revalidate(datasetId, version) {
      return (await selectedRepository()).revalidate(datasetId, version)
    },
    async getDataset(datasetId) {
      return (await selectedRepository()).getDataset(datasetId)
    },
    async applyCellReview(datasetId, request) {
      return (await selectedRepository()).applyCellReview(datasetId, request)
    },
    async getUploadPolicy() {
      const selected = await selectedRepository()
      if (!selected.getUploadPolicy) throw new Error('Uploads are not available in this sample workspace.')
      return selected.getUploadPolicy()
    },
    async upload(selection) {
      const selected = await selectedRepository()
      if (!selected.upload) throw new Error('Uploads are not available in this sample workspace.')
      return selected.upload(selection)
    },
  }
  return repository
}

const backendRepository = import.meta.env?.VITE_DATA_SOURCE === 'seeded'
  ? undefined : createHttpDatasetRepository(import.meta.env?.VITE_API_BASE_URL || '/api/v1')
export const datasetRepository = createDatasetRepository(backendRepository)
