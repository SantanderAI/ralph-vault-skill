#!/usr/bin/env python3
# Copyright (c) 2026 Santander Group
# SPDX-License-Identifier: Apache-2.0
"""ralph-vault CLI (gv) — deterministic backbone for the ralph-vault skill.

A project-agnostic deepwiki "vault" lifecycle tool. Generation of document
*content* is LLM work (driven by the FIXED prompts in ../assets/prompts via a
ralph loop); this script owns everything *deterministic*: scaffolding the tier
structure, the repo/subdir registry, status reporting and validation.

Stdlib only. No third-party deps. Works on any repo, any stack.

Subcommands:
  init      Create the vault tier structure + config if missing (idempotent).
  add       Register a repo or subdirectory to document.
  delete    Unregister a repo/subdir (optionally purge its docs).
  list      Show the registry + per-entry status.
  check     Report what is missing / incomplete / stale.
  validate  Frontmatter / wikilink / token-budget gate over the vault.
  plan      Emit plan/plan.md + plan/task/NN.md for a ralph loop.
  mark-synced  Advance a repo's last_sync_commit + log to meta/changelog.md.
  mark-reconciled  Advance last_reconcile_commit (omission-audit baseline).
  changelog    Print recent sync-log entries (filter by --repo / --since).

Config lives at <vault>/.ralphvault/config.json.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn

SCHEMA_VERSION = 1

# Skill root (scripts/ is a child of it); used to locate FIXED assets.
SKILL_ROOT = Path(__file__).resolve().parent.parent
STACK_TASKS_DIR = SKILL_ROOT / "assets" / "stack-tasks"

TIERS = {
    "index": "Cross-repo indexes (repo list, tech stack, domain map).",
    "domains": "Bounded contexts identified across repos.",
    "repos": "Per-repo deep documentation.",
    "components": "Shared components/libraries reused across ≥ 2 repos.",
    "infrastructure": "Deployable infra pieces the system runs on.",
    "technologies": "External SDKs/providers consumed by repos.",
    "relations": "Typed edges between repos (grpc/http/kafka/db/code/secret/apm).",
    "cross-cutting": "Shared concerns (auth, errors, observability, testing).",
    "adrs": "Architecture decision records.",
    "glossary": "Canonical project terms.",
    "agent-context": "Tier-1 cards, codegen rules, loading recipes.",
    "meta": "Vault hygiene: pending queues, frontmatter spec, changelog.",
}

# Tier 0/1 entry points are always loaded; deeper tiers load on demand.
LOAD_TIER = {
    "index": 1,
    "domains": 2,
    "repos": 2,
    "components": 2,
    "infrastructure": 2,
    "technologies": 2,
    "relations": 2,
    "cross-cutting": 2,
    "adrs": 3,
    "glossary": 2,
    "agent-context": 1,
    "meta": "never",
}

# Edge categories for the relations tier (subdirs created on demand by prompts).
RELATION_KINDS = ("grpc", "http", "kafka", "db", "code", "secret", "apm", "other")

# Commits touching a repo's source after which a full omission audit (reconcile)
# falls due, even if commit-equality still reports "up to date". Decouples the
# completeness re-read from change detection: pre-existing omission does not
# correlate with new commits, so it needs an occasional cadence-driven re-look.
RECONCILE_AFTER_COMMITS = 25

DEFAULT_SETTINGS = {
    "token_budget": 2000,
    "required_frontmatter": ["type", "load_tier", "schema_version"],
    "glossary": "glossary/terms.md",
    "reconcile_after_commits": RECONCILE_AFTER_COMMITS,
}

CONFIG_REL = ".ralphvault/config.json"


# --------------------------------------------------------------------------- #
# Config helpers
# --------------------------------------------------------------------------- #
def config_path(vault: Path) -> Path:
    return vault / CONFIG_REL


def load_config(vault: Path) -> dict:
    p = config_path(vault)
    if not p.exists():
        die(f"no vault config at {p}. Run `gv.py init --vault {vault}` first.")
    return json.loads(p.read_text(encoding="utf-8"))


def save_config(vault: Path, cfg: dict) -> None:
    p = config_path(vault)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def find_repo(cfg: dict, name: str) -> dict | None:
    return next((r for r in cfg["repos"] if r["name"] == name), None)


# --------------------------------------------------------------------------- #
# Output helpers
# --------------------------------------------------------------------------- #
def die(msg: str, code: int = 2) -> NoReturn:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def info(msg: str) -> None:
    print(msg)


def git_root(path: Path) -> Path | None:
    """Enclosing git worktree root for an arbitrary path (whole repo or subdir)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(out.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def git_path_head(path: Path) -> str | None:
    """Short SHA of the last commit that touched `path`.

    Path-aware: for a whole repo this is effectively HEAD; for a subdir it is the
    last commit that modified that subtree (so a subdir is not marked stale when an
    unrelated part of the monorepo moves).
    """
    path = path.resolve()
    root = git_root(path)
    if root is None:
        return None
    rel = os.path.relpath(path, root.resolve())
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "log", "-1", "--format=%h", "--", rel],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def git_changed_paths(path: Path, since: str) -> list[str] | None:
    """Files under `path` changed between `since`..HEAD, relative to `path`.

    Returns None if the diff cannot be computed (no git root, or `since` no longer
    reachable after a rebase/force-push) — callers treat that as a full refresh.
    """
    path = path.resolve()
    root = git_root(path)
    if root is None:
        return None
    rel = os.path.relpath(path, root.resolve())
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only", f"{since}..HEAD", "--", rel],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    files = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
    if rel not in (".", ""):
        prefix = rel.rstrip("/") + "/"
        files = [f[len(prefix) :] if f.startswith(prefix) else f for f in files]
    return files


def git_tracked_files(path: Path) -> list[str] | None:
    """Tracked files under `path`, relative to `path` (honours .gitignore).

    Like `git_changed_paths` but the whole current inventory rather than a diff.
    Used to compute file-level coverage (which source files no doc claims). Returns
    None when there is no git root, so callers skip the coverage advisory.
    """
    path = path.resolve()
    root = git_root(path)
    if root is None:
        return None
    rel = os.path.relpath(path, root.resolve())
    target = rel if rel not in (".", "") else "."
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--", target],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    files = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
    if rel not in (".", ""):
        prefix = rel.rstrip("/") + "/"
        files = [f[len(prefix) :] if f.startswith(prefix) else f for f in files]
    return files


