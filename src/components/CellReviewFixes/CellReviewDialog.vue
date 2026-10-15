<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import type { CellReviewGroup, Dataset } from '@/types'
import { displayCellValue } from '@/services/cellReview'
import { formatNumber } from '@/utils'
import { ModalShell } from '../ModalShell'

const props = defineProps<{ dataset: Dataset; group: CellReviewGroup; initialRow: number; mode: 'edit' | 'ignore' }>()
const isOpen = defineModel<boolean>({ required: true })
const radioName = useId()
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
const requiredColumn = computed(() => props.dataset.ruleset.rules.some(rule => rule.enabled && rule.type === 'required' && rule.column === props.group.column))
const bulkUnavailable = computed(() => uniqueColumn.value && count.value > 1 && action.value !== 'remove')
const after = computed(() => action.value === 'remove' ? 'ROW REMOVED' : action.value === 'null' ? 'NULL (missing)' : replacement.value.trim() ? replacement.value : 'Enter a replacement')
const affectedRows = computed(() => props.group.cells.slice(0, 6).map(cell => formatNumber(cell.rowNumber)).join(', ')
  + (count.value > 6 ? `, +${formatNumber(count.value - 6)} more` : ''))
const caution = computed(() => {
  const notes: string[] = []
  if (action.value === 'remove') notes.push('Entire records would be removed, including cells without findings.')
  if (action.value === 'null') notes.push(requiredColumn.value ? 'This column is required. Replacing it with NULL would still fail the required-value rule.' : 'NULL creates a missing value. Other checks may still fail.')
  if (bulkUnavailable.value) notes.push('This column must be unique. Verify and correct each value separately; a shared replacement could create duplicates.')
  if (action.value === 'custom' && replacement.value.trim() && replacement.value === String(props.group.currentValue ?? '')) notes.push('The replacement equals the current value.')
  if (action.value === 'custom' && replacement.value === 'null') notes.push('Custom input “null” is literal text. Choose Replace with NULL to create a missing value.')
  return notes.join(' ')
})
</script>

