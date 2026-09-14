/**
 * indexer.ts — procedural filepath indexer, one filetype at a time.
 * Mirrors Python src/python/indexer.py exactly (same ignore rules, same PathParts).
 * Uses zod schemas from schemas.ts to validate each FileEntry.
 *
 * Usage:
 *   npx tsx src/typescript/indexer.ts /home/zhouk/.claude-science --ext .json
 *   npx tsx src/typescript/indexer.ts /home/zhouk/.claude-science --all
 */
import fs from "node:fs";
import path from "node:path";
import { fileEntrySchema, fileTypeIndexSchema } from "./schemas.js";
import type { FileEntry, FileTypeIndex, IndexResult, PathParts } from "./types.js";

const DEFAULT_IGNORE_DIRS = new Set([
  ".git",".hg",".svn","__pycache__",".venv","venv",".mypy_cache",
  ".pytest_cache","node_modules",".next",".turbo","dist","build",
  ".parcel-cache",".claude",".codex",
]);

function normalizeExt(ext: string): string {
  if (!ext) return "";
  let e = ext.trim().toLowerCase();
  if (!e.startsWith(".")) e = "." + e;
  return e;
}

function pathPartsFromRelative(relative: string): PathParts {
  // posix handling — relative is posix from Python side
  if (!relative || relative === ".") {
    return { subdirs: [], depth: 0, filename: "", stem: "", ext: "", parentRel: "", relativePath: "" };
  }
  const parts = relative.split("/").filter(Boolean);
  const filename = parts[parts.length - 1] ?? "";
  const subdirs = parts.slice(0, -1);
  const dot = filename.lastIndexOf(".");
  // hidden dotfile with no ext: ".legacy-adopted" -> stem=filename, ext=""
  // ".key-backups" is a dir, not a file, but for files we handle:
  let stem = filename;
  let ext = "";
  if (dot > 0) { // >0 so ".gitignore" stays stem=".gitignore" ext=""
    stem = filename.slice(0, dot);
    ext = filename.slice(dot).toLowerCase();
  } else if (filename.startsWith(".") && dot === -1) {
    stem = filename; ext = "";
  } else if (dot === -1) {
    stem = filename; ext = "";
  }
  const parentRel = subdirs.join("/");
  return { subdirs, depth: subdirs.length, filename, stem, ext, parentRel, relativePath: relative };
}

export function indexOneType(
  root: string,
  fileType: string,
  opts: { ignoreDirs?: Set<string>; followSymlinks?: boolean; sortBy?: "relativePath"|"size"|"mtime" } = {}
): FileTypeIndex {
  const t0 = performance.now();
  const rootAbs = path.resolve(root);
  if (!fs.existsSync(rootAbs) || !fs.statSync(rootAbs).isDirectory()) {
    throw new Error(`root does not exist or not a directory: ${rootAbs}`);
  }
  const ext = normalizeExt(fileType);
  const ignoreDirs = opts.ignoreDirs ?? DEFAULT_IGNORE_DIRS;
  const sortBy = opts.sortBy ?? "relativePath";

  const entries: FileEntry[] = [];
  let scannedDirs = 0;
  let totalBytes = 0;

  const stack: string[] = [rootAbs];
  const seen: string[] = [];

  while (stack.length) {
    const cur = stack.pop()!;
    scannedDirs++;
    let dirents: fs.Dirent[];
    try {
      dirents = fs.readdirSync(cur, { withFileTypes: true });
    } catch { continue; }
    for (const d of dirents) {
      const full = path.join(cur, d.name);
      try {
        if (d.isDirectory()) {
          if (ignoreDirs.has(d.name)) continue;
          stack.push(full);
        } else if (d.isFile() || (opts.followSymlinks && d.isSymbolicLink())) {
          const effExt = path.extname(d.name).toLowerCase();
          if (effExt === ext) seen.push(full);
        }
      } catch { continue; }
    }
  }

  for (const absPath of seen) {
    try {
      const stat = fs.statSync(absPath);
      const relPosix = path.relative(rootAbs, absPath).split(path.sep).join("/");
      const parts = pathPartsFromRelative(relPosix);
      const entry: FileEntry = {
        relativePath: relPosix,
        absolutePath: absPath,
        parts,
        fileType: ext,
        sizeBytes: stat.size,
        mtimeNs: Number(stat.mtimeMs * 1e6),
        depth: parts.depth,
        sha256: null,
      };
      // validate via zod — mirrors Python dataclass frozen guarantees
      fileEntrySchema.parse(entry);
      entries.push(entry);
      totalBytes += stat.size;
    } catch { continue; }
  }

  if (sortBy === "relativePath") entries.sort((a,b)=> a.relativePath.localeCompare(b.relativePath));
  else if (sortBy === "size") entries.sort((a,b)=> b.sizeBytes - a.sizeBytes);
  else if (sortBy === "mtime") entries.sort((a,b)=> b.mtimeNs - a.mtimeNs);

  const elapsedMs = performance.now() - t0;
  const idx: FileTypeIndex = {
    root: rootAbs,
    fileType: ext,
    count: entries.length,
    totalBytes,
    entries,
    scannedDirs,
    elapsedMs,
    indexedAt: new Date().toISOString(),
  };
  fileTypeIndexSchema.parse(idx);
  return idx;
}

