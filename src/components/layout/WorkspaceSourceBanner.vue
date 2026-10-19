<script setup lang="ts">
import { useDatasetStore } from '@/stores'
const datasetStore = useDatasetStore()
function reconnect() { window.location.reload() }
</script>

<template>
  <div v-if="datasetStore.source" class="mb-5 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line bg-porcelain px-4 py-3 text-xs" role="status">
    <span v-if="datasetStore.source.kind === 'api'">Connected to backend · Live data</span>
    <span v-else>Sample data · {{ datasetStore.source.reason === 'backend-unavailable' ? 'Backend unavailable.' : 'Demo mode.' }} Changes are saved only for this session.</span>
    <button v-if="datasetStore.source.kind === 'seeded' && datasetStore.source.reason === 'backend-unavailable'" type="button" class="ui-button" @click="reconnect">Reconnect (reload samples)</button>
  </div>
</template>
