import {
  differenceInCalendarDays,
  format,
  isSameDay,
  isSameYear,
} from "date-fns";

/**
 * Messages that arrive closer together than this are treated as a single burst
 * and do not get their own time separator in the chat flow.
 */
export const TIME_SEPARATOR_THRESHOLD_MS = 5 * 60 * 1000; // 5 minutes

/**
 * Decide whether a friendly time separator should be shown before a message,
 * given the timestamp of the previously rendered message.
 *
 * Mirrors common IM behavior: hide the marker while messages come in quick
 * succession, and show it for the first message, after a pause, or when the
 * calendar day changes.
 */
export function shouldShowTimeSeparator(
  previous: Date | undefined | null,
  current: Date,
): boolean {
  if (!previous) return true;
  if (!isSameDay(previous, current)) return true;
  return current.getTime() - previous.getTime() >= TIME_SEPARATOR_THRESHOLD_MS;
}

/**
 * Human-friendly, IM-style label for a chat time separator, relative to `now`.
 * Examples: "Today 15:12", "Yesterday 09:30", "Mon 14:20", "Jan 5 10:00",
 * "Jan 5, 2025 10:00".
 */
export function formatFriendlyTime(date: Date, now: Date = new Date()): string {
  const time = format(date, "HH:mm");
  const days = differenceInCalendarDays(now, date);

  // `days <= 0` also covers future timestamps from minor client/server clock skew.
  if (days <= 0) return `Today ${time}`;
  if (days === 1) return `Yesterday ${time}`;
  if (days >= 2 && days < 7) return `${format(date, "EEE")} ${time}`;
  if (isSameYear(date, now)) return `${format(date, "MMM d")} ${time}`;
  return `${format(date, "MMM d, yyyy")} ${time}`;
}

/**
 * Precise timestamp shown on hover (via the title attribute) over a message
 * author. Example: "Jan 5, 2026 15:12:34".
 */
export function formatExactTime(date: Date): string {
  return format(date, "MMM d, yyyy HH:mm:ss");
}
