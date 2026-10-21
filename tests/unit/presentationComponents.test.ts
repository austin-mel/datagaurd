// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import {
  ColumnProfileTable,
  DatasetQualityCards,
  DatasetHistoryCard,
  DatasetOverviewHeader,
  ValidationIssuesTable,
  RecentDatasets,
  CellReviewFixes,
  CellReviewDialog,
  PageHeader,
} from '@/components'
import { checkedAt, dataset, datasetId, group, ruleset } from '../fixtures/workspace'

enableAutoUnmount(afterEach)
afterEach(() => { vi.useRealTimers() })

it('renders profile summaries and distinguishes unavailable profiles', async () => {
  const wrapper = mount(ColumnProfileTable, { props: { version: 'v1', profiles: [
    ...dataset().columnProfiles!,
    { name: 'date', observedTypes: ['date'], missingCount: 0, warningCount: 1, uniqueCount: 2, summary: { kind: 'date-range', minimum: '2024-01-01', maximum: '2024-02-01' } },
    { name: 'category', observedTypes: ['text'], missingCount: 0, warningCount: null, uniqueCount: 1, summary: { kind: 'top-values', values: [{ value: 'A', count: 2 }] } },
  ] } })
  expect(wrapper.text()).toContain('3 columns profiled')
  expect(wrapper.text()).toContain('Jan 1, 2024 – Feb 1, 2024')
  expect(wrapper.text()).toContain('A · 2 occurrences')
  await wrapper.setProps({ profiles: null })
  expect(wrapper.text()).toContain('Column profile not available for this version.')
})

it('renders zero scores as measured and null scores as unavailable', async () => {
  const wrapper = mount(DatasetQualityCards, { props: { dataset: dataset({ quality: 0 }) } })
  expect(wrapper.text()).toContain('0.0/ 100')
  expect(wrapper.text()).toContain('1 / 2')
  await wrapper.setProps({ dataset: dataset({ quality: null, qualityDimensions: [{ id: 'empty', label: 'Unavailable', score: null, passed: null, total: null, description: 'No checks' }] }) })
  expect(wrapper.text()).toContain('Not available')
  expect(wrapper.text()).not.toContain('/ 100')
})

it('renders validation issue, stale, empty, zero-check and unavailable states', async () => {
  const wrapper = mount(ValidationIssuesTable, { props: { validation: dataset().validation, ruleset: ruleset(), totalRows: 2 } })
  expect(wrapper.text()).toContain('1 check failed across 1 column')
  await wrapper.get('button').trigger('click')
  expect(wrapper.emitted('editRules')).toEqual([[]])
  await wrapper.setProps({ validation: { checksRun: 1, issues: [] }, stale: true })
  expect(wrapper.text()).toContain('Changes are pending')
  await wrapper.setProps({ stale: false })
  expect(wrapper.text()).toContain('No validation issues found')
  await wrapper.setProps({ validation: { checksRun: 0, issues: [] } })
  expect(wrapper.text()).toContain('The last run had no enabled checks.')
  await wrapper.setProps({ validation: null })
  expect(wrapper.text()).toContain('Validation results not available.')
})

it('groups history by Pacific calendar day and handles no history', async () => {
  const wrapper = mount(DatasetHistoryCard, { props: { history: [
    { id: 'a', occurredAt: '2026-01-15T01:00:00Z', title: 'Dataset uploaded', description: 'First' },
    { id: 'b', occurredAt: '2026-01-15T02:00:00Z', title: 'Ruleset saved', description: 'Same day' },
    { id: 'c', occurredAt: '2026-01-15T12:00:00Z', title: 'Validation ran', description: 'Next day' },
  ] } })
  expect(wrapper.findAll('h3').map(h => h.text())).toEqual(['Jan 14, 2026', 'Jan 15, 2026'])
  expect(wrapper.findAll('time').map(t => t.text())).toEqual(['17:00', '18:00', '04:00'])
  await wrapper.setProps({ history: [] })
  expect(wrapper.text()).toContain('No history is available')
})