def git_commit_distance(path: Path, since: str) -> int | None:
    """Count of commits touching `path` in `since`..HEAD, or None if uncomputable.

    Path-aware like the other git helpers. Used to drive the reconcile cadence.
    """
    path = path.resolve()
    root = git_root(path)
    if root is None:
        return None
    rel = os.path.relpath(path, root.resolve())
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "rev-list", "--count", f"{since}..HEAD", "--", rel],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    try:
        return int(out.stdout.strip())
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# Staleness / selection helpers (shared by check, plan, mark-synced)
# --------------------------------------------------------------------------- #
def entry_staleness(repo: dict) -> tuple[bool, str | None, str | None]:
    """Return (is_stale, head_sha, synced_sha). Only meaningful for path sources."""
    synced = repo.get("last_sync_commit")
    if repo.get("source_kind") != "path":
        return (False, None, synced)
    head = git_path_head(Path(repo["source"]).expanduser())
    is_stale = bool(head and synced and head != synced)
    return (is_stale, head, synced)


def entry_needs_work(vault: Path, repo: dict) -> list[str]:
    """Reasons the entry needs (re)generation: missing docs/card, pending, or stale."""
    name = repo["name"]
    docs = vault / "repos" / name
    card = vault / "agent-context" / "repo-cards" / f"{name}.md"
    reasons: list[str] = []
    if not docs.exists() or not any(docs.glob("*.md")):
        reasons.append("MISSING-DOCS")
    if not card.exists():
        reasons.append("MISSING-CARD")
    if repo.get("phase") != "done":
        reasons.append(f"phase={repo.get('phase')}")
    is_stale, head, synced = entry_staleness(repo)
    if is_stale:
        reasons.append(f"STALE(local {head} != synced {synced})")
    return reasons


def reconcile_due(repo: dict, threshold: int) -> tuple[bool, int | None]:
    """Whether a full LLM omission audit (reconcile) is due, + commits since the last.

    Returns (is_due, commits_since_reconcile). Due when the repo is documented
    (`phase: done`, path source) and either was never reconciled, its audit baseline
    is unreachable, or `threshold` commits have touched the source since. This is the
    cadence that catches omission *inside* already-covered files — the gap the
    deterministic file-level coverage check cannot see. Non-path / non-done repos are
    never due (nothing to audit yet).
    """
    if repo.get("source_kind") != "path" or repo.get("phase") != "done":
        return (False, None)
    last = repo.get("last_reconcile_commit")
    if not last:
        return (True, None)
    dist = git_commit_distance(Path(repo["source"]).expanduser(), last)
    if dist is None:
        return (True, None)
    return (dist > threshold, dist)


def _reconcile_threshold(cfg: dict) -> int:
    return cfg["settings"].get("reconcile_after_commits", RECONCILE_AFTER_COMMITS)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def touch_last_updated(vault: Path) -> None:
    (vault / "LAST-UPDATED.md").write_text(
        f"---\ntype: meta\nload_tier: never\nschema_version: {SCHEMA_VERSION}\ntags: [meta]\n---\n\n"
        f"# Last updated\n\n{now_iso()}\n",
        encoding="utf-8",
    )


# --------------------------------------------------------------------------- #
# init
# --------------------------------------------------------------------------- #
def cmd_init(args) -> int:
    vault = Path(args.vault).resolve()
    vault.mkdir(parents=True, exist_ok=True)
    created = []
    for tier, desc in TIERS.items():
        d = vault / tier
        if not d.exists():
            d.mkdir(parents=True)
            created.append(tier)
        readme = d / "README.md"
        if not readme.exists():
            lt = LOAD_TIER[tier]
            readme.write_text(
                f"---\ntype: section-readme\nload_tier: {json.dumps(lt)}\n"
                f"schema_version: {SCHEMA_VERSION}\ntags: []\n---\n\n"
                f"# {tier}\n\n> When to load: {desc}\n\n"
                f"_Index of this tier. Generated by `gv.py init`; populate via the ralph loop._\n",
                encoding="utf-8",
            )

    assets_dir = vault / "assets"
    if not assets_dir.exists():
        assets_dir.mkdir(parents=True)
        (assets_dir / "README.md").write_text(
            f"---\ntype: meta\nload_tier: never\nschema_version: {SCHEMA_VERSION}\ntags: [meta]\n---\n\n"
            "# assets\n\n> Images, diagrams and screenshots referenced from vault docs. Not loaded as context.\n",
            encoding="utf-8",
        )
        created.append("assets/")

    cfg_p = config_path(vault)
    if cfg_p.exists():
        info(f"config already present at {cfg_p} (left untouched)")
    else:
        save_config(
            vault,
            {
                "schema_version": SCHEMA_VERSION,
                "project": args.project or vault.name,
                "vault_root": ".",
                "settings": dict(DEFAULT_SETTINGS),
                "repos": [],
            },
        )
        created.append(CONFIG_REL)

    root_readme = vault / "README.md"
    if not root_readme.exists():
        root_readme.write_text(
            f"---\ntype: vault-readme\nload_tier: 0\nschema_version: {SCHEMA_VERSION}\ntags: []\n---\n\n"
            f"# {args.project or vault.name} — Knowledge Vault\n\n"
            "> Entry point (Tier 0). Load this first, then descend by tier on demand.\n\n"
            "## Tiers\n\n"
            + "\n".join(f"- **{t}** — {d}" for t, d in TIERS.items())
            + "\n\nManaged by the `ralph-vault` skill. See `.ralphvault/config.json` for the repo registry.\n",
            encoding="utf-8",
        )
        created.append("README.md")

    if not (vault / "LAST-UPDATED.md").exists():
        created.append("LAST-UPDATED.md")
    touch_last_updated(vault)

    info(f"vault ready at {vault}")
    info(f"created: {', '.join(created) if created else '(nothing — already initialized)'}")
    return 0


# --------------------------------------------------------------------------- #
# add / delete / list
# --------------------------------------------------------------------------- #
def cmd_add(args) -> int:
    vault = Path(args.vault).resolve()
    cfg = load_config(vault)
    if find_repo(cfg, args.name):
        die(f"'{args.name}' is already registered. Use a different name or `delete` first.")
    if not args.path and not args.url:
        die("provide --path (local) or --url (remote) for the source.")
    entry = {
        "name": args.name,
        "source": args.path or args.url,
        "source_kind": "path" if args.path else "url",
        "kind": "subdir" if args.subdir else "repo",
        "stack": args.stack or "auto",
        "phase": "pending",
        "last_sync_commit": None,
        "last_reconcile_commit": None,
    }
    cfg["repos"].append(entry)
    save_config(vault, cfg)
    touch_last_updated(vault)
    info(f"registered {entry['kind']} '{args.name}' (stack={entry['stack']}, phase=pending)")
    info(f"next: run `gv.py plan --repo {args.name}` then drive the ralph loop to document it.")
    return 0


