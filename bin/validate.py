#!/usr/bin/env python3

import argparse
import logging
import requests
import sys

from alert_autoconf.config import read_from_file
from json import JSONDecodeError

LOG_LEVEL = "DEBUG"


def parse_params() -> dict:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "-u",
        "--url",
        default="localhost",
        help="Graphite system render url",
        required=False,
    )
    parser.add_argument(
        "-c", "--config", help="Path to trigger description", required=True
    )
    parser.add_argument(
        "-l", "--log-level", default=LOG_LEVEL, help="Log level.", required=False
    )
    parser.add_argument(
        "-C", "--cluster",
        help="Cluster name. If specified, {cluster} will be replaced with this name.",
        required=False,
    )

    return parser.parse_args()


def main():
    frmt = "[%(asctime)s] %(levelname)s:%(name)s:%(funcName)s:%(message)s"
    logging.basicConfig(
        level=logging.getLevelName(LOG_LEVEL),
        stream=sys.stdout,
        format=frmt,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    _logger = logging.getLogger("validate")

    params = parse_params()
    log_level = params.log_level.upper()

    if LOG_LEVEL != log_level:
        logging.getLogger().setLevel(logging.getLevelName(log_level))
        _logger.setLevel(logging.getLevelName(log_level))

    is_valid = True
    data = read_from_file(params.config, params.cluster)

    for trigger in data.triggers:
        for n, target in enumerate(trigger.targets):
            request_params = {
                "format": "json",
                "target": target,
                "from": "-1min",
                "noNullPoints": "true",
                "maxDataPoints": 1,
            }
            try:
                r = requests.get(params.url, params=request_params)
                r.json()
                _logger.info('Trigger: "%s", target: "%s" OK' % (trigger.name, n))
            except JSONDecodeError as e:
                is_valid = False
                _logger.error(
                    'Trigger: "%s", target: "%s" ERROR: %s' % (trigger.name, n, r.text)
                )
            except Exception as e:
                is_valid = False
                _logger.error(
                    'Trigger: "%s", target: "%s", exception: "%s"'
                    % (trigger.name, n, e)
                )

    if not is_valid:
        sys.exit(1)


if __name__ == "__main__":
    main()
