# Action-Space Gap Analysis — ATO pack, External Cross-Check (2026-06-04)

**What this is:** output of [action-space-gap-analysis-prompt.md](action-space-gap-analysis-prompt.md) run on an **independent LLM** against the [04-ato-domain-pack.md](04-ato-domain-pack.md) Tool schema (original Artifact 2 + v2 additions). The independent anchor required by [02 §4A](02-ppa-and-taxonomy.md), applied to the action space.

**External anchors used:** OWASP credential-stuffing & Authentication Cheat Sheet, NIST SP 800-63B digital identity, FTC hacked-account recovery, PayPal public unauthorized-transaction flow, CFPB Regulation E liability, FinCEN SAR confidentiality (FIN-2012-A002), card dispute reason-code practice.

**Status:** candidate list for human/SME review (generation/external proposes; SME disposes). Not yet integrated. Verdict: **"directionally strong but not operationally sufficient."**

---

## ⚠️ Cross-cutting findings (affect the CONTRACT + ALL packs, not just ATO)
These are the most important — they're defects in how we applied our own canonical standard:

1. **Side-effect enum mismatch.** Packs use `READ-ONLY` / `MONEY-MOVEMENT` (hyphens) and combined labels like `WRITE / EXTERNAL`; the canonical standard ([pack_schema.json](pack_schema.json)) requires single underscore enums `READ_ONLY | WRITE | MONEY_MOVEMENT`. → normalize everywhere; add a separate `sends_external_message: bool` instead of an `EXTERNAL` label.
2. **Return fields not classified.** Most tool returns lack the required per-field `{classification, customer_disclosable}` ([contract.md](contract.md) §8). Detection signals (`trust_score`, `z_score`, `baseline_count`, velocity metrics, `shared_signal`, sanctions `matches[]`, `requires_compliance_review`) must be `detection_signal/customer_disclosable:false`; counterparty IDs/IPs/devices `internal_pii/false`. **Safety-critical** (prevents SAR/detection/PII leakage).
3. **`approver_id` ≠ dual control.** Sensitive actions should require a scoped, expiring **`approver_token`** validated by a separate tool — not a free-text/numeric id that can be hallucinated or socially engineered.
4. **Missing a safe-message layer.** Policies forbid leaking detection/SAR data, but no tool enforces it → add a `generate_safe_customer_message` / disclosure-filter (applies to every pack).
5. **`gated_by` not a schema field.** Add `gated_by:{policy_ids, required_verified_level?, requires_dual_control?, allowed_pre_verification?}` to the tool schema so guardrails are machine-checkable.
6. **Protective vs restorative distinction.** Protective actions (revoke sessions) may run pre-verification; restorative actions (reset MFA, release hold, restore contact) need stronger proof — encode this.

→ **These belong in `contract.md` / `pack_schema.json` and propagate to packs 04/06/07.**

---

## ATO-specific verdict
Right backbone (step-up, device-graph, velocity, holds, reverse/void, claim, escalation, session-revoke, credential/MFA reset, contact quarantine, change inventory) — but missing the tools that make those **safe and feasible**.

### Top missing tools (high priority)
`get_transaction_details` · `get_contact_methods_and_channel_risk` · `select_clean_verification_channel` · `cancel_or_recall_pending_payment` · `create_unauthorized_claim_bundle` · `remediate_account_change` · `validate_dual_control_approval` · `generate_safe_customer_message` · `revoke_third_party_and_device_trust` · `enable_post_recovery_monitoring`.

### All 18 proposed tools (name — purpose — side_effect — priority)
1. `get_contact_methods_and_channel_risk` — enumerate channels + clean-channel eligibility before step-up — READ_ONLY — high
2. `select_clean_verification_channel` — pick a verification route excluding attacker/recent channels — READ_ONLY — high
3. `initiate_document_liveness_verification` — fallback proofing when no clean OTP/passkey — WRITE — high
4. `get_identity_verification_result` — read doc/liveness/manual proofing outcome — READ_ONLY — high
5. `get_transaction_details` — status/rail/funding/counterparty; pending-vs-settled (ATO-P05 depends on it) — READ_ONLY — high
6. `cancel_or_recall_pending_payment` — stop/recall in-flight unauthorized send/withdrawal/transfer/void — MONEY_MOVEMENT — high
7. `create_unauthorized_claim_bundle` — one claim covering multiple txns in the same incident + evidence — WRITE — high
8. `evaluate_unauthorized_payment_liability` — customer-safe Reg E/eligibility timing — READ_ONLY — high
9. `remediate_account_change` — undo malicious changes (restore/remove email/phone/payee/funding/payout/address/API key) — WRITE — high
10. `revoke_third_party_and_device_trust` — revoke OAuth/API tokens, trusted devices, remembered browsers, app passwords — WRITE — high
11. `invalidate_recovery_factors` — disable attacker backup codes/recovery channels/passkeys/authenticator seeds — WRITE — high
12. `enable_post_recovery_monitoring` — enhanced monitoring/cooling controls after recovery — WRITE — med-high
13. `validate_dual_control_approval` — validate a scoped, expiring approver token — READ_ONLY — high
14. `capture_phishing_artifact` — store URL/email/SMS/screenshot/sender + takedown referral — WRITE — med-high
15. `apply_login_protection` — temp lock / step-up-on-login / rate-limit (credential-stuffing, brute-force) — WRITE — med-high
16. `generate_safe_customer_message` — approved language for holds/proofing-fail/AML/claim without leaking SAR/detection — READ_ONLY — high
17. `send_customer_security_notification` — post-recovery instructions/confirmations on a clean channel — WRITE — med-high
18. `build_fraud_investigation_evidence_package` — internal-vs-customer-safe evidence bundle for escalations — WRITE — high

