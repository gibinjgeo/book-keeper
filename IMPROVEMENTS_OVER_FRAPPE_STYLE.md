# Improvements Over Original Frappe-Style Implementation

## 1. Decimal Arithmetic (Critical Accounting Fix)

**Before**: `float` used in `calculate_invoice_totals` — subject to IEEE 754 rounding errors  
**After**: `decimal.Decimal` with `ROUND_HALF_UP` throughout; `float()` only for SQLite storage

```python
# Before
amount = round(qty * rate, 2)  # float multiplication

# After
amount = _round2(_d(qty) * _d(rate))  # Decimal multiplication
```

## 2. Invoice Status: Partially Paid

**Before**: after partial payment, status stayed "Submitted" with no indication  
**After**: explicit "Partially Paid" status; outstanding_amount updates correctly using Decimal subtraction

## 3. Overdue Auto-Detection

**Before**: overdue status had to be manually set  
**After**: `update_overdue_statuses()` runs on every page load, auto-marking invoices/bills where `due_date < today` and `outstanding_amount > 0`

## 4. Discount Support

**Before**: discount_amount was hardcoded to 0.0  
**After**: `discount_percent` parameter; calculated as percentage of net_total before tax

## 5. Credit Notes / Debit Notes

**Before**: `is_return` field existed but no workflow to create return documents  
**After**: `create_credit_note()` and `create_debit_note()` functions that clone a submitted invoice as a return document

## 6. Quote → Invoice Workflow

**Before**: no quote/estimate feature  
**After**: full quote lifecycle: Draft → Sent → Converted/Cancelled; `convert_to_invoice()` creates a sales invoice and marks quote as Converted

## 7. Banking Module

**Before**: no bank account tracking (only GL accounts)  
**After**: dedicated `bank_account` + `bank_transaction` tables; deposits, withdrawals, transfers; reconciliation tracking; linked GL account posting

## 8. 14 Reports (was 6)

**Before**: General Ledger, Trial Balance, Balance Sheet, P&L, AR, AP  
**After**: + AR Aging (with day buckets), AP Aging, Tax Summary, Sales by Customer, Purchases by Supplier, Item Sales, Cash Flow Summary, Bank Account Summary

All reports have CSV download.

## 9. AR/AP Aging with Day Buckets

**Before**: AR/AP was just a list of outstanding invoices  
**After**: Aging columns: Current, 1-30, 31-60, 61-90, 90+ days overdue (calculated vs. as-of-date)

## 10. Tax Summary Report

**Before**: no tax report  
**After**: Tax collected from sales vs tax paid on purchases, broken down by rate, with net payable/refundable

## 11. Company Profile with Tax Number

**Before**: Settings stored: name, country, currency, fiscal year only  
**After**: + tax_number (VAT/GST), phone, email, website, full address, document number prefixes

## 12. Document Number Prefixes

**Before**: hardcoded SINV-, PINV-, PAY-, JV-  
**After**: configurable per company in Settings > Document Prefixes

## 13. Rich Party / Contact Records

**Before**: Party had billing address only  
**After**: + shipping address, contact_person, opening_balance, notes, is_active

## 14. Item Purchase Price

**Before**: only sale price (`rate`)  
**After**: + `purchase_rate`, `stock_quantity`, `is_active`

## 15. Local Backup / Restore

**Before**: no backup mechanism  
**After**: timestamped DB file copies; list/restore from backup; direct DB file download button

## 16. CSV Import/Export

**Before**: no import/export  
**After**: CSV export for all major entities; CSV import for contacts and items with duplicate detection

## 17. Enhanced Dashboard

**Before**: 4 all-time totals; 2 recent lists; 4 quick action buttons  
**After**: 8 metrics (monthly income/expenses, receivable/payable, overdue counts, net profit, cash balance); Top customers; Top expense suppliers; 5 quick action buttons

## 18. Schema Migration Safety

**Before**: only `CREATE TABLE IF NOT EXISTS` — new columns silently absent on existing DBs  
**After**: `migrate_schema()` applies `ALTER TABLE ADD COLUMN` for every new column, safe to run repeatedly

## 19. Automated Test Suite (26 tests)

**Before**: no tests  
**After**: pytest suite covering money arithmetic, double-entry balance, invoice lifecycle, payment application, overdue detection, credit notes, banking, quotes, and report totals
