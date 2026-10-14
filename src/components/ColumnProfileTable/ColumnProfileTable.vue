<script setup lang="ts">
import { useId } from 'vue'
import type { ColumnProfile } from '@/types'
import { formatDate, formatNumber } from '@/utils'
defineProps<{ profiles: readonly ColumnProfile[] | null; version: string }>()
const headingId = useId()
const types = { text: { label: 'Text', icon: 'Aa' }, integer: { label: 'Integer', icon: '#' }, number: { label: 'Number', icon: '#' }, date: { label: 'Date', icon: '' }, boolean: { label: 'Boolean', icon: '' } }
</script>

<template>
  <section class="ui-panel" :aria-labelledby="headingId">
    <header class="ui-panel-header">
      <div><h2 :id="headingId">Column profile</h2><p>Inferred types, missing values, and the shape of the current dataset.</p></div>
      <span v-if="profiles !== null" class="ui-badge bg-emerald-soft text-green-text">{{ formatNumber(profiles.length) }} {{ profiles.length === 1 ? 'column' : 'columns' }} profiled</span>
      <span v-else class="ui-badge bg-ivory text-muted">Not available</span>
    </header>
    <div class="overflow-x-auto" role="region" aria-label="Column profile, horizontally scrollable" tabindex="0">
      <table class="ui-data-table min-w-[680px]">
        <thead><tr><th scope="col">Column</th><th scope="col">Type</th><th scope="col">Missing</th><th scope="col">Unique</th><th scope="col">Highlighted Values</th></tr></thead>
        <tbody>
          <tr v-for="profile in profiles" :key="profile.name">
            <th scope="row" class="font-normal"><code>{{ profile.name }}</code></th>
            <td><span v-for="type in profile.observedTypes" :key="type" class="mr-2 inline-flex items-center gap-1.5 text-[11px] text-muted"><span v-if="types[type].icon" class="font-mono text-[10px]" aria-hidden="true">{{ types[type].icon }}</span>{{ types[type].label }}</span><span v-if="!profile.observedTypes.length" class="text-muted">Not available</span></td>
            <td class="tabular-nums"><span :class="profile.missingCount ? 'rounded bg-coral-soft px-[7px] py-0.5 font-semibold text-coral-text' : 'text-muted'">{{ formatNumber(profile.missingCount) }}</span></td>
            <td class="tabular-nums">{{ formatNumber(profile.uniqueCount) }}</td>
            <td class="text-[11px] text-muted">
              <template v-if="profile.summary.kind === 'top-values'">
                <template v-for="(value, index) in profile.summary.values" :key="value.value">
                  <span v-if="index" class="mx-2">/</span><strong class="font-[550] text-ink">{{ value.value }}</strong> · {{ formatNumber(value.count) }}<template v-if="profile.summary.values.length === 1"> {{ value.count === 1 ? ' occurrence' : ' occurrences' }}</template>
                </template>
              </template>
              <template v-else-if="profile.summary.kind === 'number-range'">
                Min <strong class="font-[550]" :class="profile.summary.minimumInvalid ? 'text-coral-text' : 'text-ink'">{{ formatNumber(profile.summary.minimum) }}</strong><span class="mx-2">/</span>Max <strong class="font-[550]" :class="profile.summary.maximumInvalid ? 'text-coral-text' : 'text-ink'">{{ formatNumber(profile.summary.maximum) }}</strong>
              </template>
              <template v-else>{{ formatDate(profile.summary.minimum) }} – {{ formatDate(profile.summary.maximum) }}</template>
            </td>
          </tr>
          <tr v-if="!profiles?.length"><td colspan="5" class="text-center text-muted">Column profile not available for this version.</td></tr>
        </tbody>
      </table>
    </div>
    <footer class="ui-table-footer"><span>Unique counts exclude missing values.</span><span>Profile for version {{ version }}</span></footer>
  </section>
</template>
