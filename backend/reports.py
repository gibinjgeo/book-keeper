"""
Financial report queries: General Ledger, Trial Balance, Balance Sheet, P&L.
Mirrors GeneralLedger.ts, TrialBalance.ts, BalanceSheet.ts, ProfitAndLoss.ts.
"""
import sqlite3
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
        WHERE pi.status IN ('Submitted', 'Overdue')
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
