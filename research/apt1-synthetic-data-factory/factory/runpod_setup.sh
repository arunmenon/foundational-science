#!/usr/bin/env bash
# Reproducible vLLM setup for a RunPod pod whose driver is CUDA 12.8 (e.g. RTX PRO 6000 96GB,
# driver 570.x). The LATEST vLLM/torch are built for CUDA 13 and FAIL on a 12.8 driver
# (ImportError: libcudart.so.13 / "driver too old, found 12080"). These three pins give a
# coherent CUDA-12.8 stack that we verified end-to-end on 2026-06-08.
#
# It lives on the NETWORK VOLUME (/workspace) and is idempotent: if the venv on the volume already
# imports vllm._C, it is reused as-is (no reinstall, no re-download). So on a fresh pod:
#     1. attach the same network volume at /workspace
#     2. bash /workspace/setup_pod.sh          # ~instant if venv exists; ~5 min if rebuilding
#     3. (serve command is printed at the end)
set -euo pipefail
export HF_HOME=/workspace/hf
export HF_HUB_ENABLE_HF_TRANSFER=1
mkdir -p /workspace/hf

if /workspace/venv/bin/python -c "import vllm._C, vllm, torch" 2>/dev/null; then
  echo ">> existing venv works — reusing /workspace/venv (no reinstall)"
else
  echo ">> building venv with the pinned CUDA-12.8 stack..."
  rm -rf /workspace/venv
  python3 -m venv /workspace/venv
  /workspace/venv/bin/pip install -U pip uv
  # FIX 1 (CUDA): pin torch 2.8.0 + cu128 so uv resolves vLLM 0.11.0 (a CUDA-12.8 build).
  #              Without this, uv installs the latest vLLM (CUDA-13) whose _C needs libcudart.so.13.
  /workspace/venv/bin/uv pip install --python /workspace/venv/bin/python --torch-backend=cu128 torch==2.8.0 vllm hf_transfer
  # FIX 2 (tokenizer): transformers must be 4.x. transformers 5.x removed all_special_tokens_extended,
  #              which vLLM 0.11.0 still uses -> "Qwen2Tokenizer has no attribute all_special_tokens_extended".
  /workspace/venv/bin/uv pip install --python /workspace/venv/bin/python "transformers<5"
  # FIX 3 (numpy): numba needs NumPy <= 2.2; the default pull was numpy 2.4 -> ImportError at engine start.
  /workspace/venv/bin/uv pip install --python /workspace/venv/bin/python "numpy<2.3"
fi

# Verify the full import chain (this is what actually failed in the various wrong attempts).
/workspace/venv/bin/python - <<'PY'
import vllm._C, vllm, torch, transformers, numpy, numba
print("VERIFIED OK:",
      "vllm", vllm.__version__,
      "| torch", torch.__version__, torch.version.cuda,
      "| transformers", transformers.__version__,
      "| numpy", numpy.__version__,
      "| numba", numba.__version__,
      "| cuda_avail", torch.cuda.is_available())
PY

cat <<'EOF'

>> Ready. Serve a model with tool-calling (run inside tmux):
   export HF_HOME=/workspace/hf
   /workspace/venv/bin/vllm serve Qwen/Qwen3-30B-A3B-Instruct-2507 \
     --host 0.0.0.0 --port 8000 --served-model-name qwen3 \
     --max-model-len 16384 --gpu-memory-utilization 0.9 \
     --enable-auto-tool-choice --tool-call-parser hermes
EOF
