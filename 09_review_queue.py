"""
STEP 9: HUMAN REVIEW QUEUE (CLI Tool)

Batch-first review: shows all leads in a compact table, auto-suggests
PASS/QUERY based on SDE fit, then accepts bulk commands.

Commands:
  a <nums>        Approve specific leads by row number (space-separated)
  r <nums>        Reject specific leads by row number
  f <nums>        Flag specific leads for further research
  a all-pass      Approve all auto-suggested PASS leads
  r all-query     Reject all auto-suggested QUERY leads
  a all           Approve all remaining unreviewed leads
  r all           Reject all remaining unreviewed leads
  show <num>      Show full detail for a lead
  table           Reprint the summary table
  save            Save progress and exit
  q               Save and quit

Auto-suggest logic:
  PASS  — SDE estimate overlaps target range ($250K-$500K)
  QUERY — SDE estimate above or below target range (REVIEW: in notes)

Input:  data/top_100_for_review.csv
Output: data/top_100_for_review.csv (updated with review_status column)
"""

import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from config import OUTPUT_FINAL, TARGET_SDE_LOW, TARGET_SDE_HIGH


STATUS_SYMBOLS = {
    "approved": "[A]",
    "rejected": "[R]",
    "flagged":  "[F]",
    "":         "   ",
}

SUGGEST_PASS  = "PASS "
SUGGEST_QUERY = "QUERY"


def auto_suggest(row):
    """PASS if SDE overlaps target, QUERY if notes say REVIEW:."""
    notes = str(row.get("important_notes", ""))
    if "REVIEW:" in notes:
        return SUGGEST_QUERY
    return SUGGEST_PASS


def print_table(df, show_reviewed=True):
    """Print compact summary table of all leads."""
    header = f"{'#':>3}  {'Suggest':<7}  {'St':<3}  {'Score':>5}  {'Category':<28}  {'SDE Range':<18}  Business Name"
    print()
    print(header)
    print("-" * 110)
    for idx, row in df.iterrows():
        num = idx + 1
        status = str(row.get("review_status", "")).strip()
        if not show_reviewed and status:
            continue
        suggest = auto_suggest(row)
        st_sym = STATUS_SYMBOLS.get(status, "   ")
        score = row.get("acquisition_fit_score", "?")
        category = str(row.get("category_standardized", ""))[:28]
        sde = str(row.get("sde_range_estimate", ""))[:18]
        name = str(row.get("business_name", ""))[:45]
        print(f"{num:>3}  {suggest:<7}  {st_sym:<3}  {score:>5}  {category:<28}  {sde:<18}  {name}")
    print()


def print_detail(row, num, total):
    """Print full detail for one lead."""
    print()
    print("=" * 70)
    print(f"  Lead {num} of {total}")
    print("=" * 70)
    print(f"  Business:    {row['business_name']}")
    print(f"  Address:     {row['address']}")
    print(f"  City:        {row['city']}  |  Postal: {row['postal_code']}")
    print(f"  Phone:       {row['phone']}")
    print(f"  Website:     {row['website']}")
    print(f"  Owner:       {row['owner_name']} ({row['owner_confidence']})")
    print(f"  Industry:    {row['industry']}")
    print(f"  Category:    {row['category_standardized']}")
    print(f"  Employees:   {row['employee_range_estimate']}")
    print(f"  Revenue:     {row['revenue_range_estimate']}")
    print(f"  SDE:         {row['sde_range_estimate']}")
    print(f"  Age:         {row['age_range_estimate']}")
    print(f"  Score:       {row['acquisition_fit_score']}")
    print(f"  Notes:       {row['important_notes']}")
    status = str(row.get("review_status", "")).strip()
    if status:
        print(f"  Status:      [{status.upper()}]")
    print("-" * 70)


def parse_nums(parts, max_n):
    """Parse space-separated lead numbers from command parts. Returns list of 0-based indices."""
    indices = []
    for p in parts:
        try:
            n = int(p)
            if 1 <= n <= max_n:
                indices.append(n - 1)
        except ValueError:
            pass
    return indices


def print_stats(df):
    approved = len(df[df["review_status"] == "approved"])
    rejected = len(df[df["review_status"] == "rejected"])
    flagged  = len(df[df["review_status"] == "flagged"])
    pending  = len(df[df["review_status"].fillna("").str.len() == 0])
    print(f"\n  Approved: {approved}  Rejected: {rejected}  Flagged: {flagged}  Pending: {pending}")


