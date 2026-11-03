# Export reconcilable sales and isolated shop data

## Title and ID
`washday-mvp-reports` — BIR workbook and per-shop data export (milestone 4).

## Source
[PRD](../../reference/docs/PRD.md) §3 `/owner/reports/bir.xlsx`, openpyxl; §5 Dashboard; §6 Paper job sheet / dashboard totals; §8 Tenant isolation; §9 checklist lines 542, 545, 547 and “Still to collect”.

## References
[Preview](../../reference/prototype/index.html): Dashboard BIR report card and Export to Excel interaction; not an authority for workbook columns/layout. [Package README](../../reference/README.md), [paper reconciliation fixture](../../reference/docs/paper-job-sheet.pdf), [brand](../../reference/img/logo-header.png), [shared constraints](README.md#shared-execution-constraints). Owner's actual BIR workbook: **not supplied**.

## Desired outcome
The owner can download sales for a chosen date range in the existing BIR Excel format and obtain only her shop's data for offboarding/privacy purposes.

## Dependencies
`washday-mvp-monitoring`: authorised scope and verified date/payment aggregation. External: owner's sample current BIR workbook for exact format acceptance; obtaining it does not block implementing known aggregation/export behavior.

## Acceptance criteria
- **AC-01:** `/owner/reports/bir.xlsx` exports a selected date range as a valid Excel workbook with daily sales by branch and Cash/GCash, including job payments and self-service once each. Collection day comes from `paid_at` / self-service start, not receipt/entry time; compensation is reflected.
- **AC-02:** A next-day paper encoding of received, paid and claimed jobs contributes to its actual sheet day in export, History and dashboard consistently. Existing price snapshots determine amounts, not current prices.
- **AC-03:** **Draft pending sample:** workbook sheet structure, columns, labels, order and formatting match the owner's supplied current BIR Excel sheet and open correctly in Excel. The sample must be stored/referenced accessibly (sanitised if necessary) or its owner-approved exact format documented before this criterion becomes executable. Do not invent a “BIR-ready” replacement layout and call it accepted.
- **AC-04:** A cloud per-shop data export can be produced in CSV or JSON for offboarding/privacy, including shop-owned operational/settings data necessary to represent that shop, with no another-shop rows. This is separate from the sales-only workbook; source allows either CSV or JSON, not both as an invented requirement. Secret hashes/keys must not be exposed as user data.
- **AC-05:** Authentication/scope applies to exports and date/branch filters; foreign-shop records return 404 and no cross-tenant rows appear even with altered parameters. Invalid date ranges fail clearly without generating a misleading report.
- **AC-06:** Dashboard export control works with shared accessible theme/responsive interaction. Reproducible reconciliation fixtures, workbook inspection and cross-shop tests pass; downloading a file alone is not reconciliation evidence.

## Constraints
[Shared constraints](README.md#shared-execution-constraints); use openpyxl as specified. This sales workbook is not an official receipt or claim of regulatory certification. User-owned sample data is not production seed data. Keep exact format unknown until owner supplies it.

## Out of scope
Official receipts, billing/plans and new tax workflows are source exclusions. Dashboard and staff behavior remain with their owning outcomes. Backup/restore isolation is hub operations.

## Verification notes
Fixture with two shops, several branches, unpaid and pre-paid jobs, cross-day paper payments/claims, self-service and compensation at Manila midnight/date range boundaries. Inspect workbook values/types with openpyxl and open in Excel; compare approved sample separately. Inspect CSV/JSON exported scope and verify no secrets/foreign rows. Rerun after sync applies replicated events. AC-03 cannot pass without the actual sample/approved specification.

## Open questions/blockers
Blocked by `washday-mvp-monitoring` evidence and missing BIR sample for AC-03. Known export rules may be implemented meanwhile; the document remains draft for exact-layout acceptance. No proposed substitute format.