def cmd_delete(args) -> int:
    vault = Path(args.vault).resolve()
    cfg = load_config(vault)
    entry = find_repo(cfg, args.name)
    if not entry:
        die(f"'{args.name}' is not registered.")
    cfg["repos"] = [r for r in cfg["repos"] if r["name"] != args.name]
    save_config(vault, cfg)
    touch_last_updated(vault)
    info(f"unregistered '{args.name}'")
    if args.purge:
        docs = vault / "repos" / args.name
        card = vault / "agent-context" / "repo-cards" / f"{args.name}.md"
        for target in (docs, card):
            if target.exists():
                _rmtree(target)
                info(f"purged {target.relative_to(vault)}")
    else:
        info("docs left in place (use --purge to also delete repos/<name>/ and its repo-card).")
    return 0


def _rmtree(path: Path) -> None:
    if path.is_dir():
        for child in sorted(path.rglob("*"), reverse=True):
            child.rmdir() if child.is_dir() else child.unlink()
        path.rmdir()
    else:
        path.unlink()


def cmd_list(args) -> int:
    vault = Path(args.vault).resolve()
    cfg = load_config(vault)
    if not cfg["repos"]:
        info("registry is empty. Add one with `gv.py add --name <n> --path <p> --stack <s>`.")
        return 0
    info(f"{'NAME':28} {'KIND':8} {'STACK':10} {'PHASE':9} SOURCE")
    for r in cfg["repos"]:
        info(f"{r['name']:28} {r['kind']:8} {r['stack']:10} {r['phase']:9} {r['source']}")
    return 0


# --------------------------------------------------------------------------- #
# check
# --------------------------------------------------------------------------- #
GRAPH_TIER_DIRS = ("relations", "components", "infrastructure", "technologies")


def _graph_refs_to_repo(vault: Path, name: str) -> list[str]:
    """Graph-tier docs that wikilink to `repos/<name>/` (i.e. may go stale with it)."""
    needle = f"repos/{name}/"
    hits = []
    for tier in GRAPH_TIER_DIRS:
        d = vault / tier
        if not d.exists():
            continue
        for p in sorted(d.rglob("*.md")):
            if p.stem == "README":
                continue
            if needle in p.read_text(encoding="utf-8", errors="replace"):
                hits.append(str(p.relative_to(vault)))
    return hits


def _sample(items: list[str], n: int = 8) -> str:
    """Comma-joined first `n` items with an ellipsis when truncated."""
    return ", ".join(items[:n]) + (" …" if len(items) > n else "")


def cmd_check(args) -> int:
    vault = Path(args.vault).resolve()
    cfg = load_config(vault)
    problems = 0
    for r in cfg["repos"]:
        name = r["name"]
        status = entry_needs_work(vault, r)
        if status:
            problems += 1
            info(f"[!] {name}: {', '.join(status)}")
        else:
            info(f"[ok] {name}: up to date")
        # advisory (non-gating): a resolved stack with no tailored section map
        stack = r.get("stack", "auto")
        if stack not in ("auto", "generic") and not (STACK_TASKS_DIR / f"{stack}.md").exists():
            info(
                f"[~] {name}: stack '{stack}' has no tailored section map — falling back to generic"
            )
        # advisory (non-gating): change drift — which sections own the changed source,
        # so the loop knows *what to regenerate* (not just *that* something moved).
        drift = _change_drift(vault, r)
        if drift is not None:
            affected, _unmapped = drift
            if affected:
                info(
                    f"[~] {name}: change-drift → regenerate {len(affected)} section(s): "
                    + _sample(affected)
                )
        # advisory (non-gating): omission — tracked source files no section covers.
        # Catches files undocumented since the original sync, which commit-equality
        # reports as "up to date" forever (the blind spot this whole feature targets).
        if r.get("phase") == "done":
            uncovered = _uncovered_files(vault, r)
            if uncovered:
                info(
                    f"[~] {name}: {len(uncovered)} source file(s) not covered by any "
                    f"section's source_globs — possible omission: " + _sample(uncovered)
                )
        # advisory (non-gating): reconcile due — a full LLM omission audit is overdue
        # by the commit cadence; catches omission *inside* already-covered files.
        due, dist = reconcile_due(r, _reconcile_threshold(cfg))
        if due:
            since = f"{dist} commits since last audit" if dist is not None else "never audited"
            info(f"[~] {name}: reconcile due ({since}) — plan with `--reconcile`")
        # advisory (non-gating): graph docs that reference a stale repo may now be outdated
        if entry_staleness(r)[0]:
            refs = _graph_refs_to_repo(vault, name)
            if refs:
                info(
                    f"[~] {name}: stale repo referenced by {len(refs)} graph doc(s) — review/re-plan: "
                    + _sample(refs)
                )
    info(f"\n{problems} repo(s) need attention, {len(cfg['repos']) - problems} ok.")
    return 1 if problems and args.gate else 0


# --------------------------------------------------------------------------- #
# validate
# --------------------------------------------------------------------------- #
FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
WIKILINK_RE = re.compile(r"(?<!`)\[\[([^\]]+)\]\]")
HEADING_RE = re.compile(r"^#{1,6}\s+(.*?)\s*$", re.MULTILINE)

# Narrow, conservative mojibake signals: the U+FFFD replacement char plus a few
# unambiguous UTF-8-mis-decoded sequences (curly quotes/dashes and common
# accented vowels). Deliberately avoids broad classes like `Ã.`/`Â.` that would
# false-positive on legitimate Latin-language text.
MOJIBAKE_RE = re.compile(r"\uFFFD|â€™|â€œ|â€\x9d|â€“|â€”|Ã©|Ã¨|Ã¬|Ã²|Ã¹")

# Programming-language fences are source code and must not appear in the vault.
CODE_FENCE_LANGS = {
    "python",
    "py",
    "javascript",
    "js",
    "jsx",
    "typescript",
    "ts",
    "tsx",
    "java",
    "kotlin",
    "kt",
    "go",
    "golang",
    "rust",
    "rs",
    "c",
    "cc",
    "cpp",
    "c++",
    "csharp",
    "cs",
    "ruby",
    "rb",
    "php",
    "scala",
    "swift",
    "perl",
    "lua",
    "groovy",
    "dart",
    "elixir",
    "erlang",
    "haskell",
    "clojure",
    "sql",
}
# Diagram/tree fences are structure, not code: exempt from the length heuristic.
FENCE_LEN_EXEMPT = {"text", "txt", "plaintext", "tree", "mermaid", "dot"}
MAX_FENCE_LINES = 20

