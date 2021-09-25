#!/usr/bin/with-contenv bash

if [[ ! -z "${EXTRA_CONDA_PACKAGES:-}" ]]; then
    echo "EXTRA_CONDA_PACKAGES environment variable found. Installing".
    conda install $EXTRA_CONDA_PACKAGES -c conda-forge -c defaults -c bioconda
fi

