"""indexer.py — procedural filepath indexer, one filetype at a time.

Design mirrors claude-science audit/bench_cpu.py: trial-safe, JSON-serializable,
fresh-process friendly, with explicit --json provenance.

Usage:
  from src.python.indexer import index_one_type, index_many_types, iter_types

  idx = index_one_type("/home/zhouk/.claude-science", ".json")
  print(idx.count, idx.total_bytes)
  for entry in idx.entries:
      print(entry.relative_path, entry.parts.subdirs, entry.parts.filename)

  # one type at a time loop (procedural):
  for ft, idx in iter_types(root, [".py",".json",".md"]):
      ...

CLI:
  python -m src.python.indexer /tmp --ext .py --json out.json
  python -m src.python.indexer /tmp --ext .py --all --json out.json  # indexes all distinct exts
"""
from __future__ import annotations
import argparse
import json
import os
import time
from pathlib import Path
from typing import Iterator, List, Optional, Set

from .models import FileEntry, FileTypeIndex, PathParts, IndexResult


# same set as in audit-compute-env.sh for ignore discipline
DEFAULT_IGNORE_DIRS: Set[str] = {
    ".git", ".hg", ".svn", "__pycache__", ".venv", "venv", ".mypy_cache",
    ".pytest_cache", "node_modules", ".next", ".turbo", "dist", "build",
    ".parcel-cache", ".claude", ".codex",  # but caller can override to include .claude-science
}
DEFAULT_IGNORE_FILES: Set[str] = set()


def _should_ignore_dir(name: str, ignore_dirs: Set[str]) -> bool:
    return name in ignore_dirs


def _normalize_ext(ext: str) -> str:
    """Ensure leading dot, lowercased. '.JSON' -> '.json', 'json' -> '.json', '' -> ''."""
    if not ext:
        return ""
    e = ext.strip().lower()
    if not e.startswith("."):
        e = "." + e
    return e


def iter_files_recursive(
    root: Path,
    ext: Optional[str],
    ignore_dirs: Set[str] = DEFAULT_IGNORE_DIRS,
    follow_symlinks: bool = False,
) -> Iterator[Path]:
    """Yield absolute Path objects recursively, filtered to one ext if given.

    Procedural core: uses os.scandir iteratively (not glob) so subdirectory
    parts are available without extra stat calls. One filetype at a time
    keeps memory bounded: caller processes .py, then .json, etc.
    """
    root = root.resolve()
    stack: List[Path] = [root]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=follow_symlinks):
                            if _should_ignore_dir(entry.name, ignore_dirs):
                                continue
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=follow_symlinks):
                            p = Path(entry.path)
                            if ext is None:
                                yield p
                            else:
                                # Path.suffix is lowercased via _normalize
                                if p.suffix.lower() == ext:
                                    yield p
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError, FileNotFoundError):
            continue


def index_one_type(
    root: str | Path,
    file_type: str,
    ignore_dirs: Optional[Set[str]] = None,
    follow_symlinks: bool = False,
    compute_hash: bool = False,
    sort_by: str = "relative_path",
) -> FileTypeIndex:
    """Procedurally index ONE filetype under root.

    Returns FileTypeIndex with decomposed PathParts for every match.
    Focuses on one ext so caller can bound VRAM/RAM and stream types
    sequentially (like bench_cpu sweeps one thread count at a time).
    """
    t0 = time.perf_counter()
    root_p = Path(root).resolve()
    if not root_p.exists():
        raise FileNotFoundError(f"root does not exist: {root_p}")
    if not root_p.is_dir():
        raise NotADirectoryError(f"root is not a directory: {root_p}")

    ext = _normalize_ext(file_type)
    # allow caller to index dotless hidden files like "" by passing ""
    # but default is to require ext
    if ignore_dirs is None:
        ignore_dirs = DEFAULT_IGNORE_DIRS

    entries: List[FileEntry] = []
    scanned_dirs = 0
    total_bytes = 0

    # count scanned dirs separately for provenance
    # we walk again with os.walk for dir count when needed, but cheaper:
    # increment on each stack pop inside iter_files_recursive — we inline here
    # for single-pass efficiency.
    stack: List[Path] = [root_p]
    seen_files: List[Path] = []  # collected then stat'd — keeps scandir fast

    # Single walk that both counts dirs and collects matching files
    while stack:
        cur = stack.pop()
        scanned_dirs += 1
        try:
            with os.scandir(cur) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=follow_symlinks):
                            if _should_ignore_dir(entry.name, ignore_dirs):
                                continue
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=follow_symlinks):
                            p = Path(entry.path)
                            if p.suffix.lower() == ext:
                                seen_files.append(p)
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError, FileNotFoundError):
            continue

    # Now stat and build FileEntry objects — still procedural, one file at a time
    for abs_path in seen_files:
        try:
            stat = abs_path.stat()
            rel = abs_path.relative_to(root_p)
            parts = PathParts.from_relative(rel)
            sha = None
            if compute_hash:
                import hashlib
                h = hashlib.sha256()
                with open(abs_path, "rb") as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        h.update(chunk)
                sha = h.hexdigest()
            fe = FileEntry(
                relative_path=str(rel).replace(os.sep, "/"),  # posix for portability
                absolute_path=str(abs_path),
                parts=parts,
                file_type=ext,
                size_bytes=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
                depth=parts.depth,
                sha256=sha,
            )
            entries.append(fe)
            total_bytes += stat.st_size
        except (OSError, ValueError):
            continue

    # deterministic order — critical for diffing / caching like bench_cpu trials
    if sort_by == "relative_path":
        entries.sort(key=lambda e: e.relative_path)
    elif sort_by == "size":
        entries.sort(key=lambda e: e.size_bytes, reverse=True)
    elif sort_by == "mtime":
        entries.sort(key=lambda e: e.mtime_ns, reverse=True)

    elapsed_ms = (time.perf_counter() - t0) * 1000
    return FileTypeIndex(
        root=str(root_p),
        file_type=ext,
        count=len(entries),
        total_bytes=total_bytes,
        entries=entries,
        scanned_dirs=scanned_dirs,
        elapsed_ms=elapsed_ms,
    )


