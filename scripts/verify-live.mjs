import assert from 'node:assert/strict'
import { createHttpDatasetRepository } from '../src/services/httpDatasetRepository.ts'
import { createSeededDatasetRepository } from '../src/services/seededDatasetRepository.ts'

const api = createHttpDatasetRepository(process.env.API_URL || 'http://127.0.0.1:5173/api/v1')
const live = await api.getWorkspace()
const offline = await createSeededDatasetRepository().getWorkspace()
for (const sample of offline.datasets) {
  const dataset = live.datasets.find(item => item.id === sample.id)
  assert.ok(dataset, 'Missing live demo: ' + sample.id)
  assert.equal(dataset.rowCount, sample.rowCount)
  assert.deepEqual(dataset.columns, sample.columns)
  assert.equal(dataset.quality, sample.quality)
  assert.deepEqual(dataset.qualityDimensions.map(d => d.score), sample.qualityDimensions.map(d => d.score))
  assert.equal(dataset.validation.issues.length, sample.validation.issues.length)
  assert.equal(dataset.cellReview.length, sample.cellReview.length)
  assert.equal(dataset.columnProfiles.length, sample.columnProfiles.length)
  assert.ok(dataset.uploadedBy && dataset.uploadedAt && dataset.filename && dataset.downloadFilename && dataset.history.length)
  const download = await api.download(dataset.id, dataset.version)
  assert.equal((await download.blob.text()).trim().split('\n').length, sample.rowCount + 1)
}
console.log(JSON.stringify({ liveDatasets: live.datasets.length, demoParity: 'passed', rows: offline.datasets.map(d => d.rowCount) }, null, 2))
