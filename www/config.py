#! /usr/bin/env python3
# -*- coding:utf-8 -*-

"""
configuration
"""

import config_default

class Dict(dict):
    """新的类可以使用x.y来进行赋值和取出属性"""
    def __init__(self, names=(), values=(), **kw):
        super(Dict, self).__init__(**kw)
        for k,v in zip(names, values):
            self[k] = v

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Dict' object has no attribute '%s'" % key)

    def __setattr__(self, key, value):
        self[key] = value

#有嵌套字典，所以使用递归
def merge(defaults, override):
    r = {}
    for k,v in defaults.items():
        if k in override:
            if isinstance(v, dict):
                r[k] = merge(v, override[k])
            else:
                r[k] = override[k]
        else:
            r[k] = v
    return r

#把新的合并的字典放在我们新建的类中
def toDict(d):
    D = Dict()
    for k,v in d.items():
        D[k] = toDict(v) if isinstance(v,dict) else v
    return D

#configs是默认设置
configs = config_default.configs

try:
    #导入用户自定义配置
    import config_override
    #合并
    configs = merge(configs, config_override.configs)
except ImportError:
    pass

configs = toDict(configs)