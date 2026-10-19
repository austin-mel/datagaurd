<script setup lang="ts">
import CellEditForm from './CellEditForm.vue'
import CellIgnoreForm from './CellIgnoreForm.vue'
import { computed, ref, watch } from 'vue'
import type { CellReviewGroup, CellReviewRequest, Dataset } from '@/types'
import { formatNumber } from '@/utils'
import { ModalShell } from '@/components/shared'

const props = defineProps<{ dataset: Dataset; group: CellReviewGroup; initialRow: number; mode: 'edit' | 'ignore'; saving?: boolean; error?: string }>()
const emit = defineEmits<{ save: [request: CellReviewRequest] }>()
const isOpen = defineModel<boolean>({ required: true })
const row = ref(props.initialRow)
const action = ref<'custom' | 'null' | 'remove'>('custom')
const replacement = ref(''), reason = ref(''), scope = ref<'one' | 'all'>('one')
watch([isOpen, () => props.group, () => props.initialRow, () => props.mode], () => {
  row.value = props.initialRow; action.value = 'custom'; replacement.value = ''; reason.value = ''; scope.value = 'one'
})
const warning = computed(() => props.group.kind === 'warning')
const color = computed(() => warning.value ? 'bg-yellow-100 text-yellow-800' : 'bg-coral-soft text-coral-text')
const title = computed(() => props.mode === 'edit' ? 'Edit flagged cell' : warning.value ? 'Ignore anomaly warning' : 'Ignore rule error')
const count = computed(() => props.group.cells.length)
const uniqueColumn = computed(() => props.dataset.ruleset.rules.some(rule => rule.enabled && rule.type === 'unique' && rule.column === props.group.column))
const bulkUnavailable = computed(() => uniqueColumn.value && count.value > 1 && action.value !== 'remove')
const unchanged = computed(() => action.value === 'null' ? props.group.currentValue === null
  : action.value === 'custom' && props.group.currentValue !== null && replacement.value === String(props.group.currentValue))
const cannotSave = computed(() => props.saving || unchanged.value || (action.value === 'custom' && !replacement.value.trim()))
function save(target: 'one' | 'all') {
  if (props.saving || (props.mode === 'edit' && (cannotSave.value || (target === 'all' && bulkUnavailable.value)))) return
  emit('save', { version: props.dataset.version, groupId: props.group.id, rowNumber: row.value, scope: target,
    action: props.mode === 'ignore' ? { type: 'ignore', reason: reason.value }
      : action.value === 'remove' ? { type: 'delete-row' } : { type: 'replace', value: action.value === 'null' ? null : replacement.value },
  })
}
</script>

<template>
  <ModalShell v-model="isOpen" :title="title" :eyebrow="mode === 'edit' ? 'REVIEW A CORRECTION' : 'REVIEW A FINDING'" :dismissible="!saving"
    :description="mode === 'edit' ? 'Save changes to a new dataset version. Validation runs only when you click Run Dataset Validation.' : 'Remove findings from review and exclude them from future validation errors.'">
    <fieldset :disabled="saving" class="min-w-0 border-0 p-0">
    <div class="mb-4 flex flex-wrap items-center gap-2 text-xs">
      <strong class="font-semibold">{{ dataset.name }} · {{ dataset.version }}</strong>
      <code class="wrap-anywhere">{{ group.column }}</code>
      <span class="ui-badge" :class="color">{{ warning ? 'Anomaly warning' : 'Rule violation' }}</span>
    </div>
    <p class="mb-4 rounded-md px-3 py-2.5 text-xs leading-6" :class="color">{{ group.reason }}</p>
    <CellEditForm v-if="mode === 'edit'" v-model:row="row" v-model:action="action" v-model:replacement="replacement"
      :dataset="dataset" :group="group" :bulk-unavailable="bulkUnavailable" :color="color" />
    <CellIgnoreForm v-else v-model:scope="scope" v-model:reason="reason" :group="group" :row="row" :color="color" />

    </fieldset>
    <p v-if="error" class="mt-4 text-xs text-coral-text" role="alert">{{ error }}</p>
    <template #footer>
      <p class="w-full text-[11px] text-muted">{{ mode === 'edit' ? 'The current version stays available. Run validation after saving to refresh the results.' : 'Run validation to refresh error counts and quality scores after ignoring findings.' }}</p>
      <div class="flex w-full flex-wrap justify-end gap-2">
        <button type="button" class="ui-button" :disabled="saving" @click="isOpen = false">Cancel</button>
        <template v-if="mode === 'edit'">
          <button type="button" class="ui-button ui-button-primary" :disabled="cannotSave" @click="save('one')">{{ saving ? 'Saving…' : action === 'remove' ? 'Delete row & save version' : 'Save cell to new version' }}</button>
          <button v-if="count > 1" type="button" class="ui-button ui-button-primary" :disabled="cannotSave || bulkUnavailable" @click="save('all')">{{ bulkUnavailable ? 'Bulk replacement unavailable' : action === 'remove' ? `Delete all ${formatNumber(count)} matching rows` : `Save all ${formatNumber(count)} matching cells` }}</button>
        </template>
        <button v-else type="button" class="ui-button ui-button-primary" :disabled="saving" @click="save(scope)">{{ saving ? 'Saving…' : 'Confirm ignore' }}</button>
      </div>
    </template>
  </ModalShell>
</template>
