<script setup lang="ts">
import { SVGIcons } from '@/assets'
import { computed } from 'vue'
import type { Dataset } from '@/types'
const props = defineProps<{ dataset: Dataset; pending: boolean; revalidating: boolean; saving: boolean; error: string }>()
const emit = defineEmits<{ run: [] }>()
const running = computed(() => props.revalidating || props.dataset.processingStatus === 'running')
</script>

<template>
  <button type="button"
    class="mb-3 flex min-h-19 w-full cursor-pointer items-center justify-center gap-3 rounded-xl bg-emerald-700 px-6 py-5 text-xl font-semibold text-white shadow-sm hover:bg-emerald-800 focus-visible:outline-3 focus-visible:outline-offset-4 focus-visible:outline-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
    :disabled="!pending || running || saving"
    :title="!pending ? 'The dataset and ruleset match the last validation run.' : undefined"
    :aria-busy="running" @click="emit('run')">
    <SVGIcons name="science" class="size-6" />
    {{ running ? 'Running Dataset Validation…' : 'Run Dataset Validation' }}
  </button>
  <p v-if="dataset.rulesChangedSinceRun" class="mb-4 text-sm text-muted" role="status">Rules have changed since the displayed results. Re-run validation to apply them.</p>
  <p v-if="dataset.reviewChangedSinceRun" class="mb-4 text-sm text-muted" role="status">{{ dataset.dataChangedSinceRun ? 'Dataset edits are saved in this version. Run validation to refresh profiles, errors, and quality scores.' : 'Ignored findings have been removed from review. Run validation to refresh error counts and quality scores.' }}</p>
  <p v-if="dataset.processingStatus === 'running'" class="mb-4 text-sm text-muted" role="status">Validation is running. Results are not available yet.</p>
  <p v-if="dataset.processingStatus === 'failed'" class="mb-4 text-sm text-coral-text" role="alert">Validation failed. Results are not available. {{ dataset.processingError }}</p>
  <p v-if="error" class="mb-4 text-sm text-coral-text" role="alert">{{ error }}</p>
</template>
