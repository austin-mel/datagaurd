<script setup lang="ts">
import ColumnProfileSummary from './ColumnProfileSummary.vue'
import { useId } from 'vue'
import type { ColumnProfile } from '@/types'
import { formatNumber } from '@/utils'
defineProps<{ profiles: readonly ColumnProfile[] | null; version: string }>()
const headingId = useId()
const sqlTypes = {
  text: 'TEXT',
  integer: 'INT',
  number: 'FLOAT',
  date: 'DATE',
  boolean: 'BOOLEAN',
} satisfies Record<ColumnProfile['observedTypes'][number], string>
</script>

<template>
  <section class="ui-panel" :aria-labelledby="headingId">
    <header class="ui-panel-header">
      <div><h2 :id="headingId">Column profile</h2><p>Inferred SQL types, missing values, and the shape of the current dataset.</p></div>
      <span v-if="profiles !== null" class="ui-badge bg-emerald-soft text-green-text">{{ formatNumber(profiles.length) }} {{ profiles.length === 1 ? 'column' : 'columns' }} profiled</span>
      <span v-else class="ui-badge bg-ivory text-muted">Not available</span>
    </header>
    <div class="overflow-x-auto" role="region" aria-label="Column profile, horizontally scrollable" tabindex="0">
      <table class="ui-data-table min-w-200 table-fixed">
        <colgroup><col class="w-37.5" /><col class="w-19" /><col class="w-21" /><col class="w-24" /><col class="w-21" /><col /></colgroup>
        <thead><tr><th scope="col">Column</th><th scope="col" class="text-center">Type</th><th scope="col" class="text-center">Missing</th><th scope="col" class="text-center">Warnings</th><th scope="col" class="text-center">Unique</th><th scope="col">Highlighted Values</th></tr></thead>
        <tbody>
          <tr v-for="profile in profiles" :key="profile.name">
            <th scope="row" class="font-normal wrap-anywhere"><code>{{ profile.name }}</code></th>
            <td class="text-center"><code v-for="type in profile.observedTypes" :key="type" class="block whitespace-normal text-[11px] text-muted">{{ sqlTypes[type] }}</code><span v-if="!profile.observedTypes.length" class="text-muted">Not available</span></td>
            <td class="text-center tabular-nums"><span :class="profile.missingCount ? 'rounded bg-coral-soft px-1.75 py-0.5 font-semibold text-coral-text' : 'text-muted'">{{ formatNumber(profile.missingCount) }}</span></td>
            <td class="text-center tabular-nums">
              <span v-if="profile.warningCount !== null"
                :class="profile.warningCount ? 'rounded bg-yellow-100 px-1.75 py-0.5 font-semibold text-yellow-800' : 'text-muted'"
                :title="`${formatNumber(profile.warningCount)} anomalous ${profile.warningCount === 1 ? 'cell' : 'cells'} flagged by statistical findings`">
                {{ formatNumber(profile.warningCount) }}
              </span>
              <span v-else class="text-muted" title="Statistical findings are not available">—</span>
            </td>
            <td class="text-center tabular-nums">{{ formatNumber(profile.uniqueCount) }}</td>
            <td class="text-[11px] text-muted">
              <ColumnProfileSummary :summary="profile.summary" :column="profile.name" />
            </td>
          </tr>
          <tr v-if="!profiles?.length"><td colspan="6" class="text-center text-muted">Column profile not available for this version.</td></tr>
        </tbody>
      </table>
    </div>
    <footer class="ui-table-footer"><span>Unique counts exclude missing values. Warnings count distinct cells flagged by statistical findings.</span><span>Profile for version {{ version }}</span></footer>
  </section>
</template>