it('emits header actions and blocks them while busy', async () => {
  const wrapper = mount(DatasetOverviewHeader, { props: { dataset: dataset() } })
  await wrapper.findAll('button')[0]!.trigger('click')
  await wrapper.findAll('button')[1]!.trigger('click')
  expect(wrapper.emitted('edit-rules')).toEqual([[]])
  expect(wrapper.emitted('download')).toEqual([[]])
  await wrapper.setProps({ savingRules: true, downloading: true, dataset: dataset({ lastValidatedAt: null, status: 'failed', filename: undefined }) })
  expect(wrapper.findAll('button').every(b => b.attributes('disabled') !== undefined)).toBe(true)
  expect(wrapper.text()).toContain('Validation failed')
  expect(wrapper.text()).toContain('Not available')
})

it('updates recent timestamps and clears the timer on unmount', async () => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date(checkedAt))
  const wrapper = mount(RecentDatasets, { props: { entries: [{ dataset: dataset(), openedAt: Date.now() }], selectedId: datasetId }, global: { stubs: { RouterLink: true } } })
  expect(wrapper.text()).toContain('Opened just now')
  expect(wrapper.get('button').attributes('aria-pressed')).toBe('true')
  await wrapper.get('button').trigger('click')
  expect(wrapper.emitted('open')?.[0]).toEqual([datasetId])
  await vi.advanceTimersByTimeAsync(60_000)
  await nextTick()
  expect(wrapper.text()).toContain('Opened 1 min ago')
  await wrapper.setProps({ entries: [] })
  expect(wrapper.text()).toContain('Datasets you open will appear here.')
  wrapper.unmount()
  expect(vi.getTimerCount()).toBe(0)
})

it('paginates groups and cells, filters review findings and resets on a new version', async () => {
  const groups = Array.from({ length: 12 }, (_, index) => group({ id: String(index), column: index === 11 ? 'other' : 'value', kind: index === 11 ? 'warning' : 'violation',
    cells: Array.from({ length: index === 0 ? 12 : 1 }, (_, row) => ({ rowNumber: row + 1, identifier: 'ID' })) }))
  const wrapper = mount(CellReviewFixes, { props: { dataset: dataset({ cellReview: groups }) }, global: { stubs: { CellReviewDialog: true } } })
  const button = (text: string) => wrapper.findAll('button').find(b => b.text() === text)!
  expect(wrapper.findAll('details')).toHaveLength(10)
  await button('Next cells').trigger('click')
  expect(wrapper.findAll('details')[0]!.text()).toContain('Cells 11–12 of 12')
  await button('Next 10 groups').trigger('click')
  await button('Previous').trigger('click')
  expect(wrapper.findAll('details')[0]!.text()).toContain('Cells 11–12 of 12')
  await button('Previous cells').trigger('click')
  await button('Next 10 groups').trigger('click')
  expect(wrapper.findAll('details')).toHaveLength(2)
  await wrapper.get('input[type=search]').setValue('other')
  expect(wrapper.findAll('details')).toHaveLength(1)
  expect(wrapper.text()).toContain('Groups 1–1 of 1')
  await wrapper.get('button[aria-label="Edit row 1, other"]').trigger('click')
  const dialog = wrapper.getComponent(CellReviewDialog)
  expect(dialog.props()).toMatchObject({ initialRow: 1, mode: 'edit', modelValue: true })
  const request = { version: 'v1', groupId: '11', rowNumber: 1, scope: 'one', action: { type: 'delete-row' } }
  dialog.vm.$emit('save', request)
  expect(wrapper.emitted('save')?.[0]).toEqual([request])
  await wrapper.setProps({ dataset: dataset({ version: 'v2', cellReview: [] }) })
  expect(wrapper.text()).toContain('No flagged cells in this version.')
  expect(wrapper.findComponent(CellReviewDialog).exists()).toBe(false)
  await wrapper.setProps({ dataset: dataset({ cellReview: null }) })
  expect(wrapper.text()).toContain('Cell review is not available')
})

it('renders the page heading and action slot', () => {
  const wrapper = mount(PageHeader, { props: { title: 'Datasets', subtitle: 'Browse sources' }, slots: { actions: '<button>Upload</button>' } })
  expect(wrapper.get('h1').text()).toBe('Datasets')
  expect(wrapper.get('button').text()).toBe('Upload')
})
