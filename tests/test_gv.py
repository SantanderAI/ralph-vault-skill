# Copyright (c) 2026 Santander Group
# SPDX-License-Identifier: Apache-2.0
"""Unit and integration tests for the ralph-vault CLI (scripts/gv.py)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import gv

ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def cli(*argv: str) -> int:
    """Run the CLI like the real entry point and return its exit code."""
    return gv.main(list(argv))


def read_config(vault: Path) -> dict:
    return json.loads((vault / gv.CONFIG_REL).read_text(encoding="utf-8"))


def write_config(vault: Path, cfg: dict) -> None:
    gv.save_config(vault, cfg)


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "src"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Tester")
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


def commit(repo: Path, name: str, content: str) -> str:
    (repo / name).write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"add {name}")
    return _git(repo, "rev-parse", "--short", "HEAD")


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    v = tmp_path / "vault"
    assert cli("--vault", str(v), "init", "--project", "Proj") == 0
    return v


# --------------------------------------------------------------------------- #
# config + output helpers
# --------------------------------------------------------------------------- #
def test_config_path():
    assert gv.config_path(Path("/x")) == Path("/x") / gv.CONFIG_REL


def test_load_config_missing(tmp_path):
    with pytest.raises(SystemExit):
        gv.load_config(tmp_path / "nope")


def test_save_and_load_config(tmp_path):
    cfg = {"schema_version": 1, "repos": []}
    gv.save_config(tmp_path, cfg)
    assert gv.load_config(tmp_path) == cfg


def test_find_repo():
    cfg = {"repos": [{"name": "a"}, {"name": "b"}]}
    assert gv.find_repo(cfg, "b")["name"] == "b"
    assert gv.find_repo(cfg, "z") is None


def test_die(capsys):
    with pytest.raises(SystemExit) as e:
        gv.die("boom", code=3)
    assert e.value.code == 3
    assert "error: boom" in capsys.readouterr().err


def test_info(capsys):
    gv.info("hi")
    assert "hi" in capsys.readouterr().out


def test_skill_routes_external_provider_research_reference():
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    reference = ROOT / "references" / "external-provider-research.md"

    assert "references/external-provider-research.md" in skill
    assert reference.exists()

    text = reference.read_text(encoding="utf-8")
    assert "source URLs" in text
    assert "tool-agnostic" in text
    assert "Linkup" not in text


def test_now_iso():
    s = gv.now_iso()
    assert s.endswith("Z") and "T" in s


# --------------------------------------------------------------------------- #
# git helpers
# --------------------------------------------------------------------------- #
def test_git_helpers_no_git(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise FileNotFoundError

    monkeypatch.setattr(gv.subprocess, "run", boom)
    assert gv.git_root(tmp_path) is None
    assert gv.git_path_head(tmp_path) is None
    assert gv.git_changed_paths(tmp_path, "x") is None


def test_git_root_outside_repo(tmp_path):
    assert gv.git_root(tmp_path) is None


def test_git_path_head_and_changed(git_repo):
    head = gv.git_path_head(git_repo)
    assert head and len(head) >= 4
    base = _git(git_repo, "rev-parse", "--short", "HEAD")
    commit(git_repo, "b.py", "y = 2\n")
    changed = gv.git_changed_paths(git_repo, base)
    assert changed == ["b.py"]


def test_git_changed_paths_bad_ref(git_repo):
    assert gv.git_changed_paths(git_repo, "deadbeef") is None


def test_git_helpers_calledprocesserror(monkeypatch, tmp_path):
    monkeypatch.setattr(gv, "git_root", lambda p: tmp_path)

    def boom(*a, **k):
        raise subprocess.CalledProcessError(1, "git")

    monkeypatch.setattr(gv.subprocess, "run", boom)
    assert gv.git_path_head(tmp_path) is None
    assert gv.git_changed_paths(tmp_path, "x") is None


def test_git_changed_paths_subdir_prefix(git_repo):
    sub = git_repo / "pkg"
    sub.mkdir()
    base = _git(git_repo, "rev-parse", "--short", "HEAD")
    (sub / "m.py").write_text("z = 3\n", encoding="utf-8")
    _git(git_repo, "add", "-A")
    _git(git_repo, "commit", "-q", "-m", "sub")
    changed = gv.git_changed_paths(sub, base)
    assert changed == ["m.py"]


# --------------------------------------------------------------------------- #
# staleness
# --------------------------------------------------------------------------- #
def test_entry_staleness_url_source():
    assert gv.entry_staleness({"source_kind": "url", "last_sync_commit": "x"}) == (False, None, "x")


def test_entry_staleness_path(git_repo):
    repo = {"source_kind": "path", "source": str(git_repo), "last_sync_commit": "0000000"}
    is_stale, head, synced = gv.entry_staleness(repo)
    assert is_stale is True
    assert synced == "0000000"
    repo["last_sync_commit"] = head
    assert gv.entry_staleness(repo)[0] is False


# --------------------------------------------------------------------------- #
# init
# --------------------------------------------------------------------------- #
def test_init_creates_structure(vault):
    for tier in gv.TIERS:
        assert (vault / tier).is_dir()
        assert (vault / tier / "README.md").exists()
    assert (vault / gv.CONFIG_REL).exists()
    assert (vault / "README.md").exists()
    assert (vault / "LAST-UPDATED.md").exists()
    cfg = read_config(vault)
    assert cfg["project"] == "Proj"


def test_init_idempotent(vault, capsys):
    assert cli("--vault", str(vault), "init") == 0
    assert "already present" in capsys.readouterr().out


def test_init_default_project_name(tmp_path):
    v = tmp_path / "myvault"
    cli("--vault", str(v), "init")
    assert read_config(v)["project"] == "myvault"


# --------------------------------------------------------------------------- #
# add / delete / list
# --------------------------------------------------------------------------- #
def test_add_path_source(vault):
    assert (
        cli(
            "--vault", str(vault), "add", "--name", "svc", "--path", "/tmp/svc", "--stack", "python"
        )
        == 0
    )
    cfg = read_config(vault)
    assert cfg["repos"][0]["name"] == "svc"
    assert cfg["repos"][0]["source_kind"] == "path"
    assert cfg["repos"][0]["stack"] == "python"


def test_add_url_subdir_default_stack(vault):
    cli("--vault", str(vault), "add", "--name", "r", "--url", "https://x/y", "--subdir")
    entry = read_config(vault)["repos"][0]
    assert entry["source_kind"] == "url"
    assert entry["kind"] == "subdir"
    assert entry["stack"] == "auto"


def test_add_duplicate(vault):
    cli("--vault", str(vault), "add", "--name", "svc", "--path", "/tmp/svc")
    with pytest.raises(SystemExit):
        cli("--vault", str(vault), "add", "--name", "svc", "--path", "/tmp/other")


def test_add_requires_source(vault):
    with pytest.raises(SystemExit):
        cli("--vault", str(vault), "add", "--name", "svc")


def test_delete_not_found(vault):
    with pytest.raises(SystemExit):
        cli("--vault", str(vault), "delete", "--name", "ghost")


def test_delete_keeps_docs(vault, capsys):
    cli("--vault", str(vault), "add", "--name", "svc", "--path", "/tmp/svc")
    assert cli("--vault", str(vault), "delete", "--name", "svc") == 0
    assert read_config(vault)["repos"] == []
    assert "left in place" in capsys.readouterr().out


def test_delete_purge(vault):
    cli("--vault", str(vault), "add", "--name", "svc", "--path", "/tmp/svc")
    docs = vault / "repos" / "svc"
    (docs / "sub").mkdir(parents=True)
    (docs / "overview.md").write_text("x", encoding="utf-8")
    (docs / "sub" / "nested.md").write_text("y", encoding="utf-8")
    card = vault / "agent-context" / "repo-cards" / "svc.md"
    card.parent.mkdir(parents=True, exist_ok=True)
    card.write_text("c", encoding="utf-8")
    assert cli("--vault", str(vault), "delete", "--name", "svc", "--purge") == 0
    assert not docs.exists()
    assert not card.exists()


def test_rmtree_file(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("x", encoding="utf-8")
    gv._rmtree(f)
    assert not f.exists()


def test_list_empty(vault, capsys):
    assert cli("--vault", str(vault), "list") == 0
    assert "registry is empty" in capsys.readouterr().out


def test_list_populated(vault, capsys):
    cli("--vault", str(vault), "add", "--name", "svc", "--path", "/tmp/svc")
    assert cli("--vault", str(vault), "list") == 0
    assert "svc" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# check
# --------------------------------------------------------------------------- #
def _mark_done(vault: Path, name: str, head: str | None) -> None:
    cfg = read_config(vault)
    for r in cfg["repos"]:
        if r["name"] == name:
            r["phase"] = "done"
            r["last_sync_commit"] = head
    write_config(vault, cfg)


def test_check_problems_and_gate(vault):
    cli("--vault", str(vault), "add", "--name", "svc", "--path", "/tmp/svc")
    assert cli("--vault", str(vault), "check") == 0
    assert cli("--vault", str(vault), "check", "--gate") == 1


def test_check_ok_entry(vault, git_repo, capsys):
    cli("--vault", str(vault), "add", "--name", "svc", "--path", str(git_repo))
    docs = vault / "repos" / "svc"
    docs.mkdir(parents=True)
    (docs / "overview.md").write_text("x", encoding="utf-8")
    card = vault / "agent-context" / "repo-cards" / "svc.md"
    card.parent.mkdir(parents=True, exist_ok=True)
    card.write_text("c", encoding="utf-8")
    _mark_done(vault, "svc", gv.git_path_head(git_repo))
    assert cli("--vault", str(vault), "check") == 0
    assert "up to date" in capsys.readouterr().out


def test_check_stack_advisory(vault, capsys):
    cli("--vault", str(vault), "add", "--name", "svc", "--path", "/tmp/svc", "--stack", "cobol")
    cli("--vault", str(vault), "check")
    assert "no tailored section map" in capsys.readouterr().out


def test_check_stale_graph_advisory(vault, git_repo, capsys):
    cli("--vault", str(vault), "add", "--name", "svc", "--path", str(git_repo))
    docs = vault / "repos" / "svc"
    docs.mkdir(parents=True)
    (docs / "overview.md").write_text("x", encoding="utf-8")
    card = vault / "agent-context" / "repo-cards" / "svc.md"
    card.parent.mkdir(parents=True, exist_ok=True)
    card.write_text("c", encoding="utf-8")
    _mark_done(vault, "svc", "0000000")  # stale: synced != head
    edge = vault / "relations" / "http" / "edge.md"
    edge.parent.mkdir(parents=True, exist_ok=True)
    edge.write_text("refers to repos/svc/ here", encoding="utf-8")
    cli("--vault", str(vault), "check")
    assert "graph doc" in capsys.readouterr().out


def test_graph_refs_to_repo_skips_readme(vault):
    (vault / "relations" / "README.md").write_text("repos/svc/", encoding="utf-8")
    edge = vault / "components" / "lib.md"
    edge.write_text("uses repos/svc/", encoding="utf-8")
    refs = gv._graph_refs_to_repo(vault, "svc")
    assert refs == ["components/lib.md"]


# --------------------------------------------------------------------------- #
# validate helpers
# --------------------------------------------------------------------------- #
def test_parse_frontmatter():
    assert gv._parse_frontmatter("no fm") is None
    fm = gv._parse_frontmatter("---\ntype: x\nload_tier: 1\n- skip\n---\n\nbody")
    assert fm == {"type": "x", "load_tier": "1"}


def test_headings():
    assert gv._headings("# A\n## B\ntext") == {"A", "B"}


def test_has_source_citation():
    assert gv._has_source_citation("see `src/app.py` here") is True
    assert gv._has_source_citation("see `module.foo`") is True
    assert gv._has_source_citation("link `https://x/y`") is False
    assert gv._has_source_citation("just `word`") is False


def test_code_fences_variants():
    text = "```python\nx=1\n```\n~~~text\ntree\n~~~\n```\nbare\n```\n"
    fences = gv._code_fences(text)
    langs = [f[0] for f in fences]
    assert "python" in langs and "text" in langs and "" in langs


def test_glob_to_re():
    assert gv._glob_to_re("src/**/*.py").match("src/a/b.py")
    assert gv._glob_to_re("a?.py").match("ab.py")
    assert not gv._glob_to_re("src/*.py").match("src/a/b.py")


def test_read_source_globs_flow(tmp_path):
    p = tmp_path / "d.md"
    p.write_text(
        "---\ntype: repo-doc\nsource_globs: ['src/*.py', 'lib/**']\n---\n", encoding="utf-8"
    )
    assert gv._read_source_globs(p) == ["src/*.py", "lib/**"]


def test_read_source_globs_block(tmp_path):
    p = tmp_path / "d.md"
    p.write_text(
        "---\ntype: repo-doc\nsource_globs:\n  - src/a.py\n  - src/b.py\n---\n", encoding="utf-8"
    )
    assert gv._read_source_globs(p) == ["src/a.py", "src/b.py"]


def test_read_source_globs_none(tmp_path):
    p = tmp_path / "d.md"
    p.write_text("no frontmatter", encoding="utf-8")
    assert gv._read_source_globs(p) == []


def test_validate_clean(vault):
    assert cli("--vault", str(vault), "validate") == 0


def test_validate_errors(vault):
    bad = vault / "repos" / "no-fm.md"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("# no frontmatter here\n", encoding="utf-8")
    code = (
        "---\ntype: repo-doc\nload_tier: 2\nschema_version: 1\n---\n\n"
        "```python\nprint('x')\n```\n"
        "[[missing-target]]\n"
    )
    (vault / "repos" / "withcode.md").write_text(code, encoding="utf-8")
    assert cli("--vault", str(vault), "validate") == 1


def test_validate_relation_edge_missing_fields(vault):
    edge = vault / "relations" / "http" / "e.md"
    edge.parent.mkdir(parents=True, exist_ok=True)
    edge.write_text(
        "---\ntype: edge\nload_tier: 2\nschema_version: 1\n---\n\nbody\n", encoding="utf-8"
    )
    assert cli("--vault", str(vault), "validate") == 1


def test_validate_warnings(vault, capsys):
    doc = vault / "repos" / "doc.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    long_body = " ".join(["word"] * 2000)
    doc.write_text(
        "---\ntype: repo-doc\nload_tier: 2\nschema_version: 1\n---\n\n"
        "# Title\n\n[[#missing-anchor]]\n\n" + long_body,
        encoding="utf-8",
    )
    cli("--vault", str(vault), "validate")
    err = capsys.readouterr().err
    assert "tokens > budget" in err


def test_validate_mojibake_doubled_encoding(vault, capsys):
    doc = vault / "glossary" / "moji.md"
    doc.write_text(
        "---\ntype: x\nload_tier: 2\nschema_version: 1\n---\n\n"
        "# Title\n\nItâ€™s a quote with mojibake.\n",
        encoding="utf-8",
    )
    assert cli("--vault", str(vault), "validate") == 0  # warning never gates
    assert "mojibake" in capsys.readouterr().err


def test_validate_mojibake_replacement_char(vault, capsys):
    doc = vault / "glossary" / "repl.md"
    doc.write_text(
        "---\ntype: x\nload_tier: 2\nschema_version: 1\n---\n\n# Title\n\nbroken � byte.\n",
        encoding="utf-8",
    )
    assert cli("--vault", str(vault), "validate") == 0
    assert "mojibake" in capsys.readouterr().err


def test_validate_no_mojibake_clean(vault, capsys):
    doc = vault / "glossary" / "clean.md"
    doc.write_text(
        "---\ntype: x\nload_tier: 2\nschema_version: 1\n---\n\n# Title\n\nIt's clean UTF-8.\n",
        encoding="utf-8",
    )
    assert cli("--vault", str(vault), "validate") == 0
    assert "mojibake" not in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# _affected_docs
# --------------------------------------------------------------------------- #
def test_affected_docs_no_globs(vault):
    repo = {"name": "svc"}
    (vault / "repos" / "svc").mkdir(parents=True)
    (vault / "repos" / "svc" / "overview.md").write_text(
        "---\ntype: repo-doc\n---\n", encoding="utf-8"
    )
    affected, unmapped = gv._affected_docs(vault, repo, ["src/a.py"])
    assert affected is None
    assert unmapped == ["src/a.py"]


def test_affected_docs_with_globs(vault):
    repo = {"name": "svc"}
    d = vault / "repos" / "svc"
    d.mkdir(parents=True)
    (d / "api.md").write_text(
        "---\ntype: repo-doc\nsource_globs: ['src/api/**']\n---\n", encoding="utf-8"
    )
    affected, unmapped = gv._affected_docs(vault, repo, ["src/api/x.py", "src/other.py"])
    assert affected == ["repos/svc/api.md"]
    assert unmapped == ["src/other.py"]


# --------------------------------------------------------------------------- #
# plan
# --------------------------------------------------------------------------- #
def test_select_targets(vault):
    cli("--vault", str(vault), "add", "--name", "a", "--path", "/tmp/a")
    cli("--vault", str(vault), "add", "--name", "b", "--path", "/tmp/b")
    cfg = read_config(vault)

    class NS:
        repo = None
        pending = False
        needs_work = False
        stale = False

    assert len(gv._select_targets(NS(), cfg, vault)) == 2
    NS.repo = "a"
    assert [r["name"] for r in gv._select_targets(NS(), cfg, vault)] == ["a"]
    NS.repo = None
    NS.pending = True
    assert len(gv._select_targets(NS(), cfg, vault)) == 2


def test_plan_repo_not_found(vault):
    with pytest.raises(SystemExit):
        cli("--vault", str(vault), "plan", "--repo", "ghost")


def test_plan_nothing(vault, capsys):
    # pending selector with no pending repos
    assert cli("--vault", str(vault), "plan", "--pending") == 0
    assert "nothing to plan" in capsys.readouterr().out


def test_plan_single_repo_no_graph(vault, tmp_path):
    cli("--vault", str(vault), "add", "--name", "svc", "--path", "/tmp/svc")
    plan_dir = tmp_path / "plan"
    assert (
        cli(
            "--vault",
            str(vault),
            "plan",
            "--repo",
            "svc",
            "--no-graph",
            "--plan-dir",
            str(plan_dir),
        )
        == 0
    )
    text = (plan_dir / "plan.md").read_text(encoding="utf-8")
    assert "svc (bootstrap)" in text
    assert "graph" not in text


def test_plan_with_graph_threshold(vault, tmp_path):
    cli("--vault", str(vault), "add", "--name", "a", "--path", "/tmp/a")
    cli("--vault", str(vault), "add", "--name", "b", "--path", "/tmp/b")
    plan_dir = tmp_path / "plan"
    cli("--vault", str(vault), "plan", "--plan-dir", str(plan_dir))
    text = (plan_dir / "plan.md").read_text(encoding="utf-8")
    assert "relations (graph)" in text
    assert "components (graph)" in text
    assert "dependencies (graph)" in text


def test_plan_single_repo_dependencies_only(vault, tmp_path):
    cli("--vault", str(vault), "add", "--name", "a", "--path", "/tmp/a")
    plan_dir = tmp_path / "plan"
    cli("--vault", str(vault), "plan", "--plan-dir", str(plan_dir))
    text = (plan_dir / "plan.md").read_text(encoding="utf-8")
    assert "dependencies (graph)" in text
    assert "relations (graph)" not in text


# --------------------------------------------------------------------------- #
# _sync_scope_block / _write_task
# --------------------------------------------------------------------------- #
def test_sync_scope_url(vault):
    block = gv._sync_scope_block({"source_kind": "url", "source": "https://x"}, vault)
    assert "no local diff" in block


def test_sync_scope_no_baseline(vault, git_repo):
    repo = {"source_kind": "path", "source": str(git_repo), "last_sync_commit": None}
    assert "full refresh" in gv._sync_scope_block(repo, vault)


def test_sync_scope_unreachable(vault, git_repo):
    repo = {"source_kind": "path", "source": str(git_repo), "last_sync_commit": "deadbeef"}
    assert "not reachable" in gv._sync_scope_block(repo, vault)


def test_sync_scope_no_changes(vault, git_repo):
    head = gv.git_path_head(git_repo)
    repo = {"source_kind": "path", "source": str(git_repo), "last_sync_commit": head}
    assert "No files changed" in gv._sync_scope_block(repo, vault)


def test_sync_scope_with_changes(vault, git_repo):
    base = _git(git_repo, "rev-parse", "--short", "HEAD")
    commit(git_repo, "new.py", "n = 1\n")
    repo = {"name": "svc", "source_kind": "path", "source": str(git_repo), "last_sync_commit": base}
    (vault / "repos" / "svc").mkdir(parents=True)
    block = gv._sync_scope_block(repo, vault)
    assert "Changed files" in block
    assert "new.py" in block


def test_write_task_sync_and_bootstrap(vault, git_repo, tmp_path):
    repo = {
        "name": "svc",
        "source_kind": "path",
        "source": str(git_repo),
        "stack": "python",
        "kind": "repo",
        "last_sync_commit": None,
        "phase": "pending",
    }
    boot = tmp_path / "boot.md"
    gv._write_task(boot, repo, "bootstrap", vault)
    assert "bootstrap.md" in boot.read_text(encoding="utf-8")
    syncf = tmp_path / "sync.md"
    gv._write_task(syncf, repo, "sync", vault)
    assert "Diff scope" in syncf.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# mark-synced + changelog
# --------------------------------------------------------------------------- #
def test_mark_synced_initial(vault, git_repo):
    cli("--vault", str(vault), "add", "--name", "svc", "--path", str(git_repo))
    assert cli("--vault", str(vault), "mark-synced", "--repo", "svc") == 0
    cfg = read_config(vault)
    entry = gv.find_repo(cfg, "svc")
    assert entry["phase"] == "done"
    assert entry["last_sync_commit"]
    assert (vault / gv.CHANGELOG_REL).exists()


def test_mark_synced_with_changes(vault, git_repo):
    cli("--vault", str(vault), "add", "--name", "svc", "--path", str(git_repo))
    cli("--vault", str(vault), "mark-synced", "--repo", "svc")
    commit(git_repo, "n.py", "n = 1\n")
    assert cli("--vault", str(vault), "mark-synced", "--repo", "svc") == 0
    log = (vault / gv.CHANGELOG_REL).read_text(encoding="utf-8")
    assert "changed files" in log


def test_mark_synced_not_found(vault):
    with pytest.raises(SystemExit):
        cli("--vault", str(vault), "mark-synced", "--repo", "ghost")


def test_mark_synced_url_requires_commit(vault):
    cli("--vault", str(vault), "add", "--name", "r", "--url", "https://x/y")
    with pytest.raises(SystemExit):
        cli("--vault", str(vault), "mark-synced", "--repo", "r")
    assert cli("--vault", str(vault), "mark-synced", "--repo", "r", "--commit", "v1.0") == 0


def test_changelog_empty(vault, capsys):
    assert cli("--vault", str(vault), "changelog") == 0
    assert "no changelog yet" in capsys.readouterr().out


def test_changelog_filters(vault, git_repo, capsys):
    cli("--vault", str(vault), "add", "--name", "svc", "--path", str(git_repo))
    cli("--vault", str(vault), "mark-synced", "--repo", "svc")
    assert cli("--vault", str(vault), "changelog", "--repo", "svc") == 0
    out = capsys.readouterr().out
    assert "svc" in out
    # filter that matches nothing
    assert cli("--vault", str(vault), "changelog", "--repo", "other") == 0
    assert "no changelog entries match" in capsys.readouterr().out
    # since filter in the future → nothing
    assert cli("--vault", str(vault), "changelog", "--since", "2999-01-01") == 0
    # limit all
    assert cli("--vault", str(vault), "changelog", "--limit", "0") == 0


# --------------------------------------------------------------------------- #
# extra branch coverage
# --------------------------------------------------------------------------- #
def test_graph_refs_missing_tier_and_no_needle(tmp_path):
    (tmp_path / "relations").mkdir()
    (tmp_path / "relations" / "hit.md").write_text("uses repos/svc/", encoding="utf-8")
    (tmp_path / "relations" / "miss.md").write_text("nothing here", encoding="utf-8")
    # components / infrastructure / technologies dirs are absent on purpose
    assert gv._graph_refs_to_repo(tmp_path, "svc") == ["relations/hit.md"]


def test_vault_md_files_skips_plan(vault):
    (vault / "plan").mkdir(exist_ok=True)
    (vault / "plan" / "p.md").write_text("---\ntype: x\n---\n", encoding="utf-8")
    found = {p.relative_to(vault).parts[0] for p in gv._vault_md_files(vault)}
    assert "plan" not in found and ".ralphvault" not in found


def test_validate_missing_required_field(vault):
    d = vault / "glossary" / "bad.md"
    d.write_text("---\ntype: x\nload_tier: 2\n---\n\nbody\n", encoding="utf-8")  # no schema_version
    assert cli("--vault", str(vault), "validate") == 1


def test_validate_long_fence(vault):
    body = (
        "---\ntype: x\nload_tier: 2\nschema_version: 1\n---\n\n```json\n"
        + "\n".join(["{}"] * 21)
        + "\n```\n"
    )
    (vault / "glossary" / "long.md").write_text(body, encoding="utf-8")
    assert cli("--vault", str(vault), "validate") == 1


def test_validate_wikilink_anchors(vault, capsys):
    (vault / "glossary" / "target.md").write_text(
        "---\ntype: x\nload_tier: 2\nschema_version: 1\n---\n\n# Known\n", encoding="utf-8"
    )
    (vault / "glossary" / "doc.md").write_text(
        "---\ntype: x\nload_tier: 2\nschema_version: 1\n---\n\n# Local\n\n"
        "[[#Local]] [[glossary/target#Known]] [[glossary/target#Missing]] [[#Nope]]\n",
        encoding="utf-8",
    )
    cli("--vault", str(vault), "validate")
    err = capsys.readouterr().err
    assert "anchor '#Missing'" in err
    assert "intra-doc anchor '#Nope'" in err


def test_read_source_globs_block_then_break(tmp_path):
    p = tmp_path / "d.md"
    p.write_text("---\ntype: x\nsource_globs:\n  - a.py\n\nother: 1\n---\n", encoding="utf-8")
    assert gv._read_source_globs(p) == ["a.py"]


def test_affected_docs_mixed(vault):
    repo = {"name": "svc"}
    d = vault / "repos" / "svc"
    d.mkdir(parents=True)
    (d / "no_globs.md").write_text("---\ntype: repo-doc\n---\n", encoding="utf-8")
    (d / "api.md").write_text(
        "---\ntype: repo-doc\nsource_globs: ['src/api/**']\n---\n", encoding="utf-8"
    )
    affected, unmapped = gv._affected_docs(vault, repo, ["src/api/x.py", "src/z.py"])
    assert affected == ["repos/svc/api.md"]
    assert unmapped == ["src/z.py"]


def test_select_targets_needs_work_and_stale(vault, git_repo):
    cli("--vault", str(vault), "add", "--name", "a", "--path", str(git_repo))
    cfg = read_config(vault)
    # mark stale: done but synced != head
    cfg["repos"][0]["phase"] = "done"
    cfg["repos"][0]["last_sync_commit"] = "0000000"
    write_config(vault, cfg)
    cfg = read_config(vault)

    class NS:
        repo = None
        pending = False
        needs_work = True
        stale = False

    assert [r["name"] for r in gv._select_targets(NS(), cfg, vault)] == ["a"]
    NS.needs_work = False
    NS.stale = True
    assert [r["name"] for r in gv._select_targets(NS(), cfg, vault)] == ["a"]


def test_sync_scope_many_and_affected(vault, git_repo):
    base = _git(git_repo, "rev-parse", "--short", "HEAD")
    for i in range(41):
        (git_repo / f"f{i}.py").write_text(f"v = {i}\n", encoding="utf-8")
    _git(git_repo, "add", "-A")
    _git(git_repo, "commit", "-q", "-m", "many")
    d = vault / "repos" / "svc"
    d.mkdir(parents=True)
    (d / "api.md").write_text(
        "---\ntype: repo-doc\nsource_globs: ['f0.py']\n---\n", encoding="utf-8"
    )
    repo = {"name": "svc", "source_kind": "path", "source": str(git_repo), "last_sync_commit": base}
    block = gv._sync_scope_block(repo, vault)
    assert "more)" in block  # > 40 changed files truncated
    assert "Regenerate only these docs" in block
    assert "not mapped to any doc" in block


def test_mark_synced_unreachable_baseline(vault, git_repo, capsys):
    cli("--vault", str(vault), "add", "--name", "svc", "--path", str(git_repo))
    cfg = read_config(vault)
    cfg["repos"][0]["last_sync_commit"] = "deadbeef"
    write_config(vault, cfg)
    assert cli("--vault", str(vault), "mark-synced", "--repo", "svc") == 0
    assert "diff unavailable" in (vault / gv.CHANGELOG_REL).read_text(encoding="utf-8")


def test_mark_synced_affected_and_none(vault, git_repo):
    cli("--vault", str(vault), "add", "--name", "svc", "--path", str(git_repo))
    cli("--vault", str(vault), "mark-synced", "--repo", "svc")
    d = vault / "repos" / "svc"
    d.mkdir(parents=True, exist_ok=True)
    (d / "api.md").write_text(
        "---\ntype: repo-doc\nsource_globs: ['x.py']\n---\n", encoding="utf-8"
    )
    commit(git_repo, "x.py", "x = 1\n")
    assert cli("--vault", str(vault), "mark-synced", "--repo", "svc") == 0
    log = (vault / gv.CHANGELOG_REL).read_text(encoding="utf-8")
    assert "affected docs:" in log
    # next change does not match the glob → affected == []
    commit(git_repo, "y.py", "y = 1\n")
    assert cli("--vault", str(vault), "mark-synced", "--repo", "svc") == 0
    log = (vault / gv.CHANGELOG_REL).read_text(encoding="utf-8")
    assert "none matched" in log


def test_changelog_multiple_entries(vault, git_repo, capsys):
    cli("--vault", str(vault), "add", "--name", "svc", "--path", str(git_repo))
    cli("--vault", str(vault), "mark-synced", "--repo", "svc")
    commit(git_repo, "n.py", "n = 1\n")
    cli("--vault", str(vault), "mark-synced", "--repo", "svc")
    assert cli("--vault", str(vault), "changelog", "--limit", "1") == 0
    assert "1 of 2" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# surface coverage — git_tracked_files / _uncovered_files / _change_drift / check
# --------------------------------------------------------------------------- #
def test_git_tracked_files(git_repo):
    files = gv.git_tracked_files(git_repo)
    assert files == ["a.py"]
    commit(git_repo, "b.py", "y = 2\n")
    assert sorted(gv.git_tracked_files(git_repo)) == ["a.py", "b.py"]


def test_git_tracked_files_subdir_prefix(git_repo):
    sub = git_repo / "pkg"
    sub.mkdir()
    (sub / "m.py").write_text("z = 3\n", encoding="utf-8")
    _git(git_repo, "add", "-A")
    _git(git_repo, "commit", "-q", "-m", "sub")
    assert gv.git_tracked_files(sub) == ["m.py"]


def test_git_tracked_files_no_git(monkeypatch, tmp_path):
    monkeypatch.setattr(gv, "git_root", lambda p: None)
    assert gv.git_tracked_files(tmp_path) is None


def test_uncovered_files_none_when_no_globs(vault, git_repo):
    cli("--vault", str(vault), "add", "--name", "svc", "--path", str(git_repo))
    repo = read_config(vault)["repos"][0]
    # no docs declare source_globs yet → coverage is undefined → None
    assert gv._uncovered_files(vault, repo) is None


def test_uncovered_files_flags_omission(vault, git_repo):
    # b.py is tracked but no doc covers it; a.py is covered → only b.py is uncovered
    commit(git_repo, "b.py", "y = 2\n")
    cli("--vault", str(vault), "add", "--name", "svc", "--path", str(git_repo))
    docs = vault / "repos" / "svc"
    docs.mkdir(parents=True)
    (docs / "overview.md").write_text(
        "---\ntype: repo-doc\nsource_globs: ['a.py']\n---\n", encoding="utf-8"
    )
    repo = read_config(vault)["repos"][0]
    assert gv._uncovered_files(vault, repo) == ["b.py"]


def test_uncovered_files_url_source(vault):
    cli("--vault", str(vault), "add", "--name", "svc", "--url", "https://x/y")
    repo = read_config(vault)["repos"][0]
    assert gv._uncovered_files(vault, repo) is None


def test_change_drift_none_when_fresh(vault, git_repo):
    cli("--vault", str(vault), "add", "--name", "svc", "--path", str(git_repo))
    _mark_done(vault, "svc", gv.git_path_head(git_repo))
    repo = read_config(vault)["repos"][0]
    assert gv._change_drift(vault, repo) is None


def test_change_drift_maps_changed_to_sections(vault, git_repo):
    base = gv.git_path_head(git_repo)
    cli("--vault", str(vault), "add", "--name", "svc", "--path", str(git_repo))
    docs = vault / "repos" / "svc"
    docs.mkdir(parents=True)
    (docs / "api.md").write_text(
        "---\ntype: repo-doc\nsource_globs: ['a.py']\n---\n", encoding="utf-8"
    )
    _mark_done(vault, "svc", base)
    commit(git_repo, "a.py", "x = 99\n")  # touch the covered file
    repo = read_config(vault)["repos"][0]
    affected, unmapped = gv._change_drift(vault, repo)
    assert affected == ["repos/svc/api.md"]
    assert unmapped == []


def test_check_omission_advisory(vault, git_repo, capsys):
    commit(git_repo, "secret_handler.py", "y = 2\n")
    cli("--vault", str(vault), "add", "--name", "svc", "--path", str(git_repo))
    docs = vault / "repos" / "svc"
    docs.mkdir(parents=True)
    (docs / "overview.md").write_text(
        "---\ntype: repo-doc\nsource_globs: ['a.py']\n---\n", encoding="utf-8"
    )
    card = vault / "agent-context" / "repo-cards" / "svc.md"
    card.parent.mkdir(parents=True, exist_ok=True)
    card.write_text("c", encoding="utf-8")
    _mark_done(vault, "svc", gv.git_path_head(git_repo))
    assert cli("--vault", str(vault), "check") == 0
    out = capsys.readouterr().out
    assert "up to date" in out
    assert "possible omission" in out
    assert "secret_handler.py" in out


def test_check_change_drift_advisory(vault, git_repo, capsys):
    base = gv.git_path_head(git_repo)
    cli("--vault", str(vault), "add", "--name", "svc", "--path", str(git_repo))
    docs = vault / "repos" / "svc"
    docs.mkdir(parents=True)
    (docs / "api.md").write_text(
        "---\ntype: repo-doc\nsource_globs: ['a.py']\n---\n", encoding="utf-8"
    )
    card = vault / "agent-context" / "repo-cards" / "svc.md"
    card.parent.mkdir(parents=True, exist_ok=True)
    card.write_text("c", encoding="utf-8")
    _mark_done(vault, "svc", base)
    commit(git_repo, "a.py", "x = 42\n")
    cli("--vault", str(vault), "check")
    out = capsys.readouterr().out
    assert "change-drift → regenerate" in out
    assert "repos/svc/api.md" in out


# --------------------------------------------------------------------------- #
# reconcile cadence — git_commit_distance / reconcile_due / mark-reconciled / plan
# --------------------------------------------------------------------------- #
def test_git_commit_distance(git_repo):
    base = gv.git_path_head(git_repo)
    commit(git_repo, "b.py", "y = 2\n")
    commit(git_repo, "c.py", "z = 3\n")
    assert gv.git_commit_distance(git_repo, base) == 2


def test_git_commit_distance_bad_ref(git_repo):
    assert gv.git_commit_distance(git_repo, "deadbeef") is None


def test_git_commit_distance_no_git(monkeypatch, tmp_path):
    monkeypatch.setattr(gv, "git_root", lambda p: None)
    assert gv.git_commit_distance(tmp_path, "x") is None


def test_git_commit_distance_nonint(monkeypatch, tmp_path):
    monkeypatch.setattr(gv, "git_root", lambda p: tmp_path)

    class R:
        stdout = "notanumber"

    monkeypatch.setattr(gv.subprocess, "run", lambda *a, **k: R())
    assert gv.git_commit_distance(tmp_path, "x") is None


def _done_repo(git_repo: Path, last_reconcile):
    return {
        "source_kind": "path",
        "phase": "done",
        "source": str(git_repo),
        "last_reconcile_commit": last_reconcile,
    }


def test_reconcile_due_not_done():
    assert gv.reconcile_due({"source_kind": "path", "phase": "pending"}, 25) == (False, None)


def test_reconcile_due_url():
    assert gv.reconcile_due({"source_kind": "url", "phase": "done"}, 25) == (False, None)


def test_reconcile_due_never(git_repo):
    assert gv.reconcile_due(_done_repo(git_repo, None), 25) == (True, None)


def test_reconcile_due_fresh(git_repo):
    base = gv.git_path_head(git_repo)
    assert gv.reconcile_due(_done_repo(git_repo, base), 25) == (False, 0)


def test_reconcile_due_over_threshold(git_repo):
    base = gv.git_path_head(git_repo)
    commit(git_repo, "b.py", "y = 2\n")
    commit(git_repo, "c.py", "z = 3\n")
    assert gv.reconcile_due(_done_repo(git_repo, base), 1) == (True, 2)


def test_reconcile_due_unreachable(git_repo):
    assert gv.reconcile_due(_done_repo(git_repo, "deadbeef"), 25) == (True, None)


def test_reconcile_threshold_default_and_custom():
    assert gv._reconcile_threshold({"settings": {}}) == gv.RECONCILE_AFTER_COMMITS
    assert gv._reconcile_threshold({"settings": {"reconcile_after_commits": 3}}) == 3


def test_add_initializes_reconcile_baseline(vault):
    cli("--vault", str(vault), "add", "--name", "svc", "--path", "/tmp/svc")
    assert read_config(vault)["repos"][0]["last_reconcile_commit"] is None


def test_mark_synced_bootstrap_seeds_reconcile(vault, git_repo):
    cli("--vault", str(vault), "add", "--name", "svc", "--path", str(git_repo))
    cli("--vault", str(vault), "mark-synced", "--repo", "svc")  # initial bootstrap
    entry = read_config(vault)["repos"][0]
    assert entry["last_reconcile_commit"] == entry["last_sync_commit"]


def test_mark_synced_sync_keeps_reconcile(vault, git_repo):
    cli("--vault", str(vault), "add", "--name", "svc", "--path", str(git_repo))
    cli("--vault", str(vault), "mark-synced", "--repo", "svc")  # bootstrap
    seeded = read_config(vault)["repos"][0]["last_reconcile_commit"]
    commit(git_repo, "b.py", "y = 2\n")
    cli("--vault", str(vault), "mark-synced", "--repo", "svc")  # incremental sync
    entry = read_config(vault)["repos"][0]
    assert entry["last_reconcile_commit"] == seeded  # NOT advanced by sync
    assert entry["last_sync_commit"] != seeded  # but sync did advance


def test_mark_reconciled(vault, git_repo, capsys):
    cli("--vault", str(vault), "add", "--name", "svc", "--path", str(git_repo))
    cli("--vault", str(vault), "mark-synced", "--repo", "svc")
    commit(git_repo, "b.py", "y = 2\n")
    head = gv.git_path_head(git_repo)
    assert cli("--vault", str(vault), "mark-reconciled", "--repo", "svc") == 0
    assert read_config(vault)["repos"][0]["last_reconcile_commit"] == head
    out = capsys.readouterr().out
    assert "reconciled" in out
    cl = (vault / gv.CHANGELOG_REL).read_text(encoding="utf-8")
    assert "omission audit" in cl
    # second pass logs the previous baseline (the "(was ...)" branch)
    commit(git_repo, "c.py", "z = 3\n")
    cli("--vault", str(vault), "mark-reconciled", "--repo", "svc")
    assert "(was" in (vault / gv.CHANGELOG_REL).read_text(encoding="utf-8")


def test_mark_reconciled_not_found(vault):
    with pytest.raises(SystemExit):
        cli("--vault", str(vault), "mark-reconciled", "--repo", "nope")


def test_mark_reconciled_url_requires_commit(vault):
    cli("--vault", str(vault), "add", "--name", "r", "--url", "https://x/y")
    with pytest.raises(SystemExit):
        cli("--vault", str(vault), "mark-reconciled", "--repo", "r")


def test_mark_reconciled_url_with_commit(vault):
    cli("--vault", str(vault), "add", "--name", "r", "--url", "https://x/y")
    assert cli("--vault", str(vault), "mark-reconciled", "--repo", "r", "--commit", "abc1234") == 0
    assert read_config(vault)["repos"][0]["last_reconcile_commit"] == "abc1234"


def _make_fresh_but_audit_due(vault: Path, git_repo: Path) -> str:
    """Add svc, advance sync to HEAD (fresh) but leave reconcile at the old base."""
    base = gv.git_path_head(git_repo)
    cli("--vault", str(vault), "add", "--name", "svc", "--path", str(git_repo))
    commit(git_repo, "b.py", "y = 2\n")
    head = gv.git_path_head(git_repo)
    cfg = read_config(vault)
    cfg["settings"]["reconcile_after_commits"] = 0
    for r in cfg["repos"]:
        r["phase"] = "done"
        r["last_sync_commit"] = head  # fresh (not stale)
        r["last_reconcile_commit"] = base  # but audit baseline is old
    write_config(vault, cfg)
    return head


def test_task_mode_bootstrap(vault):
    cli("--vault", str(vault), "add", "--name", "svc", "--path", "/tmp/svc")
    cfg = read_config(vault)
    assert gv._task_mode(vault, cfg["repos"][0], cfg) == "bootstrap"


def test_task_mode_sync_when_stale(vault, git_repo):
    cli("--vault", str(vault), "add", "--name", "svc", "--path", str(git_repo))
    _mark_done(vault, "svc", "0000000")
    cfg = read_config(vault)
    assert gv._task_mode(vault, cfg["repos"][0], cfg) == "sync"


def test_task_mode_reconcile(vault, git_repo):
    _make_fresh_but_audit_due(vault, git_repo)
    cfg = read_config(vault)
    assert gv.entry_staleness(cfg["repos"][0])[0] is False
    assert gv._task_mode(vault, cfg["repos"][0], cfg) == "reconcile"


def test_task_mode_sync_fallback(vault, git_repo):
    head = gv.git_path_head(git_repo)
    cli("--vault", str(vault), "add", "--name", "svc", "--path", str(git_repo))
    cfg = read_config(vault)
    for r in cfg["repos"]:
        r["phase"] = "done"
        r["last_sync_commit"] = head
        r["last_reconcile_commit"] = head
    write_config(vault, cfg)
    cfg = read_config(vault)
    assert gv._task_mode(vault, cfg["repos"][0], cfg) == "sync"


def test_select_targets_reconcile(vault, git_repo):
    _make_fresh_but_audit_due(vault, git_repo)

    class NS:
        repo = None
        needs_work = False
        reconcile = True
        stale = False
        pending = False

    sel = gv._select_targets(NS(), read_config(vault), vault)
    assert [r["name"] for r in sel] == ["svc"]


def test_select_targets_needs_work_includes_reconcile(vault, git_repo):
    _make_fresh_but_audit_due(vault, git_repo)
    # make entry_needs_work empty so only the reconcile-due branch can select it
    docs = vault / "repos" / "svc"
    docs.mkdir(parents=True)
    (docs / "o.md").write_text("x", encoding="utf-8")
    card = vault / "agent-context" / "repo-cards" / "svc.md"
    card.parent.mkdir(parents=True, exist_ok=True)
    card.write_text("c", encoding="utf-8")

    class NS:
        repo = None
        needs_work = True
        reconcile = False
        stale = False
        pending = False

    repo = read_config(vault)["repos"][0]
    assert gv.entry_needs_work(vault, repo) == []
    sel = gv._select_targets(NS(), read_config(vault), vault)
    assert [r["name"] for r in sel] == ["svc"]


def test_plan_reconcile_task(vault, git_repo, tmp_path):
    _make_fresh_but_audit_due(vault, git_repo)
    plan_dir = tmp_path / "plan"
    assert (
        cli("--vault", str(vault), "plan", "--reconcile", "--plan-dir", str(plan_dir), "--no-graph")
        == 0
    )
    plan = (plan_dir / "plan.md").read_text(encoding="utf-8")
    assert "svc (reconcile)" in plan
    task = (plan_dir / "task" / "01.md").read_text(encoding="utf-8")
    assert "omission audit" in task
    assert "reconcile.md" in task
    assert "mark-reconciled" in task


def test_check_reconcile_due_advisory(vault, git_repo, capsys):
    _make_fresh_but_audit_due(vault, git_repo)
    docs = vault / "repos" / "svc"
    docs.mkdir(parents=True)
    (docs / "o.md").write_text("x", encoding="utf-8")
    card = vault / "agent-context" / "repo-cards" / "svc.md"
    card.parent.mkdir(parents=True, exist_ok=True)
    card.write_text("c", encoding="utf-8")
    cli("--vault", str(vault), "check")
    out = capsys.readouterr().out
    assert "reconcile due" in out
    assert "commits since last audit" in out


def test_check_reconcile_never_audited_advisory(vault, git_repo, capsys):
    cli("--vault", str(vault), "add", "--name", "svc", "--path", str(git_repo))
    docs = vault / "repos" / "svc"
    docs.mkdir(parents=True)
    (docs / "o.md").write_text("x", encoding="utf-8")
    card = vault / "agent-context" / "repo-cards" / "svc.md"
    card.parent.mkdir(parents=True, exist_ok=True)
    card.write_text("c", encoding="utf-8")
    _mark_done(vault, "svc", gv.git_path_head(git_repo))  # done, but last_reconcile stays None
    cli("--vault", str(vault), "check")
    assert "never audited" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# entrypoint
# --------------------------------------------------------------------------- #
def test_main_requires_subcommand():
    with pytest.raises(SystemExit):
        gv.main([])


def test_build_parser():
    parser = gv.build_parser()
    args = parser.parse_args(["--vault", "v", "list"])
    assert args.func is gv.cmd_list
