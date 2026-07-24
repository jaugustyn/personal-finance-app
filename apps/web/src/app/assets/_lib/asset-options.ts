import type {
  AssetAccountKind,
  AssetAccountWrapper,
  AssetCompounding,
  AssetInputMode,
  AssetType,
} from "@/lib/api";
import type { TranslationKey } from "@/lib/i18n";

export const ASSET_TYPES: readonly AssetType[] = [
  "cash",
  "savings_account",
  "deposit",
  "bond",
  "loan_receivable",
  "stock",
  "etf",
  "fund",
  "crypto",
  "precious_metal",
  "other",
];

interface AssetTypeCapabilities {
  defaultAccountKind: AssetAccountKind;
  defaultInputMode: AssetInputMode;
  supportsFixedGrowth: boolean;
  supportsInstrumentIdentifiers: boolean;
  supportsLinkedAccount: boolean;
}

const ASSET_TYPE_CAPABILITIES = {
  cash: {
    defaultAccountKind: "physical",
    defaultInputMode: "total",
    supportsFixedGrowth: false,
    supportsInstrumentIdentifiers: false,
    supportsLinkedAccount: false,
  },
  savings_account: {
    defaultAccountKind: "bank",
    defaultInputMode: "total",
    supportsFixedGrowth: true,
    supportsInstrumentIdentifiers: false,
    supportsLinkedAccount: true,
  },
  deposit: {
    defaultAccountKind: "bank",
    defaultInputMode: "total",
    supportsFixedGrowth: true,
    supportsInstrumentIdentifiers: false,
    supportsLinkedAccount: true,
  },
  bond: {
    defaultAccountKind: "brokerage",
    defaultInputMode: "unit_price",
    supportsFixedGrowth: false,
    supportsInstrumentIdentifiers: true,
    supportsLinkedAccount: true,
  },
  loan_receivable: {
    defaultAccountKind: "other",
    defaultInputMode: "total",
    supportsFixedGrowth: true,
    supportsInstrumentIdentifiers: false,
    supportsLinkedAccount: false,
  },
  stock: {
    defaultAccountKind: "brokerage",
    defaultInputMode: "unit_price",
    supportsFixedGrowth: false,
    supportsInstrumentIdentifiers: true,
    supportsLinkedAccount: true,
  },
  etf: {
    defaultAccountKind: "brokerage",
    defaultInputMode: "unit_price",
    supportsFixedGrowth: false,
    supportsInstrumentIdentifiers: true,
    supportsLinkedAccount: true,
  },
  fund: {
    defaultAccountKind: "brokerage",
    defaultInputMode: "unit_price",
    supportsFixedGrowth: false,
    supportsInstrumentIdentifiers: true,
    supportsLinkedAccount: true,
  },
  crypto: {
    defaultAccountKind: "crypto",
    defaultInputMode: "unit_price",
    supportsFixedGrowth: false,
    supportsInstrumentIdentifiers: false,
    supportsLinkedAccount: true,
  },
  precious_metal: {
    defaultAccountKind: "physical",
    defaultInputMode: "unit_price",
    supportsFixedGrowth: false,
    supportsInstrumentIdentifiers: false,
    supportsLinkedAccount: false,
  },
  other: {
    defaultAccountKind: "other",
    defaultInputMode: "total",
    supportsFixedGrowth: false,
    supportsInstrumentIdentifiers: false,
    supportsLinkedAccount: false,
  },
} as const satisfies Record<AssetType, AssetTypeCapabilities>;

export function assetTypeCapabilities(type: AssetType): AssetTypeCapabilities {
  return ASSET_TYPE_CAPABILITIES[type];
}

export const COMPOUNDING_MODES: readonly AssetCompounding[] = [
  "simple",
  "daily",
  "monthly",
  "yearly",
];

export const REVIEW_INTERVAL_OPTIONS = [
  { value: "7", key: "assets.review.7" },
  { value: "30", key: "assets.review.30" },
  { value: "90", key: "assets.review.90" },
  { value: "180", key: "assets.review.180" },
  { value: "never", key: "assets.review.never" },
] as const satisfies readonly { value: string; key: TranslationKey }[];

export function accountKindKey(value: AssetAccountKind): TranslationKey {
  return `assets.accountKind.${value}` as TranslationKey;
}

export function wrapperKey(value: AssetAccountWrapper): TranslationKey {
  return `assets.wrapper.${value}` as TranslationKey;
}

export function assetTypeKey(value: AssetType): TranslationKey {
  return `assets.type.${value}` as TranslationKey;
}

export function compoundingKey(value: AssetCompounding): TranslationKey {
  return `assets.compounding.${value}` as TranslationKey;
}
