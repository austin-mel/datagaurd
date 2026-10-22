import { ref, watch, type Ref } from 'vue'
import { useDatasetStore } from '@/stores'
import type { Dataset } from '@/types'

export function useDatasetDownload(selectedDataset: Readonly<Ref<Dataset | undefined>>) {
  const datasetStore = useDatasetStore()
  const isDownloading = ref(false)
  const downloadError = ref('')
  watch(() => selectedDataset.value?.id, () => { downloadError.value = '' })
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
  return { isDownloading, downloadError, downloadDataset }
}
