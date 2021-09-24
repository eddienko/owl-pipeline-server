#!/bin/bash

#if [[ ! -z "${CMD_INIT:-}" ]]; then
#    echo "CMD_INIT environment variable found. Running".
#    ${CMD_INIT}
#fi

CMD=${@:-"/bin/bash"}

if [[ ! -z "${RUN_AS_ROOT:-}" ]]
then
  exec "$CMD"
else
  sudo -i -E -H -u user "$CMD"
fi
