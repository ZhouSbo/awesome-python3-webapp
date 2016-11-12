#! /usr/bin/env python3
# -*- coding:utf-8 -*-

"""
url handlers
"""

import re, time, json, logging, hashlib, base64, asyncio

from logger import logger

from coroweb import get, post

from models import User, Comment, Blog, next_id

from apis import Page, APIValueError, APIResourceNotFoundError, APIPermissionError

from config import configs

from aiohttp import web

import markdown2

_ADMIN_EMAIL = "zhousbo@gmail.com"

"""
@get('/')
async def index(request):
    users = await User.findAll()
    return {
        "__template__": "test.html",
        "users":users
    }

"""
"""

@get("/api/user")
async def api_get_users(*, page="1"):
    page_index = get_page_index(page)
    user_count = await User.findNumber("count(id)")
    p = Page(user_count, page_index, page_size=2)
    if user_count == 0:
        return dict(page=p, user={})
    else:
        users = await User.findAll(orderBy = "created_at desc", limit=(p.offset, p.limit))
    for u in users:
        u.passwd = "*******" 
    return dict(page=p, users=users)
"""

COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret

_RE_EMAIL = re.compile(r"^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$")
_RE_SHA1 = re.compile(r"^[0-9a-f]{40}$")

def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except ValueError as e:
        pass
    if p < 1:
        p = 1
    return p

def text2html(text):
    lines = map(lambda s: '<p>%s</p>' % s.replace("&", "&amp;").replace("<", "&lt;").
        replace(">", "&gt;"), filter(lambda s:s.strip() != "", text.split("\n")))
    return "".join(lines)

def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        raise APIPermissionError()

