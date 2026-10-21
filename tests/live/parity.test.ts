import { beforeAll, expect, it } from 'vitest'
import { createHttpDatasetRepository, createSeededDatasetRepository } from '@/services'
import type { DatasetWorkspace } from '@/types'

// Explicit opt-in: requires a running backend with unmodified demo datasets.
// This suite only reads workspace projections and downloads source files.
const api = createHttpDatasetRepository(process.env.API_URL || 'http://127.0.0.1:8000/api/v1')
let live: DatasetWorkspace, offline: DatasetWorkspace
beforeAll(async () => {
  const workspaces = await Promise.all([api.getWorkspace(), createSeededDatasetRepository().getWorkspace()])
  live = workspaces[0]
  offline = workspaces[1]
}, 30_000)

it('matches live demo projections and downloads to the sample workspace', async () => {
  for (const sample of offline.datasets) {
    const current = live.datasets.find(item => item.id === sample.id)
    expect(current, `Missing live demo: ${sample.id}`).toBeDefined()
    expect(current).toMatchObject({ rowCount: sample.rowCount, columns: sample.columns, quality: sample.quality })
    expect(current!.qualityDimensions.map(d => d.score)).toEqual(sample.qualityDimensions.map(d => d.score))
    expect(current!.validation?.issues).toHaveLength(sample.validation!.issues.length)
    expect(current!.cellReview).toHaveLength(sample.cellReview!.length)
    expect(current!.columnProfiles).toHaveLength(sample.columnProfiles!.length)
    for (const key of ['uploadedBy', 'uploadedAt', 'filename', 'downloadFilename', 'history'] as const) expect(current![key]).toBeTruthy()
    const download = await api.download(current!.id, current!.version)
    expect((await download.blob.text()).trim().split('\n')).toHaveLength(sample.rowCount + 1)
  }
})
