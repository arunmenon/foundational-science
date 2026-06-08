# pilot.md — RunPod open-model pilot (headless, survives laptop death)

**Goal:** before spending the $50–100 batch budget, measure on **our own eval gate** whether an
open model matches the `gpt-5.4` baseline (41/50 gold) as the factory's agent — and at what
throughput / $-per-1M-tokens. Everything runs **on RunPod** (model + factory) writing to a
**network volume**, so generation survives the laptop disconnecting.

## ✅ VERIFIED working stack + fast resume (no more CUDA circus)
The pod's driver is **CUDA 12.8** (RTX PRO 6000, driver 570). The *latest* vLLM/torch are built for
CUDA 13 and **fail** on this driver (`libcudart.so.13` / "driver too old, found 12080"). The coherent
stack that works end-to-end (verified 2026-06-08) is pinned by **`runpod_setup.sh`** (a copy lives on
the volume at `/workspace/setup_pod.sh`):

| Component | Version | The fix |
|---|---|---|
| vLLM | **0.11.0** | pin `torch==2.8.0` + `uv --torch-backend=cu128` → resolves a CUDA-12.8 vLLM (not the CUDA-13 latest) |
| torch | **2.8.0+cu128** | `--torch-backend=cu128` |
| transformers | **4.57.6** | `pip install "transformers<5"` (5.x removed `all_special_tokens_extended`) |
| numpy | **2.2.6** | `pip install "numpy<2.3"` (numba needs NumPy ≤ 2.2) |

**Fast resume on a fresh pod (same GPU/driver class):** attach the network volume → it already holds the
built `venv` (14 G) **and** the Qwen3 weights (`/workspace/hf`, 57 G), so:
```bash
bash /workspace/setup_pod.sh     # idempotent: REUSES the venv if present (instant); rebuilds if not
# then serve (in tmux):
export HF_HOME=/workspace/hf
/workspace/venv/bin/vllm serve Qwen/Qwen3-30B-A3B-Instruct-2507 --host 0.0.0.0 --port 8000 \
  --served-model-name qwen3 --max-model-len 16384 --gpu-memory-utilization 0.9 \
  --enable-auto-tool-choice --tool-call-parser hermes
```
So terminating the pod is safe — everything (datasets, venv, weights, this script) is on the volume.
**Caveat:** this stack is for a **CUDA-12.8** pod. A bigger trajectory model on a **CUDA-13** pod
(driver ≥ 580) needs its own stack (likely the *latest* vLLM, which is the easy default there) — we'll
capture that recipe when we pick that model.

## Why run the factory ON RunPod (not the laptop)
- **Resilience:** the factory orchestration runs in `tmux` on a pod; close the laptop / lose wifi
  and generation keeps running.
- **Persistence:** outputs (incl. certified gold) land on a **network volume** that survives even
  after the GPU pod is destroyed.
- **Latency/cost:** factory → vLLM in the same datacenter = no round-trips to your laptop.

```
 laptop ──ssh (only to launch)──▶  RunPod
                                   ├─ vLLM serving the model      (:8000, OpenAI-compatible)
                                   └─ factory generate.py (tmux)  ──writes──▶ Network Volume (/workspace)
```

## Two topologies
- **A — one GPU pod (recommended for the pilot):** the GPU pod runs **both** vLLM and the factory.
  Simplest, lowest latency (`localhost:8000`), one thing to manage. Tear it down when done.
- **B — split (recommended for the real campaign):** a cheap **CPU pod** ($0.06/hr, like your
  existing pods) runs the factory 24/7 and is the durable control plane; the **GPU** (expensive)
  only runs while generating, as a Pod or the managed **vLLM Endpoint**. The CPU pod + network
  volume stay up cheaply; you spin the GPU up/down per batch.

---

## Step 0 — pick the candidate (start cheapest-to-test)
| Role | Model | HF id (verify) | Fits |
|---|---|---|---|
| Trajectories | **GPT-OSS-120B** (mxfp4 ~63 GB) | `openai/gpt-oss-120b` | RTX PRO 6000 Blackwell 96 GB or H100 80 GB |
| Trajectories (max tool quality) | GLM-4.5-Air (106 B) | `zai-org/GLM-4.5-Air` | 96 GB / H200 |
| Bulk text | Qwen3-30B-A3B (fp8) | `Qwen/Qwen3-30B-A3B` | any 48 GB+ |

Start with **GPT-OSS-120B on the RTX PRO 6000 Blackwell 96 GB** — single GPU, native FP4/FP8.

## Step 1 — create a Network Volume
Console → **Storage → Network Volume** → ~50 GB, region = where your GPU is (e.g. `EU-RO-1`, same
as your existing pods). It mounts at **`/workspace`** on any pod you attach it to.

## Step 2 — deploy the GPU pod (topology A) with the volume attached
Console → **Pods → Deploy** → pick the GPU, attach the network volume at `/workspace`, use a
PyTorch/vLLM template. SSH in (use your TCP endpoint form for rsync/scp, per your RunPod notes).

