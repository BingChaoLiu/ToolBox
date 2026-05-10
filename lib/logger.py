import logging
import os
import pathlib
from logging.handlers import RotatingFileHandler

# 默认日志文件名
LOG_FILENAME = "toolbox_framework.log"

def get_logger(name="toolbox"):
    """
    获取配置好的日志记录器。
    日志会输出到项目根目录下的 toolbox_framework.log 文件中。
    支持按大小滚动，保留最近 5 个日志文件，每个最大 5MB。
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    
    # 格式化
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 根目录定位
    root = pathlib.Path(__file__).parent.parent
    log_path = root / LOG_FILENAME

    # 文件 Handler (滚动)
    file_handler = RotatingFileHandler(
        log_path, maxBytes=5*1024*1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

# 预创建默认 logger 实例
logger = get_logger()
