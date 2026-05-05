"""
Financial report queries: General Ledger, Trial Balance, Balance Sheet, P&L,
Tax Summary, AR/AP Aging, Cash Flow, Sales by Customer, Purchases by Supplier,
Item Sales, Bank Account Summary.
"""
import sqlite3
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd


def general_ledger(
    conn: sqlite3.Connection,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    account: Optional[str] = None,
    party: Optional[str] = None,
    transaction_type: Optional[str] = None,
) -> pd.DataFrame:
    query = """
        SELECT
            ale.date,
            ale.account,
            ale.party,
            ale.debit,
            ale.credit,
            ale.transaction_type,
            ale.transaction_name
        FROM accounting_ledger_entry ale
        WHERE ale.is_cancelled = 0
    """
    params: list = []

    if from_date:
        query += " AND ale.date >= ?"
        params.append(from_date)
    if to_date:
        query += " AND ale.date <= ?"
        params.append(to_date)
    if account:
        query += " AND ale.account = ?"
        params.append(account)
    if party:
        query += " AND ale.party = ?"
        params.append(party)
    if transaction_type and transaction_type != "All":
        query += " AND ale.transaction_type = ?"
        params.append(transaction_type)

    query += " ORDER BY ale.date ASC, ale.id ASC"

    rows = conn.execute(query, params).fetchall()
    df = pd.DataFrame([dict(r) for r in rows])

    if df.empty:
        return pd.DataFrame(columns=["date", "account", "party", "debit", "credit",
                                     "transaction_type", "transaction_name", "balance"])

    df["debit"] = pd.to_numeric(df["debit"], errors="coerce").fillna(0)
    df["credit"] = pd.to_numeric(df["credit"], errors="coerce").fillna(0)
    df["balance"] = (df["debit"] - df["credit"]).cumsum()
    return df


