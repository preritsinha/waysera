# Relay image.
#
# Built from web/backend as the context, so paths here are relative to that
# directory rather than the repository root.

FROM python:3.13-slim

# Bytecode files and stdout buffering both just get in the way in a container:
# the first bloats the image, the second hides logs when the process is killed.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first, so a code change does not invalidate the pip layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY services ./services

# Runs unprivileged. The relay needs no filesystem access beyond its own code.
RUN useradd --create-home --uid 10001 relay
USER relay

EXPOSE 8000

# One worker, deliberately. The channel registry is an in-memory
# dict[str, set[WebSocket]], so a second worker would hold a different set of
# sockets and two people in the same journey could land on different processes
# and never see each other. Scaling past one process needs a shared bus, not
# more workers.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
