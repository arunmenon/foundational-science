# PPA Disambiguation + Refined Fraud / Commerce Domain Taxonomy

**Date:** 2026-06-04
**Status:** Research synthesis + taxonomy spec — for review
**Grounding:** [00-deep-research-apt1.md](00-deep-research-apt1.md) (APT-1 first principles) · [01-fraud-cx-factory-design.md](01-fraud-cx-factory-design.md) (factory architecture, domain-pack contract, ATO reference pack)
**Scope:** (1) Resolve what "PPA" most likely means and where it belongs in the taxonomy; (2) present the full refined Fraud + Commerce (+ PPA) domain → subdomain → sub-bucket tree, mark CX vs internal, and specify how domain packs compose via a shared base-policy library.

> ⚠️ **Hard grounding boundary.** We have **NO** real PayPal internal documents. Every PayPal-specific SOP, tool name, threshold, or internal acronym expansion below is either (a) **public-verifiable** (PayPal User Agreement, public help/dispute/AML pages, public developer/API docs, statutory law) and labeled as such, or (b) a **research-derived assumption (not verified internal)** derived from public sources and industry fraud-ops practice. Assumptions are never presented as confirmed internal fact. Internal acronyms and segment codes require team confirmation before any node label is finalized.

---

## 1. What is "PPA"? Disambiguation and recommendation

### 1.1 The two readings

The speaker is a fraud + commerce practitioner who said **"PPA commerce domain."** There are two defensible readings, and they point in the same direction for taxonomy purposes.

**Reading A — the public PayPal product meaning (high confidence on the acronym itself).**
The only publicly attested PayPal product expansion of **PPA is "PayPal Payments Advanced"** — a legacy, US-only, SMB-merchant product on the **Payflow** gateway that lets merchants accept PayPal + credit cards via hosted checkout pages, with PayPal acting as the merchant-account provider. It sits in a documented product family alongside Payflow Link (PFL), PayPal Payments Pro / Website Payments Pro (**WPP**), PayPal Payments Standard (WPS), and Express Checkout (EC). *(Source: developer.paypal.com Payflow docs; Adobe Commerce, WHMCS, Drupal/HikaShop integration docs. Confidence: high.)*

- **Critical disambiguation:** PayPal **Payments Pro = WPP (Website Payments Pro)**, NOT PPA. Within PayPal's own product lexicon PPA and Payments Pro are distinct products with distinct acronyms. **Do not equate PPA with "Payments Pro."** This eliminates the most common confusion. *(Source: developer.paypal.com paypal-payments-pro; WHMCS card-payments docs. Confidence: high.)*

**Reading B — internal data/risk-domain jargon (medium confidence; the more likely intent).**
The word **"domain"** in "PPA commerce domain" reads as **data-mesh / risk data-domain taxonomy**, not a product SKU. A modern fraud-platform team is unlikely to build a top-level *data domain* around a declining legacy Payflow merchant product. PayPal publicly frames its business as **Branded Experiences** vs **Unbranded / PSP** experiences plus **value-added services**, so "PPA" here is plausibly an **internal segment or product-area code** within that framing. **No public artifact maps "PPA" to a specific internal commerce data domain** — that exact expansion is an open item requiring internal confirmation (team data-catalog / domain registry / acronym glossary). *(Sources: PayPal investor/earnings + proxy materials, PayPal "what is a PSP" page. Confidence: medium; exact internal expansion = assumption.)*

**Ruled out / low probability:** PayPal Australia, "PayPal Account," "PayPal Personal Account." No corroborating evidence ties these to "PPA" as an established acronym in product, developer, or risk literature. A fraud + commerce practitioner saying "PPA commerce domain" is not plausibly naming a country entity or a generic account noun. *(Confidence: low.)*

### 1.2 Confidence ledger

| Item | Confidence | Basis |
|---|---|---|
| PPA acronym = "PayPal Payments Advanced" (public product) | **High** | PayPal dev docs + multiple platform integration docs |
| Payments Pro ≠ PPA (Payments Pro = WPP) | **High** | PayPal dev docs enumerate PPA, PFL, WPP separately |
| "PPA commerce domain" = internal data/risk-domain usage | **Medium** | "domain" framing; data-mesh convention; product unlikely as top-level domain |
| The *exact* internal expansion of PPA | **Assumption** | Not publicly documented; needs team glossary confirmation |
| PayPal AU / PayPal Account / Personal Account readings | **Low** | No supporting evidence |
| Taxonomy placement: PPA **under** Commerce | **Medium-High** | Robust across *both* readings (see §1.3) |

