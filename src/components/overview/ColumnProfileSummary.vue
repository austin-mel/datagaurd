<script setup lang="ts">
import type { ColumnProfile } from '@/types'
import { formatDate, formatNumber } from '@/utils'
defineProps<{ summary: ColumnProfile['summary']; column: string }>()
</script>

<template>
  <div class="w-full min-w-0 overflow-x-auto whitespace-nowrap pb-1" role="region" :aria-label="`Highlighted values for ${column}`" tabindex="0">
  <template v-if="summary.kind === 'top-values'">
    <template v-for="(value, index) in summary.values" :key="value.value">
      <span v-if="index" class="mx-2">/</span><strong class="font-[550] text-ink">{{ value.value }}</strong> · {{ formatNumber(value.count) }}<template v-if="summary.values.length === 1"> {{ value.count === 1 ? ' occurrence' : ' occurrences' }}</template>
    </template>
  </template>
  <template v-else-if="summary.kind === 'number-range'">
    Min <strong class="font-[550] text-ink">{{ formatNumber(summary.minimum) }}</strong><span class="mx-2">/</span>Max <strong class="font-[550] text-ink">{{ formatNumber(summary.maximum) }}</strong>
  </template>
  <template v-else>{{ formatDate(summary.minimum) }} – {{ formatDate(summary.maximum) }}</template>
  </div>
</template>
