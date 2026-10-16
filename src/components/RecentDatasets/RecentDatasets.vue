<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, useId } from 'vue'
import { RouterLink } from 'vue-router'
import { DatasetSourceIcon } from '../DatasetSourceIcon'
import type { Dataset } from '@/types'
import { formatOpenedAt } from '@/utils'

defineProps<{ entries: readonly { dataset: Dataset; openedAt: number }[]; selectedId?: string }>()
const emit = defineEmits<{ open: [datasetId: string] }>()
const headingId = useId()
const now = ref(Date.now())
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => { timer = setInterval(() => { now.value = Date.now() }, 60000) })
onBeforeUnmount(() => { if (timer) clearInterval(timer) })
</script>

<template>
  <section :aria-labelledby="headingId" class="mb-7">
    <div class="mb-3 flex items-center justify-between gap-3">
      <h2 :id="headingId" class="text-[13px] font-[550]">Recently opened</h2>
      <RouterLink :to="{ name: 'datasets' }" class="ui-button px-2.5 py-1.75 text-[11px]">
        View all datasets
        <svg class="ui-icon size-4" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 5 7 7-7 7" /></svg>
      </RouterLink>
    </div>
    <div v-if="entries.length" class="grid grid-cols-3 gap-3.25 max-[760px]:grid-cols-1">
      <button
        v-for="entry in entries"
        :key="entry.dataset.id"
        type="button"
        class="flex min-w-0 cursor-pointer items-center gap-2.75 rounded-[10px] border p-3.75 text-left"
        :class="entry.dataset.id === selectedId ? 'border-cobalt/40 bg-cobalt-soft' : 'border-line bg-porcelain hover:border-cobalt/40'"
        :aria-pressed="entry.dataset.id === selectedId"
        @click="emit('open', entry.dataset.id)"
      >
        <span class="grid h-9.5 w-8.5 shrink-0 place-items-center rounded-[7px] border border-line bg-ivory text-muted" :class="{ 'bg-porcelain text-cobalt': entry.dataset.id === selectedId }">
          <DatasetSourceIcon :source="entry.dataset.sourceIcon" class="size-4.5" />
        </span>
        <span class="min-w-0 flex-1">
          <strong class="block text-xs font-semibold wrap-anywhere">{{ entry.dataset.name }}</strong>
          <span class="mt-1 block text-[10px] text-muted">{{ entry.dataset.source }} · <time :datetime="new Date(entry.openedAt).toISOString()">{{ formatOpenedAt(entry.openedAt, now) }}</time></span>
        </span>
        <span v-if="entry.dataset.id === selectedId" class="text-[10px] font-semibold text-cobalt max-[1250px]:hidden max-[760px]:block">Selected</span>
      </button>
    </div>
    <p v-else class="rounded-[10px] border border-line bg-porcelain p-3.75 text-xs text-muted">Datasets you open will appear here.</p>
  </section>
</template>
