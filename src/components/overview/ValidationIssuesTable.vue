<script setup lang="ts">
import { computed, useId } from 'vue'
import type { Dataset } from '@/types'
import { formatNumber } from '@/utils'
const props = defineProps<{ validation: Dataset['validation']; ruleset: Dataset['ruleset']; totalRows: number; stale?: boolean }>()
const emit = defineEmits<{ editRules: [] }>()
const headingId = useId()
const affectedColumns = computed(() => new Set(props.validation?.issues.map(issue => issue.column) ?? []).size)
</script>

<template>
  <section class="ui-panel" :aria-labelledby="headingId">
    <header class="ui-panel-header">
      <div><h2 :id="headingId">Validation issues</h2><p v-if="validation">{{ formatNumber(validation.checksRun) }} checks in the last completed run. Updated when validation is re-run.</p><p v-else>Not available. No completed validation result exists for the latest attempt.</p></div>
      <div class="flex flex-wrap items-center gap-2">
        <span class="ui-badge bg-cobalt-soft text-cobalt">{{ ruleset.name }}</span>
        <span v-if="!validation || stale" class="ui-badge bg-ivory text-muted">{{ !validation ? 'Not available' : 'Results out of date' }}</span>
        <span v-else-if="!validation.checksRun" class="ui-badge bg-ivory text-muted">0 enabled checks</span>
        <span v-else class="ui-badge" :class="validation.issues.length ? 'bg-coral-soft text-coral-text' : 'bg-emerald-soft text-green-text'">{{ formatNumber(validation.issues.length) }} {{ validation.issues.length === 1 ? 'issue' : 'issues' }}</span>
      </div>
    </header>
    <p v-if="validation?.issues.length" class="mx-5.5 mb-4.5 flex items-center gap-2.25 rounded-[7px] bg-coral-soft px-3.25 py-2.75 text-xs text-coral-text">
      <svg class="ui-icon size-4" viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 10 18H2zM12 9v5M12 17h.01" /></svg>
      {{ formatNumber(validation.issues.length) }} {{ validation.issues.length === 1 ? 'check' : 'checks' }} failed across {{ formatNumber(affectedColumns) }} {{ affectedColumns === 1 ? 'column' : 'columns' }}. Review before using this version.
    </p>
    <div class="overflow-x-auto" role="region" aria-label="Validation issues, horizontally scrollable" tabindex="0">
      <table class="ui-data-table min-w-190">
        <thead><tr><th scope="col">Column</th><th scope="col">Rule</th><th scope="col">Message</th><th scope="col" class="text-right">Invalid Rows</th><th scope="col" class="text-right">Total Rows</th></tr></thead>
        <tbody>
          <tr v-for="issue in validation?.issues ?? []" :key="issue.id">
            <th scope="row" class="align-top font-normal"><code>{{ issue.column }}</code></th>
            <td class="align-top font-mono text-[11px] text-muted">{{ issue.rule }}</td>
            <td class="max-w-77.5 align-top">{{ issue.message }}</td>
            <td class="text-right align-top tabular-nums">{{ formatNumber(issue.affectedRows) }}</td>
            <td class="text-right align-top tabular-nums">{{ formatNumber(totalRows) }}</td>
          </tr>
          <tr v-if="!validation"><td colspan="5" class="text-center text-muted">Validation results not available.</td></tr>
          <tr v-else-if="!validation.issues.length"><td colspan="5" class="text-center" :class="validation.checksRun && !stale ? 'text-green-text' : 'text-muted'">{{ stale ? 'Changes are pending. Run validation to refresh these results.' : validation.checksRun ? 'No validation issues found in the last completed run.' : 'The last run had no enabled checks.' }}</td></tr>
        </tbody>
      </table>
    </div>
    <footer class="ui-table-footer justify-center gap-25">
      <a href="#cell-review" class="text-xs font-[550] text-cobalt hover:underline">Review flagged cells</a>
      <button type="button" class="cursor-pointer text-xs font-[550] text-cobalt hover:underline" aria-haspopup="dialog" aria-controls="quality-rules-dialog" @click="emit('editRules')">Edit quality rules</button>
    </footer>
  </section>
</template>
