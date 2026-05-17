# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Multi-TSA fan-out composite per ADR-0003 § 2.

Plurality of TSAs (≥ 2 independent providers anchoring the same chain
tip) is the recommended deployment, because a single TSA is one PKI
root of trust, which collapses to the same failure mode as trusting
Attestplane.

:class:`MultiTSAProvider` fans out a single :class:`TimestampRequest`
to N providers and returns N :class:`AnchorRecord` instances. Callers
persist all of them as separate sidecar rows; the verifier
(:func:`~attestplane.anchoring.verifier.verify_chain_with_anchors`)
accepts a list of anchors per chain head.

Fan-out is sequential in v1 for simplicity. M6 may parallelise via
``concurrent.futures.ThreadPoolExecutor``; the API is forward
compatible because the return type is already a list, and providers
are stateless under the v1 contract.
"""

from __future__ import annotations

from attestplane.anchoring.base import (
    ANCHOR_SCHEMA_VERSION,
    AnchorRecord,
    TimestampRequest,
    TSAProvider,
    TSAUnavailableError,
)


class MultiTSAProvider:
    """Composite that fans out one request to multiple TSA providers.

    The composite is intentionally **not** itself a :class:`TSAProvider`
    subclass: a TSAProvider returns one AnchorRecord per request, but
    the composite returns N. Conflating them would force callers to
    flatten or unwrap, defeating the type-level distinction between
    "single anchor" and "anchor set".

    Failure semantics: any provider's :class:`TSAUnavailableError` is
    raised immediately by default. Pass ``tolerate_partial=True`` to
    collect the AnchorRecords from successful providers and return a
    partial result; the caller decides whether N=k for k<N is
    sufficient. Use this when ADR-0003's "≥ 2 independent TSAs"
    recommendation is met by a strict subset of configured providers.
    """

    def __init__(
        self,
        providers: list[TSAProvider],
        *,
        tolerate_partial: bool = False,
    ) -> None:
        if not providers:
            raise ValueError("MultiTSAProvider requires at least one provider")
        seen_ids = {p.provider_id for p in providers}
        if len(seen_ids) != len(providers):
            raise ValueError(
                "MultiTSAProvider providers must have distinct provider_id values"
            )
        for p in providers:
            if p.schema_version != ANCHOR_SCHEMA_VERSION:
                raise ValueError(
                    f"provider {p.provider_id!r} has schema_version={p.schema_version}; "
                    f"this composite only handles ANCHOR_SCHEMA_VERSION={ANCHOR_SCHEMA_VERSION}"
                )
        self._providers = list(providers)
        self._tolerate_partial = tolerate_partial

    @property
    def provider_ids(self) -> tuple[str, ...]:
        """Tuple of the configured provider ids, in order."""
        return tuple(p.provider_id for p in self._providers)

    def request_timestamps(
        self, request: TimestampRequest, **kwargs: object,
    ) -> list[AnchorRecord]:
        """Fan out ``request`` to every provider; return the AnchorRecord list.

        ``kwargs`` are forwarded to each provider's
        :meth:`TSAProvider.request_timestamp` call. The mock provider
        accepts ``anchored_seq`` and ``now``; production providers may
        accept additional flags.

        If ``tolerate_partial=True`` was passed to the constructor and
        at least one provider succeeds, returns the partial list;
        otherwise re-raises the first :class:`TSAUnavailableError`.
        """
        results: list[AnchorRecord] = []
        first_error: TSAUnavailableError | None = None
        for provider in self._providers:
            try:
                results.append(provider.request_timestamp(request, **kwargs))
            except TSAUnavailableError as exc:
                if not self._tolerate_partial:
                    raise
                if first_error is None:
                    first_error = exc
        if self._tolerate_partial and not results and first_error is not None:
            raise first_error
        return results


__all__ = ["MultiTSAProvider"]
