#! /usr/bin/env python3
# -*-coding:utf-8 -*-

# 在下面设置之后好像就不用再次在这里设置了
# import logging; logging.basicConfig(level=logging.INFO, filename='server_info.log')

#logging是日志模块
import logging
import logging.handlers

#log存放路径
LOG_FILE = '../log/server_info.log'
#实例化handler
handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=1024*1024)
fmt = '%(asctime)s - %(filename)s: %(lineno)s - %(name)s - %(message)s'
formatter = logging.Formatter(fmt) #实例化formatter
handler.setFormatter(formatter)    #为handler添加formatter

logger = logging.getLogger("server_info")    #获取名为server_info的logger
logger.addHandler(handler)    #为logger添加handler
logger.setLevel(logging.INFO)