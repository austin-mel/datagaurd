const numberFormatter = new Intl.NumberFormat('en-US')
const scoreFormatter = new Intl.NumberFormat('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const timeZone = 'America/Los_Angeles'

export function formatNumber(value: number) { return numberFormatter.format(value) }
export function formatScore(value: number | null) { return value === null ? 'Not available' : scoreFormatter.format(value) }

export function formatValidatedAt(value: string | null, includeYear = true) {
  if (!value) return 'Not available'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Not yet validated'
  const day = new Intl.DateTimeFormat('en-US', { timeZone, month: 'short', day: 'numeric', ...(includeYear ? { year: 'numeric' as const } : {}) }).format(date)
  const time = new Intl.DateTimeFormat('en-US', { timeZone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(date)
  return `${day} · ${time}`
}

export function formatDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', month: 'short', day: 'numeric', year: 'numeric' }).format(date)
}

export function formatPacificDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : new Intl.DateTimeFormat('en-US', { timeZone, month: 'short', day: 'numeric', year: 'numeric' }).format(date)
}

export function formatPacificTime(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : new Intl.DateTimeFormat('en-US', { timeZone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(date)
}

export function formatOpenedAt(openedAt: number, now = Date.now()) {
  const minutes = Math.max(0, Math.floor((now - openedAt) / 60000))
  if (minutes === 0) return 'Opened just now'
  if (minutes < 60) return `Opened ${minutes} min ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `Opened ${hours} ${hours === 1 ? 'hour' : 'hours'} ago`
  const days = Math.floor(hours / 24)
  return days === 1 ? 'Opened yesterday' : `Opened ${days} days ago`
}
