import time
import traceback
from typing import Optional, Union, Tuple, List

import qbittorrentapi
from qbittorrentapi import TorrentDictionary, TorrentFilesList
from qbittorrentapi.client import Client
from qbittorrentapi.transfer import TransferInfoDictionary

from app.log import logger
from app.utils.string import StringUtils


class Qbittorrent:
    """
    qbittorrent下载器
    """
    def __init__(self, host: Optional[str] = None, port: int = None,
                 username: Optional[str] = None, password: Optional[str] = None,
                 category: Optional[bool] = False, sequentail: Optional[bool] = False,
                 force_resume: Optional[bool] = False, first_last_piece=False,
                 **kwargs):
        """
        若不设置参数，则创建配置文件设置的下载器
        """
        if host and port:
            self._host, self._port = host, port
        elif host:
            self._host, self._port = StringUtils.get_domain_address(address=host, prefix=True)
        else:
            logger.error("Qbittorrent配置不完整！")
            return
        self._username = username
        self._password = password
        self._category = category
        self._sequentail = sequentail
        self._force_resume = force_resume
        self._first_last_piece = first_last_piece
        self.qbc = self.__login_qbittorrent()

    def is_inactive(self) -> bool:
        """
        判断是否需要重连
        """
        if not self._host or not self._port:
            return False
        return True if not self.qbc else False

    def reconnect(self):
        """
        重连
        """
        self.qbc = self.__login_qbittorrent()

    def __login_qbittorrent(self) -> Optional[Client]:
        """
        连接qbittorrent
        :return: qbittorrent对象
        """
        if not self._host or not self._port:
            return None
        try:
            # 登录
            logger.info(f"正在连接 qbittorrent：{self._host}:{self._port}")
            qbt = qbittorrentapi.Client(host=self._host,
                                        port=self._port,
                                        username=self._username,
                                        password=self._password,
                                        VERIFY_WEBUI_CERTIFICATE=False,
                                        REQUESTS_ARGS={'timeout': (15, 60)})
            try:
                qbt.auth_log_in()
            except (qbittorrentapi.LoginFailed, qbittorrentapi.Forbidden403Error) as e:
                logger.error(f"qbittorrent 登录失败：{str(e).strip() or '请检查用户名和密码是否正确'}")
                return None
            except Exception as e:
                stack_trace = "".join(traceback.format_exception(None, e, e.__traceback__))[:2000]
                logger.error(f"qbittorrent 登录失败：{str(e)}\n{stack_trace}")
                return None
            return qbt
        except Exception as err:
            logger.error(f"qbittorrent 连接出错：{str(err)}")
            return None

    def get_torrents(self, ids: Optional[Union[str, list]] = None,
                     status: Optional[str] = None,
                     tags: Optional[Union[str, list]] = None) -> Tuple[List[TorrentDictionary], bool]:
        """
        获取种子列表
        return: 种子列表, 是否发生异常
        """
        if not self.qbc:
            return [], True
        try:
            torrents = self.qbc.torrents_info(torrent_hashes=ids,
                                              status_filter=status)
            if tags:
                results = []
                if not isinstance(tags, list):
                    tags = [tags]
                try:
                    for torrent in torrents:
                        torrent_tags = [str(tag).strip() for tag in torrent.get("tags").split(',')]
                        if set(tags).issubset(set(torrent_tags)):
                            results.append(torrent)
                finally:
                    torrents.clear()
                    del torrents
                return results, False
            return torrents or [], False
        except Exception as err:
            logger.error(f"获取种子列表出错：{str(err)}")
            return [], True

    def get_completed_torrents(self, ids: Union[str, list] = None,
                               tags: Union[str, list] = None) -> Optional[List[TorrentDictionary]]:
        """
        获取已完成的种子
        return: 种子列表, 如发生异常则返回None
        """
        if not self.qbc:
            return None
        # completed会包含移动状态 改为获取seeding状态 包含活动上传, 正在做种, 及强制做种
        torrents, error = self.get_torrents(status="seeding", ids=ids, tags=tags)
        return None if error else torrents or []

    def get_downloading_torrents(self, ids: Union[str, list] = None,
                                 tags: Union[str, list] = None) -> Optional[List[TorrentDictionary]]:
        """
        获取正在下载的种子
        return: 种子列表, 如发生异常则返回None
        """
        if not self.qbc:
            return None
        torrents, error = self.get_torrents(ids=ids,
                                            status="downloading",
                                            tags=tags)
        return None if error else torrents or []

    def delete_torrents_tag(self, ids: Union[str, list], tag: Union[str, list]) -> bool:
        """
        删除Tag
        :param ids: 种子Hash列表
        :param tag: 标签内容
        """
        if not self.qbc:
            return False
        try:
            self.qbc.torrents_delete_tags(torrent_hashes=ids, tags=tag)
            return True
        except Exception as err:
            logger.error(f"删除种子Tag出错：{str(err)}")
            return False

    def remove_torrents_tag(self, ids: Union[str, list], tag: Union[str, list]) -> bool:
        """
        移除种子Tag
        :param ids: 种子Hash列表
        :param tag: 标签内容
        """
        if not self.qbc:
            return False
        try:
            self.qbc.torrents_remove_tags(torrent_hashes=ids, tags=tag)
            return True
        except Exception as err:
            logger.error(f"移除种子Tag出错：{str(err)}")
            return False

    def set_torrents_tag(self, ids: Union[str, list], tags: list):
        """
        设置种子状态为已整理，以及是否强制做种
        """
        if not self.qbc:
            return
        try:
            # 打标签
            self.qbc.torrents_add_tags(tags=tags, torrent_hashes=ids)
        except Exception as err:
            logger.error(f"设置种子Tag出错：{str(err)}")

    def is_force_resume(self) -> bool:
        """
        是否支持强制作种
        """
        return self._force_resume

    def torrents_set_force_start(self, ids: Union[str, list]):
        """
        设置强制作种
        """
        if not self.qbc:
            return
        if not self._force_resume:
            return
        try:
            self.qbc.torrents_set_force_start(enable=True, torrent_hashes=ids)
        except Exception as err:
            logger.error(f"设置强制作种出错：{str(err)}")

    def __get_last_add_torrentid_by_tag(self, tags: Union[str, list],
                                        status: Optional[str] = None) -> Optional[str]:
        """
        根据种子的下载链接获取下载中或暂停的钟子的ID
        :return: 种子ID
        """
        try:
            torrents, _ = self.get_torrents(status=status, tags=tags)
        except Exception as err:
            logger.error(f"获取种子列表出错：{str(err)}")
            return None
        if torrents:
            return torrents[0].get("hash")
        else:
            return None

    def get_torrent_id_by_tag(self, tags: Union[str, list],
                              status: Optional[str] = None) -> Optional[str]:
        """
        通过标签多次尝试获取刚添加的种子ID，并移除标签
        """
        torrent_id = None
        # QB添加下载后需要时间，重试10次每次等待3秒
        for i in range(1, 10):
            time.sleep(3)
            torrent_id = self.__get_last_add_torrentid_by_tag(tags=tags,
                                                              status=status)
            if torrent_id is None:
                continue
            else:
                self.delete_torrents_tag(torrent_id, tags)
                break
        return torrent_id

    def add_torrent(self,
                    content: Union[str, bytes],
                    is_paused: Optional[bool] = False,
                    download_dir: Optional[str] = None,
                    tag: Union[str, list] = None,
                    category: Optional[str] = None,
                    cookie: Optional[str] = None,
                    **kwargs
                    ) -> bool:
        """
        添加种子
        :param content: 种子urls或文件内容
        :param is_paused: 添加后暂停
        :param tag: 标签
        :param category: 种子分类
        :param download_dir: 下载路径
        :param cookie: 站点Cookie用于辅助下载种子
        :param kwargs: 可选参数，如 ignore_category_check 以及 QB相关参数
        :return: bool
        """
        if not self.qbc or not content:
            return False

        # 下载内容
        if isinstance(content, str):
            urls = content
            torrent_files = None
        else:
            urls = None
            torrent_files = content

        # 保存目录
        if download_dir:
            save_path = download_dir
        else:
            save_path = None

        # 标签
        if tag:
            tags = tag
        else:
            tags = None

        # 如果忽略分类检查，则直接使用传入的分类值，否则，仅在分类存在且启用了自动管理时才传递参数
        ignore_category_check = kwargs.pop("ignore_category_check", True)
        if ignore_category_check:
            is_auto = self._category
        else:
            if category and self._category:
                is_auto = True
            else:
                is_auto = False
                category = None
        try:
            # 添加下载
            qbc_ret = self.qbc.torrents_add(urls=urls,
                                            torrent_files=torrent_files,
                                            save_path=save_path,
                                            is_paused=is_paused,
                                            tags=tags,
                                            use_auto_torrent_management=is_auto,
                                            is_sequential_download=self._sequentail,
                                            is_first_last_piece_priority=self._first_last_piece,
                                            cookie=cookie,
                                            category=category,
                                            **kwargs)
            return True if qbc_ret and str(qbc_ret).find("Ok") != -1 else False
        except Exception as err:
            logger.error(f"添加种子出错：{str(err)}")
            return False

    def start_torrents(self, ids: Union[str, list]) -> bool:
        """
        启动种子
        """
        if not self.qbc:
            return False
        try:
            self.qbc.torrents_resume(torrent_hashes=ids)
            return True
        except Exception as err:
            logger.error(f"启动种子出错：{str(err)}")
            return False

    def stop_torrents(self, ids: Union[str, list]) -> bool:
        """
        暂停种子
        """
        if not self.qbc:
            return False
        try:
            self.qbc.torrents_pause(torrent_hashes=ids)
            return True
        except Exception as err:
            logger.error(f"暂停种子出错：{str(err)}")
            return False

    def delete_torrents(self, delete_file: bool, ids: Union[str, list]) -> bool:
        """
        删除种子
        """
        if not self.qbc:
            return False
        if not ids:
            return False
        try:
            self.qbc.torrents_delete(delete_files=delete_file, torrent_hashes=ids)
            return True
        except Exception as err:
            logger.error(f"删除种子出错：{str(err)}")
            return False

    def get_files(self, tid: str) -> Optional[TorrentFilesList]:
        """
        获取种子文件清单
        """
        if not self.qbc:
            return None
        try:
            return self.qbc.torrents_files(torrent_hash=tid)
        except Exception as err:
            logger.error(f"获取种子文件列表出错：{str(err)}")
            return None

    def set_files(self, **kwargs) -> bool:
        """
        设置下载文件的状态，priority为0为不下载，priority为1为下载
        """
        if not self.qbc:
            return False
        if not kwargs.get("torrent_hash") or not kwargs.get("file_ids"):
            return False
        try:
            self.qbc.torrents_file_priority(torrent_hash=kwargs.get("torrent_hash"),
                                            file_ids=kwargs.get("file_ids"),
                                            priority=kwargs.get("priority"))
            return True
        except Exception as err:
            logger.error(f"设置种子文件状态出错：{str(err)}")
            return False

    def transfer_info(self) -> Optional[TransferInfoDictionary]:
        """
        获取传输信息
        """
        if not self.qbc:
            return None
        try:
            return self.qbc.transfer_info()
        except Exception as err:
            logger.error(f"获取传输信息出错：{str(err)}")
            return None

    def set_speed_limit(self, download_limit: float = None, upload_limit: float = None) -> bool:
        """
        设置速度限制
        :param download_limit: 下载速度限制，单位KB/s
        :param upload_limit: 上传速度限制，单位kB/s
        """
        if not self.qbc:
            return False
        download_limit = download_limit * 1024
        upload_limit = upload_limit * 1024
        try:
            self.qbc.transfer.upload_limit = int(upload_limit)
            self.qbc.transfer.download_limit = int(download_limit)
            return True
        except Exception as err:
            logger.error(f"设置速度限制出错：{str(err)}")
            return False

    def get_speed_limit(self) -> Optional[Tuple[float, float]]:
        """
        获取QB速度
        :return: 返回download_limit 和upload_limit ，默认是0
        """
        if not self.qbc:
            return None

        download_limit = 0
        upload_limit = 0
        try:
            download_limit = self.qbc.transfer.download_limit
            upload_limit = self.qbc.transfer.upload_limit
        except Exception as err:
            logger.error(f"获取速度限制出错：{str(err)}")

        return download_limit / 1024, upload_limit / 1024

    def recheck_torrents(self, ids: Union[str, list]) -> bool:
        """
        重新校验种子
        """
        if not self.qbc:
            return False
        try:
            self.qbc.torrents_recheck(torrent_hashes=ids)
            return True
        except Exception as err:
            logger.error(f"重新校验种子出错：{str(err)}")
            return False

    def update_tracker(self, hash_string: str, tracker_list: list) -> bool:
        """
        添加tracker
        """
        if not self.qbc:
            return False
        try:
            self.qbc.torrents_add_trackers(torrent_hash=hash_string, urls=tracker_list)
            return True
        except Exception as err:
            logger.error(f"修改tracker出错：{str(err)}")
            return False

    def get_content_layout(self) -> Optional[str]:
        """
        获取内容布局
        """
        if not self.qbc:
            return None
        # 获取下载器全局设置
        application = self.qbc.application.preferences
        # 获取种子内容布局: `Original: 原始, Subfolder: 创建子文件夹, NoSubfolder: 不创建子文件夹`
        return application.get("torrent_content_layout", "Original")
