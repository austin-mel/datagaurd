<script setup lang="ts">
import { computed, ref, shallowRef, useId, watch } from 'vue'
import type { CellReviewGroup, CellReviewRequest, Dataset } from '@/types'
import { formatNumber } from '@/utils'
import { displayCellValue, summarizeCellReview } from '@/services/cellReview'
import CellReviewDialog from './CellReviewDialog.vue'

const props = defineProps<{ dataset: Dataset; saving?: boolean; error?: string }>()
const emit = defineEmits<{ save: [request: CellReviewRequest] }>()
const headingId = useId()
const search = ref(''), kind = ref('all'), column = ref('all'), page = ref(0)
const cellPages = ref<Record<string, number>>({})
const pageSize = 10
const groups = computed(() => props.dataset.cellReview ?? [])
const totals = computed(() => summarizeCellReview(groups.value))
const columns = computed(() => [...new Set(groups.value.map(group => group.column))])
const filtered = computed(() => {
  const query = search.value.trim().toLowerCase()
  return groups.value.filter(group => (kind.value === 'all' || group.kind === kind.value)
    && (column.value === 'all' || group.column === column.value)
    && [group.column, group.rule, group.ruleId, displayCellValue(group.currentValue), group.reason].join(' ').toLowerCase().includes(query))
    .sort((a, b) => b.cells.length - a.cells.length || a.column.localeCompare(b.column) || a.id.localeCompare(b.id))
})
const filteredTotals = computed(() => summarizeCellReview(filtered.value))
const visible = computed(() => filtered.value.slice(page.value * pageSize, (page.value + 1) * pageSize))
const selected = shallowRef<{ group: CellReviewGroup; row: number; mode: 'edit' | 'ignore' } | null>(null)
const dialogOpen = ref(false)

watch([search, kind, column], () => { page.value = 0; cellPages.value = {} })
watch(() => props.dataset, () => {
  search.value = ''; kind.value = 'all'; column.value = 'all'; page.value = 0
  cellPages.value = {}; dialogOpen.value = false; selected.value = null
})
function cellStart(group: CellReviewGroup) { return (cellPages.value[group.id] ?? 0) * pageSize }
function openDialog(group: CellReviewGroup, row: number, mode: 'edit' | 'ignore') {
  selected.value = { group, row, mode }
  dialogOpen.value = true
}
function findingClass(group: CellReviewGroup) {
  return group.kind === 'warning' ? 'bg-yellow-100 text-yellow-800' : 'bg-coral-soft text-coral-text'
}
</script>

