import { computed, ref } from 'vue'
import { beforeEach, expect, it, vi } from 'vitest'
import { useRulesetEditor } from '@/composables/useRulesetEditor'
import { BackendUnavailableError, RulesetValidationError } from '@/services'
import { dataset, ruleset } from '../fixtures/workspace'

const { saveRuleset } = vi.hoisted(() => ({ saveRuleset: vi.fn() }))
vi.mock('@/stores', () => ({ useDatasetStore: () => ({ saveRuleset }) }))
beforeEach(() => { saveRuleset.mockReset() })

it('opens a selected dataset and closes after a successful save', async () => {
  const editor = useRulesetEditor(computed(() => dataset()))
  editor.open()
  expect(editor.isOpen.value).toBe(true)
  await editor.save(ruleset())
  expect(editor.isOpen.value).toBe(false)
  expect(editor.message.value).toContain('Test inventory saved')
  expect(editor.isSaving.value).toBe(false)
})
it.each([
  [new RulesetValidationError('Invalid rules'), 'Invalid rules'],
  [new BackendUnavailableError(), 'draft is still here'],
  [new Error('Unexpected'), 'Your changes are still here'],
])('retains the draft after %s', async (error, text) => {
  saveRuleset.mockRejectedValue(error)
  const editor = useRulesetEditor(computed(() => dataset()))
  editor.open()
  await editor.save(ruleset())
  expect(editor.isOpen.value).toBe(true)
  expect(editor.error.value).toContain(text)
  expect(editor.isSaving.value).toBe(false)
})
it('ignores missing selections and duplicate submissions', async () => {
  const selected = ref<ReturnType<typeof dataset>>()
  const editor = useRulesetEditor(computed(() => selected.value))
  editor.open()
  await editor.save(ruleset())
  expect(saveRuleset).not.toHaveBeenCalled()
  selected.value = dataset()
  let resolve!: () => void
  saveRuleset.mockImplementation(() => new Promise<void>(done => { resolve = done }))
  const pending = editor.save(ruleset())
  await editor.save(ruleset())
  expect(saveRuleset).toHaveBeenCalledTimes(1)
  resolve()
  await pending
})
