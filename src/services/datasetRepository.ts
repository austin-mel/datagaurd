import { createSeededDatasetRepository } from './seededDatasetRepository'
import { BackendUnavailableError, type DatasetRepository } from './datasetRepositoryContract'
import type { DatasetDataSource, DatasetWorkspace } from '@/types'

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
      if (active === fallback) return fallback.getWorkspace()
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
  }
  return repository
}

// Future backend integration point: supply an implementation of DatasetRepository here.
// No HTTP client, endpoint configuration, or network requests are implemented yet.
const backendRepository: DatasetRepository | undefined = undefined
export const datasetRepository = createDatasetRepository(backendRepository)
