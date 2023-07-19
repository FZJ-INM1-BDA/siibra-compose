import logging
import os

logger = logging.getLogger(__name__.split(os.path.extsep)[0])

ch = logging.StreamHandler()
formatter = logging.Formatter("[{name}:{levelname}] {message}", style="{")
ch.setFormatter(formatter)

logger.addHandler(ch)
logger.setLevel(logging.INFO)