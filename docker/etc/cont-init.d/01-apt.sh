#!/usr/bin/with-contenv bash

if [[ ! -z "${EXTRA_APT_PACKAGES:-}" ]]; then
    echo "EXTRA_APT_PACKAGES environment variable found. Installing".
    sudo apt update
    sudo apt install -yq --no-install-recommends $EXTRA_APT_PACKAGES
fi