def trial_balance(
    conn: sqlite3.Connection,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> pd.DataFrame:
    query = """
        SELECT
            a.name as account,
            a.root_type,
            a.account_type,
            a.parent_account,
            a.is_group,
            COALESCE(SUM(ale.debit), 0) as total_debit,
            COALESCE(SUM(ale.credit), 0) as total_credit
        FROM account a
        LEFT JOIN accounting_ledger_entry ale
            ON ale.account = a.name AND ale.is_cancelled = 0
    """
    params: list = []
    conditions = []

    if from_date:
        conditions.append("ale.date >= ?")
        params.append(from_date)
    if to_date:
        conditions.append("ale.date <= ?")
        params.append(to_date)

    if conditions:
        query += " AND " + " AND ".join(conditions)

    query += " GROUP BY a.name ORDER BY a.root_type, a.name"

    rows = conn.execute(query, params).fetchall()
    df = pd.DataFrame([dict(r) for r in rows])

    if df.empty:
        return pd.DataFrame(columns=["account", "root_type", "account_type",
                                     "parent_account", "is_group",
                                     "total_debit", "total_credit", "balance"])

    df["total_debit"] = pd.to_numeric(df["total_debit"], errors="coerce").fillna(0)
    df["total_credit"] = pd.to_numeric(df["total_credit"], errors="coerce").fillna(0)
    df["balance"] = df["total_debit"] - df["total_credit"]
    return df


def _get_account_balances(
    conn: sqlite3.Connection,
    root_types: list[str],
    as_of_date: Optional[str] = None,
    from_date: Optional[str] = None,
) -> dict:
    query = """
        SELECT
            a.name,
            a.root_type,
            a.account_type,
            a.parent_account,
            a.is_group,
            COALESCE(SUM(ale.debit), 0) as total_debit,
            COALESCE(SUM(ale.credit), 0) as total_credit
        FROM account a
        LEFT JOIN accounting_ledger_entry ale
            ON ale.account = a.name AND ale.is_cancelled = 0
    """
    params: list = []
    conditions = [f"a.root_type IN ({','.join('?' for _ in root_types)})"]
    params.extend(root_types)

    if from_date:
        conditions.append("ale.date >= ?")
        params.append(from_date)
    if as_of_date:
        conditions.append("ale.date <= ?")
        params.append(as_of_date)

    query += " WHERE " + " AND ".join(conditions)
    query += " GROUP BY a.name"

    rows = conn.execute(query, params).fetchall()
    result = {}
    for r in rows:
        balance = r["total_debit"] - r["total_credit"]
        result[r["name"]] = {
            "root_type": r["root_type"],
            "account_type": r["account_type"],
            "parent_account": r["parent_account"],
            "is_group": r["is_group"],
            "debit": r["total_debit"],
            "credit": r["total_credit"],
            "balance": balance,
        }
    return result


def balance_sheet(
    conn: sqlite3.Connection,
    as_of_date: Optional[str] = None,
) -> dict:
    balances = _get_account_balances(
        conn, ["Asset", "Liability", "Equity"], as_of_date=as_of_date
    )

    def build_tree(root_type: str) -> list:
        top_level = [
            {"account": name, **data}
            for name, data in balances.items()
            if data["root_type"] == root_type and not data["parent_account"]
        ]
        for item in top_level:
            _attach_children(item, balances)
        return top_level

    def _attach_children(node: dict, all_balances: dict) -> None:
        children = [
            {"account": name, **data}
            for name, data in all_balances.items()
            if data["parent_account"] == node["account"]
        ]
        if children:
            node["children"] = children
            for child in children:
                _attach_children(child, all_balances)

    return {
        "Asset": build_tree("Asset"),
        "Liability": build_tree("Liability"),
        "Equity": build_tree("Equity"),
    }


def profit_and_loss(
    conn: sqlite3.Connection,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> dict:
    balances = _get_account_balances(
        conn, ["Income", "Expense"], as_of_date=to_date, from_date=from_date
    )

    income_accounts = {k: v for k, v in balances.items() if v["root_type"] == "Income"}
    expense_accounts = {k: v for k, v in balances.items() if v["root_type"] == "Expense"}

    total_income = sum(abs(v["balance"]) for v in income_accounts.values()
                       if not v["is_group"])
    total_expense = sum(abs(v["balance"]) for v in expense_accounts.values()
                        if not v["is_group"])
    net_profit = total_income - total_expense

    return {
        "income": income_accounts,
        "expense": expense_accounts,
        "total_income": total_income,
        "total_expense": total_expense,
        "net_profit": net_profit,
    }


def accounts_receivable(conn: sqlite3.Connection, as_of_date: Optional[str] = None) -> pd.DataFrame:
    query = """
        SELECT
            si.name,
            si.party,
            si.date,
            si.due_date,
            si.grand_total,
            si.outstanding_amount,
            si.status
        FROM sales_invoice si
        WHERE si.status IN ('Submitted', 'Overdue')
          AND si.outstanding_amount > 0
          AND si.is_return = 0
    """
    params: list = []
    if as_of_date:
        query += " AND si.date <= ?"
        params.append(as_of_date)
    query += " ORDER BY si.date ASC"

    rows = conn.execute(query, params).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def accounts_payable(conn: sqlite3.Connection, as_of_date: Optional[str] = None) -> pd.DataFrame:
    query = """
        SELECT
            pi.name,
            pi.party,
            pi.date,
            pi.due_date,
            pi.grand_total,
            pi.outstanding_amount,
            pi.status
        FROM purchase_invoice pi
        WHERE pi.status IN ('Submitted', 'Overdue', 'Partially Paid')
          AND pi.outstanding_amount > 0
          AND pi.is_return = 0
    """
    params: list = []
    if as_of_date:
        query += " AND pi.date <= ?"
        params.append(as_of_date)
    query += " ORDER BY pi.date ASC"

    rows = conn.execute(query, params).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def ar_aging(conn: sqlite3.Connection, as_of_date: Optional[str] = None) -> pd.DataFrame:
    """AR aging with buckets: Current, 1-30, 31-60, 61-90, 90+ days overdue."""
    today_str = as_of_date or datetime.now().strftime("%Y-%m-%d")
    rows = conn.execute(
        """SELECT name, party, date, due_date, outstanding_amount
           FROM sales_invoice
           WHERE status IN ('Submitted', 'Overdue', 'Partially Paid')
             AND outstanding_amount > 0 AND is_return = 0""",
    ).fetchall()
    if not rows:
        return pd.DataFrame()
    records = []
    for r in rows:
        days_overdue = (datetime.strptime(today_str, "%Y-%m-%d") -
                        datetime.strptime(r["due_date"] or r["date"], "%Y-%m-%d")).days
        amt = float(r["outstanding_amount"])
        records.append({
            "Invoice": r["name"],
            "Customer": r["party"],
            "Due Date": r["due_date"],
            "Outstanding": amt,
            "Current": amt if days_overdue <= 0 else 0,
            "1-30 Days": amt if 1 <= days_overdue <= 30 else 0,
            "31-60 Days": amt if 31 <= days_overdue <= 60 else 0,
            "61-90 Days": amt if 61 <= days_overdue <= 90 else 0,
            "90+ Days": amt if days_overdue > 90 else 0,
        })
    return pd.DataFrame(records)


def ap_aging(conn: sqlite3.Connection, as_of_date: Optional[str] = None) -> pd.DataFrame:
    """AP aging with buckets: Current, 1-30, 31-60, 61-90, 90+ days overdue."""
    today_str = as_of_date or datetime.now().strftime("%Y-%m-%d")
    rows = conn.execute(
        """SELECT name, party, date, due_date, outstanding_amount
           FROM purchase_invoice
           WHERE status IN ('Submitted', 'Overdue', 'Partially Paid')
             AND outstanding_amount > 0 AND is_return = 0""",
    ).fetchall()
    if not rows:
        return pd.DataFrame()
    records = []
    for r in rows:
        days_overdue = (datetime.strptime(today_str, "%Y-%m-%d") -
                        datetime.strptime(r["due_date"] or r["date"], "%Y-%m-%d")).days
        amt = float(r["outstanding_amount"])
        records.append({
            "Invoice": r["name"],
            "Supplier": r["party"],
            "Due Date": r["due_date"],
            "Outstanding": amt,
            "Current": amt if days_overdue <= 0 else 0,
            "1-30 Days": amt if 1 <= days_overdue <= 30 else 0,
            "31-60 Days": amt if 31 <= days_overdue <= 60 else 0,
            "61-90 Days": amt if 61 <= days_overdue <= 90 else 0,
            "90+ Days": amt if days_overdue > 90 else 0,
        })
    return pd.DataFrame(records)


def tax_summary(
    conn: sqlite3.Connection,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> dict:
    """Tax collected (from sales) and tax paid (from purchases) summary."""
    q_base = " AND is_cancelled = 0"
    params_s: list = []
    params_p: list = []
    if from_date:
        q_base_s = q_base + " AND date >= ?"
        params_s.append(from_date)
        params_p.append(from_date)
    else:
        q_base_s = q_base
    if to_date:
        q_base_s = (q_base_s if from_date else q_base) + " AND date <= ?"
        params_s.append(to_date)
        params_p.append(to_date)

    collected_rows = conn.execute(
        f"""SELECT account, SUM(credit) as tax_collected
            FROM accounting_ledger_entry
            WHERE transaction_type = 'SalesInvoice'{q_base_s}
            GROUP BY account""",
        params_s,
    ).fetchall()

    paid_rows = conn.execute(
        f"""SELECT account, SUM(debit) as tax_paid
            FROM accounting_ledger_entry
            WHERE transaction_type = 'PurchaseInvoice'{q_base_s}
            GROUP BY account""",
        params_p,
    ).fetchall()

    tax_accounts = conn.execute("SELECT name, rate FROM tax").fetchall()
    tax_account_names = {t["name"] for t in tax_accounts}

    def is_tax_account(acc_name):
        row = conn.execute(
            "SELECT account_type FROM account WHERE name = ?", (acc_name,)
        ).fetchone()
        return row and row["account_type"] in ("Tax", "Duties and Taxes", "")

    tax_collected = sum(
        float(r["tax_collected"] or 0) for r in collected_rows
        if is_tax_account(r["account"])
    )
    tax_paid = sum(
        float(r["tax_paid"] or 0) for r in paid_rows
        if is_tax_account(r["account"])
    )

    inv_query = """SELECT si.name, SII.tax_amount, SII.tax_rate, SII.tax_account
                   FROM sales_invoice si
                   JOIN sales_invoice_item SII ON SII.parent = si.name
                   WHERE si.status NOT IN ('Draft', 'Cancelled')"""
    params_inv: list = []
    if from_date:
        inv_query += " AND si.date >= ?"
        params_inv.append(from_date)
    if to_date:
        inv_query += " AND si.date <= ?"
        params_inv.append(to_date)

    sales_tax_rows = conn.execute(inv_query, params_inv).fetchall()
    tax_collected_by_rate: dict = {}
    for r in sales_tax_rows:
        rate = float(r["tax_rate"] or 0)
        if rate > 0:
            tax_collected_by_rate[rate] = tax_collected_by_rate.get(rate, 0) + float(r["tax_amount"] or 0)

    pur_query = """SELECT pi.name, PII.tax_amount, PII.tax_rate
                   FROM purchase_invoice pi
                   JOIN purchase_invoice_item PII ON PII.parent = pi.name
                   WHERE pi.status NOT IN ('Draft', 'Cancelled')"""
    params_pur: list = []
    if from_date:
        pur_query += " AND pi.date >= ?"
        params_pur.append(from_date)
    if to_date:
        pur_query += " AND pi.date <= ?"
        params_pur.append(to_date)

    pur_tax_rows = conn.execute(pur_query, params_pur).fetchall()
    tax_paid_by_rate: dict = {}
    for r in pur_tax_rows:
        rate = float(r["tax_rate"] or 0)
        if rate > 0:
            tax_paid_by_rate[rate] = tax_paid_by_rate.get(rate, 0) + float(r["tax_amount"] or 0)

    all_rates = sorted(set(list(tax_collected_by_rate.keys()) + list(tax_paid_by_rate.keys())))
    breakdown = []
    total_collected = 0.0
    total_paid = 0.0
    for rate in all_rates:
        c = tax_collected_by_rate.get(rate, 0)
        p = tax_paid_by_rate.get(rate, 0)
        total_collected += c
        total_paid += p
        breakdown.append({"rate": rate, "collected": round(c, 2), "paid": round(p, 2), "net": round(c - p, 2)})

    return {
        "breakdown": breakdown,
        "total_collected": round(total_collected, 2),
        "total_paid": round(total_paid, 2),
        "net_payable": round(total_collected - total_paid, 2),
    }


def sales_by_customer(
    conn: sqlite3.Connection,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> pd.DataFrame:
    query = """
        SELECT si.party as customer,
               COUNT(si.name) as invoice_count,
               SUM(si.net_total) as net_total,
               SUM(si.tax_total) as tax_total,
               SUM(si.grand_total) as grand_total,
               SUM(si.outstanding_amount) as outstanding
        FROM sales_invoice si
        WHERE si.status NOT IN ('Draft', 'Cancelled') AND si.is_return = 0
    """
    params: list = []
    if from_date:
        query += " AND si.date >= ?"
        params.append(from_date)
    if to_date:
        query += " AND si.date <= ?"
        params.append(to_date)
    query += " GROUP BY si.party ORDER BY grand_total DESC"
    rows = conn.execute(query, params).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def purchases_by_supplier(
    conn: sqlite3.Connection,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> pd.DataFrame:
    query = """
        SELECT pi.party as supplier,
               COUNT(pi.name) as invoice_count,
               SUM(pi.net_total) as net_total,
               SUM(pi.tax_total) as tax_total,
               SUM(pi.grand_total) as grand_total,
               SUM(pi.outstanding_amount) as outstanding
        FROM purchase_invoice pi
        WHERE pi.status NOT IN ('Draft', 'Cancelled') AND pi.is_return = 0
    """
    params: list = []
    if from_date:
        query += " AND pi.date >= ?"
        params.append(from_date)
    if to_date:
        query += " AND pi.date <= ?"
        params.append(to_date)
    query += " GROUP BY pi.party ORDER BY grand_total DESC"
    rows = conn.execute(query, params).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def item_sales_report(
    conn: sqlite3.Connection,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> pd.DataFrame:
    query = """
        SELECT sii.item,
               SUM(sii.quantity) as total_qty,
               SUM(sii.amount) as net_amount,
               SUM(sii.tax_amount) as tax_amount,
               COUNT(DISTINCT si.name) as invoice_count
        FROM sales_invoice_item sii
        JOIN sales_invoice si ON si.name = sii.parent
        WHERE si.status NOT IN ('Draft', 'Cancelled') AND si.is_return = 0
    """
    params: list = []
    if from_date:
        query += " AND si.date >= ?"
        params.append(from_date)
    if to_date:
        query += " AND si.date <= ?"
        params.append(to_date)
    query += " GROUP BY sii.item ORDER BY net_amount DESC"
    rows = conn.execute(query, params).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def cash_flow_summary(
    conn: sqlite3.Connection,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> dict:
    """Simple cash flow: cash inflows from payments received, outflows from payments made."""
    q = """SELECT payment_type, SUM(amount) as total
           FROM payment WHERE status = 'Submitted'"""
    params: list = []
    if from_date:
        q += " AND date >= ?"
        params.append(from_date)
    if to_date:
        q += " AND date <= ?"
        params.append(to_date)
    q += " GROUP BY payment_type"

    rows = conn.execute(q, params).fetchall()
    inflow = 0.0
    outflow = 0.0
    for r in rows:
        if r["payment_type"] == "Receive":
            inflow += float(r["total"] or 0)
        else:
            outflow += float(r["total"] or 0)

    bank_txns = conn.execute(
        """SELECT transaction_type, SUM(amount) as total
           FROM bank_transaction
           WHERE 1=1"""
        + (" AND date >= ?" if from_date else "")
        + (" AND date <= ?" if to_date else "")
        + " GROUP BY transaction_type",
        [p for p in [from_date, to_date] if p],
    ).fetchall()
    bank_in = 0.0
    bank_out = 0.0
    for r in bank_txns:
        if r["transaction_type"] in ("Deposit", "Transfer In"):
            bank_in += float(r["total"] or 0)
        elif r["transaction_type"] in ("Withdrawal", "Transfer Out"):
            bank_out += float(r["total"] or 0)

    return {
        "operating_inflow": round(inflow, 2),
        "operating_outflow": round(outflow, 2),
        "net_operating": round(inflow - outflow, 2),
        "bank_inflow": round(bank_in, 2),
        "bank_outflow": round(bank_out, 2),
        "net_cash": round(inflow - outflow + bank_in - bank_out, 2),
    }


def bank_account_summary(conn: sqlite3.Connection) -> pd.DataFrame:
    rows = conn.execute(
        """SELECT ba.name, ba.account_type, ba.bank_name, ba.currency, ba.opening_balance,
                  COALESCE(SUM(CASE WHEN bt.transaction_type IN ('Deposit','Transfer In') THEN bt.amount
                                    WHEN bt.transaction_type IN ('Withdrawal','Transfer Out') THEN -bt.amount
                                    ELSE 0 END), 0) as movements
           FROM bank_account ba
           LEFT JOIN bank_transaction bt ON bt.bank_account = ba.name
           WHERE ba.is_active = 1
           GROUP BY ba.name ORDER BY ba.account_type, ba.name"""
    ).fetchall()
    if not rows:
        return pd.DataFrame()
    records = []
    for r in rows:
        balance = float(r["opening_balance"] or 0) + float(r["movements"] or 0)
        records.append({
            "Account": r["name"],
            "Type": r["account_type"],
            "Bank": r["bank_name"],
            "Currency": r["currency"],
            "Opening Balance": round(float(r["opening_balance"] or 0), 2),
            "Movements": round(float(r["movements"] or 0), 2),
            "Current Balance": round(balance, 2),
        })
    return pd.DataFrame(records)
