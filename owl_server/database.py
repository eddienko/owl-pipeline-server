import sqlalchemy

metadata = sqlalchemy.MetaData()

Pipeline = sqlalchemy.Table(
    "darkroom_owl_pipeline",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("config", sqlalchemy.JSON, nullable=False),
    sqlalchemy.Column("heartbeat", sqlalchemy.JSON, nullable=True),
    sqlalchemy.Column(
        "owner_id",
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey("auth_user.id"),
        nullable=False,
    ),
    sqlalchemy.Column(
        "pdef_id",
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey("darkroom_owl_pipedef.id"),
        nullable=False,
    ),
    sqlalchemy.Column(
        "status", sqlalchemy.String(length=16), default="PENDING", nullable=False
    ),
    sqlalchemy.Column("created_on", sqlalchemy.DateTime, nullable=False),
    sqlalchemy.Column("started_at", sqlalchemy.DateTime, nullable=True),
    sqlalchemy.Column("finished_at", sqlalchemy.DateTime, nullable=True),
    sqlalchemy.Column("elapsed", sqlalchemy.Float, nullable=True),
)

PipelineDefinition = sqlalchemy.Table(
    "darkroom_owl_pipedef",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("env", sqlalchemy.JSON, nullable=False),
    sqlalchemy.Column(
        "name", sqlalchemy.String(length=32), nullable=False, unique=True
    ),
    sqlalchemy.Column(
        "docker_image_id",
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey("darkroom_owl_dockerimage.id"),
        nullable=False,
    ),
    # sqlalchemy.Column("active", sqlalchemy.Boolean, default=True),
    sqlalchemy.Column("version", sqlalchemy.String(length=32), nullable=False),
)

ContainerImage = sqlalchemy.Table(
    "darkroom_owl_dockerimage",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("image", sqlalchemy.String(length=80), nullable=False),
    sqlalchemy.Column("tag", sqlalchemy.String(length=80), nullable=False),
    sqlalchemy.Column("image_spec", sqlalchemy.JSON, nullable=False),
)

Storage = sqlalchemy.Table(
    "darkroom_database_datastorage",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String(length=80), nullable=False),
    sqlalchemy.Column("spec", sqlalchemy.JSON, nullable=False),
    sqlalchemy.Column("mountPath", sqlalchemy.String(length=80), nullable=False),
)

PipelineLogs = sqlalchemy.Table(
    "darkroom_owl_pipelinelogs",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String(length=80)),
    sqlalchemy.Column("jobid_id", sqlalchemy.Integer, nullable=False, index=True),
    sqlalchemy.Column("level", sqlalchemy.String(length=16), nullable=False),
    sqlalchemy.Column("func_name", sqlalchemy.String(length=80)),
    sqlalchemy.Column("message", sqlalchemy.Text),
    sqlalchemy.Column("timestamp", sqlalchemy.DateTime, nullable=False),
)

# ContainerImage = sqlalchemy.Table(
#     "container_image",
#     metadata,
#     sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
#     sqlalchemy.Column("name", sqlalchemy.String(length=80), nullable=False),
#     sqlalchemy.Column("version", sqlalchemy.String(length=32), nullable=False),
#     sqlalchemy.Column("active", sqlalchemy.Boolean, default=True),
# )

Token = sqlalchemy.Table(
    "darkroom_owl_token",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column(
        "user_id",
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey("darkroom_core_user.id"),
        nullable=False,
        unique=True,
    ),
    sqlalchemy.Column("token", sqlalchemy.String(length=128)),
)

User = sqlalchemy.Table(
    "auth_user",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("username", sqlalchemy.String(length=32), unique=True),
    sqlalchemy.Column("password", sqlalchemy.String(length=32), unique=True),
)

UserOnly = sqlalchemy.Table(
    "auth_user",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("username", sqlalchemy.String(length=32), unique=True),
    extend_existing=True,
)
