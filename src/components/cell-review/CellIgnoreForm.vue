<script setup lang="ts">
import { computed, useId } from 'vue'
import type { CellReviewGroup } from '@/types'
import { displayCellValue } from '@/services'
import { formatNumber } from '@/utils'
const props = defineProps<{ group: CellReviewGroup; row: number; color: string }>()
const scope = defineModel<'one' | 'all'>('scope', { required: true })
const reason = defineModel<string>('reason', { required: true })
const radioName = useId()
const count = computed(() => props.group.cells.length)
</script>

<template>
  <p class="mb-4 text-xs text-muted">Row {{ formatNumber(row) }} · Value stays unchanged: <code class="ml-1 rounded p-1.5" :class="color">{{ displayCellValue(group.currentValue) }}</code></p>
  <fieldset class="mb-5 space-y-3 text-xs">
    <legend class="mb-3 font-medium">Which findings should be ignored?</legend>
    <label class="flex items-center gap-2"><input v-model="scope" type="radio" :name="radioName" value="one" class="accent-cobalt" />Only this finding · row {{ formatNumber(row) }}</label>
    <label class="flex items-center gap-2"><input v-model="scope" type="radio" :name="radioName" value="all" :disabled="count === 1" class="accent-cobalt" />All {{ formatNumber(count) }} matching findings</label>
  </fieldset>
  <label class="block text-xs text-muted">Reason for ignoring<textarea v-model="reason" class="ui-control mt-1.5 min-h-24" placeholder="e.g. Verified against the original source record" /></label>
  <p class="mt-3 text-xs text-muted" role="status">{{ formatNumber(scope === 'one' ? 1 : count) }} {{ scope === 'one' || count === 1 ? 'finding would' : 'findings would' }} be ignored. Cell values would stay unchanged.</p>
  <p class="mt-4 rounded-md bg-ivory p-3 text-[11px] leading-6 text-muted">Ignoring removes this finding from the review table. The cell stays unchanged, and this finding will no longer be flagged or counted as an error on future validation runs. Other findings on this cell still apply.</p>

</template>
