<script setup lang="ts">
import { computed, ref } from 'vue'
import { ConnectDatasetModal, DatasetTable, PageHeader, QualityRulesModal } from '@/components'
import { cloneRuleset, createSeededDatasets, type DatasetRuleset } from '@/data'

const search = ref('')
const isRulesOpen = ref(false)
const isConnectOpen = ref(false)
const datasets = ref(createSeededDatasets())
const selectedDatasetId = ref<string | null>(null)
const selectedDataset = computed(() => datasets.value.find(dataset => dataset.id === selectedDatasetId.value))
const saveMessage = ref('')

function saveRules(ruleset: DatasetRuleset) {
  const dataset = selectedDataset.value
  if (!dataset) return
  dataset.ruleset = cloneRuleset(ruleset)
  saveMessage.value = `Quality rules for ${dataset.name} saved for this page session.`
}

function openRules(datasetId: string) {
  if (!datasets.value.some(dataset => dataset.id === datasetId)) return
  selectedDatasetId.value = datasetId
  saveMessage.value = ''
  isRulesOpen.value = true
}
</script>

<template>
  <PageHeader
    title="Datasets"
    subtitle="Every source in one place. Open a dataset to inspect its latest version."
    class="mb-[26px] max-[540px]:mb-[23px]"
  >
    <template #actions>
      <button type="button" class="ui-button ui-button-primary" aria-haspopup="dialog" aria-controls="connect-dataset-dialog" @click="isConnectOpen = true">
        <svg class="ui-icon size-4" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
        Connect a new data source
      </button>
    </template>
  </PageHeader>

  <div class="mb-[18px] flex justify-end">
    <label class="flex w-[225px] items-center gap-2 rounded-[7px] border border-line bg-porcelain px-3 py-[9px] text-xs text-muted focus-within:outline-2 focus-within:outline-cobalt max-[760px]:w-full">
      <svg class="ui-icon size-4" viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></svg>
      <span class="sr-only">Search datasets</span>
      <input v-model="search" type="search" placeholder="Search datasets…" class="w-full min-w-0 bg-transparent text-ink placeholder:text-muted focus-visible:outline-none" />
    </label>
  </div>

  <DatasetTable :datasets="datasets" :search="search" @edit-quality-rules="openRules" />
  <p role="status" class="mt-3 text-xs text-green-text">{{ saveMessage }}</p>
  <QualityRulesModal v-if="selectedDataset" v-model="isRulesOpen" :dataset="selectedDataset" @save="saveRules" />
  <ConnectDatasetModal v-model="isConnectOpen" />
</template>
