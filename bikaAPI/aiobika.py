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
        if token == "":
            asyncio.run(self.login())  # 登录获取token

    def _encrypt(self, url, method) -> str:
        """加密

        :param url: 请求地址
        :param method: 请求类型(POST/GET)
        :return:
        """
        ts = str(int(time.time()))
        self.headers["time"] = ts
        raw = url.replace(GLOBAL_URL, "") + str(ts) + self.uuid_s + method + API_KEY
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
        self.headers["signature"] = self._encrypt(url=url, method=("GET" if get else "POST"))
        async with httpx.AsyncClient(verify=False, timeout=1000, proxies=self.proxies) as client:
            action = eval("client.get") if get else eval("client.post")  # get 与 post判断
            if data:
                res = await action(url=url, headers=self.headers, json=data)
            else:
                res = await action(url=url, headers=self.headers)
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
        self.headers["signature"] = self._encrypt(url=GLOBAL_URL + api, method="POST")
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
        refer.__init__(account, password, token, proxy)
        if token is None:
            await refer.login()

    async def categories(self):
        """主目录

        :return: BikaCategories
        """
        api = "categories"
        return BikaCategories(res=await refer.submit(api=api))

    async def comics(self, title: str = "", page: int = 1, tag: str = "", sort: str = "ua"):
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
        return BikaBlock(data=await refer.submit(api=api, params=params))

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
        return BikaBlock(data=await refer.submit(api=api, params=params, data=data, get=False))

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
        return BikaBlock(data=await refer.submit(api=api, params=params))

    async def info(self, book_id: str = ""):
        """漫画信息

        :param book_id: 漫画id(必须)
        :return: BikaInfo
        """
        api = f"comics/{book_id}"
        logger.info(f"查看漫画,漫画id:{book_id}")
        return BikaInfo(data=await refer.submit(api=api))

    async def episodes(self, book_id: str = "", page: int = 1):
        """漫画分话

        :param page: 页码
        :param book_id: 漫画id
        :return:BikaEpisodes
        """
        api = f"comics/{book_id}/eps"
        params = {"page": str(page)}
        logger.info(f"漫画id:{book_id},页码:{page}")
        return BikaEpisodes(data=await refer.submit(api=api, params=params))

    async def picture(self, book_id: str = "", eps_id: int = 1, page: int = 1):
        """漫画本体

        :param book_id:漫画id
        :param page:页码
        :param eps_id:分话id
        :return:BikaPicture
        """
        if book_id== "" and eps_id == 1 and page == 1:
            book_id = self.book_id
            eps_id = self.eps_id
            page = self.page
        api = f"comics/{book_id}/order/{eps_id}/pages"
        params = {"page": str(page)}
        return BikaPagination(await refer.submit(api=api, params=params))

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


class BikaPicture:
    """漫画本体——>Picture

    """

    def __init__(self, data: dict, book_id, ep_id):
        self.id: Optional[str] = data["_id"]
        self.name: Optional[str] = data["originalName"]
        self.download_url: Optional[str] = f"{data['media']['fileServer']}/static/{data['media']['path']}"


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


class BikaPagination:
    """漫画分页

    """

    def __init__(self, data: dict):
        self.total: Optional[int] = data["data"]["pages"]["total"]
        self.page: Optional[int] = data["data"]["pages"]["page"]
        self.limit: Optional[int] = data["data"]["pages"]["limit"]
        self.ep: Optional[str] = data["data"]["ep"]


class BikaEpisodes:
    """漫画分话——>episodes

    """

    def __init__(self, data: dict):
        self.id: Optional[str] = data["_id"]
        self.title: Optional[str] = data["title"]
        self.order: Optional[str] = data["order"]
        self.updated_at: Optional[str] = data["updated_at"]


"""
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


def __info__(self):  # 格式化输出
    return logger.info(json.dumps(self.raw, indent=4, ensure_ascii=False))


def __repr__(self):
    return f'<BikaEpisodes(episodes={len(self.raw)},pages={str(self.pages)}>'


class BikaInfo:
    """漫画具体信息——>BikaInfo

    """

    def __init__(self, data: dict):
        self.id = data["data"]["comic"]["_id"]
        self.creator = data["data"]["comic"]["_creator"]
        self.title = data["data"]["comic"]["title"]
        self.description = data["data"]["comic"]["description"]
        self.thumb_name = data["data"]["comic"]["thumb"]["originalName"]
        self.thumb_url = f"{data['data']['comic']['thumb']['fileServer']}/static/{data['data']['comic']['thumb']['path']}"
        self.author = data["data"]["comic"]["author"]
        self.chineseTeam = data["data"]["comic"]["chineseTeam"]
        self.categories = data["categories"]
        self.tags = data["data"]["comic"]["tags"]
        self.pagesCount = data["data"]["comic"]["pagesCount"]
        self.epsCount = data["data"]["comic"]["epsCount"]
        self.finished = data["data"]["comic"]["finished"]
        self.updated_at = data["data"]["comic"]["updated_at"]
        self.created_at = data["data"]["comic"]["created_at"]
        self.allowDownload = data["data"]["comic"]["allowDownload"]
        self.allowComment = data["data"]["comic"]["allowComment"]
        self.total_likes = data["data"]["comic"]["totalLikes"]
        self.total_views = data["data"]["comic"]["totalViews"]
        self.viewsCount = data["data"]["comic"]["viewsCount"]
        self.likesCount = data["data"]["comic"]["likesCount"]
        self.is_favourite = data["data"]["comic"]["isFavourite"]
        self.is_liked = data["data"]["comic"]["isLiked"]
        self.comments_count = data["data"]["comic"]["commentsCount"]


class BikaComic:
    """漫画信息——>Comic

    """

    def __init__(self, data: dict):
        self.id = data["_id"]
        self.title = data["title"]
        self.thumb_name = data["thumb"]["originalName"]
        self.thumb_url = f"{data['thumb']['fileServer']}/static/{data['thumb']['path']}"
        self.description = data["description"]
        self.categories = data["categories"]
        self.updated_at = data["updated_at"]
        self.created_at = data["created_at"]
        self.finished = data["finished"]
        self.tags = data["tags"]
        self.total_likes = data["totalLikes"]
        self.total_views = data["totalViews"]
        self.likes_count = data["likesCount"]


class BikaBlock:  # Comics
    """搜索与分区——>Block(Comics)

    """

    def __init__(self, data: dict):
        self.total = data["data"]["comics"]["total"]
        self.page = data["data"]["comics"]["page"]
        self.pages = data["data"]["comics"]["pages"]
        self.limit = data["data"]["comics"]["limit"]

    # def __info__(self):  # 格式化输出
    # return logger.info(json.dumps(self.raw, indent=4, ensure_ascii=False))

    def __repr__(self):
        return f'<BikaBlock(total={str(self.total)},page={str(self.page)}/{str(self.pages)}>'


class BikaCategories:
    """主目录——>Categories

    """

    def __init__(self, res: dict, book_id, eps_id, page):
        # super().__init__(book_id=book_id, eps_id=eps_id, page=page, API=API)
        self.raw = res["data"]["categories"]

    def slice(self):
        pass
