import logging


def get_logger(name="wildlife"):
    return logging.getLogger(name)


def banner(title):
    get_logger().info("%s", title)
