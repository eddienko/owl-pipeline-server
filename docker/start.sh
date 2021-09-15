#!/bin/bash

if [[ ! -z "${RUN_DEVELOP:-}" ]]; then
    pip install git+https://github.com/eddienko/owl-pipeline-server.git@devel
else
    pip install owl-pipeline-server==0.8.3
fi

if [[ ! -z "${EXTRA_APT_PACKAGES:-}" ]]; then
    echo "EXTRA_APT_PACKAGES environment variable found. Installing".
    apt update
    apt install -yq --no-install-recommends $EXTRA_APT_PACKAGES
fi

if [[ ! -z "${EXTRA_CONDA_PACKAGES:-}" ]]; then
    echo "EXTRA_CONDA_PACKAGES environment variable found. Installing".
    /opt/conda/bin/conda install $EXTRA_CONDA_PACKAGES -c conda-forge -c default
fi

if [[ ! -z "${EXTRA_PIP_PACKAGES:-}" ]]; then
    echo "EXTRA_PIP_PACKAGES environment variable found. Installing".
    /opt/conda/bin/pip install $EXTRA_PIP_PACKAGES
fi

sudo -E --preserve-env=PATH -H -u user exec "$@"
