<script setup lang="ts">
import { computed, useId } from 'vue'
import type { Dataset } from '@/types'
import { formatNumber, formatPacificDate } from '@/utils'

const props = defineProps<{ dataset: Dataset }>()
const emit = defineEmits<{ 'edit-rules': [] }>()
const headingId = useId()
const enabledRuleCount = computed(() => props.dataset.ruleset.rules.filter(rule => rule.enabled).length)
</script>

<template>
  <section class="ui-panel" :aria-labelledby="headingId">
    <header class="ui-panel-header max-[540px]:px-4 max-[540px]:py-[18px]">
      <div><h2 :id="headingId">Dataset details</h2><p>Source and version information for this view.</p></div>
    </header>
    <dl class="grid grid-cols-2 gap-x-5 gap-y-[18px] px-[22px] pb-[23px] text-xs max-[540px]:px-4 max-[380px]:grid-cols-1">
      <div class="min-w-0">
        <dt class="mb-1 text-[10px] text-muted">Source</dt>
        <dd class="wrap-anywhere">{{ dataset.source }}</dd>
      </div>
      <div class="min-w-0">
        <dt class="mb-1 text-[10px] text-muted">Original filename</dt>
        <dd class="wrap-anywhere">{{ dataset.filename ?? 'Not applicable' }}</dd>
      </div>
      <div class="min-w-0">
        <dt class="mb-1 text-[10px] text-muted">{{ dataset.isCurrentVersion ? 'Current version' : 'Version' }}</dt>
        <dd class="wrap-anywhere">{{ dataset.version }}<template v-if="dataset.uploadedAt"> · Uploaded <time :datetime="dataset.uploadedAt">{{ formatPacificDate(dataset.uploadedAt) }}</time></template></dd>
      </div>
      <div class="min-w-0">
        <dt class="mb-1 text-[10px] text-muted">Uploaded by</dt>
        <dd class="wrap-anywhere">{{ dataset.uploadedBy ?? 'Not available' }}</dd>
      </div>
      <div class="min-w-0">
        <dt class="mb-1 text-[10px] text-muted">Validation set</dt>
        <dd>
          <button type="button" class="cursor-pointer text-left font-[550] text-cobalt wrap-anywhere hover:underline" aria-haspopup="dialog" aria-controls="quality-rules-dialog" @click="emit('edit-rules')">
            {{ dataset.ruleset.name }} · {{ formatNumber(enabledRuleCount) }} {{ enabledRuleCount === 1 ? 'rule' : 'rules' }}
          </button>
        </dd>
      </div>
      <div class="min-w-0">
        <dt class="mb-1 text-[10px] text-muted">Download filename</dt>
        <dd class="wrap-anywhere">{{ dataset.downloadFilename ?? 'Not available' }}</dd>
      </div>
    </dl>
  </section>
</template>
