#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio

import hmac
import json
import time

import uuid
from typing import Any, Dict, Optional, List, Union

import httpx
import hashlib
from urllib import parse

from loguru import logger

GLOBAL_URL = "https://picaapi.picacomic.com/"
API_KEY = "C69BAF41DA5ABD1FFEDC6D2FEA56B"
SECRET_KEY = "~d}$Q7$eIni=V)9\\RK/P.RM4;9[7|@/CA}b~OW!3?EV`:<>M7pddUBL5n|0/*Cn"
# uuid_s = str(uuid.uuid4()).replace("-", "")
HEADERS = {
    "api-key": "C69BAF41DA5ABD1FFEDC6D2FEA56B",
    "accept": "application/vnd.picacomic.com.v1+json",
    "app-channel": "2",
    "time": 0,
    "nonce": "",
    "signature": "encrypt",
    "app-version": "2.2.1.2.3.4",
    "app-uuid": "418e56fb-60fb-352b-8fca-c6e8f0737ce6",
    "app-platform": "android",
    "app-build-version": "45",
    "Content-Type": "application/json; charset=UTF-8",
    "User-Agent": "okhttp/3.8.1",
}
SORT_NAME = {"ua": "默认",
             "dd": "新->旧",
             "da": "旧->新",
             "ld": "最多爱心",
             "vd": "最多指名"}


def run_time(fc):  # 测试运行时间
    start = time.clock()
    fc()
    end = time.clock()
    logger.debug(f'{fc.__name__}fcRunning time: {end - start} Seconds')


class AIORefer:
    """提供http访问 基类

    """

    def __init__(self, account="", password="", token="", proxy=None):
        self.account = account
        self.password = password
        self.proxies = proxy
        self.headers = HEADERS.copy()
        self.uuid_s = str(uuid.uuid4()).replace("-", "")
        self.headers["nonce"] = self.uuid_s
        self.headers["authorization"] = token

    def _encrypt(self, url, method) -> str:
        """加密

        :param url: 请求地址
        :param method: 请求类型(POST/GET)
        :return:
        """
        ts = str(int(time.time()))
        self.headers["time"] = ts
        raw = url.replace(GLOBAL_URL, "") + ts + self.uuid_s + method + API_KEY
        raw = raw.lower()
        hc = hmac.new(SECRET_KEY.encode(), digestmod=hashlib.sha256)
        hc.update(raw.encode())
        return hc.hexdigest()

    @staticmethod
    def _remake(url: str = "", params: dict = None) -> str:
        """重构url

        :param url: 重构的url
        :param params: params
        :return: 重构后url
        """
        if params:
            return f"{url}?" + "&".join([f"{str(v[0])}={str(v[1])}" for v in list(params.items())])
        else:
            return url

    async def submit(self, api: str = "", data=None, params: dict = None, get: bool = True):
        """请求

        :param api: api名称
        :param data: body
        :param params: params
        :param get: 是否是get
        :return: dict
        """

        url = self._remake(url=GLOBAL_URL + api, params=params)
        method = "GET" if get else "POST"
        self.headers["signature"] = self._encrypt(url=url, method=method)
        async with httpx.AsyncClient(verify=False, timeout=1000, proxies=self.proxies) as client:
            if get:
                if data:
                    res = await client.get(url=url, headers=self.headers, json=data)
                else:
                    res = await client.get(url=url, headers=self.headers)
            else:
                if data:
                    res = await client.post(url=url, headers=self.headers, json=data)
                else:
                    res = await client.post(url=url, headers=self.headers)

            logger.info(res.json())

            if res.json()["code"] == 401 and res.json()["error"] == "1005":  # token过期重载函数
                logger.error("TOKEN过期，正在尝试重新获取")
                await self.login()
                return await self.submit(api=api, data=data, get=get)
            return res.json()

    async def login(self):
        """登录 获取token

        """
        api = "auth/sign-in"
        send = {"email": self.account, "password": self.password}
        res = await self.submit(api=api, data=send, get=False)
        if res["code"] == 200:
            self.headers["authorization"] = res["data"]["token"]
            logger.success("TOKEN获取成功")
        elif res["code"] == 400:
            if res["error"] == "發現重大版本更新":
                logger.error("發現重大版本更新,请及时更新headers")
            elif res["error"] == "1004":
                logger.error("错误的账号或密码,请重试:(")
        else:
            logger.error("TOKEN获取失败,请重试:(")


