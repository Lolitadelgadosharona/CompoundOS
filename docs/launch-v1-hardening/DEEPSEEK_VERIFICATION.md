# DeepSeek verification

VERIFIED FACT: REQUIRED production dependency for V1 contribution Committee completion and human approval; the route invokes DeepSeek directly and offers no production approval fallback. Missing credentials or configured pricing fails closed. Existing research generation separately uses its governed provider router and is not a DeepSeek fallback for approving a contribution plan.

Credential path: macOS Keychain service compoundos-deepseek/account compoundos first; explicitly allowed environment fallback second. Availability was checked as a boolean only: false. No secrets were printed or stored.

REAL PROVIDER: NOT VERIFIED — CREDENTIALS/ENVIRONMENT REQUIRED. This is a launch blocker, not proof that code hardening failed. Synthetic adapter tests verify payload JSON mode, timeout/failure behavior, malformed/truncated output, invalid usage, citations, numeric assertions and duplicate claims at UNIT/INTEGRATION strength only.

Owner launch verification must pin/verify the actual supported model and input/output pricing (COMPOUNDOS_DEEPSEEK_INPUT_USD_PER_MILLION / COMPOUNDOS_DEEPSEEK_OUTPUT_USD_PER_MILLION), install credentials safely, confirm disclosure, execute a minimal real current-evidence evaluation, validate returned model/usage/cost and all references, and retain redacted evidence. Current default model remains the existing deepseek-chat; its availability is not asserted. Current [official API documentation](https://api-docs.deepseek.com/api/create-chat-completion/) and [model/pricing documentation](https://api-docs.deepseek.com/quick_start/pricing/) must be consulted before configuration. No invented price is hardcoded.

Evidence is preserved in the Owner review package. UNIT and synthetic PostgreSQL INTEGRATION results are not real-provider or production evidence. No production migration, deployment, broker connection, trade, push or merge was performed.
