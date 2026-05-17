# Attestplane Trademark Policy

**Version**: 1.0  
**Effective Date**: 2026-05-17  
**Trademark Holder**: Attestplane Pte. Ltd. (Singapore, in formation as of 2026-05-17)  
**Policy Contact**: trademark@attestplane.com  
**Next Review**: M9 (2026-Q4) — aligned with GOVERNANCE.md amendment process

> **Disclaimer**: This document is a trademark policy statement issued by Attestplane Pte. Ltd.
> It does not constitute legal advice in any jurisdiction. Users should consult a
> jurisdiction-licensed attorney before relying on any trademark interpretation for their
> specific situation.

---

## 1. Trademark Holder and Scope

### 1.1 Owner

All Attestplane trademarks are owned by **Attestplane Pte. Ltd.**, a Singapore private
limited company (in formation as of 2026-05-17; UEN pending). Upon incorporation
completion, the company holds and enforces these marks globally.

### 1.2 Registered and Pending Marks

| Mark | Nice Class(es) | Use | Status |
|---|---|---|---|
| **Attestplane** | 9 + 42 | Primary brand — downloadable software and SaaS audit services | USPTO + EUIPO to be filed (target W2–W3 2026); **™ until registration confirmed** |
| **Attestplane Certified** | 42 | Certification mark — authorized deployments only | USPTO + EUIPO to be filed (target W2–W3 2026); **™ until registration confirmed** |
| Attestplane logo (design mark) | 9 + 42 | Visual brand identity | TBD — file after brand-assets finalized (target M5) |

**Symbol usage**: The ™ symbol is used for all marks during the pre-registration period.
Upon USPTO and/or EUIPO registration, the ® symbol will be adopted in the relevant
jurisdictions. Do not use ® before registration is confirmed.

### 1.3 Separation from License

The Attestplane core substrate is distributed under the Apache License 2.0. **The Apache
2.0 license grants copyright and patent rights; it does not grant any trademark license.**
These two regimes are strictly separate. You may use, modify, and redistribute the
software under Apache 2.0 without infringing copyright — but your trademark rights are
governed solely by this policy.

This is the same model used by the Apache Software Foundation and Red Hat, Inc.

---

## 2. Allowed Use — No Permission Needed

The following uses are permitted without contacting us, provided they are accurate and
not misleading.

| Permitted Use | Conditions |
|---|---|
| Referring to the Attestplane project by name in writing, speech, or code | Must use correct spelling, capitalization, and spacing ("Attestplane" — not "Attest Plane", "attestPlane", "ATTESTPLANE") |
| Non-commercial blog posts, tutorials, conference talks, academic papers, and educational materials | Must not imply endorsement by or partnership with Attestplane Pte. Ltd. |
| Distributing **unmodified** upstream source or binaries (e.g., Linux distro packages, OS package managers) | Must include unmodified LICENSE, NOTICE, and copyright headers |
| Descriptive phrases: "Built on Attestplane", "Compatible with Attestplane", "Integrates with Attestplane" | Must appear as a modifier, not as a product or company name; font/size must be visually subordinate to your own brand |
| Comparative and factual statements (e.g., benchmark comparisons, feature comparisons) | Must be accurate and not disparaging |
| Linking to attestplane.com or the project's GitHub repository | No restrictions |

---

## 3. Uses Requiring Written Permission

The following uses require prior written approval from **trademark@attestplane.com**
(response within 14 business days).

| Use Requiring Permission | Reason |
|---|---|
| A commercial product, service, or SaaS platform whose name contains "Attestplane" | Risk of consumer confusion about source or sponsorship |
| A domain name containing "attestplane", "attest-plane", "attestplain", "attestpane", or confusingly similar variants | Anti-squatting and brand protection |
| Paid training courses, bootcamps, or certification prep services using the Attestplane name | Commercial use of mark |
| Unauthorized audit, compliance, or certification services claiming to be "Attestplane" affiliated | Certification mark integrity |
| Logo use in commercial merchandise, event sponsorship, or co-branding materials | Controls association with Attestplane Pte. Ltd. |
| Any use that could reasonably imply official endorsement, partnership, or affiliation with Attestplane Pte. Ltd. | Prevents consumer deception |

