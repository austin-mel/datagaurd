import { ref, type ComputedRef } from 'vue'
import type { Dataset } from '@/types'
import type { DatasetRuleset } from '@/data'
import { useDatasetStore } from '@/stores'
import { RulesetValidationError } from '@/services'

export function useRulesetEditor(dataset: ComputedRef<Dataset | undefined>) {
  const { saveRuleset } = useDatasetStore()
  const isOpen = ref(false)
  const isSaving = ref(false)
  const error = ref('')
  const message = ref('')

  function open() {
    if (!dataset.value || isSaving.value) return
    error.value = ''
    message.value = ''
    isOpen.value = true
  }

  async function save(ruleset: DatasetRuleset) {
    const selected = dataset.value
    if (!selected || isSaving.value) return
    isSaving.value = true
    error.value = ''
    try {
      await saveRuleset(selected.id, ruleset)
      isOpen.value = false
      message.value = `Quality rules for ${selected.name} saved. Validation issues and quality scores updated.`
    } catch (cause) {
      error.value = cause instanceof RulesetValidationError ? cause.message : 'Unable to save rules. Your changes are still here; please try again.'
    } finally {
      isSaving.value = false
    }
  }

  return { isOpen, isSaving, error, message, open, save }
}
