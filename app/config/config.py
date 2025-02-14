# app/config.py
import json
import logging
import os

import botocore.session
from aws_secretsmanager_caching import SecretCache, SecretCacheConfig
from dotenv import load_dotenv

from utils.logging import setup_logging
from utils.slack_alert import init_slack

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


def load_from_aws(name):
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
                "username": os.getenv("DB_USERNAME"),
                "password": os.getenv("DB_PASSWORD"),
                "host": os.getenv("DB_HOST"),
                "port": os.getenv("DB_PORT"),
                "dbname": os.getenv("DB_NAME"),
            }
        # validate the db config
        if "host" not in self.db:
            raise ValueError("db config is not set")
        # ==== this part can be load from env or aws secrets manager
        self.db["auto_migrate"] = self.load("DB_AUTO_MIGRATE", "true") == "true"
        self.debug = self.load("DEBUG") == "true"
        self.debug_resp = (
            self.load("DEBUG_RESP", "false") == "true"
        )  # Agent response with thought steps and time cost
        self.debug_checkpoint = (
            self.load("DEBUG_CHECKPOINT", "false") == "true"
        )  # log with checkpoint
        # Internal
        self.internal_base_url = self.load("INTERNAL_BASE_URL", "http://intent-api")
        # Admin
        self.admin_auth_enabled = self.load("ADMIN_AUTH_ENABLED", "false") == "true"
        self.admin_jwt_secret = self.load("ADMIN_JWT_SECRET")
        # API
        self.api_auth_enabled = self.load("API_AUTH_ENABLED", "false") == "true"
        self.api_jwt_secret = self.load("API_JWT_SECRET")
        # CDP
        self.cdp_api_key_name = self.load("CDP_API_KEY_NAME")
        self.cdp_api_key_private_key = self.load("CDP_API_KEY_PRIVATE_KEY")
        # Crossmint
        self.crossmint_api_key = self.load("CROSSMINT_API_KEY")
        # AI
        self.openai_api_key = self.load("OPENAI_API_KEY")
        self.deepseek_api_key = self.load("DEEPSEEK_API_KEY")
        self.system_prompt = self.load("SYSTEM_PROMPT")
        # Autonomous
        # self.autonomous_entrypoint_interval = int(
        #     self.load("AUTONOMOUS_ENTRYPOINT_INTERVAL", "1")
        # )
        self.autonomous_memory_public = self.load("AUTONOMOUS_MEMORY_PUBLIC", "true")
        # Telegram server settings
        self.tg_base_url = self.load("TG_BASE_URL")
        self.tg_server_host = self.load("TG_SERVER_HOST", "127.0.0.1")
        self.tg_server_port = self.load("TG_SERVER_PORT", "8081")
        self.tg_new_agent_poll_interval = self.load("TG_NEW_AGENT_POLL_INTERVAL", "60")
        # Twitter
        self.twitter_oauth2_client_id = self.load("TWITTER_OAUTH2_CLIENT_ID")
        self.twitter_oauth2_client_secret = self.load("TWITTER_OAUTH2_CLIENT_SECRET")
        self.twitter_oauth2_redirect_uri = self.load("TWITTER_OAUTH2_REDIRECT_URI")
        self.twitter_entrypoint_interval = int(
            self.load("TWITTER_ENTRYPOINT_INTERVAL", "15")
        )  # in minutes
        # Slack Alert
        self.slack_alert_token = self.load(
            "SLACK_ALERT_TOKEN"
        )  # For alert purposes only
        self.slack_alert_channel = self.load("SLACK_ALERT_CHANNEL")
        # Sentry
        self.sentry_dsn = self.load("SENTRY_DSN")
        self.sentry_traces_sample_rate = float(
            self.load("SENTRY_TRACES_SAMPLE_RATE", "0.01")
        )
        self.sentry_profiles_sample_rate = float(
            self.load("SENTRY_PROFILES_SAMPLE_RATE", "0.01")
        )
        # RPC
        self.rpc_base_mainnet = self.load(
            "RPC_BASE_MAINNET", "https://mainnet.base.org"
        )
        # ===== config loaded
        # Now we know the env, set up logging
        setup_logging(self.env, self.debug)
        logger.info("config loaded")
        # If the slack alert token exists, init it
        if self.slack_alert_token and self.slack_alert_channel:
            init_slack(self.slack_alert_token, self.slack_alert_channel)

    def load(self, key, default=None):
        """Load a secret from the secrets map or env"""
        return self.secrets.get(key, os.getenv(key, default))


config: Config = Config()
