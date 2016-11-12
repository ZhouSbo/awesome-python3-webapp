#! /usr/bin/python3
# -*- coding:utf-8 -*-

# logging作用是记录日志，等级分别为debug(),info(),warning(),error(),critical(),默认是warning,
# 使用logging.basicConfig(filename="example.log", level=logging.DEBUG)可以修改日志存放位置
#import logging; logging.basicConfig(level=logging.INFO)

import asyncio, os, json, time
from datetime import datetime
    
from aiohttp import web

from jinja2 import Environment, FileSystemLoader
from config import configs
import orm

from coroweb import add_routes, add_static

from handlers import cookie2user, COOKIE_NAME

from logger import logger

#初始化jinja2模板，配置jinja2的环境
def init_jinja2(app, **kw):
    logger.info("init jinja2...")
    options = dict(
        autoescape = kw.get("autoescape", True),    #自动转义xml/html的特殊字符
        block_start_string = kw.get('block_start_string', "{%"),    #设置代码起始字符串
        block_end_string = kw.get("block_end_string", "%}"),
        variable_start_string = kw.get("variable_start_string", "{{"),
        variable_end_string = kw.get("variable_end_string", "}}"),    #变量起始字符串
        auto_reload = kw.get("auto_reload", True)    #模板被修改后自动重置
        ) 
    path = kw.get('path', None)    #从kw中获取路径，没有设置为None
    #如果路径为None
    if path is None:
        #将模板路径设置为当前路径下templates文件夹
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'templates')
        logger.info("set jinja2 template path: %s" % path)
        #载入模板
        env = Environment(loader=FileSystemLoader(path), **options)
        # 过滤器设置
        filters = kw.get("filters", None)
        if filters is not None:
            for name, f in filters.items():
                env.filters[name] = f
        app["__templating__"] = env    #将env环境存入app的属性中

#装饰器，每当有http请求就记录日志
async def logger_factory(app, handler):
    async def logger_fact(request):
        logger.info("Request: %s %s" % (request.method, request.path))
        return (await handler(request))
    return logger_fact

async def auth_factory(app, handler):
    async def auth(request):
        logger.info("check user:%s %s" % (request.method, request.path))
        request.__user__ = None
        cookie_str = request.cookies.get(COOKIE_NAME)
        if cookie_str:
            user = await cookie2user(cookie_str)
            if user:
                logger.info("set current user:%s" % user.email)
                request.__user__ = user
        if request.path.startswith("/manage/") and (request.__user__ is None or not request.__user__.admin):
            return web.HTTPFound("/signin")
        return await handler(request)
    return auth

#只有请求方法为POST才有用，什么作用？？闭包干什么
async def data_factory(app, handler):
    async def parse_data(request):
        if request.method == "POST":
            if request.content_type.startswith("application/json"):
                request.__data__ = await request.json()
                logger.info("request json: %s" % str(request.__data__))
            elif request.content_type.startswith("application/x-www-form-urlencoded"):
                request.__data__ = await request.post()
                logger.info("request form :%s" % str(request.__data__))
        return (await handler(request))
    return parse_data

#又是闭包？为什么要用闭包
async def response_factory(app, handler):
    async def response(request):
        logger.info("Request handler...")
        #调用handler处理函数，返回相应结果
        r = await handler(request)
        # 若响应结果为StreamResponse,直接返回
        # StreamResponse是aiohttp定义response的基类,即所有响应类型都继承自该类
        # StreamResponse主要为流式数据而设计
        if isinstance(r, web.StreamResponse):
            return r
        # 若响应结果为字节流,则将其作为应答的body部分,并设置响应类型为流型
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp.content_type = "application/octet-stream"
            return resp
        if isinstance(r, str):
             # 判断响应结果是否为重定向.若是,则返回重定向的地址
            if r.startswith("redirect:"):
                return web.HTTPFound(r[9:])
            resp = web.Response(body = r.encode("utf-8"))
            resp.content_type = "text/html;charset=utf-8"
            return resp
        # 若响应结果为字典,则获取它的模板属性,此处为jinja2.env(见init_jinja2)
        if isinstance(r, dict):
            template = r.get("__template__")
            # 若不存在对应模板,则将字典调整为json格式返回,并设置响应类型为json
            if template is None:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode("utf-8"))
                resp.content_type = "application/json;charset=utf-8"
                return resp
             # 存在对应模板的,则将套用模板,用request handler的结果进行渲染
            else:
                r['__user__'] = request.__user__
                resp = web.Response(body=app["__templating__"].get_template(template).render(**r).encode("utf-8"))
                resp.content_type = "text/html;charset=utf-8"
                return resp
        # 若响应结果为整型的
        # 此时r为状态码,即404,500等
        if isinstance(r, int) and r >= 100 and r <= 600:
            return web.Response
        if isinstance(r, tuple) and len(r) ==2:
            t, m = r
            if isinstance(t, int) and t >= 100 and t <= 600:
                return web.Response(t, str(m))
        resp = web.Response(body=str(r).encode("utf-8"))
        resp.content_type = "text/plain;charset=utf-8"
        return resp
    return response

#返回创建日志的时间
def datetime_filter(t):
    #现在的事件减去创建的事件
    delta = int(time.time() - t)
    if delta < 60:
        return u"1分钟前"
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    #好像是对时间进行转换
    dt = datetime.fromtimestamp(t)
    return u"%s年%s月%s日" % (dt.year, dt.month, dt.day) 
            
async def init(loop):
    #创建数据库连接池
    await orm.create_pool(loop=loop, **configs.db)
    #表示将下面的协程实例放入web.Application中运行
    #中间件是什么？？
    app = web.Application(loop=loop, middlewares=[
        logger_factory, auth_factory, response_factory])
    #初始化jinja2模板并传入时间过滤器
    init_jinja2(app, filters=dict(datetime = datetime_filter))
    #增加路由，路由的作用就是当客户端发出命令时，服务器所对应的方法
    #handlers指的是handlers.py模块
    add_routes(app, "handlers")
    add_static(app)
    #loop实例拥有create_server方法，第一个参数是protocol_factory，这里是app.make_handler(),make_handler()表示创建HTTP protocol factory来处理请求
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logger.info("server started at http://127.0.0.1:9000")  #记录日志
    return srv
    
loop = asyncio.get_event_loop()  #创建协程实例
#传入参数，init(loop)，loop是前一行中创建的协程的实例，将这个协程对象传入函数
loop.run_until_complete(init(loop)) 
loop.run_forever()