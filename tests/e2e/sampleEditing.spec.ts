import { test, expect } from './fixtures'
import { seededDatasetIds } from '../../src/data'

test('runs real sample edits, downloads the new CSV and resets edits on reload', async ({ page, api }) => {
  api.workspaceStatus = 503
  await page.goto(`?dataset=${seededDatasetIds.facilities}`)
  await expect(page.getByRole('heading', { name: 'County facilities', exact: true })).toBeVisible()
  const edit = page.getByRole('button', { name: /^Edit row / }).first()
  await edit.click()
  const dialog = page.getByRole('dialog', { name: 'Edit flagged cell' })
  await dialog.getByLabel('Replacement value', { exact: true }).fill('E2E-VERIFIED-001')
  await dialog.getByRole('button', { name: 'Save cell to new version' }).click()
  await expect(dialog).not.toBeVisible()
  await expect(page.getByText('New dataset version saved. Click Run Dataset Validation when you are ready.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Run Dataset Validation', exact: true })).toBeEnabled()
  const downloadEvent = page.waitForEvent('download')
  await page.getByRole('button', { name: /Download/ }).click()
  const download = await downloadEvent
  expect(download.suggestedFilename()).toMatch(/_v4\.csv$/)
  const stream = await download.createReadStream()
  const chunks: Buffer[] = []
  for await (const chunk of stream!) chunks.push(Buffer.from(chunk))
  expect(Buffer.concat(chunks).toString('utf8')).toContain('E2E-VERIFIED-001')
  await page.getByRole('button', { name: 'Run Dataset Validation', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Run Dataset Validation', exact: true })).toBeDisabled()
  expect(api.writes).toEqual([])
  await page.reload()
  await expect(page.getByRole('heading', { name: 'County facilities', exact: true })).toBeVisible()
  const originalEvent = page.waitForEvent('download')
  await page.getByRole('button', { name: /Download/ }).click()
  expect((await originalEvent).suggestedFilename()).toMatch(/_v3\.csv$/)
})

test('creates custom sample rules and validates a new version', async ({ page, api }) => {
  api.workspaceStatus = 503
  await page.goto(`?dataset=${seededDatasetIds.customers}`)
  await page.getByRole('button', { name: 'Edit quality rules', exact: true }).first().click()
  const dialog = page.getByRole('dialog', { name: /Quality rules/ })
  await dialog.getByRole('button', { name: 'Create custom ruleset' }).click()
  await dialog.getByRole('button', { name: 'Add rule' }).click()
  await dialog.getByRole('button', { name: 'Save rules', exact: true }).click()
  await expect(dialog).not.toBeVisible()
  await expect(page.getByRole('button', { name: 'Run Dataset Validation', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: 'Run Dataset Validation', exact: true }).click()
  await expect(page.getByText('v13 · Validation results saved.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Run Dataset Validation', exact: true })).toBeDisabled()
  expect(api.writes).toEqual([])
})
