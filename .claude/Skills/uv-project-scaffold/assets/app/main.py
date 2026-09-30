"""Application entry point.

Run from the project root:
    uv run --env-file .env python -m app.main
"""

import os


def main() -> None:
    app_name = os.getenv("APP_NAME", "api")
    app_env = os.getenv("APP_ENV", "development")
    print(f"Hello, World! 👋 {app_name} is running in {app_env} mode.")


if __name__ == "__main__":
    main()
