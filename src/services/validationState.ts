import type { Dataset } from '../types'

export function hasPendingValidation(dataset: Dataset): boolean {
  return dataset.processingStatus !== 'running' && (dataset.processingStatus === 'failed'
    || dataset.processingStatus === 'not_started' || dataset.validationPending === true
    || dataset.rulesChangedSinceRun || !!dataset.reviewChangedSinceRun || !!dataset.dataChangedSinceRun)
}