### 1.3 Recommendation: model PPA as a sub-bucket family **under** the Commerce domain

**Recommendation:** Place **PPA as a sub-bucket family under the Commerce domain**, not as its own top-level domain.

**Reasoning (robust across both readings):**
1. **Either interpretation is a child of Commerce.** Whether PPA is the *Payments Advanced* product or an internal *commerce-segment code*, it is fundamentally a **payment-acceptance / checkout construct** — conceptually a child of Commerce, not a peer.
2. **It mirrors PayPal's own framing.** PayPal frames the business as **Branded vs Unbranded/PSP** experiences. A single payment-flow acronym is naturally a **sub-family** within that structure, not a peer of Commerce itself.
3. **Avoids taxonomy fragmentation.** Elevating one product/segment to top level over-weights it and fragments the tree; nesting keeps the top level clean (Fraud, Commerce) and lets PPA inherit Commerce's shared base policy.

**Action before finalizing the node label:** verify the exact internal expansion of "PPA" with the PayPal team (data-catalog / domain registry / acronym glossary). Until then, label the node **`PPA (PayPal Payments Advanced — pending internal confirmation)`** and treat the expansion as a research-derived assumption.

---

## 2. Refined Fraud + Commerce (+ PPA) taxonomy — tree (v1 — SUPERSEDED by §2.v2 below, 2026-06-04)

Notation: **[CX]** = customer-facing sub-bucket (a contact-driven flow a fraud/commerce CX agent would handle, and therefore a candidate **domain pack** in the factory); **[INT]** = internal / ops-tier (detected and adjudicated by automated rules or back-office risk/AML/dispute ops, not resolved at the front-line CX tier); **[CX/INT]** = customer-facing intake exists but adjudication is internal.

This is the seven-bucket fraud taxonomy from [01](01-fraud-cx-factory-design.md) (§7–8), now refined into domain → subdomain → sub-bucket and reconciled with the PPA placement above.