refer = AIORefer()  # 实例化


class AIOBikaAPI:

    def __init__(self,
                 account: Optional[str] = None,
                 password: Optional[str] = None,
                 token: Optional[str] = None,
                 proxy: Optional[str] = None
                 ):
        if account:
            refer.__init__(account, password, token, proxy)
        self.category = None
        self.book_id = None
        self.eps_id = None
        self.eps_order = None
        self.eps_counts = None
        self.page = None
        self.pages = None

    @staticmethod
    async def categories():
        """主目录

        :return: BikaCategories
        """
        api = "categories"
        return BikaCategories(res=await refer.submit(api=api))

    async def comics(self, title: str = "", page: int = 1, tag: str = "", sort: str = "ua", initial=False):
        """分区


        :param page: 分页，从1开始 (可选)
        :param title: 分区名字，categories里面的title，如"嗶咔漢化"(必须)
        :param tag: 标签的名字，由info返回数据里面的"tags"获得 (可选)
        :param sort: 排序依据 (可选)
                ua: 默认
                dd: 新到旧
                da: 旧到新
                ld: 最多爱心
                vd: 最多指名
        :param initial: 用于初始化BikaBlock(无需使用)
        :return: BikaBlock
        """
        api = "comics"
        params = {
            "page": str(page),
            "c": parse.quote(title),
            "s": sort
        }
        if tag:
            params["t"] = parse.quote(tag)
        logger.info(f"查看分区:{title},页码:{page},排序:{SORT_NAME[sort]}")
        res = await refer.submit(api=api, params=params)
        if initial:
            return res
        else:
            return BikaBlock().initial(res=res)

    @staticmethod
    async def advanced_search(categories: list = None, sort: str = "ua", *, page: int = 1, keyword: str = ""):
        """搜索

        :param page: 分页，从1开始(必须)
        :param keyword: 关键词(必须)
        :param categories: 分区(可选)
        :param sort: (可选)
            ua: 默认
            dd: 新到旧
            da: 旧到新
            ld: 最多爱心
            vd: 最多指名
        :return: BikaBlock
        """
        api = "comics/advanced-search"
        params = {"page": str(page)}
        data = {
            "keyword": keyword,
            "sort": sort
        }
        if categories:
            data["categories"] = categories
        logger.info(f"搜索:{keyword},页码:{page},分区:{categories},排序:{SORT_NAME[sort]}")
        return BikaBlock().initial(res=await refer.submit(api=api, params=params, data=data, get=False))

    @staticmethod
    async def tags(page: int = 1, sort: str = "ua", *, tag: str = ""):
        """查找标签

        :param page: 分页，从1开始(必须)
        :param tag: 标签的名字，由info返回数据里面的"tags"获得(必须)
        :param sort: (可选)
            ua: 默认
            dd: 新到旧
            da: 旧到新
            ld: 最多爱心
            vd: 最多指名
        :return: BikaBlock
        """
        api = f"comics"
        params = {
            "page": str(page),
            "t": parse.quote(tag)
        }
        logger.info(f"搜索标签:{tag},页码:{page},排序:{SORT_NAME[sort]}")
        return BikaBlock().initial(res=await refer.submit(api=api, params=params))

    async def info(self, book_id: str = "", initial=False):
        """漫画信息

        :param book_id: 漫画id(必须)
        :param initial: 用于初始化BikaInfo(无需使用)
        :return: BikaInfo
        """
        api = f"comics/{book_id}"
        logger.info(f"查看漫画,漫画id:{book_id}")
        res = await refer.submit(api=api)
        if initial:
            return res
        else:
            return BikaInfo().initial(res=res)

    async def episodes(self, book_id: str = "", page: int = 1, initial=False):
        """漫画分话

        :param page: 页码
        :param book_id: 漫画id
        :param initial: 用于初始化BikaEpisodes(无需使用)
        :return:BikaEpisodes
        """
        api = f"comics/{book_id}/eps"
        params = {"page": str(page)}
        logger.info(f"漫画id:{book_id},页码:{page}")
        res = await refer.submit(api=api, params=params)
        if initial:
            return res
        else:
            return BikaEpisodes().initial(res=res)

    async def picture(self, book_id: str = "", eps_id: int = 1, page: int = 1, initial=False):
        """漫画本体

        :param book_id:漫画id
        :param page:页码
        :param eps_id:分话id
        :param initial: 用于初始化BikaBlock(无需使用)
        :return:BikaPicture
        """
        if book_id == "" and eps_id == 1 and page == 1:
            book_id = self.book_id
            eps_id = self.eps_id
            page = self.page
        api = f"comics/{book_id}/order/{eps_id}/pages"
        params = {"page": str(page)}
        res = await refer.submit(api=api, params=params)
        if initial:
            return res
        else:
            return BikaPagination().initial(res=res)

    async def downloader(self):  # 下载器
        pass

    async def recommend(self):  # 看了這本子的人也在看
        pass

    async def keyword(self):  # 大家都在搜
        pass

    async def like(self):  # 标记(不)喜欢此漫画
        pass

    async def get_comments(self):  # 获取评论
        pass

    async def send_comment(self):  # 发表评论
        pass

    async def favourite(self):  # (取消)收藏
        pass

    async def game(self):  # 游戏区
        pass

    async def game_info(self):  # 游戏信息
        pass

    async def my_info(self):  # 个人信息
        pass

    async def my_favourite(self):  # 已收藏漫画
        pass

    async def my_comment(self):  # 我的评论
        pass

    async def change_password(self):  # 修改密码
        pass