def iter_types(
    root: str | Path,
    file_types: List[str],
    **kwargs,
) -> Iterator[tuple[str, FileTypeIndex]]:
    """Procedural iterator: one filetype at a time, yielding (ext, index)."""
    for ft in file_types:
        ext = _normalize_ext(ft)
        yield ext, index_one_type(root, ext, **kwargs)


def discover_file_types(
    root: str | Path,
    ignore_dirs: Optional[Set[str]] = None,
    limit: Optional[int] = None,
) -> List[str]:
    """Scan once to discover distinct exts present — then caller can iterate one by one."""
    root_p = Path(root).resolve()
    if ignore_dirs is None:
        ignore_dirs = DEFAULT_IGNORE_DIRS
    exts: Set[str] = set()
    stack = [root_p]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for entry in it:
                    try:
                        if entry.is_dir():
                            if entry.name in ignore_dirs:
                                continue
                            stack.append(Path(entry.path))
                        elif entry.is_file():
                            ext = Path(entry.name).suffix.lower()
                            # include "" for extensionless files
                            exts.add(ext)
                            if limit and len(exts) >= limit:
                                return sorted(exts)
                    except OSError:
                        continue
        except OSError:
            continue
    return sorted(exts)


def index_many_types(
    root: str | Path,
    file_types: Optional[List[str]] = None,
    ignore_dirs: Optional[Set[str]] = None,
    **kwargs,
) -> IndexResult:
    """Index several types sequentially — still one at a time internally."""
    t0 = time.perf_counter()
    root_p = Path(root).resolve()
    if file_types is None:
        file_types = discover_file_types(root_p, ignore_dirs=ignore_dirs)
    indexes: List[FileTypeIndex] = []
    for ext in file_types:
        idx = index_one_type(root_p, ext, ignore_dirs=ignore_dirs, **kwargs)
        indexes.append(idx)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    return IndexResult(root=str(root_p), indexes=indexes, elapsed_ms=elapsed_ms)


# --- CLI mirroring audit/audit-compute-env.sh style ---
def main() -> None:
    ap = argparse.ArgumentParser(description="Procedural filepath indexer — one filetype at a time")
    ap.add_argument("root", help="root directory to walk")
    ap.add_argument("--ext", default=".py", help="single filetype to index, e.g. .json (default .py)")
    ap.add_argument("--all", action="store_true", help="discover and index all exts under root")
    ap.add_argument("--json", dest="json_out", help="write JSON to file (else stdout)")
    ap.add_argument("--ignore", nargs="*", help="extra dir names to ignore")
    ap.add_argument("--include-hidden", action="store_true", help="do not ignore .git/.venv/node_modules")
    ap.add_argument("--hash", action="store_true", help="compute sha256 per file")
    ap.add_argument("--sort", choices=["relative_path", "size", "mtime"], default="relative_path")
    ap.add_argument("--limit", type=int, help="limit entries printed to stdout (does not affect JSON)")
    args = ap.parse_args()

    ignore = set(DEFAULT_IGNORE_DIRS) if not args.include_hidden else set()
    if args.ignore:
        ignore.update(args.ignore)

    if args.all:
        res = index_many_types(args.root, ignore_dirs=ignore, compute_hash=args.hash, sort_by=args.sort)
        out = json.dumps(res.to_dict(), indent=2)
        print(f"Indexed {len(res.indexes)} types under {res.root} in {res.elapsed_ms:.1f}ms")
        for ix in res.indexes:
            print(f"  {ix.file_type or '(no ext)':12s} {ix.count:6d} files  {ix.total_bytes/1024:.1f} KiB  {ix.scanned_dirs} dirs")
    else:
        idx = index_one_type(args.root, args.ext, ignore_dirs=ignore, compute_hash=args.hash, sort_by=args.sort)
        print(f"Indexed {idx.count} *{idx.file_type} files under {idx.root} ({idx.total_bytes} bytes, {idx.scanned_dirs} dirs, {idx.elapsed_ms:.1f}ms)")
        for e in idx.entries[: args.limit or 20]:
            print(f"  {e.relative_path:60s}  {e.parts.subdirs}  {e.size_bytes}B")
        if args.limit and idx.count > args.limit:
            print(f"  ... +{idx.count - args.limit} more")
        out = idx.to_json()

    if args.json_out:
        Path(args.json_out).write_text(out)
        print(f"Wrote {args.json_out}")
    elif args.all:
        # already printed summary; dump full JSON to stdout when no --json
        pass


if __name__ == "__main__":
    main()
