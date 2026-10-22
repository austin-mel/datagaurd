<script setup lang="ts">
import { SVGIcons } from '@/assets'
import { ModalShell, RuleEditorRow } from '@/components'
import { computed, nextTick, ref, useId, useTemplateRef, watch } from 'vue'
import type { Dataset, DatasetDataSource, DatasetRuleset, QualityRule, RuleEditorCatalog } from '@/types'
import { cloneRuleset, createQualityRule } from '@/utils'
import {
  assertValidRuleset,
  RulesetValidationError,
  isAutomaticIdentifierRule,
  resolveIdentifier,
} from '@/services'

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
      <SVGIcons name="rules" />
    </template>

    <div class="mb-4.75 flex flex-wrap items-center justify-between gap-3.75">
      <div>
        <strong class="block text-[15px] font-semibold">{{ dataset.name }}</strong>
        <p class="mt-1 text-xs text-muted">{{ dataset.source }} · Current version {{ dataset.version }}</p>
      </div>
      <span class="rounded-[5px] bg-cobalt-soft px-1.75 py-1 text-[10px] font-semibold text-cobalt" aria-live="polite">
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
        <table class="w-full min-w-195 border-collapse text-left text-[11px]">
          <thead class="border-y border-line bg-table-header text-[10px] text-muted">
            <tr>
              <th scope="col" class="px-2 py-2.5 font-[550] whitespace-nowrap first:w-10 first:pl-2.5 last:w-8.75 last:pr-2.5">On</th>
              <th scope="col" class="px-2 py-2.5 font-[550] whitespace-nowrap first:w-10 first:pl-2.5 last:w-8.75 last:pr-2.5">Column</th>
              <th scope="col" class="px-2 py-2.5 font-[550] whitespace-nowrap first:w-10 first:pl-2.5 last:w-8.75 last:pr-2.5">Rule type</th>
              <th scope="col" class="px-2 py-2.5 font-[550] whitespace-nowrap first:w-10 first:pl-2.5 last:w-8.75 last:pr-2.5">Condition</th>
              <th scope="col" class="px-2 py-2.5 font-[550] whitespace-nowrap first:w-10 first:pl-2.5 last:w-8.75 last:pr-2.5">Remove</th>
            </tr>
          </thead>
          <tbody>
            <RuleEditorRow v-for="(rule, index) in draft.rules" :key="rule.id"
              v-model="draft.rules[index]!" :number="index + 1" :columns="dataset.columns"
              :rule-catalog="ruleCatalog" :locked="isIdentifierRule(rule)"
              @remove="removeRule(rule.id)" @reset-condition="error = ''" />
            <tr v-if="draft.rules.length === 0"><td colspan="5" class="w-8.75 px-2.5 py-3 text-center align-middle text-muted">No rules yet. Add a rule to start defining your checks.</td></tr>
          </tbody>
        </table>
      </div>
      </fieldset>
      <div v-if="!isCustom" class="flex justify-center pt-4.25">
        <button type="button" class="ui-button ui-button-success" @click="createCustomRuleset">
          <SVGIcons name="add" class="size-4" />
          Create custom ruleset
        </button>
      </div>
      <div v-else class="flex flex-wrap items-center justify-center gap-3.75 pt-4.25">
        <button ref="addButton" type="button" class="ui-button px-2.5 py-1.75 text-[11px]" :disabled="saving || dataset.columns.length === 0" @click="addRule">
          <SVGIcons name="add" class="size-4" />
          Add rule
        </button>
      </div>
      <p v-if="error" :id="errorId" class="mt-4 rounded-[7px] bg-coral-soft p-3 text-xs text-coral-text" role="alert">{{ error }}</p>
      <p v-if="saveError" class="mt-4 rounded-[7px] bg-coral-soft p-3 text-xs text-coral-text" role="alert">{{ saveError }}</p>
    </form>

    <p class="mt-5 flex items-start gap-2 rounded-[7px] bg-cobalt-soft px-3.5 py-3 text-[11px] leading-[1.7]">
      <SVGIcons name="info" class="mt-0.5 size-3.75 text-cobalt" />
      <span v-if="isCustom">Saving applies these rules to <strong>{{ dataset.name }}</strong>. To refresh the validation issues table and update the quality scores click the "Run Dataset Validation" button.</span>
      <span v-else>Create a custom ruleset to change these default checks for <strong>{{ dataset.name }}</strong>.</span>
    </p>

    <template #footer="{ close }">
      <p class="text-[10px] text-muted">{{ sourceKind === 'seeded' ? 'Sample data: changes are kept for this page session.' : 'Changes are saved to the connected workspace.' }}</p>
      <div class="ml-auto flex gap-2.25">
        <button type="button" class="ui-button" :disabled="saving" @click="close"><SVGIcons name="close" class="size-4" /> Cancel</button>
        <button type="submit" :form="formId" class="ui-button ui-button-primary" :disabled="!isCustom || saving"><SVGIcons name="check" class="size-4" /> {{ saving ? 'Saving…' : 'Save rules' }}</button>
      </div>
    </template>
  </ModalShell>
</template>