```
PAYPAL RISK + COMMERCE TAXONOMY
│
├── DOMAIN: FRAUD  (risk / financial-crime)
│   │
│   ├── SUBDOMAIN: Account Takeover (ATO)          ✦ reference pack (see 01 §7)
│   │   ├── report-compromise / recover-access          [CX]
│   │   ├── unauthorized-transaction dispute (post-ATO) [CX]
│   │   ├── credential-change inventory & remediation    [CX]
│   │   └── high-confidence-ATO-with-loss handoff        [CX/INT]  → escalate, do not resolve at CX tier
│   │
│   ├── SUBDOMAIN: Card-Testing / BIN Attacks
│   │   ├── automated velocity / BIN-range blocking      [INT]     (rules/CAPTCHA/device fingerprint; not phone-agent work)
│   │   ├── auth-to-decline ratio monitoring             [INT]
│   │   └── victim whose card appears in a test attack   [CX]      → treat as unauthorized-card-use, advise issuer, file claim
│   │
│   ├── SUBDOMAIN: Synthetic Identity
│   │   ├── onboarding KYC anomaly detection             [INT]
│   │   ├── document / liveness verification queue        [INT]    (KYC/risk queue)
│   │   └── recovery-time synthetic-ID indicators         [CX/INT] → route to KYC/risk, never override
│   │
│   ├── SUBDOMAIN: Mule / AML (money laundering)
│   │   ├── fan-in/fan-out & structuring network detection [INT]
│   │   ├── linked-device/IP/phone ring analysis           [INT]   → AML / financial-crime team
│   │   └── duped-mule customer contact                    [CX/INT] → intake at CX, adjudicate at AML tier
│   │
│   ├── SUBDOMAIN: Refund / Chargeback Abuse ("friendly fraud")
│   │   ├── buyer unauthorized/INR/SNAD intake             [CX]     (standard unauthorized-transaction flow)
│   │   ├── repeat-disputer scoring                        [INT]    (never disclosed to customer)
│   │   └── dispute adjudication                           [INT]    (dispute/risk ops)
│   │
│   ├── SUBDOMAIN: Merchant Collusion / Bust-Out
│   │   ├── volume-spike vs history detection              [INT]
│   │   ├── coordinated buyer-seller pair analysis         [INT]
│   │   ├── reserve / hold / withdrawal-delay on account   [INT]    (UA rights — see §4)
│   │   └── seller appeal of hold/reserve                  [CX]     (standard appeal/info-submission flow)
│   │
│   └── SUBDOMAIN: Scams / APP Fraud (authorized push payment)
│       ├── pre-send scam interdiction / warning           [CX]    (first-time payee, urgency, atypical amount)
│       ├── post-send scam report                          [CX]    (recovery NOT guaranteed — jurisdiction-dependent)
│       └── beneficiary-previously-reported network signal [INT]
│
└── DOMAIN: COMMERCE  (buyer/seller experience, payment acceptance)
    │
    ├── SUBDOMAIN: PPA  (PayPal Payments Advanced — pending internal confirmation)   ← §1.3 recommendation
    │   ├── hosted-checkout / Payflow acceptance support    [CX]
    │   ├── merchant onboarding / account-provider support  [CX]
    │   └── gateway / transaction-decline troubleshooting    [CX/INT]
    │   (Note: PPA sits beside the broader Branded vs Unbranded/PSP framing; see §1.3.
    │    If "PPA" resolves internally to a segment code rather than the product, the
    │    sub-buckets re-map but the placement under Commerce holds.)
    │
    ├── SUBDOMAIN: Disputes & Claims (buyer/seller protection)
    │   ├── unauthorized-transaction claim intake           [CX]    (Resolution Center path — public)
    │   ├── item-not-received (INR) claim                    [CX]
    │   ├── significantly-not-as-described (SNAD) claim      [CX]
    │   └── claim adjudication / protection determination     [INT]
    │
    ├── SUBDOMAIN: Returns & Refunds
    │   ├── refund request / status                          [CX]
    │   └── refund liability & fee handling                   [INT]   (seller liable per UA)
    │
    ├── SUBDOMAIN: Checkout Support
    │   ├── payment-failure / decline help                   [CX]
    │   ├── payment-method management                         [CX]
    │   └── subscription / recurring-payment cancel           [CX]
    │
    └── SUBDOMAIN: Account & Funds Management
        ├── withdrawal-delay / hold inquiry                  [CX]    (UA delay/hold rights — public)
        ├── reserve inquiry (business account)                [CX]    (UA reserve right — public)
        └── limitation appeal / information request           [CX]   (standard Resolution Center flow)
```

### 2.1 CX vs internal — the dividing rule

The line is not the fraud *type*; it is **whether a verified customer contact drives the work**:

- **[CX] sub-buckets** are contact-initiated, require identity-appropriate authentication, and follow a public-or-assumed SOP the agent executes (intake, containment, coaching, claim filing, appeal submission). These are the candidate **domain packs** for the factory in [01](01-fraud-cx-factory-design.md).
- **[INT] sub-buckets** are detected/adjudicated by automated rules or back-office risk/AML/dispute ops. Per the guardrails in [01](01-fraud-cx-factory-design.md) and the fraud knowledge base, the CX agent **must not** resolve these at the front line, disclose detection rules/thresholds, confirm an investigation, reveal repeat-disputer scoring, or disclose SAR existence (BSA anti-tipping-off, 31 U.S.C. 5318(g)(2) — statutory). *(Card-testing velocity numbers, repeat-disputer scoring, dollar escalation thresholds = research-derived assumptions / generic industry examples, not verified internal.)*
- **[CX/INT]** sub-buckets have a customer-facing intake but an internal adjudication boundary: the agent **takes the report and escalates**, it does not adjudicate.

### 2.2 What changed from the [01] taxonomy

