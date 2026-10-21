<script setup lang="ts">
import { SVGIcons } from '@/assets'
import { computed, ref, shallowRef, useId, watch } from 'vue'
import type { CellReviewGroup as ReviewGroup, CellReviewRequest, Dataset } from '@/types'
import { formatNumber } from '@/utils'
import { displayCellValue, summarizeCellReview } from '@/services'
import { CellReviewDialog, CellReviewGroup } from '@/components'

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
const selected = shallowRef<{ group: ReviewGroup; row: number; mode: 'edit' | 'ignore' } | null>(null)
const dialogOpen = ref(false)

watch([search, kind, column], () => { page.value = 0; cellPages.value = {} })
watch(() => props.dataset, () => {
  search.value = ''; kind.value = 'all'; column.value = 'all'; page.value = 0
  cellPages.value = {}; dialogOpen.value = false; selected.value = null
})
function openDialog(group: ReviewGroup, row: number, mode: 'edit' | 'ignore') {
  selected.value = { group, row, mode }
  dialogOpen.value = true
}
</script>

<template>
  <section id="cell-review" class="ui-panel" :aria-labelledby="headingId">
    <header class="ui-panel-header">
      <div><h2 :id="headingId">Cell Review &amp; Fixes</h2><p>Review flagged values and save a correction for one cell or all matching cells.</p></div>
      <span class="ui-badge bg-cobalt-soft text-cobalt">{{ dataset.name }} · {{ dataset.version }}</span>
    </header>
    <p v-if="dataset.cellReview == null" class="px-5.5 pb-5 text-xs text-muted" role="status">Cell review is not available for this version.</p>
    <template v-else>
      <div class="flex flex-wrap gap-2 px-5.5 pb-4.25">
        <span class="ui-badge bg-coral-soft text-coral-text">{{ formatNumber(totals.violations) }} rule {{ totals.violations === 1 ? 'violation' : 'violations' }}</span>
        <span class="ui-badge bg-yellow-100 text-yellow-800">{{ formatNumber(totals.warnings) }} anomaly {{ totals.warnings === 1 ? 'warning' : 'warnings' }}</span>
        <span class="ui-badge bg-ivory text-muted">{{ formatNumber(totals.cells) }} cells across {{ formatNumber(totals.rows) }} rows</span>
      </div>
      <p v-if="dataset.rulesChangedSinceRun" class="px-5.5 pb-4 text-xs text-muted">Findings reflect the last validation run. Re-run validation to apply the saved rules.</p>
      <p v-if="dataset.reviewChangedSinceRun" class="px-5.5 pb-4 text-xs text-muted" role="status">Saved changes are pending validation. This table shows remaining findings from the last run; click Run Dataset Validation to refresh results.</p>
      <div class="grid gap-3 border-y border-line bg-ivory px-5.5 py-4 sm:grid-cols-[1.4fr_1fr_1fr]">
        <label class="review-label">Find a value, column, or rule<input v-model="search" type="search" class="ui-control" placeholder="Search flagged values…" /></label>
        <label class="review-label">Finding type<select v-model="kind" class="ui-control"><option value="all">All findings</option><option value="violation">Rule violations</option><option value="warning">Anomaly warnings</option></select></label>
        <label class="review-label">Column<select v-model="column" class="ui-control"><option value="all">All columns</option><option v-for="name in columns" :key="name" :value="name">{{ name }}</option></select></label>
      </div>
      <div class="flex flex-wrap justify-between gap-2 px-5.5 py-3 text-[11px] text-muted">
        <span><strong class="font-medium text-ink">Grouped by column, finding, and exact current value</strong> · Most repeated first</span>
        <span role="status" aria-live="polite">{{ formatNumber(filtered.length) }} groups · {{ formatNumber(filteredTotals.cells) }} flagged cells</span>
      </div>
      <div class="px-5.5">
        <CellReviewGroup v-for="(group, index) in visible" :key="`${page}:${group.id}`"
          v-model:page="cellPages[group.id]" :group="group" :open="index === 0"
          @review="(row, mode) => openDialog(group, row, mode)" />
        <p v-if="!visible.length" class="py-8 text-center text-sm text-muted">{{ groups.length ? 'No findings match these filters.' : dataset.reviewChangedSinceRun ? 'No remaining findings from the last run. Run validation to check your changes.' : 'No flagged cells in this version.' }}</p>
      </div>
      <div class="ui-table-footer">
        <span>{{ filtered.length ? `Groups ${formatNumber(page * pageSize + 1)}–${formatNumber(Math.min((page + 1) * pageSize, filtered.length))} of ${formatNumber(filtered.length)}` : '0 groups' }}</span>
        <div class="flex gap-2"><button type="button" class="ui-button" :disabled="page === 0" @click="page--"><SVGIcons name="arrowBack" class="size-4" /> Previous</button><button type="button" class="ui-button" :disabled="(page + 1) * pageSize >= filtered.length" @click="page++">Next 10 groups <SVGIcons name="arrowForward" class="size-4" /></button></div>
      </div>
    </template>
    <CellReviewDialog v-if="selected" v-model="dialogOpen" :dataset="dataset" :group="selected.group" :initial-row="selected.row" :mode="selected.mode" :saving="saving" :error="error" @save="emit('save', $event)" />
  </section>
</template>

<style scoped>
@reference '../../assets/main.css';
.review-label { @apply text-muted; display: flex; flex-direction: column; gap: 6px; font-size: 11px; }
</style>