class BikaRaw:
    def __init__(self):
        pass


class BikaPicture(AIOBikaAPI):
    """漫画本体——>Picture

    可用方法:

    pre_page(): 上一张

    next_page():下一张

    download(): 下载当前页

    categories(): 主目录

    comics(title=""): 前往分区


    """

    def __init__(self,
                 data: dict = None,
                 ):
        super().__init__()
        # self.category: List[str] = category
        # self.book_id: Optional[str] = book_id
        # self.eps_id: Optional[str] = eps_id
        # self.eps_order: Optional[int] = eps_order
        # self.eps_orders: Optional[int] = eps_orders
        # self.page: Optional[int] = page
        # self.pages: Optional[int] = pages
        self.pic_id: str = data["_id"]
        self.pic_name: str = data["originalName"]
        self.download_url: str = f"{data['media']['fileServer']}/static/{data['media']['path']}"

    def next_page(self):
        pass


"""
    def download(self, page=None, proxies=None):
        if page > 0:
            url = f"{self.raw[page - 1]['media']['fileServer']}/static/info['media']['path']"
            asyncio.run(
                self._downloader(url=url, filename=self.raw[page - 1]['media']['originalName'], proxies=proxies))
        else:
            loop = asyncio.new_event_loop()
            tasks = [asyncio.ensure_future(
                self._downloader(url=f"{info['media']['fileServer']}/static/info['media']['path']",
                                 filename=info['media']['originalName'], proxies=proxies)) for info in self.raw]
            loop.run_until_complete(asyncio.wait(tasks))

    @staticmethod
    async def _downloader(url="", filename="", proxies=None):
        async with httpx.AsyncClient(verify=False, timeout=1000, proxies=proxies) as client:
            with httpx.stream("GET", url=url) as r:
                with open(filename, 'wb') as fd:
                    for data in r.iter_bytes():
                        fd.write(data)
                logger.success(f"{filename}下载完成")

    def __info__(self):  # 格式化输出
        return logger.info(json.dumps(self.raw, indent=4, ensure_ascii=False))

    def __repr__(self):
        return f'<BikaEpisodes(episodes={len(self.raw)},pages={str(self.pages)}>'

"""


