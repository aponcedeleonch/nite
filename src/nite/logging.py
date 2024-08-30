import sys
import logging
import logging.config
import logging.handlers
from multiprocessing import Queue
import traceback
from dataclasses import dataclass
import copy


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
            'level': 'INFO',
            'formatter': 'process',
        }
    },
    'loggers': {
        'nite': {
            'level': 'INFO',
            'handlers': ['console'],
            'propagate': False
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console'],
        'propagate': False
    },
}


@dataclass
class LogggingProcessConfig:
    queue: Queue
    logger_name: str


def listener_logging_process(log_queue: Queue):
    while True:
        try:
            record = log_queue.get()
            if record is None:  # We send this as a sentinel to tell the listener to quit.
                break
            logger = logging.getLogger(record.name)
            logger.handle(record)
        except Exception:
            print('Problem in logging listener', file=sys.stderr)
            traceback.print_exc(file=sys.stderr)


def configure_process_logging(logging_config: LogggingProcessConfig):
    handler = logging.handlers.QueueHandler(logging_config.queue)
    logger = logging.getLogger(logging_config.logger_name)
    logger.addHandler(handler)
    return logger


def configure_module_logging(logger_name: str):
    logger_config = copy.deepcopy(config_dictionary)
    logging.config.dictConfig(logger_config)
    logger = logging.getLogger(logger_name)
    return logger
