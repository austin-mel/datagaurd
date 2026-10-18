import { test, expect, datasetId } from './fixtures'
import { dataset } from '../fixtures/workspace'
import { seededDatasetIds } from '../../src/data/datasetIds'

test('opens live data, searches by filename and navigates by identity', async ({ page, api }) => {
  api.datasets.push(dataset({ id: 'other-id', name: 'Another inventory', filename: 'other.xlsx' }))
  await page.goto('/datasets')
  await expect(page).toHaveTitle('Dataguard | Datasets')
  await expect(page.getByText('Connected to backend · Live data')).toBeVisible()
  await page.getByRole('searchbox', { name: 'Search datasets' }).fill(' INVENTORY.CSV ')
  await expect(page.getByRole('button', { name: 'Open overview for Test inventory' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Open overview for Another inventory' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Open overview for Test inventory' }).click()
  await expect(page).toHaveURL(new RegExp(`dataset=${datasetId}`))
  await expect(page.getByRole('heading', { name: 'Test inventory', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Run Dataset Validation', exact: true })).toBeDisabled()
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Test inventory', exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Datasets', exact: true }).click()
  await page.getByRole('searchbox', { name: 'Search datasets' }).fill('no match')
  await expect(page.getByText('No datasets match your search.')).toBeVisible()
})

test('keeps an empty backend authoritative and handles unknown dataset links', async ({ page, api }) => {
  api.datasets = []
  await page.goto('/')
  await expect(page.getByText('No datasets are available yet.')).toBeVisible()
  await expect(page.getByText(/Sample data/)).toHaveCount(0)
  api.datasets = [dataset()]
  await page.goto('/?dataset=unknown')
  await expect(page.getByText('This dataset is no longer available. Choose another dataset to continue.')).toBeVisible()
  await page.getByRole('link', { name: 'View datasets' }).click()
  await expect(page.getByRole('button', { name: 'Open overview for Test inventory' })).toBeVisible()
})

test('surfaces authorization failures and recovers on retry', async ({ page, api }) => {
  api.workspaceStatus = 403
  await page.goto('/')
  await expect(page.getByRole('alert')).toContainText('Workspace access denied')
  await expect(page.getByText(/Sample data/)).toHaveCount(0)
  api.workspaceStatus = 200
  await page.getByRole('button', { name: 'Try again' }).click()
  await expect(page.getByRole('heading', { name: 'Test inventory', exact: true })).toBeVisible()
})

test('shows malformed response errors instead of silently using samples', async ({ page, api }) => {
  api.malformed = true
  await page.goto('/datasets')
  await expect(page.getByRole('alert')).toContainText('invalid workspace')
  await expect(page.getByText(/Sample data/)).toHaveCount(0)
})

test('falls back offline, migrates bookmarks and disables uploads', async ({ page, api }) => {
  api.workspaceStatus = 503
  await page.goto('/?dataset=demo-facilities')
  await expect(page).toHaveURL(new RegExp(`dataset=${seededDatasetIds.facilities}`))
  await expect(page.getByText(/Sample data · Backend unavailable/)).toBeVisible()
  await expect(page.getByRole('heading', { name: 'County facilities', exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Datasets', exact: true }).click()
  await expect(page.getByRole('button', { name: /Open overview for/ })).toHaveCount(3)
  await page.getByRole('button', { name: 'Connect a new data source' }).click()
  const dialog = page.getByRole('dialog', { name: 'Connect a data source' })
  await expect(dialog.getByText('Uploads are not available in this sample workspace.')).toBeVisible()
  await expect(dialog.getByRole('button', { name: 'Upload & validate' })).toBeDisabled()
  await page.keyboard.press('Escape')
  await expect(dialog).not.toBeVisible()
  expect(api.writes).toEqual([])
  api.workspaceStatus = 200
  await page.getByRole('button', { name: 'Reconnect (reload samples)' }).click()
  await expect(page.getByText('Connected to backend · Live data')).toBeVisible()
})

test('loads seeded examples when the workspace API is missing and reconnects', async ({ page }) => {
  const consoleErrors: string[] = []
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  await page.route('**/api/v1/workspace', route => route.fulfill({ status: 404, contentType: 'text/html', body: '<html>Not Found</html>' }))
  await page.goto('/datagaurd/')
  await expect(page.getByText(/Sample data · Backend unavailable/)).toBeVisible()
  expect(consoleErrors).toContain('Workspace API request failed (404): /api/v1/workspace')
  await expect(page.getByRole('heading', { name: 'County facilities', exact: true })).toBeVisible()
  await expect(page.getByRole('alert')).toHaveCount(0)
  await page.getByRole('link', { name: 'Datasets', exact: true }).click()
  await expect(page.getByRole('button', { name: /Open overview for/ })).toHaveCount(3)
  await page.unroute('**/api/v1/workspace')
  await page.getByRole('button', { name: 'Reconnect (reload samples)' }).click()
  await expect(page.getByText('Connected to backend · Live data')).toBeVisible()
})

test('persists recent selection across navigation and reloads', async ({ page, api }) => {
  api.datasets.push(dataset({ id: 'second', name: 'Second dataset' }))
  await page.goto('/datasets')
  await page.getByRole('button', { name: 'Open overview for Second dataset' }).click()
  await page.getByRole('link', { name: 'Datasets', exact: true }).click()
  await page.getByRole('link', { name: 'Overview', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Second dataset', exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Second dataset', exact: true })).toBeVisible()
})
