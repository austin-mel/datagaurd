<script setup lang="ts">
import { ModalShell } from '../ModalShell'

const isOpen = defineModel<boolean>({ required: true })
</script>

<template>
  <ModalShell
    id="connect-dataset-dialog"
    v-model="isOpen"
    title="Connect a data source"
    eyebrow="ADD TO YOUR WORKSPACE"
    description="Upload a file to bring a new dataset into your workspace."
    size="compact"
  >
    <template #icon>
      <svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6" /></svg>
    </template>

    <section
      class="flex flex-col items-center rounded-[10px] border border-dashed border-cobalt/40 bg-cobalt-soft/40 px-5 py-10 text-center"
      aria-label="File upload preview"
      @dragover.prevent
      @drop.prevent
    >
      <span class="mb-4 grid size-14 place-items-center rounded-xl bg-cobalt-soft text-cobalt">
        <svg class="ui-icon size-7" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6" /></svg>
      </span>
      <h3 class="text-[15px] font-semibold">Drag and drop your files here</h3>
      <p class="mt-2 text-xs text-muted">Or choose files from your computer.</p>
      <button type="button" class="ui-button mt-5" disabled>Browse files</button>
      <p class="mt-3 text-[11px] text-muted">CSV files with column headers</p>
    </section>
    <div class="mt-4 flex flex-wrap items-center justify-between gap-2 text-[11px] text-muted">
      <span>No files selected</span>
      <span>File uploads are coming soon.</span>
    </div>

    <template #footer="{ close }">
      <p class="text-[10px] text-muted">Your original source files will be preserved.</p>
      <div class="ml-auto flex gap-[9px]">
        <button type="button" class="ui-button" @click="close">Cancel</button>
        <button type="button" class="ui-button ui-button-primary" disabled>Connect &amp; validate</button>
      </div>
    </template>
  </ModalShell>
</template>