export function discoverFileTypes(root: string, ignoreDirs: Set<string> = DEFAULT_IGNORE_DIRS): string[] {
  const rootAbs = path.resolve(root);
  const exts = new Set<string>();
  const stack = [rootAbs];
  while (stack.length) {
    const cur = stack.pop()!;
    let dirents: fs.Dirent[];
    try { dirents = fs.readdirSync(cur, { withFileTypes: true }); } catch { continue; }
    for (const d of dirents) {
      const full = path.join(cur, d.name);
      try {
        if (d.isDirectory()) {
          if (ignoreDirs.has(d.name)) continue;
          stack.push(full);
        } else if (d.isFile()) {
          exts.add(path.extname(d.name).toLowerCase());
        }
      } catch { continue; }
    }
  }
  return [...exts].sort();
}

export function indexManyTypes(root: string, fileTypes?: string[], ignoreDirs?: Set<string>): IndexResult {
  const t0 = performance.now();
  const types = fileTypes ?? discoverFileTypes(root, ignoreDirs);
  const indexes = types.map(ft => indexOneType(root, ft, { ignoreDirs }));
  return { root: path.resolve(root), indexes, elapsedMs: performance.now() - t0 };
}

// CLI mirroring Python
if (import.meta.url === `file://${process.argv[1]}`) {
  const root = process.argv[2] ?? "/home/zhouk/.claude-science";
  const extIdx = process.argv.indexOf("--ext");
  const ext = extIdx !== -1 ? process.argv[extIdx+1] : ".json";
  const all = process.argv.includes("--all");
  const jsonOutIdx = process.argv.indexOf("--json");
  const jsonOut = jsonOutIdx !== -1 ? process.argv[jsonOutIdx+1] : null;
  const includeHidden = process.argv.includes("--include-hidden");

  const ignore = includeHidden ? new Set<string>() : DEFAULT_IGNORE_DIRS;
  if (all) {
    const res = indexManyTypes(root, undefined, ignore);
    console.log(`Indexed ${res.indexes.length} types under ${res.root} in ${res.elapsedMs.toFixed(1)}ms`);
    for (const ix of res.indexes) console.log(`  ${ix.fileType || "(no ext)"} ${ix.count} files`);
    if (jsonOut) fs.writeFileSync(jsonOut, JSON.stringify(res, null, 2));
  } else {
    const idx = indexOneType(root, ext, { ignoreDirs: ignore });
    console.log(`Indexed ${idx.count} *${idx.fileType} files under ${idx.root} (${idx.totalBytes} bytes, ${idx.scannedDirs} dirs, ${idx.elapsedMs.toFixed(1)}ms)`);
    for (const e of idx.entries.slice(0,20)) console.log(`  ${e.relativePath}  ${JSON.stringify(e.parts.subdirs)}  ${e.sizeBytes}B`);
    if (jsonOut) fs.writeFileSync(jsonOut, JSON.stringify(idx, null, 2));
  }
}
