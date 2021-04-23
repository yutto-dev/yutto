import logging
import coloredlogs

logger = logging.getLogger()
coloredlogs.install(
    level='DEBUG',
    fmt='%(asctime)s %(levelname)s %(message)s',
    logger=logger,
    datefmt='%H:%M:%S'
)
