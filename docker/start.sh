#!/bin/bash

#if [[ ! -z "${CMD_INIT:-}" ]]; then
#    echo "CMD_INIT environment variable found. Running".
#    ${CMD_INIT}
#fi


if [[ ! -z "${RUN_AS_ROOT:-}" ]]
then
  exec "$@"
else
  sudo -i -E -H -u user "$@"
fi
