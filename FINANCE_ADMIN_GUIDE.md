# SaccoAPI Finance Architecture & Admin Guide

## Overview
The `finances` app has been upgraded to a robust, hierarchical General Ledger (GL) system. 
This new architecture supports compound journal entries, hierarchical Chart of Accounts (COA) for advanced financial reporting, and a dynamic rules engine for mapping transactions.

This document outlines the core concepts and provides instructions for Administrators on how to configure and manage the system via the Django Admin Panel.

---

## Core Operational Concepts

### 1. Hierarchical Chart of Accounts (COA)
The `GLAccount` model now supports a parent-child relationship.
*   **Account Classes:** Root categories such as Assets, Liabilities, Equity, Revenue, and Expenses.
*   **Parent Accounts:** Groups like "Current Assets" or "Cash at Bank".
*   **Leaf Accounts:** The actual accounts where transactions hit, like "KCB Account" or "Equity Bank Account".
*   *Financial reports (Balance Sheet, Income Statement) will automatically recursively calculate balances from the leaf accounts up to the root.*

### 2. Transaction Templates (The Rules Engine)
Previously, debit and credit logic was hardcoded in `finances/utils.py`. The new `TransactionTemplate` and `TransactionTemplateLine` models allow you to configure these rules dynamically via the database.
*   When a "Savings Deposit" or "Loan Repayment" happens, the system looks up the corresponding `TransactionTemplate`.
*   It reads the `TransactionTemplateLine`s to determine which `GLAccount` to Debit and which to Credit.

### 3. Smart Fallbacks
If a new transaction type (like a new dynamic fee) is introduced, the `post_to_gl` utility is designed to automatically generate a `TransactionTemplate` and the corresponding GL Lines on the fly. It will ensure operations do not fail and the books remain balanced, giving the Admin time to review and adjust the mappings later.

---

## Administrator Operations Guide

All configurations can be done from the Django Admin Panel under the **FINANCES** section.

### A. Managing the Chart of Accounts

**To create a new sub-account (e.g., A new bank account for savings):**
1. Navigate to **Finances ➔ GL Accounts**.
2. Click **Add GL Account**.
3. Provide a unique **Code** (e.g., `1011`) and **Name** (e.g., `Equity Bank Account`).
4. Select the appropriate **Account type** (e.g., `Asset`).
5. In the **Parent** dropdown, select the grouping account (e.g., `1010 - Cash at Bank`).
6. Save the account.
*Note: Sub-accounts must have the exact same Account Type as their parent.*

### B. Changing Transaction Rules (Routing Funds)

If you want to change where money goes for a specific action (e.g., routing all new Savings Deposits to the new Equity Bank Account):
1. Navigate to **Finances ➔ Transaction Templates**.
2. Open the template responsible for the action (e.g., `Savings Deposit`).
3. Scroll down to the **Transaction template lines**.
4. You will see the existing rules (e.g., Debit `1010 - Cash at Bank` and Credit `2010 - Member Savings Deposits`).
5. Change the `GL Account` dropdown on the Debit line from `1010 - Cash at Bank` to your newly created `1011 - Equity Bank Account`.
6. Save the template.
*Result: All future savings deposits will securely route into that new GL account. Historical transactions remain untouched.*

### C. Reviewing Transactions (Journals)

To audit and trace transactions:
1. Navigate to **Finances ➔ Journals**.
2. You will see a list of all compound journal headers (e.g., "Savings Deposit...").
3. Click into any Journal to see the exact Date, Description, Source Model, and the **Journal Entries** (line items) detailing the exact Debits and Credits applied to balance the books.

---
*Generated as part of the Finances App Architectural Upgrade (2026).*
