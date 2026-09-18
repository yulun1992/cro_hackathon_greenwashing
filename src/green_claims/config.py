"""Configuration stores secret names; credentials are read only for live requests."""
import os
from dataclasses import dataclass
from green_claims.generation.client import ChatCompletionsClient

@dataclass(frozen=True)
class Settings:
    api_url: str = ""
    model: str = ""
    secret_scope: str = ""
    secret_key: str = ""
    auth_type: str = "api-key"
    language: str = "English"

    @classmethod
    def from_env(cls):
        return cls(api_url=os.getenv("AZURE_OPENAI_CHAT_URL", ""),
                   model=os.getenv("AZURE_OPENAI_DEPLOYMENT", ""),
                   secret_scope=os.getenv("DATABRICKS_SECRET_SCOPE", ""),
                   secret_key=os.getenv("DATABRICKS_SECRET_KEY", ""),
                   auth_type=os.getenv("AZURE_OPENAI_AUTH_TYPE", "api-key"),
                   language=os.getenv("OUTPUT_LANGUAGE", "English"))

    def make_client(self, dbutils=None):
        if bool(self.secret_scope) != bool(self.secret_key):
            raise ValueError("Supply both secret scope and secret key name.")
        if self.secret_scope:
            if dbutils is None:
                raise ValueError("Databricks secrets require a Databricks session.")
            key = dbutils.secrets.get(scope=self.secret_scope, key=self.secret_key)
        else:
            key = os.getenv("AZURE_OPENAI_API_KEY", "")
        return ChatCompletionsClient(self.api_url, self.model, key, self.auth_type)