Start vLLM in a tmux window:
```bash
tmux new -s vllm
pip install -U vllm            # if not already in the image
vllm serve openai/gpt-oss-120b \
  --host 0.0.0.0 --port 8000 \
  --served-model-name gptoss \
  --max-model-len 16384 \
  --gpu-memory-utilization 0.9
# wait for "Application startup complete", then: curl http://localhost:8000/v1/models
# detach: Ctrl-b then d
```
Quant: GPT-OSS ships **mxfp4** (~63 GB, fits 96/80 GB). For Qwen3-30B use `--quantization fp8`.
Keep trajectory models at FP8/FP4, **not INT4** (INT4 can hurt function-calling).

## Step 3 — put the factory on the volume
Either clone the branch:
```bash
cd /workspace
git clone -b feat/ato-synthetic-data-factory <repo-url> repo
cd repo/research/apt1-synthetic-data-factory/factory
```
…or rsync from the laptop (factory is pure Python 3 stdlib — no deps for generate.py):
```bash
rsync -avz -e "ssh -p <PORT>" \
  /Users/arunmenon/projects/Foundation-Science/research/apt1-synthetic-data-factory/factory/ \
  root@<POD_IP>:/workspace/factory/
```

## Step 4 — run the pilot in tmux (survives disconnect)
```bash
tmux new -s gen
cd /workspace/factory          # (or /workspace/repo/.../factory)
export OPENAI_BASE_URL=http://localhost:8000/v1
export OPENAI_API_KEY=local    # vLLM needs no key, but our client requires this var non-empty
export OPENAI_MODEL=gptoss     # = --served-model-name
export JUDGE_DISABLED=1        # STAGE 1: measure agent pass-rate + throughput, fully self-hosted
export GEN_K=20
time python3 generate.py
# detach: Ctrl-b then d  → generation keeps running; you can close the laptop now.
```
Outputs land in `/workspace/factory/generated/*.jsonl` on the **network volume** → they persist
after teardown. Reattach anytime from anywhere: `ssh … && tmux attach -t gen`.

## Step 5 — read the result (vs the gpt-5.4 baseline)
```bash
python3 - <<'PY'
import glob, json, os
from collections import Counter
f = max(glob.glob("generated/ato.*.candidates.jsonl"), key=os.path.getmtime)
rows = [json.loads(l) for l in open(f)]
bp = Counter(r.get("blueprint","<err>") for r in rows)
passed = Counter(r.get("blueprint","<err>") for r in rows if r.get("grade",{}).get("final_grade")=="PASS")
hv = Counter(v["id"] for r in rows for v in r.get("grade",{}).get("hard_violations",[]))
print("model:", rows[0]["model"]["agent"])
for b in sorted(bp): print(f"  {b:<22} pass {passed[b]}/{bp[b]}")
print("safety breaches:", dict(hv) or "NONE")
PY
```
- **Quality:** pass-rate per blueprint vs gpt-5.4 (41/50) / gpt-5.4-mini (32/50).
- **Throughput:** `time` from Step 4 → total output tokens ÷ seconds = tok/s → $/1M at the pod's $/hr.
- Decision: if pass-rate is close to baseline at a much lower $/1M, proceed to the full batch.

## Step 6 — teardown
Stop/destroy the **GPU pod**. The **network volume** (and your gold) remains. You only paid for GPU
while it was up. (In topology B, leave the cheap CPU pod up as the control plane.)

---

## Known wrinkles (read before relying on the numbers)
1. **Judge in the pilot.** Stage 1 sets `JUDGE_DISABLED=1`, so you measure *pass-rate* (outcome +
   P01–P12), **not certified gold** (P13 needs the judge). For gold numbers, two options:
   - (a) judge on the **same hosted model** (unset `JUDGE_DISABLED`, `JUDGE_MODEL=gptoss`) —
     fully self-hosted but the judge is *uncalibrated* for the open model;
   - (b) keep the **calibrated gpt-5.4-mini** judge (the clean experiment) — needs a small
     `JUDGE_BASE_URL` / `JUDGE_API_KEY` split in `generate.py`/`judge.py` so the agent can be local
     vLLM while the judge stays on OpenAI. **(I can add this — ~10 lines.)**
2. **Throughput is under-measured by default.** `generate.py` runs trajectories **sequentially**,
   so the GPU sits idle between calls and tok/s looks low. To measure real batched throughput (and
   to make the bulk job cheap), the client must fire **concurrent** requests. **(I can add a
   `GEN_CONCURRENCY` flag — small change.)** Until then, run a few `generate.py` in parallel, or
   read tok/s from vLLM's own logs.
3. **Serverless vs Pod.** With the sequential client, a dedicated Pod is mostly idle — Serverless
   (pay-per-compute) may be cheaper for the pilot. Once concurrency is added and the GPU is
   saturated, a Community/spot **Pod** at the lower $/hr wins for the bulk batch.
4. **Cost.** A pilot is ~1–3 GPU-hours; your current ~$26 balance covers it with room to spare.
