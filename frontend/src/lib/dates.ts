/**
 * Local-date helpers.
 *
 * `toISOString()` converts to UTC, so calling it on a Date that still carries a
 * local time-of-day silently shifts the calendar day -- west of UTC an evening
 * rolls forward to tomorrow. Every date the API sees is a plain calendar day,
 * so format from the local fields instead of going through UTC.
 */

export function fmtDate(d: Date): string {
  const month = `${d.getMonth() + 1}`.padStart(2, "0");
  const day = `${d.getDate()}`.padStart(2, "0");
  return `${d.getFullYear()}-${month}-${day}`;
}

export function startOfWeek(date: Date): Date {
  const d = new Date(date);
  d.setDate(d.getDate() - d.getDay());
  d.setHours(0, 0, 0, 0);
  return d;
}

export function addDays(date: Date, days: number): Date {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

export function weekDays(weekStart: Date): Date[] {
  return Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
}
