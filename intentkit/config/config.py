import json
import logging
import os
from typing import overload

from dotenv import load_dotenv

from intentkit.utils.chain import ChainProvider, QuicknodeChainProvider
from intentkit.utils.logging import setup_logging
from intentkit.utils.slack_alert import init_slack

SecretsMap = dict[str, str | int]
DatabaseConfig = dict[str, str | int | bool]

# Load environment variables from .env file
_ = load_dotenv()

logger = logging.getLogger(__name__)


def load_from_aws(name: str) -> SecretsMap:
    import botocore.session
    from aws_secretsmanager_caching import SecretCache, SecretCacheConfig

    client = botocore.session.get_session().create_client("secretsmanager")
    cache_config = SecretCacheConfig()
    cache = SecretCache(config=cache_config, client=client)
    secret = cache.get_secret_string(name)
    return json.loads(secret)


class Config:
    def __init__(self) -> None:
        # ==== this part can only be load from env
        self.env: str = os.getenv("ENV", "local")
        self.release: str = os.getenv("RELEASE", "local")
        secret_name: str | None = os.getenv("AWS_SECRET_NAME")
        db_secret_name: str | None = os.getenv("AWS_DB_SECRET_NAME")
        # ==== load from aws secrets manager
        self.secrets: SecretsMap = {}
        if secret_name:
            self.secrets = load_from_aws(secret_name)
        self.db: DatabaseConfig
        if db_secret_name:
            secret_db: SecretsMap = load_from_aws(db_secret_name)
            # format the db config
            secret_db["port"] = str(secret_db["port"])
            # only keep the necessary fields
            self.db = {
                k: v
                for k, v in secret_db.items()
                if k in ["username", "password", "host", "dbname", "port"]
            }
        else:
            self.db = {
                "username": self.load("DB_USERNAME", ""),
                "password": self.load("DB_PASSWORD", ""),
                "host": self.load("DB_HOST", ""),
                "port": self.load("DB_PORT", "5432"),
                "dbname": self.load("DB_NAME", ""),
            }
        # ==== this part can be load from env or aws secrets manager
        self.db["auto_migrate"] = self.load("DB_AUTO_MIGRATE", "true") == "true"
        self.db["pool_size"] = self.load_int("DB_POOL_SIZE", 3)
        self.debug: bool = self.load("DEBUG") == "true"
        self.debug_checkpoint: bool = (
            self.load("DEBUG_CHECKPOINT", "false") == "true"
        )  # log with checkpoint
        # Redis
        self.redis_host: str | None = self.load("REDIS_HOST")
        self.redis_port: int = self.load_int("REDIS_PORT", 6379)
        self.redis_db: int = self.load_int("REDIS_DB", 0)
        # AWS S3
        self.aws_s3_bucket: str | None = self.load("AWS_S3_BUCKET")
        self.aws_s3_cdn_url: str | None = self.load("AWS_S3_CDN_URL")
        # If using custom S3 endpoint
        self.aws_s3_endpoint_url: str | None = self.load("AWS_S3_ENDPOINT_URL")
        self.aws_s3_region_name: str | None = self.load("AWS_S3_REGION_NAME")
        self.aws_s3_access_key_id: str | None = self.load("AWS_S3_ACCESS_KEY_ID")
        self.aws_s3_secret_access_key: str | None = self.load(
            "AWS_S3_SECRET_ACCESS_KEY"
        )
        # Internal API
        self.internal_base_url: str = self.load(
            "INTERNAL_BASE_URL", "http://intent-api"
        )
        # Payment
        self.payment_enabled: bool = self.load("PAYMENT_ENABLED", "false") == "true"
        # Open API for agent
        self.open_api_base_url: str = self.load(
            "OPEN_API_BASE_URL", "http://localhost:8000"
        )
        # CDP - AgentKit 0.7.x Configuration
        self.cdp_api_key_id: str | None = self.load("CDP_API_KEY_ID")
        self.cdp_api_key_secret: str | None = self.load("CDP_API_KEY_SECRET")
        self.cdp_wallet_secret: str | None = self.load("CDP_WALLET_SECRET")
        # LLM providers
        self.openai_api_key: str | None = self.load("OPENAI_API_KEY")
        self.google_api_key: str | None = self.load("GOOGLE_API_KEY")
        self.deepseek_api_key: str | None = self.load("DEEPSEEK_API_KEY")
        self.xai_api_key: str | None = self.load("XAI_API_KEY")
        self.eternal_api_key: str | None = self.load("ETERNAL_API_KEY")
        self.reigent_api_key: str | None = self.load("REIGENT_API_KEY")
        self.venice_api_key: str | None = self.load("VENICE_API_KEY")
        self.openrouter_api_key: str | None = self.load("OPENROUTER_API_KEY")
        # LLM Config
        self.system_prompt: str | None = self.load("SYSTEM_PROMPT")
        self.intentkit_prompt: str | None = self.load("INTENTKIT_PROMPT")
        self.input_token_limit: int = self.load_int("INPUT_TOKEN_LIMIT", 60000)
        # XMTP
        self.xmtp_system_prompt: str | None = self.load(
            "XMTP_SYSTEM_PROMPT",
            "You are assisting a user who uses an XMTP client that only displays plain-text messages, so do not use Markdown formatting.",
        )
        # Telegram server settings
        self.tg_system_prompt: str | None = self.load("TG_SYSTEM_PROMPT")
        self.tg_base_url: str | None = self.load("TG_BASE_URL")
        self.tg_server_host: str = self.load("TG_SERVER_HOST", "127.0.0.1")
        self.tg_server_port: str = self.load("TG_SERVER_PORT", "8081")
        self.tg_new_agent_poll_interval: str = self.load(
            "TG_NEW_AGENT_POLL_INTERVAL", "60"
        )
        # Discord server settings
        self.discord_new_agent_poll_interval: str = self.load(
            "DISCORD_NEW_AGENT_POLL_INTERVAL", "30"
        )
        # Twitter
        self.twitter_oauth2_client_id: str | None = self.load(
            "TWITTER_OAUTH2_CLIENT_ID"
        )
        self.twitter_oauth2_client_secret: str | None = self.load(
            "TWITTER_OAUTH2_CLIENT_SECRET"
        )
        self.twitter_oauth2_redirect_uri: str | None = self.load(
            "TWITTER_OAUTH2_REDIRECT_URI"
        )
        self.twitter_entrypoint_interval: int = self.load_int(
            "TWITTER_ENTRYPOINT_INTERVAL", 5
        )  # in minutes
        # Slack Alert
        self.slack_alert_token: str | None = self.load("SLACK_ALERT_TOKEN")
        self.slack_alert_channel: str | None = self.load("SLACK_ALERT_CHANNEL")
        # Skills - Platform Hosted Keys
        self.acolyt_api_key: str | None = self.load("ACOLYT_API_KEY")
        self.allora_api_key: str | None = self.load("ALLORA_API_KEY")
        self.elfa_api_key: str | None = self.load("ELFA_API_KEY")
        self.heurist_api_key: str | None = self.load("HEURIST_API_KEY")
        self.enso_api_token: str | None = self.load("ENSO_API_TOKEN")
        self.dapplooker_api_key: str | None = self.load("DAPPLOOKER_API_KEY")
        self.moralis_api_key: str | None = self.load("MORALIS_API_KEY")
        self.tavily_api_key: str | None = self.load("TAVILY_API_KEY")
        self.cookiefun_api_key: str | None = self.load("COOKIEFUN_API_KEY")
        self.firecrawl_api_key: str | None = self.load("FIRECRAWL_API_KEY")
        # Sentry
        self.sentry_dsn: str | None = self.load("SENTRY_DSN")
        self.sentry_sample_rate: float = self.load_float("SENTRY_SAMPLE_RATE", 0.1)
        self.sentry_traces_sample_rate: float = self.load_float(
            "SENTRY_TRACES_SAMPLE_RATE", 0.01
        )
        self.sentry_profiles_sample_rate: float = self.load_float(
            "SENTRY_PROFILES_SAMPLE_RATE", 0.01
        )
        # RPC Providers
        self.quicknode_api_key: str | None = self.load("QUICKNODE_API_KEY")
        self.chain_provider: ChainProvider | None = None
        if self.quicknode_api_key:
            self.chain_provider = QuicknodeChainProvider(self.quicknode_api_key)
        if self.chain_provider:
            self.chain_provider.init_chain_configs()

        # Nation
        self.nation_api_key: str | None = self.load("NATION_API_KEY")
        self.nation_api_url: str = self.load("NATION_API_URL", "")

        # ===== config loaded
        # Now we know the env, set up logging
        setup_logging(self.env, self.debug)
        logger.info("config loaded")

        # If the slack alert token exists, init it
        if self.slack_alert_token and self.slack_alert_channel:
            init_slack(self.slack_alert_token, self.slack_alert_channel)

    @overload
    def load(self, key: str) -> str | None: ...  # noqa: F811

    @overload
    def load(self, key: str, default: str) -> str: ...  # noqa: F811

    def load(self, key: str, default: str | None = None) -> str | None:
        """Load a secret from the secrets map or env"""
        env_value = os.getenv(key, default)
        raw_value = self.secrets.get(key, env_value)
        if raw_value is None:
            value: str | None = default
        elif isinstance(raw_value, str):
            value = raw_value
        else:
            value = str(raw_value)

        # If value is empty string, use default instead
        if value == "":
            value = default

        if value:
            value = value.replace("\\n", "\n")
        if value and value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        return value

    def load_int(self, key: str, default: int = 0) -> int:
        """Load an integer value from env, handling empty strings gracefully"""
        value = self.load(key, str(default))
        if not value:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid integer value for {key}, using default: {default}")
            return default

    def load_float(self, key: str, default: float = 0.0) -> float:
        """Load a float value from env, handling empty strings gracefully"""
        value = self.load(key, str(default))
        if not value:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid float value for {key}, using default: {default}")
            return default


config: Config = Config()
