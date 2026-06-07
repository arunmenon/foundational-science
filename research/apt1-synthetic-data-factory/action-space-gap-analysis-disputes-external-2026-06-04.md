# Action-Space Gap Analysis — Commerce/Disputes pack (07), External Cross-Check (2026-06-04)

**What this is:** independent-LLM run of [action-space-gap-analysis-prompt.md](action-space-gap-analysis-prompt.md) against [07-commerce-disputes-domain-pack.md](07-commerce-disputes-domain-pack.md) (Tool schema + v2 additions). Third of three pack reviews. Candidate list; integrated via the consolidated pass (contract v1.1).

**External anchors:** PayPal dispute timeframes (180-day INR; SNAD 30-from-delivery/180-from-payment; F&F not covered by Purchase Protection); Visa dispute families (Fraud / Authorization / Processing Errors / Consumer Disputes); Stripe reason-code categories; Mastercard merchant rules; FinCEN SAR confidentiality (FIN-2012-A002); CFPB Reg E.

**Verdict:** **PARTIAL** — credible skeleton, not production-sufficient.

---

## Cross-cutting findings — CONFIRMS ATO + scams a THIRD time (→ contract v1.1)
1. **Enum mismatch** — pack uses `READ-ONLY` / `MONEY-MOVEMENT`; standard is `READ_ONLY | WRITE | MONEY_MOVEMENT`.
2. **Return fields unclassified** — esp. `get_repeat_disputer_score {score, band}` MUST be `detection_signal/customer_disclosable:false` (the pack's own killer example).
3. **`gated_by` not a schema field.**
4. **`issue_refund` under-gated** — no `adjudication_outcome_token`, `approver_token`, or idempotency key on a MONEY_MOVEMENT action.
5. **No safe-message layer** (`generate_safe_dispute_message`).
6. **Policy↔tool consistency** — lifecycle says refund gated on adjudication token, but no `record_adjudication_outcome` tool exists to produce it; `cause` tag exists but no `classify_unauthorized_cause`; CrossPackHandoff is a state object but no `create_cross_pack_handoff` tool. (Same bug-class as ATO/scams.)
7. **Inherited tools not declared locally** (escalate/sanctions/account-graph).

## Disputes-specific top missing tools
`classify_dispute_type` · `get_transaction_context` · `get_delivery_and_fulfillment_status` · `evaluate_purchase_protection_eligibility_v2` · `generate_safe_dispute_message` · `create_dispute_case` · `classify_unauthorized_cause` · `create_cross_pack_handoff` · `request_evidence_by_template` · `submit_classified_evidence` · `lookup_network_reason_code_requirements` · `submit_representment_packet` · `record_adjudication_outcome` · `validate_dual_control_approval` · `issue_claim_refund_or_credit`.

### All 23 proposed tools (name — purpose — side_effect — priority)
1. `classify_dispute_type` — narrative+facts → INR/SNAD/Unauthorized/processing-error/credit-not-processed/recurring/duplicate — READ_ONLY — high
2. `get_transaction_context` — full dispute-relevant txn context (role/rail/funding/item/safe-counterparty) — READ_ONLY — high
3. `get_delivery_and_fulfillment_status` — shipping/delivery/digital/service completion — READ_ONLY — high
4. `evaluate_purchase_protection_eligibility_v2` — category/payment-type/jurisdiction/exclusions — READ_ONLY — high
5. `generate_safe_dispute_message` — approved eligibility/status/denial/SAR-safe language — READ_ONLY — high
6. `create_dispute_case` — structured filing (upgrade thin `file_dispute`) — WRITE — high
7. `create_cross_pack_handoff` — formal unauthorized → ATO/instrument-fraud handoff — WRITE — high
8. `classify_unauthorized_cause` — ATO/stolen-card/stolen-bank/wallet-token/merchant-error/first-party — READ_ONLY — high
9. `request_evidence_by_template` — reason-code/type-specific evidence + deadlines — WRITE — high
10. `submit_classified_evidence` — evidence w/ file-level classification + PII detection — WRITE — high
11. `get_evidence_status` — outstanding evidence per party — READ_ONLY — med-high
12. `lookup_network_reason_code_requirements` — family+code+evidence reqs+representment eligibility — READ_ONLY — high
13. `validate_representment_packet` — completeness vs reason-code reqs — READ_ONLY — high
14. `submit_representment_packet` — submit to acquirer/network — WRITE — high
15. `get_representment_status` — representment/pre-arb/arbitration outcome+liability — READ_ONLY — high
16. `record_adjudication_outcome` — back-office decision + outcome token — WRITE — high
17. `validate_dual_control_approval` — scoped approver token for refund/goodwill/override — READ_ONLY — high
18. `issue_claim_refund_or_credit` — controlled refund (upgrade `issue_refund`) — MONEY_MOVEMENT — high
19. `verify_refund_or_credit_status` — refund/ARN/seller-debit status — READ_ONLY — med-high
20. `validate_processing_error` — duplicate/amount-mismatch/auth-capture/paid-by-other-means — READ_ONLY — med-high
21. `get_subscription_or_recurring_billing_context` — cancelled-recurring/subscription disputes — READ_ONLY — med-high
22. `analyze_return_refund_abuse_signals` — internal abuse indicators (never disclosed) — READ_ONLY — med-high
23. `append_dispute_audit_event` — explicit audit log (DSP-P10) — WRITE — high

### Key structural fixes to existing tools
- `get_transaction` → `get_transaction_context` (split safe-display vs internal counterparty id).
- `check_filing_window`: needs delivery/fulfillment date (SNAD); classify basis.
- `check_protection_eligibility`: coarse enum → category/payment-type/jurisdiction/exclusions + safe vs internal basis.
- `file_dispute`: thin → `create_dispute_case`; for UNAUTHORIZED require `cause` + `create_cross_pack_handoff` (not a buyer-protection filing).
- `request_evidence`/`submit_evidence` → templated + classified versions.
- `get_repeat_disputer_score`: classify `score`/`band` detection_signal:false; internal-routing only (DSP-P09 neutrality).
- `escalate_to_adjudication`: split `customer_safe_summary` vs `neutral_internal_summary`; neutral template.
- `issue_refund` → `issue_claim_refund_or_credit` with `adjudication_outcome_token` + `approver_token` + idempotency.
- `lookup_reason_code` → `lookup_network_reason_code_requirements` (define network enum; add evidence reqs/representment eligibility).
- `get_dispute_deadline`: add RFI/pre-arb/arbitration stages, timezone, stop-clock.
- `build_representment_packet`: add validate + submit + status tools.

### Safety & disclosure issues (top)
Repeat-disputer score leakage (highest immediate risk); `issue_refund` under-gated; counterparty PII not separated; SAR confidentiality policy-only (needs schema classification + safe-message); reason-code tooling too shallow; representment incomplete (build≠submit≠track); unauthorized routing mechanically incomplete; eligibility can over-promise ("eligible" ≠ "will win"); evidence lacks classification; neutrality not operationalized (free-text adjudication summary can encode bias).

### Edge / scope-dependent (SME)
Marketplace evidence ingestion, package-weight/empty-box analysis, FTID/return-label fraud scoring, carrier API automation, seller reserve/hold integration, buyer/seller mediation chat, external SNAD appraisal, law-enforcement reporting, automated appeal/reopen.

### Sources (external reviewer)
PayPal dispute-filing timeframes & F&F help; Visa Dispute Management Guidelines; Stripe reason codes; Mastercard merchant guide; FinCEN FIN-2012-A002; CFPB Reg E.
