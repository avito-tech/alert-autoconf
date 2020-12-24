#!/usr/bin/env python3

import os
import argparse
import logging
import pkg_resources

from collections import ChainMap

from redis import Redis

from alert_autoconf import LOG_FORMAT, LOG_LEVEL
from alert_autoconf import config
from alert_autoconf import defaults
from alert_autoconf import teamcity
from alert_autoconf.moira import MoiraAlert
from moira_client import Moira
from moira_client import RetryPolicy


def parse_params() -> dict:
    """
    Разбор параметров из командной строки
    :return: набор параметров
    """
    parser = argparse.ArgumentParser(add_help=True)
    defaults = {
        "url": "localhost",
        "config": "etc/example.yaml",
        "log_level": LOG_LEVEL,
        "user": None,
        "password": None,
        "token": None,
        "redis_token_storage": None,
    }

    parser.add_argument(
        "-c", "--config", help="Path to trigger description", required=False
    )
    parser.add_argument("-u", "--url", help="Alerting system api url", required=False)
    parser.add_argument("-l", "--log-level", help="Log level.", required=False)
    parser.add_argument("-U", "--user", help="User name.", required=False)
    parser.add_argument("-p", "--password", help="User password.", required=False)
    parser.add_argument("-t", "--token", help="Triggers token.", required=False)
    parser.add_argument(
        "-s", "--redis_token_storage", help="Token storage.", required=True
    )
    parser.add_argument(
        "-C", "--cluster",
        help="Cluster name. If specified, {cluster} will be replaced with this name.",
        required=False,
    )

    namespace = parser.parse_args()
    if namespace.token is None:
        if namespace.cluster is None:
            parser.error("At least one of -t/--token and -C/--cluster is required")
        namespace.token = "kubernetes:{}".format(namespace.cluster)
    command_line_args = {k: v for k, v in vars(namespace).items() if v}

    return ChainMap(command_line_args, os.environ, defaults)


def main():
    logging.basicConfig(level=logging.getLevelName(LOG_LEVEL), format=LOG_FORMAT)

    logger = logging.getLogger("alert")

    params = parse_params()

    log_level = params["log_level"].upper()
    if LOG_LEVEL != log_level:
        logger.setLevel(logging.getLevelName(log_level))

    # urllib3 logging is too verbose, set it at WARNING or more
    loglevel_as_int = logging._nameToLevel[log_level.upper()]
    # `loglevel_as_int` is 50 for CRITICAL, 10 for DEBUG
    logging.getLogger("urllib3").setLevel(max(logging.WARNING, loglevel_as_int))
    # after this line, the loglevel for urllib3 is CRITICAL, ERROR or WARNING

    if not params["url"].startswith("http://"):
        params["url"] = "{}{}".format("http://", params["url"])

    moira = Moira(
        params["url"],
        auth_user=params["user"],
        auth_pass=params["password"],
        auth_custom={
            "User-Agent": _make_user_agent(),
        },
        retry_policy=RetryPolicy(
            max_tries=3,
            delay=1,
            backoff=1.5,
        ),
    )

    redis = Redis.from_url(params["redis_token_storage"])

    alert = MoiraAlert(moira=moira, redis=redis, token=params["token"])

    data = config.read_from_file(params["config"], cluster_name=params.get("cluster"))
    defaults.apply_defaults(data, redis)

    alert.setup(data)


def _make_user_agent():
    distribution = pkg_resources.get_distribution("alert-autoconf")
    user_agent = f'{distribution.project_name}/{distribution.version}'
    teamcity_build_id = teamcity.get_teamcity_build_id()
    if teamcity_build_id is not None:
        user_agent = f'{user_agent} (TeamCity; https://tmct.yourdomain.ru/viewLog.html?buildId={teamcity_build_id})'
    return user_agent


if __name__ == "__main__":
    main()
