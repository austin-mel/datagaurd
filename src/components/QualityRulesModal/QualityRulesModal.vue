<script setup lang="ts">
import { computed, nextTick, ref, useId, useTemplateRef, watch } from 'vue'
import { ModalShell } from '../ModalShell'
import { facilities, facilityColumns, ruleTypes, ruleCondition, type QualityRule } from '@/data'

const props = defineProps<{ rules: readonly QualityRule[] }>()
const isOpen = defineModel<boolean>({ required: true })
const emit = defineEmits<{ save: [rules: QualityRule[]] }>()
const formId = useId()
const errorId = useId()
const addButton = useTemplateRef<HTMLButtonElement>('addButton')
const draft = ref<QualityRule[]>([])
const error = ref('')
const enabledCount = computed(() => draft.value.filter(rule => rule.enabled).length)

watch(isOpen, (open) => {
  if (open) {
    draft.value = props.rules.map(rule => ({ ...rule }))
    error.value = ''
  }
}, { immediate: true })

function addRule() {
  draft.value.push({
    id: crypto.randomUUID(), enabled: true, column: 'facility_id', type: 'required',
    condition: ruleCondition('required'), minimum: 0, maximum: 100, severity: 'High',
  })
  error.value = ''
}

async function removeRule(id: string) {
  draft.value = draft.value.filter(rule => rule.id !== id)
  error.value = ''
  await nextTick()
  addButton.value?.focus()
}

function resetCondition(rule: QualityRule) {
  rule.condition = ruleCondition(rule.type)
  rule.minimum = 0
  rule.maximum = 100
  error.value = ''
}

function saveRules() {
  error.value = ''
  for (const rule of draft.value.filter(rule => rule.enabled)) {
    if (rule.type === 'range' && (rule.minimum === '' || rule.maximum === '' || rule.minimum > rule.maximum)) {
      error.value = `${rule.column}: the minimum must be less than or equal to the maximum.`
      return
    }
    if (['allowed', 'date', 'regex'].includes(rule.type) && !rule.condition.trim()) {
      error.value = `${rule.column}: enter a condition.`
      return
    }
    if (rule.type === 'regex') {
      try { new RegExp(rule.condition) } catch {
        error.value = `${rule.column}: enter a valid regular expression.`
        return
      }
    }
  }
  emit('save', draft.value.map(rule => ({ ...rule })))
  isOpen.value = false
}
</script>

