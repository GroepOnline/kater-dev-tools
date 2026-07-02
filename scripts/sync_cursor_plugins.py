#!/usr/bin/env python3
"""Sync Cursor / Claude-compatible plugin marketplaces for the agent CLI.

Reads committed SSOT from `.agents/cursor/settings.json`, clones marketplace git
sources, installs enabled plugins under `~/.agents/cursor/plugins/local/`, registers
them for Cursor IDE discovery, and exposes install paths for `agent --plugin-dir`.

Usage:
  python3 scripts/sync_cursor_plugins.py              # install / update
  python3 scripts/sync_cursor_plugins.py --check      # validate SSOT only
  python3 scripts/sync_cursor_plugins.py --dry-run    # show planned actions
  python3 scripts/sync_cursor_plugins.py --print-plugin-dirs
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = ROOT / ".agents" / "cursor" / "settings.json"
CLAUDE_SETTINGS_LINK = ROOT / ".claude" / "settings.json"

MARKETPLACE_MANIFESTS = (
    ".claude-plugin/marketplace.json",
    ".cursor-plugin/marketplace.json",
    ".grok-plugin/marketplace.json",
    ".agents/plugins/marketplace.json",  # openai/plugins
)

PLUGIN_COMPONENTS = (
    ".claude-plugin",
    ".cursor-plugin",
    ".grok-plugin",
    "skills",
    "commands",
    "rules",
    "assets",
    "hooks",
    "mcp.json",
    ".mcp.json",
)

GITHUB_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class PluginRef:
    name: str
    marketplace: str

    @property
    def plugin_id(self) -> str:
        return f"{self.name}@{self.marketplace}"


def log(msg: str) -> None:
    print(f"[sync-cursor-plugins] {msg}", flush=True)


def load_settings() -> dict[str, Any]:
    if not SETTINGS_PATH.exists():
        raise SystemExit(f"Missing SSOT: {SETTINGS_PATH}")
    return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))


def parse_plugin_id(plugin_id: str) -> PluginRef:
    if "@" not in plugin_id:
        raise ValueError(f"Invalid plugin id (expected name@marketplace): {plugin_id!r}")
    name, marketplace = plugin_id.rsplit("@", 1)
    if not name or not marketplace:
        raise ValueError(f"Invalid plugin id (expected name@marketplace): {plugin_id!r}")
    return PluginRef(name=name, marketplace=marketplace)


def validate_settings(settings: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    marketplaces = settings.get("extraKnownMarketplaces")
    enabled = settings.get("enabledPlugins")

    if not isinstance(marketplaces, dict) or not marketplaces:
        errors.append("extraKnownMarketplaces must be a non-empty object")
    if not isinstance(enabled, dict) or not enabled:
        errors.append("enabledPlugins must be a non-empty object")

    if isinstance(marketplaces, dict):
        for key, entry in marketplaces.items():
            if " " in key:
                errors.append(f"marketplace key {key!r} must not contain spaces")
            source = (entry or {}).get("source") if isinstance(entry, dict) else None
            if not isinstance(source, dict):
                errors.append(f"marketplace {key!r} missing source object")
                continue
            kind = source.get("source")
            if kind == "github":
                repo = source.get("repo", "")
                if not isinstance(repo, str) or not GITHUB_REPO_RE.match(repo):
                    errors.append(f"marketplace {key!r} has invalid github repo {repo!r}")
            elif kind == "git":
                url = source.get("url", "")
                if not isinstance(url, str) or not url:
                    errors.append(f"marketplace {key!r} missing git url")
            else:
                errors.append(f"marketplace {key!r} uses unsupported source kind {kind!r}")

    if isinstance(enabled, dict):
        for plugin_id, value in enabled.items():
            if value is not True:
                continue
            try:
                ref = parse_plugin_id(plugin_id)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            if isinstance(marketplaces, dict) and ref.marketplace not in marketplaces:
                errors.append(
                    f"enabled plugin {plugin_id!r} references unknown marketplace "
                    f"{ref.marketplace!r}"
                )

    return errors


def plugin_cache_root() -> Path:
    return Path(os.environ.get("CURSOR_PLUGINS_HOME", Path.home() / ".cursor" / "plugins"))


def marketplace_cache_dir(marketplace_key: str) -> Path:
    return plugin_cache_root() / "marketplaces" / marketplace_key


def plugin_install_dir(plugin_id: str) -> Path:
    slug = plugin_id.replace("@", "__").replace("/", "_")
    return plugin_cache_root() / "local" / slug


def git_clone_or_update(
    *,
    url: str,
    dest: Path,
    ref: str | None = None,
    sha: str | None = None,
    sparse_path: str | None = None,
    dry_run: bool,
) -> None:
    if dry_run:
        log(f"would sync git {url} -> {dest}")
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and (dest / ".git").is_dir():
        if sha:
            subprocess.run(["git", "-C", str(dest), "fetch", "origin", sha], check=True)
            subprocess.run(["git", "-C", str(dest), "checkout", "--force", sha], check=True)
        else:
            subprocess.run(["git", "-C", str(dest), "fetch", "--depth", "1", "origin"], check=True)
            target = ref or "FETCH_HEAD"
            subprocess.run(["git", "-C", str(dest), "checkout", "--force", target], check=True)
            subprocess.run(["git", "-C", str(dest), "pull", "--ff-only"], check=False)
        return

    if dest.exists():
        shutil.rmtree(dest)

    clone_cmd = ["git", "clone"]
    if not sha:
        clone_cmd.append("--depth=1")
    if ref and not sha:
        clone_cmd.extend(["--branch", ref])
    if sparse_path:
        clone_cmd.extend(["--filter=blob:none", "--sparse", url, str(dest)])
    else:
        clone_cmd.extend([url, str(dest)])

    subprocess.run(clone_cmd, check=True)
    if sparse_path:
        subprocess.run(
            ["git", "-C", str(dest), "sparse-checkout", "set", sparse_path],
            check=True,
        )
    if sha:
        subprocess.run(["git", "-C", str(dest), "checkout", sha], check=True)


def marketplace_git_url(source: dict[str, Any]) -> tuple[str, str | None, str | None]:
    kind = source["source"]
    if kind == "github":
        repo = source["repo"]
        ref = source.get("ref")
        return f"https://github.com/{repo}.git", ref, None
    if kind == "git":
        return source["url"], source.get("ref"), source.get("sha")
    raise ValueError(f"Unsupported marketplace source kind: {kind!r}")


def sync_marketplace(key: str, entry: dict[str, Any], *, dry_run: bool) -> Path:
    source = entry["source"]
    url, ref, sha = marketplace_git_url(source)
    dest = marketplace_cache_dir(key)
    git_clone_or_update(url=url, dest=dest, ref=ref, sha=sha, dry_run=dry_run)
    return dest


def find_marketplace_manifest(marketplace_root: Path) -> Path:
    for rel in MARKETPLACE_MANIFESTS:
        candidate = marketplace_root / rel
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"No marketplace manifest under {marketplace_root}")


def load_marketplace_plugins(marketplace_root: Path) -> dict[str, dict[str, Any]]:
    manifest_path = find_marketplace_manifest(marketplace_root)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    plugins = payload.get("plugins", [])
    if not isinstance(plugins, list):
        raise ValueError(f"Invalid marketplace manifest: {manifest_path}")
    by_name: dict[str, dict[str, Any]] = {}
    for entry in plugins:
        if isinstance(entry, dict) and isinstance(entry.get("name"), str):
            by_name[entry["name"]] = entry
    return by_name


def plugin_source_dir(entry: dict[str, Any], marketplace_root: Path, *, dry_run: bool) -> Path:
    source = entry.get("source")
    if isinstance(source, str):
        rel = source.removeprefix("./")
        return marketplace_root / rel

    if not isinstance(source, dict):
        raise ValueError(f"Plugin {entry.get('name')!r} has no installable source")

    kind = source.get("source")
    if kind == "local":
        rel = source.get("path", ".").removeprefix("./")
        return marketplace_root / rel

    if kind == "git-subdir":
        url = source["url"]
        if GITHUB_REPO_RE.match(url):
            url = f"https://github.com/{url}.git"
        ref = source.get("ref")
        sha = source.get("sha")
        subpath = source["path"]
        cache = plugin_cache_root() / "sources" / _slug(url) / subpath.replace("/", "__")
        if not dry_run and not cache.is_dir():
            tmp = cache.parent / "_repo"
            git_clone_or_update(
                url=url,
                dest=tmp,
                ref=ref,
                sha=sha,
                sparse_path=subpath,
                dry_run=False,
            )
            src = tmp / subpath
            if not src.is_dir():
                raise FileNotFoundError(f"git-subdir path missing: {src}")
            cache.parent.mkdir(parents=True, exist_ok=True)
            if cache.exists():
                shutil.rmtree(cache)
            shutil.copytree(src, cache)
            shutil.rmtree(tmp, ignore_errors=True)
        return cache

    if kind in {"git", "url", "github"}:
        url = f"https://github.com/{source['repo']}.git" if kind == "github" else source["url"]
        ref = source.get("ref")
        sha = source.get("sha")
        cache = plugin_cache_root() / "sources" / _slug(url)
        git_clone_or_update(url=url, dest=cache, ref=ref, sha=sha, dry_run=dry_run)
        return cache

    raise ValueError(f"Unsupported plugin source kind: {kind!r}")


def _slug(value: str) -> str:
    parsed = urlparse(value)
    base = parsed.path.strip("/").replace("/", "_") or parsed.netloc
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", base)


def install_plugin_tree(src: Path, dest: Path, *, dry_run: bool) -> None:
    if dry_run:
        log(f"would install plugin tree {src} -> {dest}")
        return

    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    for component in PLUGIN_COMPONENTS:
        source = src / component
        if source.exists():
            target = dest / component
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)


def upsert_json(path: Path, mutator: Any, *, dry_run: bool) -> None:
    if dry_run:
        return
    data: dict[str, Any] = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    mutator(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def register_plugin(plugin_id: str, install_path: Path, *, dry_run: bool) -> None:
    claude_plugins = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    claude_settings = Path.home() / ".claude" / "settings.json"

    def mutate_installed(payload: dict[str, Any]) -> None:
        plugins = payload.setdefault("plugins", {})
        entries = [
            e
            for e in plugins.get(plugin_id, [])
            if not (isinstance(e, dict) and e.get("scope") == "project")
        ]
        entries.insert(
            0,
            {
                "scope": "project",
                "installPath": str(install_path),
                "projectPath": str(ROOT),
            },
        )
        plugins[plugin_id] = entries

    def mutate_settings(payload: dict[str, Any]) -> None:
        payload.setdefault("enabledPlugins", {})[plugin_id] = True

    upsert_json(claude_plugins, mutate_installed, dry_run=dry_run)
    upsert_json(claude_settings, mutate_settings, dry_run=dry_run)


def ensure_claude_settings_link(*, dry_run: bool) -> None:
    if dry_run:
        return
    CLAUDE_SETTINGS_LINK.parent.mkdir(parents=True, exist_ok=True)
    if CLAUDE_SETTINGS_LINK.is_symlink():
        if CLAUDE_SETTINGS_LINK.resolve() == SETTINGS_PATH.resolve():
            return
        CLAUDE_SETTINGS_LINK.unlink()
    elif CLAUDE_SETTINGS_LINK.exists():
        CLAUDE_SETTINGS_LINK.unlink()
    CLAUDE_SETTINGS_LINK.symlink_to(Path("..") / ".cursor" / "settings.json")


def write_install_manifest(installed: dict[str, str], *, dry_run: bool) -> Path:
    manifest_path = ROOT / ".cursor" / "plugins" / "installed" / "manifest.json"
    if dry_run:
        return manifest_path
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "plugins": installed,
    }
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def sync_repo_skills(installed_dirs: list[Path], *, dry_run: bool) -> None:
    skills_root = ROOT / ".cursor" / "skills"
    if dry_run:
        return
    if skills_root.exists():
        for child in skills_root.iterdir():
            if child.is_symlink():
                child.unlink()
    else:
        skills_root.mkdir(parents=True, exist_ok=True)

    for plugin_dir in installed_dirs:
        skills_dir = plugin_dir / "skills"
        if not skills_dir.is_dir():
            continue
        for skill in skills_dir.iterdir():
            if not skill.is_dir():
                continue
            link = skills_root / skill.name
            if link.exists():
                continue
            link.symlink_to(skill.resolve())


def run_sync(*, dry_run: bool) -> list[Path]:
    settings = load_settings()
    errors = validate_settings(settings)
    if errors:
        for err in errors:
            log(f"ERROR: {err}")
        raise SystemExit(1)

    ensure_claude_settings_link(dry_run=dry_run)

    marketplaces = settings["extraKnownMarketplaces"]
    enabled = {
        plugin_id
        for plugin_id, value in settings.get("enabledPlugins", {}).items()
        if value is True
    }

    marketplace_roots: dict[str, Path] = {}
    for key, entry in marketplaces.items():
        log(f"sync marketplace {key}")
        marketplace_roots[key] = sync_marketplace(key, entry, dry_run=dry_run)

    installed_dirs: list[Path] = []
    installed_map: dict[str, str] = {}

    for plugin_id in sorted(enabled):
        ref = parse_plugin_id(plugin_id)
        marketplace_root = marketplace_roots[ref.marketplace]
        if dry_run and not marketplace_root.is_dir():
            dest = plugin_install_dir(plugin_id)
            installed_dirs.append(dest)
            installed_map[plugin_id] = str(dest)
            log(f"would install {plugin_id}")
            continue

        catalog = load_marketplace_plugins(marketplace_root)
        entry = catalog.get(ref.name)
        if entry is None:
            raise SystemExit(f"Plugin {ref.name!r} not found in marketplace {ref.marketplace!r}")

        src = plugin_source_dir(entry, marketplace_root, dry_run=dry_run)
        dest = plugin_install_dir(plugin_id)
        log(f"install {plugin_id} from {src}")
        install_plugin_tree(src, dest, dry_run=dry_run)
        register_plugin(plugin_id, dest, dry_run=dry_run)
        installed_dirs.append(dest)
        installed_map[plugin_id] = str(dest)

    write_install_manifest(installed_map, dry_run=dry_run)
    sync_repo_skills(installed_dirs, dry_run=dry_run)
    return installed_dirs


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Cursor plugin marketplaces")
    parser.add_argument("--check", action="store_true", help="Validate settings SSOT only")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without writing")
    parser.add_argument(
        "--print-plugin-dirs",
        action="store_true",
        help="Print installed plugin directories (one per line)",
    )
    args = parser.parse_args()

    if args.check:
        errors = validate_settings(load_settings())
        if errors:
            for err in errors:
                log(f"ERROR: {err}")
            raise SystemExit(1)
        log("settings OK")
        return

    if args.print_plugin_dirs:
        manifest = ROOT / ".cursor" / "plugins" / "installed" / "manifest.json"
        if manifest.is_file():
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            for path in payload.get("plugins", {}).values():
                print(path)
            return
        settings = load_settings()
        for plugin_id, value in settings.get("enabledPlugins", {}).items():
            if value is True:
                print(plugin_install_dir(plugin_id))
        return

    dirs = run_sync(dry_run=args.dry_run)
    log(f"done ({len(dirs)} plugins)")


if __name__ == "__main__":
    main()
