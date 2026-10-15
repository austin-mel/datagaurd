<script setup lang="ts">
import { computed, nextTick, ref, useId, useTemplateRef, watch } from 'vue'
import { ModalShell } from '../ModalShell'
import type { Dataset, DatasetDataSource, DatasetRuleset, QualityRule, RuleEditorCatalog } from '@/types'
import { cloneRuleset, createQualityRule, ruleDefaults } from '@/utils'
import { assertValidRuleset, RulesetValidationError } from '@/services'
import { isAutomaticIdentifierRule, resolveIdentifier } from '@/services/identifiers'

const props = defineProps<{ dataset: Dataset; ruleCatalog: RuleEditorCatalog; sourceKind: DatasetDataSource['kind']; saving?: boolean; saveError?: string }>()
const isOpen = defineModel<boolean>({ required: true })
const emit = defineEmits<{ save: [ruleset: DatasetRuleset] }>()
const formId = useId()
const errorId = useId()
const addButton = useTemplateRef<HTMLButtonElement>('addButton')
const draft = ref(cloneRuleset(props.dataset.ruleset))
const isCustom = computed(() => draft.value.kind === 'custom')
const error = ref('')
const enabledCount = computed(() => draft.value.rules.filter(rule => rule.enabled).length)
const identifier = computed(() => resolveIdentifier(draft.value, props.dataset.columns))
const isIdentifierRule = (rule: QualityRule) => isAutomaticIdentifierRule(draft.value, rule)

watch([isOpen, () => props.dataset.id], ([open]) => {
  if (open) {
    draft.value = cloneRuleset(props.dataset.ruleset)
    error.value = ''
  }
}, { immediate: true })

async function createCustomRuleset() {
  draft.value = { ...draft.value, id: crypto.randomUUID(), kind: 'custom' }
  error.value = ''
  await nextTick()
  addButton.value?.focus()
}

function addRule() {
  const column = props.dataset.columns[0]
  if (!isCustom.value || props.saving || !column) return
  draft.value.rules.push(createQualityRule(props.ruleCatalog, column))
  error.value = ''
}

async function removeRule(id: string) {
  if (!isCustom.value || props.saving) return
  if (draft.value.rules.some(rule => rule.id === id && isIdentifierRule(rule))) return
  draft.value.rules = draft.value.rules.filter(rule => rule.id !== id)
  error.value = ''
  await nextTick()
  addButton.value?.focus()
}

function resetCondition(rule: QualityRule) {
  if (!isCustom.value || props.saving || isIdentifierRule(rule)) return
  Object.assign(rule, ruleDefaults(props.ruleCatalog, rule.type))
  error.value = ''
}

function saveRules() {
  if (!isCustom.value || props.saving) return
  error.value = ''
  try {
    assertValidRuleset(draft.value, props.dataset.columns)
  } catch (cause) {
    error.value = cause instanceof RulesetValidationError ? cause.message : 'Unable to validate these rules.'
    return
  }
  emit('save', cloneRuleset(draft.value))
}
</script>

