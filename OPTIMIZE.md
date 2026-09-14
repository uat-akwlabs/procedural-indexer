# Optimize for this machine (WSL2 + RTX 2080 Ti 11GB + 3900X 24T + 110Gi RAM)

## What was fixed
- Added CUDA env to `~/.bashrc` + `~/.zshrc`: `CUDA_HOME=/usr/local/cuda`, `PATH+=/usr/local/cuda/bin`, `LD_LIBRARY_PATH+=/usr/local/cuda/lib64:/usr/lib/wsl/lib` — `nvcc 13.1.115` now in PATH (`knowledge/hardware.md:2`)
- Created `.venv` (Python 3.12) with `torch 2.11 cu128` verified CUDA: `torch.cuda.is_available()=True`, 4096 matmul 56ms FP32, 10GB alloc ok (`knowledge/hardware.md:4`)
- Avoided heavy docker pulls (froze last run) — docker GPU is available via `nvidia-container-toolkit 1.19` but do `docker run --gpus all` only when needed, with `--pull never` if image cached

## Use this hardware properly

### GPU — Turing sm_75, 11GB (10GB usable)
```bash
source .venv/bin/activate
export CUDA_HOME=/usr/local/cuda
```
- **Precision:** Use `FP16` + `torch.cuda.amp` / `autocast(dtype=torch.float16)` — Turing has FP16 Tensor Cores. BF16 is emulated on 2080 Ti (slower, avoid). FP32 for final eval only.
- **Batch sizing:** 11GB → for LLM: 7B QLoRA 4-bit fits (~6GB), for SD: batch 4-8 at 512px, for 3D/vision: gradient checkpoint + batch 4. Always leave 0.8-1GB headroom for WSL/Xwayland (~1.2GB already used).
- **Compile:** `nvcc -arch=sm_75` ; PyTorch: `TORCH_CUDA_ARCH_LIST="7.5"` if building extensions. `xformers` limited on Turing — prefer `flash-attn` off, `sdpa` with `mem_efficient` off.
- **Monitor:** `watch -n 1 nvidia-smi` ; in code `torch.cuda.memory_allocated()` ; OOM → halve batch or enable `gradient_checkpointing=True`

### CPU/RAM — 3900X 24 threads, 110Gi available
- DataLoader: `num_workers=12-16` (half threads), `pin_memory=True`, `prefetch_factor=4`
- Threads: `export OMP_NUM_THREADS=12 MKL_NUM_THREADS=12 OPENBLAS_NUM_THREADS=12` (avoid oversubscription)
- In-memory joins OK up to ~80GB (leave 30GB for OS + GPU staging). Use `F:\` for large datasets via `/media/f` (1.1T free) not C:.

### Disk — FIX C: FIRST
- **CRITICAL:** `C:\` has only 14GB free (100% full). WSL VHDX lives on C: by default — even though capped at 512GB, growth will fail. 
  - Immediate: clean `C:\` (Downloads, Docker unused images `docker system prune`, pip cache `pip cache purge`, `%TEMP%`).
  - Better: move WSL distro to F: → `wsl --export Ubuntu-24.04 F:\WSL\backup.tar` then `wsl --import` to F:, or at least move Docker data-root to F:.
  - Keep datasets, checkpoints, HF cache on F: → `export HF_HOME=/media/f/hf_cache HF_DATASETS_CACHE=/media/f/hf_cache`
- WSL disk is `ext4` on `/dev/sdd` 317GB free — no action, `sparseVhd=true` already reclaims.

### WSL — already optimal
No change needed to `.wslconfig` (`memory=112GB`, `processors=24`, `swap=32GB` on F:, `sparseVhd`, `autoMemoryReclaim=gradual`). To apply after edit: `wsl --shutdown` from PowerShell.

## Quick smoke test
```bash
source .venv/bin/activate
python -c "import torch; print(torch.cuda.get_device_name(0)); print(torch.randn(1, device='cuda'))"
nvcc --version  # 13.1.115
nvidia-smi      # Driver 591.86
```
