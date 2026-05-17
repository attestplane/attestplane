# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""AIOS adapter — SPEC ONLY.

This module is **deliberately empty of executable code**. It exists to
document the contract that an AIOS-to-Attestplane adapter must satisfy.
The concrete adapter lives in the AIOS commercial repository (closed
source) per ADR-0004 § 4 (dependency direction):

    AIOS depends on Attestplane (pins ``attestplane>=0.0.1-alpha``).
    Attestplane does not depend on AIOS — ever.

If you are looking for an importable ``AIOSAdapter`` class, it is not here
and will not be added. The substrate OSS tree does not ship runtime
adapters; only the abstract :class:`~attestplane.adapters.GenericRuntimeAdapter`
base class.

Contract
--------

An AIOS adapter MUST:

1. Subclass :class:`~attestplane.adapters.GenericRuntimeAdapter` with
   ``RuntimeEvent`` bound to the AIOS event union type (``aios.audit.Event``
   or equivalent in the AIOS repo).
2. Set ``runtime_name = "aios"`` and ``schema_version`` equal to the AIOS
   audit-event schema version it targets.
3. Implement ``translate(runtime_event) → EventDraft`` purely (no I/O, no
   clock reads, no calls back into AIOS).
4. Map AIOS event kinds to Attestplane evidence event types per the table
   below (ADR-0004 § 2):

   ===========================  ====================================
   AIOS event kind              Attestplane ``event_type``
   ===========================  ====================================
   ``lease_granted``            ``lease_lifecycle_event``
   ``lease_consumed``           ``lease_lifecycle_event``
   ``lease_expired``            ``lease_lifecycle_event``
   ``lease_revoked``            ``lease_lifecycle_event``
   ``budget_decision``          ``budget_event``
   ``settlement_requested``     ``settlement_event``
   ``settlement_verified``      ``settlement_event``
   ``settlement_completed``     ``settlement_event``
   ``worker_assigned``          ``worker_assignment_event``
   ``runtime_started``          ``runtime_lifecycle_event``
   ``runtime_stopped``          ``runtime_lifecycle_event``
   ``gateway_decision``         ``gateway_decision_event``
   ``admin_action``             ``admin_action_event``
   ``distributed_dispatch``     ``distributed_dispatch_event``
   ``policy_check``             ``policy_check_event``
   ``state_transition``         ``state_transition_event``
   ``cancel``                   ``cancel_event``
   ``routing``                  ``routing_event``
   ``eval``                     ``eval_event``
   ``budget_exceeded``          ``budget_exceeded_event``
   ===========================  ====================================

5. Redact per the ADR-0004 § 2 redaction column. Concretely:

   - Lease events: drop ``lease_secret``, ``token_body``, ``signing_key``.
   - Budget events: drop ``customer_billing_id``, ``invoice_ref``.
   - Settlement events: drop ``payment_instrument``, ``account_number``,
     ``card_pan``.
   - Worker events: drop ``worker_auth_token``, ``worker_jwt``.
   - Runtime events: drop ``process_credentials``, ``env_secrets``.
   - Gateway events: drop ``auth_headers``, ``bearer_token``.
   - Admin events: drop ``admin_credentials``, ``internal_user_name``;
     hash user identifiers via :class:`~attestplane.types.SubjectRef`
     ``scheme="sha256_salted"``.
   - Distributed events: drop ``worker_network_address`` (substitute hash).
   - Policy events: hash ``policy_expression_body``; never include the
     raw expression text.

6. Wrap any AIOS subject identifier (``aios_user_id``, ``tenant_user_id``,
   ``operator_id``) in :class:`~attestplane.types.SubjectRef` with
   ``scheme="sha256_salted"`` before placing it in the returned draft.
   Raw direct identifiers in ``payload`` are a GDPR Art. 4(5) violation.

7. Populate the EU AI Act Art. 12(2)(a) fields when the AIOS event
   carries the corresponding context:

   - ``session_id`` ← AIOS ``run_id`` (string-encoded)
   - ``reference_db_ref`` ← AIOS ``policy_id`` for policy_check events,
     ``budget_id`` for budget events
   - ``matched_input_ref`` ← AIOS ``artifact_sha256`` when present
   - ``human_verifier`` ← :class:`~attestplane.types.SubjectRef` of the
     human reviewer for events that carry HITL evidence

Anti-requirements (an AIOS adapter MUST NOT)
--------------------------------------------

- Implement ``execute``, ``grant``, ``decide``, ``schedule``, or any
  other authority/execution verb. The ABC's ``__init_subclass__`` hook
  rejects these names at class-creation time.
- Call back into the AIOS API to enrich an event. If the AIOS event
  lacks needed context, AIOS must emit a richer event upstream — not the
  adapter.
- Persist or cache state across ``translate`` calls. Adapters are pure
  translators; statefulness belongs in the runtime or the substrate.
- Synthesize ``timestamp``, ``event_id``, ``seq``, ``prev_hash``, or
  ``event_hash``. Those are substrate-assigned only.
- Bridge the dependency direction. The AIOS adapter lives in the AIOS
  repository and depends on Attestplane; it never gets pulled into the
  Attestplane substrate tree even as an optional dependency.

Test fixtures
-------------

A reference set of AIOS-flavoured ``RuntimeEvent`` → ``EventDraft`` pairs
will ship under ``tests/adapters/aios/`` in the AIOS repository, not here.
The substrate side enforces the contract through
:class:`~attestplane.adapters.GenericRuntimeAdapter`'s ``__init_subclass__``
hook and through the unit tests in
``sdk/python/tests/adapters/test_base.py``.

Cross-references
----------------

- ADR-0004 § 1, § 2, § 4: boundary rules
- :class:`attestplane.adapters.GenericRuntimeAdapter`: the ABC to subclass
- :class:`attestplane.types.SubjectRef`: GDPR pseudonymization gate
- :class:`attestplane.types.EventDraft`: the only output type
- Migration plan ticket #4 (this file) and ticket #8 (concrete AIOS
  adapter implementation in M5, in the AIOS repo)
"""
