# Action-Space Gap Analysis — APP/Scams pack (06), External Cross-Check (2026-06-04)

**What this is:** output of [action-space-gap-analysis-prompt.md](action-space-gap-analysis-prompt.md) on an independent LLM against [06-app-scams-domain-pack.md](../docs/06-app-scams-domain-pack.md) (Tool schema + v2 additions). Second of three pack reviews. Candidate list for SME review; not yet integrated.

**External anchors:** UK Finance APP scam categories, UK PSR reimbursement regime (live 7 Oct 2024; 5/35-business-day handling, claim cap/excess, vulnerable-consumer exception, stop-the-clock), US CFPB Reg E (authorized scam ≠ unauthorized EFT), PayPal Friends&Family/Purchase-Protection, FTC crypto/romance/gift-card guidance, FinCEN SAR confidentiality (FIN-2012-A002).

**Verdict:** **PARTIAL, not production-sufficient** — good conceptual spine, under-specified exactly where APP ops are most sensitive.

---

## Cross-cutting findings — CONFIRMS the ATO review (→ contract + all packs)
Same canonical-layer defects, independently found again:
1. **Enum mismatch** — pack uses `WRITE / EXTERNAL`, `MONEY-MOVEMENT / WRITE`; standard requires `READ_ONLY | WRITE | MONEY_MOVEMENT` (+ separate `sends_external_message: bool`).
2. **Return fields mostly unclassified** — `beneficiary_reported_count`, `risk`, `coercion_indicators`, `vulnerability_indicators`, recall failure reasons, sanctions output, beneficiary IDs must be `customer_disclosable:false`.
3. **`gated_by` not a schema field** — add it as structured metadata.
4. **No dual-control token** — sensitive MONEY_MOVEMENT (cooling-off hold, recall, future-payment block, reimbursement) need a validated `approver_token` + a `validate_dual_control_approval` tool.
5. **No safe-message layer** — add `generate_safe_scam_customer_message` (every pack needs one).
6. **NEW cross-cutting lesson — policy↔tool consistency:** SCAM-P01/P02 reference a `process_payment` action that **does not exist** in the menu → the policy is ungradable as written. (Mirrors ATO's `channel` vs `channel_target` mismatch.) **Rule to add: a policy predicate may only reference tools/fields that exist in the pack.**
7. **NEW — inherited tools not declared locally:** `escalate_to_human`, `sanctions_watchlist_check` are used by inheritance but not declared in the pack → fails the local schema standard. Decide: import/inline inherited tools per pack.
8. **NEW — my v2 refresh was incomplete:** `scam_signal_check`'s `scam_typology` enum still only has 6 values; it must cover all 11 v2 subtypes (advance-fee, safe-account, CEO/BEC, P2P, gift-card, crypto-offramp were missing from the enum even though taxonomy v2 lists them).

---

## Scam-specific top missing tools
`get_payment_context` · `suspend_or_block_payment_flow` · `document_customer_acknowledged_and_proceeded` · `classify_app_scam_subtype` · `issue_effective_scam_warning` · `create_scam_evidence_package` · `assess_psr_app_reimbursement` · `create_scam_claim_case` · `submit_beneficiary_bank_recall_package` · `get_recall_status` · `create_vulnerability_assessment` · `generate_safe_scam_customer_message` · `validate_dual_control_approval`.

### All 22 proposed tools (name — purpose — side_effect — priority)
1. `get_payment_context` — stage/rail/funding/type/jurisdiction; pre-send vs pending vs settled — READ_ONLY — high
2. `suspend_or_block_payment_flow` — stop a pre-send/in-session payment while assessing — MONEY_MOVEMENT — high
3. `document_customer_acknowledged_and_proceeded` — record the warned-and-proceeded (no-coercion) case — WRITE — high
4. `lookup_scam_warning_template` — approved subtype-specific warning + comprehension checks — READ_ONLY — high
5. `issue_effective_scam_warning` — auditable warning (version/channel/comprehension/ack) — WRITE — high
6. `classify_app_scam_subtype` — classify into the full UK-Finance taxonomy (not the reduced enum) — READ_ONLY — high
7. `submit_beneficiary_bank_recall_package` — recall + evidence + institution data — WRITE — high
8. `get_recall_status` — poll recall/cancel lifecycle + recovered amount — READ_ONLY — high
9. `create_scam_evidence_package` — screenshots/messages/invoices/URLs/wallet/gift-card/listing — WRITE — high
10. `assess_psr_app_reimbursement` — UK PSR eligibility w/ rail/dates/cap/excess/vuln/stop-clock/5-35d — READ_ONLY — high
11. `assess_authorized_vs_unauthorized_payment` — APP-scam vs unauthorized EFT/ATO routing (Reg E) — READ_ONLY — high
12. `create_scam_claim_case` — upgrade `file_scam_claim`: bundle/evidence/deadlines/jurisdiction — WRITE — high
13. `issue_reimbursement_or_goodwill_credit` — execute approved reimbursement (post-adjudication) — MONEY_MOVEMENT — high
14. `create_vulnerability_assessment` — capture vuln/coercion → specialist routing + reimbursement consequence — WRITE — high
15. `initiate_private_channel_safety_check` — move customer off scammer-controlled call; can they speak freely — WRITE — high
16. `verify_invoice_or_mandate_change` — validate supplier via known-good contact; capture evidence — READ_ONLY — med-high
17. `capture_marketplace_purchase_scam_evidence` — listing/seller/chat/payment-type for purchase/P2P — WRITE — med-high
18. `submit_giftcard_issuer_recovery_request` — issuer recovery + redemption status — WRITE — med-high
19. `submit_crypto_exchange_or_wallet_report` — report wallet/tx-hash/exchange; off-ramp irreversibility — WRITE — med-high
20. `generate_safe_scam_customer_message` — approved no-overpromise/SAR-safe language — READ_ONLY — high
21. `set_repeated_payment_intervention_plan` — bounded, reviewable repeat-victim controls — MONEY_MOVEMENT — med-high
22. `validate_dual_control_approval` — validate scoped approver token for holds/recalls/reimbursement — READ_ONLY — high

### Key structural fixes to existing tools
- `scam_signal_check`: expand `scam_typology` enum to all v2 subtypes; classify `risk`/indicators; add confidence/evidence/customer-safe explanation.
- `issue_scam_warning`: fix `WRITE / EXTERNAL`; return template id/version/timestamp/comprehension; tie to expanded subtypes.
- `place_cooling_off_hold`: accept `proposed_payment_id`/`{payee_id,amount,funding}` (pre-send has no payment_id yet); add duration caps + approver token + release criteria.
- `attempt_recall`: add rail/stage/cutoff/amount/idempotency + customer-safe status; `beneficiary_recall_request`: fix `WRITE / EXTERNAL`, add evidence/status/deadline (→ split into submit + get_recall_status).
- `assess_reimbursement_eligibility`: add UK PSR variables; split `customer_safe_basis` vs `internal_rule_basis`.
- `file_scam_claim`: add evidence/payment-ids/subtype/jurisdiction/dates/vuln/deadline.
- `capture_crypto_destination` / `capture_giftcard_details`: classify wallet/code tokens; pair with report/recovery tools; fix `WRITE / EXTERNAL`.
- `block_future_payments_to_payee`: fix `MONEY-MOVEMENT / WRITE`; add duration/scope/consent/appeal/approver token.
- `report_beneficiary`: add status/submitted_at; classify beneficiary IDs; pair with safe-message (never say "flagged as fraudster").
- `verify_official_contact`/`flag_vulnerability`: richer returns; classify sensitive vuln data; make routing explicit.
- Inherited `escalate_to_human`/`sanctions_watchlist_check`: declare/import locally with classifications.

### Safety & disclosure issues (top)
SCAM-P01/P02 ungradable (no payment-processing/block/document-proceeded action); `payment_id` dependency breaks true pre-send intervention; reimbursement eligibility dangerously under-specified for PSR; no safe-message layer; network/vuln signals unprotected; counterparty PII leakage risk (victims demand scammer details); dangerous controls lack dual-control; over-blocking of legit large payments not handled; SAR-safe handling is policy-only.

### Edge / scope-dependent (SME)
Social-platform takedown/report, trusted-contact workflow, behavioural-biometrics trigger review, law-enforcement report generation, telecom/call-status verification, blockchain analytics/risk scoring, automated outreach to non-bank wallet/exchange providers.

### Sources (external reviewer)
UK Finance APP categories & Half-Year Fraud Report; UK PSR reimbursement protections & PS25/5; CFPB Reg E EFT FAQ §1005.6; PayPal Friends&Family scams help; FTC crypto/romance/gift-card; FinCEN FIN-2012-A002.
