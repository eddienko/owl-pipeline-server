#!/bin/bash

if [[ ! -z "${RUN_DEVELOP:-}" ]]; then
    pip install git+https://github.com/eddienko/owl-pipeline-server.git
else
    pip install owl-pipeline-server==new_version
fi

if [[ ! -z "${EXTRA_PIP_PACKAGES:-}" ]]; then
    echo "EXTRA_PIP_PACKAGES environment variable found. Installing".
    /opt/conda/bin/pip install $EXTRA_PIP_PACKAGES
fi

exec "$@"