<template>
  <ModalShell
    id="quality-rules-dialog"
    v-model="isOpen"
    :title="`Quality rules · ${facilities.name}`"
    eyebrow="DATASET VALIDATION"
  >
    <template #icon>
      <svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M10 6h11M10 12h11M10 18h11M3 5l1 1 2-2M3 11l1 1 2-2M3 17l1 1 2-2" /></svg>
    </template>

    <div class="mb-[19px] flex flex-wrap items-center justify-between gap-[15px]">
      <div>
        <strong class="block text-[15px] font-semibold">{{ facilities.name }}</strong>
        <p class="mt-1 text-xs text-muted">{{ facilities.source }} · Current version {{ facilities.version }}</p>
      </div>
      <span class="rounded-[5px] bg-cobalt-soft px-[7px] py-1 text-[10px] font-semibold text-cobalt" aria-live="polite">
        {{ enabledCount }} enabled {{ enabledCount === 1 ? 'rule' : 'rules' }}
      </span>
    </div>

    <form :id="formId" :aria-describedby="error ? errorId : undefined" @submit.prevent="saveRules">
      <div class="overflow-x-auto" role="region" aria-label="County facilities rule editor, horizontally scrollable" tabindex="0">
        <table class="rule-editor w-full min-w-[875px] border-collapse text-left text-[11px]">
          <thead class="border-y border-line bg-table-header text-[10px] text-muted">
            <tr>
              <th scope="col">On</th>
              <th scope="col">Column</th>
              <th scope="col">Rule type</th>
              <th scope="col">Condition</th>
              <th scope="col">Severity</th>
              <th scope="col">Remove</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(rule, index) in draft" :key="rule.id" class="border-b border-line last:border-0">
              <td>
                <input v-model="rule.enabled" type="checkbox" class="size-3.5 accent-cobalt" :aria-label="`Enable rule ${index + 1}: ${rule.column}`" />
              </td>
              <td>
                <select v-model="rule.column" class="ui-control w-[171px] font-mono" :aria-label="`Column for rule ${index + 1}`">
                  <option v-for="column in facilityColumns" :key="column" :value="column">{{ column }}</option>
                </select>
              </td>
              <td>
                <select v-model="rule.type" class="ui-control w-[135px]" :aria-label="`Type for rule ${index + 1}`" @change="resetCondition(rule)">
                  <option v-for="type in ruleTypes" :key="type.value" :value="type.value">{{ type.label }}</option>
                </select>
              </td>
              <td class="min-w-[235px]">
                <div v-if="rule.type === 'range'" class="flex gap-2">
                  <label class="min-w-0 flex-1 text-[9px] text-muted">
                    Minimum
                    <input v-model="rule.minimum" type="number" step="any" class="ui-control mt-[3px]" :required="rule.enabled" :aria-label="`Minimum for rule ${index + 1}`" />
                  </label>
                  <label class="min-w-0 flex-1 text-[9px] text-muted">
                    Maximum
                    <input v-model="rule.maximum" type="number" step="any" class="ui-control mt-[3px]" :required="rule.enabled" :aria-label="`Maximum for rule ${index + 1}`" />
                  </label>
                </div>
                <input v-else-if="rule.type === 'min'" v-model="rule.minimum" type="number" step="any" class="ui-control" :required="rule.enabled" :aria-label="`Minimum for rule ${index + 1}`" />
                <input v-else-if="rule.type === 'max'" v-model="rule.maximum" type="number" step="any" class="ui-control" :required="rule.enabled" :aria-label="`Maximum for rule ${index + 1}`" />
                <input
                  v-else
                  v-model="rule.condition"
                  class="ui-control"
                  :readonly="rule.type === 'required' || rule.type === 'unique'"
                  :required="rule.enabled"
                  :aria-label="`Condition for rule ${index + 1}`"
                />
              </td>
              <td>
                <select v-model="rule.severity" class="ui-control w-[95px]" :aria-label="`Severity for rule ${index + 1}`">
                  <option>High</option><option>Medium</option><option>Low</option>
                </select>
              </td>
              <td>
                <button type="button" class="cursor-pointer rounded p-[5px] text-muted hover:bg-coral-soft hover:text-coral-text" :aria-label="`Remove rule ${index + 1}: ${rule.column}`" @click="removeRule(rule.id)">
                  <svg class="ui-icon size-3.5" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7" /></svg>
                </button>
              </td>
            </tr>
            <tr v-if="draft.length === 0"><td colspan="6" class="text-center text-muted">No rules yet. Add a rule to start defining your checks.</td></tr>
          </tbody>
        </table>
      </div>
      <div class="flex flex-wrap items-center justify-between gap-[15px] pt-[17px]">
        <button ref="addButton" type="button" class="ui-button px-2.5 py-[7px] text-[11px]" @click="addRule">
          <svg class="ui-icon size-4" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
          Add rule
        </button>
        <p class="text-[11px] text-muted">Required and unique checks are evaluated separately.</p>
      </div>
      <p v-if="error" :id="errorId" class="mt-4 rounded-[7px] bg-coral-soft p-3 text-xs text-coral-text" role="alert">{{ error }}</p>
    </form>

    <p class="mt-5 flex items-start gap-2 rounded-[7px] bg-cobalt-soft px-3.5 py-3 text-[11px] leading-[1.7]">
      <svg class="ui-icon mt-0.5 size-[15px] text-cobalt" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7h.01" /></svg>
      <span>These rules apply only to <strong>{{ facilities.name }}</strong>. Other datasets keep their own rules.</span>
    </p>

    <template #footer="{ close }">
      <p class="text-[10px] text-muted">Changes are kept for this page session.</p>
      <div class="ml-auto flex gap-[9px]">
        <button type="button" class="ui-button" @click="close">Cancel</button>
        <button type="submit" :form="formId" class="ui-button ui-button-primary">Save rules</button>
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
