import asyncio
import functools
import json
import os
from contextlib import suppress
from datetime import datetime
from typing import Any, Dict, Optional

import databases
import zmq
import zmq.asyncio
from fastapi import FastAPI, Header, HTTPException, status
from owl_server.config import config
from pydantic import BaseModel

from .. import database as db
from ..crypto import PBKDF2PasswordHasher, get_random_string

OWL_USERNAME = "owl"

database = databases.Database(config.dbi)


def authenticate(admin=False):
    def wrapper(func):
        @functools.wraps(func)
        async def wrapped(*args, **kwargs):
            auth = kwargs["authentication"]
            auth += " dummy dummy"
            username, token, *_ = auth.split()
            await check_token(username, token)
            if admin:
                await check_admin(username)
            kwargs["username"] = username
            return await func(*args, **kwargs)

        return wrapped

    return wrapper


async def check_token(username, token) -> bool:
    q = db.Token.select().where(db.Token.c.username == username)
    res = await database.fetch_one(q)
    if (not res) or (res["token"] != token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized",
        )


async def check_password(user) -> bool:
    q = db.User.select().where(db.User.c.username == user.username)
    res = await database.fetch_one(q)
    if not res:
        return False
    hasher = PBKDF2PasswordHasher()
    return hasher.verify(user.password, res["password"])


async def check_admin(username) -> bool:
    q = db.User.select().where(db.User.c.username == username)
    res = await database.fetch_one(q)
    if (not res) or (res["is_admin"] is False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized",
        )


async def check_config(config):
    await asyncio.sleep(0)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Empty config",
        )
    return config


async def check_status(st):
    await asyncio.sleep(0)
    if st not in [
        "ALL",
        "PENDING",
        "STARTING",
        "RUNNING",
        "FINISHED",
        "ERROR",
        "TO_CANCEL",
        "CANCELLED",
    ]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid status",
        )
    return st


def AdminSocket():
    host = os.environ.get("OWL_SCHEDULER_SERVICE_HOST")
    port = os.environ.get("OWL_SCHEDULER_SERVICE_PORT_ADMIN")
    admin_addr = f"tcp://{host}:{port}"
    ctx = zmq.asyncio.Context()
    admin_socket = ctx.socket(zmq.DEALER)
    admin_socket.setsockopt(zmq.IDENTITY, config.token.encode("utf-8"))
    admin_socket.connect(admin_addr)
    return admin_socket


app = FastAPI()

admin_socket = AdminSocket()


@app.on_event("startup")
async def startup():
    await database.connect()
    token = config.token
    try:
        q = db.Token.insert().values(username=OWL_USERNAME, token=token)
        await database.execute(q)
    except Exception:
        q = (
            db.Token.update()
            .where(db.Token.c.username == OWL_USERNAME)
            .values(token=token)
        )
        await database.execute(q)


@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()


class User(BaseModel):
    username: str
    password: Optional[str] = None
    is_admin: Optional[bool] = False
    active: Optional[bool] = True


class Pipeline(BaseModel):
    config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class PipeDef(BaseModel):
    name: str
    pdef: str
    extra_pip_packages: str
    active: Optional[bool] = True


class AdminCommand(BaseModel):
    cmd: Dict[str, Any]


@app.get("/api/pipeline/list/{status}")
@authenticate()
async def pipeline_list(
    status: str, listall: bool = False, authentication=Header(None), username=None
):
    st = await check_status(status.upper())
    q = db.Pipeline.select()
    if st not in ["ALL"]:
        q = q.where(db.Pipeline.c.status == st)
    if username not in [OWL_USERNAME]:
        if listall:
            try:
                await check_admin(username)
            except HTTPException:
                q = q.where(db.Pipeline.c.user == username)
        else:
            q = q.where(db.Pipeline.c.user == username)
    q = q.order_by(db.Pipeline.c.id.desc())
    res = await database.fetch_all(q)
    return res


@app.get("/api/pipeline/status/{uid}")
@authenticate()
async def pipeline_status_get(uid: int, authentication=Header(None), username=None):
    q = db.Pipeline.select().where(db.Pipeline.c.id == uid)
    res = await database.fetch_one(q)
    return res


@app.get("/api/pipeline/log/{uid}")
@authenticate()
async def pipeline_log(uid: int, authentication=Header(None), username=None):
    # TODO: check that pipeline user == username
    await asyncio.sleep(0)
    log = ""
    with suppress(Exception):
        log = open(f"/var/run/owl/logs/pipeline_{uid}.log").read()
    return {"log": log}


@app.post("/api/pipeline/add")
@authenticate()
async def pipeline_add(pipe: Pipeline, authentication=Header(None), username=None):
    config = await check_config(pipe.config)
    q = db.Pipeline.insert().values(
        user=username, config=config, created_at=datetime.now(), status="PENDING"
    )
    uid = await database.execute(q)
    return {"id": uid}


@app.post("/api/pipeline/cancel/{uid}")
@authenticate()
async def pipeline_cancel(uid: int, authentication=Header(None), username=None):
    q = db.Pipeline.select().where(db.Pipeline.c.id == uid)
    res = await database.fetch_one(q)
    if res["user"] != username:
        q = db.User.select().where(db.User.c.username == username)
        res = await database.fetch_one(q)
        if not res["is_admin"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized",
            )
    q = db.Pipeline.update().where(db.Pipeline.c.id == uid).values(status="TO_CANCEL")
    await database.execute(q)
    return {"id": uid, "status": "TO_CANCEL"}


