<script setup lang="ts">
import { SVGIcons } from '@/assets'
import { RouterLink } from 'vue-router'
import {
  WorkspaceState,
  PageHeader,
  CellReviewFixes,
  ColumnProfileTable,
  DatasetHistoryCard,
  DatasetOverviewHeader,
  DatasetQualityCards,
  RecentDatasets,
  ValidationIssuesTable,
  DatasetValidationPanel,
  QualityRulesModal,
} from '@/components'
import { useOverviewDataset, useDatasetDownload, useDatasetActions } from '@/composables'

const { datasets, ruleCatalog, source, selectedDataset, recentDatasets, openDataset } = useOverviewDataset()
const { isDownloading, downloadError, downloadDataset } = useDatasetDownload(selectedDataset)
const { isRulesOpen, isSaving, saveError, saveMessage, openRules, saveRules, isRevalidating, validationError,
  isReviewSaving, reviewError, reviewMessage, validationPending, rerunValidation, saveCellReview } = useDatasetActions(selectedDataset)
</script>

<template>
  <PageHeader
    title="Overview"
    subtitle="Pick up where you left off. See what needs attention."
    class="mb-6.5"
  />
  <WorkspaceState>
    <RecentDatasets :entries="recentDatasets" :selected-id="selectedDataset?.id" @open="openDataset" />
    <template v-if="selectedDataset">
      <DatasetOverviewHeader :dataset="selectedDataset" :downloading="isDownloading" :saving-rules="isSaving || isReviewSaving" @download="downloadDataset" @edit-rules="openRules" />
      <p v-if="downloadError" class="mb-4.5 text-xs text-coral-text" role="alert">{{ downloadError }}</p>
      <DatasetQualityCards :dataset="selectedDataset" />
      <DatasetValidationPanel :dataset="selectedDataset" :pending="validationPending" :revalidating="isRevalidating"
        :saving="isSaving || isReviewSaving" :error="validationError" @run="rerunValidation" />
      <div class="grid min-w-0 gap-5.5">
        <div class="grid min-w-0 grid-cols-[minmax(0,1fr)_300px] gap-5.5 max-[1279px]:grid-cols-1">
          <ColumnProfileTable :profiles="selectedDataset.columnProfiles" :version="selectedDataset.version" />
          <div class="relative min-w-0">
            <DatasetHistoryCard :history="selectedDataset.history" class="absolute inset-0 max-[1279px]:relative max-[1279px]:max-h-112" />
          </div>
        </div>
        <ValidationIssuesTable :validation="selectedDataset.validation" :ruleset="selectedDataset.ruleset" :stale="validationPending" :total-rows="selectedDataset.rowCount" @edit-rules="openRules" />
        <CellReviewFixes :dataset="selectedDataset" :saving="isReviewSaving" :error="reviewError" @save="saveCellReview" />
      </div>
      <p v-if="reviewMessage" role="status" class="mt-3 text-xs text-green-text">{{ reviewMessage }}</p>
      <p role="status" class="mt-3 text-xs text-green-text">{{ saveMessage }}</p>
      <QualityRulesModal v-if="ruleCatalog && source" v-model="isRulesOpen" :dataset="selectedDataset" :rule-catalog="ruleCatalog" :source-kind="source.kind" :saving="isSaving" :save-error="saveError" @save="saveRules" />
    </template>
    <div v-else class="ui-panel p-5">
      <p class="mb-3 text-sm text-muted">{{ datasets.length ? 'This dataset is no longer available. Choose another dataset to continue.' : 'No datasets are available yet.' }}</p>
      <RouterLink :to="{ name: 'datasets' }" class="ui-button">View datasets <SVGIcons name="arrowForward" class="size-4" /></RouterLink>
    </div>
  </WorkspaceState>
</template>
