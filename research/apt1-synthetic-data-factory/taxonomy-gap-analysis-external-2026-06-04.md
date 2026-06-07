# Taxonomy Gap Analysis — External Cross-Check (2026-06-04)

**What this is:** the output of running [taxonomy-gap-analysis-prompt.md](taxonomy-gap-analysis-prompt.md) on an **independent LLM** against [02-ppa-and-taxonomy.md](02-ppa-and-taxonomy.md). This is the **independent-anchor validation** required by [02 §4A](02-ppa-and-taxonomy.md) to break the generation-circularity (the taxonomy and packs were AI-generated from the same source; this check uses *external* published frameworks).

**Status:** candidate list for human/SME review (per the "generation proposes; an outside source disposes" rule). Not yet integrated into the taxonomy — integration pending the scope decision (CX customer/merchant fraud vs enterprise-wide) and v2 authoring.

**External frameworks used as anchors:** ACFE Fraud Tree (corruption / asset misappropriation / financial-statement fraud); FATF/FinCEN AML typologies (placement/layering/integration, PML, TBML, CVC, mules, structuring); UK Finance/PSR APP scam categories (purchase, investment, romance, advance-fee, invoice/mandate, CEO, police/bank impersonation, other impersonation); Visa/Mastercard/Stripe dispute & reason-code categories; OWASP ATO vectors; FBI/FTC scam guidance; NRF return-fraud patterns; Federal Reserve synthetic-identity toolkit.

---

## Headline verdict
A **solid skeletal taxonomy, but not operationally complete.** It covers the obvious first-order buckets (ATO, BIN/card testing, synthetic identity, mules/AML, friendly fraud, merchant bust-out/collusion, APP scams, disputes, refunds, checkout, holds/reserves, PPA) but is **materially incomplete** against independent frameworks — many standard categories are missing or collapsed into vague buckets.

### Highest-priority missing / under-modeled (high confidence)
1. **APP scam subtypes** — purchase, investment/crypto, romance, advance-fee, invoice/mandate, CEO/BEC, police/bank impersonation, safe-account. (Our pack 06 currently treats APP as one bucket.)
2. **Payment-instrument fraud beyond ATO** — stolen card, stolen bank account, wallet-token provisioning, ACH/direct-debit misuse, CNP stolen-card purchase.
3. **Card-network reason-code taxonomy + representment** — Fraud / Authorization / Processing-error / Consumer-dispute classes. (Affects pack 07.)
4. **Money-mule lifecycle & recruitment** — unwitting / witting / complicit; account rental/sale.
5. **AML/CFT expansion** — placement/layering/integration staging, TBML, crypto/CVC laundering, shell/front companies, sanctions/CFT/proliferation.
6. **New-account / application fraud** distinct from synthetic identity.
7. **ATO vector taxonomy** — credential stuffing, phishing, SIM-swap, session hijack, MFA bypass. (Affects pack 04.)
8. **Refund/return-abuse subtypes** — wardrobing, empty-box, switch, FTID, refund-without-return.
9. **Merchant risk beyond bust-out** — transaction laundering, fake storefront/non-delivery, reserve evasion.
10. **Promo/referral abuse, loyalty/stored-value fraud, first-party fraud beyond "friendly fraud", reseller/triangulation fraud.**

### Edge / scope-dependent (decide explicitly)
ACFE **internal/employee/vendor/procurement fraud** and **financial-statement fraud**; detailed crypto typologies (if crypto is in product scope); vulnerability/coercion as a first-class node vs cross-cutting tag; jurisdiction-specific reimbursement regimes beyond UK PSR / Reg E.

### Most important STRUCTURAL insight
The current tree **mixes different dimensions as peer nodes** (actor vs attack-vector vs payment-rail vs customer-claim vs ops-queue). Recommended fix: a **primary tree + orthogonal cross-cutting tags** — `actor, victim, rail, instrument, scam-subtype, attack-vector, ML-lifecycle-stage, transaction-status, jurisdiction, reimbursement-regime, recovery-state, CX-vs-INT-authority`. Also: model **"unauthorized transaction" as a claim-type with cause tags** (ATO / stolen card / stolen bank / wallet token / merchant error / first-party) rather than duplicating it under both Fraud and Commerce.

---

## Full external analysis (verbatim)