# Backticked tokens; used to detect a backlink to the original source (R3).
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
# Doc types that are leaves of progressive disclosure and must point back to code.
EVIDENCE_TYPES = {"repo-doc", "module"}


def _parse_frontmatter(text: str) -> dict | None:
    m = FM_RE.match(text)
    if not m:
        return None
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "\t", "-")):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def _vault_md_files(vault: Path):
    for p in vault.rglob("*.md"):
        rel = p.relative_to(vault)
        if rel.parts and rel.parts[0] in (".ralphvault", "plan"):
            continue
        yield p


def _headings(text: str) -> set[str]:
    return {h.strip() for h in HEADING_RE.findall(text)}


def _has_source_citation(text: str) -> bool:
    """True if the doc backticks at least one path-like token (a link to source)."""
    for tok in INLINE_CODE_RE.findall(text):
        t = tok.strip()
        if t.startswith(("http://", "https://")):
            continue
        if "/" in t or re.search(r"\.\w{1,6}(#[\w.]+)?$", t):
            return True
    return False


def _code_fences(text: str):
    """Yield (lang, content_line_count) for each fenced code block."""
    out = []
    open_fence = None  # (fence_char, fence_length)
    lang = ""
    count = 0
    for line in text.splitlines():
        s = line.lstrip()
        if open_fence is None:
            m = re.match(r"^([`~]{3,})\s*([A-Za-z0-9_+\-#.]*)", s)
            if m:
                open_fence = (m.group(1)[0], len(m.group(1)))
                lang = m.group(2).lower()
                count = 0
        else:
            ch, ln = open_fence
            if re.match(rf"^{re.escape(ch)}{{{ln},}}\s*$", s):
                out.append((lang, count))
                open_fence = None
            else:
                count += 1
    return out


def cmd_validate(args) -> int:
    vault = Path(args.vault).resolve()
    cfg = load_config(vault)
    required = cfg["settings"].get("required_frontmatter", DEFAULT_SETTINGS["required_frontmatter"])
    budget = cfg["settings"].get("token_budget", DEFAULT_SETTINGS["token_budget"])
    max_fence = cfg["settings"].get("code_fence_max_lines", MAX_FENCE_LINES)

    # index existing doc stems for wikilink resolution
    stems = set()
    for p in _vault_md_files(vault):
        rel = p.relative_to(vault).with_suffix("")
        stems.add(str(rel))
        stems.add(p.stem)
    dirs = {str(d.relative_to(vault)) for d in vault.rglob("*") if d.is_dir()}

    errors, warnings = [], []
    for p in _vault_md_files(vault):
        rel = p.relative_to(vault)
        text = p.read_text(encoding="utf-8", errors="replace")
        # mojibake / encoding corruption (advisory: warning, never gating)
        hits = MOJIBAKE_RE.findall(text)
        if hits:
            warnings.append(
                f"{rel}: possible mojibake / encoding corruption ({len(hits)} occurrence(s)) — check the file is valid UTF-8"
            )
        fm = _parse_frontmatter(text)
        if fm is None:
            errors.append(f"{rel}: missing YAML frontmatter")
        else:
            for field in required:
                if field not in fm:
                    errors.append(f"{rel}: frontmatter missing required field '{field}'")
            if rel.parts[0] == "relations" and p.stem != "README":
                for ef in ("from", "to", "relation_type"):
                    if ef not in fm:
                        errors.append(f"{rel}: relation edge missing frontmatter field '{ef}'")
        # token budget (rough: words * 1.3)
        approx = int(len(text.split()) * 1.3)
        if approx > budget and p.stem not in ("terms",):
            warnings.append(f"{rel}: ~{approx} tokens > budget {budget}")
        # no source code in the vault (deterministic gate for R5)
        for lang, n in _code_fences(text):
            if lang in CODE_FENCE_LANGS:
                errors.append(
                    f"{rel}: contains a '{lang}' code block ({n} lines) — the vault must not contain source code; summarize at a higher abstraction level"
                )
            elif lang not in FENCE_LEN_EXEMPT and n > max_fence:
                errors.append(
                    f"{rel}: long code fence ({n} lines, lang='{lang or 'none'}') looks like copied source — summarize, or tag as ```text if it is a diagram/tree"
                )
        # backlink to original source (R3): leaf docs must cite the code they summarize
        if fm and fm.get("type") in EVIDENCE_TYPES and not _has_source_citation(text):
            warnings.append(
                f"{rel}: no source-code citation — add a path under '## Evidence' to keep the backlink to the original code"
            )
        # module-level incremental sync (R-incremental): leaf docs should scope their source
        if fm and fm.get("type") in EVIDENCE_TYPES and not _read_source_globs(p):
            warnings.append(
                f"{rel}: no source_globs — sync of this repo falls back to a whole-repo refresh; add source_globs to enable module-level incremental sync"
            )
        # wikilinks
        for raw in WIKILINK_RE.findall(text):
            target = raw.split("|", 1)[0]
            target, _, anchor = target.partition("#")
            target = target.strip()
            if target == "":  # intra-doc anchor
                if anchor and anchor not in _headings(text):
                    warnings.append(f"{rel}: intra-doc anchor '#{anchor}' not found")
                continue
            if target not in stems and target not in dirs:
                errors.append(f"{rel}: wikilink target not found: [[{target}]]")
            elif anchor:
                tp = (vault / target).with_suffix(".md")
                if tp.exists() and anchor not in _headings(
                    tp.read_text(encoding="utf-8", errors="replace")
                ):
                    warnings.append(f"{rel}: anchor '#{anchor}' not found in {target}")

    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    info(
        f"\nvalidate: {len(errors)} error(s), {len(warnings)} warning(s) across vault {vault.name}"
    )
    return 1 if errors else 0


