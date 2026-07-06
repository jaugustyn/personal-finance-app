import type { ImportPreview } from "@/lib/api";
import type { TranslationKey } from "@/lib/i18n";

export const LOGICAL_FIELDS = [
  { key: "date", required: true, recommended: false, description: "" },
  { key: "amount", required: true, recommended: false, description: "" },
  { key: "currency", required: false, recommended: false, description: "" },
  { key: "merchant", required: true, recommended: false, description: "" },
  { key: "title", required: false, recommended: true, description: "" },
  { key: "category", required: false, recommended: false, description: "" },
  { key: "external_id", required: false, recommended: false, description: "" },
] as const;

export type FieldKey = (typeof LOGICAL_FIELDS)[number]["key"];
export type FieldSpec = {
  key: FieldKey;
  required: boolean;
  recommended: boolean;
  description: string;
};

const LOGICAL_FIELD_KEYS = new Set<string>(LOGICAL_FIELDS.map((field) => field.key));

export function fieldSpecsFromPreview(preview: ImportPreview | null): FieldSpec[] {
  if (!preview?.field_specs?.length) return [...LOGICAL_FIELDS];
  return preview.field_specs
    .filter((spec) => LOGICAL_FIELD_KEYS.has(spec.key))
    .map((spec) => ({
      key: spec.key as FieldKey,
      required: spec.required,
      recommended: spec.recommended,
      description: spec.description,
    }));
}

export function buildCustomWarnings(
  mapping: Record<FieldKey, string>,
  t: (key: TranslationKey) => string,
) {
  const warnings: string[] = [];
  if (!mapping.currency) {
    warnings.push(t("imports.warning.currencyDefault"));
  }
  return Array.from(new Set(warnings));
}

export const fieldHintKey = (key: FieldKey): TranslationKey =>
  `imports.fieldHint.${key}` as TranslationKey;