- **PPA added** as a named subdomain **under Commerce** (was an unlabeled "(PPA)" annotation on the Commerce row in [01] §8); placement justified in §1.3 and flagged pending internal confirmation.
- **Each fraud subdomain decomposed into sub-buckets** with explicit **[CX]/[INT]/[CX/INT]** tags, making concrete the "card-testing/mule = mostly internal" note from [01] §8.
- **Commerce expanded** from the four packs in [01] (unauthorized-dispute, returns/refunds, checkout-support, subscription-cancel) into subdomains (Disputes & Claims, Returns & Refunds, Checkout Support, Account & Funds Management) plus PPA, aligned to public PayPal flows.

---

## 2.v2 — Restructured taxonomy (v2, 2026-06-04) `[AUTHORITATIVE]`

Rebuilt after the external cross-check ([taxonomy-gap-analysis-external-2026-06-04.md](../validation/taxonomy-gap-analysis-external-2026-06-04.md)). **Scope: customer + merchant fraud/financial-crime CX.** Internal/employee/vendor/financial-statement fraud is **OUT of scope** (noted at the end for handoff only). Two changes from v1: (a) a cleaner primary tree with the missing standard categories added; (b) **orthogonal cross-cutting tags** so we stop mixing actor/vector/rail/claim/queue as peer nodes.

Tags: **[CX]** customer-facing · **[INT]** internal/ops · **[CX/INT]** customer intake + internal adjudication. ✦ = existing reference pack. **(new)** = added from the gap analysis.

```
DOMAIN: FRAUD  (customer + merchant financial crime)
│
├── Account Security & ATO            ✦ pack 04
│   ├── ATTACK VECTORS (new, was collapsed): credential-stuffing · phishing · SIM-swap ·
│   │   session-hijack/token-theft · MFA-bypass/fatigue · support-channel social-eng · brute-force   [CX/INT]
│   ├── report-compromise / recover-access                                   [CX]
│   └── credential-change inventory & remediation                           [CX]
│
├── Payment Instrument Fraud  (new parent — split from card-testing)
│   ├── card-testing / BIN attack: attack-detection [INT]  ·  victim-claim [CX]   ✦ (pack 04 adjacent)
│   ├── CNP stolen-card purchase (new)                                       [CX/INT]
│   ├── stolen bank / ACH / direct-debit misuse (new)                       [CX/INT]
│   ├── wallet-token provisioning / account-linking fraud (new)             [CX/INT]
│   └── lost / stolen / counterfeit card (new)                              [CX/INT]
│
├── Scams / APP Fraud  (authorized push payment — contacting party IS the owner)   ✦ pack 06
│   ├── SUBTYPES (new, was one bucket): purchase · investment/crypto-investment · romance ·
│   │   advance-fee/job/loan/prize · invoice-mandate redirection · CEO/BEC ·
│   │   impersonation (police/bank/gov/platform) · safe-account · P2P (marketplace/QR/handle) ·
│   │   gift-card · crypto off-ramp                                          [CX / CX-INT]
│   ├── pre-send interdiction / warning                                     [CX]
│   └── post-send report + recovery                                         [CX/INT]
│
├── Identity & Onboarding Fraud
│   ├── synthetic identity: onboarding · sleeper · bust-out · SSN/child-misuse (new subtypes)   ✦
│   └── new-account / application fraud (new): stolen-ID · mule-account · promo-farm   [CX/INT]
│
├── First-Party / Refund / Chargeback Abuse   (renamed from "friendly fraud")   ✦ pack 07 adjacent
│   ├── chargeback fraud (align to network reason codes)
│   ├── return abuse (new): wardrobing · empty-box · switch · FTID · refund-without-return · serial
│   ├── refund abuse
│   └── first-party misrepresentation (new): intentional non-payment · false claims · buyer-policy abuse
│
├── Incentive & Stored-Value Abuse  (new subdomain)
│   ├── promo / referral / bonus abuse (new)
│   └── loyalty / points / stored-value fraud (new)
│
├── Merchant Risk & Abuse  (new parent — was just "collusion/bust-out")
│   ├── bust-out (new subtypes): reserve-evasion · fake-fulfillment · volume-spike · withdrawal-sprint · linked-merchants   ✦
│   ├── collusion (buyer-seller pair)                                        [INT]
│   ├── transaction laundering / hidden merchant-of-record (new)            [CX/INT]
│   ├── fake storefront / seller non-delivery (new)                         [CX/INT]
│   ├── reseller / triangulation fraud (new)                                [CX/INT]
│   ├── prohibited-goods / AUP violation (new)                              [CX/INT]
│   └── merchant financial / underwriting misrepresentation (new)           [CX/INT]
│
└── AML/CFT & Illicit Finance  (renamed from "Mule / AML"; mules now a child)
    ├── ML-stage tags (new): placement · layering · integration             [INT]
    ├── mule networks & lifecycle (new depth): unwitting / witting / complicit · recruitment · account rental-sale   ✦ partial
    ├── structuring / smurfing                                              [INT]
    ├── trade-based ML (new)                                                [INT]
    ├── professional-ML networks (new)                                      [INT]
    ├── shell / front companies & beneficial-owner concealment (new)        [INT]
    ├── crypto / CVC laundering (new)                                       [INT]
    └── sanctions / CFT / proliferation screening (new)                     [INT + CX status]

DOMAIN: COMMERCE  (buyer/seller experience & payment support)
│
├── Disputes & Claims
│   ├── unauthorized transaction = CLAIM-TYPE with CAUSE TAGS (new model):
│   │      {ATO · stolen-card · stolen-bank · wallet-token · merchant-error · first-party}   [CX intake / INT adjudicate]
│   ├── INR · SNAD · credit-not-processed · duplicate · cancelled-recurring · processing-error   ✦ pack 07
│   └── Card-Network Disputes (new): Fraud · Authorization · Processing-error · Consumer-dispute
│          families + representment / evidence / deadline workflow
├── Returns & Refunds        intake [CX] · liability [INT]
├── Checkout Support         payment-failure/decline · payment-method mgmt · subscription cancel   [CX]
├── Account & Funds Mgmt     withdrawal-delay/hold inquiry · reserve inquiry · limitation appeal   [CX intake / INT decide]
└── PPA (PayPal Payments Advanced — pending internal confirmation)
       hosted-checkout support · merchant onboarding · gateway troubleshooting   [CX / CX-INT]

[OUT OF SCOPE]  Internal / employee / vendor-procurement / financial-statement fraud (ACFE internal categories).
   Excluded per scope decision (customer + merchant CX). A CX agent only intakes/route-to-internal-investigations;
   listed here so the boundary is explicit, not forgotten.
```

