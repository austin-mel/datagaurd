import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useDatasetStore } from '@/stores'
import type { DatasetUploadSelection } from '@/services'

export function useDatasetUpload() {
  const datasetStore = useDatasetStore()
  const { source, uploadPolicy } = storeToRefs(datasetStore)
  const isConnectOpen = ref(false)
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

  return { isConnectOpen, uploadPolicy, uploading, uploadError, openUpload, upload }
}
