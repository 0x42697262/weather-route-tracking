"""Start the ASGI server with values from the validated environment."""

import uvicorn
from django.conf import settings

from core.constants import WEB_APPLICATION, WEB_BIND_HOST, WEB_PORT


def main() -> None:
    """Run uvicorn; forwarded headers are trusted only when `BEHIND_PROXY` is set."""
    app_env = settings.APP_ENV
    uvicorn.run(
        WEB_APPLICATION,
        host=WEB_BIND_HOST,
        port=WEB_PORT,
        workers=app_env.web_workers,
        proxy_headers=app_env.behind_proxy,
        forwarded_allow_ips="*",
        log_config=None,
        lifespan="off",
        server_header=False,
    )


if __name__ == "__main__":
    main()
