const relativeFormat = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })

const MINUTE_SECONDS = 60
const HOUR_SECONDS = 3600
const DAY_SECONDS = 86400
const WEEK_SECONDS = 604800
const MONTH_SECONDS = 2592000

export function humanizeRelativeTime(value: string): string {
  const normalized = value.includes('T') ? value : value.replace(' ', 'T')
  const timeMs = Date.parse(normalized)
  if (Number.isNaN(timeMs)) {
    return value
  }
  const diffSeconds = Math.round((timeMs - Date.now()) / 1000)
  const absSeconds = Math.abs(diffSeconds)
  if (absSeconds < MINUTE_SECONDS) {
    return relativeFormat.format(diffSeconds, 'second')
  }
  if (absSeconds < HOUR_SECONDS) {
    return relativeFormat.format(Math.round(diffSeconds / MINUTE_SECONDS), 'minute')
  }
  if (absSeconds < DAY_SECONDS) {
    return relativeFormat.format(Math.round(diffSeconds / HOUR_SECONDS), 'hour')
  }
  if (absSeconds < WEEK_SECONDS) {
    return relativeFormat.format(Math.round(diffSeconds / DAY_SECONDS), 'day')
  }
  if (absSeconds < MONTH_SECONDS) {
    return relativeFormat.format(Math.round(diffSeconds / WEEK_SECONDS), 'week')
  }
  return new Date(timeMs).toLocaleString()
}
