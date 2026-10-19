<script setup lang="ts">
import type { QualityRule, RuleEditorCatalog, RuleType } from '@/types'
import { ruleDefaults } from '@/utils'
import RuleConditionFields from './RuleConditionFields.vue'
const props = defineProps<{ number: number; columns: readonly string[]; ruleCatalog: RuleEditorCatalog; locked: boolean }>()
const rule = defineModel<QualityRule>({ required: true })
const emit = defineEmits<{ remove: []; resetCondition: [] }>()
function update(patch: Partial<QualityRule>) { rule.value = { ...rule.value, ...patch } }
function changeType(type: RuleType) {
  if (props.locked) return
  update({ type, ...ruleDefaults(props.ruleCatalog, type) })
  emit('resetCondition')
}
</script>

<template>
  <tr class="border-b border-line last:border-0">
    <td>
      <input :checked="rule.enabled" @change="update({ enabled: ($event.target as HTMLInputElement).checked })" type="checkbox" :disabled="locked" class="size-3.5 accent-cobalt" :aria-label="`Enable rule ${number}: ${rule.column}`" />
    </td>
    <td>
      <select :value="rule.column" @change="update({ column: ($event.target as HTMLSelectElement).value })" :disabled="locked" class="ui-control w-42.75 font-mono" :aria-label="`Column for rule ${number}`">
        <option v-for="column in columns" :key="column" :value="column">{{ column }}</option>
      </select>
    </td>
    <td>
      <select :value="rule.type" :disabled="locked" class="ui-control w-33.75" :aria-label="`Type for rule ${number}`" @change="changeType(($event.target as HTMLSelectElement).value as RuleType)">
        <option v-for="type in ruleCatalog.ruleTypes" :key="type.value" :value="type.value">{{ type.label }}</option>
      </select>
    </td>
    <td class="min-w-58.75">
      <RuleConditionFields v-model="rule" :number="number" :rule-catalog="ruleCatalog" />
    </td>
    <td>
      <button type="button" :disabled="locked" class="cursor-pointer rounded p-1.25 text-muted enabled:hover:bg-coral-soft enabled:hover:text-coral-text disabled:cursor-not-allowed disabled:opacity-40" :aria-label="`Remove rule ${number}: ${rule.column}`" @click="emit('remove')">
        <svg class="ui-icon size-3.5" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7" /></svg>
      </button>
    </td>
  </tr>
</template>
