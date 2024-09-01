import logging
import logging.config
import logging.handlers
import copy

from nite.config import LOGGING_LEVEL


config_dictionary = {
    'version': 1,
    'formatters': {
        'process': {
            'class': 'logging.Formatter',
            'format': '%(asctime)s %(processName)-12s %(levelname)-8s %(name)-15s: %(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': LOGGING_LEVEL,
            'formatter': 'process',
        }
    },
    'loggers': {
        'nite': {
            'level': LOGGING_LEVEL,
            'handlers': ['console'],
            'propagate': False
        }
    },
    'root': {
        'level': LOGGING_LEVEL,
        'handlers': ['console'],
        'propagate': False
    },
}


def configure_module_logging(logger_name: str):
    logger_config = copy.deepcopy(config_dictionary)
    logging.config.dictConfig(logger_config)
    logger = logging.getLogger(logger_name)
    return logger