When in doubt, email trademark@attestplane.com before proceeding. We aim to say yes to
legitimate uses and will respond with a clear decision.

---

## 4. Fork and Redistribution Rules

This section implements the ASF + Red Hat mixed model for modified distributions.

### 4.1 Unmodified Distribution (Permitted)

Redistributing unmodified Attestplane source code or binaries under Apache 2.0 is
permitted. You must:

- Retain the LICENSE file, NOTICE file, and all copyright headers unchanged.
- Not remove or alter any trademark notices.
- Not imply that your distribution is the official upstream.

### 4.2 Modified Forks — Required Rebrand

If you fork Attestplane and **make substantive modifications** (changes to core audit
logic, hash chain behavior, framework mappings, API contracts, or public interfaces),
you **must not** use "Attestplane" as the project name or primary brand.

| Scenario | Permitted? |
|---|---|
| Fork with internal patches, distributed as "Attestplane" internally | Yes — internal use only, not redistributed publicly |
| Fork published as "Attestplane Enterprise by Foo Corp" | **No** — commercial product name using primary mark |
| Fork published as "MyAttest" with tagline "compatible with Attestplane" | No for product name; "compatible with Attestplane" tagline is OK under §2 |
| Fork fully rebranded as "FooBar Audit Substrate, Attestplane-compatible" | Yes — rebrand complete, modifier phrase is accurate |
| Fork compiled into a proprietary SaaS, sold as "Attestplane" | **No** — requires full rebrand regardless of Apache 2.0 |
| OSS fork that only adds minor documentation or CI configuration changes | May retain "Attestplane" name; contact us if uncertain |

The test is: **would a reasonably informed user believe your product is the official
Attestplane project or is authorized by Attestplane Pte. Ltd.?** If yes, rebrand is
required.

### 4.3 What Substantive Modification Means

Substantive modification includes but is not limited to: changes to the hash-chain
algorithm or canonicalization rules (currently SHA-256 over restricted-JCS per
[ADR-0002](docs/adr/0002-substrate-data-model-and-hash-chain-v0.md)), RFC-3161
anchoring logic (per [ADR-0003](docs/adr/0003-tsa-rfc-3161-anchoring.md)), auditor
JSON API schema, framework mapping files, or the core `AttestSubstrate` /
`ChainedEvent` types. Formatting changes, CI fixes, and documentation additions are
generally not substantive.

---

## 5. Attestplane Certified — Certification Mark Rules

"Attestplane Certified" is a **certification mark** (Nice Class 42). It certifies that
a deployment has passed the Attestplane audit process, not that it originates from
Attestplane Pte. Ltd.

### 5.1 Who May Use "Attestplane Certified"

Only deployments that have **completed and passed the Attestplane Certification Process**
(described below) may use the "Attestplane Certified" mark, in the authorized form and
context specified in the certification agreement.

### 5.2 Certification Process (Placeholder — Target M6–M7)

> **[CERTIFICATION_PROCESS_TBD — formal program launches M6–M7 2026]**

The certification process will require demonstration of all of the following, verified
by Attestplane Pte. Ltd. or an authorized auditor:

| Requirement | Specification |
|---|---|
| **Chain integrity** | Hash chain (algorithm and canonicalization per current ADR-0002 — SHA-256 at v0.0.1) is unbroken; no entries modified post-write; `verify()` returns `ok` |
| **RFC-3161 anchoring** | All chain segments anchored to a qualified TSA; timestamps verifiable |
| **Framework coverage** | All applicable EU AI Act Article 12–17 obligations mapped and evidenced |
| **API conformance** | Auditor JSON API responds per the published schema version |
| **Operational security** | Key management and storage meet minimum Attestplane security baseline |
| **Commercial compliance attestation** | Deploying entity has reviewed and accepted the Attestplane Terms of Service |

Until the formal program is published, **no entity may claim "Attestplane Certified"**
for any deployment. The placeholder language in this section does not create any
certification entitlement.

