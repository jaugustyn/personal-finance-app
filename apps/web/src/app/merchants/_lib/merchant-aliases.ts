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

export function groupAliases(aliases: MerchantAlias[]): MerchantAliasGroup[] {
  const groups = new Map<string, MerchantAliasGroup>();
  for (const alias of aliases) {
    const existing = groups.get(alias.canonical_key);
    if (existing) {
      existing.aliases.push(alias);
    } else {
      groups.set(alias.canonical_key, {
        canonical_key: alias.canonical_key,
        canonical_label: alias.canonical_label,
        aliases: [alias],
      });
    }
  }
  return Array.from(groups.values())
    .map((group) => ({
      ...group,
      aliases: [...group.aliases].sort((a, b) =>
        a.alias_label.localeCompare(b.alias_label, "pl", { sensitivity: "base" }),
      ),
    }))
    .sort((a, b) =>
      a.canonical_label.localeCompare(b.canonical_label, "pl", {
        sensitivity: "base",
      }),
    );
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
