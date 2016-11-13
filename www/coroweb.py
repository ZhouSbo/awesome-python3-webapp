#! /usr/bin/env  python3
# -*- coding:utf-8 -*-

#------------------------------
#inspect模块四种作用
#第一种是类型检查，判断是否是类、方法、函数、生成器、协程等等，还可以获取模块、函数等的名字，members等
#第二种是检索源代码，获取源代码，文档等
#第三种是获取类或函数的参数的信息，这个模块中使用的主要是是这个用法
#-------------------------------

import asyncio, os, inspect, functools

from logger import logger

from urllib import parse

from aiohttp import web

from apis import APIError

# 装饰器，在Handlers模块中被引用，作用是给http请求添加请求方法请求路径这两个属性
def get(path):
    """
    define decorator @get('/path')
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = "GET"
        wrapper.__route__ = path
        return wrapper
    return decorator

def post(path):
    """
    Define decorator @post('/path')
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator

#print(name, param)
#a a \ b b=1 \ args *args \ c c=1 \ kw **kw
#param.kind作用是描述参数值如何绑定到参数，可能有以下值
# POSITIONAL_ONLY 位置参数
# POSITION_OR_KEYWORD 命名关键字参数或位置参数 a b=1
# VAR_POSITIONAL 可变参数， *args
# KEYWORD_ONLY  命名关键字参数 *args之后的关键字参数 c=1
# VAR_KEYWORD 关键字参数 **kw

#位置参数
#默认参数 a = 1
#可变参数 *args
#关键字参数 **kw字典，可以接受任何关键字参数
#命名关键字参数，在*后，只能接受制定关键字的参数

#为什么要有get_required_kw_args和get_named_kw_args的区别呢？一个不是把另一个全部包括了吗？
def get_required_kw_args(fn):
    "把fn中命名关键字参数且没有指定默认值的参数名提取出来"
    args = []
    #返回一个mappingproxy对象，里面是fn的参数
    params = inspect.signature(fn).parameters
    #params.items()返回OrderedDict()对象，如果传入参数是a, b=1, *args,c=1 **kw
    for name, param in params.items():
        #参数类型为命名关键字且没有指定默认值，把关键字参数的名加入args这个list中
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
        return tuple(args)

def get_named_kw_args(fn):
    "把fn中所有命名关键字参数的参数名提取出来"
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)

def has_named_kw_args(fn):
    "判断fn中有没有命名关键字参数，有返回True"
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True

def has_var_kw_arg(fn):
    "判断fn中有没有关键字参数，有返回True"
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True

#判断fn中有没有request参数
def has_request_arg(fn):
    sig = inspect.signature(fn)
    params = sig.parameters
    found = False
    for name, param in params.items():
        if name == "request":
            found = True
            continue
        # found默认为False，
        #对所有参数进行迭代循环，这些参数只要有一个不满足以下条件就raise error
        if found and (
        param.kind != inspect.Parameter.VAR_POSITIONAL and   #不是可变参数
        param.kind != inspect.Parameter.KEYWORD_ONLY and    #不是命名关键字参数
        param.kind != inspect.Parameter.VAR_KEYWORD):   #不是关键字参数
            raise ValueError("request parameter must be the last named parameter in functon: %s %s" % (fn.__name__, str(sig)))
    return found