# --------------------------------------------------------------------------- #
# source_globs → affected docs (module-level diff scoping)
# --------------------------------------------------------------------------- #
def _glob_to_re(glob: str) -> re.Pattern:
    """Translate a path glob (supports **, *, ?) to an anchored regex."""
    i, n, out = 0, len(glob), []
    while i < n:
        if glob[i : i + 2] == "**":
            out.append(".*")
            i += 2
            if i < n and glob[i] == "/":
                i += 1
        elif glob[i] == "*":
            out.append("[^/]*")
            i += 1
        elif glob[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def _read_source_globs(path: Path) -> list[str]:
    """Read the optional `source_globs` frontmatter field (flow or block list)."""
    m = FM_RE.match(path.read_text(encoding="utf-8", errors="replace"))
    if not m:
        return []
    lines = m.group(1).splitlines()
    globs: list[str] = []
    for idx, line in enumerate(lines):
        if not line.strip().startswith("source_globs:"):
            continue
        _, _, val = line.partition(":")
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            globs = [g.strip().strip("'\"") for g in val[1:-1].split(",")]
        else:
            for nxt in lines[idx + 1 :]:
                if re.match(r"^\s*-\s+", nxt):
                    globs.append(nxt.strip()[1:].strip().strip("'\""))
                elif nxt.strip() == "":
                    continue
                else:
                    break
        break
    return [g for g in globs if g]


def _affected_docs(
    vault: Path, repo: dict, changed: list[str]
) -> tuple[list[str] | None, list[str]]:
    """Map changed source files to the repo docs that declare `source_globs`.

    Returns (affected_doc_rel_paths, unmapped_changed_files). `affected` is None when
    no doc under the repo declares any `source_globs` yet (legacy vaults) — callers
    fall back to the whole-repo sync keyword mapping in that case.
    """
    repo_dir = vault / "repos" / repo["name"]
    affected: list[str] = []
    matched: set[str] = set()
    any_globs = False
    for p in sorted(repo_dir.rglob("*.md")):
        globs = _read_source_globs(p)
        if not globs:
            continue
        any_globs = True
        pats = [_glob_to_re(g) for g in globs]
        hits = [f for f in changed if any(pat.match(f) for pat in pats)]
        if hits:
            affected.append(str(p.relative_to(vault)))
            matched.update(hits)
    if not any_globs:
        return (None, list(changed))
    unmapped = [f for f in changed if f not in matched]
    return (affected, unmapped)


def _repo_source_globs(vault: Path, repo: dict) -> list[re.Pattern]:
    """All `source_globs` declared across a repo's docs, compiled to regexes."""
    repo_dir = vault / "repos" / repo["name"]
    pats: list[re.Pattern] = []
    for p in sorted(repo_dir.rglob("*.md")):
        for g in _read_source_globs(p):
            pats.append(_glob_to_re(g))
    return pats


def _uncovered_files(vault: Path, repo: dict) -> list[str] | None:
    """Tracked source files under the repo that no doc's `source_globs` covers.

    Deterministic, language-agnostic omission signal (file-level): catches a source
    file no documentation section claims, including one that already existed at sync
    time — the blind spot commit-equality cannot see. Cannot see uncovered items
    *inside* a covered file (that is the LLM reconcile pass's job).

    Returns None — caller skips the advisory — when the repo has no path source, no
    git root, or no doc declares `source_globs` yet (a legacy vault, where the whole
    notion of coverage is undefined; `validate` already warns to add them).
    """
    if repo.get("source_kind") != "path":
        return None
    files = git_tracked_files(Path(repo["source"]).expanduser())
    if files is None:
        return None
    pats = _repo_source_globs(vault, repo)
    if not pats:
        return None
    return [f for f in files if not any(pat.match(f) for pat in pats)]


def _change_drift(vault: Path, repo: dict) -> tuple[list[str] | None, list[str]] | None:
    """For a stale path repo, the (affected_docs, unmapped_changed_files) since sync.

    Returns None when the repo is not stale, has no path source, or no baseline /
    no changed files — i.e. there is no actionable change-drift to report. `affected`
    is None for legacy vaults with no `source_globs` declared (same contract as
    `_affected_docs`), so the caller can tell "no drift" from "cannot scope".
    """
    is_stale, _head, synced = entry_staleness(repo)
    if not is_stale or repo.get("source_kind") != "path" or not synced:
        return None
    changed = git_changed_paths(Path(repo["source"]).expanduser(), synced)
    if not changed:
        return None
    return _affected_docs(vault, repo, changed)


# --------------------------------------------------------------------------- #
# plan  (emit ralph-loop plan files)
# --------------------------------------------------------------------------- #
PLAN_INSTRUCTIONS = """## Loop instructions (ralph)

Each iteration executes **exactly one** subtask and stops. Do not chain.

1. Find the first unchecked `[ ]` subtask (recurse into `task/NN.md` links).
   If none remain anywhere → create `plan/stop.md` and stop.
2. Execute that single subtask, then mark it `[x]`.
   - Documentation subtask: follow the referenced prompt under
     `<skill>/assets/prompts/` against the named repo, write into the vault,
     then run `gv.py validate` before marking done.
   - Graph subtask (relations/components/dependencies): runs **after** all repo
     tasks; follow its prompt across the registered repos, write into the matching
     tier, then run `gv.py validate` before marking done.
3. Stop. Do not look for the next subtask.
"""

# Graph tiers appended after the repo tasks. Each carries a `min_repos` threshold:
# relations/components need ≥ 2 repos (edges / shared consumers); dependencies is
# meaningful for a single repo (it consumes external infra/providers regardless).
GRAPH_TIERS = {
    "relations": (
        2,
        "assets/prompts/relations.md",
        "Generate/refresh typed edges between registered repos.",
        "- [ ] Scan the documented repos for evidenced integrations and write one typed edge per file "
        "under `relations/<kind>/` (grpc/http/kafka/db/code/secret/apm/other).\n"
        "- [ ] Run `gv.py validate --vault <vault>`; fix any edge frontmatter error.\n"
        "- [ ] [juez] verify each edge cites evidence on both ends and both endpoints resolve to a registered repo.\n",
    ),
    "components": (
        2,
        "assets/prompts/components.md",
        "Promote shared components/libraries reused by ≥ 2 registered repos.",
        "- [ ] Identify components consumed by ≥ 2 repos and write one file per component under `components/`.\n"
        "- [ ] Run `gv.py validate --vault <vault>`; fix any error.\n"
        "- [ ] [juez] verify each component lists ≥ 2 consumers with evidence.\n",
    ),
    "dependencies": (
        1,
        "assets/prompts/dependencies.md",
        "Catalogue external infra + providers (reverse index of consuming repos).",
        "- [ ] Write one file per external piece under `infrastructure/` (deployed) or `technologies/` (third-party SDK/API), each listing the consuming repos with evidence.\n"
        "- [ ] Run `gv.py validate --vault <vault>`; fix any error.\n"
        "- [ ] [juez] verify the reverse index is complete and no secrets are pasted.\n",
    ),
}


def _select_targets(args, cfg: dict, vault: Path) -> list[dict]:
    if args.repo:
        return [r for r in cfg["repos"] if r["name"] == args.repo]
    thr = _reconcile_threshold(cfg)
    if getattr(args, "needs_work", False):
        return [r for r in cfg["repos"] if entry_needs_work(vault, r) or reconcile_due(r, thr)[0]]
    if getattr(args, "reconcile", False):
        return [r for r in cfg["repos"] if reconcile_due(r, thr)[0]]
    if getattr(args, "stale", False):
        return [r for r in cfg["repos"] if entry_staleness(r)[0]]
    if args.pending:
        return [r for r in cfg["repos"] if r["phase"] != "done"]
    return list(cfg["repos"])


def _task_mode(vault: Path, repo: dict, cfg: dict) -> str:
    """bootstrap (never done) → sync (done + stale) → reconcile (done + audit due) → sync."""
    if repo.get("phase") != "done":
        return "bootstrap"
    if entry_staleness(repo)[0]:
        return "sync"
    if reconcile_due(repo, _reconcile_threshold(cfg))[0]:
        return "reconcile"
    return "sync"


def cmd_plan(args) -> int:
    vault = Path(args.vault).resolve()
    cfg = load_config(vault)
    targets = _select_targets(args, cfg, vault)
    if args.repo and not targets:
        die(f"'{args.repo}' is not registered.")
    if not targets:
        info("nothing to plan (no matching repos for the given selector).")
        return 0

    plan_dir = Path(args.plan_dir).resolve()
    (plan_dir / "task").mkdir(parents=True, exist_ok=True)

    lines = [
        f"# Vault plan — {cfg.get('project', vault.name)}",
        "",
        PLAN_INSTRUCTIONS,
        "",
        "## Tasks",
        "",
    ]
    n = 0
    for r in targets:
        n += 1
        task_file = f"task/{n:02d}.md"
        mode = _task_mode(vault, r, cfg)
        lines.append(f"- [ ] {r['name']} ({mode}) → {task_file}")
        dest = plan_dir / "task" / f"{n:02d}.md"
        if mode == "reconcile":
            _write_reconcile_task(dest, r, vault)
        else:
            _write_task(dest, r, mode, vault)

    # Always append the graph tasks (relations + components + dependencies) so a
    # plan that (re)builds repos also refreshes the graph. Skipped with --no-graph;
    # each tier also honours its own `min_repos` threshold.
    graph = 0
    if not getattr(args, "no_graph", False):
        nrepos = len(cfg["repos"])
        for tier, spec in GRAPH_TIERS.items():
            if nrepos < spec[0]:
                continue
            n += 1
            graph += 1
            task_file = f"task/{n:02d}.md"
            lines.append(f"- [ ] {tier} (graph) → {task_file}")
            _write_graph_task(plan_dir / "task" / f"{n:02d}.md", tier, cfg)

    (plan_dir / "plan.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    info(
        f"wrote {plan_dir / 'plan.md'} + {n} task file(s) ({len(targets)} repo, {graph} graph) under {plan_dir / 'task'}"
    )
    info("drive it with: ralph-loop.sh <N> plan/plan.md")
    return 0


def _sync_scope_block(repo: dict, vault: Path) -> str:
    """Markdown block describing the diff scope for a sync task (module-level)."""
    is_stale, head, synced = entry_staleness(repo)
    if repo.get("source_kind") != "path":
        return (
            "## Diff scope\n\n"
            "Remote (`url`) source — no local diff. Refresh per `sync.md` and re-stamp provenance.\n\n"
        )
    if not synced or not head:
        return "## Diff scope\n\nNo recorded baseline commit — treat as a full refresh.\n\n"
    changed = git_changed_paths(Path(repo["source"]).expanduser(), synced)
    if changed is None:
        return (
            f"## Diff scope\n\nBaseline `{synced}` not reachable (rebase/force-push). "
            "Treat as a full refresh.\n\n"
        )
    if not changed:
        return (
            f"## Diff scope\n\nNo files changed under the source between `{synced}` and `{head}`. "
            "Re-stamp provenance only.\n\n"
        )
    affected, unmapped = _affected_docs(vault, repo, changed)
    out = [f"## Diff scope (`{synced}` → `{head}`)", "", f"Changed files ({len(changed)}):"]
    out += [f"- `{f}`" for f in changed[:40]]
    if len(changed) > 40:
        out.append(f"- … (+{len(changed) - 40} more)")
    out.append("")
    if affected is None:
        out += [
            "No `source_globs` declared on this repo's docs yet — regenerate the ",
            "sections per the `sync.md` path-keyword mapping, and add `source_globs` ",
            "to each doc so future syncs scope to modules.",
            "",
        ]
    else:
        out.append("**Regenerate only these docs** (matched via `source_globs`):")
        out += [f"- [ ] `{d}`" for d in affected] or ["- (none matched)"]
        if unmapped:
            out += [
                "",
                "Changed files not mapped to any doc (review; may need a new "
                "module doc or a `source_globs` fix):",
            ]
            out += [f"- `{f}`" for f in unmapped[:20]]
        out.append("")
    return "\n".join(out) + "\n"


def _write_task(path: Path, repo: dict, mode: str, vault: Path) -> None:
    prompt = "assets/prompts/bootstrap.md" if mode == "bootstrap" else "assets/prompts/sync.md"
    head = (
        git_path_head(Path(repo["source"]).expanduser())
        if repo.get("source_kind") == "path"
        else None
    )
    parts = [
        f"# Task — document {repo['name']} ({mode})\n",
        f"Source: `{repo['source']}` · stack: `{repo['stack']}` · kind: `{repo['kind']}`"
        + (
            f" · last_sync: `{repo.get('last_sync_commit')}` → head: `{head}`"
            if mode == "sync"
            else ""
        )
        + "\n",
        f"Follow the FIXED prompt `{prompt}` from the ralph-vault skill, writing into "
        f"`{vault.name}/repos/{repo['name']}/` and its repo-card.\n",
    ]
    if mode == "sync":
        parts.append(_sync_scope_block(repo, vault))
        parts.append(
            "## Subtasks\n\n"
            "- [ ] Regenerate each affected doc listed under **Diff scope** (full section, not in-place patch); "
            "keep `source_globs` and other frontmatter, bump `commit`/`last_sync`.\n"
            "- [ ] While regenerating, scan the changed files for any new public/enumerable item "
            "(route, command, env var, exported symbol, table, event…) not yet documented, and add it — "
            "the diff is the cheapest moment to catch omission.\n"
            f"- [ ] Refresh the repo-card `agent-context/repo-cards/{repo['name']}.md` if interfaces changed.\n"
            "- [ ] Run `gv.py validate --vault <vault>`; fix any reported error.\n"
            "- [ ] [juez] verify the refreshed docs against the source.\n"
            f"- [ ] Close: `gv.py mark-synced --vault <vault> --repo {repo['name']}` (advances last_sync_commit + logs to meta/changelog.md).\n"
        )
    else:
        parts.append(
            "## Subtasks\n\n"
            "- [ ] Detect stack (if `auto`) and seed the per-section task list from the matching `assets/stack-tasks/<stack>.md`.\n"
            f"- [ ] Generate the per-section docs under `repos/{repo['name']}/`, stamping `source_globs` (the source paths each section covers, relative to the source).\n"
            f"- [ ] Write the tier-1 repo-card `agent-context/repo-cards/{repo['name']}.md`.\n"
            "- [ ] Run `gv.py validate --vault <vault>`; fix any reported error.\n"
            "- [ ] [juez] verify the docs against the source (faithfulness, no copied code, frontmatter present).\n"
            f"- [ ] Close: `gv.py mark-synced --vault <vault> --repo {repo['name']}` (sets phase=done, records the baseline commit + logs it).\n"
        )
    path.write_text("\n".join(parts), encoding="utf-8")


def _write_reconcile_task(path: Path, repo: dict, vault: Path) -> None:
    """Standalone omission-audit task: re-read the surface, document what is missing.

    Cadence-driven (not change-driven): catches items that already existed but were
    never documented — the blind spot deterministic checks and commit-equality miss.
    """
    head = (
        git_path_head(Path(repo["source"]).expanduser())
        if repo.get("source_kind") == "path"
        else None
    )
    last = repo.get("last_reconcile_commit")
    body = (
        f"# Task — reconcile {repo['name']} (omission audit)\n\n"
        f"Source: `{repo['source']}` · stack: `{repo['stack']}` · kind: `{repo['kind']}` · "
        f"last_reconcile: `{last}` → head: `{head}`\n\n"
        "Follow the FIXED prompt `assets/prompts/reconcile.md` from the ralph-vault skill. "
        "This is a **completeness** pass, not a rewrite: confirm the existing docs account "
        f"for everything enumerable in the source under `repos/{repo['name']}/`, and only add "
        "what is missing.\n\n"
        "## Subtasks\n\n"
        "- [ ] Enumerate the public/enumerable surface of the source (routes, commands, env "
        "vars, exported symbols, tables, events, config flags — whatever the stack exposes).\n"
        f"- [ ] For each item, confirm it is accounted for in `repos/{repo['name']}/` (literally, "
        "or subsumed by a summary). List every gap.\n"
        "- [ ] Document each gap in the owning section (extend, do not rewrite); stamp/keep "
        "`source_globs` so the file-level coverage check sees the new coverage.\n"
        "- [ ] Run `gv.py validate --vault <vault>`; fix any reported error.\n"
        f"- [ ] [juez] verify no enumerable item of {repo['name']} is left undocumented.\n"
        f"- [ ] Close: `gv.py mark-reconciled --vault <vault> --repo {repo['name']}` "
        "(records the audit baseline + logs to meta/changelog.md).\n"
    )
    path.write_text(body, encoding="utf-8")


def _write_graph_task(path: Path, tier: str, cfg: dict) -> None:
    _, prompt, summary, subtasks = GRAPH_TIERS[tier]
    repos = ", ".join(r["name"] for r in cfg["repos"]) or "(none)"
    body = (
        f"# Task — {tier} (cross-repo graph)\n\n"
        f"{summary} Run **after** the repo tasks in this plan are done.\n\n"
        f"Follow the FIXED prompt `{prompt}` from the ralph-vault skill.\n\n"
        f"Registered repos: {repos}.\n\n"
        "## Subtasks\n\n"
        f"{subtasks}"
    )
    path.write_text(body, encoding="utf-8")


# --------------------------------------------------------------------------- #
# mark-synced  (advance last_sync_commit + append to meta/changelog.md)
# --------------------------------------------------------------------------- #
CHANGELOG_REL = "meta/changelog.md"


def _ensure_changelog(vault: Path) -> Path:
    p = vault / CHANGELOG_REL
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            f"---\ntype: meta\nload_tier: never\nschema_version: {SCHEMA_VERSION}\ntags: [meta]\n---\n\n"
            "# Changelog\n\n"
            "> Append-only sync log: which commits affected which docs, and when. "
            "Written by `gv.py mark-synced`. Distinct from `LAST-UPDATED.md` (a vault-wide timestamp).\n",
            encoding="utf-8",
        )
    return p


