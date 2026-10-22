<script setup lang="ts">
import type { Dataset } from '@/types'
import { formatNumber, formatScore } from '@/utils'
defineProps<{ dataset: Dataset }>()
</script>

<template>
  <section class="ui-panel mb-5.75 rounded-xl" :aria-label="`${dataset.name} quality scores`">
    <div class="grid grid-cols-4 max-[760px]:grid-cols-2 max-[380px]:grid-cols-1">
      <div class="min-w-0 border-r px-5.25 py-4.5 last:border-r-0 max-[760px]:nth-2:border-r-0 max-[760px]:[&:nth-child(-n+2)]:border-b max-[380px]:border-r-0 max-[380px]:not-last:border-b border-cobalt bg-cobalt text-porcelain">
        <p class="text-xs">Overall quality</p>
        <p class="mt-1.75 leading-[1.3] font-semibold tracking-[-0.9px] tabular-nums" :class="dataset.quality === null ? 'text-lg' : 'text-[31px]'">{{ formatScore(dataset.quality) }}<span v-if="dataset.quality !== null" class="ml-0.5 text-[15px] font-normal tracking-normal">/ 100</span></p>
        <p class="mt-1.25 text-[10px]">{{ dataset.name }} · {{ dataset.version }}</p>
      </div>
      <div v-for="dimension in dataset.qualityDimensions" :key="dimension.id" class="min-w-0 border-r px-5.25 py-4.5 last:border-r-0 max-[760px]:nth-2:border-r-0 max-[760px]:[&:nth-child(-n+2)]:border-b max-[380px]:border-r-0 max-[380px]:not-last:border-b border-line">
        <p class="text-xs text-muted">{{ dimension.label }}</p>
        <p class="mt-1.75 leading-[1.3] font-semibold tracking-[-0.9px] tabular-nums" :class="dimension.score === null ? 'text-lg' : 'text-[31px]'">{{ formatScore(dimension.score) }}<span v-if="dimension.score !== null" class="ml-0.5 text-[15px] font-normal tracking-normal">%</span></p>
        <p class="mt-1.25 text-[10px] text-muted"><template v-if="dimension.passed !== null && dimension.total !== null">{{ formatNumber(dimension.passed) }} / {{ formatNumber(dimension.total) }} </template> {{ dimension.description }}</p>
      </div>
    </div>
    <p class="border-t border-line px-4.5 py-2.5 text-[10px] leading-[1.7] text-muted">{{ dataset.qualityNote }}</p>
  </section>
</template>
