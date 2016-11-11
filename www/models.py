#! /usr/bin/env python3
# -*- coding:utf-8 -*-

"""
Model for user,blog, coment
"""
# 为什么一定要用uuid来生成主键？不能使用用户名作为主键吗？

import time, uuid
from orm import Model, StringField, BooleanField, FloatField, TextField

def next_id():
    #使用uuid函数 加上时间等生成一个随机数，作为主键
    return '%015d%s000' % (int(time.time()*1000), uuid.uuid4().hex)

class User(Model):
    # User表，包括id email passwd admin name image create_at这几列
    #其中id是主键
    __table__ = 'users'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    email = StringField(ddl='varchar(50)')
    passwd = StringField(ddl="varchar(50)")
    admin = BooleanField() #是不是管理员身份
    name = StringField(ddl="varchar(50)")
    image = StringField(ddl="varchar(500)")
    created_at = FloatField(default=time.time)

class Blog(Model):
    # blog表，包括id user_id user_name user_image name summary content created_at
    #id是主键
    __table__ = 'blogs'

    id = StringField(primary_key=True, default=next_id, ddl="varchar(50)")
    user_id = StringField(ddl='varchar(50)')  #作者id
    user_name = StringField(ddl='varchar(50)')  #作者姓名
    user_image = StringField(ddl='varchar(500)')  #作者上传的图片
    name = StringField(ddl='varchar(50)')  #文章名字
    summary = StringField(ddl='varchar(200)')  #文章摘要
    content = TextField()  #文章内容
    created_at = FloatField(default=time.time)  #文章创建日期，便于后期排序

class Comment(Model):
    #评论
    # id blog_id user_id user_name user_image content created_at
    __table__ = 'comments'

    id = StringField(primary_key=True, default=next_id, ddl="varchar(50)")
    blog_id = StringField(ddl='varchar(50)')  #博客id
    user_id = StringField(ddl='varchar(50)')  #评论者id
    user_name = StringField(ddl='varchar(50)')  #评论者的姓名
    user_image = StringField(ddl="varchar(500)")  #评论者上传的图片
    content = TextField()  #评论内容
    created_at = FloatField(default=time.time)