def main():
    print("=" * 60)
    print(" STEP 9: HUMAN REVIEW QUEUE (Batch Mode)")
    print("=" * 60)

    if not os.path.exists(OUTPUT_FINAL):
        print(f"\n  [ERROR] {OUTPUT_FINAL} not found. Run steps 0-7 first.")
        sys.exit(1)

    df = pd.read_csv(OUTPUT_FINAL)
    print(f"  [INPUT] {len(df)} leads from {OUTPUT_FINAL}")

    if "review_status" not in df.columns:
        df["review_status"] = ""
    else:
        df["review_status"] = df["review_status"].fillna("")

    # Auto-suggest summary
    pass_ids  = [i for i, r in df.iterrows() if auto_suggest(r) == SUGGEST_PASS]
    query_ids = [i for i, r in df.iterrows() if auto_suggest(r) == SUGGEST_QUERY]
    reviewed  = len(df[df["review_status"].str.len() > 0])

    print(f"\n  Auto-suggest: {len(pass_ids)} PASS  |  {len(query_ids)} QUERY  |  {reviewed} already reviewed")
    print(f"  PASS  = SDE overlaps target range ($250K-$500K CAD)")
    print(f"  QUERY = SDE estimate out of target range (needs closer look)")

    print_table(df)

    print("  Commands: a/r/f <nums>  |  a all-pass  |  r all-query  |  a all  |  r all")
    print("            show <num>   |  table        |  save/q")

    changes = 0

    while True:
        try:
            raw = input("\n  > ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not raw:
            continue

        parts = raw.lower().split()
        cmd = parts[0]

        # ── quit / save ─────────────────────────────────────────────────
        if cmd in ("q", "quit", "save"):
            break

        # ── table ───────────────────────────────────────────────────────
        elif cmd == "table":
            print_table(df)

        # ── show <num> ──────────────────────────────────────────────────
        elif cmd == "show" and len(parts) >= 2:
            nums = parse_nums(parts[1:], len(df))
            for i in nums:
                print_detail(df.iloc[i], i + 1, len(df))

        # ── bulk shortcuts ───────────────────────────────────────────────
        elif cmd == "a" and len(parts) == 2 and parts[1] == "all-pass":
            unreviewed_pass = [i for i in pass_ids if not df.at[i, "review_status"]]
            for i in unreviewed_pass:
                df.at[i, "review_status"] = "approved"
            changes += len(unreviewed_pass)
            print(f"  -> APPROVED {len(unreviewed_pass)} PASS leads")
            print_stats(df)

        elif cmd == "r" and len(parts) == 2 and parts[1] == "all-query":
            unreviewed_query = [i for i in query_ids if not df.at[i, "review_status"]]
            for i in unreviewed_query:
                df.at[i, "review_status"] = "rejected"
            changes += len(unreviewed_query)
            print(f"  -> REJECTED {len(unreviewed_query)} QUERY leads")
            print_stats(df)

        elif cmd == "a" and len(parts) == 2 and parts[1] == "all":
            targets = [i for i, r in df.iterrows() if not df.at[i, "review_status"]]
            for i in targets:
                df.at[i, "review_status"] = "approved"
            changes += len(targets)
            print(f"  -> APPROVED {len(targets)} leads")
            print_stats(df)

        elif cmd == "r" and len(parts) == 2 and parts[1] == "all":
            targets = [i for i, r in df.iterrows() if not df.at[i, "review_status"]]
            for i in targets:
                df.at[i, "review_status"] = "rejected"
            changes += len(targets)
            print(f"  -> REJECTED {len(targets)} leads")
            print_stats(df)

        # ── individual a/r/f <nums> ──────────────────────────────────────
        elif cmd in ("a", "r", "f") and len(parts) >= 2:
            action_map = {"a": "approved", "r": "rejected", "f": "flagged"}
            status = action_map[cmd]
            nums = parse_nums(parts[1:], len(df))
            if not nums:
                print("  No valid lead numbers.")
                continue
            for i in nums:
                df.at[i, "review_status"] = status
            changes += len(nums)
            names = [df.at[i, "business_name"] for i in nums]
            label = status.upper()
            for n in names:
                print(f"  -> {label}: {n}")
            print_stats(df)

        else:
            print("  Unknown command. Try: a 1 5 12 | r 3 | f 7 | a all-pass | r all-query | show 4 | table | q")

    # Save
    if changes > 0:
        df.to_csv(OUTPUT_FINAL, index=False, encoding="utf-8")
        print(f"\n  [SAVED] {changes} reviews recorded -> {OUTPUT_FINAL}")

    print_stats(df)


if __name__ == "__main__":
    main()
