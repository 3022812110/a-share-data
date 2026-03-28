export function numberText(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "--";
  return Number(value).toFixed(digits);
}

export function percentText(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "--";
  const num = Number(value);
  return `${num > 0 ? "+" : ""}${num.toFixed(2)}%`;
}

export function capText(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "--";
  return `${Number(value).toFixed(2)}亿`;
}

export function trillionText(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "--";
  return `${(Number(value) / 10000).toFixed(2)}万亿`;
}

export function colorStyle(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return undefined;
  const num = Number(value);
  if (num > 0) return { color: "#cf1322" };
  if (num < 0) return { color: "#389e0d" };
  return undefined;
}