### 5.3 Annual Re-Certification

Certifications expire 12 months after issuance. Certified entities must complete annual
re-certification to maintain the mark. The re-certification process will be published
alongside the initial certification program.

### 5.4 Revocation

Attestplane Pte. Ltd. may revoke certification if a certified deployment subsequently
fails to maintain conformance, or if the certified entity breaches the certification
agreement or these trademark terms.

### 5.5 Unauthorized Use

Using "Attestplane Certified" without completing the certification process constitutes
trademark infringement. Attestplane Pte. Ltd. will actively enforce this mark. See §8.

---

## 6. Prohibited Uses

The following uses are prohibited under all circumstances.

| Prohibited Use | Category |
|---|---|
| Domain squatting, typosquatting, or registering domains confusingly similar to "attestplane" | Brand abuse |
| Phishing sites, impersonation, or fraudulent communications using Attestplane marks | Security + fraud |
| Using "Attestplane" or "Attestplane Certified" as a company name, trade name, or registered business name without a written trademark license | Unauthorized commercial use |
| Using the marks in any way that falsely implies an endorsement, sponsorship, or partnership that does not exist | Consumer deception |
| Using the marks in misleading, defamatory, or disparaging contexts | Reputational harm |
| Applying the ® symbol to any Attestplane mark before USPTO or EUIPO registration is confirmed | Misrepresentation |
| Claiming "Attestplane Certified" status without completing the certification process | Certification mark infringement |
| Altering the Attestplane wordmark (changing spelling, capitalization, spacing, or combining with other words to create a new mark) | Trademark dilution |

### 6.1 First-Party Authorized Domains

For the avoidance of doubt, the following domain names are registered to and operated by Attestplane Pte. Ltd. (or its founder on its behalf during the in-formation period) and are not subject to the anti-squatting provision above:

| Domain | Registered | Intended Use |
|---|---|---|
| `attestplane.com` | 2026-05-17 | Primary corporate, legal, and policy contact domain |
| `attestplane.io` | 2026-05-17 | Developer and OSS project domain |
| `attestplane.ai` | 2026-05-17 | Brand and market positioning domain |
| `attestplane.dev` | 2026-05-17 | Developer documentation and tooling |
| `attestplane.app` | 2026-05-17 | Future hosted application surface |

Third parties registering or operating domains other than those listed above using "attestplane" or visually or phonetically similar variants are subject to §6 unless covered by §2 (nominative fair use) or §3 (written permission).

This list will be updated as additional first-party domains are registered. Always check the current version of this file for the authoritative list.

---

## 7. Logo and Brand Assets

Official logo files, color specifications, and brand usage guidelines will be published
in the `attestplane/brand-assets` repository upon design completion (target M5, 2026-08).

Until then:

- Do not create your own version of the Attestplane logo.
- Do not use placeholder or AI-generated logos and label them as "Attestplane."
- Text-only references to "Attestplane" in correct form (see §2) are permitted.

---

## 8. Enforcement

### 8.1 Enforcement Philosophy

Attestplane Pte. Ltd. actively monitors for trademark misuse and will enforce its marks
proportionately. The goal is to protect the integrity of the Attestplane brand for the
benefit of the community — not to block legitimate non-commercial uses.

**Escalation tiers**:

1. **Informal notice**: email from trademark@attestplane.com requesting voluntary
   correction, with a reasonable cure period (typically 14–30 days).
2. **Formal cease-and-desist letter**: drafted and sent by Attestplane Pte. Ltd.
3. **Legal proceedings**: USPTO/EUIPO opposition, cancellation, or infringement action
   where necessary.

Budget allocation for enforcement is maintained at a minimum of USD 10,000 per the
company's risk register (COMMERCIAL_STRATEGY v1.3 §6).

### 8.2 Lawyer-Founder Stewardship

**This trademark policy is directly stewarded by the Attestplane founder**, who is a
China-licensed Business and Compliance lawyer. Cease-and-desist letters and first-wave
enforcement actions are handled in-house by the founder in their capacity as Director of
Attestplane Pte. Ltd. — not outsourced to external counsel as a first step.

