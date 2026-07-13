# Local Ollama runtime

Ollama is the project's only required AI runtime. The default configuration runs entirely locally, disables Ollama cloud features, and exposes the project-managed API only on `127.0.0.1:11435`. The nonstandard host port avoids conflicting with a native Ollama installation, which normally uses `11434`; inside the container, Ollama still listens on `11434`.

## Default models

- Instruction: `qwen3:4b-instruct` (approximately 2.5 GB)
- Embeddings: `embeddinggemma` (approximately 622 MB)

Override either model in `.env` without changing application code. Model quality and embedding dimensions are versioned and evaluated in later milestones.

## CPU mode

CPU mode is the portable default and requires no override file:

```powershell
corepack pnpm ollama:setup
corepack pnpm ollama:check
corepack pnpm test:ollama
```

Expect the first command to download the Ollama image and both model weights, requiring several gigabytes of disk space and network transfer. Generation may be slow on CPU-only systems.

## NVIDIA GPU mode

NVIDIA acceleration requires a supported GPU, current drivers, and NVIDIA Container Toolkit support in Docker. On Windows, Docker Desktop must use the WSL2 backend with GPU support.

```powershell
docker compose -f docker-compose.yml -f infra/ollama/compose.nvidia.yml up --detach --wait ollama
python scripts/setup_ollama.py --skip-start
python scripts/smoke_ollama.py
```

The override reserves one NVIDIA GPU. Edit the override deliberately if a different device policy is required.

## AMD GPU mode

The AMD override uses Ollama's ROCm image and Linux `/dev/kfd` and `/dev/dri` devices. It is intended for compatible Linux hosts; it is not the default Windows or macOS path.

```bash
docker compose -f docker-compose.yml -f infra/ollama/compose.amd.yml up --detach --wait ollama
python scripts/setup_ollama.py --skip-start
python scripts/smoke_ollama.py
```

## Readiness states

The readiness command distinguishes:

- `unavailable`
- `instruction_model_missing`
- `embedding_model_missing`
- `model_loading`
- `ready`

The setup probe reports installed-model readiness. The later API runtime will use `model_loading` while an installed model is actively warming. When a model is missing, run `corepack pnpm ollama:setup`. Do not substitute a hosted model.

Downloaded models are stored in the Docker named volume `ollama_data` and survive container recreation. `docker compose down` preserves them; `docker compose down --volumes` deletes them.
