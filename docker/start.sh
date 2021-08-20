#!/bin/bash

if [[ ! -z "${RUN_DEVELOP:-}" ]]; then
    pip install git+https://github.com/eddienko/owl-pipeline-server.git@devel
else
    pip install owl-pipeline-server==0.7.1
fi

if [[ ! -z "${EXTRA_PIP_PACKAGES:-}" ]]; then
    echo "EXTRA_PIP_PACKAGES environment variable found. Installing".
    /opt/conda/bin/pip install $EXTRA_PIP_PACKAGES
fi

exec "$@"