class BikaPagination(AIOBikaAPI):
    """漫画分页

    """

    def __init__(self, data: dict = None):
        super().__init__()
        if data:
            self.eps_id = data["_id"]
            self.eps_title = data["title"]
            self.eps_order = data["order"]
            self.update_at = data["update_at"]

        # ------------------ 自我构建后(initial) ------------------
        self.children = None
        self.pages = None
        self.eps_order = None
        self.eps_count = None
        self.eps_id = None
        self.eps_title = None

    def initial(self, res=None):
        self.children = [BikaPicture(x) for x in res["data"]["pages"]["docs"]]
        self.pages = res["data"]["pages"]["total"]
        self.eps_order = res["data"]["pages"]["page"]
        self.eps_counts = res["data"]["pages"]["pages"]
        self.eps_id = res["data"]["ep"]["_id"]
        self.eps_title = res["data"]["ep"]["title"]


    # TODO 上下级操作
    # TODO 自动识别调用


class BikaEpisodes(AIOBikaAPI):
    """漫画分话——>episodes

    """

    def __init__(self, data: dict, eps_order=0):
        super().__init__()
        self.eps_count: int = data["epsCount"]
        # ------------------ 自我构建后(initial) ------------------
        self.children = None
        self.eps_count = None
        self.eps_counts = None

    def initial(self, res=None):
        self.children = [BikaPagination(x) for x in res["data"]["eps"]["docs"]]
        self.eps_count = res["data"]["eps"]["page"]
        self.eps_counts = res["data"]["eps"]["total"]

    async def child(self, order: int = 0) -> Union[List[BikaPagination], BikaPagination]:
        """获取第 order 的初始化后的子对象->分页

        :param order: 序号 从1开始(0时为全部)
        :return: 子对象 BikaPagination(order=0时为列表)
        """
        if order != 0:
            res = await super().picture(book_id=self.book_id, page=self.children[order - 1].eps_count, initial=True)
            self.children[order - 1].initial(res=res)
            return self.children[order - 1]
        else:  # TODO 全部
            pass
    # TODO 上下级操作
    # TODO 自动识别调用


"""
def __info__(self):  # 格式化输出
    return logger.info(json.dumps(self.raw, indent=4, ensure_ascii=False))


def __repr__(self):
    return f'<BikaEpisodes(episodes={len(self.raw)},pages={str(self.pages)}>'

    def child(self, pagination: Optional[int] = None) -> Union[List[BikaPagination], BikaPagination]:
        获取分页
        :param pagination: 获取分页位置，默认获取全部，可指定分页
        :return: 子类

        if pagination:
            api = f"comics/{book_id}/eps"
            params = {
                "page": str(pagination)
            }
            logger.info(f"漫画id:{book_id},页码:{pagination}")
            return await self.submit(api=api, params=params)
"""


