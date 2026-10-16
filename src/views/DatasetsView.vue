<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { ConnectDatasetModal, DatasetTable, PageHeader, QualityRulesModal } from '@/components'
import { useRulesetEditor } from '@/composables'
import { useDatasetStore } from '@/stores'
import type { DatasetUploadSelection } from '@/services/datasetUpload'

const search = ref('')
const isConnectOpen = ref(false)
const datasetStore = useDatasetStore()
const { datasets, ruleCatalog, source, status, error, uploadPolicy } = storeToRefs(datasetStore)
const uploading = ref(false)
const uploadError = ref('')
async function openUpload() {
  uploadError.value = ''
  isConnectOpen.value = true
  if (source.value?.kind === 'api') {
    try { await datasetStore.loadUploadPolicy() }
    catch (cause) { uploadError.value = cause instanceof Error ? cause.message : 'Unable to load upload limits.' }
  }
}
async function upload(selection: DatasetUploadSelection) {
  uploading.value = true
  uploadError.value = ''
  try {
    await datasetStore.upload(selection)
    isConnectOpen.value = false
  } catch (cause) { uploadError.value = cause instanceof Error ? cause.message : 'Upload failed.' }
  finally { uploading.value = false }
}
const { load } = datasetStore
const selectedDatasetId = ref<string | null>(null)
const selectedDataset = computed(() => datasets.value.find(dataset => dataset.id === selectedDatasetId.value))
const { isOpen: isRulesOpen, isSaving, error: saveError, message: saveMessage, open: openEditor, save: saveRules } = useRulesetEditor(selectedDataset)

function openRules(datasetId: string) {
  if (!datasets.value.some(dataset => dataset.id === datasetId)) return
  selectedDatasetId.value = datasetId
  openEditor()
}

void load()
</script>

<template>
  <PageHeader
    title="Datasets"
    subtitle="Every source in one place. Open a dataset to inspect its latest version."
    class="mb-6.5 max-[540px]:mb-5.75"
  >
    <template #actions>
      <button type="button" class="ui-button ui-button-primary" :disabled="status !== 'ready'" aria-haspopup="dialog" aria-controls="connect-dataset-dialog" @click="openUpload">
        <svg class="ui-icon size-4" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
        Connect a new data source
      </button>
    </template>
  </PageHeader>

  <div class="mb-4.5 flex justify-end">
    <label class="flex w-56.25 items-center gap-2 rounded-[7px] border border-line bg-porcelain px-3 py-2.25 text-xs text-muted focus-within:outline-2 focus-within:outline-cobalt max-[760px]:w-full">
      <svg class="ui-icon size-4" viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></svg>
      <span class="sr-only">Search datasets</span>
      <input v-model="search" type="search" placeholder="Search datasets…" class="w-full min-w-0 bg-transparent text-ink placeholder:text-muted focus-visible:outline-none" />
    </label>
  </div>

  <p v-if="status === 'idle' || status === 'loading'" class="text-sm text-muted" role="status">Loading datasets…</p>
  <div v-else-if="status === 'error'" class="ui-panel p-5" role="alert">
    <p class="mb-3 text-sm text-coral-text">{{ error }}</p>
    <button type="button" class="ui-button" @click="load">Try again</button>
  </div>
  <DatasetTable v-else :datasets="datasets" :search="search" @edit-quality-rules="openRules" />
  <p role="status" class="mt-3 text-xs text-green-text">{{ saveMessage }}</p>
  <QualityRulesModal v-if="selectedDataset && ruleCatalog && source" v-model="isRulesOpen" :dataset="selectedDataset" :rule-catalog="ruleCatalog" :source-kind="source.kind" :saving="isSaving" :save-error="saveError" @save="saveRules" />
  <ConnectDatasetModal v-model="isConnectOpen" :policy="uploadPolicy ?? undefined" :upload-available="source?.kind === 'api' && !!uploadPolicy"
    :uploading="uploading" :upload-error="uploadError" @upload="upload" />
</template>
