export function usd(value: string | number): string {
  return Number(value).toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export function day(value: string): string {
  return new Date(value).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export function dayTime(value: string): string {
  return new Date(value).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
}

export function monthName(value: string): string {
  return new Date(value).toLocaleDateString("en-GB", { month: "long", year: "numeric", timeZone: "UTC" });
}
