import type { DatasetRow } from '@/types'
import { seededDatasetIds } from './datasetIds'

// Fictional source values for the local repository, including the reference's defects.
const facilityScores = [85, 92, 74, 88, 96, 90, 78, 84, 91, 87, 93, 89, 80, 86, 95, 92, 88, -8, 108, 105]
const facilityDates = [
  '2026-09-01', '2026-09-02', '2026-09-03', '2026-09-04', '2026-09-05',
  '2026-09-06', '2026-09-07', '2026-09-08', '2026-09-09', '2026-09-10',
  '2026-09-11', '2026-09-12', '2026-09-13', '2026-09-14', '2026-09-02',
  '2026-09-03', '2026-09-04', '2026-09-05', '2026-10-09', '2026-10-12',
]
const facilities: readonly DatasetRow[] = facilityScores.map((score, index) => ({
  facility_id: index < 2 ? null : `FAC-${String(index === 4 ? 4 : index + 1).padStart(3, '0')}`,
  facility_name: index === 0 ? 'Bayview Clinic' : `County facility ${index + 1}`,
  county: index < 8 ? 'Sacramento' : index < 14 ? 'Alameda' : index < 18 ? 'Contra Costa' : 'San Francisco',
  facility_type: index < 10 ? 'Clinic' : index < 16 ? 'School' : 'Hospital',
  inspection_score: score,
  inspection_date: facilityDates[index] ?? null,
}))

const customerRowCount = 248512
const missingCustomerIds = 1243
const duplicateCustomerIds = 9643
const missingEmails = 2100
const otherCountries = [
  'Mexico', 'United Kingdom', 'France', 'Germany', 'Italy', 'Spain', 'Portugal',
  'Netherlands', 'Belgium', 'Sweden', 'Norway', 'Denmark', 'Finland', 'Ireland',
  'Switzerland', 'Austria', 'Poland', 'Australia', 'New Zealand', 'Japan',
  'South Korea', 'India', 'Singapore', 'Brazil', 'Argentina', 'South Africa',
] as const

// Generate the large fictional source on demand instead of shipping a large JSON file.
function* customers(): Generator<DatasetRow> {
  for (let index = 0; index < customerRowCount; index++) {
    const idIndex = index - missingCustomerIds
    const emailIndex = index - missingEmails
    yield {
      customer_id: idIndex < 0 ? null : idIndex < 3 ? 'CUS-001204'
        : idIndex < duplicateCustomerIds ? `CUS-DUP-${Math.floor((idIndex - 3) / 2)}` : `CUS-UNQ-${idIndex}`,
      customer_name: index < 12 ? 'Alex Lee'
        : index < 7214 ? `Customer group ${Math.floor((index - 12) / 2)}` : `Customer ${index}`,
      email: emailIndex < 0 ? null : emailIndex < 8 ? 'contact@example.com'
        : emailIndex < 3198 ? `group${Math.floor((emailIndex - 8) / 2)}@example.com`
          : emailIndex < 3898 ? `invalid-email-${emailIndex}` : `customer${emailIndex}@example.com`,
      country: index < 45 ? null : index < 176477 ? 'United States' : index < 207797 ? 'Canada'
        : otherCountries[(index - 207797) % otherCountries.length] ?? null,
    }
  }
}

const inventory: readonly DatasetRow[] = Array.from({ length: 12 }, (_, index) => ({
  product_id: `PRD-${String(index + 1).padStart(3, '0')}`,
  product_name: `Office supply ${index + 1}`,
  category: index % 2 ? 'Paper' : 'Equipment',
  quantity: index === 10 ? -3 : (index + 1) * 5,
  unit_price: index === 11 ? 9999 : (index + 1) * 2.5,
}))

export const seededRowCounts = { facilities: facilities.length, inventory: inventory.length, customers: customerRowCount }

export function getSeededDatasetRows(datasetId: string): Iterable<DatasetRow> {
  if (datasetId === seededDatasetIds.facilities) return facilities
  if (datasetId === seededDatasetIds.customers) return customers()
  if (datasetId === seededDatasetIds.inventory) return inventory
  throw new Error(`No seeded rows for dataset ${datasetId}`)
}
