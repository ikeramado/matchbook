# Brief

The pitch for matchbook's second version, following the structure of a
[Shape Up pitch](https://basecamp.com/shapeup/1.5-chapter-06): problem, appetite, solution,
rabbit holes and no-gos. It builds on the first version (same log, same checks C1 to C11),
whose brief is in git history. The checkable conditions live in [CRITERIA.md](CRITERIA.md).

## Problem

Before paying a supplier, accounts payable teams confirm that the purchase order, the goods
receipt and the invoice line up under the item's matching rule. The first version checks
this on the BPI Challenge 2019 log and documents how. It does not tell a client what they
need in two minutes: how much money the exceptions involve, which ones to look at first,
whether the checks find the faults they claim to find, and what they gain over the simple
match their team already does in a spreadsheet.

## Appetite

One week, on top of the first version, not a rewrite.

## Solution

Four parts, one slice each, in this order.

### 1. Money at stake

Each finding of C1 to C4 and C6 carries the euros at stake and a severity.

- **Euros at stake.** C1: the value of the invoice receipt found with no goods receipt in
  force. C2 and C3: the value of the `Clear Invoice` found with no receipt in force. C4:
  the value of the first event in the finding's evidence (a consignment item holds one
  value on every event, CRITERIA.md). C6: the absolute net difference it prints.
- **Severity.** High at 10,000 EUR or more, medium from 1,000 EUR, low below. A finding
  with the reversal note of C2 and C3 goes one level lower (high to medium, medium to low).
  C7 findings and `C6 not checked` items are data quality, not exceptions: they carry
  neither.

On the full log this gives 69 high, 286 medium and 666 low findings out of 1,021:

| Criterion | High | Medium | Low |
|---|---:|---:|---:|
| C2 | 19 | 140 | 576 |
| C3 | 0 | 7 | 3 |
| C6 | 50 | 139 | 87 |

### 2. Known truth

matchbook copies the log in memory and injects faults of known kind into the copy; nothing
is written anywhere (C10). Each fault goes into an item that neither matchbook nor the
baseline (part 3) flags on the original log, chosen with a seeded random generator from
the items it applies to, so the same seed gives the same injected log. Every kind is
injected into 50 items, each item at most once. An event added "one second after" another
has its timestamp plus one second and its place right after it in log order.

Faults, each with the criterion that must flag it:

| Kind | Criterion | Applied to | Change |
|---|---|---|---|
| F1 | C1 | closed *invoice after GR* goods item (no `Record Service Entry Sheet`) whose first `Record Invoice Receipt` comes after its first `Record Goods Receipt` | that invoice receipt moves to one second before the first goods receipt |
| F2 | C2 | closed *invoice before GR* item | every `Record Goods Receipt` and `Cancel Goods Receipt` is removed |
| F3 | C2 | closed *invoice before GR* item with exactly one `Record Goods Receipt`, before its first `Clear Invoice` | a `Cancel Goods Receipt` of the same value is added one second after the receipt |
| F4 | C3 | closed *2-way match* item | every `Record Invoice Receipt` and `Cancel Invoice Receipt` is removed |
| F5 | C4 | *Consignment* item with no `Record Invoice Receipt` and no `Clear Invoice` | a `Record Invoice Receipt` of the item's value is added one second after its last event |
| F6 | C6 | closed *invoice after GR* goods item | its last `Record Invoice Receipt` rises by 10% of its value, rounded down to whole euros, and at least 100 EUR |

Look-alikes, each a pattern measured in the real log that is not a fault
and must not be flagged by any criterion:

| Kind | Applied to | Change |
|---|---|---|
| L1 | closed *invoice after GR* goods item with exactly one `Record Goods Receipt`, before its first `Record Invoice Receipt` | a `Cancel Goods Receipt` and a `Record Goods Receipt` of the same value are added one and two seconds after it: a receipt corrected |
| L2 | closed *invoice after GR* goods item with exactly one `Record Invoice Receipt` | a `Cancel Invoice Receipt` and a `Record Invoice Receipt` of the same value are added one and two seconds after it: an invoice corrected |
| L3 | closed *invoice after GR* goods item with exactly one `Record Goods Receipt`, of value `v` of 2 EUR or more | it is replaced by two receipts at the same time, of `floor(v / 2)` and `v - floor(v / 2) - 1`: one delivery in two parts whose cents add up past a euro |

"Closed" means the item has a `Clear Invoice`, as in C1 to C6.

A fault counts as detected when its criterion flags the item. A look-alike flagged by any
criterion is a false alarm, and so is a fault item flagged by a criterion other than its
own.

### 3. Before and after

The baseline is the three-way match a team would build in a spreadsheet: it looks only at
whether documents exist and whether totals agree. It ignores the order of events, the
cancellations, the reversal note and the truncation to whole euros, and it checks service
items with cancellations or changes like any other. Its rules, each standing in for a
criterion of matchbook:

| Rule | Stands in for | Flags |
|---|---|---|
| B2 | C2 | a closed 3-way match item (either kind) with no `Record Goods Receipt` |
| B3 | C3 | a closed *2-way match* item with no `Record Invoice Receipt` |
| B4 | C4 | a *Consignment* item with a `Record Invoice Receipt` or a `Clear Invoice` |
| B6 | C6 | a closed *invoice after GR* item with a `Record Invoice Receipt` whose sum of `Record Invoice Receipt` values differs from its sum of `Record Service Entry Sheet` values (service items) or `Record Goods Receipt` values (the rest) |

There is no rule for C1: a spreadsheet match does not look at order, so the baseline misses
F1 by design. The baseline runs on the same injected log as matchbook, and the report puts
the two side by side per kind. On the real log, a first measurement gives the baseline 566
B2 and 1,928 B6 items against 735 C2 and 276 C6 (plus 534 not checked) for matchbook, and
none for B3 and B4 against 10 C3; the report gives the counts of items each flags that the
other does not.

### 4. Diagnosis report

`python -m matchbook report <log> <output.md>` writes a Markdown report:

- a status per control (the rule behind C1, C2, C3, C4 and C6) on the real log: PASS with
  no finding, HOLD with findings and none high, FAIL with a high finding;
- the findings by severity, with the count and euros per severity and per criterion;
- detection and false alarms of matchbook and of the baseline on the injected log, per
  kind;
- a keep, fix or replace plan: keep a PASS control, fix a HOLD control, replace a FAIL
  control, each with the finding that decides it.

The README opens with a first screen that shows the numbers of the report and one real
finding told step by step, and 2 or 3 images made from the report.

## Rabbit holes

- **The truth is made with the same understanding as the checks.** The faults are injected
  by rules written by the same people as the checks, so detecting them shows that each
  check catches its kind, not how many real faults the log holds. The look-alikes come from
  patterns measured in the real log, and the baseline shows what the same understanding
  costs a team without it. The README says so next to the numbers.
- **Severity thresholds.** 10,000 and 1,000 EUR were set by the human on 2026-11-08 from the real
  log (they put 69 findings in high), not taken from a policy of the company that produced it.
- **The real log has its own exceptions.** The 1,021 real findings stay as they are; the
  injected items are chosen among the items no one flags, so a real exception never
  counts as a false alarm of an injected one.

## No-gos

- "The AI explains each finding" is not in this version (ROADMAP.md, Later).
- No RAG and no agent in matchbook.
- C1 to C11 do not change; C5 stays deferred.
- No new data, no user interface, no database, and no changes to the source data.
- Open items stay out, as in the first version.
