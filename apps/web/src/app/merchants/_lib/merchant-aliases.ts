import type {
  MerchantAlias,
  MerchantAliasGroup,
  MerchantCandidate,
  MerchantCandidateVariant,
} from "@/lib/api";

export const NEW_GROUP = "__new__";

export interface MerchantAliasPayload {
  canonical_label: string;
  canonical_key?: string | null;
  aliases: string[];
}

export function groupAliases(
  aliases: MerchantAlias[],
  compare: (left: string, right: string) => number,
): MerchantAliasGroup[] {
  const groups = new Map<string, MerchantAliasGroup>();
  for (const alias of aliases) {
    const existing = groups.get(alias.canonical_key);
    if (existing) {
      existing.aliases.push(alias);
      existing.total_expenses += Number(alias.total_expenses);
    } else {
      groups.set(alias.canonical_key, {
        canonical_key: alias.canonical_key,
        canonical_label: alias.canonical_label,
        aliases: [alias],
        total_expenses: Number(alias.total_expenses),
        base_currency: alias.base_currency,
      });
    }
  }
  return Array.from(groups.values())
    .map((group) => ({
      ...group,
      aliases: [...group.aliases].sort((a, b) =>
        compare(a.alias_label, b.alias_label),
      ),
    }))
    .sort((a, b) => compare(a.canonical_label, b.canonical_label));
}

export function candidateVariants(
  candidate: MerchantCandidate,
): MerchantCandidateVariant[] {
  if ((candidate.variants ?? []).length > 0) return candidate.variants;
  return candidate.aliases.map((alias) => ({
    alias_key: alias,
    alias_label: alias,
    count: 0,
    total_debit: 0,
    base_currency: candidate.base_currency,
  }));
}