<template>
  <section id="cell-review" class="ui-panel" :aria-labelledby="headingId">
    <header class="ui-panel-header">
      <div><h2 :id="headingId">Cell Review &amp; Fixes</h2><p>Review flagged values and save a correction for one cell or all matching cells.</p></div>
      <span class="ui-badge bg-cobalt-soft text-cobalt">{{ dataset.name }} · {{ dataset.version }}</span>
    </header>
    <p v-if="dataset.cellReview == null" class="px-[22px] pb-5 text-xs text-muted" role="status">Cell review is not available for this version.</p>
    <template v-else>
      <div class="flex flex-wrap gap-2 px-[22px] pb-[17px]">
        <span class="ui-badge bg-coral-soft text-coral-text">{{ formatNumber(totals.violations) }} rule {{ totals.violations === 1 ? 'violation' : 'violations' }}</span>
        <span class="ui-badge bg-yellow-100 text-yellow-800">{{ formatNumber(totals.warnings) }} anomaly {{ totals.warnings === 1 ? 'warning' : 'warnings' }}</span>
        <span class="ui-badge bg-ivory text-muted">{{ formatNumber(totals.cells) }} cells across {{ formatNumber(totals.rows) }} rows</span>
      </div>
      <p v-if="dataset.rulesChangedSinceRun" class="px-[22px] pb-4 text-xs text-muted">Findings reflect the last validation run. Re-run validation to apply the saved rules.</p>
      <p v-if="dataset.reviewChangedSinceRun" class="px-[22px] pb-4 text-xs text-muted" role="status">Saved changes are pending validation. This table shows remaining findings from the last run; click Run Dataset Validation to refresh results.</p>
      <div class="grid gap-3 border-y border-line bg-ivory px-[22px] py-4 sm:grid-cols-[1.4fr_1fr_1fr]">
        <label class="review-label">Find a value, column, or rule<input v-model="search" type="search" class="ui-control" placeholder="Search flagged values…" /></label>
        <label class="review-label">Finding type<select v-model="kind" class="ui-control"><option value="all">All findings</option><option value="violation">Rule violations</option><option value="warning">Anomaly warnings</option></select></label>
        <label class="review-label">Column<select v-model="column" class="ui-control"><option value="all">All columns</option><option v-for="name in columns" :key="name" :value="name">{{ name }}</option></select></label>
      </div>
      <div class="flex flex-wrap justify-between gap-2 px-[22px] py-3 text-[11px] text-muted">
        <span><strong class="font-medium text-ink">Grouped by column, finding, and exact current value</strong> · Most repeated first</span>
        <span role="status" aria-live="polite">{{ formatNumber(filtered.length) }} groups · {{ formatNumber(filteredTotals.cells) }} flagged cells</span>
      </div>
      <div class="px-[22px]">
        <details v-for="(group, index) in visible" :key="`${page}:${group.id}`" class="finding-group mb-3 overflow-hidden rounded-lg border border-line" :open="index === 0">
          <summary class="group-summary">
            <span class="min-w-0"><code class="block text-xs font-medium wrap-anywhere">{{ group.column }}</code><span class="mt-1.5 flex flex-wrap items-center gap-2"><span class="ui-badge" :class="findingClass(group)">{{ group.kind === 'warning' ? 'Anomaly warning' : 'Rule violation' }}</span><span class="text-[10px] text-muted">{{ group.rule }}</span></span></span>
            <span class="min-w-0"><span class="value-caption">FLAGGED VALUE</span><code class="flagged-value" :class="findingClass(group)">{{ displayCellValue(group.currentValue) }}</code></span>
            <span class="text-right"><strong class="block text-sm font-semibold tabular-nums">{{ formatNumber(group.cells.length) }} {{ group.cells.length === 1 ? 'cell' : 'cells' }}</strong><small class="text-[10px] text-muted">{{ formatNumber(group.cells.length) }} {{ group.cells.length === 1 ? 'row' : 'rows' }}</small></span>
          </summary>
          <p class="border-t border-line px-4 py-3 text-xs leading-6 text-muted">{{ group.reason }}</p>
          <ul class="px-4">
            <li v-for="cell in group.cells.slice(cellStart(group), cellStart(group) + pageSize)" :key="cell.rowNumber" class="cell-item">
              <div><strong class="block text-xs font-medium">Row {{ formatNumber(cell.rowNumber) }}</strong><small class="mt-1 block text-[10px] text-muted wrap-anywhere">{{ cell.identifier ?? 'Unassigned ID' }}</small></div>
              <div class="min-w-0"><span class="value-caption">CURRENT VALUE</span><code class="flagged-value" :class="findingClass(group)">{{ displayCellValue(group.currentValue) }}</code></div>
              <div class="flex flex-wrap gap-2">
                <button type="button" class="ui-button ui-button-primary text-[10px]" aria-haspopup="dialog" :aria-label="`Edit row ${cell.rowNumber}, ${group.column}`" @click="openDialog(group, cell.rowNumber, 'edit')">Edit value</button>
                <button type="button" class="ui-button border-coral-text bg-transparent text-[10px] text-coral-text hover:bg-coral-soft" aria-haspopup="dialog" :aria-label="`Ignore ${group.kind === 'warning' ? 'warning' : 'error'} for row ${cell.rowNumber}, ${group.column}`" @click="openDialog(group, cell.rowNumber, 'ignore')">Ignore {{ group.kind === 'warning' ? 'warning' : 'error' }}</button>
              </div>
            </li>
          </ul>
          <div v-if="group.cells.length > pageSize" class="ui-table-footer">
            <span>Cells {{ formatNumber(cellStart(group) + 1) }}–{{ formatNumber(Math.min(cellStart(group) + pageSize, group.cells.length)) }} of {{ formatNumber(group.cells.length) }}</span>
            <div class="flex gap-2"><button type="button" class="ui-button" :disabled="cellStart(group) === 0" @click="cellPages[group.id] = (cellPages[group.id] ?? 0) - 1">Previous cells</button><button type="button" class="ui-button" :disabled="cellStart(group) + pageSize >= group.cells.length" @click="cellPages[group.id] = (cellPages[group.id] ?? 0) + 1">Next cells</button></div>
          </div>
        </details>
        <p v-if="!visible.length" class="py-8 text-center text-sm text-muted">{{ groups.length ? 'No findings match these filters.' : dataset.reviewChangedSinceRun ? 'No remaining findings from the last run. Run validation to check your changes.' : 'No flagged cells in this version.' }}</p>
      </div>
      <div class="ui-table-footer">
        <span>{{ filtered.length ? `Groups ${formatNumber(page * pageSize + 1)}–${formatNumber(Math.min((page + 1) * pageSize, filtered.length))} of ${formatNumber(filtered.length)}` : '0 groups' }}</span>
        <div class="flex gap-2"><button type="button" class="ui-button" :disabled="page === 0" @click="page--">Previous</button><button type="button" class="ui-button" :disabled="(page + 1) * pageSize >= filtered.length" @click="page++">Next 10 groups</button></div>
      </div>
    </template>
    <CellReviewDialog v-if="selected" v-model="dialogOpen" :dataset="dataset" :group="selected.group" :initial-row="selected.row" :mode="selected.mode" :saving="saving" :error="error" @save="emit('save', $event)" />
  </section>
</template>

<style scoped>
@reference '../../assets/main.css';
.review-label { @apply text-muted; display: flex; flex-direction: column; gap: 6px; font-size: 11px; }
.group-summary { display: grid; grid-template-columns: minmax(170px, 1.4fr) minmax(100px, 1fr) 80px 14px; gap: 16px; align-items: center; padding: 15px 17px; cursor: pointer; list-style: none; }
.group-summary::-webkit-details-marker { display: none; }
.group-summary::after { content: '›'; font-size: 22px; text-align: center; }
.finding-group[open] > summary { @apply bg-ivory; }
.finding-group[open] > summary::after { transform: rotate(90deg); }
.value-caption { @apply text-muted; display: block; font-size: 9px; letter-spacing: .04em; margin-bottom: 5px; }
.flagged-value { display: inline-block; padding: 5px 8px; border-radius: 5px; font-size: 12px; overflow-wrap: anywhere; white-space: pre-wrap; }
.cell-item { @apply border-t border-line; display: grid; grid-template-columns: minmax(100px, 1fr) minmax(100px, 1fr) auto; gap: 12px; align-items: center; padding: 12px 0; }
@media (max-width: 640px) {
  .group-summary { grid-template-columns: minmax(0, 1fr) 70px 14px; gap: 10px; }
  .group-summary > :nth-child(2) { grid-column: 1; grid-row: 2; }
  .group-summary > :nth-child(3) { grid-column: 2; grid-row: 1; }
  .group-summary::after { grid-column: 3; grid-row: 1; }
  .cell-item { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
  .cell-item > :last-child { grid-column: 1 / -1; }
}
</style>
