// @vitest-environment jsdom
import { afterEach, beforeAll, describe, expect, it } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { nextTick } from 'vue'
import ModalShell from '@/components/ModalShell/ModalShell.vue'
import ConnectDatasetModal from '@/components/ConnectDatasetModal/ConnectDatasetModal.vue'
import QualityRulesModal from '@/components/QualityRulesModal/QualityRulesModal.vue'
import CellReviewDialog from '@/components/CellReviewFixes/CellReviewDialog.vue'
import DatasetTable from '@/components/DatasetTable/DatasetTable.vue'
import { seededRuleCatalog } from '@/data/qualityRules'
import { dataset, datasetId, group, rule, ruleset } from '../fixtures/workspace'

enableAutoUnmount(afterEach)
beforeAll(() => {
  // jsdom does not implement native dialog methods; real focus trapping,
  // Escape and top-layer behavior are exercised by Playwright.
  HTMLDialogElement.prototype.showModal = function () { this.open = true }
  HTMLDialogElement.prototype.close = function () { this.open = false }
})
afterEach(() => { document.body.innerHTML = '' })
const global = { stubs: { teleport: true } }

describe('modal shell', () => {
  it('opens a labelled dialog, emits dismissal and restores focus', async () => {
    const opener = document.createElement('button')
    document.body.append(opener)
    opener.focus()
    const wrapper = mount(ModalShell, { attachTo: document.body, props: { modelValue: false, title: 'Review' }, global })
    await wrapper.setProps({ modelValue: true })
    expect(wrapper.get('dialog').attributes('open')).toBeDefined()
    expect(document.getElementById(wrapper.get('dialog').attributes('aria-labelledby')!)?.textContent).toBe('Review')
    await wrapper.get('dialog').trigger('cancel')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([false])
    await wrapper.setProps({ modelValue: false })
    expect(document.activeElement).toBe(opener)
  })
  it('blocks dismissal during saves', async () => {
    const wrapper = mount(ModalShell, { props: { modelValue: true, title: 'Saving', dismissible: false }, global })
    await wrapper.get('dialog').trigger('cancel')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })
})

describe('upload dialog', () => {
  async function choose(wrapper: ReturnType<typeof mount>, files: File[]) {
    const input = wrapper.get('input[type=file]')
    Object.defineProperty(input.element, 'files', { configurable: true, value: files })
    await input.trigger('change')
  }
  it('rejects invalid and multiple files then emits a valid workbook selection', async () => {
    const wrapper = mount(ConnectDatasetModal, { props: { modelValue: true, uploadAvailable: true }, global })
    await choose(wrapper, [new File(['x'], 'bad.exe')])
    expect(wrapper.get('[role=alert]').text()).toContain('Choose')
    await choose(wrapper, [new File(['a'], 'a.csv'), new File(['b'], 'b.csv')])
    expect(wrapper.get('[role=alert]').text()).toContain('one dataset')
    const file = new File(['workbook'], 'data.xlsx')
    await choose(wrapper, [file])
    await wrapper.get('input[placeholder]').setValue('  Sheet 1  ')
    await wrapper.findAll('button').find(b => b.text() === 'Upload & validate')!.trigger('click')
    expect(wrapper.emitted('upload')?.[0]).toEqual([{ file, sheetName: 'Sheet 1' }])
  })
  it('disables submission in sample mode and while uploading', async () => {
    const wrapper = mount(ConnectDatasetModal, { props: { modelValue: true }, global })
    await choose(wrapper, [new File(['id'], 'data.csv')])
    expect(wrapper.findAll('button').find(b => b.text() === 'Upload & validate')!.attributes('disabled')).toBeDefined()
    await wrapper.setProps({ uploadAvailable: true, uploading: true })
    expect(wrapper.get('input[type=file]').attributes('disabled')).toBeDefined()
  })
})

