import { formatExactTime, formatFriendlyTime } from "@/lib/chatTime";

/**
 * Centered, muted time marker rendered between chat messages that are far apart
 * in time (IM-style). Hovering reveals the exact timestamp.
 */
export function ChatTimeSeparator({ date }: { date: Date }) {
  return (
    <div className="flex justify-center py-1">
      <time
        className="text-xs text-muted-foreground"
        dateTime={date.toISOString()}
        title={formatExactTime(date)}
      >
        {formatFriendlyTime(date)}
      </time>
    </div>
  );
}
