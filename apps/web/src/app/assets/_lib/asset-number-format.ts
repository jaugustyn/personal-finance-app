export const ASSET_VALUE_DECIMAL_PLACES = 8;
export const ASSET_RATE_DECIMAL_PLACES = 4;

/**
 * Keep the precision returned by the API, but do not expose database padding
 * such as `12.50000000` in editable fields.
 */
export function compactAssetDecimal(
  value: number | string | null | undefined,
): string {
  if (value == null) return "";

  const raw = String(value).trim();
  if (!raw || !raw.includes(".")) return raw;

  return raw.replace(/(\.\d*?[1-9])0+$/, "$1").replace(/\.0+$/, "");
}

export function formatAssetDecimal(
  value: number | string,
  locale: string,
  maximumFractionDigits = ASSET_VALUE_DECIMAL_PLACES,
): string {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";

  return new Intl.NumberFormat(locale, {
    maximumFractionDigits,
  }).format(number);
}
