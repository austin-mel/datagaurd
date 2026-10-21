import { test, expect, datasetId } from './fixtures'

const directLinks = [
  { path: 'datasets', title: 'Datasets', heading: 'Datasets' },
  {
    path: `overview?dataset=${datasetId}&filter=A%26B%2FC%3D1&filter=two+words&empty=#column-profile`,
    title: 'Overview',
    heading: 'Test inventory',
  },
]

for (const { path, title, heading } of directLinks) {
  test(`opens and reloads a direct ${title} link on GitHub Pages`, async ({ page, request, baseURL }) => {
    const destination = new URL(path, baseURL)
    const appRoot = new URL(baseURL!)
    const fallback = await request.get(new URL('404.html', appRoot).href)
    const fallbackHtml = await fallback.text()
    const rootResponses: number[] = []

    page.on('response', response => {
      if (response.request().isNavigationRequest() && new URL(response.url()).pathname === appRoot.pathname) {
        rootResponses.push(response.status())
      }
    })
    // Static hosting serves 404.html at the requested URL instead of Vite's SPA fallback.
    await page.route(url => url.pathname === destination.pathname, route => {
      if (!route.request().isNavigationRequest()) return route.continue()
      return route.fulfill({ status: 404, contentType: 'text/html', body: fallbackHtml })
    })

    await page.goto(destination.href)
    await expect(page).toHaveURL(destination.href)
    await expect(page).toHaveTitle(`Dataguard | ${title}`)
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible()
    expect(rootResponses).toEqual([200])

    rootResponses.length = 0
    await page.reload()
    await expect(page).toHaveURL(destination.href)
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible()
    expect(rootResponses).toEqual([200])

    const otherPage = title === 'Datasets' ? 'Overview' : 'Datasets'
    await page.getByRole('link', { name: otherPage, exact: true }).click()
    await expect(page).toHaveTitle(`Dataguard | ${otherPage}`)
    await page.goBack()
    await expect(page).toHaveURL(destination.href)
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible()
  })
}
