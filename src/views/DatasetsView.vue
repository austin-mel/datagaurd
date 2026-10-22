<script setup lang="ts">
import { SVGIcons } from '@/assets'
import {
  WorkspaceState,
  PageHeader,
  ConnectDatasetModal,
  DatasetTable,
  QualityRulesModal,
} from '@/components'
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useRulesetEditor, useDatasetUpload } from '@/composables'
import { useDatasetStore } from '@/stores'

const search = ref('')
const datasetStore = useDatasetStore()
const { datasets, ruleCatalog, source, status } = storeToRefs(datasetStore)
const { isConnectOpen, uploadPolicy, uploading, uploadError, openUpload, upload } = useDatasetUpload()
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
        <SVGIcons name="add" class="size-4" />
        Connect a new data source
      </button>
    </template>
  </PageHeader>

  <div class="mb-4.5 flex justify-end">
    <label class="flex w-56.25 items-center gap-2 rounded-[7px] border border-line bg-porcelain px-3 py-2.25 text-xs text-muted focus-within:outline-2 focus-within:outline-cobalt max-[760px]:w-full">
      <SVGIcons name="search" class="size-4" />
      <span class="sr-only">Search datasets</span>
      <input v-model="search" type="search" placeholder="Search datasets…" class="w-full min-w-0 bg-transparent text-ink placeholder:text-muted focus-visible:outline-none" />
    </label>
  </div>

  <WorkspaceState>
    <DatasetTable :datasets="datasets" :search="search" @edit-quality-rules="openRules" />
  </WorkspaceState>
  <p role="status" class="mt-3 text-xs text-green-text">{{ saveMessage }}</p>
  <QualityRulesModal v-if="selectedDataset && ruleCatalog && source" v-model="isRulesOpen" :dataset="selectedDataset" :rule-catalog="ruleCatalog" :source-kind="source.kind" :saving="isSaving" :save-error="saveError" @save="saveRules" />
  <ConnectDatasetModal v-model="isConnectOpen" :policy="uploadPolicy ?? undefined" :upload-available="source?.kind === 'api' && !!uploadPolicy"
    :uploading="uploading" :upload-error="uploadError" @upload="upload" />
</template>
