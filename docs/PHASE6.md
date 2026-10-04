# Phase 6 — Advanced Intelligence

Phase 6 begins with deterministic, local-first watchlists and discovery change detection.

- Watchlists persist bounded public-data queries and schedules.
- Due schedules can be inspected without executing external work.
- Alerts compare persisted discovery runs for new, dropped, and materially changed engineers.
- No notification channel or automated outreach is enabled.

Due watchlists are now connected to the durable worker. Each schedule slot uses a deterministic idempotency key, so repeated scheduler ticks do not create duplicate jobs. Worker execution remains bounded to public GitHub repository search results, applies the configured profile scoring rules, and persists the resulting run through the existing History store.

Alert acknowledgement state is now persisted locally in a separate SQLite store. The protected API can list pending/acknowledged events and acknowledge an event; no external notification channel is enabled.

Repository health intelligence is now implemented as a deterministic, metadata-only assessment of a single public repository. It reports activity age, archive/disabled state, license metadata, security-analysis metadata when available, and a bounded health grade. It is a heuristic signal and explicitly not a vulnerability scan.

Compare-search history is now implemented as a bounded local snapshot store. A protected API and CLI can execute real public GitHub repository searches, retain up to 30 results per snapshot and 20 snapshots per named search, and deterministically report added, removed, star changes, and rank movement. No private GitHub data or credentials are persisted.

Validation note: this branch contains the Phase 6 implementation and regression coverage; the remaining gate is the complete local/CI validation pass before merge.


## Compare-search history

Phase 6 search history stores bounded snapshots of public repository-search results and compares consecutive snapshots by stable repository identity. It reports added repositories, removed repositories, star-count changes, and rank movement. Storage is local SQLite, protected API access is required, and no notification or outreach behavior is enabled.


## Multi-profile comparison

Phase 6 compares up to 10 named profiles against the same bounded set of up to 30 public GitHub users. Each candidate's public repositories are fetched once and scored independently under every profile, making differences in domain fit explicit without mixing profile state. The CLI emits JSON for reproducible inspection; API credentials and private data are never persisted.


## Repository health intelligence

Use the CLI to assess one public repository without cloning it:

    snb repo-health owner/repository

The assessment is intentionally conservative and explainable. It does not claim to find vulnerabilities, inspect private code, or mutate GitHub state. The score is based only on public repository metadata and reports its limitations alongside the result.


## Organization intelligence

Discovery runs now aggregate public organization memberships already present on recommendations. The result includes member count, aggregate and average recommendation score, score share across the run, domain diversity, and the strongest matching domains. Membership is deduplicated per engineer and the output is bounded; no additional private organization data is collected.


## Security technology taxonomy

Public repository metadata can now be classified into a bounded security taxonomy covering cloud security, identity/zero trust, application security, detection engineering, Linux/eBPF, security automation, vulnerability research, and software supply-chain security. Matches include the keyword evidence used for the classification so the result remains explainable and reproducible.


## Graph snapshots and standard formats

Saved discovery graphs can now be exported deterministically from local history:

    snb graph-export --history-db data/history.db --format graphml --output reports/network.graphml

Supported formats are JSON, edge list/TSV, GraphML, and GEXF. Node and edge ordering is normalized so repeated exports of the same graph are reproducible. Export is local and read-only.


## Public data-source integration

The platform now includes an optional, bounded CISA Known Exploited Vulnerabilities integration at /api/v1/public/threats/kev. It requires no credential, caps the returned catalog slice, validates the response shape, and returns only selected public vulnerability metadata. Upstream failure is surfaced as a controlled 502 response. The integration is contextual threat intelligence; it does not claim that a repository or engineer is vulnerable.
