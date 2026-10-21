<script setup lang="ts">
import { SVGIcons } from '@/assets'
import { useRouter } from 'vue-router'
import type { Dataset } from '@/types'
import { formatNumber, formatScore, formatValidatedAt } from '@/utils'
defineProps<{ dataset: Dataset }>()
const emit = defineEmits<{ editQualityRules: [datasetId: string] }>()
const router = useRouter()
function openOverview(datasetId: string) {
  void router.push({ name: 'overview', query: { dataset: datasetId } })
}
</script>

<template>
  <tr class="border-b border-line last:border-0 hover:bg-table-selected">
    <th scope="row">
      <div class="flex items-center gap-2.75">
        <span
          class="grid h-9.5 w-8.5 shrink-0 place-items-center rounded-[7px] border border-line bg-ivory text-muted"
        >
          <SVGIcons :name="dataset.sourceIcon" class="size-4.5" />
        </span>
        <div>
          <strong class="block font-[550]">{{ dataset.name }}</strong>
          <span class="mt-0.75 block text-[10px] font-normal text-muted">
            {{ dataset.source }} · {{ formatNumber(dataset.rowCount) }} rows
          </span>
        </div>
      </div>
    </th>
    <td>
      <span
        class="inline-flex rounded-[5px] bg-cobalt-soft px-1.75 py-1 text-[10px] font-semibold text-cobalt"
      >
        {{ dataset.version }}
      </span>
    </td>
    <td class="tabular-nums">{{ formatScore(dataset.quality) }}</td>
    <td class="whitespace-nowrap text-muted">
      <time v-if="dataset.lastValidatedAt" :datetime="dataset.lastValidatedAt">{{ formatValidatedAt(dataset.lastValidatedAt, false) }}</time>
      <span v-else>Not available · {{ dataset.processingStatus === 'not_started' ? 'Not started' : dataset.processingStatus }}</span>
    </td>
    <td>
      <div class="flex items-center gap-6 whitespace-nowrap">
        <button
          type="button"
          class="ui-button px-2.25 py-1.75 text-[10px] text-cobalt"
          :aria-label="`Open overview for ${dataset.name}`"
          @click="openOverview(dataset.id)"
        >
          Open overview
          <SVGIcons name="arrowForward" class="size-3.5" />
        </button>
        <button
          type="button"
          class="ui-button px-2.25 py-1.75 text-[10px]"
          aria-haspopup="dialog"
          aria-controls="quality-rules-dialog"
          :aria-label="`Edit quality rules for ${dataset.name}`"
          @click="emit('editQualityRules', dataset.id)"
        >
          <SVGIcons name="rules" class="size-3.25" />
          Edit quality rules
        </button>
      </div>
    </td>
  </tr>
</template>
