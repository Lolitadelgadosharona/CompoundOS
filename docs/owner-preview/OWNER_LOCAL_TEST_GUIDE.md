# Owner Experience Test Guide

Open **http://localhost:3802**. No terminal, login or API key is required for normal Preview testing. Persistent DEMO/SIMULATED/no-trades banner applies throughout.

1. Dashboard: inspect total portfolio, holdings, cash, CNY10000 planned monthly contribution, risks and latest plan status.
2. Portfolio: compare current%, target% and under/overweight positions. Figures come from the real engine.
3. Review Investment Plan: read proposed purchases and why new capital goes to gaps. No selling is proposed.
4. Prepare DEMO plan for review. No holdings/cash are changed.
5. Inspect Policy and Guardian; warnings stay visible and critical blocks keep approval unavailable.
6. ASK COMMITTEE → confirm local simulated analysis → Run SIMULATED COMMITTEE. Review both reasons, risks and confidence.
7. APPROVE DEMO PLAN or REJECT. No broker/order/transaction is created; rejected plans cannot be approved later.
8. Decisions: view date, amount, status and recorded governance. Expand a decision, then open Journal/evidence/audit one level deeper.
9. Accounts: IB, Fidelity and Schwab are READ ONLY / Not Connected. Manual Portfolio is local records. No real credential fields exist.
10. Settings → Household for context; explore6/8/10% and10/20/30-year educational wealth scenarios on Dashboard. They are SCENARIO, NOT FORECAST and do not affect the investment plan.

Existing records are preserved. History contains both approval and rejection examples created during verification. Current CNY cash is distinct from the next planned monthly contribution. Performance metrics without trusted history stay Not available.

Developer start/stop remains `./scripts/start-owner-preview.sh` / `./scripts/stop-owner-preview.sh`; stop preserves volumes and never touches other projects. Do not enter real credentials or copy this Preview DB into LIVE.

## Review round 2

Start with ACTION REQUIRED at http://localhost:3802. The authorized DEMO strategy is
50/30/10/10, with AAPL and BRK.B at zero target. Current holdings are independent.
The unchanged 20% concentration rule honestly blocks this example. Do not expect
an approval button to become enabled while concentration or required coverage fails.

Committee navigation opens the six-perspective simulated discussion. Ask why VTI
receives capital, the strongest opposition, and which evidence is missing. Macro is
NOT EVALUATED and confidence NOT AVAILABLE. This discussion is not completed governance.
Modification execution is deferred and cannot bypass fresh candidate review.

Old approved/rejected DEMO records remain historical records of their original configurations.
Restart preserves the new strategy and any subsequent explicitly saved Owner edits.
