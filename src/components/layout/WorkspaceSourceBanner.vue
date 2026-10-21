<script setup lang="ts">
import { SVGIcons } from '@/assets'
import { useDatasetStore } from '@/stores'
const datasetStore = useDatasetStore()
function reconnect() { window.location.reload() }
</script>

<template>
  <div v-if="datasetStore.source" class="mb-5 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line bg-porcelain px-4 py-3 text-xs" role="status">
    <span v-if="datasetStore.source.kind === 'api'">Viewing live data · Connected to backend.</span>
    <span v-else>Viewing seeded sample data · {{ datasetStore.source.reason === 'backend-unavailable' ? 'Backend unavailable. To save resources, the backend spins down after idling, after a request it takes ~1 minute to spin back up.' : 'Demo mode enabled.' }} Changes are saved only for this session.</span>
    <button v-if="datasetStore.source.kind === 'seeded' && datasetStore.source.reason === 'backend-unavailable'" type="button" class="ui-button" @click="reconnect">
      <SVGIcons name="refresh" class="size-4" />
      Reconnect (reload samples)
    </button>
  </div>
</template>
