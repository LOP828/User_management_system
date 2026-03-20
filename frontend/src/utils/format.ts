import dayjs from "dayjs";

export function formatDateTime(value?: string | null) {
  if (!value) {
    return "-";
  }
  const parsed = dayjs(value);
  if (!parsed.isValid()) {
    return value;
  }
  return parsed.format("YYYY-MM-DD HH:mm");
}
