<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ColumnProfileTable, DatasetHistoryCard, DatasetOverviewHeader, DatasetQualityCards, PageHeader, QualityRulesModal, RecentDatasets, ValidationIssuesTable } from '@/components'
import { useRulesetEditor } from '@/composables'
import { useDatasetStore, useRecentDatasetStore } from '@/stores'

const route = useRoute()
const router = useRouter()
const datasetStore = useDatasetStore()
const { datasets, ruleCatalog, source, status, error } = storeToRefs(datasetStore)
const { load } = datasetStore
const isDownloading = ref(false)
const downloadError = ref('')
const isRevalidating = ref(false)
const validationError = ref('')
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
  validationError.value = ''
  if (id) record(id)
}, { immediate: true })

function openDataset(datasetId: string) {
  void router.push({ name: 'overview', query: { dataset: datasetId } })
}

async function rerunValidation() {
  const dataset = selectedDataset.value
  if (!dataset || !dataset.rulesChangedSinceRun || isRevalidating.value || isSaving.value || dataset.processingStatus === 'running') return
  isRevalidating.value = true
  validationError.value = ''
  saveMessage.value = ''
  try { await datasetStore.revalidate(dataset.id, dataset.version) }
  catch (cause) {
    if (selectedDataset.value?.id === dataset.id) validationError.value = cause instanceof Error ? cause.message : 'Unable to re-run validation.'
  } finally { isRevalidating.value = false }
}

// Future repositories may return a persisted running attempt before it completes.
let refreshTimer: ReturnType<typeof setTimeout> | undefined
let disposed = false
function scheduleRefresh() {
  clearTimeout(refreshTimer)
  if (disposed || selectedDataset.value?.processingStatus !== 'running') return
  const id = selectedDataset.value.id
  refreshTimer = setTimeout(async () => {
    try { await datasetStore.refreshDataset(id) }
    catch { validationError.value = 'Unable to refresh validation status. Retrying…' }
    scheduleRefresh()
  }, 3000)
}
watch(() => [selectedDataset.value?.id, selectedDataset.value?.processingStatus], scheduleRefresh)
onUnmounted(() => { disposed = true; clearTimeout(refreshTimer) })

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
      <button type="button"
        class="mb-3 flex min-h-[76px] w-full cursor-pointer items-center justify-center rounded-xl bg-emerald-700 px-6 py-5 text-xl font-semibold text-white shadow-sm hover:bg-emerald-800 focus-visible:outline-3 focus-visible:outline-offset-4 focus-visible:outline-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
        :disabled="!selectedDataset.rulesChangedSinceRun || isRevalidating || isSaving || selectedDataset.processingStatus === 'running'"
        :title="!selectedDataset.rulesChangedSinceRun ? 'The saved ruleset matches the last validation run.' : undefined"
        :aria-busy="isRevalidating || selectedDataset.processingStatus === 'running'" @click="rerunValidation">
        {{ isRevalidating || selectedDataset.processingStatus === 'running' ? 'Running Dataset Validation…' : 'Run Dataset Validation' }}
      </button>
      <p v-if="selectedDataset.rulesChangedSinceRun" class="mb-4 text-sm text-muted" role="status">Rules have changed since the displayed results. Re-run validation to apply them.</p>
      <p v-if="selectedDataset.processingStatus === 'running'" class="mb-4 text-sm text-muted" role="status">Validation is running. Results are not available yet.</p>
      <p v-if="selectedDataset.processingStatus === 'failed'" class="mb-4 text-sm text-coral-text" role="alert">Validation failed. Results are not available. {{ selectedDataset.processingError }}</p>
      <p v-if="validationError" class="mb-4 text-sm text-coral-text" role="alert">{{ validationError }}</p>
      <div class="grid min-w-0 gap-[22px]">
        <div class="grid min-w-0 grid-cols-[minmax(0,1fr)_300px] gap-[22px] max-[1279px]:grid-cols-1">
          <ColumnProfileTable :profiles="selectedDataset.columnProfiles" :version="selectedDataset.version" />
          <div class="relative min-w-0">
            <DatasetHistoryCard :history="selectedDataset.history" class="absolute inset-0 max-[1279px]:relative max-[1279px]:max-h-[28rem]" />
          </div>
        </div>
        <ValidationIssuesTable :validation="selectedDataset.validation" :ruleset="selectedDataset.ruleset" :stale="selectedDataset.rulesChangedSinceRun" :total-rows="selectedDataset.rowCount" @edit-rules="openRules" />
      </div>
      <p role="status" class="mt-3 text-xs text-green-text">{{ saveMessage }}</p>
      <QualityRulesModal v-if="ruleCatalog && source" v-model="isRulesOpen" :dataset="selectedDataset" :rule-catalog="ruleCatalog" :source-kind="source.kind" :saving="isSaving" :save-error="saveError" @save="saveRules" />
    </template>
    <div v-else class="ui-panel p-5">
      <p class="mb-3 text-sm text-muted">{{ datasets.length ? 'This dataset is no longer available. Choose another dataset to continue.' : 'No datasets are available yet.' }}</p>
      <RouterLink :to="{ name: 'datasets' }" class="ui-button">View datasets</RouterLink>
    </div>
  </template>
</template>
