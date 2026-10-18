import { readFile } from 'node:fs/promises'
import { test, expect, datasetId } from './fixtures'

test('uploads a CSV and displays the returned dataset', async ({ page, api }) => {
  await page.goto('/datasets')
  const opener = page.getByRole('button', { name: 'Connect a new data source' })
  await opener.click()
  const dialog = page.getByRole('dialog', { name: 'Connect a data source' })
  await dialog.getByLabel('Dataset file', { exact: true }).setInputFiles({ name: 'bad.exe', mimeType: 'application/octet-stream', buffer: Buffer.from('bad') })
  await expect(dialog.getByRole('alert')).toContainText('Choose')
  await expect(dialog.getByRole('button', { name: 'Upload & validate' })).toBeDisabled()
  await dialog.getByLabel('Dataset file', { exact: true }).setInputFiles({ name: 'upload.csv', mimeType: 'text/csv', buffer: Buffer.from('id,value\nA,1') })
  await dialog.getByRole('button', { name: 'Upload & validate' }).click()
  await expect(dialog).not.toBeVisible()
  await expect(page.getByRole('button', { name: 'Open overview for Uploaded inventory' })).toBeVisible()
  expect(api.writes[0]).toMatchObject({ method: 'POST', path: '/api/v1/datasets' })
  expect(api.writes[0]?.body).toContain('filename="upload.csv"')
  // WebKit's intercepted multipart body omits file bytes. The HTTP repository
  // unit test verifies those bytes; here assert the submitted file identity.
})

test('shows upload failures without losing the chosen file', async ({ page, api }) => {
  api.failWrites = true
  await page.goto('/datasets')
  await page.getByRole('button', { name: 'Connect a new data source' }).click()
  const dialog = page.getByRole('dialog', { name: 'Connect a data source' })
  await dialog.getByLabel('Dataset file', { exact: true }).setInputFiles({ name: 'upload.csv', mimeType: 'text/csv', buffer: Buffer.from('id\nA') })
  await dialog.getByRole('button', { name: 'Upload & validate' }).click()
  await expect(dialog.getByRole('alert')).toContainText('Version conflict')
  await expect(dialog.getByText('upload.csv', { exact: true })).toBeVisible()
  api.failWrites = false
  await dialog.getByRole('button', { name: 'Upload & validate' }).click()
  await expect(dialog).not.toBeVisible()
})

test('downloads exact source bytes and reports download errors', async ({ page, api }) => {
  await page.goto('/')
  const pending = page.waitForEvent('download')
  await page.getByRole('button', { name: /Download/ }).click()
  const download = await pending
  expect(download.suggestedFilename()).toBe('inventory_v1.csv')
  expect(await readFile((await download.path())!, 'utf8')).toBe('id,value\r\nA,10\r\nB,\r\n')
  api.failDownload = true
  await page.getByRole('button', { name: /Download/ }).click()
  await expect(page.getByRole('alert')).toContainText('Unable to download')
})

