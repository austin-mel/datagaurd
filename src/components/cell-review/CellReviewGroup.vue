<script setup lang="ts">
import { SVGIcons } from '@/assets'
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
  <details class="group/finding mb-3 overflow-hidden rounded-lg border border-line" :open="open">
    <summary class="grid cursor-pointer list-none grid-cols-[minmax(170px,1.4fr)_minmax(100px,1fr)_80px_14px] items-center gap-4 px-4.25 py-3.75 after:text-center after:text-[22px] after:content-['›'] group-open/finding:bg-ivory group-open/finding:after:rotate-90 [&::-webkit-details-marker]:hidden max-[640px]:grid-cols-[minmax(0,1fr)_70px_14px] max-[640px]:gap-2.5 max-[640px]:after:col-start-3 max-[640px]:after:row-start-1">
      <span class="min-w-0"><code class="block text-xs font-medium wrap-anywhere">{{ group.column }}</code><span class="mt-1.5 flex flex-wrap items-center gap-2"><span class="ui-badge" :class="color">{{ group.kind === 'warning' ? 'Anomaly warning' : 'Rule violation' }}</span><span class="text-[10px] text-muted">{{ group.rule }}</span></span></span>
      <span class="min-w-0 max-[640px]:col-start-1 max-[640px]:row-start-2"><span class="mb-1.25 block text-[9px] tracking-[0.04em] text-muted">FLAGGED VALUE</span><code class="inline-block rounded-[5px] px-2 py-1.25 text-xs whitespace-pre-wrap wrap-anywhere" :class="color">{{ displayCellValue(group.currentValue) }}</code></span>
      <span class="text-right max-[640px]:col-start-2 max-[640px]:row-start-1"><strong class="block text-sm font-semibold tabular-nums">{{ formatNumber(group.cells.length) }} {{ group.cells.length === 1 ? 'cell' : 'cells' }}</strong><small class="text-[10px] text-muted">{{ formatNumber(group.cells.length) }} {{ group.cells.length === 1 ? 'row' : 'rows' }}</small></span>
    </summary>
    <p class="border-t border-line px-4 py-3 text-xs leading-6 text-muted">{{ group.reason }}</p>
    <ul class="px-4">
      <li v-for="cell in group.cells.slice(start, start + pageSize)" :key="cell.rowNumber" class="grid grid-cols-[minmax(100px,1fr)_minmax(100px,1fr)_auto] items-center gap-3 border-t border-line py-3 max-[640px]:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div><strong class="block text-xs font-medium">Row {{ formatNumber(cell.rowNumber) }}</strong><small class="mt-1 block text-[10px] text-muted wrap-anywhere">{{ cell.identifier ?? 'Unassigned ID' }}</small></div>
        <div class="min-w-0"><span class="mb-1.25 block text-[9px] tracking-[0.04em] text-muted">CURRENT VALUE</span><code class="inline-block rounded-[5px] px-2 py-1.25 text-xs whitespace-pre-wrap wrap-anywhere bg-cobalt-soft text-cobalt">{{ displayCellValue(group.currentValue) }}</code></div>
        <div class="flex flex-wrap gap-2 max-[640px]:col-span-full">
          <button type="button" class="ui-button ui-button-primary text-[10px]" aria-haspopup="dialog" :aria-label="`Edit row ${cell.rowNumber}, ${group.column}`" @click="emit('review', cell.rowNumber, 'edit')"><SVGIcons name="edit" class="size-4" /> Edit value</button>
          <button type="button" class="ui-button border-coral-text bg-transparent text-[10px] text-coral-text hover:bg-coral-soft" aria-haspopup="dialog" :aria-label="`Ignore ${group.kind === 'warning' ? 'warning' : 'error'} for row ${cell.rowNumber}, ${group.column}`" @click="emit('review', cell.rowNumber, 'ignore')"><SVGIcons name="ignore" class="size-4" /> Ignore {{ group.kind === 'warning' ? 'warning' : 'error' }}</button>
        </div>
      </li>
    </ul>
    <div v-if="group.cells.length > pageSize" class="ui-table-footer">
      <span>Cells {{ formatNumber(start + 1) }}–{{ formatNumber(Math.min(start + pageSize, group.cells.length)) }} of {{ formatNumber(group.cells.length) }}</span>
      <div class="flex gap-2"><button type="button" class="ui-button" :disabled="start === 0" @click="page--"><SVGIcons name="arrowBack" class="size-4" /> Previous cells</button><button type="button" class="ui-button" :disabled="start + pageSize >= group.cells.length" @click="page++">Next cells <SVGIcons name="arrowForward" class="size-4" /></button></div>
    </div>
  </details>
</template>