class RequestHandler(object):
    "请求处理"
    def __init__(self, app, fn):
        #app是什么？ fn又是什么？
        self._app = app
        self._func = fn
        self._has_request_arg = has_request_arg(fn)  #判断fn函数中有没有request 有返回True
        self._has_var_kw_arg = has_var_kw_arg(fn)    #判断fn中有没有关键字参数，有返回True
        self._has_named_kw_args = has_named_kw_args(fn)    #判断fn中有没有命名关键字参数，有返回True
        self._named_kw_args = get_named_kw_args(fn)    #把fn中所有命名关键字参数的参数名提取出来 返回元组
        self._required_kw_args = get_required_kw_args(fn)    #把fn中关键字参数且没有指定默认值的参数名提取出来，返回元组

    # 重载__call__之后，类就像函数一样可以调用
    async def __call__(self, request):
        test1 = {arg: value for arg, value in request.__data__.items() if arg in required_args}
        print(test1)
        print(request.match_info)
        print(request)
        #kw为什么不直接定义为一个空字典？是因为get中可能为空吗？
        kw = None
        #传入的request参数如果有关键字参数且没有默认值或者有命名关键字参数或者有关键字参数
        if self._has_var_kw_arg or self._has_named_kw_args or self._required_kw_args:
            # request方法为POST
            if request.method == "POST":
                #没有主体类型，就返回错误，没有主体类型，就无法知道到底是json还是表单模式
                if not request.content_type:
                    return web.HTTPBadRequest("Missing Content-Type.")
                ct = request.content_type.lower()
                #如果是json格式
                if ct.startswith("application/json"):
                    #参数解包？
                    params = await request.json()
                    #解包的参数必须是字典
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest("JSON body must be object")
                    # 将解包的参数传递给kw
                    kw = params
                elif ct.startswith("application/x-www-form-urlencode") or ct.startswith('multipart/form-data'):
                    params =await request.post()
                    kw = dict(**params)
                else:
                    #只支持这两种参数传递方式
                    return web.HTTPBadRequest("Unsupported Content-type: %s" % request.content_type)

            #request方法为GET
            if request.method == "GET":
                # 获取请求字符串，这个request是哪个模块里面的？
                qs = request.query_string
                #如果qs不是空字符串
                if qs:
                    kw = dict()
                    # parse.parse_qs属于urllib，对GET方法传递的参数进行解码，分别解码成字典形式
                    for k, v in parse.parse_qs(qs, True).items():
                        kw[k] = v[0]
        
        # 如果kw还是None，说明没有request方法和get方法
        if kw is None:
            #aiohttp中的request.match_info是什么？
            kw = dict(**request.match_info)
        else:
            # 如果传递的fn参数中没有关键字参数但是有命名关键字参数
            if not self._has_var_kw_arg and self._named_kw_args:
                copy = dict()
                for name in self._named_kw_args:  #命名关键字参数的名字，是一个元组
                    #只要命名关键字参数中的值？
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            # 这个不知道是什么意思request.match_info.items()
            for k, v in request.match_info.items():
                if k in kw:
                    logger.warn("Duplicate arg name in named arg and kw args:%s" % k)
                kw[k] = v

        #如果有request参数
        if self._has_request_arg:
            kw["request"] = request    #返回True

        #把fn中关键字参数且没有指定默认值的参数名提取出来，返回元组，如果返回的元组中有不在kw中的就返回丢失参数，这里是一个检查？
        if self._required_kw_args:
            for name in self._required_kw_args:
                if not name in kw:
                    return web.HTTPBadRequest("Missing argument: %s" % name)
        logger.info("call with args: %s" % str(kw))

        #上面全是在处理参数，处理好之后，放到func中进行处理，然后返回
        try:
            r = await self._func(**kw)
            return r
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)

# 向app中添加静态文件目录
def add_static(app):
    # os.path.abspath(__file__)返回脚本执行的绝对路径，dirname是获取文件所属文件夹路径
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static', path)
    logger.info("add static %s => %s" % ('/static/', path))

# 从fn中提取出method和post，然后将其注册到app
def add_route(app, fn):
    method = getattr(fn, "__method__", None)  #从fn中获取method
    path = getattr(fn, "__route__", None)    #从fn中获取path
    if path is None or method is None:
        raise ValueError("@get or @post not defined in %s" % str(fn))
    #如果函数不是协程也不是生成器就变成协程
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        fn = asyncio.coroutine(fn)
    logger.info("add route %s %s => %s(%s)" % (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
    app.router.add_route(method, path, RequestHandler(app, fn))    #将函数注册到app

#这个函数执行完之后自动转入add_route中进行下一步处理 
# 模块导入时文件目录是以点表示归属，a文件夹下b.py 导入import a.b
#module_name 理解为模块导入时完整的路径更好一点
def add_routes(app, module_name):
    #寻找'.'
    n = module_name.rfind('.')
    # 没找到，说明在当前目录下，直接导入
    if n == (-1):
        # __import__中字符串表示模块名字，globals和locals好像是解释模块在上下文中的范围，后面的列表表示从模块中导入这个变量
        mod = __import__(module_name, globals(), locals())
    else:
        #将模块的名字提取出来
        name = module_name[n+1:]
        #from module_name[:n] import name 如果没有就默认为name
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
    #依次迭代mod的属性
    for attr in dir(mod):
        if attr.startswith('_'):    #私有属性排除
            continue
        fn = getattr(mod, attr)    #fn就是这个模块的属性
        if callable(fn):    #如果这个属性是函数
            method = getattr(fn, '__method__', None)
            path = getattr(fn, "__route__", None)
            if method and path:
                add_route(app, fn)