> Reviewer treated the uploaded taxonomy's quoted node names as the only evidence of coverage. The taxonomy itself warns it is AI-generated, public-source-derived, and not validated against internal data or SME review.

### A. Coverage map
| Reference category | Mapped to our node? (quote, or MISSING/PARTIAL) | Notes |
|---|---|---|
| ACFE corruption | PARTIAL: "Merchant Collusion / Bust-Out" | Covers buyer-seller collusion, but not bribery, kickbacks, conflicts of interest, bid rigging, illegal gratuities, economic extortion. |
| ACFE asset misappropriation | PARTIAL: "Refund / Chargeback Abuse ('friendly fraud')" | Covers customer-side abuse but misses employee/vendor/payroll/cash/inventory theft. |
| ACFE financial statement fraud | MISSING | No node for accounting misstatement, falsified merchant financials, reserve underwriting deception. |
| ACFE conflicts of interest / kickbacks | PARTIAL: "coordinated buyer-seller pair analysis" | Only external commerce collusion, not employee/vendor procurement conflicts. |
| ACFE fraudulent disbursements / billing | MISSING | Relevant to internal ops and merchant payout manipulation. |
| AML placement | PARTIAL: "Mule / AML (money laundering)" | AML exists, but placement not an explicit dimension. |
| AML layering | PARTIAL: "fan-in/fan-out & structuring network detection" | Misses chain-hopping, crypto conversion, shell entities, multi-rail layering. |
| AML integration | MISSING | No node for return of funds as apparently legitimate proceeds. |
| Structuring / smurfing | PRESENT: "fan-in/fan-out & structuring network detection" | Correctly internal; lacks customer-facing inquiry/limitation-appeal posture. |
| Money mule networks | PRESENT/PARTIAL: "Mule / AML"; "duped-mule customer contact" | Misses recruitment, account rental/sale, witting vs unwitting vs complicit. |
| Trade-based money laundering | MISSING | FATF treats TBML as disguising proceeds via trade transactions. |
| Professional money laundering networks | MISSING | FATF PML typology: specialized actors/services/networks. |
| Shell/front companies / beneficial-owner concealment | MISSING | Important for merchant onboarding, transaction laundering, AML. |
| Terrorist financing / CFT | MISSING | AML present, but not CFT, sanctions, proliferation, high-risk geographies. |
| Crypto/CVC laundering | MISSING | No crypto-specific AML branch. |
| APP fraud — generic | PRESENT: "Scams / APP Fraud" | Correct high-level bucket. |
| APP purchase scam | PARTIAL: "post-send scam report" | No subtype. |
| APP investment scam | PARTIAL: "post-send scam report" | No investment/crypto subtype. |
| APP romance scam | PARTIAL: "post-send scam report" | No grooming subtype. |
| APP advance-fee scam | PARTIAL: "post-send scam report" | No fee-before-benefit subtype. |
| APP invoice / mandate scam | PARTIAL: "post-send scam report" | No redirection/mandate-change subtype. |
| APP CEO fraud / exec impersonation | PARTIAL: "post-send scam report" | No BEC subtype. |
| APP police/bank impersonation | PARTIAL: "pre-send scam interdiction / warning"; "post-send scam report" | No safe-account/emergency-authority subtype. |
| APP safe-account scam | PARTIAL: "pre-send scam interdiction / warning" | Deserves own node ("move money to protect it"). |
| P2P scam | PARTIAL: "Scams / APP Fraud" | Needs P2P distinctions: F&F, marketplace, QR, handle impersonation. |
| Gift-card scam | MISSING | No gift-card payment-instrument/scam node. |
| Crypto off-ramp scam | MISSING | Investment/romance/job scams guiding victim to buy/send crypto. |
| Card testing / BIN attack | PRESENT: "Card-Testing / BIN Attacks" | Good. |
| Card-not-present fraud | PARTIAL: "victim whose card appears in a test attack"; "unauthorized-transaction claim intake" | Missing CNP stolen-card purchase outside BIN testing. |
| Lost/stolen/counterfeit card | MISSING/PARTIAL | Taxonomy mostly digital-account oriented. |
| Card authorization errors | PARTIAL: "payment-failure / decline help"; "gateway / transaction-decline troubleshooting" | Not mapped to chargeback reason-code class. |
| Card processing errors | PARTIAL: "refund request / status"; "payment-failure / decline help" | Missing duplicate processing, incorrect amount, paid-by-other-means. |
| Card consumer disputes | PARTIAL: "item-not-received (INR)"; "significantly-not-as-described (SNAD)"; "subscription / recurring-payment cancel" | Misses credit-not-processed, duplicate, cancelled recurring, non-receipt of cash/load value. |
| Mastercard no-cardholder-authorization | PARTIAL: "unauthorized-transaction claim intake" | No explicit network reason-code mapping (e.g. MC 4837). |
| Credential stuffing | PARTIAL: "Account Takeover (ATO)" | No vector subtype. |
| Brute-force login | PARTIAL: "Account Takeover (ATO)" | No vector subtype / bot-lockout implications. |
| Phishing / social-engineering ATO | PARTIAL: "report-compromise / recover-access" | No acquisition-vector node. |
| SIM-swap / telecom takeover | MISSING/PARTIAL | No explicit node. |
| Session hijack / token theft | MISSING/PARTIAL | ATO bucket too coarse. |
| MFA bypass / MFA fatigue | MISSING/PARTIAL | ATO bucket too coarse. |
| Synthetic identity | PRESENT: "Synthetic Identity" | Should separate onboarding, sleeper, bust-out, child/SSN misuse, synthetic-vs-stolen. |
| New-account / application fraud | PARTIAL: "onboarding KYC anomaly detection" | Not equal to synthetic ID; stolen-ID, mule accounts, promo farms missing. |
| First-party fraud | PARTIAL: "Refund / Chargeback Abuse ('friendly fraud')" | Too narrow; includes intentional non-payment, false claims, credit abuse. |
| Promo / bonus / referral abuse | MISSING | No incentives-abuse node. |
| Refund / return abuse | PARTIAL: "Returns & Refunds"; "Refund / Chargeback Abuse" | No wardrobing, empty-box, switch, FTID, refund-without-return. |
| Reseller / triangulation fraud | MISSING | Fraudster sells goods, buys with stolen instrument, ships to real buyer. |
| Merchant bust-out | PRESENT: "Merchant Collusion / Bust-Out" | Needs subtypes: reserve evasion, fake fulfillment, volume spike, withdrawal sprint, linked merchants. |
| Merchant collusion | PRESENT: "Merchant Collusion / Bust-Out"; "coordinated buyer-seller pair analysis" | Good high-level coverage. |
| Transaction laundering | MISSING/PARTIAL | No explicit hidden-merchant-of-record node. |
| Chargeback fraud | PRESENT/PARTIAL: "Refund / Chargeback Abuse" | Not aligned to reason codes, representment, compelling evidence, issuer-acquirer workflow. |
| Loyalty-points fraud | MISSING | No stored-value/rewards node. |
| Payment-instrument fraud | PARTIAL: "payment-method management"; "unauthorized-transaction claim intake" | Missing stolen cards, ACH misuse, wallet token provisioning, account-linking, bank-return fraud. |

