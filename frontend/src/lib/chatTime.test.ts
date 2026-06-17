import { describe, expect, it } from "vitest";

import {
  TIME_SEPARATOR_THRESHOLD_MS,
  formatExactTime,
  formatFriendlyTime,
  shouldShowTimeSeparator,
} from "./chatTime";

describe("shouldShowTimeSeparator", () => {
  it("always shows for the first message (no previous)", () => {
    expect(shouldShowTimeSeparator(undefined, new Date())).toBe(true);
    expect(shouldShowTimeSeparator(null, new Date())).toBe(true);
  });

  it("hides while messages stay within the threshold on the same day", () => {
    const prev = new Date(2026, 5, 17, 10, 0, 0);
    const curr = new Date(2026, 5, 17, 10, 4, 0); // 4 minutes later
    expect(shouldShowTimeSeparator(prev, curr)).toBe(false);
  });

  it("shows once the gap reaches the threshold", () => {
    const prev = new Date(2026, 5, 17, 10, 0, 0);
    const exactly = new Date(prev.getTime() + TIME_SEPARATOR_THRESHOLD_MS);
    const beyond = new Date(2026, 5, 17, 10, 6, 0);
    expect(shouldShowTimeSeparator(prev, exactly)).toBe(true);
    expect(shouldShowTimeSeparator(prev, beyond)).toBe(true);
  });

  it("hides just below the threshold", () => {
    const prev = new Date(2026, 5, 17, 10, 0, 0);
    const justBelow = new Date(prev.getTime() + TIME_SEPARATOR_THRESHOLD_MS - 1);
    expect(shouldShowTimeSeparator(prev, justBelow)).toBe(false);
  });

  it("shows when the calendar day changes even within the threshold", () => {
    const prev = new Date(2026, 5, 16, 23, 59, 0);
    const curr = new Date(2026, 5, 17, 0, 1, 0); // 2 minutes later, next day
    expect(shouldShowTimeSeparator(prev, curr)).toBe(true);
  });
});

describe("formatFriendlyTime", () => {
  const now = new Date(2026, 5, 17, 10, 0, 0); // Wed Jun 17, 2026

  it("labels today", () => {
    expect(formatFriendlyTime(new Date(2026, 5, 17, 9, 30, 0), now)).toBe(
      "Today 09:30",
    );
  });

  it("labels yesterday", () => {
    expect(formatFriendlyTime(new Date(2026, 5, 16, 15, 12, 0), now)).toBe(
      "Yesterday 15:12",
    );
  });

  it("labels future timestamps (clock skew) as today", () => {
    expect(formatFriendlyTime(new Date(2026, 5, 18, 9, 0, 0), now)).toBe(
      "Today 09:00",
    );
  });

  it("uses month format at the 7-day boundary", () => {
    expect(formatFriendlyTime(new Date(2026, 5, 10, 10, 0, 0), now)).toBe(
      "Jun 10 10:00",
    );
  });

  it("labels recent days within the past week by weekday", () => {
    const result = formatFriendlyTime(new Date(2026, 5, 14, 14, 20, 0), now);
    expect(result).toMatch(/^(Mon|Tue|Wed|Thu|Fri|Sat|Sun) 14:20$/);
  });

  it("labels older dates in the same year without the year", () => {
    expect(formatFriendlyTime(new Date(2026, 2, 3, 10, 0, 0), now)).toBe(
      "Mar 3 10:00",
    );
  });

  it("includes the year for dates in a previous year", () => {
    expect(formatFriendlyTime(new Date(2025, 11, 25, 18, 45, 0), now)).toBe(
      "Dec 25, 2025 18:45",
    );
  });
});

describe("formatExactTime", () => {
  it("renders a precise timestamp", () => {
    expect(formatExactTime(new Date(2026, 0, 5, 15, 12, 34))).toBe(
      "Jan 5, 2026 15:12:34",
    );
  });
});
