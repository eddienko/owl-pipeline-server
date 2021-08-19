import json
import logging
import os
import re
import select
import sys
from collections import namedtuple
from typing import IO, Callable, Dict, Union

import yaml
from kubernetes import client

log = logging.getLogger("owl.cli")


SERIALIZATION_API_CLIENT = client.ApiClient()
SERIALIZATION_API_CLIENT.pool.close()

_path_matcher = re.compile(r"(\S+)?(\$\{([^}^{]+)\})")


def _path_constructor(loader, node):
    """Extract the matched value, expand env variable, and replace the match."""
    value = node.value
    match = _path_matcher.match(value)
    env_var = match.groups()[2]
    return value.replace(match.groups()[1], os.environ.get(env_var, ""))


yaml.add_implicit_resolver("!path", _path_matcher, None, yaml.SafeLoader)
yaml.add_constructor("!path", _path_constructor, yaml.SafeLoader)


def read_config(
    config: Union[str, IO[str]], validate: Callable = None
) -> Dict[str, str]:
    """Read configuration file.

    Parameters
    ----------
    config
        input configuration
    validate
        validation schema

    Returns
    -------
    parsed configuration
    """
    try:
        conf = yaml.safe_load(config)
    except:  # noqa
        log.critical("Unable to read configuration file.")
        raise
    if validate:
        conf = validate(conf)
    return conf


def read_config_stdin(*args):
    """Read config from stdin."""
    handler, *_ = select.select([sys.stdin], [], [], 1)
    if handler:
        config = yaml.safe_load(handler[0].readline())
    else:
        config = {}

    return config


_FakeResponse = namedtuple("_FakeResponse", ["data"])


def _make_spec_from_dict(_dict: Dict, kind=client.V1Pod):
    return SERIALIZATION_API_CLIENT.deserialize(
        _FakeResponse(data=json.dumps(_dict)), kind
    )
