#!/bin/bash

#if [[ ! -z "${CMD_INIT:-}" ]]; then
#    echo "CMD_INIT environment variable found. Running".
#    ${CMD_INIT}
#fi

CMD=${@:-/bin/bash}

echo "#!/bin/bash -l" > "/tmp/run.sh"
echo "$CMD" >> "/tmp/run.sh"
chmod a+x /tmp/run.sh

if [[ ! -z "${RUN_AS_ROOT:-}" ]]
then
  exec "$CMD"
else
  sudo -E -H -u user "/tmp/run.sh"
fi
