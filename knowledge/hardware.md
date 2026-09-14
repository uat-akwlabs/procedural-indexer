# Hardware Profile — DESKTOP-UFNGRM3 WSL2 (2026-09-13)

**CPU:** AMD Ryzen 9 3900X 12-Core (24 threads) Zen2, ~3.8GHz base, L3 64MB (reported as 16MB per CCX) — `lscpu:24`
**RAM:** Host 128GB → WSL capped at 112GB (`memory=112GB` in `C:\Users\Zhouk\.wslconfig`), observed 110Gi + 32GB swap on F:\WSL\swap.vhdx (good: off C:)
**GPU:** NVIDIA RTX 2080 Ti (TU102) 11GB VRAM (11264 MiB), Compute 7.5, 68 SMs, 250W, Driver 591.86 CUDA 13.1 compat, ~10GB usable alloc tested
**CUDA Toolchain:** CUDA 13.1 (nvcc 13.1.115 at /usr/local/cuda -> /etc/alternatives/cuda-13.1), + PyTorch 2.11 cu128 (CUDA 12.8 runtime) in `.venv`
**Disk:** WSL VHDX `/dev/sdd` 503GB (317GB free, 34% used) capped at 512GB via `defaultVhdSize=512GB` — lives on C:. **C:\ 1.9T only 14GB free (100%) — CRITICAL**. F:\ 1.9T 1.1T free.
**Kernel:** 6.6.87.2-microsoft-standard-WSL2, `systemd=true`, Docker 29.8.0, nvidia-container-toolkit 1.19.0
**WSL config:** 24 processors, `sparseVhd=true`, `autoMemoryReclaim=gradual`, NAT+ dnsTunneling, nestedVirt true — well tuned.