### B. Proposed additions (the gaps)
1. **APP purchase scam** — Fraud → Scams/APP → Purchase scam. Victim pays for goods/services that don't exist/won't be delivered. CX/INT. High/high. Actions: scam-intake wizard, payment trace, beneficiary risk flag, recall attempt, eligibility/reimbursement check, safety coaching.
2. **APP investment/crypto-investment scam** — induced transfer to fake investment/trading/crypto. CX/INT. High/high. Actions: stop-future-payments, beneficiary escalation, crypto-address capture, timeline, vulnerability flag, external-report guidance.
3. **APP romance/relationship scam** — emotional trust → payments. CX/INT. High/high. Actions: non-judgmental scripts, pattern review, repeated-payment hold, trusted-contact, beneficiary flag, vulnerability escalation.
4. **APP impersonation/safe-account scam** — impersonates bank/platform/gov/police → "protect your money." CX/INT. High/high. Actions: real-time scam break, official-channel verification, freeze/hold, recall, impersonation report.
5. **APP invoice/mandate redirection** — spoofed supplier comms redirect a legit payment. CX/INT. High/high. Actions: invoice evidence capture, counterparty verification, recall, beneficiary restriction referral, business-account review.
6. **CEO fraud / BEC** — impersonate exec/vendor/payroll to induce payment. CX/INT. High/high. Actions: high-value escalation, recall, business-admin security review, mailbox-compromise advice, audit-log export.
7. **APP advance-fee / job / loan / prize** — upfront fee to unlock promised benefit. CX. High/high. Actions: payment trace, classification, future-payment block/warning, report recipient, education.
8. **Gift-card scam** — buy gift cards & share codes as payment. CX/INT. High/high. Actions: capture brand/code/timing, advise issuer, account-compromise review, report, coaching.
9. **Crypto off-ramp / CVC scam payment** — coached to buy crypto/use ATM and send to scammer wallet. CX/INT. High/high. Actions: capture wallet/exchange, restrict risky sends, explain irreversibility, external reporting, AML referral.
10. **Mule recruitment & lifecycle** — unwitting/witting/complicit receive→move→withdraw→forward proceeds. CX/INT. High/high. Actions: mule-intake questionnaire, activity freeze/escalation, SAR-safe language, do-not-disclose rules, closure/appeal path.
11. **AML stage classification (placement/layering/integration)** — tag behavior by ML stage. INT. High/high. Actions: escalation, safe disclosure, document request/status-only scripts.
12. **Trade-based ML / invoice manipulation** — over/under-invoicing, false trade docs, phantom goods. INT. High/high. Actions: merchant document request, trade-doc upload, escalation, non-disclosure guardrails.
13. **Transaction laundering / hidden merchant-of-record** — processing for undisclosed/prohibited third parties. CX/INT. High/high. Actions: merchant-info request, website/product evidence, limitation appeal, reserve/hold explanation.
14. **Sanctions / CFT / proliferation-finance screening** — blocked persons, high-risk geos, TF indicators, evasion. INT + CX status. High/high. Actions: collect ID/business docs, generic compliance-review status, never reveal screening logic, route to sanctions ops.
15. **Card-network dispute reason-code taxonomy** — fraud/authorization/processing-error/consumer-dispute families. CX/INT. High/high. Actions: reason-code lookup, evidence checklist, representment packet, deadline calculator, status updates.
16. **Payment-instrument fraud** — unauthorized use/linking of cards/bank/wallet/tokens/direct-debit. CX/INT. High/high. Actions: remove instrument/token, unauthorized claim, advise issuer/bank, device/token audit.
17. **CNP stolen-card purchase fraud** — stolen card credentials used online w/o owning the account. CX/INT. High/high. Actions: identify merchant/payment, unauthorized claim, instrument risk flag, issuer advice.
18. **ATO vector taxonomy** — credential-stuffing/phishing/SIM-swap/session-hijack/MFA-bypass/device-compromise/support-channel SE. CX/INT. High/high. Actions: vector capture, password/session reset, device logout, MFA reset, contact-method quarantine, credential-change inventory.
19. **New-account / application fraud** — fraudulent opening via stolen/synthetic/mule/manipulated identity. CX/INT. High/high. Actions: KYC intake, identity-theft flow, limitation appeal, victim remediation.
20. **First-party fraud beyond disputes** — account holder intentionally misrepresents for gain. CX/INT. High/high. Actions: neutral evidence capture, no-accusation scripts, dispute limitation/escalation, repeat-abuse routing.
21. **Promo / referral / bonus abuse** — exploit sign-up/referral/coupons via fake/multiple accounts or collusion. CX/INT. High/medium-high. Actions: explain ineligibility, appeal info, route to abuse ops, account-link review.
22. **Loyalty / points / stored-value fraud** — theft/unauthorized redemption/transfer/sale of points/credits/wallet value. CX/INT. High/medium. Actions: freeze/reverse redemption, restore-points policy check, ATO recovery, redemption audit.
23. **Return/refund abuse subtypes** — wardrobing/empty-box/switch/bricking/fake-tracking/refund-without-return/serial claims. CX/INT. High/high. Actions: return-tracking review, proof-of-return upload, merchant evidence, neutral denial/appeal.
24. **Reseller / triangulation fraud** — sell to real buyer, buy with stolen instrument, ship to buyer. CX/INT. High/high. Actions: link buyer/merchant cases, shipping/order evidence, stolen-instrument claim, merchant representment.
25. **Seller non-delivery / fake storefront** — merchant takes payment w/o intent/capacity to fulfill, then withdraws. CX/INT. High/high. Actions: buyer claim at scale, merchant hold/reserve, shipping evidence, payout freeze, mass-claim handling.
26. **Merchant reserve evasion / linked-merchant cycling** — linked accounts to evade holds/reserves/caps/limitations. INT + CX appeals. High/medium-high. Actions: limitation appeal, document request, linked-account escalation.
27. **Insider / employee fraud & collusion** — staff/contractors abuse access/approvals/refunds/dispute decisions. INT. High/medium-high. Actions: CX intake/status only; internal audit logs, access review, internal-investigations referral.
28. **Financial-statement / merchant underwriting misrepresentation** — falsify financials/volume/ownership for better terms. CX/INT. Medium-high/medium. Actions: document intake, authenticity escalation, reserve/limitation appeal.
29. **Vendor / procurement / billing fraud** — fake vendors, inflated/duplicate invoices, kickbacks. INT. Medium/low-medium. Actions: not front-line; internal report intake, evidence preservation, whistleblower routing.
30. **Customer vulnerability / coercion overlay (cross-cutting)** — elder abuse, coercive control, trafficking, cognitive vulnerability in scam/mule cases. CX/INT. Medium-high/medium-high. Actions: break-the-spell script, private-channel confirmation, trusted-contact/legal options, vulnerability escalation.

