# Tiny image with only what dossier rendering needs.
# It is run with --network none, so everything must be installed at build time.
FROM python:3.12-slim
RUN pip install --no-cache-dir matplotlib reportlab
# Matplotlib needs a writable config dir; the container runs as a non-root user.
ENV MPLCONFIGDIR=/tmp/mpl
RUN useradd --create-home runner
USER runner
WORKDIR /work
