from enum import Enum

# ═══════════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════════


class SourceType(str, Enum):
    """
    Type of source entry in a subscription.
    CONFIG: Direct proxy configuration (vless://, vmess://, etc.)
    EXTERNAL_URL: HTTPS URL to third-party subscription provider
    INTERNAL_TOKEN: Token reference to another subscription (same user)
    """

    CONFIG = "config"
    EXTERNAL_URL = "external_url"
    INTERNAL_TOKEN = "internal_token"

    def __str__(self) -> str:
        return self.value
