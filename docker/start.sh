#!/bin/bash

#if [[ ! -z "${CMD_INIT:-}" ]]; then
#    echo "CMD_INIT environment variable found. Running".
#    ${CMD_INIT}
#fi

exec "$@"