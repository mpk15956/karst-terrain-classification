# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# Stage 1: pixi build. Resolves the locked CPU environment and copies the
# project source into the build context.
# ---------------------------------------------------------------------------
FROM ghcr.io/prefix-dev/pixi:0.67.0 AS build

WORKDIR /app

# Copy lockfile + manifest first so dep changes alone bust the layer cache.
COPY pyproject.toml pixi.lock ./
COPY README.md ./
COPY src/ src/
COPY scripts/ scripts/

# Install the locked CPU environment. The container ships CPU-only; CUDA
# reproduction needs host-specific GPU passthrough configuration.
RUN pixi install --locked --environment cpu

# Bake the activation hook so `apptainer exec` and `podman run --entrypoint=''`
# still pick up the env.
RUN pixi shell-hook --environment cpu --frozen > /shell-hook.sh \
    && echo 'exec "$@"' >> /shell-hook.sh

# ---------------------------------------------------------------------------
# Stage 2: runtime. Slim Debian base + the resolved pixi env.
# ---------------------------------------------------------------------------
FROM debian:12-slim AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY --from=build /app /app
COPY --from=build /shell-hook.sh /shell-hook.sh

# Path activation. LD_LIBRARY_PATH is required because conda-forge libstdc++
# is newer than what `debian:12-slim` ships, and the system loader otherwise
# wins for transitively loaded extensions (e.g. scipy's _distance_pybind.so).
ENV PATH=/app/.pixi/envs/cpu/bin:$PATH
ENV LD_LIBRARY_PATH=/app/.pixi/envs/cpu/lib

ENTRYPOINT ["/bin/bash", "/shell-hook.sh"]
CMD ["python", "/app/scripts/smoke.py"]
