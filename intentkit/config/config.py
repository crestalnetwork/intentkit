# app/config.py
import json
import logging
import os

from dotenv import load_dotenv

from intentkit.utils.chain import ChainProvider, QuicknodeChainProvider
from intentkit.utils.logging import setup_logging
from intentkit.utils.s3 import init_s3
from intentkit.utils.slack_alert import init_slack

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


def load_from_aws(name):
    import botocore.session
    from aws_secretsmanager_caching import SecretCache, SecretCacheConfig

    client = botocore.session.get_session().create_client("secretsmanager")
    cache_config = SecretCacheConfig()
    cache = SecretCache(config=cache_config, client=client)
    secret = cache.get_secret_string(name)
    return json.loads(secret)


class Config:
    def __init__(self):
        # ==== this part can only be load from env
        self.env = os.getenv("ENV", "local")
        self.release = os.getenv("RELEASE", "local")
        secret_name = os.getenv("AWS_SECRET_NAME")
        db_secret_name = os.getenv("AWS_DB_SECRET_NAME")
        # ==== load from aws secrets manager
        if secret_name:
            self.secrets = load_from_aws(secret_name)
        else:
            self.secrets = {}
        if db_secret_name:
            self.db = load_from_aws(db_secret_name)
            # format the db config
            self.db["port"] = str(self.db["port"])
            # only keep the necessary fields
            self.db = {
                k: v
                for k, v in self.db.items()
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
        self.debug = self.load("DEBUG") == "true"
        self.debug_checkpoint = (
            self.load("DEBUG_CHECKPOINT", "false") == "true"
        )  # log with checkpoint
        # Redis
        self.redis_host = self.load("REDIS_HOST")
        self.redis_port = self.load_int("REDIS_PORT", 6379)
        self.redis_db = self.load_int("REDIS_DB", 0)
        # AWS
        self.aws_s3_bucket = self.load("AWS_S3_BUCKET")
        self.aws_s3_cdn_url = self.load("AWS_S3_CDN_URL")
        # Internal API
        self.internal_base_url = self.load("INTERNAL_BASE_URL", "http://intent-api")
        self.admin_auth_enabled = self.load("ADMIN_AUTH_ENABLED", "false") == "true"
        self.admin_jwt_secret = self.load("ADMIN_JWT_SECRET")
        self.debug_auth_enabled = self.load("DEBUG_AUTH_ENABLED", "false") == "true"
        self.debug_username = self.load("DEBUG_USERNAME")
        self.debug_password = self.load("DEBUG_PASSWORD")
        self.admin_llm_skill_control = (
            self.load("ADMIN_LLM_SKILL_CONTROL", "false") == "true"
        )
        # Payment
        self.payment_enabled = self.load("PAYMENT_ENABLED", "false") == "true"
        # Open API for agent
        self.open_api_base_url = self.load("OPEN_API_BASE_URL", "http://localhost:8000")
        # CDP - AgentKit 0.6.0 Configuration
        self.cdp_api_key_id = self.load("CDP_API_KEY_ID")
        self.cdp_api_key_secret = self.load("CDP_API_KEY_SECRET")
        self.cdp_wallet_secret = self.load("CDP_WALLET_SECRET")
        # LLM providers
        self.openai_api_key = self.load("OPENAI_API_KEY")
        self.deepseek_api_key = self.load("DEEPSEEK_API_KEY")
        self.xai_api_key = self.load("XAI_API_KEY")
        self.eternal_api_key = self.load("ETERNAL_API_KEY")
        self.reigent_api_key = self.load("REIGENT_API_KEY")
        self.venice_api_key = self.load("VENICE_API_KEY")
        # LLM Config
        self.system_prompt = self.load("SYSTEM_PROMPT")
        self.input_token_limit = self.load_int("INPUT_TOKEN_LIMIT", 60000)
        # XMTP
        self.xmtp_system_prompt = self.load(
            "XMTP_SYSTEM_PROMPT",
            "You are assisting a user who uses an XMTP client that only displays plain-text messages, so do not use Markdown formatting.",
        )
        # Telegram server settings
        self.tg_system_prompt = self.load("TG_SYSTEM_PROMPT")
        self.tg_base_url = self.load("TG_BASE_URL")
        self.tg_server_host = self.load("TG_SERVER_HOST", "127.0.0.1")
        self.tg_server_port = self.load("TG_SERVER_PORT", "8081")
        self.tg_new_agent_poll_interval = self.load("TG_NEW_AGENT_POLL_INTERVAL", "60")
        # Twitter
        self.twitter_oauth2_client_id = self.load("TWITTER_OAUTH2_CLIENT_ID")
        self.twitter_oauth2_client_secret = self.load("TWITTER_OAUTH2_CLIENT_SECRET")
        self.twitter_oauth2_redirect_uri = self.load("TWITTER_OAUTH2_REDIRECT_URI")
        self.twitter_entrypoint_interval = self.load_int(
            "TWITTER_ENTRYPOINT_INTERVAL", 5
        )  # in minutes
        # Slack Alert
        self.slack_alert_token = self.load("SLACK_ALERT_TOKEN")
        self.slack_alert_channel = self.load("SLACK_ALERT_CHANNEL")
        # Skills - Platform Hosted Keys
        self.acolyt_api_key = self.load("ACOLYT_API_KEY")
        self.allora_api_key = self.load("ALLORA_API_KEY")
        self.elfa_api_key = self.load("ELFA_API_KEY")
        self.heurist_api_key = self.load("HEURIST_API_KEY")
        self.enso_api_token = self.load("ENSO_API_TOKEN")
        self.dapplooker_api_key = self.load("DAPPLOOKER_API_KEY")
        self.moralis_api_key = self.load("MORALIS_API_KEY")
        self.tavily_api_key = self.load("TAVILY_API_KEY")
        self.cookiefun_api_key = self.load("COOKIEFUN_API_KEY")
        self.firecrawl_api_key = self.load("FIRECRAWL_API_KEY")
        # Sentry
        self.sentry_dsn = self.load("SENTRY_DSN")
        self.sentry_sample_rate = self.load_float("SENTRY_SAMPLE_RATE", 0.1)
        self.sentry_traces_sample_rate = self.load_float(
            "SENTRY_TRACES_SAMPLE_RATE", 0.01
        )
        self.sentry_profiles_sample_rate = self.load_float(
            "SENTRY_PROFILES_SAMPLE_RATE", 0.01
        )
        # RPC Providers
        self.quicknode_api_key = self.load("QUICKNODE_API_KEY")
        if self.quicknode_api_key:
            self.chain_provider: ChainProvider = QuicknodeChainProvider(
                self.quicknode_api_key
            )
        if hasattr(self, "chain_provider"):
            self.chain_provider.init_chain_configs()
        self.rpc_networks = self.load(
            "RPC_NETWORKS", "base-mainnet,base-sepolia,ethereum-sepolia,solana-mainnet"
        )

        # Nation
        self.nation_api_key = self.load("NATION_API_KEY")
        self.nation_api_url = self.load("NATION_API_URL", "")

        # ===== config loaded
        # Now we know the env, set up logging
        setup_logging(self.env, self.debug)
        logger.info("config loaded")

        # If the slack alert token exists, init it
        if self.slack_alert_token and self.slack_alert_channel:
            init_slack(self.slack_alert_token, self.slack_alert_channel)
        # If the AWS S3 bucket and CDN URL exist, init it
        if self.aws_s3_bucket and self.aws_s3_cdn_url:
            init_s3(self.aws_s3_bucket, self.aws_s3_cdn_url, self.env)

    def load(self, key, default=None):
        """Load a secret from the secrets map or env"""
        value = self.secrets.get(key, os.getenv(key, default))

        # If value is empty string, use default instead
        if value == "":
            value = default

        if value:
            value = value.replace("\\n", "\n")
        if value and value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        return value

    def load_int(self, key, default=0):
        """Load an integer value from env, handling empty strings gracefully"""
        value = self.load(key, str(default))
        if value is None or value == "":
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid integer value for {key}, using default: {default}")
            return default

    def load_float(self, key, default=0.0):
        """Load a float value from env, handling empty strings gracefully"""
        value = self.load(key, str(default))
        if value is None or value == "":
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid float value for {key}, using default: {default}")
            return default


config: Config = Config()