### Orthogonal cross-cutting tags (apply to ANY case — the v2 reframe)
Stop encoding these as tree nodes; attach them as attributes:
`actor {customer | fraudster-3rd-party | merchant | mule}` · `victim {owner | counterparty | merchant | platform}` ·
`pressure_source {contacting_party | absent_third_party | none}` (ties to packs / [contract.md](../spec/contract.md) §4) ·
`payment_rail {P2P | card | ACH-bank | wallet | crypto | cross-border}` · `instrument {card | bank | wallet-token | stored-value | crypto}` ·
`transaction_status {pre-send | pending-unsettled | settled | withdrawn | converted}` ·
`ml_lifecycle_stage {placement | layering | integration}` (AML only) ·
`jurisdiction / reimbursement_regime {UK-PSR-mandatory | US-RegE-unauthorized-only | none}` ·
`recovery_state {recallable | claim-only | unrecoverable}` · `authority {CX-resolvable | INT-adjudicated | CX-intake+INT-decide}` ·
`vulnerability_coercion {none | elder | coercion | trafficking | cognitive}` (new safety overlay → changes agent scripts).

### Structural fixes applied (from the cross-check §C)
APP split into subtypes · "unauthorized" modeled as claim-type-with-cause-tags (no Fraud/Commerce duplication) · "friendly fraud" → "First-Party/Refund/Chargeback Abuse" with subtypes · "Mule/AML" → "AML/CFT & Illicit Finance" (mules a child) · added "Merchant Risk & Abuse" and "Payment Instrument Fraud" parents · card-network reason-code disputes added · CX/INT dual-layer (decision INT + inquiry/appeal/status CX) · attack-detection split from victim-claim · orthogonal tags introduced · vulnerability/coercion overlay added · internal fraud explicitly out of scope.

