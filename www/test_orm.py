 #!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试增删改查，单元化测试？？unitest??
"""
import orm, asyncio, sys, time
from models import User, Blog, Comment

async def test_insert(loop):
    await orm.create_pool(loop=loop, user='root', password='1992', db='awesome')
    u = User(name='test2', 
        email='test2@test.com', 
        passwd='test2', 
        image='about:blank')
    await u.save()

async def test_insert_blogs(loop):
    await orm.create_pool(loop=loop, user='root', password='1992', db='awesome')
    b = Blog(user_id = "zhousbo@gmail.com",
        user_name = "zhoushaobo",
        user_image = "about:blank",
        name = "first blog",
        summary = "test blog",
        content = "test"
        )
    await b.save()

async def test_update(loop):
    await orm.create_pool(loop=loop, user='root', password='1992', db='awesome')
    u = User(id = "001478260747756523c7f945c084195a67ff9d0e592cfe7000",
        created_at = time.time(),
        admin = True,
        name='test', 
        email='update@test.com', 
        passwd='test', 
        image='about:blank')
    await u.update()

async def test_findAll(loop):
    await orm.create_pool(loop=loop, user='root', password='1992', db='awesome')
    rs = await User.findAll(email='update@test.com')
    for i in range(len(rs)):
        print(rs[i])

async def test_findNumber(loop):
    await orm.create_pool(loop=loop, user='root', password='1992', db='awesome')
    count = await User.findNumber('email')
    print(count)
    
async def test_find(loop):
    await orm.create_pool(loop=loop, user='root', password='1992', db='awesome')
    rs = await User.find("001478260747756523c7f945c084195a67ff9d0e592cfe7000")
    print(rs)

async def test_remove(loop):
    await orm.create_pool(loop=loop, user='root', password='1992', db='awesome')
    u = User(id="0014782608142948c4db961222946258fb9dd3472fd8da6000")
    await u.remove()

loop = asyncio.get_event_loop()
loop.run_until_complete(test_insert(loop))  
__pool = orm.__pool
__pool.close()    #必须首先关闭连接迟才不会报错
loop.run_until_complete(__pool.wait_closed())
loop.close()