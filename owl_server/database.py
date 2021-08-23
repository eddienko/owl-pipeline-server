import sqlalchemy

metadata = sqlalchemy.MetaData()

Pipeline = sqlalchemy.Table(
    "pipeline",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("config", sqlalchemy.JSON, nullable=False),
    sqlalchemy.Column("heartbeat", sqlalchemy.JSON, nullable=True),
    sqlalchemy.Column("user", sqlalchemy.String(length=32), nullable=False),
    sqlalchemy.Column(
        "status", sqlalchemy.String(length=16), default="PENDING", nullable=False
    ),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, nullable=False),
    sqlalchemy.Column("started_at", sqlalchemy.DateTime, nullable=True),
    sqlalchemy.Column("finished_at", sqlalchemy.DateTime, nullable=True),
    sqlalchemy.Column("elapsed", sqlalchemy.Float, nullable=True),
)

PipelineDefinition = sqlalchemy.Table(
    "pipeline_definition",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("pdef", sqlalchemy.JSON, nullable=False),
    sqlalchemy.Column(
        "name", sqlalchemy.String(length=32), nullable=False, unique=True
    ),
    sqlalchemy.Column("extra_pip_packages", sqlalchemy.Text, nullable=False),
    sqlalchemy.Column("active", sqlalchemy.Boolean, default=True),
    # sqlalchemy.Column("version", sqlalchemy.String(length=32), nullable=False),
)

ContainerImage = sqlalchemy.Table(
    "container_image",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String(length=80), nullable=False),
    sqlalchemy.Column("version", sqlalchemy.String(length=32), nullable=False),
    sqlalchemy.Column("active", sqlalchemy.Boolean, default=True),
)

Token = sqlalchemy.Table(
    "token",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("username", sqlalchemy.String(length=32), unique=True),
    sqlalchemy.Column("token", sqlalchemy.String(length=128)),
)

User = sqlalchemy.Table(
    "owl_user",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("username", sqlalchemy.String(length=32), unique=True),
    sqlalchemy.Column("password", sqlalchemy.String(length=128)),
    sqlalchemy.Column("is_admin", sqlalchemy.Boolean, default=False),
    sqlalchemy.Column("active", sqlalchemy.Boolean, default=True),
)
