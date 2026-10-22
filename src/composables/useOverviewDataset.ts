import { computed, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'
import { useDatasetStore, useRecentDatasetStore } from '@/stores'

export function useOverviewDataset() {
  const route = useRoute()
  const router = useRouter()
  const store = useDatasetStore()
  const { datasets, ruleCatalog, source, status } = storeToRefs(store)
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
  watch(() => selectedDataset.value?.id, id => { if (id) record(id) }, { immediate: true })
  function openDataset(datasetId: string) {
    void router.push({ name: 'overview', query: { dataset: datasetId } })
  }
  void store.load()
  return { datasets, ruleCatalog, source, selectedDataset, recentDatasets, openDataset }
}