@app.post("/api/pipeline/update/{uid}")
@authenticate()
async def pipeline_update(
    uid: int, pipe: Pipeline, authentication=Header(None), username=None
):
    new = await check_status(pipe.status.upper())
    q = db.Pipeline.select().where(db.Pipeline.c.id == uid)
    res = await database.fetch_one(q)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Pipeline {uid} not found",
        )
    if username not in [OWL_USERNAME, res["user"]]:
        await check_admin(username)
    update = False
    if (res["status"] in ["TO_CANCEL"]) and (new == "CANCELLED"):
        update = True
    elif res["status"] not in ["TO_CANCEL"]:
        update = True
    if update:
        q = db.Pipeline.update().where(db.Pipeline.c.id == uid).values(status=new)
        await database.execute(q)

    return {"id": uid, "status": new, "user": res["user"]}


@app.post("/api/admin/command")
@authenticate(admin=True)
async def admin_command(
    command: AdminCommand, authentication=Header(None), username=None
):
    msg = json.dumps(command.cmd).encode("utf-8")
    await admin_socket.send(msg)
    return {"status": "message sent"}


@app.post("/api/auth/login")
async def login(user: User):
    res = await check_password(user)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    token = get_random_string(64)
    try:
        q = db.Token.insert().values(username=user.username, token=token)
        await database.execute(q)
    except Exception:
        q = (
            db.Token.update()
            .where(db.Token.c.username == user.username)
            .values(token=token)
        )
        await database.execute(q)
    return {"token": token}


@app.post("/api/auth/logout")
@authenticate()
async def logout(user: User, authentication=Header(None), username=None):
    q = db.Token.delete().where(db.Token.c.username == username)
    with suppress(Exception):
        await database.execute(q)
    return {"user": user.username}


@app.post("/api/auth/user/add")
@authenticate(admin=True)
async def add_user(user: User, authentication=Header(None), username=None):
    hasher = PBKDF2PasswordHasher()
    salt = hasher.salt()
    password = hasher.encode(user.password, salt)
    try:
        q = db.User.insert().values(
            username=user.username,
            password=password,
            is_admin=user.is_admin,
            active=user.active,
        )
        await database.execute(q)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_208_ALREADY_REPORTED, detail="User already exists",
        )
    return {"user": user.username}


@app.post("/api/auth/user/update")
@authenticate(admin=True)
async def update_user(user: User, authentication=Header(None), username=None):
    data = {"is_admin": user.is_admin, "active": user.active}
    if user.password:
        hasher = PBKDF2PasswordHasher()
        salt = hasher.salt()
        password = hasher.encode(user.password, salt)
        data.update({"password": password})

    q = db.User.update().where(db.User.c.username == user.username).values(**data)
    await database.execute(q)

    if "password" in data:
        q = db.Token.delete(db.Token.c.username == user.username)
        await database.execute(q)

    return {"user": user.username}


@app.post("/api/auth/change_password")
@authenticate()
async def change_password(user: User, authentication=Header(None), username=None):
    if not user.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Password not supplied",
        )

    hasher = PBKDF2PasswordHasher()
    salt = hasher.salt()
    password = hasher.encode(user.password, salt)
    data = {"password": password}

    q = db.User.update().where(db.User.c.username == username).values(**data)
    await database.execute(q)

    q = db.Token.delete(db.Token.c.username == username)
    await database.execute(q)

    return {"user": user.username}


@app.get("/api/auth/user/get/{user}")
@authenticate(admin=True)
async def get_user(user: str, authentication=Header(None), username=None):
    q = db.User.select()
    if user != "0":
        q = q.where(db.User.c.username == user)
    else:
        q = q.order_by(db.User.c.id)
    res = await database.fetch_all(q)
    # remove password
    resd = [dict(r) for r in res]
    [r.pop("password", None) for r in resd]
    return resd


@app.post("/api/auth/user/delete")
@authenticate(admin=True)
async def delete_user(user: User, authentication=Header(None), username=None):
    q = db.User.delete().where(db.User.c.username == user.username)
    await database.execute(q)

    q = db.Token.delete(db.Token.c.username == user.username)
    await database.execute(q)

    return {"user": user.username}


@app.post("/api/pdef/add")
@authenticate(admin=True)
async def add_pdef(pdef: PipeDef, authentication=Header(None), username=None):
    try:
        q = db.PipelineDefinition.insert().values(
            name=pdef.name,
            pdef=pdef.pdef,
            extra_pip_packages=pdef.extra_pip_packages,
            active=pdef.active,
        )
        await database.execute(q)
        action = "created"
    except Exception:
        q = (
            db.PipelineDefinition.update()
            .where(db.PipelineDefinition.c.name == pdef.name)
            .values(
                pdef=pdef.pdef,
                extra_pip_packages=pdef.extra_pip_packages,
                active=pdef.active,
            )
        )
        await database.execute(q)
        action = "updated"
    return {"name": pdef.name, "action": action}


@app.get("/api/pdef/list")
@authenticate()
async def list_pdef(authentication=Header(None), username=None):
    q = db.PipelineDefinition.select().order_by(db.PipelineDefinition.c.id)
    res = await database.fetch_all(q)
    return res


@app.get("/api/pdef/get/{name}")
@authenticate()
async def get_pdef(name: str, authentication=Header(None), username=None):
    q = db.PipelineDefinition.select().where(db.PipelineDefinition.c.name == name)
    res = await database.fetch_one(q)
    return res


@app.get("/")
def read_root():
    return {"Hello": "World"}