### Pack impact (downstream)
- **Pack 06 (APP/scams):** should expand to the 11 scam subtypes above (its personas/policies/state generalize, but disposition + warnings differ per subtype).
- **Pack 07 (Disputes):** add card-network reason-code families + representment; adopt unauthorized-as-claim-with-cause-tags.
- **Pack 04 (ATO):** add the attack-vector subtypes.
- **New packs implied:** Payment-Instrument-Fraud, Merchant-Risk, AML/CFT (mostly INT — limited CX surface).

### Still required to certify (unchanged from §4A)
This v2 is now cross-checked against **external** frameworks (one independent anchor ✓). It is still **not** certified against **internal** PayPal taxonomy/logs + SME — that remains the gold-standard step before production use.

## 3. How domain packs compose via a shared base-policy library

This extends the **domain-pack = 5 artifacts** contract from [01](01-fraud-cx-factory-design.md) (§3) and the one-line "shared base policy" note in [01] §8 into a concrete composition model. The factory **core never hard-codes domain logic**; everything domain-specific lives in a pack. Cross-cutting rules live **once** in a shared base-policy library and are imported by every pack (DRY across subdomains).

```
                 ┌──────────────────────────────────────────────────────────┐
                 │  SHARED BASE-POLICY LIBRARY  (domain-agnostic primitives)  │
                 │                                                            │
                 │  BASE-AUTH-*   identity verification & tiered step-up      │
                 │  BASE-ESC-*    escalation triggers / no-override rules     │
                 │  BASE-DISC-*   disclosure limits (anti-tipping-off, no     │
                 │                detection-rule/threshold/PII disclosure)    │
                 │  BASE-FUNDS-*  hold vs reverse vs claim decisioning        │
                 │  BASE-AUDIT-*  log-all-actions / reason-code requirements   │
                 └───────────┬──────────────────────────┬─────────────────────┘
                             │ imported by              │ imported by
            ┌────────────────┴───────┐         ┌────────┴───────────────────┐
            ▼                        ▼         ▼                            ▼
   ┌─────────────────┐   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
   │ FRAUD: ATO pack │   │ FRAUD: APP-scam │  │ COMMERCE: PPA   │  │ COMMERCE:       │
   │                 │   │ pack            │  │ pack            │  │ Disputes pack   │
   │ Policy  (ATO-*) │   │ Policy (SCAM-*) │  │ Policy (PPA-*)  │  │ Policy (DSP-*)  │
   │  + imports BASE │   │  + imports BASE │  │  + imports BASE │  │  + imports BASE │
   │ Tool schema     │   │ Tool schema     │  │ Tool schema     │  │ Tool schema     │
   │ Personas        │   │ Personas        │  │ Personas        │  │ Personas        │
   │ State schema    │   │ State schema    │  │ State schema    │  │ State schema    │
   │ Checkers        │   │ Checkers        │  │ Checkers        │  │ Checkers        │
   └─────────────────┘   └─────────────────┘  └─────────────────┘  └─────────────────┘
```

### 3.1 What lives in the shared base-policy library

The base library holds policy primitives that every CX sub-bucket needs, expressed as the **machine-checkable predicates** from [01](01-fraud-cx-factory-design.md) §4.3 (each rule = id + text + type + checker). All PayPal-specific values are public-anchored or labeled assumptions:

| Base family | Primitive (illustrative) | Grounding |
|---|---|---|
| **BASE-AUTH** | Tiered step-up: low/medium/high risk → standard / second independent factor / document-based ID + liveness. **Treat any contact method changed in the recent window as attacker-controlled; never send recovery codes to it.** | Research-derived assumption (the recent-window, e.g. 24–72h, is an assumption; ID+liveness step-up is industry consensus) |
| **BASE-ESC** | Escalate-don't-resolve for: confirmed ATO with loss; failed identity proofing + insistence; mule/network or synthetic-ID signals; AML matches; high-dollar threshold; any case requiring disclosure of investigation detail. | Research-derived assumption (dollar threshold is an assumption) |
| **BASE-DISC** | Never disclose SAR existence (anti-tipping-off); never reveal detection rules/thresholds/model signals; never confirm/deny an active investigation; never disclose counterparty PII; minimize data to the verified accountholder's need. | **Statutory** (31 U.S.C. 5318(g)(2)) + research-derived assumption for the rest |
| **BASE-FUNDS** | HOLD while in-flight + suspected/unconfirmed; attempt recall/reversal while pending + confirmed-unauthorized; for SETTLED sends open the unauthorized-transaction claim (10-day investigation email) rather than promise reversal; do not over-promise recovery on authorized (scam) payments. | Public-anchored (UA hold/delay/reserve rights; public 10-day email; 180-day / 30-day SNAD windows) + research-derived assumption for decision ordering |
| **BASE-ELIG** | Determine coverage/eligibility by the correct rule (purchase-protection coverage, scam-reimbursement scheme, jurisdictional protection) **before** describing outcomes; never assert coverage that does not apply; never over-promise. *(added per [05-introspection-and-contract-revision.md](05-introspection-and-contract-revision.md) G3, surfaced by [07-commerce-disputes-domain-pack.md](07-commerce-disputes-domain-pack.md); shared by APP SCAM-P04 + Disputes DSP-P01)* | Public coverage exclusions + UK PSR / Reg E asymmetry; decision ordering = research-derived assumption |
| **BASE-AUDIT** | Log all actions with reason codes; emit SAR flag on disposition without disclosing it to the customer. | Research-derived assumption (audit logging is best practice) |

