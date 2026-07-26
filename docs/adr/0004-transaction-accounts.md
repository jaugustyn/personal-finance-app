# ADR-0004: Transactional Accounts as Operation Ownership

- **Status:** accepted
- **Date:** 2026-07-26

## Context

A bank or parser identifies where a record came from, but it does not identify
the user's logical account. The same parser can import several accounts, while
one multi-currency account can contain PLN, EUR and USD operations. Global
deduplication also incorrectly treats identical operations from two accounts as
the same record.

## Decision

1. Every import and transaction belongs to one transactional `Account`.
2. `account_id` answers “on which account did the operation occur?”.
3. `source` answers “where did this record come from?”. It remains provenance,
   not account identity.
4. One import contains operations from one logical account.
5. An account may contain multiple transaction currencies. Its stored currency
   is only a PLN default in this iteration.
6. Deduplication is scoped by `(account_id, dedup_hash)`.
7. Accounts are edited, archived and restored rather than deleted.
8. Transactions do not determine an account balance. Balance tracking is
   intentionally outside the current scope and will only be reconsidered if
   real usage justifies it.
9. Transactional `Account` and wealth-tracking `AssetAccount` remain separate.

## Consequences

Positive:

- imports and manual operations have explicit ownership;
- reimporting one account stays idempotent without merging another account;
- Revolut can remain one multi-currency account;
- account filtering has a stable, explicit foundation.

Negative:

- importing and manually adding a transaction requires an account choice;
- changing an import's account needs an atomic deduplication check;
- bank balances and wealth valuations are intentionally not derived from these
  records.

## Rejected alternatives

- **Use `source` as account identity:** one parser or bank can represent several
  logical accounts and a single account may receive records from different
  import formats.
- **Create one account per currency:** this misrepresents multi-currency accounts
  and adds unnecessary user work.
- **Merge with `AssetAccount`:** transaction ownership and approximate wealth
  valuation have different lifecycles and guarantees.
