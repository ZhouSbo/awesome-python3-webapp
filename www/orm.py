#! /usr/bin/env python3
# -*- coding:utf-8 -*-

import asyncio
import aiomysql
import sys
from logger import logger

def log(sql, args=()):
    logger.info('SQL:%s, args: %s' % (sql, args))

# 创建一个全局的连接池
async def create_pool(loop, **kw):  #传入参数pool和字典kw
    logger.info('create database connection pool...')  
    global __pool  #将其为全局变量
    # aiomysql.create_pool是创建一个可以连接至数据库的池子
    __pool = await aiomysql.create_pool(
        host = kw.get('host', '127.0.0.1'),  #未传入就是默认的
        port = kw.get('port', 3306),  #未传入就是默认的
        user = kw['user'],  #必须传入用户名和密码
        password = kw['password'],
        db = kw['db'],
        charset = kw.get('charset', 'utf8'),
        autocommit = kw.get('autocommit', True),  #自动提交？
        maxsize = kw.get('maxsize', 10),  #最大连接数
        minsize = kw.get('minsize', 1),  #最小连接数
        loop = loop  #这个loop是函数中的参数loop
        )

#封装的select语句
async def select(sql, args, size=None):
    log(sql, args)
    #声明__pool是全局变量才可以在这个函数中调用
    global __pool
    async with __pool.get() as conn:  #从连接池中取出一个连接
        #取出连接之后，默认已经使用connect建立了连接？，
        #conn.cursor(aiomysql.DictCursor)是创建一个字典游标，以字典方式返回结果，列名为key
        cur = await conn.cursor(aiomysql.DictCursor)  
        # 执行命令，首先将sql语句中的？换为%s，这里args是传入的参数，传入的是替换占位符的参数
        await cur.execute(sql.replace('?', '%s'), args or ())
        #如果传入了size参数就获取返回的结果数，没有传入size返回所有的结果
        if size:
            rs = await cur.fetchmany(size)
        else:
            rs = await cur.fetchall()
        # 关闭游标
        await cur.close()
        # 记录日志，len(rs)是结果数
        logger.info('rows returned: %s ' % len(rs))
        return rs

#执行INSERT UPDATE DELETE都要用到通用的execute语句，因为都要相同的参数，返回一个整数表示受到影响的行数
# 传入参数为sql，代表sql语句，args是sql中的参数
async def execute(sql, args,autocommit=True):
    #调用自己创建的log函数
    log(sql)
    #从连接池中取出一个连接
    async with __pool.get() as conn:
        #如果不是自动提交就conn.begin(),使用事务进行处理，这个是sqlalchemy中的方法
        #connection = engine.connect()连接之后，trans = connection.begin()，返回一个事务对象，通常使用在try中
        if not autocommit:
            await conn.begin()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql.replace("?", "%s"), args)
                affected = cur.rowcount
            #前面创建事务对象，必须对事务进行commit才能生效
            if not autocommit:
                await conn.commit()
        except BaseException as e:
            # 如果出错，回滚至执行之前，避免出错，select不用是因为不会对数据造成变动
            if not autocommit:
                await conn.rollback()
            raise
        #返回受影响的行数
        return affected

# 这个函数在元类中被引用
def create_args_string(num):
    L = []
    for n in range(num):
        L.append("?")
    # num是3，L就是"? ,? ,?"
    return ', '.join(L)

class Field(object):
    #创建了一个列的模板，包括列名，列的类型，是不是主键，default是什么？
    def __init__(self, name, column_type, primary_key, default):
        self.name = name  #列
        self.column_type = column_type  #字段类型，就是这一列是int还是float
        self.primary_key = primary_key  #主键，必须唯一
        self.default = default  #默认值，什么的默认值？
    # 可以使用这个函数看每一列的详细信息
    def __str__(self):
        return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type,self.name)

# 这个是Field的子类，表示通过列的模板创建了一个详细的列
#默认不作为主键，但是可以传入参数进行修改，使其作为主键
class StringField(Field):
    #这个列名字默认为None，不是主键，default是None，列的类型，属于数据库中的串数据类型，表示长度可变长度，最多不超过255字节
    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
            # 面向对象的用法，super()表示使用父类的方法创建，依次传入参数
            super().__init__(name, ddl, primary_key, default)

# Field的子类，创建MySQL数值数据类型中的BOOLEAN类型，绝对不能作为主键，所以不论传入参数是什么，初始化都为False
class BooleanField(Field):
    def __init__(self, name=None, default=False):
        super().__init__(name, "boolean", False, default)

# Field的子类，创建MySQL数值数据类型中的BIGINT类型，
class IntegerField(Field):
    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'bigint', primary_key, default)

# real表示4字节的浮点值
class FloatField(Field):
    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)

#text表示最大长度为64K的变长文本，应该是用来作为blog的文章，肯定不能作为主键
class TextField(Field):
    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)

