"""models.py — dataclasses for procedural filepath indexing.

Mirrors TypeScript types in src/typescript/types.ts; zod schemas in
src/typescript/schemas.ts are generated via ts-to-zod. Change types.ts
first, regenerate schemas, then port the dataclass.

One filetype at a time is enforced by the indexer API.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Optional
import time
import json


@dataclass(frozen=True)
class PathParts:
    """Decomposition of a relative filepath into subdirectory parts + filename.

    Example: rel="runtime/0.1.47-release/seed/manifest.json"
      subdirs=["runtime","0.1.47-release","seed"], filename="manifest.json",
      stem="manifest", ext=".json", depth=3
    """
    subdirs: List[str]
    depth: int          # len(subdirs) — convenient for grouping/filtering
    filename: str       # basename with ext
    stem: str           # filename without ext
    ext: str            # ".json" lowercased, "" if no ext
    parent_rel: str     # "runtime/0.1.47-release/seed" or "" at root
    # full relative path reconstructed for convenience
    relative_path: str

    @staticmethod
    def from_relative(relative: Path | str) -> "PathParts":
        p = Path(relative)
        # p.parts is OS-split; for relative we want posix semantics
        parts = p.parts
        if not parts or parts == (".",):
            return PathParts([], 0, "", "", "", "", "")
        filename = parts[-1]
        subdirs = list(parts[:-1])
        # handle stem/ext correctly even for dotfiles
        stem = Path(filename).stem
        ext = Path(filename).suffix.lower()
        # dotfile like ".key-backups" has suffix "" — keep as is
        if filename.startswith(".") and ext == "":
            # treat hidden dotfile with no ext: stem is filename, ext ""
            pass
        parent_rel = str(Path(*subdirs)) if subdirs else ""
        if parent_rel == ".":
            parent_rel = ""
        return PathParts(
            subdirs=subdirs,
            depth=len(subdirs),
            filename=filename,
            stem=stem,
            ext=ext,
            parent_rel=parent_rel,
            relative_path=str(p),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class FileEntry:
    """Single indexed file — one row in a per-type index."""
    relative_path: str      # path relative to index root, posix
    absolute_path: str      # resolved absolute path
    parts: PathParts        # decomposed subdirectory parts + filename
    file_type: str          # ext lowercased, e.g. ".py", ".json"
    size_bytes: int
    mtime_ns: int           # nanoseconds since epoch — stable for sorting
    depth: int              # duplicate of parts.depth for flat queries
    # optional hash — computed on demand, not during walk
    sha256: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["parts"] = self.parts.to_dict()
        return d


@dataclass
class FileTypeIndex:
    """All files of one ext under a root — the 'one filetype at a time' unit."""
    root: str               # absolute root that was walked
    file_type: str          # the single ext this index covers, e.g. ".json"
    count: int              # len(entries)
    total_bytes: int
    entries: List[FileEntry] = field(default_factory=list)
    scanned_dirs: int = 0
    elapsed_ms: float = 0.0
    # provenance for audit
    indexed_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "file_type": self.file_type,
            "count": self.count,
            "total_bytes": self.total_bytes,
            "entries": [e.to_dict() for e in self.entries],
            "scanned_dirs": self.scanned_dirs,
            "elapsed_ms": self.elapsed_ms,
            "indexed_at": self.indexed_at,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    # helpers for procedural consumers
    def filter_by_depth(self, depth: int) -> List[FileEntry]:
        return [e for e in self.entries if e.depth == depth]

    def filter_by_subdir(self, subdir: str) -> List[FileEntry]:
        """Return entries whose parent_rel == subdir or starts with subdir/."""
        prefix = subdir.rstrip("/")
        return [e for e in self.entries if e.parts.parent_rel == prefix or e.parts.parent_rel.startswith(prefix + "/")]

    def group_by_subdir(self) -> dict[str, List[FileEntry]]:
        from collections import defaultdict
        g: dict[str, List[FileEntry]] = defaultdict(list)
        for e in self.entries:
            g[e.parts.parent_rel].append(e)
        return dict(g)


@dataclass
class IndexResult:
    """Container for multi-type indexing — convenience wrapper around many FileTypeIndex."""
    root: str
    indexes: List[FileTypeIndex] = field(default_factory=list)
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "elapsed_ms": self.elapsed_ms,
            "indexes": [ix.to_dict() for ix in self.indexes],
        }

    def summary(self) -> dict:
        return {
            ix.file_type: {"count": ix.count, "total_bytes": ix.total_bytes}
            for ix in self.indexes
        }
