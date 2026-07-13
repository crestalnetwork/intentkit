import json
import logging
import os
from decimal import Decimal, InvalidOperation
from typing import TypeAlias, TypedDict, overload

from dotenv import load_dotenv

from intentkit.utils.alert import init_alert
from intentkit.utils.alert_handler import setup_alert_handler
from intentkit.utils.chain import ChainProvider, QuicknodeChainProvider
from intentkit.utils.logging import setup_logging

SecretsMap: TypeAlias = dict[str, str | int]


class DatabaseConfig(TypedDict):
    host: str | None
    username: str | None
    password: str | None
    dbname: str | None
    port: str | None
    auto_migrate: bool
    pool_size: int


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
        self.env: str = os.getenv("ENV") or "local"
        self.release: str = os.getenv("RELEASE") or "local"
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
            self.db = {
                "host": str(secret_db.get("host")) if secret_db.get("host") else None,
                "username": str(secret_db.get("username"))
                if secret_db.get("username")
                else None,
                "password": str(secret_db.get("password"))
                if secret_db.get("password")
                else None,
                "dbname": str(secret_db.get("dbname"))
                if secret_db.get("dbname")
                else None,
                "port": str(secret_db.get("port", "5432")),
                "auto_migrate": self.load("DB_AUTO_MIGRATE", "true") == "true",
                "pool_size": self.load_int("DB_POOL_SIZE", 3),
            }
        else:
            self.db = {
                "username": self.load("DB_USERNAME", ""),
                "password": self.load("DB_PASSWORD", ""),
                "host": self.load("DB_HOST", ""),
                "port": self.load("DB_PORT", "5432"),
                "dbname": self.load("DB_NAME", ""),
                "auto_migrate": self.load("DB_AUTO_MIGRATE", "true") == "true",
                "pool_size": self.load_int("DB_POOL_SIZE", 3),
            }
        self.debug: bool = self.load("DEBUG") == "true"
        self.debug_checkpoint: bool = (
            self.load("DEBUG_CHECKPOINT", "false") == "true"
        )  # log with checkpoint
        # Redis
        self.redis_host: str = self.load("REDIS_HOST") or ""
        self.redis_port: int = self.load_int("REDIS_PORT", 6379)
        self.redis_db: int = self.load_int("REDIS_DB", 0)
        self.redis_password: str | None = self.load("REDIS_PASSWORD")
        self.redis_ssl: bool = self.load("REDIS_SSL", "false") == "true"
        if not self.redis_host:
            raise RuntimeError("REDIS_HOST is required for Redis")
        # AWS S3
        self.aws_s3_cdn_url: str | None = self.load("AWS_S3_CDN_URL")
        self.aws_s3_bucket: str | None = self.load("AWS_S3_BUCKET")
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
        self.hourly_budget: Decimal | None = self.load_decimal("HOURLY_BUDGET")
        # App (frontend) base URL
        self.app_base_url: str = self.load("APP_BASE_URL", "http://localhost:3000")
        # Optional CDN domain substituted for app_base_url in WeChat-bound links.
        self.wechat_base_url: str | None = self.load("WECHAT_BASE_URL")
        # CDP SDK Configuration
        self.cdp_api_key_id: str | None = self.load("CDP_API_KEY_ID")
        self.cdp_api_key_secret: str | None = self.load("CDP_API_KEY_SECRET")
        self.cdp_wallet_secret: str | None = self.load("CDP_WALLET_SECRET")
        # Supabase Auth
        self.supabase_jwt_signing_key: str | None = self.load(
            "SUPABASE_JWT_SIGNING_KEY"
        )
        self.supabase_jwks_url: str | None = self.load("SUPABASE_JWKS_URL")
        self.supabase_url: str | None = self.load("SUPABASE_URL")
        self.supabase_service_role_key: str | None = self.load(
            "SUPABASE_SERVICE_ROLE_KEY"
        )
        # Privy and Safe
        self.privy_app_id: str | None = self.load("PRIVY_APP_ID")
        self.privy_app_secret: str | None = self.load("PRIVY_APP_SECRET")
        self.privy_base_url: str = self.load(
            "PRIVY_BASE_URL", "https://api.privy.io/v1"
        )
        privy_auth_keys_raw = self.load("PRIVY_AUTHORIZATION_KEYS") or self.load(
            "PRIVY_AUTHORIZATION_KEY"
        )
        self.privy_authorization_private_keys: list[str] = (
            [k.strip() for k in privy_auth_keys_raw.split(",") if k.strip()]
            if privy_auth_keys_raw
            else []
        )
        self.safe_api_key: str | None = self.load("SAFE_API_KEY")
        # Master wallet for gas sponsorship (pays for Safe deployments)
        self.master_wallet_private_key: str | None = self.load(
            "MASTER_WALLET_PRIVATE_KEY"
        )
        # LLM providers
        self.openai_api_key: str | None = self.load("OPENAI_API_KEY")
        self.google_api_key: str | None = self.load("GOOGLE_API_KEY")
        self.google_genai_use_vertexai: bool = (
            self.load("GOOGLE_GENAI_USE_VERTEXAI", "false") == "true"
        )
        self.google_cloud_project: str | None = self.load("GOOGLE_CLOUD_PROJECT")
        self.deepseek_api_key: str | None = self.load("DEEPSEEK_API_KEY")
        self.xai_api_key: str | None = self.load("XAI_API_KEY")
        self.minimax_plan_api_key: str | None = self.load("MINIMAX_PLAN_API_KEY")
        self.minimax_plan_base_url: str = self.load(
            "MINIMAX_PLAN_BASE_URL", "https://api.minimax.io/anthropic"
        )
        self.mimo_plan_api_key: str | None = self.load("MIMO_PLAN_API_KEY")
        self.openrouter_api_key: str | None = self.load("OPENROUTER_API_KEY")
        # OpenAI Compatible provider
        self.openai_compatible_api_key: str | None = self.load(
            "OPENAI_COMPATIBLE_API_KEY"
        )
        self.openai_compatible_provider: str = self.load(
            "OPENAI_COMPATIBLE_PROVIDER", "OpenAI Compatible"
        )
        self.openai_compatible_base_url: str | None = self.load(
            "OPENAI_COMPATIBLE_BASE_URL"
        )
        self.openai_compatible_model: str | None = self.load("OPENAI_COMPATIBLE_MODEL")
        self.openai_compatible_model_lite: str | None = self.load(
            "OPENAI_COMPATIBLE_MODEL_LITE"
        )
        # Anthropic Compatible provider
        self.anthropic_compatible_api_key: str | None = self.load(
            "ANTHROPIC_COMPATIBLE_API_KEY"
        )
        self.anthropic_compatible_provider: str = self.load(
            "ANTHROPIC_COMPATIBLE_PROVIDER", "Anthropic Compatible"
        )
        self.anthropic_compatible_base_url: str | None = self.load(
            "ANTHROPIC_COMPATIBLE_BASE_URL"
        )
        self.anthropic_compatible_model: str | None = self.load(
            "ANTHROPIC_COMPATIBLE_MODEL"
        )
        self.anthropic_compatible_model_lite: str | None = self.load(
            "ANTHROPIC_COMPATIBLE_MODEL_LITE"
        )
        # LLM Config
        self.system_prompt: str | None = self.load("SYSTEM_PROMPT")
        self.intentkit_prompt: str | None = self.load("INTENTKIT_PROMPT")
        # XMTP
        self.xmtp_system_prompt: str | None = self.load(
            "XMTP_SYSTEM_PROMPT",
            "You are assisting a user who uses an XMTP client that only displays plain-text messages, so do not use Markdown formatting.",
        )
        # WeChat
        self.wechat_system_prompt: str | None = self.load("WECHAT_SYSTEM_PROMPT")
        # Telegram server settings
        self.tg_system_prompt: str | None = self.load("TG_SYSTEM_PROMPT")
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
        # Slack Alert
        self.slack_alert_token: str | None = self.load("SLACK_ALERT_TOKEN")
        self.slack_alert_channel: str | None = self.load("SLACK_ALERT_CHANNEL")
        # Telegram Alert
        self.tg_alert_bot_token: str | None = self.load("TG_ALERT_BOT_TOKEN")
        self.tg_alert_chat_id: str | None = self.load("TG_ALERT_CHAT_ID")
        # Tools - Platform Hosted Keys
        self.allora_api_key: str | None = self.load("ALLORA_API_KEY")
        self.carv_api_key: str | None = self.load("CARV_API_KEY")
        self.elfa_api_key: str | None = self.load("ELFA_API_KEY")
        self.heurist_api_key: str | None = self.load("HEURIST_API_KEY")
        self.enso_api_token: str | None = self.load("ENSO_API_TOKEN")
        self.dapplooker_api_key: str | None = self.load("DAPPLOOKER_API_KEY")
        self.moralis_api_key: str | None = self.load("MORALIS_API_KEY")
        self.tavily_api_key: str | None = self.load("TAVILY_API_KEY")
        self.jina_api_key: str | None = self.load("JINA_API_KEY")
        self.cookiefun_api_key: str | None = self.load("COOKIEFUN_API_KEY")
        self.firecrawl_api_key: str | None = self.load("FIRECRAWL_API_KEY")
        self.cryptopanic_api_key: str | None = self.load("CRYPTOPANIC_API_KEY")
        self.unrealspeech_api_key: str | None = self.load("UNREALSPEECH_API_KEY")
        self.dune_api_key: str | None = self.load("DUNE_API_KEY")
        self.aixbt_api_key: str | None = self.load("AIXBT_API_KEY")
        self.cryptocompare_api_key: str | None = self.load("CRYPTOCOMPARE_API_KEY")
        self.venice_api_key: str | None = self.load("VENICE_API_KEY")
        self.coingecko_api_key: str | None = self.load("COINGECKO_API_KEY")
        self.opensea_api_key: str | None = self.load("OPENSEA_API_KEY")
        # Cloudflare Browser Rendering
        self.cloudflare_account_id: str | None = self.load("CLOUDFLARE_ACCOUNT_ID")
        self.cloudflare_api_token: str | None = self.load("CLOUDFLARE_API_TOKEN")
        # Z.AI Plan API
        self.zai_plan_api_key: str | None = self.load("ZAI_PLAN_API_KEY")
        # Tracing backends (LangSmith / Langfuse). Only one runs at a time:
        # Langfuse takes precedence when its keys are present and LangSmith is
        # disabled, so a deployment can A/B the two by swapping env vars.
        # Values load through config first (env or AWS secrets, quotes stripped).
        self.langfuse_public_key: str | None = self.load("LANGFUSE_PUBLIC_KEY")
        self.langfuse_secret_key: str | None = self.load("LANGFUSE_SECRET_KEY")
        # LANGFUSE_BASE_URL is the canonical name in the SDK; LANGFUSE_HOST is
        # its legacy alias, kept as a fallback. Optional — defaults to cloud.
        self.langfuse_base_url: str | None = self.load(
            "LANGFUSE_BASE_URL"
        ) or self.load("LANGFUSE_HOST")
        self.langfuse_tracing: bool = bool(
            self.langfuse_public_key and self.langfuse_secret_key
        )
        # LangSmith reads its settings from env vars directly; load them and
        # write the sanitized values back for the SDK. Langfuse wins when both
        # are configured, so LangSmith is forced off in that case.
        self.langsmith_api_key: str | None = self.load("LANGSMITH_API_KEY")
        self.langsmith_project: str = self.load("LANGSMITH_PROJECT", "intentkit")
        self.langsmith_endpoint: str | None = self.load("LANGSMITH_ENDPOINT")
        self.langsmith_tracing: bool = (
            self.load("LANGSMITH_TRACING", "false") == "true"
            and not self.langfuse_tracing
        )
        self._export_langsmith_env()
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
        self.infura_api_key: str | None = self.load("INFURA_API_KEY")
        self.chain_provider: ChainProvider | None = None
        if self.quicknode_api_key:
            self.chain_provider = QuicknodeChainProvider(self.quicknode_api_key)
        elif self.infura_api_key and self.infura_api_key.strip():
            # Avoid circular import, import here
            from intentkit.utils.chain import InfuraChainProvider

            self.chain_provider = InfuraChainProvider(self.infura_api_key.strip())

        if self.chain_provider:
            self.chain_provider.init_chain_configs()

        # Agent Execution Limits
        self.recursion_limit: int = self.load_int("RECURSION_LIMIT", 100)
        self.super_recursion_limit: int = self.load_int("SUPER_RECURSION_LIMIT", 1000)

        # ===== config loaded
        # Now we know the env, set up logging
        setup_logging(self.env, self.debug, self.release)
        # Initialize unified alert system (Telegram > Slack > None) before
        # attaching the handler, so is_alert_enabled() reflects the real state.
        _ = init_alert(
            telegram_bot_token=self.tg_alert_bot_token,
            telegram_chat_id=self.tg_alert_chat_id,
            slack_token=self.slack_alert_token,
            slack_channel=self.slack_alert_channel,
        )
        # Set up alert handler for ERROR+ logs (only if alert is enabled)
        _ = setup_alert_handler(
            redis_host=self.redis_host,
            redis_port=self.redis_port,
            redis_db=self.redis_db,
            redis_password=self.redis_password,
            redis_ssl=self.redis_ssl,
            env=self.env,
            release=self.release,
        )
        # Attach Langfuse last, so its startup log uses the configured logging.
        self._setup_langfuse()

    def _setup_langfuse(self) -> None:
        """Attach Langfuse to every LangChain run when its keys are configured.

        Unlike LangSmith (env-var driven), Langfuse needs a callback handler;
        ``intentkit.config.tracing`` registers it through LangChain's global
        configure hook. Langfuse and LangSmith are mutually exclusive — see the
        tracing-backend block in ``__init__``.
        """
        if not self.langfuse_tracing:
            return
        if not (self.langfuse_public_key and self.langfuse_secret_key):
            return
        from intentkit.config.tracing import setup_langfuse

        _ = setup_langfuse(
            public_key=self.langfuse_public_key,
            secret_key=self.langfuse_secret_key,
            base_url=self.langfuse_base_url,
            environment=self.env,
            release=self.release,
        )

    def _export_langsmith_env(self) -> None:
        """Write sanitized LangSmith settings back to the env vars the SDK reads.

        Every tracing-flag spelling the SDK accepts is pinned, so a stray
        LANGCHAIN_* variable in the deployment cannot override the config
        value (LANGSMITH_TRACING_V2 has the highest precedence in the SDK).
        """
        api_key = self.langsmith_api_key
        enabled = self.langsmith_tracing and api_key is not None
        for var in (
            "LANGSMITH_TRACING",
            "LANGSMITH_TRACING_V2",
            "LANGCHAIN_TRACING",
            "LANGCHAIN_TRACING_V2",
        ):
            os.environ[var] = "true" if enabled else "false"
        if enabled and api_key is not None:
            os.environ["LANGSMITH_API_KEY"] = api_key
            os.environ["LANGSMITH_PROJECT"] = self.langsmith_project
            if self.langsmith_endpoint:
                os.environ["LANGSMITH_ENDPOINT"] = self.langsmith_endpoint
        # The SDK caches env reads (lru_cache); drop any values read before
        # this export so correctness doesn't depend on import order.
        try:
            from langsmith import utils as ls_utils

            ls_utils.get_env_var.cache_clear()  # pyright: ignore[reportFunctionMemberAccess]
            ls_utils.get_tracer_project.cache_clear()
        except (ImportError, AttributeError):
            pass

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
        # Strip one pair of matching surrounding quotes from either source
        # (process env or AWS secret) — docker `environment:` blocks and
        # pasted secret values carry quotes through literally.
        if (
            value
            and len(value) >= 2
            and value[0] == value[-1]
            and value[0] in ("'", '"')
        ):
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
            logger.warning(
                "Invalid integer value for %s, using default: %s", key, default
            )
            return default

    def load_float(self, key: str, default: float = 0.0) -> float:
        """Load a float value from env, handling empty strings gracefully"""
        value = self.load(key, str(default))
        if not value:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.warning(
                "Invalid float value for %s, using default: %s", key, default
            )
            return default

    def load_decimal(self, key: str, default: Decimal | None = None) -> Decimal | None:
        """Load a Decimal value from env, handling empty strings gracefully"""
        default_value = default if default is not None else None
        value = self.load(key, str(default)) if default is not None else self.load(key)
        if not value:
            return default_value
        try:
            return Decimal(value)
        except (InvalidOperation, ValueError, TypeError):
            logger.warning(
                f"Invalid decimal value for {key}, using default: {default_value}"
            )
            return default_value


config: Config = Config()

logger.info("config loaded")