<template>
  <ModalShell v-model="isOpen" :title="title" :eyebrow="mode === 'edit' ? 'REVIEW A CORRECTION' : 'REVIEW A FINDING'" description="Preview only. No changes will be saved to the dataset.">
    <div class="mb-4 flex flex-wrap items-center gap-2 text-xs">
      <strong class="font-semibold">{{ dataset.name }} · {{ dataset.version }}</strong>
      <code class="wrap-anywhere">{{ group.column }}</code>
      <span class="ui-badge" :class="color">{{ warning ? 'Anomaly warning' : 'Rule violation' }}</span>
    </div>
    <p class="mb-4 rounded-md px-3 py-2.5 text-xs leading-6" :class="color">{{ group.reason }}</p>
    <template v-if="mode === 'edit'">
      <label class="mb-5 block max-w-lg text-xs text-muted">Selected cell
        <select v-model="row" class="ui-control mt-1.5">
          <option v-for="cell in group.cells" :key="cell.rowNumber" :value="cell.rowNumber">Row {{ formatNumber(cell.rowNumber) }} · {{ cell.identifier ?? 'Unassigned ID' }} · {{ group.column }}</option>
        </select>
      </label>
      <fieldset class="mb-5">
        <legend class="mb-2 text-xs font-medium">How should this cell be handled?</legend>
        <div class="grid gap-2 sm:grid-cols-3">
          <label class="flex cursor-pointer items-start gap-2 rounded-lg border border-line p-3 has-checked:border-cobalt has-checked:bg-cobalt-soft">
            <input v-model="action" type="radio" :name="radioName" value="custom" class="mt-0.5 accent-cobalt" />
            <span><strong class="block text-xs font-medium">Replace with custom input</strong><small class="mt-1 block text-[10px] leading-5 text-muted">Enter the verified value yourself.</small></span>
          </label>
          <label class="flex cursor-pointer items-start gap-2 rounded-lg border border-line p-3 has-checked:border-cobalt has-checked:bg-cobalt-soft">
            <input v-model="action" type="radio" :name="radioName" value="null" class="mt-0.5 accent-cobalt" />
            <span><strong class="block text-xs font-medium">Replace with NULL</strong><small class="mt-1 block text-[10px] leading-5 text-muted">Make this a missing value, not the text “null”.</small></span>
          </label>
          <label class="flex cursor-pointer items-start gap-2 rounded-lg border border-line p-3 has-checked:border-cobalt has-checked:bg-cobalt-soft">
            <input v-model="action" type="radio" :name="radioName" value="remove" class="mt-0.5 accent-cobalt" />
            <span><strong class="block text-xs font-medium">Remove entire row</strong><small class="mt-1 block text-[10px] leading-5 text-muted">Remove all {{ formatNumber(dataset.columns.length) }} cells in the record.</small></span>
          </label>
        </div>
      </fieldset>
      <label v-if="action === 'custom'" class="mb-5 block text-xs text-muted">Replacement value
        <input v-model="replacement" type="text" class="ui-control mt-1.5" placeholder="Enter the verified replacement" autocomplete="off" />
      </label>
      <div class="mb-4 grid grid-cols-[minmax(0,1fr)_16px_minmax(0,1fr)] items-center gap-3" aria-label="Before and after preview">
        <div><span class="mb-1 block text-[9px] text-muted">FLAGGED CURRENT VALUE</span><code class="block rounded-md p-3 text-sm whitespace-pre-wrap wrap-anywhere" :class="color">{{ displayCellValue(group.currentValue) }}</code></div>
        <span aria-hidden="true" class="text-muted">→</span>
        <div><span class="mb-1 block text-[9px] text-muted">{{ action === 'remove' ? 'ENTIRE RECORD REMOVED' : 'REPLACEMENT VALUE' }}</span><code class="block rounded-md p-3 text-sm whitespace-pre-wrap wrap-anywhere" :class="action === 'remove' ? 'bg-coral-soft text-coral-text' : 'bg-emerald-soft text-green-text'">{{ after }}</code></div>
      </div>
      <div class="grid gap-3 sm:grid-cols-2" aria-live="polite">
        <div class="rounded-lg bg-ivory p-4"><p class="text-[10px] text-muted">THIS CELL ONLY</p><strong class="mt-1 block text-sm font-semibold">{{ action === 'remove' ? `1 entire row · ${formatNumber(dataset.columns.length)} cells` : '1 cell · 1 row' }}</strong><small class="mt-1 block text-[10px] text-muted">Row {{ formatNumber(row) }} · {{ group.column }}</small></div>
        <div class="rounded-lg bg-ivory p-4"><p class="text-[10px] text-muted">ALL CELLS WITH THE SAME FLAGGED VALUE</p><strong class="mt-1 block text-sm font-semibold">{{ action === 'remove' ? `${formatNumber(count)} entire rows · ${formatNumber(count * dataset.columns.length)} cells` : `${formatNumber(count)} cells · ${formatNumber(count)} rows` }}</strong><small class="mt-1 block text-[10px] text-muted">Rows {{ affectedRows }} · includes the selected cell.</small></div>
      </div>
      <p class="mt-3 text-[11px] leading-6 text-muted">All matches means this dataset, version {{ dataset.version }}, column <code>{{ group.column }}</code>, finding “{{ group.rule }}”, and the exact current value. It includes matches outside the current page and filters.</p>
      <p v-if="caution" class="mt-3 rounded-md bg-coral-soft p-3 text-[11px] leading-6 text-coral-text" role="status">{{ caution }}</p>
    </template>
    <template v-else>
      <p class="mb-4 text-xs text-muted">Row {{ formatNumber(row) }} · Value stays unchanged: <code class="ml-1 rounded p-1.5" :class="color">{{ displayCellValue(group.currentValue) }}</code></p>
      <fieldset class="mb-5 space-y-3 text-xs">
        <legend class="mb-3 font-medium">Which findings should be ignored?</legend>
        <label class="flex items-center gap-2"><input v-model="scope" type="radio" :name="radioName" value="one" class="accent-cobalt" />Only this finding · row {{ formatNumber(row) }}</label>
        <label class="flex items-center gap-2"><input v-model="scope" type="radio" :name="radioName" value="all" :disabled="count === 1" class="accent-cobalt" />All {{ formatNumber(count) }} matching findings</label>
      </fieldset>
      <label class="block text-xs text-muted">Reason for ignoring<textarea v-model="reason" class="ui-control mt-1.5 min-h-24" placeholder="e.g. Verified against the original source record" /></label>
      <p class="mt-3 text-xs text-muted" role="status">{{ formatNumber(scope === 'one' ? 1 : count) }} {{ scope === 'one' || count === 1 ? 'finding would' : 'findings would' }} be ignored. Cell values would stay unchanged.</p>
      <p class="mt-4 rounded-md bg-ivory p-3 text-[11px] leading-6 text-muted">Ignoring a finding would remove it from the review queue while retaining its audit record. It would not correct the value, make a failed rule pass, or improve the quality score.</p>
    </template>
    <template #footer>
      <p class="w-full text-[11px] text-muted">Preview only. {{ mode === 'edit' ? 'Saving corrections and creating a new dataset version are not available yet.' : 'Saving ignore decisions is not available yet.' }}</p>
      <div class="flex w-full flex-wrap justify-end gap-2">
        <button type="button" class="ui-button" @click="isOpen = false">Cancel</button>
        <template v-if="mode === 'edit'">
          <button type="button" class="ui-button" disabled>{{ action === 'remove' ? 'Confirm removal · 1 row' : 'Confirm fix · this cell' }}</button>
          <button v-if="count > 1" type="button" class="ui-button ui-button-primary" disabled>{{ bulkUnavailable ? 'Bulk replacement unavailable' : action === 'remove' ? `Remove all ${formatNumber(count)} matching rows` : `Apply fix to all ${formatNumber(count)} matching cells` }}</button>
        </template>
        <button v-else type="button" class="ui-button ui-button-primary" disabled>Confirm ignore</button>
      </div>
    </template>
  </ModalShell>
</template>
