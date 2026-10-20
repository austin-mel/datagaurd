import { computed, ref, watch, type Ref } from 'vue'
import { useDatasetStore } from '@/stores'
import type { CellReviewRequest, Dataset } from '@/types'
import { hasPendingValidation } from '@/services'
import { useRulesetEditor } from './useRulesetEditor'
import { useValidationPolling } from './useValidationPolling'

export function useDatasetActions(selectedDataset: Readonly<Ref<Dataset | undefined>>) {
  const datasetStore = useDatasetStore()
  const { isOpen: isRulesOpen, isSaving, error: saveError, message: saveMessage, open: openRules, save: saveRules } = useRulesetEditor(selectedDataset)
  const isRevalidating = ref(false)
  const validationError = ref('')
  const isReviewSaving = ref(false)
  const reviewError = ref('')
  const reviewMessage = ref('')
  const validationPending = computed(() => !!selectedDataset.value && hasPendingValidation(selectedDataset.value))
  const busy = computed(() => isRevalidating.value || isSaving.value || isReviewSaving.value || selectedDataset.value?.processingStatus === 'running')

  watch(() => selectedDataset.value?.id, () => {
    isRulesOpen.value = false
    saveMessage.value = ''
    validationError.value = ''
    reviewError.value = ''
    reviewMessage.value = ''
  }, { immediate: true })
  useValidationPolling(selectedDataset, validationError)

  async function rerunValidation() {
    const dataset = selectedDataset.value
    if (!dataset || !validationPending.value || busy.value) return
    isRevalidating.value = true
    validationError.value = ''
    saveMessage.value = ''
    reviewMessage.value = ''
    try { await datasetStore.revalidate(dataset.id, dataset.version) }
    catch (cause) {
      if (selectedDataset.value?.id === dataset.id) validationError.value = cause instanceof Error ? cause.message : 'Unable to re-run validation.'
    } finally { isRevalidating.value = false }
  }

  async function saveCellReview(request: CellReviewRequest) {
    const dataset = selectedDataset.value
    if (!dataset || busy.value) return
    isReviewSaving.value = true
    reviewError.value = ''
    reviewMessage.value = ''
    try {
      await datasetStore.applyCellReview(dataset.id, request)
      if (selectedDataset.value?.id === dataset.id) reviewMessage.value = request.action.type === 'ignore'
        ? 'Finding ignored. Run validation to refresh error counts and scores.'
        : 'New dataset version saved. Click Run Dataset Validation when you are ready.'
    } catch (cause) {
      if (selectedDataset.value?.id === dataset.id) reviewError.value = cause instanceof Error ? cause.message : 'Unable to save the changes. Please try again.'
    } finally { isReviewSaving.value = false }
  }
  return { isRulesOpen, isSaving, saveError, saveMessage, openRules, saveRules, isRevalidating, validationError,
    isReviewSaving, reviewError, reviewMessage, validationPending, rerunValidation, saveCellReview }
}
