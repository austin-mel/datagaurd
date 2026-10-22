// @vitest-environment jsdom
import { afterEach, beforeAll, beforeEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import App from '../../src/App.vue'
import { OverviewView, DatasetsView } from '@/views'
import { useDatasetStore } from '@/stores'
import { defaultUploadPolicy } from '@/types'
import type { DatasetDataSource } from '@/types'
import type { DatasetRepository } from '@/services'
import { dataset, datasetId, workspace } from '../fixtures/workspace'

const repository = vi.hoisted(() => ({
  source: { kind: 'api' } as DatasetDataSource,
  getWorkspace: vi.fn<DatasetRepository['getWorkspace']>(),
  getDataset: vi.fn<DatasetRepository['getDataset']>(),
  download: vi.fn<DatasetRepository['download']>(),
  updateRuleset: vi.fn<DatasetRepository['updateRuleset']>(),
  revalidate: vi.fn<DatasetRepository['revalidate']>(),
  applyCellReview: vi.fn<DatasetRepository['applyCellReview']>(),
  getUploadPolicy: vi.fn<NonNullable<DatasetRepository['getUploadPolicy']>>(),
  upload: vi.fn<NonNullable<DatasetRepository['upload']>>(),
}))
vi.mock('@/services', async importOriginal => ({
  ...await importOriginal<typeof import('@/services')>(), datasetRepository: repository,
}))

enableAutoUnmount(afterEach)
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () { this.open = true }
  HTMLDialogElement.prototype.close = function () { this.open = false }
})
beforeEach(() => {
  vi.resetAllMocks()
  localStorage.clear()
  repository.source = { kind: 'api' }
  repository.getWorkspace.mockResolvedValue(workspace())
  repository.getDataset.mockResolvedValue(dataset())
  repository.getUploadPolicy.mockResolvedValue(defaultUploadPolicy)
  repository.revalidate.mockResolvedValue(dataset({ version: 'v2' }))
  repository.applyCellReview.mockResolvedValue(dataset({ version: 'v2', cellReview: [], reviewChangedSinceRun: true, validationPending: true }))
  repository.updateRuleset.mockImplementation(async (_id, ruleset) => dataset({ ruleset, rulesChangedSinceRun: true, validationPending: true }))
})
afterEach(() => { vi.useRealTimers(); document.body.innerHTML = '' })

async function open(path = '/') {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/', name: 'overview', component: OverviewView, meta: { title: 'Overview' } },
    { path: '/datasets', name: 'datasets', component: DatasetsView, meta: { title: 'Datasets' } },
  ] })
  await router.push(path)
  const pinia = createPinia()
  const wrapper = mount(App, { attachTo: document.body, global: { plugins: [pinia, router], stubs: { teleport: true } } })
  await flushPromises()
  return { wrapper, router, store: useDatasetStore(pinia) }
}
function button(wrapper: VueWrapper, text: string) {
  return wrapper.findAll('button').find(button => button.text() === text)!
}

it('shows loading and errors, retries, and preserves recent selection across views', async () => {
  let resolve!: (value: ReturnType<typeof workspace>) => void
  repository.getWorkspace.mockImplementationOnce(() => new Promise(done => { resolve = done }))
  const { wrapper, router } = await open()
  expect(wrapper.text()).toContain('Loading datasets…')
  resolve(workspace([dataset(), dataset({ id: 'second', name: 'Second dataset' })]))
  await flushPromises()
  expect(wrapper.text()).toContain('Viewing live data · Connected to backend.')
  await router.push('/?dataset=second')
  await router.push('/datasets')
  await router.push('/')
  await flushPromises()
  expect(wrapper.get('h2').text()).toBe('Recently opened')
  expect(wrapper.findAll('h2').some(heading => heading.text() === 'Second dataset')).toBe(true)
  await wrapper.findAll('button').find(button => button.find('strong').exists() && button.get('strong').text() === 'Test inventory')!.trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.query.dataset).toBe(datasetId)
  await router.push('/?dataset=missing')
  expect(wrapper.text()).toContain('This dataset is no longer available.')
})

it('retries a workspace failure without hiding it behind sample data', async () => {
  repository.getWorkspace.mockRejectedValueOnce(new Error('Access denied'))
  const { wrapper } = await open('/datasets')
  expect(wrapper.get('[role=alert]').text()).toContain('Access denied')
  await button(wrapper, 'Try again').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('Test inventory')
})

it('renders empty workspaces and source notices', async () => {
  repository.source = { kind: 'seeded', reason: 'backend-unavailable' }
  repository.getWorkspace.mockResolvedValue(workspace([]))
  const { wrapper, store } = await open()
  expect(wrapper.text()).toContain('No datasets are available yet.')
  expect(wrapper.text()).toContain('Backend unavailable.')
  expect(button(wrapper, 'Reconnect (reload samples)')).toBeDefined()
  store.source = { kind: 'seeded', reason: 'not-configured' }
  await flushPromises()
  expect(wrapper.text()).toContain('Demo mode enabled.')
})

