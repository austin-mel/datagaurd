import type {
  CellReviewRequest,
  Dataset,
  DatasetDataSource,
  DatasetRuleset,
  DatasetWorkspace,
  UploadPolicy,
} from '@/types'
import type { DatasetUploadSelection } from './datasetUpload'

export interface DatasetRepository {
  readonly source: DatasetDataSource
  getWorkspace(): Promise<DatasetWorkspace>
  download(datasetId: string, version: string): Promise<{ filename: string; blob: Blob }>
  updateRuleset(datasetId: string, ruleset: DatasetRuleset): Promise<Dataset>
  revalidate(datasetId: string, version: string): Promise<Dataset>
  getDataset(datasetId: string): Promise<Dataset>
  applyCellReview(datasetId: string, request: CellReviewRequest): Promise<Dataset>
  getUploadPolicy?(): Promise<UploadPolicy>
  upload?(selection: DatasetUploadSelection): Promise<Dataset>
}

export class BackendUnavailableError extends Error {}