class BikaInfo(AIOBikaAPI):
    """漫画具体信息——>BikaInfo

    """

    def __init__(self, data: dict = None):
        super().__init__()
        self.children = None
        if data:
            self.book_id = data["_id"]
            self.title = data["title"]
            self.author = data["author"]
            if 'totalViews' in data.keys():
                self.total_views = data["totalViews"]
            if 'isWeg' in data.keys():
                self.total_likes = data["totalLikes"]
            self.pages_count = data["pagesCount"]
            self.eps_count = data["epsCount"]
            self.finished = data["finished"]
            self.categories = data["categories"]
            self.thumb_name = data["thumb"]["originalName"]
            self.thumb_url = f"{data['thumb']['fileServer']}/static/{data['thumb']['path']}"
            self.likes_count = data["likesCount"]
        # ------------------ 自我构建后(initial) ------------------
        self.creator = None
        self.description = None
        self.chineseTeam = None
        self.tags = None
        self.updated_at = None
        self.created_at = None
        self.allowDownload = None
        self.allowComment = None
        self.viewsCount = None
        self.is_favourite = None
        self.is_liked = None
        self.comments_count = None

    def initial(self, res=None):
        self.creator = res["data"]["comic"]["_creator"]
        self.description = res["data"]["comic"]["description"]
        self.chineseTeam = res["data"]["comic"]["chineseTeam"]
        self.tags = res["data"]["comic"]["tags"]
        self.updated_at = res["data"]["comic"]["updated_at"]
        self.created_at = res["data"]["comic"]["created_at"]
        self.allowDownload = res["data"]["comic"]["allowDownload"]
        self.allowComment = res["data"]["comic"]["allowComment"]
        self.viewsCount = res["data"]["comic"]["viewsCount"]
        self.is_favourite = res["data"]["comic"]["isFavourite"]
        self.is_liked = res["data"]["comic"]["isLiked"]
        self.comments_count = res["data"]["comic"]["commentsCount"]
        self.children = [BikaEpisodes(x) for x in res["data"]["comics"]["docs"]]

    async def child(self, order: int = 0) -> Union[List[BikaEpisodes], BikaEpisodes]:
        """获取第 order 的初始化后的子对象->分话

        :param order: 序号 从1开始(0时为全部)
        :return: 子对象 BikaEpisodes(order=0时为列表)
        """
        if order != 0:
            res = await super().episodes(book_id=self.book_id, page=self.children[order - 1].eps_count, initial=True)
            self.children[order - 1].initial(res=res)
            return self.children[order - 1]
        else:  # TODO 全部
            pass
    # TODO 上下级操作
    # TODO 自动识别调用


class BikaBlock(AIOBikaAPI):  # Comics
    """搜索与分区——>Block(Comics)

    """

    def __init__(self, data: dict = None):
        super().__init__()
        if data:
            self.title = data["title"]
            self.thumb_name = data["thumb"]["originalName"]
            self.thumb_url = f"{data['thumb']['fileServer']}/static/{data['thumb']['path']}"
            if 'isWeg' in data.keys():
                self.is_web = data["isWeb"]
            if 'link' in data.keys():
                self.link = data["link"]
            if 'active' in data.keys():
                self.active = data["active"]
            if 'id' in data.keys():
                self.categories_id = data["_id"]
        # ------------------ 自我构建后(initial) ------------------
        self.total = None
        self.comic_page = None
        self.comic_pages = None
        self.comic_limit = None
        self.children = None

    def initial(self, res=None):
        self.total = res["data"]["comics"]["total"]
        self.comic_page = res["data"]["comics"]["page"]
        self.comic_pages = res["data"]["comics"]["pages"]
        self.comic_limit = res["data"]["comics"]["limit"]
        self.children = [BikaInfo(x) for x in res["data"]["comics"]["docs"]]

    async def child(self, order: int = 0) -> Union[List[BikaInfo], BikaInfo]:
        """获取第 order 的初始化后的子对象->漫画信息

        :param order: 序号 从1开始(0时为全部)
        :return: 子对象 BikaBlock(order=0时为列表)
        """
        if order != 0:
            res = await super().info(book_id=self.children[order - 1].id, initial=True)
            self.children[order - 1].initial(res=res)
            return self.children[order - 1]
        else:  # TODO 全部
            pass
    # TODO 上下级操作
    # TODO 自动识别调用


class BikaCategories(AIOBikaAPI):
    """主目录——>Categories

    """

    def __init__(self, res: dict):
        super().__init__()
        self.children: List[BikaBlock] = [BikaBlock(x) for x in res["data"]["categories"]]

    async def child(self, order: int == 0) -> Union[List[BikaBlock], BikaBlock]:
        """获取第 order 的初始化后的子对象->分区

        :param order: 序号 从1开始(0时为全部)
        :return: 子对象 BikaBlock(order=0时为列表)
        """
        if order != 0:
            res = await super().comics(title=self.children[order - 1].title, initial=True)
            self.children[order - 1].initial(res=res)
            return self.children[order - 1]
        else:  # TODO 全部
            pass
    # TODO 上下级操作
    # TODO 自动识别调用
