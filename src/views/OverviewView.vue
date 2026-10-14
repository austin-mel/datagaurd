<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ColumnProfileTable, DatasetDetailsCard, DatasetHistoryCard, DatasetOverviewHeader, DatasetQualityCards, PageHeader, QualityRulesModal, RecentDatasets, ValidationIssuesTable } from '@/components'
import { useRulesetEditor } from '@/composables'
import { useDatasetStore, useRecentDatasetStore } from '@/stores'

const route = useRoute()
const router = useRouter()
const datasetStore = useDatasetStore()
const { datasets, status, error } = storeToRefs(datasetStore)
const { load } = datasetStore
const isDownloading = ref(false)
const downloadError = ref('')
const recentStore = useRecentDatasetStore()
const { visits, lastOpenedId } = storeToRefs(recentStore)
const { record, reconcile } = recentStore

watch(status, value => {
  if (value === 'ready') reconcile(datasets.value.map(dataset => dataset.id))
}, { immediate: true })

const recentDatasets = computed(() => visits.value.flatMap(visit => {
  const dataset = datasets.value.find(item => item.id === visit.datasetId)
  return dataset ? [{ dataset, openedAt: visit.openedAt }] : []
}))

const selectedDataset = computed(() => {
  if (route.query.dataset !== undefined) {
    return datasets.value.find(dataset => dataset.id === route.query.dataset)
  }
  return datasets.value.find(dataset => dataset.id === lastOpenedId.value) ?? datasets.value[0]
})

const { isOpen: isRulesOpen, isSaving, error: saveError, message: saveMessage, open: openRules, save: saveRules } = useRulesetEditor(selectedDataset)

watch(() => selectedDataset.value?.id, id => {
  isRulesOpen.value = false
  saveMessage.value = ''
  downloadError.value = ''
  if (id) record(id)
}, { immediate: true })

function openDataset(datasetId: string) {
  void router.push({ name: 'overview', query: { dataset: datasetId } })
}

async function downloadDataset() {
  const dataset = selectedDataset.value
  if (!dataset || isDownloading.value) return
  isDownloading.value = true
  downloadError.value = ''
  try {
    const { filename, blob } = await datasetStore.download(dataset.id, dataset.version)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    try {
      document.body.append(link)
      link.click()
    } finally {
      link.remove()
      // Allow the browser to start reading the file before releasing its URL.
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    }
  } catch {
    if (selectedDataset.value?.id === dataset.id) {
      downloadError.value = 'Unable to download this dataset. Please try again.'
    }
  } finally {
    isDownloading.value = false
  }
}

void load()
</script>

<template>
  <PageHeader
    title="Overview"
    subtitle="Pick up where you left off. See what needs attention."
    class="mb-[26px]"
  />
  <p v-if="status === 'idle' || status === 'loading'" class="text-sm text-muted" role="status">Loading datasets…</p>
  <div v-else-if="status === 'error'" class="ui-panel p-5" role="alert">
    <p class="mb-3 text-sm text-coral-text">{{ error }}</p>
    <button type="button" class="ui-button" @click="load">Try again</button>
  </div>
  <template v-else>
    <RecentDatasets :entries="recentDatasets" :selected-id="selectedDataset?.id" @open="openDataset" />
    <template v-if="selectedDataset">
      <DatasetOverviewHeader :dataset="selectedDataset" :downloading="isDownloading" :saving-rules="isSaving" @download="downloadDataset" @edit-rules="openRules" />
      <p v-if="downloadError" class="mb-[18px] text-xs text-coral-text" role="alert">{{ downloadError }}</p>
      <DatasetQualityCards :dataset="selectedDataset" />
      <div class="grid min-w-0 gap-[22px]">
        <div class="grid min-w-0 grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] gap-[22px] max-[760px]:grid-cols-1">
          <DatasetDetailsCard :dataset="selectedDataset" @edit-rules="openRules" />
          <DatasetHistoryCard :history="selectedDataset.history" />
        </div>
        <ColumnProfileTable :profiles="selectedDataset.columnProfiles" :version="selectedDataset.version" />
        <ValidationIssuesTable :validation="selectedDataset.validation" :ruleset-kind="selectedDataset.ruleset.kind" :total-rows="selectedDataset.rowCount" @edit-rules="openRules" />
      </div>
      <p role="status" class="mt-3 text-xs text-green-text">{{ saveMessage }}</p>
      <QualityRulesModal v-model="isRulesOpen" :dataset="selectedDataset" :saving="isSaving" :save-error="saveError" @save="saveRules" />
    </template>
    <div v-else class="ui-panel p-5">
      <p class="mb-3 text-sm text-muted">{{ datasets.length ? 'This dataset is no longer available. Choose another dataset to continue.' : 'No datasets are available yet.' }}</p>
      <RouterLink :to="{ name: 'datasets' }" class="ui-button">View datasets</RouterLink>
    </div>
  </template>
</template>
