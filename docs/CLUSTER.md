# CLUSTER.md — deepnet slurm usage (probed 2026-07-14)

## HARD RULE

**No job runs on the login node.** The login node is for editing, git, quick queries
(`sinfo`, `squeue`), and `make verify`-scale checks (seconds). Everything else —
probing grids, label generation, calibration, dataset processing, Phase D training —
is submitted via `sbatch` (templates in `scripts/slurm/`).

## Cluster layout (re-probe with `sinfo -N -o "%N %P %T %C %m %G"` if stale)

| Node | Partition | CPUs | RAM | GPUs | Sees our /data1? |
|---|---|---|---|---|---|
| deepnet2 | `gpu2` (default) | 64 | ~1 TB | H200 MIG: 28× 1g.18gb, 6× 2g.35gb, 2× 7g.141gb | **YES** (NFS mount of the login node's /data1) |
| mcore-n01 | `cpu` | 128 | ~1 TB | none | **NO** — it has a different, node-local /data1 (98% full) |

- **Walltime limit:** 2 days on both partitions.
- **Per-user GPU QOS caps** (`max_jobs_qos`): 4× 1g.18gb, 2× 2g.35gb, 1× 7g.141gb.
- **`--mcs-label=$USER` is REQUIRED** on every submission or allocation fails with
  "Please include --mcs-label in your job".

## Consequences for this project

1. **Run everything on `gpu2`** — CPU-only jobs included (it has 64 CPUs, typically
   idle). The repo, the `topofield` conda env, and `data/` are all directly visible
   there via NFS. Request `--gres=gpu:...` only when torch training actually needs it.
2. **Do NOT use the `cpu` partition** unless you explicitly stage code+env+data to
   mcore-n01 (it cannot see our /data1, and its local disk is nearly full). If probe
   grids ever saturate deepnet2's 64 CPUs, revisit with a staging script and a
   DECISIONS.md entry.
3. **GPU sizing:** probes (V0–V6) fit easily in a 1g.18gb MIG slice; Phase D encoders
   (≤8M params) fit in 1g.18gb too — request 2g.35gb only if profiling shows memory
   pressure. Never request the 7g.141gb slice without a measured need (there are only
   2 on the machine and the per-user cap is 1).
4. **Parallelism model for Phase B:** array jobs over grid cells
   (`scripts/slurm/grid_array.sbatch`), each task one config shard; the registry is
   append-only and safe under concurrent writers on one node (POSIX append), but keep
   per-cell outputs in per-run directories to avoid collisions.
5. Job logs go to `runs/slurm-%j.out` (gitignored). Every job still writes a normal
   run manifest; the slurm job ID is recorded in the manifest via `$SLURM_JOB_ID`.

## Quick reference

```bash
# submit                                  # monitor
sbatch scripts/slurm/calibrate.sbatch     squeue -u $USER
sbatch scripts/slurm/verify.sbatch        sacct -j <jobid> --format=JobID,State,Elapsed,MaxRSS
# interactive debugging shell on the compute node (still not the login node!)
srun -p gpu2 -n1 -c4 -t 02:00:00 --mcs-label=$USER --pty bash
```
