# syntax=docker/dockerfile:1

# ---- build: install locked dependencies and the package into a venv ----
FROM python:3.12.16-slim-trixie AS build

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /src
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-deps .

# ---- runtime: Python + Pango (WeasyPrint) + fonts, non-root ----
FROM python:3.12.16-slim-trixie

# Native libraries required by WeasyPrint (see its "First steps" docs) and the
# DejaVu fonts used by the report template.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin fechou

COPY --from=build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY examples ./examples
RUN mkdir -p data out && chown fechou:fechou data out

USER fechou

# Default: demo mode (fictitious data, no credentials, nothing sent).
ENTRYPOINT ["fechou"]
CMD ["demo"]