### Key structural/metadata fixes to existing ATO tools
- `identity_step_up`: arg `channel` → `channel_target`/`channel_id` (so ATO-P03 is enforceable); sourced from contact-method lookup; fix `WRITE / EXTERNAL` label; classify returns. Promote `identity_step_up_verify` to a full tool.
- `account_graph_device_lookup`: classify device/session/IP/trust_score as `internal_pii`/`detection_signal` false; add contact methods (or split out).
- `velocity_check`: all metrics `detection_signal/false`; add brute-force/credential-stuffing action route.
- `sanctions_watchlist_check`: `matches[]`/`screening_id`/`requires_compliance_review` → not customer-disclosable; fix `WRITE / EXTERNAL`; pair with safe-message + doc collection.
- `place_hold`: multi-scope array (ensure SENDS+WITHDRAWALS), idempotency key, `gated_by: ATO-P01`, classify returns.
- `release_hold`: replace `approver_id` with validated `approver_token`; require verified ≥2 + dual-control for high-risk/AML-linked.
- `reverse_or_refund_transaction`: split into rail-specific cancel/recall vs refund/void; require prior `get_transaction_details`; add idempotency + approver token; classify `seller_payable_breakdown`/`links`.
- `send_verification_challenge`: split into confirm-activity / doc-liveness / step-up; model async lifecycle (ISSUED/PENDING/EXPIRED/CONFIRMED/DENIED).
- `file_unauthorized_claim`: support claim bundle + evidence + dates + funding source + jurisdiction; ETA jurisdiction-derived not hard-coded.
- `escalate_to_human`: separate `customer_safe_summary` vs `internal_summary`; classify `sla_target`.
- `revoke_all_sessions`: add scopes (sessions/refresh-tokens/OAuth/API/remembered-devices/passkeys).
- `force_credential_reset`: add `delivery_channel_id` + clean-channel enforcement + reset-link invalidation + compromised-password screening.
- `reset_mfa`: add list/remove/invalidate-backup-codes/re-enroll lifecycle.
- `quarantine_contact_method`: needs `channel_id` from a lookup; richer return (quarantine_id/effective_at/customer_safe_summary).
- `list_recent_account_changes`: classify every change field; pair with `remediate_account_change`.

### Scenario coverage (all PARTIAL — none fully solvable yet)
Every v2 ATO subtype came back **PARTIAL**: report-compromise/recover-access, unauthorized-dispute, credential-change-remediation, high-confidence-ATO-with-loss, credential-stuffing, phishing, SIM-swap, session-hijack/token-theft, MFA-bypass, support-channel-SE, brute-force. Gaps map to the missing tools above.

### Safety & disclosure issues (top)
Clean-channel enforcement under-tooled (can force an ATO-P03 breach); money-movement actions lack preconditions/idempotency/approval; `approver_id` is not real dual-control; detection signals returned but unclassified; SAR/sanctions leakage risk; counterparty PII leakage; no safe-message layer; protective vs restorative not distinguished; no post-recovery monitoring; no internal-vs-customer evidence boundary.

### Edge / scope-dependent (for SME — may sit outside the ATO CX pack)
Card-network reason-code representment (→ disputes pack 07); Reg E liability calculator; telecom/SIM-swap carrier verification; population-level credential-stuffing/bot controls; merchant API-key rotation.

### Sources (external reviewer)
OWASP Credential Stuffing & Authentication Cheat Sheet; NIST SP 800-63B; FTC hacked-account recovery; PayPal unauthorized-transaction help; CFPB Reg E §1005.6; FinCEN FIN-2012-A002 (SAR confidentiality); card reason-code guides.