test('saves edited rules and requires explicit revalidation', async ({ page, api }) => {
  await page.goto('/datasets')
  await page.getByRole('button', { name: 'Edit quality rules for Test inventory' }).click()
  const dialog = page.getByRole('dialog', { name: 'Quality rules · Test inventory' })
  await dialog.getByRole('button', { name: 'Add rule' }).click()
  await dialog.getByLabel('Column for rule 2', { exact: true }).selectOption('value')
  await dialog.getByLabel('Type for rule 2', { exact: true }).selectOption('min')
  await dialog.getByLabel('Minimum for rule 2', { exact: true }).fill('5')
  await dialog.getByRole('button', { name: 'Save rules', exact: true }).click()
  await expect(dialog).not.toBeVisible()
  expect(api.writes).toHaveLength(1)
  expect(JSON.parse(api.writes[0]!.body).rules[1]).toMatchObject({ column: 'value', type: 'min', minimum: 5 })
  await page.getByRole('button', { name: 'Open overview for Test inventory' }).click()
  await expect(page.getByText('Rules have changed since the displayed results. Re-run validation to apply them.')).toBeVisible()
  await page.getByRole('button', { name: 'Run Dataset Validation', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Run Dataset Validation', exact: true })).toBeDisabled()
  await expect(page.getByText('v2 · Validation results saved.')).toBeVisible()
  expect(api.writes[1]).toMatchObject({ path: `/api/v1/datasets/${datasetId}/validation`, body: '{"version":"v1"}' })
})

test('retains a rules draft after a failed save and restores focus on Escape', async ({ page, api }) => {
  api.failWrites = true
  await page.goto('/datasets')
  const opener = page.getByRole('button', { name: 'Edit quality rules for Test inventory' })
  // Safari does not focus buttons on mouse clicks. Open from the keyboard to
  // exercise the modal's return-to-previous-focus contract in every browser.
  await opener.focus()
  await opener.press('Enter')
  const dialog = page.getByRole('dialog', { name: 'Quality rules · Test inventory' })
  await dialog.getByLabel('Enable rule 1: value', { exact: true }).uncheck()
  await dialog.getByRole('button', { name: 'Save rules', exact: true }).click()
  await expect(dialog.getByRole('alert')).toContainText('Your changes are still here')
  await expect(dialog.getByLabel('Enable rule 1: value', { exact: true })).not.toBeChecked()
  await page.keyboard.press('Escape')
  await expect(dialog).not.toBeVisible()
  await expect(opener).toBeFocused()
  await opener.click()
  await expect(dialog.getByLabel('Enable rule 1: value', { exact: true })).toBeChecked()
})

test('corrects a cell into a new version then validates it', async ({ page, api }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Edit row 2, value', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Edit flagged cell' })
  await expect(dialog.getByRole('button', { name: 'Save cell to new version' })).toBeDisabled()
  await dialog.getByLabel('Replacement value', { exact: true }).fill('25')
  await dialog.getByRole('button', { name: 'Save cell to new version' }).click()
  await expect(dialog).not.toBeVisible()
  await expect(page.getByText('New dataset version saved. Click Run Dataset Validation when you are ready.')).toBeVisible()
  expect(JSON.parse(api.writes[0]!.body)).toEqual({ version: 'v1', groupId: 'missing-value', rowNumber: 2, scope: 'one', action: { type: 'replace', value: '25' } })
  await page.getByRole('button', { name: 'Run Dataset Validation', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Run Dataset Validation', exact: true })).toBeDisabled()
  expect(JSON.parse(api.writes[1]!.body)).toEqual({ version: 'v2' })
  await page.reload()
  await expect(page.getByRole('button', { name: 'Edit row 2, value', exact: true })).toHaveCount(0)
})

test('ignores a finding with a reason without changing the version', async ({ page, api }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Ignore error for row 2, value', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Ignore rule error' })
  await dialog.getByLabel('Reason for ignoring').fill('Verified against the original')
  await dialog.getByRole('button', { name: 'Confirm ignore' }).click()
  await expect(dialog).not.toBeVisible()
  expect(JSON.parse(api.writes[0]!.body).action).toEqual({ type: 'ignore', reason: 'Verified against the original' })
  expect(api.datasets[0]?.version).toBe('v1')
  await expect(page.getByRole('button', { name: 'Run Dataset Validation', exact: true })).toBeEnabled()
})

test('deletes a flagged row and preserves failed-edit drafts', async ({ page, api }) => {
  api.failWrites = true
  await page.goto('/')
  await page.getByRole('button', { name: 'Edit row 2, value', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Edit flagged cell' })
  await dialog.getByRole('radio', { name: /Remove entire row/ }).check()
  await dialog.getByRole('button', { name: 'Delete row & save version' }).click()
  await expect(dialog.getByRole('alert')).toContainText('Version conflict')
  api.failWrites = false
  await dialog.getByRole('button', { name: 'Delete row & save version' }).click()
  await expect(dialog).not.toBeVisible()
  expect(api.datasets[0]?.rowCount).toBe(1)
  expect(JSON.parse(api.writes[1]!.body).action).toEqual({ type: 'delete-row' })
})