<template>
  <ModalShell
    id="quality-rules-dialog"
    v-model="isOpen"
    :title="`Quality rules · ${dataset.name}`"
    eyebrow="DATASET VALIDATION"
    :dismissible="!saving"
  >
    <template #icon>
      <svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M10 6h11M10 12h11M10 18h11M3 5l1 1 2-2M3 11l1 1 2-2M3 17l1 1 2-2" /></svg>
    </template>

    <div class="mb-[19px] flex flex-wrap items-center justify-between gap-[15px]">
      <div>
        <strong class="block text-[15px] font-semibold">{{ dataset.name }}</strong>
        <p class="mt-1 text-xs text-muted">{{ dataset.source }} · Current version {{ dataset.version }}</p>
      </div>
      <span class="rounded-[5px] bg-cobalt-soft px-[7px] py-1 text-[10px] font-semibold text-cobalt" aria-live="polite">
        {{ draft.name }} · {{ enabledCount }} enabled {{ enabledCount === 1 ? 'rule' : 'rules' }}
      </span>
    </div>

    <p v-if="draft.description" class="mb-4 text-xs text-muted">{{ draft.description }}</p>
    <p v-if="draft.backendConfiguration?.identifier_policy === 'auto' && identifier.column" class="mb-4 text-xs text-muted">Automatic identifier checks for {{ identifier.column }} must remain enabled. Add other unique columns as separate rules.</p>
    <p v-if="identifier.reason" class="mb-4 text-xs text-muted" role="status">{{ identifier.reason }} Cell review will show row numbers without an identifier.</p>
    <p class="mb-4 text-xs text-muted">All rules must be complete, including disabled rules. Allowed values are comma-separated; quote values containing commas. Regex uses a plain pattern, up to 200 ASCII characters, with no flags, lookarounds or backreferences. Shorthand classes use ASCII characters.</p>
    <form :id="formId" :aria-describedby="error ? errorId : undefined" @submit.prevent="saveRules">
      <fieldset :disabled="!isCustom || saving" class="min-w-0">
        <legend class="sr-only">{{ isCustom ? 'Custom ruleset' : 'Default rules (read only)' }}</legend>
      <div class="overflow-x-auto" role="region" :aria-label="`${dataset.name} rule editor, horizontally scrollable`" tabindex="0">
        <table class="rule-editor w-full min-w-[780px] border-collapse text-left text-[11px]">
          <thead class="border-y border-line bg-table-header text-[10px] text-muted">
            <tr>
              <th scope="col">On</th>
              <th scope="col">Column</th>
              <th scope="col">Rule type</th>
              <th scope="col">Condition</th>
              <th scope="col">Remove</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(rule, index) in draft.rules" :key="rule.id" class="border-b border-line last:border-0">
              <td>
                <input v-model="rule.enabled" type="checkbox" :disabled="isIdentifierRule(rule)" class="size-3.5 accent-cobalt" :aria-label="`Enable rule ${index + 1}: ${rule.column}`" />
              </td>
              <td>
                <select v-model="rule.column" :disabled="isIdentifierRule(rule)" class="ui-control w-[171px] font-mono" :aria-label="`Column for rule ${index + 1}`">
                  <option v-for="column in dataset.columns" :key="column" :value="column">{{ column }}</option>
                </select>
              </td>
              <td>
                <select v-model="rule.type" :disabled="isIdentifierRule(rule)" class="ui-control w-[135px]" :aria-label="`Type for rule ${index + 1}`" @change="resetCondition(rule)">
                  <option v-for="type in ruleCatalog.ruleTypes" :key="type.value" :value="type.value">{{ type.label }}</option>
                </select>
              </td>
              <td class="min-w-[235px]">
                <div v-if="rule.type === 'range'" class="flex gap-2">
                  <label class="min-w-0 flex-1 text-[9px] text-muted">
                    Minimum
                    <input v-model="rule.minimum" type="number" step="any" class="ui-control mt-[3px]" required :aria-label="`Minimum for rule ${index + 1}`" />
                  </label>
                  <label class="min-w-0 flex-1 text-[9px] text-muted">
                    Maximum
                    <input v-model="rule.maximum" type="number" step="any" class="ui-control mt-[3px]" required :aria-label="`Maximum for rule ${index + 1}`" />
                  </label>
                </div>
                <input v-else-if="rule.type === 'min'" v-model="rule.minimum" type="number" step="any" class="ui-control" required :aria-label="`Minimum for rule ${index + 1}`" />
                <input v-else-if="rule.type === 'max'" v-model="rule.maximum" type="number" step="any" class="ui-control" required :aria-label="`Maximum for rule ${index + 1}`" />
                <div v-else-if="rule.type === 'date'" class="space-y-2">
                  <select v-model="rule.condition" class="ui-control" :aria-label="`Date condition for rule ${index + 1}`">
                    <option v-for="condition in ruleCatalog.dateConditions" :key="condition" :value="condition">{{ condition }}</option>
                  </select>
                  <div class="flex gap-2">
                    <label class="min-w-0 flex-1 text-[9px] text-muted">
                      {{ rule.condition === 'Between two selected dates' ? 'Start date (inclusive)' : 'Selected date' }}
                      <input v-model="rule.selectedDate" type="date" min="0001-01-01" :max="rule.condition === 'Between two selected dates' && rule.endDate ? rule.endDate : '9999-12-31'" required class="ui-control mt-[3px]" :aria-label="`Selected date for rule ${index + 1}`" />
                    </label>
                    <label v-if="rule.condition === 'Between two selected dates'" class="min-w-0 flex-1 text-[9px] text-muted">
                      End date (inclusive)
                      <input v-model="rule.endDate" type="date" :min="rule.selectedDate || '0001-01-01'" max="9999-12-31" required class="ui-control mt-[3px]" :aria-label="`End date for rule ${index + 1}`" />
                    </label>
                  </div>
                </div>
                <input
                  v-else
                  v-model="rule.condition"
                  class="ui-control"
                  :readonly="rule.type === 'required' || rule.type === 'unique' || rule.type === 'numeric'"
                  required
                  :aria-label="`Condition for rule ${index + 1}`"
                />
              </td>
              <td>
                <button type="button" :disabled="isIdentifierRule(rule)" class="cursor-pointer rounded p-[5px] text-muted enabled:hover:bg-coral-soft enabled:hover:text-coral-text disabled:cursor-not-allowed disabled:opacity-40" :aria-label="`Remove rule ${index + 1}: ${rule.column}`" @click="removeRule(rule.id)">
                  <svg class="ui-icon size-3.5" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7" /></svg>
                </button>
              </td>
            </tr>
            <tr v-if="draft.rules.length === 0"><td colspan="5" class="text-center text-muted">No rules yet. Add a rule to start defining your checks.</td></tr>
          </tbody>
        </table>
      </div>
      </fieldset>
      <div v-if="!isCustom" class="flex justify-center pt-[17px]">
        <button type="button" class="ui-button ui-button-success" @click="createCustomRuleset">
          Create custom ruleset
        </button>
      </div>
      <div v-else class="flex flex-wrap items-center justify-center gap-[15px] pt-[17px]">
        <button ref="addButton" type="button" class="ui-button px-2.5 py-[7px] text-[11px]" :disabled="saving || dataset.columns.length === 0" @click="addRule">
          <svg class="ui-icon size-4" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
          Add rule
        </button>
      </div>
      <p v-if="error" :id="errorId" class="mt-4 rounded-[7px] bg-coral-soft p-3 text-xs text-coral-text" role="alert">{{ error }}</p>
      <p v-if="saveError" class="mt-4 rounded-[7px] bg-coral-soft p-3 text-xs text-coral-text" role="alert">{{ saveError }}</p>
    </form>

    <p class="mt-5 flex items-start gap-2 rounded-[7px] bg-cobalt-soft px-3.5 py-3 text-[11px] leading-[1.7]">
      <svg class="ui-icon mt-0.5 size-[15px] text-cobalt" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7h.01" /></svg>
      <span v-if="isCustom">Saving applies these rules to <strong>{{ dataset.name }}</strong>. To refresh the validation issues table and update the quality scores click the "Run Dataset Validation" button.</span>
      <span v-else>Create a custom ruleset to change these default checks for <strong>{{ dataset.name }}</strong>.</span>
    </p>

    <template #footer="{ close }">
      <p class="text-[10px] text-muted">{{ sourceKind === 'seeded' ? 'Sample data: changes are kept for this page session.' : 'Changes are saved to the connected workspace.' }}</p>
      <div class="ml-auto flex gap-[9px]">
        <button type="button" class="ui-button" :disabled="saving" @click="close">Cancel</button>
        <button type="submit" :form="formId" class="ui-button ui-button-primary" :disabled="!isCustom || saving">{{ saving ? 'Saving…' : 'Save rules' }}</button>
      </div>
    </template>
  </ModalShell>
</template>

<style scoped>
.rule-editor th { padding: 10px 8px; font-weight: 550; white-space: nowrap; }
.rule-editor td { padding: 12px 8px; vertical-align: middle; }
.rule-editor th:first-child, .rule-editor td:first-child { padding-left: 10px; width: 40px; }
.rule-editor th:last-child, .rule-editor td:last-child { padding-right: 10px; width: 35px; }
</style>
