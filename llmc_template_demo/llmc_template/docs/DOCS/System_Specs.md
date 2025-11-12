# Host: ff (Flagship Shitbox)

Internal IP: `192.168.5.66`

## CPU
- Model: 11th Gen Intel(R) Core(TM) i7-1185G7 @ 3.00GHz (Tiger Lake)
- Architecture: x86_64
- Cores/Threads: 4 cores / 8 threads (HT enabled)
- Base / Max Frequency: 3.0 GHz base, turbo up to 4.8 GHz
- Instruction Sets: AVX2, AVX-512 (multiple extensions), AES-NI, BMI1/2, FMA, SHA, etc.
- Virtualization: VT-x available

## Memory
- Total RAM: 31.9 GiB online
- NUMA Nodes: Single node (0-7 CPUs)

## Storage
- Root device: `/dev/nvme0n1p5`
- Capacity: 247 GiB usable (258,994,152 1K blocks)
- Free space (2025-11-01): ~188 GiB (197,279,620 1K blocks)
- EFI partition: `/dev/nvme0n1p1` (256 MiB, 15% used)
- Google Drive mount: `/home/vmlinux/mnt/dcgoogledrive` (200 GiB quota, ~62 GiB free)

## Kernel Flags (Highlights)
- Hardware capabilities include AVX-512 variants, SHA extensions, GFNI, VAES, VPCLMULQDQ, and Intel PT.
- Spectre/Meltdown mitigations active; Spectre v1/v2 smart mitigations enabled.

## Notes
- Treat as primary dev/host box for LLMC; assume no dedicated GPU acceleration.
- Keep concurrent build processes to one to avoid thermal throttling.
- Log this spec when tuning local LLM presets (e.g., Goetia 24B Q5 for creative writing).

# Host: scrappy (Surface Scrappy Box)

Internal IP: `102.168.5.76`

## CPU
- Model: Intel(R) Core(TM) i7-6650U @ 2.20GHz (Skylake-U)
- Architecture: x86_64
- Cores/Threads: 2 cores / 4 threads (HT enabled)
- Base / Max Frequency: 2.2 GHz base, turbo up to 3.4 GHz
- Instruction Sets: AVX2, FMA, AES-NI, BMI1/2, MPX, etc.; VT-x available.

## Memory
- Total RAM: 16 GiB online
- NUMA Nodes: Single node (0-3 CPUs)

## Storage
- (Not enumerated; treat as limited—keep generated artifacts minimal.)

## Notes
- Microsoft Surface chassis with damaged display—treat as headless utility/scrappy box.
- Good for lightweight orchestration tasks, agent experiments, or background sync services.
- Watch thermals; prefer single build thread and lower-priority workloads.

# Host: p16 (Daily Driver Shitbox)

Internal IP: (TBD; record when static)

## CPU
- Model: 13th Gen Intel(R) Core(TM) i9-13950HX (Raptor Lake)
- Cores/Threads: 24 cores (8P + 16E) / 32 threads
- Notes: High turbo headroom; reserve for heavier LLM runs or multi-agent orchestration.

## Memory
- Total RAM: 64 GiB

## Storage
- NVMe capacity: 4 TB usable

## GPU
- NVIDIA RTX 2000 Ada Generation Laptop GPU (8 GiB VRAM). Treat as primary acceleration target for quantized 13B–24B models.

## Notes
- Primary development workstation; leverage for local UI builds, quantized 24B models, and multi-service orchestration.
- Keep ff for always-on services; offload bursty workloads here when plugged into mains.