This reflects deliberate design: trademark policy drafted and enforced by a practicing
lawyer-founder produces more precise, faster, and less expensive enforcement outcomes
than boilerplate-based outsourcing. External counsel is engaged where US or EU bar
standing is required for court proceedings.

> This policy and enforcement approach does not constitute legal advice to any third
> party. Recipients of enforcement notices should obtain independent legal advice from a
> jurisdiction-licensed attorney.

---

## 9. Reporting Trademark Misuse

If you observe a use of the Attestplane marks that appears to violate this policy, please
report it so we can investigate.

**Report to**: trademark@attestplane.com  
**Subject line format**: `[TM REPORT] Brief description`  
**Include**:

- URL or screenshot of the suspected misuse
- Your assessment of why it may violate this policy
- Your contact information (optional — anonymous reports accepted)

We will acknowledge receipt within 5 business days and complete an initial assessment
within 30 days.

---

## 10. Permission Requests

To request a trademark license or permission for a use listed in §3:

**Contact**: trademark@attestplane.com  
**Subject line format**: `[TM PERMISSION] Brief description of intended use`  
**Include**:

- Description of the intended use (product name, domain, service description)
- Jurisdiction(s) where the mark will be used
- Whether the use is commercial
- Your company or individual name and contact information

**Response commitment**: We aim to respond within **14 business days**. Complex requests
may require additional time; we will acknowledge and provide a timeline estimate.

Permission grants are documented in writing. Verbal permissions are not binding on
Attestplane Pte. Ltd.

---

## 11. Updates to This Policy

### 11.1 Version Control

This policy is version-controlled. The current version number and effective date appear
in the header. All versions are retained in the project repository for historical
reference.

### 11.2 Amendment Process

Material amendments to this policy follow the same process as GOVERNANCE.md amendments
(see GOVERNANCE.md §Amendment Process):

1. Draft amendment proposed by Attestplane Pte. Ltd. or a community maintainer.
2. 30-day public comment period via GitHub Issues tagged `trademark-policy`.
3. Final amendment approved by Attestplane Pte. Ltd. Director.
4. New version published with updated version number and effective date.
5. 30-day notice period before new version takes effect (except for urgent security or
   legal corrections, which may take effect immediately with notice).

### 11.3 Notification

Material updates will be announced via the project's official channels (GitHub
Discussions, project mailing list, attestplane.com/blog). Continuing to use the marks
after the new version's effective date constitutes acceptance of the updated policy.

---

## 12. Governing Law and Dispute Resolution

This policy is issued by Attestplane Pte. Ltd., incorporated in Singapore. Disputes
relating to trademark ownership, licensing, or this policy that cannot be resolved
informally shall be subject to Singapore law and the non-exclusive jurisdiction of the
Singapore courts, without prejudice to Attestplane Pte. Ltd.'s right to seek injunctive
relief in any jurisdiction where infringement occurs.

---

## Quick Reference

### Common questions

| Question | Answer |
|---|---|
| Write a blog post about Attestplane? | Yes — no permission needed (§2) |
| Give a conference talk mentioning Attestplane? | Yes — no permission needed (§2) |
| Distribute an unmodified Attestplane package in my OS distro? | Yes — retain LICENSE/NOTICE (§4.1) |
| Fork and publish a modified version called "Attestplane Pro"? | No — rebrand required (§4.2) |
| Build a SaaS on top of Attestplane and call it "Attestplane Cloud"? | No — requires written permission (§3) |
| Register attestplane.io or attest-plane.com? | No — prohibited (§6) |
| Say my product is "Attestplane Certified"? | Not until certification program launches M6–M7 (§5) |
| Use the Attestplane logo in my presentation slides? | Logo TBD — text-only references permitted now (§7) |

---

*Attestplane™ and Attestplane Certified™ are trademarks of Attestplane Pte. Ltd.*  
*Apache License 2.0 governs copyright and patent rights in the software — not trademark rights.*  
*This document does not constitute legal advice. Consult a qualified attorney in your jurisdiction.*