it('saves a rules draft and validates only on an explicit request', async () => {
  const { wrapper, router } = await open('/datasets')
  await wrapper.get('button[aria-label="Edit quality rules for Test inventory"]').trigger('click')
  await wrapper.get('input[type=checkbox]').setValue(false)
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(repository.updateRuleset).toHaveBeenCalledWith(datasetId, expect.objectContaining({ rules: [expect.objectContaining({ enabled: false })] }))
  expect(repository.revalidate).not.toHaveBeenCalled()
  await router.push('/')
  await flushPromises()
  expect(wrapper.text()).toContain('Rules have changed since the displayed results.')
  await button(wrapper, 'Run Dataset Validation').trigger('click')
  await flushPromises()
  expect(repository.revalidate).toHaveBeenCalledWith(datasetId, 'v1')
  expect(button(wrapper, 'Run Dataset Validation').attributes('disabled')).toBeDefined()
})

it('retains failed cell edits and distinguishes saved edits from ignored findings', async () => {
  repository.applyCellReview.mockRejectedValueOnce(new Error('Version conflict'))
  const { wrapper, store } = await open()
  await wrapper.get('button[aria-label="Edit row 2, value"]').trigger('click')
  await wrapper.get('input[placeholder="Enter the verified replacement"]').setValue('25')
  await button(wrapper, 'Save cell to new version').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('Version conflict')
  expect(wrapper.get('input[placeholder="Enter the verified replacement"]').element).toHaveProperty('value', '25')
  await button(wrapper, 'Save cell to new version').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('New dataset version saved.')
  store.datasets = [dataset()]
  await flushPromises()
  await wrapper.get('button[aria-label="Ignore error for row 2, value"]').trigger('click')
  await button(wrapper, 'Confirm ignore').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('Finding ignored.')
})

it('reports validation failures and polls running validations until completion', async () => {
  vi.useFakeTimers()
  repository.getWorkspace.mockResolvedValue(workspace([dataset({ validationPending: true, processingStatus: 'running' })]))
  repository.getDataset.mockRejectedValueOnce(new Error('Offline')).mockResolvedValueOnce(dataset({ validationPending: true, processingStatus: 'failed', processingError: 'Check failed' }))
  const { wrapper } = await open()
  expect(wrapper.text()).toContain('Validation is running.')
  await vi.advanceTimersByTimeAsync(3000)
  await flushPromises()
  expect(wrapper.text()).toContain('Unable to refresh validation status. Retrying…')
  await vi.advanceTimersByTimeAsync(3000)
  await flushPromises()
  expect(wrapper.text()).toContain('Check failed')
  repository.revalidate.mockRejectedValueOnce(new Error('Unable to validate'))
  await button(wrapper, 'Run Dataset Validation').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('Unable to validate')
  const requests = repository.getDataset.mock.calls.length
  wrapper.unmount()
  await vi.advanceTimersByTimeAsync(6000)
  expect(repository.getDataset).toHaveBeenCalledTimes(requests)
})

it('downloads the selected immutable version and releases the browser URL', async () => {
  vi.useFakeTimers()
  vi.stubGlobal('URL', Object.assign(class extends URL {}, { createObjectURL: vi.fn(() => 'blob:test'), revokeObjectURL: vi.fn() }))
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  repository.download.mockResolvedValueOnce({ filename: 'original.csv', blob: new Blob(['source']) }).mockRejectedValueOnce(new Error('Offline'))
  const { wrapper, router } = await open()
  await button(wrapper, 'Download v1').trigger('click')
  await flushPromises()
  expect(repository.download).toHaveBeenCalledWith(datasetId, 'v1')
  expect(click).toHaveBeenCalledOnce()
  expect(document.querySelector('a[download]')).toBeNull()
  await vi.advanceTimersByTimeAsync(1000)
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:test')
  await button(wrapper, 'Download v1').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('Unable to download this dataset.')
  await router.push('/?dataset=missing')
  expect(wrapper.text()).not.toContain('Unable to download this dataset.')
})

it('loads upload policy, retains failed uploads, and adds the returned dataset', async () => {
  repository.getUploadPolicy.mockRejectedValueOnce(new Error('Policy unavailable'))
  repository.upload.mockRejectedValueOnce(new Error('Upload failed')).mockResolvedValueOnce(dataset({ id: 'uploaded', name: 'Uploaded inventory' }))
  const { wrapper } = await open('/datasets')
  await button(wrapper, 'Connect a new data source').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('Policy unavailable')
  await button(wrapper, 'Cancel').trigger('click')
  await button(wrapper, 'Connect a new data source').trigger('click')
  await flushPromises()
  const input = wrapper.get('input[type=file]')
  const file = new File(['id\nA'], 'upload.csv')
  Object.defineProperty(input.element, 'files', { configurable: true, value: [file] })
  await input.trigger('change')
  await button(wrapper, 'Upload & validate').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('Upload failed')
  await button(wrapper, 'Upload & validate').trigger('click')
  await flushPromises()
  expect(repository.upload).toHaveBeenCalledWith({ file, sheetName: undefined })
  expect(wrapper.text()).toContain('Uploaded inventory')
})
