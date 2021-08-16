from argparse import Namespace

import uvicorn
import yaml
from owl_server.config import config
from uvicorn.config import LOGGING_CONFIG


def run_api(args: Namespace) -> None:  # pragma: nocover
    """Start the API service.

    Parameters
    ----------
    arg
        Argparse namespace containing command line flags.
    """
    from owl_server.api import app
    from owl_server.log import logconf

    LOGGING_CONFIG.update(yaml.safe_load(logconf["api"]))
    api_port = int(config.env.OWL_API_SERVICE_PORT)

    uvicorn.run(app, host="0.0.0.0", port=api_port)
