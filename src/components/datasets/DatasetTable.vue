<script setup lang="ts">
import { computed } from 'vue'
import type { Dataset } from '@/types'
import { DatasetTableRow } from '@/components'

const props = withDefaults(defineProps<{ datasets: readonly Dataset[]; search?: string }>(), { search: '' })
const emit = defineEmits<{ editQualityRules: [datasetId: string] }>()
const filteredDatasets = computed(() => {
  const query = props.search.trim().toLowerCase()
  return props.datasets.filter(dataset => `${dataset.name} ${dataset.source} ${dataset.filename ?? ''}`.toLowerCase().includes(query))
})

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
      <table class="catalog-table w-full min-w-215 border-collapse text-left">
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
          <DatasetTableRow v-for="dataset in filteredDatasets" :key="dataset.id" :dataset="dataset" @edit-quality-rules="emit('editQualityRules', $event)" />
          <tr v-if="filteredDatasets.length === 0">
            <td colspan="5" class="text-center text-muted">{{ datasets.length ? 'No datasets match your search.' : 'No datasets yet. Connect a data source to get started.' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <footer
      class="flex flex-wrap items-center justify-between gap-2.25 border-t border-line px-5.5 py-2.75 text-[10px] text-muted max-[540px]:px-4"
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

.catalog-table :deep(tbody th),
.catalog-table :deep(td) {
  padding: 14px 16px;
}

.catalog-table :deep(th):first-child {
  padding-left: 22px;
}

.catalog-table :deep(th):last-child,
.catalog-table :deep(td):last-child {
  padding-right: 22px;
}

</style>
