<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import type { Dataset } from '@/data'

const props = withDefaults(defineProps<{ datasets: readonly Dataset[]; search?: string }>(), { search: '' })
const emit = defineEmits<{ editQualityRules: [datasetId: string] }>()
const router = useRouter()
const rowCountFormatter = new Intl.NumberFormat('en-US')
const filteredDatasets = computed(() => {
  const query = props.search.trim().toLowerCase()
  return props.datasets.filter(dataset => `${dataset.name} ${dataset.source} ${dataset.filename ?? ''}`.toLowerCase().includes(query))
})

function openOverview(datasetId: string) {
  void router.push({ name: 'overview', query: { dataset: datasetId } })
}
</script>

<template>
  <section
    class="overflow-hidden rounded-[13px] border border-line bg-porcelain"
    aria-label="All connected datasets"
  >
    <div
      class="overflow-x-auto focus-visible:outline-3 focus-visible:-outline-offset-3 focus-visible:outline-cobalt"
      role="region"
      aria-label="Dataset catalog, horizontally scrollable"
      tabindex="0"
    >
      <table class="catalog-table w-full min-w-[860px] border-collapse text-left">
        <thead class="border-b border-line bg-table-header text-[10px] whitespace-nowrap text-muted">
          <tr>
            <th scope="col">Dataset / source</th>
            <th scope="col">Current version</th>
            <th scope="col">Quality</th>
            <th scope="col">Last validated</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody class="text-xs">
          <tr v-for="dataset in filteredDatasets" :key="dataset.id" class="border-b border-line last:border-0 hover:bg-table-selected">
            <th scope="row">
              <div class="flex items-center gap-[11px]">
                <span
                  class="grid h-[38px] w-[34px] shrink-0 place-items-center rounded-[7px] border border-line bg-ivory text-muted"
                >
                  <svg class="icon size-[18px]" viewBox="0 0 24 24" aria-hidden="true">
                    <template v-if="dataset.sourceIcon === 'file'">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <path d="M14 2v6h6M8 13h8M8 17h5" />
                    </template>
                    <path v-else d="M7 18a5 5 0 1 1 1-9.9A6 6 0 0 1 20 10a4 4 0 0 1-1 8H7z" />
                  </svg>
                </span>
                <div>
                  <strong class="block font-[550]">{{ dataset.name }}</strong>
                  <span class="mt-[3px] block text-[10px] font-normal text-muted">
                    {{ dataset.source }} · {{ rowCountFormatter.format(dataset.rowCount) }} rows
                  </span>
                </div>
              </div>
            </th>
            <td>
              <span
                class="inline-flex rounded-[5px] bg-cobalt-soft px-[7px] py-1 text-[10px] font-semibold text-cobalt"
              >
                {{ dataset.version }}
              </span>
            </td>
            <td class="tabular-nums">{{ dataset.quality }}</td>
            <td class="whitespace-nowrap text-muted">
              <time :datetime="dataset.lastValidatedAt">{{ dataset.lastValidatedLabel }}</time>
            </td>
            <td>
              <div class="flex items-center gap-6 whitespace-nowrap">
                <button
                  type="button"
                  class="ui-button px-[9px] py-[7px] text-[10px] text-cobalt"
                  :aria-label="`Open overview for ${dataset.name}`"
                  @click="openOverview(dataset.id)"
                >
                  Open overview
                </button>
                <button
                  type="button"
                  class="ui-button px-[9px] py-[7px] text-[10px]"
                  aria-haspopup="dialog"
                  aria-controls="quality-rules-dialog"
                  :aria-label="`Edit quality rules for ${dataset.name}`"
                  @click="emit('editQualityRules', dataset.id)"
                >
                  <svg class="icon size-[13px]" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M10 6h11M10 12h11M10 18h11M3 5l1 1 2-2M3 11l1 1 2-2M3 17l1 1 2-2" />
                  </svg>
                  Edit quality rules
                </button>
              </div>
            </td>
          </tr>
          <tr v-if="filteredDatasets.length === 0">
            <td colspan="5" class="text-center text-muted">No datasets match your search.</td>
          </tr>
        </tbody>
      </table>
    </div>
    <footer
      class="flex flex-wrap items-center justify-between gap-[9px] border-t border-line px-[22px] py-[11px] text-[10px] text-muted max-[540px]:px-4"
    >
      <span role="status">{{ filteredDatasets.length }} {{ filteredDatasets.length === 1 ? 'dataset' : 'datasets' }}</span>
      <span>Quality scores are out of 100.</span>
    </footer>
  </section>
</template>

<style scoped>
.catalog-table thead th {
  padding: 10px 16px;
  font-weight: 550;
}

.catalog-table tbody th,
.catalog-table td {
  padding: 14px 16px;
}

.catalog-table th:first-child {
  padding-left: 22px;
}

.catalog-table th:last-child,
.catalog-table td:last-child {
  padding-right: 22px;
}

.icon {
  flex-shrink: 0;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}
</style>
