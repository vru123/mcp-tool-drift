# MCP tool drift

**Do the tools behind third-party MCP servers change after you approve them?** This repo installs historical releases of 20 public MCP servers, asks each one what tools it offers, and diffs what an agent would read from one release to the next: tool names, descriptions, input schemas and risk hints (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`). It then checks whether public release notes said anything about the changes.

It backs the article *The Tool You Approved Isn't the Tool That's Running*.

## Results (snapshot taken 5 October 2026)

| Measure | Result |
| --- | --- |
| Servers / releases sampled / releases probed successfully | 20 / 181 / 172 |
| Intervals between consecutive sampled releases | 152 |
| Intervals where something an agent reads changed (beyond formatting) | 108 (71%) |
| Intervals with at least one change routed **hold** (re-approve before use) | 90 (59%) |
| Servers with at least one hold change | 19 of 20 (only `fetch` never changed) |
| Already-declared risk hints that flipped | 12, on 4 servers; 10 made the tool riskier |
| Risk hints declared for the first time on an existing tool | 458 |
| Hold intervals with no breaking-change version signal (patch/minor or date-based versions) | 55 of 90 |
| Hold intervals with no release notes, or notes that mention none of the changes | 63 of 90 |
| Risk-hint flips described in release notes | 0 of 12 (2 covered by a blanket "updated hints for all tools" line) |

Full numbers: [`data/derived/summary.json`](data/derived/summary.json) and [`data/derived/disclosure_summary.json`](data/derived/disclosure_summary.json).

## Servers

| Group | Servers (package) |
| --- | --- |
| Official reference | filesystem, memory, everything, sequential-thinking (npm `@modelcontextprotocol/server-*`); fetch, git, time (PyPI `mcp-server-*`) |
| Data and cloud | `@azure/mcp`, `@supabase/mcp-server-supabase`, `mcp-server-kubernetes` |
| Work and business | `@notionhq/notion-mcp-server`, `@hubspot/mcp-server`, `@stripe/mcp`, `figma-developer-mcp`, `@sentry/mcp-server`, `@heroku/mcp-server` |
| Agents and browsing | `@playwright/mcp`, `firecrawl-mcp`, `@browserbasehq/mcp-server-browserbase`, `@upstash/context7-mcp` |

Excluded: Cloudflare (no releases in the window), Snowflake (needs a real account configuration to start), AWS Core (dependencies would not resolve under date pinning).

## Method

1. **Sample.** For each server, up to 10 stable releases published 1 April 2025 to 5 October 2026, evenly spread across that server's releases, with the first and last always included. Unpublished versions are excluded. The sample is fixed in `data/meta/releases.json`.
2. **Install as of the release date.** npm `--before=<release date + 2 days>`; `uvx --exclude-newer <release date + 2 days>`. Dependencies are the versions available just after the release shipped.
3. **Probe.** Each server starts with fake credentials in a throwaway directory. `scripts/probe.js` sends only `initialize`, `notifications/initialized` and `tools/list` (following pagination), saves the reply and kills the process. **No tool is ever called.**
4. **Diff** consecutive successfully probed releases (`scripts/diff.py`). Risk hints are compared as *effective* values: a hint a server does not declare takes the MCP specification's default (`readOnlyHint=false`, `destructiveHint=true`, `idempotentHint=false`, `openWorldHint=true`).
5. **Code** each change with a proposed code and route (below). The 24 description changes flagged as possible scope changes were reviewed by hand (`data/derived/scope_review.csv`).
6. **Disclosure** (`scripts/fetch_notes.py`, `scripts/disclosure.py`). Release notes from GitHub release pages and CHANGELOG files, covering every version inside each interval, not only the sampled ones. Matching is deliberately generous: the tool's name anywhere in the notes counts as disclosed (for hint changes, any mention of annotations or hints also counts). Manual corrections are listed in `data/meta/disclosure_overrides.json`.

### Codebook (proposed, for review)

| Code | Meaning | Route |
| --- | --- | --- |
| C0 | Serialization noise: `$schema`/`additionalProperties`, whitespace-only text | log |
| C1 | Cosmetic: description or parameter-description rewording, no change in capability | log |
| C1s | Safety or usage guidance added to a description | log |
| C2 | Capability expansion: new parameter, or a description claiming broader capability | **hold** |
| C2b | Contract change: types, enums, defaults, limits or required parameters changed | **hold** |
| C3a / C3b / C3c | Risk hint flipped (declared in both releases) / introduced (newly declared, differs from the default) / withdrawn | **hold** |
| C4 | New tool | **hold** |
| C5 | Tool or parameter removed | log |

Rows marked `(review)` or without `(manual)` in `proposed_code` are machine-assigned. Use the `reviewer_code` and `reviewer_note` columns in `data/derived/changes.csv` to record your own coding.

## Repository layout

```
servers.json                     server list, launch args, fake credentials, exclusions
scripts/list_releases.py         draw the release sample (writes data/meta/releases.json)
scripts/run_batch.py             resumable, time-boxed sweep: install, probe, save
scripts/probe.js                 stdio MCP client: initialize + tools/list only
scripts/mock_supabase_content_api.cjs   fixed placeholder for Supabase's live docs schema
scripts/bundle_raw.py            merge per-release snapshots into data/raw/<server>.json
scripts/diff.py                  consecutive-release diff + proposed codes
scripts/apply_review.py          merge manual review into changes.csv
scripts/summarize.py             headline numbers + chart timeline
scripts/fetch_notes.py           collect release notes
scripts/disclosure.py            score disclosure of hold changes
scripts/run_all.sh               the pipeline
data/raw/<server>.json           tools/list snapshot for every sampled release (incl. failures with reasons)
data/meta/                       release sample, probe failure notes, disclosure overrides
data/notes/<server>.json         release notes text per version, with source URLs
data/derived/                    changes.csv, pairs.csv, scope_review.csv, disclosure.csv, timeline.csv, summaries
```

## Reproduce

Requires Node 20+, Python 3.11+ and [uv](https://docs.astral.sh/uv/). Use a personal machine or a disposable VM.

```sh
./scripts/run_all.sh            # re-run the analysis from the committed snapshots (seconds)
./scripts/run_all.sh --resweep  # re-install and re-probe all 181 releases first (about 15-20 minutes)
```

A resweep should reproduce the same tool lists, because installs are date-pinned. Differences would come from packages since removed from npm/PyPI, or from a different Node version.

## Probe failures (9 of 181)

Listed with reasons in `data/meta/probe_failures.json`:

- **Stripe 0.3.0–0.3.3** are thin relays to Stripe's hosted server (`mcp.stripe.com`). The package defines no tools, so the definitions can change with no release.
- **Heroku 1.2.6, 1.2.8 and 1.2.10** do not start (broken ESM import).
- **Sentry 0.2.0** is library-only, with no runnable server.
- **Firecrawl 3.1.2** has a dependency first published after the release itself.

## Limitations

- **Intervals, not releases.** With up to 10 sampled releases per server, one interval can span several releases. A change that was made and reversed inside an interval is invisible, and counts are per interval.
- **Packages, not deployments.** Hosted MCP servers can change with no release at all, so these rates are a floor for what agents actually see.
- **Fake credentials.** Some servers may list different tools once authenticated.
- **Supabase** `search_docs` pastes a schema fetched live from supabase.com into its own description at list time. It was replaced with a fixed placeholder (`scripts/mock_supabase_content_api.cjs`).
- **Azure's** default grouping of tools changed between releases, which inflates its added and removed tool counts.
- **Unreviewed rewordings.** Only 24 description changes were reviewed by hand. The other 211 rewordings carry a proposed "cosmetic" code, so capability-expansion counts are a lower bound.
- **Generous disclosure matching**, which flatters vendors.

## Safety

No tool was invoked, no real credentials were used, and servers ran against an empty sandbox directory and a dummy kubeconfig pointing at `127.0.0.1`.
