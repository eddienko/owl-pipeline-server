import functools
import os
import subprocess
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

email_txt = """
Your pipeline with ID {jobid} has completed with status: {status}.

If the pipeline returns some result, please find it below.

{result}

You can obtain the full pipeline log output with the command

owl job logs {jobid}
"""

email_html = """<html><body>
<p>Your pipeline with ID {jobid} has completed with status: <b>{status}</b>.</p>

<p>If the pipeline returns some result, please find it below.</p>

<pre>
{result}
</pre>

<p>You can obtain the full pipeline log output with the command:</p>

<pre>
owl job logs {jobid}
</pre>
</body></html>
"""


def safe_loop():
    """Run coroutine in a safe loop.

    The coroutine runs in a 'while True' loop
    and exceptions logged.
    """

    def wrapper(func):
        @functools.wraps(func)
        async def wrapped(*args):
            logger = args[0].logger
            while True:
                try:
                    res = await func(*args)
                    if res is True:
                        break
                except Exception:
                    logger.error("Unkown exception", exc_info=True)

        return wrapped

    return wrapper


def slurm_envvars(*args, **kwargs):
    return {
        k: os.getenv(k)
        for k in [
            "POD_NAME",
            "POD_IP",
            "CONTAINER_CPU_REQUEST",
            "CONTAINER_MEMORY_LIMIT",
        ]
    }


def slurm_configure(info, **kwargs):
    new = []
    for line in open("/etc/slurm/slurm.conf").readlines():
        if line.startswith("ControlMachine="):
            new.append("ControlMachine={}\n".format(info["POD_NAME"]))
        elif line.startswith("ControlAddr="):
            new.append("ControlAddr={}\n".format(info["POD_IP"]))
        elif line.startswith("AccountingStorageHost="):
            new.append("AccountingStorageHost={}\n".format(info["POD_IP"]))
        elif line.startswith("NodeName="):
            for v in info["workers"].values():
                new.append(
                    "NodeName={} NodeAddr={} CPUs={} RealMemory={} State=UNKNOWN\n".format(
                        v["POD_NAME"],
                        v["POD_IP"],
                        v["CONTAINER_CPU_REQUEST"],
                        int(int(v["CONTAINER_MEMORY_LIMIT"]) * 1.048576),
                    )
                )
        else:
            new.append(line)
    with open("/etc/slurm/slurm.conf", "w") as fh:
        fh.write("".join(new))
    if os.getenv("POD_IP") == info["POD_IP"]:
        subprocess.run("sudo slurmctld".split())
    else:
        subprocess.run("sudo slurmd".split())


async def send_email(config, pipeline):
    if not config["enabled"]:
        return

    try:
        userinfo = pipeline["userinfo"]
        to_address = userinfo["email"]
    except Exception:
        return

    if not to_address:
        return

    jobid = pipeline["uid"]
    status = pipeline["status"]
    result = pipeline.get("heartbeat", {}).get("result", "")

    message = MIMEMultipart("alternative")
    message["From"] = config.get("from_address", "owl@localhost")
    message["To"] = to_address
    message["Subject"] = f"Pipeline {jobid}: {status}"
    message_txt = MIMEText(
        email_txt.format(jobid=jobid, status=status, result=result), "plain", "utf-8"
    )
    message_html = MIMEText(
        email_html.format(jobid=jobid, status=status, result=result), "html", "utf-8"
    )
    message.attach(message_txt)
    message.attach(message_html)

    await aiosmtplib.send(message, hostname=config["host"], port=config["port"])