def user2cookie(user, max_age):
    expires = str(int(time.time()) + max_age)
    s = "%s-%s-%s-%s" % (user.id, user.passwd, expires, _COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return "-".join(L)

async def cookie2user(cookie_str):
    if not cookie_str:
        return None
    try:
        L = cookie_str.split("-")
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        if int(expires) < time.time():
            return None
        user = await User.find(uid)
        if user is None:
            return None
        s = "%s-%s-%s-%s" % (uid, user.passwd, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode("utf-8")).hexdigest():
            logger.info("invalid sha1")
            return None
        user.passwd = "*******"
        return user
    except Exception as e:
        logger.exception(e)
        return None

#主页面
@get("/")
async def index(*, page="1"):
    page_index = get_page_index(page)
    num = await Blog.findNumber("count(id)")
    if (not num) and num == 0:
        logger.info("the type of num is : %s" % type(num))
        blogs = []
    else:
        page = Page(num, page_index)
        blogs = await Blog.findAll(orderBy="created_at desc", limit=(page.offset, page.limit))
    return {
        "__template__":"blogs.html",
        "page":page,
        "blogs":blogs
    }

#---------------------------注册、登录、注销----------------------------

@get("/register")
async def register():
    return {
        "__template__":"register.html"
    }

@post("/api/users")
async def api_register_user(*, email, name, passwd):
    if not name or not name.strip():
        raise APIValueError("name")
    if not email or not _RE_EMAIL.match(email):
        raise APIError("email")
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIError("passwd")
    users = await User.findAll("email=?", [email])
    if len(users):
        raise APIValueError("register:failed", 'email', "Email is already in use.")
    uid = next_id()
    sha1_passwd = "%s:%s" % (uid, passwd)
    admin = False
    if email == _ADMIN_EMAIL:
        admin = True

    user = User(
        id=uid, 
        name=name.strip(), 
        email=email, 
        passwd=hashlib.sha1(sha1_passwd.encode("utf-8")).hexdigest(), 
        image="http://www.gravatar.com/avatar/%s?d=mm&s=120" % hashlib.md5(email.encode("utf-8")).hexdigest(), admin=admin
        )
    await user.save()
    logger.info("save user OK")
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passed = "*******"
    r.content_type = "application/json"
    r.body = json.dumps(user, ensure_ascii=False, default=lambda o:o.__dict__).encode("utf-8")
    return r

@get("/signin")
async def signin():
    return {
        "__template__":"signin.html"
    }

@post("/api/authenticate")
async def authenticate(*, email, passwd):
    if not email:
        raise APIValueError("email", "Invalid email")
    if not passwd:
        raise APIValueError("passwd", "Invalid passwd.")
    users = await User.findAll("email=?", [email])
    if not len(users):
        raise APIValueError("email", "email not exist")
    user = users[0]

    browser_sha1_passwd = "%s:%s" % (user.id, passwd)
    browser_sha1 = hashlib.sha1(browser_sha1_passwd.encode("utf-8"))
    if user.passwd != browser_sha1.hexdigest():
        raise APIValueError("passwd", "Invalid passwd")

    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = "*******"
    r.content_type = "application/json"
    r.body = json.dumps(user, ensure_ascii=False, default=lambda o:o.__dict__).encode("utf-8")
    return r

@get("/signout")
def signout(request):
    referer = request.headers.get("Referer")
    r = web.HTTPFound(referer or "/")
    r.set_cookie(COOKIE_NAME, "-deleted-", max_age=0, httponly=True)
    logger.info("user signed out")
    return r

#-------------------------用户管理---------------------------

@get("/show_all_users")
async def show_all_users():
    users = await User.findAll()
    logger.info("to index...")
    return {
        "__template__":"all_users.html",
        "users":users
    }

@get("/api/users")
async def api_get_users(request):
    users = await User.findAll(orderBy="created_at desc")
    logger.info("users = %s and type = %s" % (users, type(users)))
    for u in users:
        u.passwd = "*******"
    return dict(users=users)

@get("/manage/users")
async def manage_users(*, page="1"):
    return {
        "__template__":"manage_users.html",
        "page_index":get_page_index(page)
    }

#----------------------------博客管理--------------------------
@get("/manage/blogs/create")
async def manage_create_blog():
    return {
        "__template__" :"manage_blog_edit.html",
        "id":"",
        "action":"/api/blogs"
    }

@get("/manage/blogs")
async def manage_blogs(*, page="1"):
    return {
        "__template__": "manage_blogs.html",
        "page_index":get_page_index(page)
    }

@post("/api/blogs")
async def api_create_blog(request, *, name, summary, content):
    check_admin(request)
    if not name or not name.strip():
        raise APIValueError("name", "name can not empty")
    if not summary or not summary.strip():
        raise APIValueError("summary", "summary can not be empty")
    if not content or not content.strip():
        raise APIValueError("content", "content can not be empty")
    blog = Blog(
        user_id = request.__user__.id,
        user_name = request.__user__.name,
        user_image = request.__user__.image,
        name = name.strip(),
        summary = summary.strip(),
        content = content.strip()
        )
    await blog.save()
    return blog

@get("/api/blogs")
async def api_blog(*, page="1"):
    page_index = get_page_index(page)
    blog_count = await Blog.findNumber("count(id)")
    p = Page(blog_count, page_index)
    if blog_count == 0:
        return dict(page=p, blogs=[])
    blogs = await Blog.findAll(orderBy="created_at desc", limit=(p.offset, p.limit))
    return dict(page=p, blogs=blogs)

@get('/blog/{id}')
async def get_blog(id):
    blog = await Blog.find(id)
    comments = await Comment.findAll("blog_id=?", [id], orderBy="created_at desc")
    for c in comments:
        c.html_content = text2html(c.content)
    blog.html_content = markdown2.markdown(blog.content)
    return {
        "__template__":"blog.html",
        "blog":blog,
        "comments":comments
    }

@get("/api/blogs/{id}")
async def api_get_blog(*, id):
    blog = await Blog.find(id)
    return blog

@post("/api/blogs/{id}/delete")
async def api_delete_blog(id, request):
    logger.info("删除博客的博客id为: %s" % id)
    check_admin(request)
    b = await Blog.find(id)
    if b is None:
        raise APIResourceNotFoundError("comment")
    await b.remove()
    return dict(id=id)

@post("/api/blogs/modify")
async def api_modify_blog(request, *, id, name, summary, content):
    logger.info("修改博客的博客id为: %s ", id)
    if not name or not name.strip():
        raise APIValueError('name', 'name cannot be empty')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary cannot be empty')
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty')
    blog = await Blog.find(id)
    blog.name = name
    blog.summary = summary
    blog.content = content

    await blog.update()
    return blog

@get("/manage/blogs/modify/{id}")
async def manage_modify_blog(id):
    return {
        "__template__":"manage_blog_modify.html",
        "id":id,
        "action":"/api/blogs/modify"
    }

#--------------------------------评论管理-----------------------
@get("/manage/")
async def manage():
    return "redirect:/manage/comments"

@get("/manage/comments")
async def manage_comments(*, page="1"):
    return {
        "__template__":"manage_comments.html",
        "page_index":get_page_index(page)
    }

@get("/api/comments")
async def api_comments(*, page="1"):
    page_index = get_page_index(page)
    num = await Comment.findNumber("count(id)")
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, comment=())
    comments = await Comment.findAll(orderBy="created_at desc", limit=(p.offset, p.limit))
    return dict(page=p, comments=comments)

@post('/api/blogs/{id}/comments')
async def api_create_comment(id, request, *, content):
    # 对某个博客发表评论
    user = request.__user__
        # 必须为登陆状态下，评论
    if user is None:
        raise APIPermissionError('content')
    # 评论不能为空
    if not content or not content.strip():
        raise APIValueError('content')
    # 查询一下博客id是否有对应的博客
    blog = await Blog.find(id)
    # 没有的话抛出错误
    if blog is None:
        raise APIResourceNotFoundError('Blog')
    # 构建一条评论数据
    comment = Comment(
        blog_id=blog.id,
        user_id=user.id, 
        user_name=user.name,
        user_image=user.image, 
        content=content.strip()
        )
        # 保存到评论表里
    await comment.save()
    return comment
    
    
@post('/api/comments/{id}/delete')
async def api_delete_comments(id, request):
    # 删除某个评论
    logger.info(id)
    # 先检查是否是管理员操作，只有管理员才有删除评论权限
    check_admin(request)
    # 查询一下评论id是否有对应的评论
    c = await Comment.find(id)
    # 没有的话抛出错误
    if c is None:
        raise APIResourceNotFoundError('Comment')
    # 有的话删除
    await c.remove()
    return dict(id=id)    