def _append_changelog(
    vault: Path,
    repo: dict,
    frm: str | None,
    to: str | None,
    changed: list[str] | None,
    affected: list[str] | None,
) -> None:
    p = _ensure_changelog(vault)
    lines = [f"\n## {now_iso()} · {repo['name']}", ""]
    if not frm:
        lines.append(f"- initial bootstrap · baseline `{to}`")
    else:
        lines.append(f"- commits: `{frm}` → `{to}`")
    if changed is None and frm:
        lines.append("- diff unavailable (baseline not reachable) — treated as full refresh")
    elif changed is not None:
        lines.append(
            f"- changed files ({len(changed)}): "
            + (
                ", ".join(f"`{f}`" for f in changed[:20]) + (" …" if len(changed) > 20 else "")
                if changed
                else "none"
            )
        )
    if affected:
        lines.append("- affected docs: " + ", ".join(f"`{d}`" for d in affected))
    elif affected == [] and changed:
        lines.append("- affected docs: none matched `source_globs`")
    with p.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def cmd_mark_synced(args) -> int:
    vault = Path(args.vault).resolve()
    cfg = load_config(vault)
    entry = find_repo(cfg, args.repo)
    if not entry:
        die(f"'{args.repo}' is not registered.")
    frm = entry.get("last_sync_commit")
    to = args.commit
    changed = None
    affected = None
    if entry.get("source_kind") == "path":
        src = Path(entry["source"]).expanduser()
        if not to:
            to = git_path_head(src)
        if frm and to:
            changed = git_changed_paths(src, frm)
            if changed is not None:
                affected, _ = _affected_docs(vault, entry, changed)
    if not to:
        die("could not resolve a commit to record (pass --commit for url sources).")
    entry["phase"] = "done"
    entry["last_sync_commit"] = to
    # The initial bootstrap documents the *whole* surface, so it doubles as the first
    # omission audit — seed the reconcile baseline. An incremental sync touches only the
    # changed sections, so it must NOT advance it (that is `mark-reconciled`'s job).
    if not frm:
        entry["last_reconcile_commit"] = to
    save_config(vault, cfg)
    _append_changelog(vault, entry, frm, to, changed, affected)
    touch_last_updated(vault)
    info(f"marked '{args.repo}' synced at {to} (was {frm or 'unset'}); logged to {CHANGELOG_REL}")
    return 0


