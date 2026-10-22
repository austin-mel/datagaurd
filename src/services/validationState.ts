import type { Dataset } from '@/types'

export function hasPendingValidation(dataset: Dataset): boolean {
  return dataset.processingStatus !== 'running' && (dataset.processingStatus === 'failed'
    || dataset.processingStatus === 'not_started' || dataset.validationPending === true
    || dataset.rulesChangedSinceRun || !!dataset.reviewChangedSinceRun || !!dataset.dataChangedSinceRun)
}

export function clearValidationResults(dataset: Dataset): Dataset {
  return {
    ...dataset,
    quality: null, lastValidatedAt: null, validation: null, columnProfiles: null,
    qualityDimensions: dataset.qualityDimensions.map(dimension => ({ ...dimension, score: null, passed: null, total: null })),
  }
}
