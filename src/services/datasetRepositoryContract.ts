import type { Dataset, DatasetDataSource, DatasetRuleset, DatasetWorkspace } from '@/types'

export interface DatasetRepository {
  readonly source: DatasetDataSource
  getWorkspace(): Promise<DatasetWorkspace>
  download(datasetId: string, version: string): Promise<{ filename: string; blob: Blob }>
  updateRuleset(datasetId: string, ruleset: DatasetRuleset): Promise<Dataset>
  revalidate(datasetId: string, version: string): Promise<Dataset>
  getDataset(datasetId: string): Promise<Dataset>
}

export class BackendUnavailableError extends Error {}
