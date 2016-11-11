#! /usr/bin/env python3
# -*- coding:utf-8 -*-

"""
Default configuration
"""

#session是什么？？
configs = {
    "debug":True,
    'db':{
        "hosts":"127.0.0.1",
        "port":3306,
        "user":"root",
        "password":"1992",
        "db":"awesome"
    },
    "session":{
    'secret':"Awesome"
    }
}