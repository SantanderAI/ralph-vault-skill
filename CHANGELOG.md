# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Open-source readiness scaffolding:
  - Apache 2.0 `LICENSE` + `NOTICE`, `CONTRIBUTING.md` (CLA), `CODE_OF_CONDUCT.md`,
    `SECURITY.md`, `CODEOWNERS`
  - Issue templates (bug, feature) and PR template
  - `pyproject.toml` tooling config (ruff, black, mypy, pytest, coverage)
  - SPDX headers on Python sources
  - Test suite for `scripts/gv.py` (99% branch coverage)
  - GitHub Actions workflows (third-party actions pinned to SHA digests):
    - `ci.yml` — ruff + black + mypy + pytest matrix (3.10/3.11/3.12) with Codecov
    - `codeql.yml` — CodeQL SAST (push, PR, weekly cron)
    - `dep-scan.yml` — `pip-audit` (push, PR, daily cron)
    - `license-check.yml` — SPDX header verification + no-runtime-deps guard
    - `pattern-check.yml` — internal-pattern scan with allowlist
    - `scorecard.yml` — OpenSSF Scorecard supply-chain analysis
    - `cla.yml` — CLA Assistant Lite
    - `stale.yml` — stale issues/PRs automation
    - `release.yml` — versioned skill archive attached to GitHub Releases
  - `.github/dependabot.yml` — monthly Python and GitHub Actions updates
  - README badges, tagline, and Requirements/Contributing/Security/License/Citation sections

## [0.1.0] - 2026-06-11

### Added
- `ralph-vault` agent skill: project-agnostic, progressive-disclosure knowledge
  vault ("deepwiki") for one or many code repositories
- `scripts/gv.py` — stdlib-only CLI backbone with subcommands:
  `init`, `add`, `delete`, `list`, `check`, `validate`, `plan`, `mark-synced`,
  `changelog`
- Tiered vault structure (index, domains, repos, components, infrastructure,
  technologies, relations, cross-cutting, adrs, glossary, agent-context, meta)
- Per-repo registry in `.ralphvault/config.json` (no hardcoded repos)
- Path-aware staleness detection and module-level incremental sync via
  `source_globs`
- Deterministic validation gate: frontmatter, wikilinks, token budgets,
  no-source-code rule, and source-backlink checks
- FIXED prompts for ralph-loop content generation under `assets/prompts/`
- `install.sh` for copying the skill into Codex/Claude/Gemini skill directories

[Unreleased]: https://github.com/SantanderAI/ralph-vault-skill/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/SantanderAI/ralph-vault-skill/releases/tag/v0.1.0
