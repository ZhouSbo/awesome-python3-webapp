#! /usr/bin/env python3
# -*- coding:utf-8 -*-

"""
Json API defination
"""

import json, inspect, functools
from logger import logger

_PAGE_SIZE = 20

class APIError(Exception):
    "base APIError"
    def __init__(self, error, data="", message=""):
        super(APIError, self).__init__(message)
        self.error = error
        self.data = data
        self.message = message

class APIValueError(APIError):
    "输入的值有错误"
    def __init__(self, field, message=""):
        super(APIValueError, self).__init__("value:invalid", field, message)

class APIResourceNotFoundError(APIError):
    "资源没有找到"
    def __init__(self, field, message=""):
        super(APIResourceNotFoundError, self).__init__("value:notfound", field, message)

class APIPermissionError(APIError):
    "api has no permission"
    def __init__(self, message=""):
        super(APIPermissionError, self).__init__("permission:forbidden", "permission", message)

#用于分页
#为什么要把这个类放在这里？？
class Page(object):
    # item_count 要显示的条目总数量 
    # page_index 要显示的是第几页
    # page_size 每页的条目数量
    def __init__(self, item_count, page_index=1, page_size=_PAGE_SIZE):
        self.__item_count = item_count
        self.__page_size = page_size
        #多少页才能显示全部条目
        self.__page_count = item_count // page_size + (1 if item_count % page_size > 0 else 0)
        #如果没有条目或要显示的页数超出能显示的页数范围
        if (item_count == 0) or (page_index > self.__page_count):
            self.offset = 0
            self.limit = 0
            self.__page_index = 1
        else:
            #显示的页数就是传入的页数
            self.__page_index = page_index
            #这页的初始条目的offset
            self.offset = self.__page_size * (page_index - 1)
            #这一页能显示的数据
            self.limit = self.__item_count if self.__item_count < self.__page_size else self.__page_size
        self.has_next = self.__page_index < self.__page_count    #是否有下一页
        self.has_previous = self.__page_index > 1    #是否有上一页

    def __str__(self):
        return "item_count:%s, page_count:%s, page_index:%s, page_size:%s, offs\
        et:%s, limit:%s" % (self.__item_count, self.__page_count, self.__page_index, self.__page_size, self.offset, self.limit)

    __repr__ = __str__