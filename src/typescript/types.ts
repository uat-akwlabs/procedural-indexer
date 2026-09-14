/**
 * types.ts — source of truth for procedural filepath indexing.
 * Mirrors Python src/python/models.py dataclasses.
 * Zod schemas are generated via ts-to-zod into schemas.ts.
 * Change THIS file, then run: npx ts-to-zod src/typescript/types.ts src/typescript/schemas.ts
 *
 * One filetype at a time is the procedural invariant.
 */

/** Decomposed relative path: subdirs + filename */
export interface PathParts {
  /** subdirectory parts from root, e.g. ["runtime","0.1.47-release","seed"] */
  subdirs: string[];
  /** len(subdirs) — denormalized for flat queries */
  depth: number;
  /** basename with ext, e.g. "manifest.json" */
  filename: string;
  /** without ext, e.g. "manifest" */
  stem: string;
  /** lowercased ext with dot, e.g. ".json" or "" */
  ext: string;
  /** parent rel posix, e.g. "runtime/0.1.47-release/seed" or "" */
  parentRel: string;
  /** full relative posix path, e.g. "runtime/seed/manifest.json" */
  relativePath: string;
}

/** Single indexed file — one row in a per-type index */
export interface FileEntry {
  /** posix relative path from index root */
  relativePath: string;
  /** absolute path */
  absolutePath: string;
  /** decomposed parts */
  parts: PathParts;
  /** lowercased ext the index was filtered to, e.g. ".py" */
  fileType: string;
  sizeBytes: number;
  /** nanoseconds since epoch */
  mtimeNs: number;
  /** duplicate of parts.depth for flat queries */
  depth: number;
  /** optional sha256 hex, computed on demand */
  sha256?: string | null;
}

/** All files of one ext under a root — the 'one filetype at a time' unit */
export interface FileTypeIndex {
  /** absolute root that was walked */
  root: string;
  /** the single ext this index covers, e.g. ".json" */
  fileType: string;
  count: number;
  totalBytes: number;
  entries: FileEntry[];
  scannedDirs: number;
  elapsedMs: number;
  indexedAt: string; // ISO8601
}

/** Container for multi-type indexing */
export interface IndexResult {
  root: string;
  indexes: FileTypeIndex[];
  elapsedMs: number;
}
