# ---------------------------------------------------------------------------
# Montreal Housing Intelligence -- runner image (milestone J4.3)
#
# This image carries the interpreter and the dependencies, and NOTHING ELSE.
# The project code is not copied in: it is bind-mounted read-only at run time
# (see the `runner` service in docker-compose.yml).
#
# Why the code stays outside the image
# ------------------------------------
# * Whatever runs on the server can be identified with `git log` in
#   /opt/mhi/repo. With a COPY, you would have to open the image to find out
#   which commit is executing.
# * Fixing a bug is a deploy, not a rebuild. Rebuilding costs minutes on a
#   2-vCPU server shared with a production n8n stack; copying files costs
#   seconds.
# * The image only changes when requirements.lock.txt changes, which is rare.
# * Read-only means the pipeline cannot rewrite its own source. That is a
#   property, not a side effect.
#
# Pinned to the exact Python the project was developed and tested on
# (3.14.6, see requirements.txt). "3.14-slim" would drift to a different patch
# release on some future rebuild, and a portfolio repository that does not
# reproduce is not reproducible.
# ---------------------------------------------------------------------------
FROM python:3.14.6-slim

# --- Dependencies ----------------------------------------------------------
#
# Installed from the LOCK file, not from requirements.txt: the lock pins every
# transitive dependency too, which is what makes the server environment equal
# to the laptop one rather than merely similar.
#
# Copied on its own, before anything else, so that Docker can cache this layer.
# A code change then costs nothing to redeploy, because the code is not in the
# image at all.
COPY requirements.lock.txt /tmp/requirements.lock.txt
RUN pip install --no-cache-dir -r /tmp/requirements.lock.txt \
    && rm /tmp/requirements.lock.txt \
    && pip check

# --- Runtime environment ---------------------------------------------------
# Unbuffered output so a log line reaches n8n as it happens rather than when
# the process ends -- which is the difference between watching a pipeline and
# reading its autopsy. No .pyc files: the code directory is read-only anyway.
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1

# dbt reads its connection settings from dbt/profiles.yml, which holds no
# secret of its own: every credential arrives as an environment variable.
ENV DBT_PROFILES_DIR=/app/dbt

# dbt insists on writing target/ and logs/. The repository is mounted
# read-only, so both are redirected to a writable volume. Verified against
# dbt 1.12.3 on 2026-09-13: `dbt run --help` documents DBT_TARGET_PATH and
# DBT_LOG_PATH.
ENV DBT_TARGET_PATH=/artifacts/target
ENV DBT_LOG_PATH=/artifacts/logs

# --- A user that is not root ----------------------------------------------
#
# Fixed UID/GID rather than "whatever adduser picks": the writable directories
# live on the host and are chowned to this exact number by the deploy script.
# A name means nothing across the container boundary; a number does.
RUN groupadd --gid 10001 mhi \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin mhi

WORKDIR /app
USER 10001:10001

# No CMD on purpose. This image is never "started": every use is an explicit
#   docker compose run --rm runner <command>
# and leaving CMD empty means a mistyped invocation fails instead of silently
# running something nobody asked for.
