#!/usr/bin/env python3

import argparse

from redis import Redis

from alert_autoconf import defaults


def parse_params() -> dict:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "-c", "--config", help="Path to default config", required=False
    )
    parser.add_argument(
        "-s", "--redis_token_storage", help="Token storage.", required=True
    )

    namespace = parser.parse_args()
    command_line_args = {k: v for k, v in vars(namespace).items() if v}
    return command_line_args


def main():
    params = parse_params()
    redis = Redis.from_url(params["redis_token_storage"])
    with open(params["config"]) as f:
        redis.set(
            defaults.DEFAULT_TRIGGER_KEY,
            f.read(),
        )


if __name__ == "__main__":
    main()
