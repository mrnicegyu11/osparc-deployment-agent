import trafaret as T

from .rest_config import schema as rest_schema

app_schema = T.Dict(
    {
        T.Key("host", default="0.0.0.0"): T.IP,
        "port": T.Int(),
        "log_level": T.Enum(
            "DEBUG", "WARNING", "INFO", "ERROR", "CRITICAL", "FATAL", "NOTSET"
        ),
        T.Key("deployed_version", optional=True, default=""): T.Or(
            T.Regexp(regexp=r"^[0-9]+[.][0-9]+[.][0-9]+$"), T.Null
        ),
        T.Key("stack_name", default="", optional=True): T.String(allow_blank=True),
        "watched_git_repositories": T.List(
            T.Dict(
                {
                    "id": T.String(),
                    "url": T.URL,
                    T.Key("username", optional=True, default=""): T.Or(
                        T.String(allow_blank=True), T.Null
                    ),
                    T.Key("password", optional=True, default=""): T.Or(
                        T.String(allow_blank=True), T.Null
                    ),
                    T.Key("branch", default="master", optional=True): T.String(
                        allow_blank=True
                    ),
                    T.Key("tags_regex", default="", optional=True): T.String(
                        allow_blank=True
                    ),
                    T.Key("branch_regex", default="", optional=True): T.String(
                        allow_blank=True
                    ),
                    T.Key("workdir", default="."): T.String(allow_blank=False),
                    T.Key("command", optional=False): T.List(
                        T.String(allow_blank=False), min_length=1
                    ),
                    T.Key("pull_only_files", default=False): T.Bool(),
                    T.Key("paths", default=[]): T.List(T.String()),
                }
            ),
            min_length=1,
        ),
        "docker_private_registries": T.List(
            T.Dict(
                {
                    "url": T.URL,
                    T.Key("username", optional=True, default=""): T.String(
                        allow_blank=True
                    ),
                    T.Key("password", optional=True, default=""): T.String(
                        allow_blank=True
                    ),
                }
            )
        ),
        "polling_interval": T.Int(gte=0),
        T.Key("notifications", optional=True, default=[]): T.List(
            T.Dict(
                {
                    "service": T.String,
                    "url": T.URL,
                    "enabled": T.Bool(),
                    "channel_id": T.String(),
                    "personal_token": T.String(),
                    "message": T.String(),
                    "header_unique_name": T.String(),
                }
            )
        ),
    }
)

schema = T.Dict(
    {"version": T.String(), T.Key("rest"): rest_schema, T.Key("main"): app_schema}
)

# TODO: config submodule that knows about schema with web.Application intpu parameters
# TODO: def get_main_config(app: ):
