import ipaddress
import re
import socket

import voluptuous as vo


class AttrDict(dict):
    """Attribute dictionary.

    Allows to access dictionary items by attribute.

    Parameters
    ----------
    d : Dict[Any, Any]
        input dictionary

    Examples
    --------
    >>> d = {'a': 1, 'b': 2}
    >>> ad = AttrDict(d)
    >>> ad.a
    ... 1
    """

    def __getattr__(self, item):
        return self.get(item, None)

    def __getstate__(self):
        return self

    def __setstate__(self, state):
        self.update(state)


class AttrSchema(vo.Schema):
    """Attribute schema.

    Allows to access schema items by attribute.
    """

    def __call__(self, d):
        return AttrDict(super().__call__(d))


def IpAddress():
    def checker(address):
        try:
            ipaddress.ip_address(address)
        except ValueError:
            raise vo.Invalid(f"Invalid IP address: {address}")
        return address

    return checker


def Hostname():
    def checker(name):
        try:
            address = socket.gethostbyname(name)
        except ValueError:
            raise vo.Invalid(f"Invalid IP address: {name}")
        return address

    return checker


def Choice(kind, choices):
    def checker(value):
        if value not in choices:
            raise vo.Invalid(f"{value} not valid for {kind}")
        return value

    return checker


def DockerImage():
    def checker(value):
        m = re.compile(r"([a-z]+)/([a-z0-9-):([a-z0-9.]+)?").match(value)
        if m is None:
            raise vo.Invalid(f"Invalid Docker image: {value!r}")
        return value

    return checker


def _validate_scheduler(conf):
    return conf


schema_env = AttrSchema(
    {
        vo.Required("OWL_SCHEDULER_SERVICE_HOST"): vo.Any(
            vo.All(str, IpAddress()), vo.All(str, Hostname())
        ),
        vo.Required("OWL_SCHEDULER_SERVICE_PORT_PIPE"): vo.All(
            vo.Coerce(int), vo.Range(min=1000, max=9999)
        ),
        vo.Required("OWL_SCHEDULER_SERVICE_PORT_LOGS"): vo.All(
            vo.Coerce(int), vo.Range(min=1000, max=9999)
        ),
        vo.Required("OWL_SCHEDULER_SERVICE_PORT_ADMIN"): vo.All(
            vo.Coerce(int), vo.Range(min=1000, max=9999)
        ),
        vo.Required("OWL_API_SERVICE_HOST"): vo.Any(
            vo.All(str, IpAddress()), vo.All(str, Hostname())
        ),
        vo.Required("OWL_API_SERVICE_PORT"): vo.All(
            vo.Coerce(int), vo.Range(min=1000, max=9999)
        ),
        vo.Required("OWL_IMAGE_SPEC"): vo.All(str, vo.Length(min=6)),
    }
)

schema_server = AttrSchema(
    vo.All(
        {
            vo.Required("token"): vo.All(str, vo.Length(min=20)),
            vo.Required("loglevel"): vo.All(
                str, Choice("loglevel", ["DEBUG", "INFO", "WARNING", "ERROR"])
            ),
            vo.Required("heartbeat"): vo.All(vo.Coerce(int), vo.Range(min=10, max=100)),
            vo.Required("max_pipelines"): vo.All(
                vo.Coerce(int), vo.Range(min=1, max=100)
            ),
            vo.Required("dbi"): vo.All(str, vo.Length(min=6)),
            vo.Required("env"): schema_env,
        },
        _validate_scheduler,
    ),
    # extra=vo.REMOVE_EXTRA,
    extra=vo.ALLOW_EXTRA,
)

schema_resources = AttrSchema(
    {
        vo.Optional("workers", default=3): vo.All(int, vo.Range(min=1, max=100)),
        vo.Optional("memory", default=7): vo.All(int, vo.Range(min=1, max=100)),
        vo.Optional("threads", default=2): vo.All(int, vo.Range(min=1, max=100)),
        vo.Optional("processes", default=1): vo.All(int, vo.Range(min=1, max=100)),
        vo.Optional("image"): DockerImage(),
        vo.Optional("dynamic", default=False): bool,
        vo.Optional("workers_min", default=1): vo.All(int, vo.Range(min=1, max=100)),
    }
)

schema_pipeline = AttrSchema(
    {vo.Required("resources"): schema_resources}, extra=vo.ALLOW_EXTRA
)
