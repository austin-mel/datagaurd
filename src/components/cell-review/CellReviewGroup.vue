<script setup lang="ts">
import { computed } from 'vue'
import type { CellReviewGroup } from '@/types'
import { formatNumber } from '@/utils'
import { displayCellValue } from '@/services'
const props = defineProps<{ group: CellReviewGroup; open: boolean }>()
const emit = defineEmits<{ review: [row: number, mode: 'edit' | 'ignore'] }>()
const page = defineModel<number>('page', { default: 0 })
const pageSize = 10
const start = computed(() => page.value * pageSize)
const color = computed(() => props.group.kind === 'warning' ? 'bg-yellow-100 text-yellow-800' : 'bg-coral-soft text-coral-text')
</script>

<template>
  <details class="finding-group mb-3 overflow-hidden rounded-lg border border-line" :open="open">
    <summary class="group-summary">
      <span class="min-w-0"><code class="block text-xs font-medium wrap-anywhere">{{ group.column }}</code><span class="mt-1.5 flex flex-wrap items-center gap-2"><span class="ui-badge" :class="color">{{ group.kind === 'warning' ? 'Anomaly warning' : 'Rule violation' }}</span><span class="text-[10px] text-muted">{{ group.rule }}</span></span></span>
      <span class="min-w-0"><span class="value-caption">FLAGGED VALUE</span><code class="flagged-value" :class="color">{{ displayCellValue(group.currentValue) }}</code></span>
      <span class="text-right"><strong class="block text-sm font-semibold tabular-nums">{{ formatNumber(group.cells.length) }} {{ group.cells.length === 1 ? 'cell' : 'cells' }}</strong><small class="text-[10px] text-muted">{{ formatNumber(group.cells.length) }} {{ group.cells.length === 1 ? 'row' : 'rows' }}</small></span>
    </summary>
    <p class="border-t border-line px-4 py-3 text-xs leading-6 text-muted">{{ group.reason }}</p>
    <ul class="px-4">
      <li v-for="cell in group.cells.slice(start, start + pageSize)" :key="cell.rowNumber" class="cell-item">
        <div><strong class="block text-xs font-medium">Row {{ formatNumber(cell.rowNumber) }}</strong><small class="mt-1 block text-[10px] text-muted wrap-anywhere">{{ cell.identifier ?? 'Unassigned ID' }}</small></div>
        <div class="min-w-0"><span class="value-caption">CURRENT VALUE</span><code class="flagged-value bg-cobalt-soft text-cobalt">{{ displayCellValue(group.currentValue) }}</code></div>
        <div class="flex flex-wrap gap-2">
          <button type="button" class="ui-button ui-button-primary text-[10px]" aria-haspopup="dialog" :aria-label="`Edit row ${cell.rowNumber}, ${group.column}`" @click="emit('review', cell.rowNumber, 'edit')">Edit value</button>
          <button type="button" class="ui-button border-coral-text bg-transparent text-[10px] text-coral-text hover:bg-coral-soft" aria-haspopup="dialog" :aria-label="`Ignore ${group.kind === 'warning' ? 'warning' : 'error'} for row ${cell.rowNumber}, ${group.column}`" @click="emit('review', cell.rowNumber, 'ignore')">Ignore {{ group.kind === 'warning' ? 'warning' : 'error' }}</button>
        </div>
      </li>
    </ul>
    <div v-if="group.cells.length > pageSize" class="ui-table-footer">
      <span>Cells {{ formatNumber(start + 1) }}–{{ formatNumber(Math.min(start + pageSize, group.cells.length)) }} of {{ formatNumber(group.cells.length) }}</span>
      <div class="flex gap-2"><button type="button" class="ui-button" :disabled="start === 0" @click="page--">Previous cells</button><button type="button" class="ui-button" :disabled="start + pageSize >= group.cells.length" @click="page++">Next cells</button></div>
    </div>
  </details>
</template>

<style scoped>
@reference '../../assets/main.css';
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