describe('rules editor', () => {
  it('requires a custom copy, edits without mutating props and resets cancelled drafts', async () => {
    const original = dataset({ ruleset: ruleset([rule()], { kind: 'default' }) })
    const wrapper = mount(QualityRulesModal, { props: { modelValue: true, dataset: original, ruleCatalog: seededRuleCatalog, sourceKind: 'seeded' }, global })
    expect(wrapper.get('fieldset').attributes('disabled')).toBeDefined()
    await wrapper.findAll('button').find(b => b.text() === 'Create custom ruleset')!.trigger('click')
    await wrapper.get('input[type=checkbox]').setValue(false)
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('save')?.[0]?.[0]).toMatchObject({ kind: 'custom', rules: [expect.objectContaining({ enabled: false })] })
    expect(original.ruleset.rules[0]?.enabled).toBe(true)
    await wrapper.setProps({ modelValue: false })
    await wrapper.setProps({ modelValue: true })
    expect(wrapper.get('input[type=checkbox]').element).toHaveProperty('checked', true)
  })
  it('displays validation errors and does not emit an invalid save', async () => {
    const wrapper = mount(QualityRulesModal, { props: { modelValue: true, dataset: dataset(), ruleCatalog: seededRuleCatalog, sourceKind: 'api' }, global })
    await wrapper.get('select[aria-label="Type for rule 1"]').setValue('regex')
    await wrapper.get('input[aria-label="Condition for rule 1"]').setValue('(?=bad)')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.get('[role=alert]').text()).toContain('lookarounds')
    expect(wrapper.emitted('save')).toBeUndefined()
  })
})

describe('cell review dialog', () => {
  it('prevents unchanged or empty values and emits a version-scoped replacement', async () => {
    const wrapper = mount(CellReviewDialog, { props: { modelValue: true, dataset: dataset(), group: group({ currentValue: 'old' }), initialRow: 2, mode: 'edit' }, global })
    const save = () => wrapper.findAll('button').find(b => b.text() === 'Save cell to new version')!
    expect(save().attributes('disabled')).toBeDefined()
    await wrapper.get('input[type=text]').setValue('old')
    expect(save().attributes('disabled')).toBeDefined()
    await wrapper.get('input[type=text]').setValue('new')
    await save().trigger('click')
    expect(wrapper.emitted('save')?.[0]).toEqual([{ version: 'v1', groupId: 'missing-value', rowNumber: 2, scope: 'one', action: { type: 'replace', value: 'new' } }])
  })
  it('disables bulk replacement for unique columns but permits row deletion', async () => {
    const wrapper = mount(CellReviewDialog, { props: { modelValue: true, dataset: dataset({ ruleset: ruleset([rule({ type: 'unique' })]) }),
      group: group({ cells: [{ rowNumber: 1, identifier: 'A' }, { rowNumber: 2, identifier: 'B' }] }), initialRow: 1, mode: 'edit' }, global })
    await wrapper.get('input[type=text]').setValue('new')
    expect(wrapper.findAll('button').find(b => b.text() === 'Bulk replacement unavailable')!.attributes('disabled')).toBeDefined()
    await wrapper.get('input[value=remove]').setValue()
    await wrapper.findAll('button').find(b => b.text() === 'Delete all 2 matching rows')!.trigger('click')
    expect(wrapper.emitted('save')?.[0]?.[0]).toMatchObject({ scope: 'all', action: { type: 'delete-row' } })
  })
  it('emits an ignore action with the supplied reason', async () => {
    const wrapper = mount(CellReviewDialog, { props: { modelValue: true, dataset: dataset(), group: group(), initialRow: 2, mode: 'ignore' }, global })
    await wrapper.get('textarea').setValue('Verified with source')
    await wrapper.findAll('button').find(b => b.text() === 'Confirm ignore')!.trigger('click')
    expect(wrapper.emitted('save')?.[0]?.[0]).toMatchObject({ action: { type: 'ignore', reason: 'Verified with source' } })
  })
})

describe('dataset catalog', () => {
  it('filters name/source/filename and navigates by ID', async () => {
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', name: 'overview', component: { template: '<div />' } }] })
    await router.push('/')
    const wrapper = mount(DatasetTable, { props: { datasets: [dataset(), dataset({ id: 'second', name: 'Other', filename: 'other.xlsx' })], search: ' INVENTORY.CSV ' }, global: { plugins: [router] } })
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
    await wrapper.get('button[aria-label="Open overview for Test inventory"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.dataset).toBe(datasetId)
    await wrapper.get('button[aria-label="Edit quality rules for Test inventory"]').trigger('click')
    expect(wrapper.emitted('editQualityRules')?.[0]).toEqual([datasetId])
    await wrapper.setProps({ search: 'nothing' })
    expect(wrapper.text()).toContain('No datasets match your search.')
    await wrapper.setProps({ datasets: [] })
    expect(wrapper.text()).toContain('No datasets yet.')
    await nextTick()
  })
})
