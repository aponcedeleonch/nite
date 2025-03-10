# import copy
# import logging
# import logging.config
# import logging.handlers

# from nite.config import LOGGING_LEVEL

# config_dictionary = {
#     "version": 1,
#     "formatters": {
#         "process": {
#             "class": "logging.Formatter",
#             "format": "%(asctime)s %(processName)-12s %(levelname)-8s %(name)-15s: %(message)s",
#         }
#     },
#     "handlers": {
#         "console": {
#             "class": "logging.StreamHandler",
#             "level": LOGGING_LEVEL,
#             "formatter": "process",
#         }
#     },
#     "loggers": {
#         "nite": {"level": LOGGING_LEVEL, "handlers": ["console"], "propagate": False},
#         "uvicorn": {"level": LOGGING_LEVEL, "handlers": ["console"], "propagate": False},
#         "uvicorn.error": {"level": LOGGING_LEVEL, "handlers": ["console"], "propagate": False},
#     },
#     "root": {"level": LOGGING_LEVEL, "handlers": ["console"], "propagate": False},
# }


# def configure_module_logging(logger_name: str):
#     # Disable warnings. Librosa emits a lot of UserWarnings that are not relevant.
#     logger_config = copy.deepcopy(config_dictionary)
#     logging.config.dictConfig(logger_config)
#     logger = logging.getLogger(logger_name)
#     return logger


import logging
import structlog

from nite.config import LOGGING_LEVEL

timestamper = structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S")
shared_processors = [
    structlog.stdlib.add_log_level,
    timestamper,
]

structlog.configure(
    processors=shared_processors + [
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

formatter = structlog.stdlib.ProcessorFormatter(
    # These run ONLY on `logging` entries that do NOT originate within
    # structlog.
    foreign_pre_chain=shared_processors,
    # These run on ALL entries after the pre_chain is done.
    processors=[
        # Remove _record & _from_structlog.
        structlog.stdlib.ProcessorFormatter.remove_processors_meta,
        structlog.dev.ConsoleRenderer(),
    ],
)

def configure_nite_logging():
    handler = logging.StreamHandler()
    # Use OUR `ProcessorFormatter` to format all `logging` entries.
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(LOGGING_LEVEL)
