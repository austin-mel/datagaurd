<script setup lang="ts">
import { computed, useId } from 'vue'
import type { Dataset } from '@/types'
import { formatNumber } from '@/utils'
const props = defineProps<{ validation: Dataset['validation']; ruleset: Dataset['ruleset']; totalRows: number }>()
const emit = defineEmits<{ editRules: [] }>()
const headingId = useId()
const affectedColumns = computed(() => new Set(props.validation.issues.map(issue => issue.column)).size)
</script>

<template>
  <section class="ui-panel" :aria-labelledby="headingId">
    <header class="ui-panel-header">
      <div><h2 :id="headingId">Validation issues</h2><p>{{ formatNumber(validation.checksRun) }} enabled {{ validation.checksRun === 1 ? 'check' : 'checks' }} in the current {{ ruleset.kind }} ruleset. Updated when rules are saved.</p></div>
      <div class="flex flex-wrap items-center gap-2">
        <span class="ui-badge bg-cobalt-soft text-cobalt">{{ ruleset.name }}</span>
        <span v-if="!validation.checksRun" class="ui-badge bg-ivory text-muted">0 enabled checks</span>
        <span v-else class="ui-badge" :class="validation.issues.length ? 'bg-coral-soft text-coral-text' : 'bg-emerald-soft text-green-text'">{{ formatNumber(validation.issues.length) }} {{ validation.issues.length === 1 ? 'issue' : 'issues' }}</span>
      </div>
    </header>
    <p v-if="validation.issues.length" class="mx-[22px] mb-[18px] flex items-center gap-[9px] rounded-[7px] bg-coral-soft px-[13px] py-[11px] text-xs text-coral-text">
      <svg class="ui-icon size-4" viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 10 18H2zM12 9v5M12 17h.01" /></svg>
      {{ formatNumber(validation.issues.length) }} {{ validation.issues.length === 1 ? 'check' : 'checks' }} failed across {{ formatNumber(affectedColumns) }} {{ affectedColumns === 1 ? 'column' : 'columns' }}. Review before using this version.
    </p>
    <div class="overflow-x-auto" role="region" aria-label="Validation issues, horizontally scrollable" tabindex="0">
      <table class="ui-data-table min-w-[760px]">
        <thead><tr><th scope="col">Column</th><th scope="col">Rule</th><th scope="col">Message</th><th scope="col" class="text-right">Invalid Rows</th><th scope="col" class="text-right">Total Rows</th></tr></thead>
        <tbody>
          <tr v-for="issue in validation.issues" :key="issue.id">
            <th scope="row" class="align-top font-normal"><code>{{ issue.column }}</code></th>
            <td class="align-top font-mono text-[11px] text-muted">{{ issue.rule }}</td>
            <td class="max-w-[310px] align-top">{{ issue.message }}</td>
            <td class="text-right align-top tabular-nums">{{ formatNumber(issue.affectedRows) }}</td>
            <td class="text-right align-top tabular-nums">{{ formatNumber(totalRows) }}</td>
          </tr>
          <tr v-if="!validation.issues.length"><td colspan="5" class="text-center" :class="validation.checksRun ? 'text-green-text' : 'text-muted'">{{ validation.checksRun ? 'No validation issues found with the current saved ruleset.' : 'The assigned ruleset has no enabled checks. Add or enable a rule to validate this dataset.' }}</td></tr>
        </tbody>
      </table>
    </div>
    <footer class="ui-table-footer">
      <span>A row can fail more than one rule.</span>
      <button type="button" class="cursor-pointer text-xs font-[550] text-cobalt hover:underline" aria-haspopup="dialog" aria-controls="quality-rules-dialog" @click="emit('editRules')">Edit quality rules</button>
    </footer>
  </section>
</template>
