FROM python:3.13-slim

# uv for dependency install; legalize-cli for statute lookup (called as a subprocess)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 PATH="/root/.local/bin:$PATH"

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY legal_verify ./legal_verify
COPY README.md ./
RUN uv sync --frozen --no-dev && uv tool install legalize-cli

ENV HOST=0.0.0.0 PORT=8000
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "legal-verify-web"]