### 3.2 How a pack composes with the base

1. **Import + extend.** A pack's Policy artifact `imports` the base families and adds **domain-specific rules** (e.g., ATO-P03 "never reverse before identity verified ≥2" specializes BASE-AUTH + BASE-FUNDS; see [01](01-fraud-cx-factory-design.md) §4.3, §7).
2. **Override by specialization, not mutation.** A pack may *tighten* a base rule (stricter step-up for high-value ATO) but never silently relax it; relaxations require an explicit, audited pack-level rule — mirroring the **monotonic** discipline of the CaseState contract in [01](01-fraud-cx-factory-design.md) §4.1.
3. **Checkers inherit too.** The Checkers artifact runs **base policy-violation predicates + pack-specific predicates** over every trajectory. A trajectory that matches the final-state goal but breaches a base rule (e.g., a BASE-DISC tipping-off violation) **fails** — the fraud-critical case from [01](01-fraud-cx-factory-design.md) §2 (state-diff alone misses guardrail breaches).
4. **State schema layering.** Pack CaseState extends a shared base state (`session_id`, `verified_identity`, `actions_taken`, `disposition` with `sar_flag`) with domain fields (e.g., PPA: `merchant_account_status`, `gateway_decline_code`).
5. **Conflict resolution.** Where a base rule and a pack rule both fire, the **stricter constraint wins**; hard constraints always dominate soft/escalation rules. This makes guardrail behavior predictable and independently gradable across all packs.

### 3.3 Why this matters for the factory

- **Adding a subdomain = author one pack** (5 artifacts) that imports the base — the engine and the cross-cutting guardrails do not change. This is the "factory per domain/subdomain" principle from [01](01-fraud-cx-factory-design.md) §3 made composable.
- **Consistency of guardrails across domains.** Because anti-tipping-off, step-up, and hold/reverse logic live in one base library, Fraud-ATO and Commerce-PPA enforce the **same** disclosure and funds-movement discipline — improving the Pass100-style consistency target ([01](01-fraud-cx-factory-design.md) §9) at the *policy* level, not just per-pack.
- **PPA inherits Commerce + base for free.** Once PPA is placed under Commerce (§1.3), its pack imports the shared base-policy library like any other, so PPA CX flows get the same auth/escalation/disclosure/funds guardrails without re-authoring them.

---

## 4. Public anchors used (ground truth) vs assumptions

**Public-verifiable (ground truth):** Resolution Center reporting path; PayPal's stated **10-day** unauthorized-activity investigation email; **180-day** dispute filing window (**30-day** SNAD variant); UA rights to **hold** funds during disputes, **delay** withdrawals after reversals, and place **reserves** on high-risk business accounts; sellers liable for refunded/invalidated amounts + fees; EFTA/Regulation E **$50 / $500 / 60-day** consumer-liability tiers (federal law, not PayPal-set); BSA/FinCEN **anti-tipping-off** (31 U.S.C. 5318(g)(2)); PPA = "PayPal Payments Advanced" and Payments Pro = WPP (public PayPal dev docs); PayPal's public **Branded vs Unbranded/PSP** business framing.