class ModelMetaclass(type):
    "每个表创建时（比如Users表）,将Users表中添加的各种属性（id name __table__等）分别放入__table__、__mappings__、"
    "__primary_key_、__fields__属性中,其中__mappings__放置除__table__之外的key和value，fields放置除主键和__table__的__mappings__的key"
    "随后使用这这些属性方便地构造四个数据库操作语句select update insert delete"
    # 元类类似于装饰器？ 初始化一个类时首先对这个类进行__new__处理
    # cls类似于self，不过在类中使用cls避免混淆
    # name是创建的类的名字
    # bases是准备继承的父类的名字，是元祖
    # attrs是希望每次创建类时都存在的属性，比如希望每个新建的类又有foo="bar"属性，attr就是{"foo":bar}
    #在这里，attr中包含的是models中User类中__table__, email等属性
    #  元类作用
    #1)   拦截类的创建
    #2)   修改类
    #3)   返回修改之后的类
    def __new__(cls, name, bases, attrs):
        #如果传入的是"Model"类，那么直接返回，不对Model类进行处理,因为Model类已经包含这些属性了
        if name == "Model":
            return type.__new__(cls, name, bases, attrs)
        # 看属性中是否存在__table__属性，没有就将参数中的name，也就是类名赋予给tableName(就是数据库的表名)
        tableName = attrs.get('__table__', None) or name
        # 日志记录 根据类名创建表名
        logger.info("found model: %s (table:%s)" % (name, tableName))
        # 创建空字典mappings，用来储存attrs中的属性，但是不储存__table__
        mappings = dict()
        # 储存attrs中的key，就是email admin等值，但是不储存主键id和__table__
        fields = []
        # 主键默认为None，找到再进行赋值
        primaryKey = None
        # 依次迭代类的属性
        # k是key，v是value,这里key是id，email等，value是StringField(primary_key=True, default=next_id, ddl='varchar(50)')
        for k,v in attrs.items():
            # Field是上面创建的每一列的模板,在attr中除了__table__,其余email列，name列都是属于Field类
            #如果这个列是Field类
            if isinstance(v, Field):
                logger.info("   found mapping: %s ==> %s" % (k,v))
                #将这个属性放在mapping中
                mappings[k] = v
                # 如果找到主键，这里v是一个类，取出这个类的属性
                if v.primary_key:
                    #如果发现主键已经存在，报错
                    if primaryKey:
                        raise StandardError("Duplicate priary key for field: %s" % k)
                    # 对主键赋值，k是列名，设置这个列为主键
                    primaryKey = k
                # 最后将除__table__和primary_key之外的所有属性放入fields中，fields是上面定义的[]
                else:
                    fields.append(k)
        #到这里，我们将设置了主键和表名，将除__table__之外的属性放在mappings中，并将mappings的key(不包括主键)放在fields中

        # 没有找到主键，报错
        if not primaryKey:
            raise StandardError("Primary key not found.")
        #本来attrs中有各种各样的属性，现在，将除表名之外的属性全部删除
        for k in mappings.keys():
            attrs.pop(k)

        #到现在，我们从attrs中删除了除__table__之外的全部的属性，将其余的这些属性放到mappings中
        #将mappings中的key放到field列表中(不包括主键)，
        #对fields列表进行处理，对每一个字符串两边加上` `
        escaped_fields = list(map(lambda f: '`%s`' % f, fields))
        #依次对attrs加入这几个属性
        attrs['__mappings__'] = mappings  
        attrs['__table__'] = tableName  
        attrs["__primary_key__"] = primaryKey     
        attrs["__fields__"] = fields   
        # 构造默认的SELECT INSERT UPDATE DELETE语句
        # 分别作为attrs的属性
        #数据库的变量加上` `
        # select 主键, 除主键之外的所有属性 from tableName
        attrs["__select__"] = 'select `%s`, %s from `%s`' % (primaryKey, ', '.join(escaped_fields), tableName)
        # insert into tableName (各个属性如name, email等,主键) values (占位符)  +1 加的是主键的占位符
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (tableName, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
        # update tebleName set cust_name='zsb',cust_email='zhousbo@gmail.com' where cust_id=1005
        # 因此这里第一个%s为表名，第二个应该是表达式，第三个是主键名
        attrs['__update__'] = 'update `%s` set %s where `%s` = ?' % (tableName, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primaryKey)
        return type.__new__(cls, name, bases, attrs)

class Model(dict, metaclass=ModelMetaclass):
    # 创建Model类，首先对这个类进行元类处理
    def __init__(self, **kw):
        super(Model, self).__init__(**kw)

    # 使字典对象可以通过d.k的方式获取值
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'" % key)
    
    # 可以通过d.k=v的方式设置值
    def __setattr__(self, key, value):
        self[key] = value

    #没有与key对应的属性值就返回None
    def getValue(self, key):
        return getattr(self, key, None)

    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        #如果没有于key对应的属性值就使用下列方法
        if value is None:
            # 实例中找不到就到__mappings__中去寻找
            field = self.__mappings__[key]
            # 如果在__mappings__中找到了key
            if field.default is not None:
                # 如果是方法就返回调用后的值，具体的值就直接返回
                value = field.default() if callable(field.default) else field.default
                logger.debug("using default value for %s:%s" % (key, str(value)))
                # 找到之后就设置为属性
                setattr(self, key,value)
        return value

    # @classmethod是将其标记为类方法，可以不创建实例而直接调用类方法
    @classmethod
    async def findAll(cls, where=None, args=None, **kw):
        'find objects by where clause'   #通过条件查找
        sql = [cls.__select__]    #cls.__select__是'select `%s`, %s from `%s`'字符串
        # 如果传入的参数说要有where
        if where:
            #在sql语句中加入'where'和where变量，['select `%s`, %s from `%s`', 'where', "cust_id=1005"]
            sql.append("where")
            sql.append(where)    #这里的where应该是传入的变量，传入的应该是一个表达式，比如cust_id=1005之类条件的
        # 如果args是None，定义为[],这个args推测为原始select语句'select `%s`, %s from `%s`'中的中的3个参数
        if args is None:
            args = []
        # 从参数字典中取得oederBy的值
        orderBy = kw.get('orderBy', None)
        # 如果存在就添加，orderBy同样是一个条件，按照价格排序等，比如为price
        if orderBy:
            sql.append("order by")  #['select `%s`, %s from `%s`','where',"cust_id=1005"，'order by', "price"]
            sql.append(orderBy)
        # 看是否存在limit语句
        limit = kw.get('limit', None)
        # 如果存在limit
        if limit is not None:
            sql.append("limit") 
            # 传入的limit是一个int,返回前几行，比如为3 
            if isinstance(limit, int):
                sql.append("?")  #['select `%s`, %s from `%s`','where',"cust_id=1005"，'order by', "price", "limit", "?"]
                #在参数中添加传入的limit数字
                args.append(limit)
            # 如果是一个元组，表示从第2行开始的4行
            #不需要检查tuple里面的数字是不是int吗？
            elif isinstance(limit, tuple) and len(limit)==2:
                sql.append('?, ?')  #['select `%s`, %s from `%s`','where',"cust_id=1005",'order by', "price","limit", "?,?"]
                #将limit参数放到args中
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value: %s' % str(limit))
        # 将所有的用空格连接起来
        # rs = 'select `%s`, %s from `%s` where cust_id=1005 order by price limit ?,?', [xxx,yyy,zzz,2,3]
        #select在上已经封装好了，从这里调用没有传入size函数
        # rs是查询出来的结果，这里调用上面的select函数，返回的是列表，列表中的元素是字典
        rs = await select(' '.join(sql), args) 
        # cls(**r)不懂是什么意思
        return [cls(**r) for r in rs]

    @classmethod
    async def findNumber(cls, selectField, where=None, args=None):
        '  find number by select and where'    #根据where条件查询结果数，查询的是数量
        # selectField是选择的列名，_num_就是类似于count(account_id) as num
        #这里sql语句没有从类中继承
        sql = ['select %s `_num_` from `%s`' % (selectField, cls.__table__)]
        if where:
            sql.append('where')
        #这里传入了参数size，执行
        rs = await select(' '.join(sql), args, 1)
        if len(rs) == 0:
            return None
        return rs[0]["_num_"]

    @classmethod
    async def find(cls, pk):
        '  find object by primary key' #通过主键查找对象，cls是类的self,pk是主键
        # 分别将三个参数传入这个语句'select `%s`, %s from `%s`'，？？？这里不懂？？？？
        rs = await select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        # rs是查找的结果，为0 就是没找到返回None
        if len(rs) == 0:
            return None
        #这里这个cls代表的应该是Model这个类自己，创建了一个新的类
        return cls(**rs[0])

    async def save(self):
        # self.fields是其余的属性，依次对其使用getValueOrDefault进行处理，然后变成列表
        args = list(map(self.getValueOrDefault, self.__fields__))
        # 将主键放到最后
        args.append(self.getValueOrDefault(self.__primary_key__))
        #执行INSERT语句，第一个是表名，其余是各列的属性名，values后面是主键，最后是加"?"的函数
        #'insert into `%s` (%s, `%s`) values (%s)' % (tableName, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
        rows = await execute(self.__insert__, args)
        # 一次只能插入一行数据？
        if rows != 1:
            logger.warn('failed to insert record:affected rows: %s' % rows)

    async def update(self):
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        # 第一个是表名，第二个是表达式，第三个是主键
        #'update `%s` set %s where `%s` = ?'
        rows = await execute(self.__update__, args)
        if rows != 1:
            logger.warn("failed to update by primary key: affected rows: %s" % rows)

    async def remove(self):
        args = [self.getValue(self.__primary_key__)]
        # 第一个是表名，第二个是主键名
        # 'delete from `%s` where `%s`=?'
        rows = await execute(self.__delete__, args)
        if rows != 1:
            logger.warn("failed to remove by primary key: affected rows: %s" % rows)

