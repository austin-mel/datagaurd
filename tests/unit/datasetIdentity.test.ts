import { expect, it } from 'vitest'
import { seededDatasetIds } from '@/data/datasetIds'
import { createSeededDatasetRepository } from '@/services/seededDatasetRepository'

it('uses stable UUID identities for all real demo datasets and downloads', async () => {
  const repository = createSeededDatasetRepository()
  const { datasets } = await repository.getWorkspace()
  expect(new Set(datasets.map(d => d.id)).size).toBe(3)
  expect(datasets.map(d => d.id).sort()).toEqual(Object.values(seededDatasetIds).sort())
  for (const dataset of datasets) {
    expect(dataset.id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
    expect((await repository.getDataset(dataset.id)).name).toBe(dataset.name)
    expect((await repository.download(dataset.id, dataset.version)).blob.size).toBeGreaterThan(0)
    await expect(repository.getDataset(dataset.name)).rejects.toThrow(/not found/)
  }
})

it('requires dataset IDs rather than sample-name aliases', async () => {
  const repository = createSeededDatasetRepository()
  for (const id of ['facilities', 'demo-facilities']) {
    await expect(repository.getDataset(id)).rejects.toThrow(/not found/)
  }
})