### C. Structural fixes
- **Over-compressed "Scams / APP Fraud"** → split into the ~12 subtypes (purchase, investment, romance, advance-fee, invoice/mandate, CEO/BEC, police/bank impersonation, other impersonation, safe-account, P2P marketplace, gift-card, crypto off-ramp).
- **Overlap: "unauthorized-transaction dispute (post-ATO)" vs "unauthorized-transaction claim intake"** → model unauthorized transaction as a **claim type with cause tags** (ATO / stolen card / stolen bank / wallet token / merchant error / first-party).
- **Misleading "Refund / Chargeback Abuse ('friendly fraud')"** → rename "First-Party / Refund / Chargeback Abuse"; subtypes: chargeback fraud, return abuse, refund abuse, promo abuse, buyer-policy abuse.
- **Under-scoped "Mule / AML"** → rename parent "AML/CFT & Illicit Finance"; mule networks become one child; add FATF stages, TBML, PML, shell/front companies, crypto, CFT/sanctions.
- **Missing merchant-risk layer** → add "Merchant Risk & Abuse" subdomain: bust-out, collusion, transaction laundering, fake storefront, reserve evasion, prohibited activity.
- **CX/INT tag issues** (holds/reserves; verification queue) → dual-layer model: decision node INT, inquiry/appeal/status node CX, linked explicitly.
- **Wrong abstraction: "Card-Testing/BIN Attacks" (attack) vs "victim whose card appears in test attack" (case)** → split attack-detection vs customer-harm/claim; add "Payment Instrument Fraud" parent.
- **Disputes need reason-code alignment** → add "Card Network Disputes" with Visa/MC categories + evidence/representment.
- **PPA** → keep under Commerce; don't use as a fraud anchor until internal expansion confirmed.
- **Orthogonal dimensions** → taxonomy mixes actor/vector/rail/claim/queue as peers; add cross-cutting tags: actor, victim, rail, instrument, scam-subtype, attack-vector, ML-lifecycle-stage, jurisdiction, reimbursement-regime, recovery-state, CX-vs-INT-authority.
- **Action-state granularity** → add transaction lifecycle/status (pending/completed/settled/withdrawn/crypto-converted/card-funded/bank-funded/cross-border) + action-eligibility matrix.
- **Customer-safety overlay** → vulnerability/coercion cross-cutting flag.
- **Internal fraud** → decide scope explicitly (customer/merchant risk only vs enterprise).
- **Ambiguous Fraud-vs-Commerce split** → consider top-level domains: Customer Account Security, Payment Instrument Fraud, Scams/APP, Disputes/Claims, Merchant Risk, AML/CFT, Internal Fraud, Commerce Support.

### Sources (from the external reviewer)
ACFE Fraud Tree; FATF PML, TBML, Virtual-Assets red-flags; FinCEN structuring, CVC advisory, imposter/mule advisory; UK Finance Annual Fraud Report; FTC scams / gift-card / crypto guidance; Stripe dispute reason codes; Visa Dispute Management Guidelines; Mastercard reason-code references; OWASP credential stuffing; Fed Synthetic Identity toolkit; NRF return-fraud; Stripe first-party fraud. (Full URLs in chat record.)
