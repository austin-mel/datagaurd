<script setup lang="ts">
import { SVGIcons } from '@/assets'
import type { Dataset } from '@/types'
import { formatNumber, formatValidatedAt } from '@/utils'
defineProps<{ dataset: Dataset; downloading?: boolean; savingRules?: boolean }>()
const emit = defineEmits<{ download: []; 'edit-rules': [] }>()
const statuses = {
  'needs-review': { label: 'Needs review', classes: 'bg-coral-soft text-coral-text' },
  healthy: { label: 'Healthy', classes: 'bg-emerald-soft text-green-text' },
  unvalidated: { label: 'Not evaluated', classes: 'bg-ivory text-muted' },
  running: { label: 'Running', classes: 'bg-cobalt-soft text-cobalt' },
  failed: { label: 'Validation failed', classes: 'bg-coral-soft text-coral-text' },
}
</script>

<template>
  <header class="mb-4.5 flex flex-wrap items-center justify-between gap-5 border-t border-line pt-6">
    <div class="min-w-0 flex-1 basis-105">
      <div class="flex flex-wrap items-center gap-2.25">
        <h2 class="text-2xl font-[620] tracking-[-0.7px] wrap-anywhere">{{ dataset.name }}</h2>
        <span class="ui-badge bg-cobalt-soft text-cobalt">{{ dataset.version }}<template v-if="dataset.isCurrentVersion"> · Current</template></span>
        <span class="ui-badge bg-cobalt-soft text-cobalt">{{ dataset.ruleset.kind === 'default' ? 'Default ruleset' : 'Custom ruleset' }}</span>
        <span class="ui-badge" :class="statuses[dataset.status].classes">{{ statuses[dataset.status].label }}</span>
      </div>
      <p class="mt-1.75 flex flex-wrap items-center gap-2 text-[11px] text-muted">
        <span class="wrap-anywhere">{{ dataset.filename ?? dataset.source }}</span><span aria-hidden="true">/</span>
        <span>{{ formatNumber(dataset.rowCount) }} rows</span><span aria-hidden="true">/</span>
        <span>{{ formatNumber(dataset.columns.length) }} columns</span><span aria-hidden="true">/</span>
        <span>Validated <time v-if="dataset.lastValidatedAt" :datetime="dataset.lastValidatedAt">{{ formatValidatedAt(dataset.lastValidatedAt) }}</time><span v-else>Not available</span></span>
      </p>
    </div>
    <div class="flex flex-wrap items-center gap-2.25 max-[540px]:w-full">
      <button type="button" class="ui-button max-[540px]:flex-1 max-[540px]:px-2.5 max-[540px]:text-[11px]" :disabled="savingRules" aria-haspopup="dialog" aria-controls="quality-rules-dialog" @click="emit('edit-rules')">
        <SVGIcons name="rules" class="size-4" />
        Edit quality rules
      </button>
      <button type="button" class="ui-button ui-button-primary max-[540px]:flex-1 max-[540px]:px-2.5 max-[540px]:text-[11px]" :disabled="downloading" :aria-busy="downloading" @click="emit('download')">
        <SVGIcons name="download" class="size-4" />
        {{ downloading ? 'Downloading…' : `Download ${dataset.version}` }}
      </button>
    </div>
  </header>
</template>
