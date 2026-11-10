# Criteria

The checkable conditions for matchbook (see [BRIEF.md](BRIEF.md)): C1 to C11 for the first
version, C12 to C21 for the second, C22 onward for its publication (slice S11). They are
written in [EARS](https://alistairmavin.com/ears/) form ("When ..., matchbook shall ...").
Every criterion has an ID; each test names the criterion it checks, and the work is done when
every criterion has passing tests.

Activity names are the ones in the log (all 42 were counted on the real file). "Item" means
one trace: one purchase order item.

## Document checks

| ID | Criterion |
|---|---|
| C1 | When a *3-way match, invoice after GR* item that has a `Record Goods Receipt` or a `Clear Invoice` has a `Record Invoice Receipt` while no goods receipt is in force (before its first `Record Goods Receipt`, or after `Cancel Goods Receipt` events have undone every earlier one), matchbook shall flag it. An item with a `Clear Invoice` is closed, as in C2, so one invoiced with no goods receipt at all is flagged; one with neither is an open item and is not. |
| C2 | When a 3-way match item (either kind) has a `Clear Invoice` while no goods receipt is in force (no earlier `Record Goods Receipt`, or `Cancel Goods Receipt` events have undone every earlier one), matchbook shall flag it. An item with a `Clear Invoice` is closed, so one with no goods receipt at all is flagged. When that `Clear Invoice` comes within 10 minutes after a `Cancel Invoice Receipt`, the finding carries a note that it may be the clearing of the reversal, not a payment. |
| C3 | When a *2-way match* item has a `Clear Invoice` while no invoice receipt is in force (no earlier `Record Invoice Receipt`, or `Cancel Invoice Receipt` events have undone every earlier one), matchbook shall flag it, with the same note as C2 when the `Clear Invoice` comes within 10 minutes after a `Cancel Invoice Receipt`. |
| C4 | When a *Consignment* item has a `Clear Invoice`, or a `Record Invoice Receipt` that `Cancel Invoice Receipt` events have not undone, matchbook shall flag it. |

## Amount checks

Measured with `uv run python -m matchbook.measure <log>`.

- *2-way match*, *3-way match, invoice before GR* and *Consignment*: `Cumulative net worth
  (EUR)` is a value of the item, not of each document. It is the same on every event of
  1,044 of 1,044, 220,355 of 221,010 and 14,498 of 14,498 items, and every `Record Invoice
  Receipt` equals the order's value (695 of 695 and 209,128 of 209,128).
- *3-way match, invoice after GR*: each event holds the amount of its own document. All
  1,595,923 values of the log are whole euros, truncated from the amount (52 service entry
  sheets of 68 EUR are invoiced at 3,563 EUR, a price of 68.52), so a document stored as `v`
  is worth between `v` and `v + 1`. Each `Cancel Invoice Receipt` and `Cancel Goods
  Receipt` holds the value of an earlier document of its kind (425 of 436 and 543 of 543
  in service items, 371 of 371 and 28 of 28 in goods items). An item with a `Record Service
  Entry Sheet` is a service item: its service entry sheets are what was received, and its
  `Record Goods Receipt` values are not explained (they are not the sum of the item's or
  the document's service entry sheets). Net invoiced matches net received, within the
  truncation, in 5,420 of 5,465 closed goods items without cancellations or changes, 1,539
  of 1,613 closed goods items with them, and 1,905 of 2,062 closed service items without
  them, but only in 255 of 534 closed service items with them.

C5 stays deferred: no category holds the ordered total. In *invoice after GR* service items
the order's value is the amount of one entry, not the total (net invoiced is above it in
1,887 of 2,896 items); in the other categories every invoice equals the order's value, so
C5 could never flag anything there. C5 is resumed when a source with the ordered quantity
or total is available.

C6 compares, for one item, the net invoiced value (the `Record Invoice Receipt` values
minus the `Cancel Invoice Receipt` values) with the net received value (the `Record
Service Entry Sheet` values in a service item; the `Record Goods Receipt` values minus the
`Cancel Goods Receipt` values in a goods item). The only tolerance is the truncation:
with `i` invoices, `c` invoice cancellations, `r` receipts and `g` receipt cancellations,
the stored net difference `d = invoiced - received` is a finding when `d >= r + c` or
`d <= -(i + g)`. A service item with any `Cancel Goods Receipt`, `Cancel Invoice Receipt`,
`Change Price`, `Change Quantity`, `Record Subsequent Invoice` or `Cancel Subsequent
Invoice` has no known rule (255 of 534 match) and is reported apart, not checked. Open
items (no `Clear Invoice`) are not checked, as in C1 and C2: an invoice may still be due.
On the full log C6 flags 276 items: 45 and 74 closed goods items without and with
cancellations or changes, and 157 closed service items.

| ID | Criterion |
|---|---|
| C5 | When the invoiced value of a 3-way or 2-way match item exceeds its ordered value by more than the tolerance, matchbook shall flag it. Deferred: the log holds no ordered total. |
| C6 | When a closed *3-way match, invoice after GR* item (one with a `Clear Invoice`) has a net invoiced value that differs from its net received value by more than the truncation allows, matchbook shall flag it, except a service item with cancellations or changes, which matchbook shall report apart as not checked. |

## Data quality

The log holds purchase orders of 2018 and runs on into January 2019: its 45,128 events of
January 2019 (17,638 of them `Clear Invoice`) are the normal tail of 2018 orders, not
errors. Outside that window are 327 events of 271 items: 318 before 2018 (back to 1948)
and 9 from February 2019 to April 2020. All are `Vendor creates invoice` or `Vendor creates
debit memo` (the date the vendor wrote on its document), except 7 `Create Purchase
Requisition Item` of 2017; none is a receipt, a cancellation or a clearing.

| ID | Criterion |
|---|---|
| C7 | When an event's timestamp falls before 2018-01-01 or after 2019-01-31 (UTC), matchbook shall report the item and those events separately and leave those events, not the rest of the item, out of the document checks (C1 to C4). |

## Output and operation

| ID | Criterion |
|---|---|
| C8 | matchbook shall process the full log on the development machine in under 10 minutes. |
| C9 | matchbook shall produce identical output for identical input. |
| C10 | matchbook shall never write to the data directory. |
| C11 | For every flagged item, matchbook shall output the item, the criterion ID and the events, dates and amounts that broke it. |

## Money at stake

| ID | Criterion |
|---|---|
| C12 | For every finding of C1 to C4 and C6, matchbook shall output the euros at stake as BRIEF.md defines them per criterion (*Money at stake*). |
| C13 | For every finding of C1 to C4 and C6, matchbook shall output a severity: high at 10,000 EUR at stake or more, medium from 1,000 EUR, low below, one level lower for a finding with the reversal note. C7 findings and `C6 not checked` items shall carry no severity. |

## Known truth

| ID | Criterion |
|---|---|
| C14 | When given a seed, matchbook shall build in memory an injected copy of the log with each fault kind (F1 to F6) and look-alike kind (L1 to L3) of BRIEF.md in 50 items, each chosen by the seed among the items the kind applies to that neither matchbook nor the baseline flags on the original log, each item changed at most once; the same seed shall give the same injected log. |
| C15 | When run on the injected log, matchbook shall report per fault kind how many of its items the kind's criterion flags (detected) and how many another criterion flags, and per look-alike kind how many of its items any criterion flags (false alarms). |

## Before and after

| ID | Criterion |
|---|---|
| C16 | matchbook shall include the baseline of BRIEF.md (rules B2, B3, B4 and B6), and a baseline rule shall flag an item exactly when BRIEF.md says it does. |
| C17 | When run on the injected log, matchbook shall report the detected faults and false alarms of the baseline per kind next to its own, a fault of kind F1 counting as missed by the baseline; on the real log it shall report, per baseline rule, the items flagged by the rule only, by its criterion only, and by both. |

## Diagnosis report

| ID | Criterion |
|---|---|
| C18 | When asked for a report, matchbook shall write a Markdown file with a status per control (C1, C2, C3, C4, C6) on the real log: PASS with no finding, HOLD with findings and none high, FAIL with a high finding; and a plan that keeps each PASS control, fixes each HOLD control and replaces each FAIL control, naming the finding that decides it: for a HOLD control its finding with the most euros at stake, for a FAIL control its high finding with the most euros at stake. |
| C19 | The report shall list the count and euros at stake of the findings per severity and per criterion, and the tables of C15 and C17. |
| C20 | The README's section *The report on the full log* shall show the numbers of the report on the full log and one real finding told event by event; a test shall fail when they differ from a run of the report (skipped when the log is not available). |
| C21 | The README's section *The report on the full log* shall show three images drawn from the report on the full log: the findings per control by severity, the detection and false alarms of matchbook and of the baseline on the injected log, and the overlap of each baseline rule with its criterion on the real log; a test shall fail when an image differs from one drawn from a run of the report (skipped when the log is not available). |

## Publication

For a client who reads the repository on GitHub: the README opens as a case study of the
work, in plain words, and the technical detail follows.

| ID | Criterion |
|---|---|
| C22 | The README's first section shall be a case study with the parts *Situation*, *What I did*, *Result* and *What this means for you*, ending with a link to the author's Upwork profile; its numbers shall be those of the report on the full log, and a test shall fail when they differ from a run of the report (skipped when the log is not available). |
| C23 | The README's first section shall name no criterion, fault or look-alike by its code (C1, F1, L1 and so on), and the README shall give each code it uses elsewhere with its name in words. |
| C24 | The README shall have a section *Limitations* that states that the log is public data from 2018, that euros at stake are an amount to review and not a confirmed loss, and that the injected faults show that each check catches its kind, not how many real faults the log holds. |
| C25 | The README shall describe the product and its use only, with no section on the development workflow (check, template, git hooks, agent guardrails, sessions, merge tiers) and no link to one, and shall carry no status line that names a version other than the latest tag. |
| C26 | The repository shall carry an MIT `LICENSE` naming the author, and `pyproject.toml` shall declare the same license. |
| C27 | A GitHub Actions workflow shall run `ruff format --check`, `ruff check`, `mypy` and `pytest` on every push and pull request, and the README shall show its status badge. |
