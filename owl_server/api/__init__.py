import asyncio
import functools
import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional

import databases
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
    if (not res) or (res.token != token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized",
        )


async def check_password(user) -> bool:
    q = db.User.select().where(db.User.c.username == user.username)
    res = await database.fetch_one(q)
    if not res:
        return False
    hasher = PBKDF2PasswordHasher()
    return hasher.verify(user.password, res.password)


async def check_admin(username) -> bool:
    q = db.User.select().where(db.User.c.username == username)
    res = await database.fetch_one(q)
    if (not res) or (res.is_admin is False):
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


app = FastAPI()


@app.on_event("startup")
async def startup():
    await database.connect()
    token = config.token
    try:
        q = db.Token.insert().values(username=OWL_USERNAME, token=token)
        await database.execute(q)
    except sqlite3.IntegrityError:
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


class Pipeline(BaseModel):
    config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class PipeDef(BaseModel):
    name: str
    pdef: str
    extra_pip_packages: str


@app.get("/api/pipeline/list/{status}")
@authenticate()
async def pipeline_list(status: str, authentication=Header(None), username=None):
    st = await check_status(status.upper())
    q = db.Pipeline.select().where(db.Pipeline.c.status == st)
    res = await database.fetch_all(q)
    return res


@app.get("/api/pipeline/status/{uid}")
@authenticate()
async def pipeline_status_get(uid: int, authentication=Header(None), username=None):
    q = db.Pipeline.select().where(db.Pipeline.c.id == uid)
    res = await database.fetch_one(q)
    return res


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
    if res.user != username:
        q = db.User.select().where(db.User.c.username == username)
        res = await database.fetch_one(q)
        if not res.is_admin:
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
    if username not in [OWL_USERNAME, res.user]:
        await check_admin(username)
    if res.status not in ["TO_CANCEL"]:
        q = db.Pipeline.update().where(db.Pipeline.c.id == uid).values(status=new)
        await database.execute(q)

    return {"id": uid, "status": new, "user": res.user}


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
    except sqlite3.IntegrityError:
        q = (
            db.Token.update()
            .where(db.Token.c.username == user.username)
            .values(token=token)
        )
        await database.execute(q)
    return {"token": token}


@app.post("/api/auth/user/add")
@authenticate(admin=True)
async def add_user(user: User, authentication=Header(None), username=None):
    hasher = PBKDF2PasswordHasher()
    salt = hasher.salt()
    password = hasher.encode(user.password, salt)
    try:
        q = db.User.insert().values(
            username=user.username, password=password, is_admin=user.is_admin
        )
        await database.execute(q)
    except sqlite3.IntegrityError:
        q = (
            db.User.update()
            .where(db.User.c.username == user.username)
            .values(password=password, is_admin=user.is_admin)
        )
        await database.execute(q)

    return {"user": user.username}


@app.post("/api/auth/user/update")
@authenticate(admin=True)
async def update_user(user: User, authentication=Header(None), username=None):
    data = {"is_admin": user.is_admin}
    if user.password:
        hasher = PBKDF2PasswordHasher()
        salt = hasher.salt()
        password = hasher.encode(user.password, salt)
        data.update({"password": password})

    q = db.User.update().where(db.User.c.username == user.username).values(**data)
    await database.execute(q)

    q = db.Token.delete(db.Token.c.username == user.username)
    await database.execute(q)

    return {"user": user.username}


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
            name=pdef.name, pdef=pdef.pdef, extra_pip_packages=pdef.extra_pip_packages
        )
        await database.execute(q)
        action = "created"
    except sqlite3.IntegrityError:
        q = (
            db.PipelineDefinition.update()
            .where(db.PipelineDefinition.c.name == pdef.name)
            .values(pdef=pdef.pdef, extra_pip_packages=pdef.extra_pip_packages)
        )
        await database.execute(q)
        action = "updated"
    return {"name": pdef.name, "action": action}


@app.get("/api/pdef/list")
@authenticate()
async def list_pdef(authentication=Header(None), username=None):
    q = db.PipelineDefinition.select()
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
