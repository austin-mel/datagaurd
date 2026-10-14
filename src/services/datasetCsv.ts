import type { DatasetRow, DatasetValue } from '@/types'

function csvCell(value: DatasetValue | undefined): string {
  return `"${String(value ?? '').replace(/"/g, '""')}"`
}

export function createDatasetCsv(columns: readonly string[], rows: Iterable<DatasetRow>): Blob {
  const lines = [columns.map(csvCell).join(',')]
  for (const row of rows) {
    lines.push(columns.map(column => csvCell(row[column])).join(','))
  }
  // Include a UTF-8 BOM so spreadsheet apps preserve non-ASCII source values.
  return new Blob(['\uFEFF', lines.join('\r\n'), '\r\n'], { type: 'text/csv;charset=utf-8' })
}
