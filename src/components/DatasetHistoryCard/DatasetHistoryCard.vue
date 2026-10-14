<script setup lang="ts">
import { computed, useId } from 'vue'
import type { DatasetHistoryEvent } from '@/types'
import { formatPacificDate, formatPacificTime } from '@/utils'

const props = defineProps<{ history?: readonly DatasetHistoryEvent[] }>()
const headingId = useId()
const dateGroups = computed(() => {
  const groups = new Map<string, DatasetHistoryEvent[]>()
  for (const event of props.history ?? []) {
    const date = formatPacificDate(event.occurredAt)
    const events = groups.get(date) ?? []
    events.push(event)
    groups.set(date, events)
  }
  return Array.from(groups, ([date, events]) => ({ date, events }))
})
</script>

<template>
  <section class="ui-panel" :aria-labelledby="headingId">
    <header class="ui-panel-header max-[540px]:px-4 max-[540px]:py-[18px]">
      <div>
        <h2 :id="headingId">Dataset history</h2>
        <p>{{ dateGroups.length === 1 ? dateGroups[0]?.date : 'Recent activity' }} · Pacific time</p>
      </div>
    </header>
    <div class="space-y-4 px-[22px] pb-5 max-[540px]:px-4">
      <div v-for="group in dateGroups" :key="group.date">
        <h3 v-if="dateGroups.length > 1" class="mb-3 text-[11px] font-[550] text-muted">{{ group.date }}</h3>
        <ol class="flex flex-col gap-4">
          <li v-for="event in group.events" :key="event.id" class="grid grid-cols-[44px_minmax(0,1fr)] gap-2.5">
            <time :datetime="event.occurredAt" class="mt-0.5 font-mono text-[10px] text-muted">{{ formatPacificTime(event.occurredAt) }}</time>
            <div class="wrap-anywhere">
              <strong class="block text-xs font-[550]">{{ event.title }}</strong>
              <small class="mt-0.5 block text-[10px] text-muted">{{ event.description }}</small>
            </div>
          </li>
        </ol>
      </div>
      <p v-if="!dateGroups.length" class="text-xs text-muted">No history is available for this dataset yet.</p>
    </div>
  </section>
</template>
