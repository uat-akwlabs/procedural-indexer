# Procedural Knowledge Find — .claude-science (one filetype at a time)

**Root:** `/home/zhouk/.claude-science` — 23 top-level entries you listed, decomposed via `PathParts.from_relative()` `src/python/models.py:18`.

## Your 23 paths decomposed (depth 0)

All `depth=0`, `parentRel=""`, `subdirs=[]` — they ARE the root index. Procedural core is `subdirs + filename + ext` per file, recursed.

```
.key-backups  -> subdirs=[] depth=0 ext=""          DIR
.legacy-adopted -> [] ""                            FILE (no ext)
.oauth-tokens -> [] ""                              DIR
active-org.json -> [] .json
auth-owner.lock -> [] .lock
conda -> [] ""                                      DIR (17GB, 457 exts)
daemon.sock -> [] .sock
encryption.key -> [] .key
...
```

Validated: Python `index_one_type(..., ".json", include_hidden)` = 4992 files = TS `npx tsx indexer.ts --ext .json --include-hidden` = 4992 `src/typescript/indexer.ts:42`.

## Where knowledge lives — procedural grouping by first subdir

One filetype at a time, then `group_by_subdir()` `src/python/models.py:78`:

| ext | total | orgs | runtime | meaning |
| --- | --- | --- | --- | --- |
| .py | 433 | 75 | 358 | 75 in `orgs/.../artifacts/proj_e0f942749beb/...` are the better implementation |
| .sh | 14 | 14 | 0 | all knowledge |
| .yml | 6 | 6 | 0 | env specs source of truth |
| .md | 175 | 123 | 47 | audit reports |
| .json | 72* | 28 | 32 | bench results |
| .cu | 2 | 2 | 0 | smoketest |

*filtered (ignore conda); unfiltered 4992.

**Better implementation is `orgs/9ec44738-.../artifacts/proj_e0f942749beb/`** — the cancelled `Optimize Local Environment for Data-Intensive Workloads` frame `2fb8c30a`:

- `audit/audit-compute-env.sh` (108 lines, `--json` mode) — measures GPU `/dev/dxg` vs `/dev/nvidia*`, `libcuda.so.1`, `nvcc --list-gpu-arch`, BLAS via `numpy.__file__` parents `src/python/indexer.py:12` pattern
- `audit/bench_cpu.py` — 5 trials per thread count, median/min/max/spread, stability-aware `recommended=20` not peak `src/python/models.py:78`
- `setup/env/environment-datacompute.yml` + `environment-gpu.yml` — source of truth, not hand-install
- `setup/tuning/compute-tuning.sh` — `OMP_NUM_THREADS=20` measured +86% fp32, `expandable_segments:True` for 11GB
- `setup/setup.sh` idempotent converge, `verify-gpu.py`, `arch_smoketest.cu` (sm_75)

Contrast: earlier naive `lscpu/free/df/nvidia-smi` one-shot. Better does **measured, not inferred**, with provenance JSON.

## Code execution (mirrored Python ↔ TS+zod)

Python: `src/python/models.py` dataclasses `PathParts`, `FileEntry`, `FileTypeIndex` + `src/python/indexer.py:index_one_type(root, ext)` `src/python/indexer.py:60`.
TS: `src/typescript/types.ts` interfaces + `schemas.ts` generated via `npx ts-to-zod src/typescript/types.ts src/typescript/schemas.ts` `package.json:10` + `src/typescript/indexer.ts:indexOneType` `src/typescript/indexer.ts:42` with `zod` validation per entry.

Cross-validated: same `relativePath`, `subdirs`, `depth`, `parentRel`, counts for all exts under same `ignoreDirs`.

Run:
```bash
source .venv/bin/activate
python -m src.python.indexer /home/zhouk/.claude-science --ext .json --include-hidden --json /tmp/py.json
npx tsx src/typescript/indexer.ts /home/zhouk/.claude-science --ext .json --include-hidden --json /tmp/ts.json
diff <(jq .count /tmp/py.json) <(jq .count /tmp/ts.json) # both 4992
```