**Research-derived assumptions (NOT verified internal):** the exact internal expansion/scope of "PPA" as a *data domain*; the contain→verify→remediate ATO step order and tiered step-up thresholds; the "contact-changed-in-last-24–72h = attacker-controlled" rule; dollar-based escalation thresholds; card-testing velocity numbers (generic industry examples); any specific internal tool names; all pack/base policy IDs in this doc are illustrative encodings, not PayPal artifacts.

---

## 4A. Provenance, circularity & how to validate this taxonomy `[added 2026-06-04]`

**Provenance — who created this taxonomy.** It was **generated by the research workflow** (AI synthesis over *public* sources: PayPal's public User Agreement, public dispute/AML/help pages, general industry fraud-ops writing). It was **not** authored by a human fraud SME and **not** taken from PayPal's real internal taxonomy. Every node is a research-derived assumption.

**⚠️ Circularity caveat.** Each domain pack's action space (Tool schema in [04](04-ato-domain-pack.md)/[06](06-app-scams-domain-pack.md)/[07](07-commerce-disputes-domain-pack.md)) was generated from the **same source** as this taxonomy. Therefore **checking action-space completeness against this taxonomy is circular** — they share the same blind spots, so neither can certify the other. More broadly, *almost every artifact in this package (taxonomy, SOPs, tools, action spaces) shares one origin: AI research over public info* — so **nothing here independently validates anything else yet.** Treat the whole package as one coherent *hypothesis* of the domain, not ground truth.

**Corrected framing.** "Check coverage against the taxonomy" is an **internal-consistency check, NOT a completeness/coverage proof.** Do not present it as evidence that the taxonomy or action space is complete.

**How to actually validate (break the circularity) — requires an INDEPENDENT anchor:**
1. **External cross-check (do now; partially independent).** Cross-check this taxonomy AND each pack's action space against **published external fraud typologies** that did NOT come from our generation — e.g. the **ACFE fraud tree**, **FATF/FinCEN AML/CFT typologies**, **UK PSR APP-scam categories**, **card-scheme fraud reason-code** taxonomies, and standard ATO / synthetic-ID / mule / refund-abuse / merchant-bust-out category lists. Map each external category to our nodes; **unmapped external categories = candidate gaps.** A reusable prompt for this is at [taxonomy-gap-analysis-prompt.md](../validation/taxonomy-gap-analysis-prompt.md). **✓ First external cross-check completed 2026-06-04** (independent LLM vs ACFE / FATF-FinCEN / UK Finance-PSR / Visa-MC-Stripe / OWASP / NRF / Fed) — results in [taxonomy-gap-analysis-external-2026-06-04.md](../validation/taxonomy-gap-analysis-external-2026-06-04.md): verdict *"solid skeletal but materially incomplete,"* ~25 high-confidence gaps + structural fixes, pending the scope decision and a v2 rewrite.
2. **Internal grounding (gold standard; eventual).** Reconcile against PayPal's real internal taxonomy, SOP catalog, tool inventory, and **case/call logs** (logs show what *actually* happens), with **human fraud-ops SME sign-off**. This is the only true completeness certification.
3. **Living artifact.** Generation (LLM gap-finder panels + the empirical "the generator needed a missing tool" detector) may keep *proposing* additions, but **only an independent anchor (1 then 2) can certify** representativeness. *Generation proposes; an outside source disposes.*

## 5. Open items / decisions needed

1. **Confirm the internal expansion of "PPA"** with the PayPal team (data-catalog / domain registry / acronym glossary). Until confirmed, keep the node label provisional. *(Blocks finalizing the Commerce/PPA node name only — not the placement, which holds either way.)*
2. **CX vs internal boundary review:** validate the [CX]/[INT]/[CX/INT] tags against the team's actual front-line scope of authority.
3. **Base-policy ground truth:** who supplies real PayPal SOPs/guardrails to replace the assumption-labeled base rules (links to [01](01-fraud-cx-factory-design.md) §10 open item 1).
4. **v1 pack set:** which [CX] sub-buckets become the first authored packs (recommend: Fraud-ATO ✦ already specced + Commerce-Disputes + one PPA pack) to exercise base-policy composition across both domains ([01](01-fraud-cx-factory-design.md) §11 P4).
