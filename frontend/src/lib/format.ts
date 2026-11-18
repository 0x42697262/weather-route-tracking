import { DISPLAY_LOCALE, MINUTES_PER_HOUR, MS_PER_HOUR, SECONDS_PER_MINUTE } from "@/constants";
import { durationText } from "@/text";

const DATE_PART_LENGTH = 2;
const DATE_PART_PAD = "0";

const timeFormatter = new Intl.DateTimeFormat(DISPLAY_LOCALE, {
  hour: "numeric",
  minute: "2-digit",
  timeZoneName: "short",
});

const dateTimeFormatter = new Intl.DateTimeFormat(DISPLAY_LOCALE, {
  weekday: "short",
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
  timeZoneName: "short",
});

export function formatTime(isoUtc: string): string {
  return timeFormatter.format(new Date(isoUtc));
}

export function formatDateTime(isoUtc: string): string {
  return dateTimeFormatter.format(new Date(isoUtc));
}

export function addHoursUtc(isoUtc: string, hours: number): string {
  return new Date(new Date(isoUtc).getTime() + hours * MS_PER_HOUR).toISOString();
}

export function formatHourFromStart(startTimeUtc: string, hour: number): string {
  return formatDateTime(addHoursUtc(startTimeUtc, hour));
}

export function formatDurationS(durationS: number): string {
  const totalMinutes = Math.round(durationS / SECONDS_PER_MINUTE);
  const hours = Math.floor(totalMinutes / MINUTES_PER_HOUR);
  const minutes = totalMinutes % MINUTES_PER_HOUR;
  return hours > 0 ? durationText.hoursAndMinutes(hours, minutes) : durationText.minutesOnly(minutes);
}

function padDatePart(value: number): string {
  return String(value).padStart(DATE_PART_LENGTH, DATE_PART_PAD);
}

export function toDateTimeInputValue(isoUtc: string): string {
  const date = new Date(isoUtc);
  const day = [date.getFullYear(), padDatePart(date.getMonth() + 1), padDatePart(date.getDate())];
  const time = [padDatePart(date.getHours()), padDatePart(date.getMinutes())];
  return `${day.join("-")}T${time.join(":")}`;
}

export function fromDateTimeInputValue(inputValue: string): string | null {
  const date = new Date(inputValue);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

const ZONE_NAME_PART = "timeZoneName";

export function formatZoneName(isoUtc: string): string {
  return timeFormatter.formatToParts(new Date(isoUtc)).find((part) => part.type === ZONE_NAME_PART)?.value ?? "";
}
