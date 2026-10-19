const dateTimeFormatter = new Intl.DateTimeFormat('pl-PL', {
  dateStyle: 'medium',
  timeStyle: 'short',
})

export function formatDateTime(value: string) {
  return dateTimeFormatter.format(new Date(value))
}