def cmd_mark_reconciled(args) -> int:
    vault = Path(args.vault).resolve()
    cfg = load_config(vault)
    entry = find_repo(cfg, args.repo)
    if not entry:
        die(f"'{args.repo}' is not registered.")
    frm = entry.get("last_reconcile_commit")
    to = args.commit
    if entry.get("source_kind") == "path" and not to:
        to = git_path_head(Path(entry["source"]).expanduser())
    if not to:
        die("could not resolve a commit to record (pass --commit for url sources).")
    entry["last_reconcile_commit"] = to
    save_config(vault, cfg)
    p = _ensure_changelog(vault)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(
            f"\n## {now_iso()} · {entry['name']}\n\n"
            f"- reconciled (omission audit) · baseline `{to}`"
            + (f" (was `{frm}`)" if frm else "")
            + "\n"
        )
    touch_last_updated(vault)
    info(
        f"marked '{args.repo}' reconciled at {to} (was {frm or 'unset'}); logged to {CHANGELOG_REL}"
    )
    return 0


def cmd_changelog(args) -> int:
    vault = Path(args.vault).resolve()
    p = vault / CHANGELOG_REL
    if not p.exists():
        info(f"no changelog yet at {CHANGELOG_REL} (written by `gv.py mark-synced`).")
        return 0
    # split into entries: each starts at a '## <iso> · <name>' header
    entries: list[tuple[str, str, str]] = []  # (iso, name, block)
    cur_head, cur_lines = None, []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"^##\s+(\S+)\s+·\s+(.+?)\s*$", line)
        if m:
            if cur_head:
                entries.append((cur_head[0], cur_head[1], "\n".join(cur_lines).rstrip()))
            cur_head, cur_lines = (m.group(1), m.group(2)), [line]
        elif cur_head:
            cur_lines.append(line)
    if cur_head:
        entries.append((cur_head[0], cur_head[1], "\n".join(cur_lines).rstrip()))
    if args.repo:
        entries = [e for e in entries if e[1] == args.repo]
    if args.since:
        entries = [e for e in entries if e[0] >= args.since]
    if not entries:
        info("no changelog entries match the filter.")
        return 0
    shown = entries[-args.limit :] if args.limit and args.limit > 0 else entries
    for _, _, block in shown:
        info("\n" + block)
    info(f"\n({len(shown)} of {len(entries)} entr{'y' if len(entries) == 1 else 'ies'} shown)")
    return 0


