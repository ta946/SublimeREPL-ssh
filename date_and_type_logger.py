import logging
import logging.handlers
import os

__version__ = "1.3.0"


class DataAndTypeLoggerAdapter(logging.LoggerAdapter):
    def __init__(self, logger, default_type=""):
        super().__init__(logger, {})
        self._default_type = default_type

    def process(self, msg, kwargs):
        kwargs['extra'] = {'data': kwargs.get('extra', {}), 'type': self._default_type}
        return msg, kwargs


def get_date_and_type_logger(name=__name__, default_type="", to_stdout=True, to_file=True,
                             timed_rotate_split_error=False, rotate_log=False, rotate_kwargs=None, log_directory_path=None,
                             filename=None, level_stdout=logging.DEBUG, level_file=logging.DEBUG):
    """
    :param name: name of logger to get
    :param default_type: name for context of log
    :param to_stdout: print logs to stdout
    :param to_file: save logs to file
    :param timed_rotate_split_error: save logs to file, creating extra file for error logs, and rotate the log files every hour (overwrites rotate_log)
    :param rotate_log: if to_file,  rotate the log files (every hour by default) (overwritten by timed_rotate_split_error) 
    :param rotate_kwargs: keyword arguments for TimedRotatingFileHandler
    :param log_directory_path: log directory
    :param filename: log file name (ignored if timed_rotate_split_error)
    :param level: logging level
    :returns: logger
    """
    if rotate_kwargs is None:
        rotate_kwargs = {}
    logger_ = logging.getLogger(name)
    level_stdout = logging._checkLevel(level_stdout)
    level_file = logging._checkLevel(level_file)
    level_logger = min(level_stdout, level_file)
    logfmt = logging.Formatter("{" + ", ".join(f"\"{k}\": \"%({k})s\"" for k in (
        "asctime", "levelname", "type", "message", "data", "name", "funcName")) + ", \"lineno\": \"%(lineno)d\"}")

    log_handlers = []
    log_levels = []
    if to_stdout:
        log_handlers.append(logging.StreamHandler())
        log_levels.append(level_stdout)

    if to_file:
        if log_directory_path is None:
            log_directory_path = ''
        else:
            os.makedirs(log_directory_path, exist_ok=True)
        if timed_rotate_split_error:
            error_log_path = os.path.join(log_directory_path, 'error_logs.json')
            all_log_path = os.path.join(log_directory_path, 'daily_log.json')
            log_handlers.append(logging.handlers.TimedRotatingFileHandler(error_log_path, **rotate_kwargs))
            log_levels.append(logging.WARNING)
            log_handlers.append(logging.handlers.TimedRotatingFileHandler(all_log_path, **rotate_kwargs))
            log_levels.append(logging.DEBUG)
            level_logger = min(level_logger, logging.DEBUG)
        else:
            if filename is None:
                filename = f'{default_type}_log.json' if default_type else 'log.json'
            log_path = os.path.join(log_directory_path, filename)
            if rotate_log:
                log_handler = logging.handlers.TimedRotatingFileHandler(log_path, **rotate_kwargs)
            else:
                log_handler = logging.FileHandler(log_path)
            log_handlers.append(log_handler)
            log_levels.append(level_file)

    for log_handler, level in zip(log_handlers, log_levels):
        log_handler.setFormatter(logfmt)
        log_handler.setLevel(level)
        logger_.addHandler(log_handler)

    logger_.setLevel(level_logger)
    logger = DataAndTypeLoggerAdapter(logger_, default_type=default_type)
    return logger
