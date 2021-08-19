import os
import sys
import threading
from collections.abc import Mapping

import yaml

from . import utils  # noqa: F401
from .schema import AttrDict, schema_server

paths = [
    os.getenv("OWL_ROOT_CONFIG", "/etc/owl"),
    os.path.join(sys.prefix, "etc", "owl"),
    os.path.join(os.path.expanduser("~"), ".config", "owl"),
    os.path.join(os.path.expanduser("~"), ".owl"),
]


if "OWL_CONFIG" in os.environ:
    PATH = os.environ["OWL_CONFIG"]
    paths.append(PATH)


global_config = config = AttrDict()

config_lock = threading.Lock()

defaults = []


def canonical_name(k, config):
    """Return the canonical name for a key.
    Handles user choice of '-' or '_' conventions by standardizing on whichever
    version was set first. If a key already exists in either hyphen or
    underscore form, the existing version is the canonical name. If neither
    version exists the original key is used as is.
    """
    try:
        if k in config:
            return k
    except TypeError:
        # config is not a mapping, return the same name as provided
        return k

    altk = k.replace("_", "-") if "_" in k else k.replace("-", "_")

    if altk in config:
        return altk

    return k


def update(old, new, priority="new"):
    """Update a nested dictionary with values from another
    This is like dict.update except that it smoothly merges nested values
    This operates in-place and modifies old

    Parameters
    ----------
    priority: string {'old', 'new'}
        If new (default) then the new dictionary has preference.
        Otherwise the old dictionary does.

    Examples
    --------
    >>> a = {'x': 1, 'y': {'a': 2}}
    >>> b = {'x': 2, 'y': {'b': 3}}
    >>> update(a, b)  # doctest: +SKIP
    {'x': 2, 'y': {'a': 2, 'b': 3}}
    >>> a = {'x': 1, 'y': {'a': 2}}
    >>> b = {'x': 2, 'y': {'b': 3}}
    >>> update(a, b, priority='old')  # doctest: +SKIP
    {'x': 1, 'y': {'a': 2, 'b': 3}}

    See Also
    --------
    dask.config.merge
    """
    for k, v in new.items():
        k = canonical_name(k, old)

        if isinstance(v, Mapping):
            if k not in old or old[k] is None:
                old[k] = AttrDict()
            update(old[k], v, priority=priority)
        elif priority == "new" or k not in old:
            old[k] = v

    return old


def merge(*dicts):
    """Update a sequence of nested dictionaries
    This prefers the values in the latter dictionaries to those in the former
    Examples
    --------
    >>> a = {'x': 1, 'y': {'a': 2}}
    >>> b = {'y': {'b': 3}}
    >>> merge(a, b)  # doctest: +SKIP
    {'x': 1, 'y': {'a': 2, 'b': 3}}
    See Also
    --------
    dask.config.update
    """
    result = {}
    for d in dicts:
        update(result, d)
    return result


def collect_yaml(paths=paths):
    """Collect configuration from yaml files
    This searches through a list of paths, expands to find all yaml or json
    files, and then parses each file.
    """
    # Find all paths
    file_paths = []
    for path in paths:
        if os.path.exists(path):
            if os.path.isdir(path):
                try:
                    file_paths.extend(
                        sorted(
                            [
                                os.path.join(path, p)
                                for p in os.listdir(path)
                                if os.path.splitext(p)[1].lower()
                                in (".json", ".yaml", ".yml")
                            ]
                        )
                    )
                except OSError:
                    # Ignore permission errors
                    pass
            else:
                file_paths.append(path)

    configs = []

    # Parse yaml files
    for path in file_paths:
        try:
            with open(path) as f:
                data = yaml.safe_load(f.read()) or {}
                configs.append(data)
        except OSError:
            # Ignore permission errors
            pass

    return configs


def collect(paths=paths, env=None):
    """
    Collect configuration from paths and environment variables
    Parameters
    ----------
    paths : List[str]
        A list of paths to search for yaml config files
    env : dict
        The system environment variables
    Returns
    -------
    config: dict
    See Also
    --------
    dask.config.refresh: collect configuration and update into primary config
    """
    if env is None:
        env = os.environ

    configs = collect_yaml(paths=paths)
    # configs.append(collect_env(env=env))

    return merge(*configs)


def refresh(config=config, defaults=defaults, **kwargs):
    """
    Update configuration by re-reading yaml files and env variables
    This mutates the global dask.config.config, or the config parameter if
    passed in.
    This goes through the following stages:
    1.  Clearing out all old configuration
    2.  Updating from the stored defaults from downstream libraries
        (see update_defaults)
    3.  Updating from yaml files and environment variables
    Note that some functionality only checks configuration once at startup and
    may not change behavior, even if configuration changes.  It is recommended
    to restart your python process if convenient to ensure that new
    configuration changes take place.
    See Also
    --------
    dask.config.collect: for parameters
    dask.config.update_defaults
    """
    config.clear()

    for d in defaults:
        update(config, d, priority="old")

    update(config, collect(**kwargs))


def update_defaults(new, config=config, defaults=defaults):
    """Add a new set of defaults to the configuration
    It does two things:
    1.  Add the defaults to a global collection to be used by refresh later
    2.  Updates the global config with the new configuration
        prioritizing older values over newer ones
    """
    defaults.append(new)
    update(config, new, priority="old")
    schema_server(config)


def _initialize():
    _defaults = {}

    update_defaults(_defaults)


refresh()
_initialize()