# --------------------------------------------------------------------------- #
# argparse
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gv.py", description="ralph-vault lifecycle CLI")
    p.add_argument("--vault", default="vault", help="path to the vault dir (default: vault)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="create vault structure + config (idempotent)")
    s.add_argument("--project", help="project name (default: vault dir name)")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("add", help="register a repo/subdir")
    s.add_argument("--name", required=True)
    s.add_argument("--path", help="local source path")
    s.add_argument("--url", help="remote source url")
    s.add_argument("--stack", help="stack id (java/python/node/go/frontend/scala) or 'auto'")
    s.add_argument(
        "--subdir", action="store_true", help="treat source as a subdirectory, not a full repo"
    )
    s.set_defaults(func=cmd_add)

    s = sub.add_parser("delete", help="unregister a repo/subdir")
    s.add_argument("--name", required=True)
    s.add_argument("--purge", action="store_true", help="also delete its docs + repo-card")
    s.set_defaults(func=cmd_delete)

    s = sub.add_parser("list", help="show the registry")
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("check", help="report missing/incomplete/stale repos")
    s.add_argument("--gate", action="store_true", help="exit 1 if any repo needs attention")
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("validate", help="frontmatter/wikilink/budget gate over the vault")
    s.set_defaults(func=cmd_validate)

    s = sub.add_parser("plan", help="emit ralph-loop plan files")
    s.add_argument("--repo", help="plan a single repo")
    s.add_argument("--pending", action="store_true", help="only repos with phase != done")
    s.add_argument(
        "--stale",
        action="store_true",
        help="only done repos whose source path moved since last_sync_commit",
    )
    s.add_argument(
        "--needs-work",
        dest="needs_work",
        action="store_true",
        help="repos that are pending, missing docs/card, stale, or due an omission audit (recommended)",
    )
    s.add_argument(
        "--reconcile",
        action="store_true",
        help="only done repos due a full omission audit (per reconcile_after_commits)",
    )
    s.add_argument(
        "--no-graph",
        dest="no_graph",
        action="store_true",
        help="skip the appended relations + components graph tasks",
    )
    s.add_argument("--plan-dir", default="plan", help="output dir for plan.md (default: plan)")
    s.set_defaults(func=cmd_plan)

    s = sub.add_parser("mark-synced", help="advance last_sync_commit + log to meta/changelog.md")
    s.add_argument("--repo", required=True)
    s.add_argument(
        "--commit", help="commit to record (default: last commit touching the source path)"
    )
    s.set_defaults(func=cmd_mark_synced)

    s = sub.add_parser(
        "mark-reconciled", help="advance last_reconcile_commit (omission audit baseline)"
    )
    s.add_argument("--repo", required=True)
    s.add_argument(
        "--commit", help="commit to record (default: last commit touching the source path)"
    )
    s.set_defaults(func=cmd_mark_reconciled)

    s = sub.add_parser("changelog", help="print recent sync-log entries from meta/changelog.md")
    s.add_argument("--repo", help="only entries for this repo")
    s.add_argument(
        "--since", help="only entries at/after this ISO timestamp prefix (e.g. 2026-06-06)"
    )
    s.add_argument(
        "--limit", type=int, default=10, help="max entries to show (default: 10; <=0 = all)"
    )
    s.set_defaults(func=cmd_changelog)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
