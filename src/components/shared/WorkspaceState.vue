<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useDatasetStore } from '@/stores'
const store = useDatasetStore()
const { status, error } = storeToRefs(store)
const { load } = store
</script>

<template>
  <p v-if="status === 'idle' || status === 'loading'" class="text-sm text-muted" role="status">Loading datasets…</p>
  <div v-else-if="status === 'error'" class="ui-panel p-5" role="alert">
    <p class="mb-3 text-sm text-coral-text">{{ error }}</p>
    <button type="button" class="ui-button" @click="load">Try again</button>
  </div>
  <slot v-else />
</template>
