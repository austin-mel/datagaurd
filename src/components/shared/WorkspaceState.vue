<script setup lang="ts">
import { SVGIcons } from '@/assets'
import { storeToRefs } from 'pinia'
import { useDatasetStore } from '@/stores'
const store = useDatasetStore()
const { status, error } = storeToRefs(store)
const { load } = store
</script>

<template>
  <p v-if="status === 'idle' || status === 'loading'" class="text-sm text-muted" role="status">Loading datasets…</p>
  <div v-else-if="status === 'error'" class="ui-panel p-5" role="alert">
    <p class="mb-3 flex items-start gap-2 text-sm text-coral-text"><SVGIcons name="error" class="mt-0.5 size-4" />{{ error }}</p>
    <button type="button" class="ui-button" @click="load"><SVGIcons name="refresh" class="size-4" /> Try again</button>
  </div>
  <slot v-else />
</template>
