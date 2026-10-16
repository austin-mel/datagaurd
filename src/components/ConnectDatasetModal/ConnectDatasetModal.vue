<script setup lang="ts">
import { computed, ref, useTemplateRef, watch } from 'vue'
import { ModalShell } from '../ModalShell'
import { defaultUploadPolicy, type UploadPolicy } from '@/types/backend'
import { validateUpload, type DatasetUploadSelection } from '@/services/datasetUpload'

const props = withDefaults(defineProps<{ policy?: UploadPolicy; uploadAvailable?: boolean; uploading?: boolean; uploadError?: string }>(), {
  policy: () => defaultUploadPolicy, uploadAvailable: false, uploading: false, uploadError: '',
})
const isOpen = defineModel<boolean>({ required: true })
const emit = defineEmits<{ upload: [selection: DatasetUploadSelection] }>()
const input = useTemplateRef<HTMLInputElement>('fileInput')
const selected = ref<File | null>(null)
const sheetName = ref('')
const error = ref('')
const accept = computed(() => props.policy.extensions.join(','))
const isWorkbook = computed(() => selected.value?.name.toLowerCase().endsWith('.xlsx'))
watch(isOpen, () => { selected.value = null; error.value = ''; sheetName.value = '' })
function choose(files: FileList | null) {
  error.value = ''
  selected.value = null
  if (!files?.length) return
  if (files.length !== 1) { error.value = 'Choose one dataset file at a time.'; return }
  const file = files[0]
  if (!file) return
  error.value = validateUpload(file, props.policy) ?? ''
  if (!error.value) selected.value = file
}
function submit() {
  if (!selected.value || !props.uploadAvailable || props.uploading) return
  error.value = validateUpload(selected.value, props.policy) ?? ''
  if (!error.value) emit('upload', { file: selected.value, ...(isWorkbook.value && sheetName.value.trim() ? { sheetName: sheetName.value.trim() } : {}) })
}
</script>

<template>
  <ModalShell id="connect-dataset-dialog" v-model="isOpen" title="Connect a data source" eyebrow="ADD TO YOUR WORKSPACE"
    description="Upload a dataset file from your computer." size="compact" :dismissible="!uploading">
    <template #icon><svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6" /></svg></template>
    <section class="flex flex-col items-center rounded-[10px] border border-dashed border-cobalt/40 bg-cobalt-soft/40 px-5 py-10 text-center"
      aria-label="Dataset file upload" @dragover.prevent @drop.prevent="!uploading && choose($event.dataTransfer?.files ?? null)">
      <h3 class="text-[15px] font-semibold">Drag and drop a dataset file here</h3>
      <p class="mt-2 text-xs text-muted">Or choose a file from your computer.</p>
      <input ref="fileInput" type="file" class="sr-only" :accept="accept" :disabled="uploading" aria-label="Dataset file"
        @change="choose(($event.target as HTMLInputElement).files)" />
      <button type="button" class="ui-button mt-5" :disabled="uploading" @click="input?.click()">Browse files</button>
      <p class="mt-3 text-[11px] text-muted">{{ policy.extensions.join(', ') }} · Up to {{ Math.round(policy.max_upload_bytes / 1024 / 1024) }} MB</p>
    </section>
    <p class="mt-4 text-xs text-muted">{{ selected?.name ?? 'No file selected' }}</p>
    <label v-if="isWorkbook" class="mt-4 block text-xs">Worksheet name
      <input v-model="sheetName" class="ui-control mt-2 w-full" placeholder="Required when the workbook has multiple worksheets" :disabled="uploading" />
    </label>
    <p v-if="error || uploadError" role="alert" class="mt-3 text-xs text-coral-text">{{ error || uploadError }}</p>
    <p v-if="!uploadAvailable" class="mt-3 text-xs text-muted">Uploads are not available in this sample workspace.</p>
    <template #footer="{ close }">
      <p class="text-[10px] text-muted">Your original source files will be preserved.</p>
      <div class="ml-auto flex gap-2.25">
        <button type="button" class="ui-button" :disabled="uploading" @click="close">Cancel</button>
        <button type="button" class="ui-button ui-button-primary" :disabled="!selected || !!error || !uploadAvailable || uploading" @click="submit">
          {{ uploading ? 'Uploading…' : 'Upload & validate' }}
        </button>
      </div>
    </template>
  </ModalShell>
</template>

