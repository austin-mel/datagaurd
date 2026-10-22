<script setup lang="ts">
import { computed } from 'vue'
import type { QualityRule, RuleEditorCatalog } from '@/types'
defineProps<{ number: number; ruleCatalog: RuleEditorCatalog }>()
const rule = defineModel<QualityRule>({ required: true })
function field<K extends keyof QualityRule>(key: K) {
  return computed({ get: () => rule.value[key], set: (value: QualityRule[K]) => { rule.value = { ...rule.value, [key]: value } } })
}
const condition = field('condition')
const minimum = field('minimum')
const maximum = field('maximum')
const selectedDate = field('selectedDate')
const endDate = field('endDate')
</script>

<template>
  <div v-if="rule.type === 'range'" class="flex gap-2">
    <label class="min-w-0 flex-1 text-[9px] text-muted">
      Minimum
      <input v-model="minimum" type="number" step="any" class="ui-control mt-0.75" required :aria-label="`Minimum for rule ${number}`" />
    </label>
    <label class="min-w-0 flex-1 text-[9px] text-muted">
      Maximum
      <input v-model="maximum" type="number" step="any" class="ui-control mt-0.75" required :aria-label="`Maximum for rule ${number}`" />
    </label>
  </div>
  <input v-else-if="rule.type === 'min'" v-model="minimum" type="number" step="any" class="ui-control" required :aria-label="`Minimum for rule ${number}`" />
  <input v-else-if="rule.type === 'max'" v-model="maximum" type="number" step="any" class="ui-control" required :aria-label="`Maximum for rule ${number}`" />
  <div v-else-if="rule.type === 'date'" class="space-y-2">
    <select v-model="condition" class="ui-control" :aria-label="`Date condition for rule ${number}`">
      <option v-for="condition in ruleCatalog.dateConditions" :key="condition" :value="condition">{{ condition }}</option>
    </select>
    <div class="flex gap-2">
      <label class="min-w-0 flex-1 text-[9px] text-muted">
        {{ rule.condition === 'Between two selected dates' ? 'Start date (inclusive)' : 'Selected date' }}
        <input v-model="selectedDate" type="date" min="0001-01-01" :max="rule.condition === 'Between two selected dates' && rule.endDate ? rule.endDate : '9999-12-31'" required class="ui-control mt-0.75" :aria-label="`Selected date for rule ${number}`" />
      </label>
      <label v-if="rule.condition === 'Between two selected dates'" class="min-w-0 flex-1 text-[9px] text-muted">
        End date (inclusive)
        <input v-model="endDate" type="date" :min="rule.selectedDate || '0001-01-01'" max="9999-12-31" required class="ui-control mt-0.75" :aria-label="`End date for rule ${number}`" />
      </label>
    </div>
  </div>
  <input
    v-else
    v-model="condition"
    class="ui-control"
    :readonly="rule.type === 'required' || rule.type === 'unique' || rule.type === 'numeric'"
    required
    :aria-label="`Condition for rule ${number}`"
  />
</template>
