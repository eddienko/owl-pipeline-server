#!/usr/bin/with-contenv bash

if [[ ! -z "${RUN_DEVELOP:-}" ]]; then
    pip install git+https://github.com/eddienko/owl-pipeline-server.git@${RUN_DEVELOP} --user
else
    pip install owl-pipeline-server==0.8.3 --user
fi

