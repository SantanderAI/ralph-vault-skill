# Action: external provider research

Use this reference when a technology file needs public facts about a third-party
API, SDK, managed service, or data provider and the repo docs do not contain
enough evidence to fill the notes safely.

This is an evidence-gathering pass for `technologies/<name>.md`. It does not
replace the dependency inventory in `references/dependencies.md`; it improves the
quality of a single technology page when fields such as limits, regions,
authentication model, pricing, data retention, or official documentation links
would otherwise be guessed.

## When

- A `technologies/<name>.md` page would otherwise contain vague `TBD` notes.
- A repo mentions an external provider but only shows the SDK name or env var.
- An agent needs source-backed context before summarizing provider constraints.
- Security, privacy, or procurement details matter for how the provider is used.

## Source Rules

- Prefer official docs, API references, pricing pages, security pages, data
  processing pages, and status or limits pages.
- Use reputable secondary sources only when official docs do not answer the
  question, and label them as secondary.
- Preserve source URLs for every provider fact that affects architecture,
  operations, security, pricing, or data retention.
- Never paste secrets, customer data, private endpoints, internal URLs, account
  IDs, or credentials into the vault.
- If a fact is not public or cannot be verified, write `Not found in public
  sources` instead of guessing.

## Suggested Web Research Path

Use whatever web search or fetch tool your agent already has to retrieve the
official provider context before writing the technology page. This guidance is
tool-agnostic: any search/fetch capability works, and the source rules below
matter more than the choice of tool. Favor tools and settings that return
clean, sourced content with source URLs, and that fit your project's privacy and
data-handling requirements.

For a known official URL, fetch the page directly:

```text
Fetch {official_provider_url}. Extract product purpose, authentication model,
rate limits or usage limits, pricing model, data retention statement, security
or compliance notes, and source URLs. Use null for fields not present.
```

For an SDK or provider name without a known URL, search first, then fetch:

```text
Find the official documentation for "{provider_name}" {provider_context}.
Prefer the provider's own docs, API reference, pricing page, security page, and
data retention or privacy page. Extract product purpose, authentication model,
rate limits or usage limits, pricing model, data retention statement, security
or compliance notes, and source URLs. Do not use unofficial pages unless no
official source answers the field, and label secondary sources.
```

Use date or domain filters only when the task already provides the source family
or time window. Do not invent domains.

## How To Write The Technology Page

In `technologies/<name>.md`, keep the repo-derived reverse index separate from
provider facts:

- `Repos that use it`: evidence from local repo docs or source paths only.
- `Notes`: concise source-backed provider facts with inline source URLs.
- `Constraints`: limits, regions, data retention, pricing, security, or auth
  requirements that affect agent or system behavior.
- `Unknowns`: facts that were searched for but not found.

Do not make the technology page a product brochure. The useful output is a
bounded operational card an agent can trust while working in the repo.

## Output Trace

```text
EXTERNAL PROVIDER RESEARCH OK - technologies/{name} - sources: {N}
```
