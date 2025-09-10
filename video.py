#!/usr/bin/env python3
"""
Bilibili视频下载核心模块

提供VideoDownloader类，负责视频下载的核心功能：
- 凭据管理
- 视频信息获取
- 视频文件下载
- 音视频合并处理
"""

import asyncio
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List

import aiohttp
import aiofiles
from bilibili_api import video, HEADERS, Credential, user
from bilibili_api.video import VideoQuality
from bilibili_api.channel_series import ChannelSeries, ChannelSeriesType, ChannelOrder


class VideoDownloader:
    """B站视频下载器核心类"""
    
    def __init__(self, credential: Optional[Credential] = None, preferred_quality: str = "auto"):
        """
        初始化下载器
        
        Args:
            credential: B站登录凭据(用于高画质下载)
            preferred_quality: 首选画质(auto/1080p60/4k/8k等)
        """
        self.credential = credential
        self.preferred_quality = preferred_quality
        
        # 设置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs.txt'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('VideoDownloader')
        
        # 输出登录状态和画质信息
        if self.credential:
            self.logger.info("✅ 已加载登录凭据，支持高画质下载")
        else:
            self.logger.info("⚠️  未提供登录凭据，将使用普通画质下载")
        self.logger.info(f"🎬 画质偏好: {self.preferred_quality}")
    
    @staticmethod
    def load_credentials(config_path: Optional[str] = None) -> Optional[Credential]:
        """
        从配置文件或环境变量加载登录凭据
        
        Args:
            config_path: 配置文件路径 (JSON格式)
            
        Returns:
            Credential对象，如果无法加载则返回None
        """
        # 尝试从环境变量加载
        sessdata = os.getenv('BILI_SESSDATA')
        bili_jct = os.getenv('BILI_JCT')
        buvid3 = os.getenv('BILI_BUVID3')
        dedeuserid = os.getenv('BILI_DEDEUSERID')
        ac_time_value = os.getenv('BILI_AC_TIME_VALUE')
        
        # 尝试从配置文件加载
        if config_path and Path(config_path).exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    sessdata = config.get('SESSDATA', sessdata)
                    bili_jct = config.get('bili_jct', bili_jct)
                    buvid3 = config.get('buvid3', buvid3)
                    dedeuserid = config.get('DedeUserID', dedeuserid)
                    ac_time_value = config.get('ac_time_value', ac_time_value)
            except Exception as e:
                print(f"⚠️  配置文件加载失败: {e}")
        
        # 检查必需的凭据
        if not sessdata:
            return None
            
        try:
            # 创建凭据对象
            credential = Credential(
                sessdata=sessdata,
                bili_jct=bili_jct or "",
                buvid3=buvid3 or "",
                dedeuserid=dedeuserid or "",
                ac_time_value=ac_time_value or ""
            )
            return credential
        except Exception as e:
            print(f"⚠️  凭据创建失败: {e}")
            return None
    
    def get_safe_filename(self, title: str, bvid: str) -> str:
        """生成安全的文件名"""
        # 清理标题中的非法字符
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_', '.')).strip()
        safe_title = safe_title[:50]  # 限制长度
        
        return f"{safe_title}_{bvid}.mp4"
    
    async def get_video_info(self, bvid: str) -> Dict:
        """获取单个视频信息"""
        try:
            v = video.Video(bvid=bvid)
            info = await v.get_info()
            return info
        except Exception as e:
            self.logger.error(f"获取视频信息失败: {e}")
            return {}
    
    async def download_file(self, url: str, file_path: Path, desc: str = "下载") -> bool:
        """下载单个文件"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=HEADERS) as response:
                    if response.status == 200:
                        total_size = int(response.headers.get('content-length', 0))
                        downloaded = 0
                        
                        async with aiofiles.open(file_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                await f.write(chunk)
                                downloaded += len(chunk)
                                if total_size > 0:
                                    progress = (downloaded / total_size) * 100
                                    print(f"\r{desc}: {progress:.1f}% ({downloaded}/{total_size})", end="")
                        print()  # 换行
                        return True
                    else:
                        self.logger.error(f"{desc}失败: HTTP {response.status}")
                        return False
        except Exception as e:
            self.logger.error(f"{desc}出错: {e}")
            return False
    
    async def download_single_video(self, bvid: str, download_folder: Path, semaphore: Optional[asyncio.Semaphore] = None) -> bool:
        """
        下载单个视频
        
        Args:
            bvid: 视频BVID
            download_folder: 下载目录
            semaphore: 并发控制信号量
            
        Returns:
            下载成功返回True，失败返回False
        """
        # 如果提供了信号量，使用它进行并发控制
        if semaphore:
            async with semaphore:
                return await self._download_video_impl(bvid, download_folder)
        else:
            return await self._download_video_impl(bvid, download_folder)
    
    async def _download_video_impl(self, bvid: str, download_folder: Path) -> bool:
        """下载视频的具体实现"""
        try:
            # 获取视频信息
            info = await self.get_video_info(bvid)
            if not info:
                print(f"无法获取视频信息: {bvid}")
                return False
            
            title = info['title']
            print(f"\n视频信息:")
            print(f"标题: {title}")
            print(f"UP主: {info.get('owner', {}).get('name', 'Unknown')}")
            print(f"时长: {info.get('duration', 'Unknown')}秒")
            print(f"播放量: {info.get('stat', {}).get('view', 'Unknown')}")
            
            filename = self.get_safe_filename(title, bvid)
            final_path = download_folder / filename
            
            # 检查文件是否已存在
            if final_path.exists():
                print(f"视频已存在: {filename}")
                return True
            
            print(f"\n开始下载: {title}")
            
            # 创建视频对象并获取下载链接
            v = video.Video(bvid=bvid, credential=self.credential)
            download_url_data = await v.get_download_url(0)
            
            # 解析下载数据
            detecter = video.VideoDownloadURLDataDetecter(data=download_url_data)
            streams = detecter.detect_best_streams()
            
            # 显示获得的最佳画质信息
            if streams:
                best_quality = streams[0].video_quality
                quality_names = {
                    16: "360P", 32: "480P", 64: "720P", 80: "1080P", 
                    112: "1080P+", 116: "1080P60", 120: "4K", 125: "HDR", 126: "杜比视界", 127: "8K"
                }
                quality_name = quality_names.get(best_quality.value, f"质量码{best_quality.value}")
                auth_status = "🔓 会员画质" if self.credential else "🔒 普通画质"
                print(f"📺 获得画质: {quality_name} ({auth_status})")
            
            if not streams:
                print(f"无法获取视频流: {title}")
                return False
            
            # 检查流类型并下载
            if detecter.check_flv_mp4_stream():
                # FLV/MP4 流 - 直接下载
                temp_file = download_folder / f"temp_{bvid}.flv"
                success = await self.download_file(streams[0].url, temp_file, f"下载 {title}")
                
                if success:
                    # 使用 ffmpeg 转换格式
                    result = os.system(f'ffmpeg -i "{temp_file}" -c copy "{final_path}" -y > /dev/null 2>&1')
                    temp_file.unlink(missing_ok=True)
                    
                    if result == 0:
                        print(f"✅ 下载完成: {filename}")
                        return True
                    else:
                        print(f"❌ 视频转换失败: {title}")
                        return False
            else:
                # DASH 流 - 音视频分离
                video_temp = download_folder / f"temp_video_{bvid}.m4s"
                audio_temp = download_folder / f"temp_audio_{bvid}.m4s"
                
                # 下载视频流和音频流
                video_success = await self.download_file(streams[0].url, video_temp, f"下载视频流")
                if video_success and len(streams) > 1:
                    audio_success = await self.download_file(streams[1].url, audio_temp, f"下载音频流")
                else:
                    audio_success = True  # 只有视频流的情况
                
                if video_success:
                    # 使用 ffmpeg 合并音视频
                    if len(streams) > 1 and audio_success:
                        cmd = f'ffmpeg -i "{video_temp}" -i "{audio_temp}" -c copy "{final_path}" -y > /dev/null 2>&1'
                    else:
                        cmd = f'ffmpeg -i "{video_temp}" -c copy "{final_path}" -y > /dev/null 2>&1'
                    
                    result = os.system(cmd)
                    
                    # 清理临时文件
                    video_temp.unlink(missing_ok=True)
                    audio_temp.unlink(missing_ok=True)
                    
                    if result == 0:
                        print(f"✅ 下载完成: {filename}")
                        return True
                    else:
                        print(f"❌ 视频合并失败: {title}")
                        return False
                        
        except Exception as e:
            print(f"❌ 下载失败: {e}")
            return False
            
        return False
    
    def check_ffmpeg(self) -> bool:
        """检查系统是否安装了ffmpeg"""
        return os.system("ffmpeg -version > /dev/null 2>&1") == 0


class BilibiliVideoManager:
    """Bilibili视频管理器 - 整合视频、用户、合集相关功能"""
    
    def __init__(self, download_dir: str = "downloads", max_concurrent: int = 3, 
                 credential: Optional[Credential] = None, preferred_quality: str = "auto"):
        """
        初始化管理器
        
        Args:
            download_dir: 下载目录
            max_concurrent: 最大并发下载数
            credential: B站登录凭据(用于高画质下载)
            preferred_quality: 首选画质(auto/1080p60/4k/8k等)
        """
        self.download_dir = Path(download_dir)
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.credential = credential
        
        # 创建视频下载器
        self.downloader = VideoDownloader(credential=credential, preferred_quality=preferred_quality)
        # 使用专门的管理器日志记录器
        self.logger = logging.getLogger('VideoManager')
    
    async def get_user_info(self, uid: int) -> Dict:
        """获取用户信息"""
        try:
            user_obj = user.User(uid)
            info = await user_obj.get_user_info()
            return info
        except Exception as e:
            self.logger.error(f"获取用户信息失败: {e}")
            return {}
    
    def create_download_folder(self, user_info: Dict, uid: int) -> Path:
        """创建下载文件夹"""
        if user_info:
            username = user_info.get('name', f'UID_{uid}')
        else:
            username = f'UID_{uid}'
            
        # 清理文件名中的非法字符
        username = "".join(c for c in username if c.isalnum() or c in (' ', '-', '_')).strip()
        
        user_folder = self.download_dir / f"{username}_{uid}"
        user_folder.mkdir(parents=True, exist_ok=True)
        
        return user_folder
    
    async def download_single_video(self, bvid: str, download_folder: Path = None) -> bool:
        """下载单个视频"""
        if download_folder is None:
            download_folder = self.download_dir
            download_folder.mkdir(parents=True, exist_ok=True)
        
        # 检查ffmpeg
        if not self.downloader.check_ffmpeg():
            print("⚠️  警告: 未找到 ffmpeg，可能无法正确处理某些视频")
            print("请安装 ffmpeg: https://ffmpeg.org/")
        
        return await self.downloader.download_single_video(bvid, download_folder)
    
    async def list_user_videos_data(self, uid: int) -> List[Dict]:
        """获取用户所有投稿视频数据"""
        user_obj = user.User(uid)
        all_videos = []
        page = 1
        
        self.logger.info(f"正在获取用户 {uid} 的视频列表...")
        
        while True:
            try:
                videos_data = await user_obj.get_videos(pn=page, ps=30)
                videos = videos_data.get('list', {}).get('vlist', [])
                
                if not videos:
                    break
                    
                all_videos.extend(videos)
                
                # 检查是否还有更多页
                if len(videos) < 30:
                    break
                    
                page += 1
                await asyncio.sleep(0.5)  # 避免请求过快
                
            except Exception as e:
                self.logger.error(f"获取第{page}页视频列表失败: {e}")
                break
        
        return all_videos
    
    async def list_user_videos(self, uid: int) -> None:
        """列出用户所有视频"""
        # 获取用户信息
        user_info = await self.get_user_info(uid)
        if not user_info:
            print(f"❌ 无法获取用户信息，请检查用户ID: {uid}")
            return
        
        username = user_info.get('name', 'Unknown')
        print(f"\n用户：{username} (UID: {uid})")
        
        # 获取视频列表
        videos = await self.list_user_videos_data(uid)
        if not videos:
            print("❌ 未找到任何视频")
            return
        
        print(f"总共 {len(videos)} 个视频\n")
        
        # 按时间倒序排列（最新的在前面）
        videos.sort(key=lambda x: x.get('created', 0), reverse=True)
        
        for i, video_info in enumerate(videos, 1):
            title = video_info['title']
            bvid = video_info['bvid']
            created = datetime.fromtimestamp(video_info.get('created', 0)).strftime('%Y-%m-%d')
            play_count = video_info.get('play', 0)
            
            print(f"{i:3d}. {title} [{bvid}] ({created}, {play_count:,}播放)")
    
    async def download_user_videos(self, uid: int) -> None:
        """下载用户所有视频"""
        # 获取用户信息
        user_info = await self.get_user_info(uid)
        if not user_info:
            print(f"❌ 无法获取用户信息，请检查用户ID: {uid}")
            return
        
        username = user_info.get('name', 'Unknown')
        print(f"\n开始下载用户 {username} (UID: {uid}) 的视频")
        
        # 创建下载目录
        download_folder = self.create_download_folder(user_info, uid)
        print(f"下载目录: {download_folder}")
        
        # 获取所有视频
        all_videos = await self.list_user_videos_data(uid)
        if not all_videos:
            print("❌ 未找到任何视频")
            return
        
        print(f"\n共找到 {len(all_videos)} 个视频，开始批量下载...")
        
        success_count = 0
        failed_count = 0
        
        # 检查ffmpeg
        if not self.downloader.check_ffmpeg():
            print("⚠️  警告: 未找到 ffmpeg，可能无法正确处理某些视频")
            print("请安装 ffmpeg: https://ffmpeg.org/")
        
        # 创建下载任务
        tasks = []
        for video_info in all_videos:
            task = self.downloader.download_single_video(video_info['bvid'], download_folder, self.semaphore)
            tasks.append(task)
        
        # 执行下载
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"❌ 视频下载异常 {all_videos[i]['title']}: {result}")
                failed_count += 1
            elif result:
                success_count += 1
            else:
                failed_count += 1
        
        print(f"\n📊 下载完成！成功: {success_count}, 失败: {failed_count}")
    
    # 合集相关方法
    
    async def get_user_collections_data(self, uid: int) -> List[Dict]:
        """获取用户所有合集"""
        try:
            user_obj = user.User(uid, credential=self.credential)
            collections = await user_obj.get_channels()
            
            collection_list = []
            for collection in collections:
                try:
                    meta = await collection.get_meta()
                    collection_info = {
                        'id': collection.id_,
                        'type': 'season' if collection.is_new else 'series',
                        'name': meta.get('name', meta.get('title', 'Unknown')),
                        'description': meta.get('description', meta.get('intro', '')),
                        'total': meta.get('total', meta.get('ep_count', 0)),
                        'cover': meta.get('cover', ''),
                        'created_time': meta.get('ctime', 0)
                    }
                    collection_list.append(collection_info)
                    await asyncio.sleep(0.1)  # 避免请求过快
                except Exception as e:
                    self.logger.warning(f"获取合集 {collection.id_} 信息失败: {e}")
                    continue
            
            return collection_list
        except Exception as e:
            self.logger.error(f"获取用户合集失败: {e}")
            return []
    
    async def get_collection_videos(self, collection_id: int, collection_type: str = 'auto') -> List[Dict]:
        """获取合集中的所有视频"""
        try:
            # 自动检测合集类型
            if collection_type == 'auto':
                detected_type = None
                collection = None
                
                # 先尝试作为新版合集(season)
                try:
                    self.logger.info(f"尝试将合集 {collection_id} 作为 SEASON 类型检测...")
                    test_collection = ChannelSeries(
                        type_=ChannelSeriesType.SEASON, 
                        id_=collection_id, 
                        credential=self.credential
                    )
                    # 尝试获取第一页视频数据来验证类型
                    test_videos = await test_collection.get_videos(
                        sort=ChannelOrder.DEFAULT, 
                        pn=1, 
                        ps=1
                    )
                    if test_videos and 'episodes' in test_videos:
                        detected_type = 'season'
                        collection = test_collection
                        self.logger.info(f"成功检测到 SEASON 类型合集")
                except Exception as e:
                    self.logger.info(f"SEASON 类型检测失败: {e}")
                
                # 如果SEASON失败，尝试作为旧版合集(series)
                if not detected_type:
                    try:
                        self.logger.info(f"尝试将合集 {collection_id} 作为 SERIES 类型检测...")
                        test_collection = ChannelSeries(
                            type_=ChannelSeriesType.SERIES, 
                            id_=collection_id, 
                            credential=self.credential
                        )
                        # 尝试获取第一页视频数据来验证类型
                        test_videos = await test_collection.get_videos(
                            sort=ChannelOrder.DEFAULT, 
                            pn=1, 
                            ps=1
                        )
                        if test_videos and 'archives' in test_videos:
                            detected_type = 'series'
                            collection = test_collection
                            self.logger.info(f"成功检测到 SERIES 类型合集")
                    except Exception as e:
                        self.logger.info(f"SERIES 类型检测失败: {e}")
                
                if not detected_type:
                    raise Exception(f"无法自动检测合集 {collection_id} 的类型，请手动指定 --type series 或 --type season")
                
                collection_type = detected_type
            else:
                # 使用指定类型
                series_type = ChannelSeriesType.SEASON if collection_type == 'season' else ChannelSeriesType.SERIES
                collection = ChannelSeries(
                    type_=series_type, 
                    id_=collection_id, 
                    credential=self.credential
                )
            
            all_videos = []
            page = 1
            page_size = 100
            
            while True:
                try:
                    videos_data = await collection.get_videos(
                        sort=ChannelOrder.DEFAULT, 
                        pn=page, 
                        ps=page_size
                    )
                    
                    if collection_type == 'season':
                        videos = videos_data.get('episodes', [])
                        for video_info in videos:
                            video_data = {
                                'title': video_info.get('title', 'Unknown'),
                                'bvid': video_info.get('bvid', ''),
                                'aid': video_info.get('aid', 0),
                                'duration': video_info.get('duration', 0),
                                'view': video_info.get('stat', {}).get('view', 0),
                                'created': video_info.get('pubdate', 0)
                            }
                            all_videos.append(video_data)
                    else:
                        videos = videos_data.get('archives', [])
                        for video_info in videos:
                            video_data = {
                                'title': video_info.get('title', 'Unknown'),
                                'bvid': video_info.get('bvid', ''),
                                'aid': video_info.get('aid', 0),
                                'duration': video_info.get('duration', 0),
                                'view': video_info.get('stat', {}).get('view', 0),
                                'created': video_info.get('pubdate', 0)
                            }
                            all_videos.append(video_data)
                    
                    if not videos or len(videos) < page_size:
                        break
                        
                    page += 1
                    await asyncio.sleep(0.5)  # 避免请求过快
                    
                except Exception as e:
                    self.logger.error(f"获取第{page}页视频列表失败: {e}")
                    break
            
            return all_videos
        except Exception as e:
            self.logger.error(f"获取合集视频失败: {e}")
            return []
    
    async def download_collection_videos(self, collection_id: int, collection_type: str = 'auto', collection_name: str = None) -> None:
        """下载合集中的所有视频"""
        try:
            # 获取合集信息
            if not collection_name:
                if collection_type == 'auto':
                    # 使用改进的自动检测逻辑
                    detected_type = None
                    
                    # 先尝试作为新版合集(season)
                    try:
                        self.logger.info(f"尝试将合集 {collection_id} 作为 SEASON 类型检测...")
                        test_collection = ChannelSeries(
                            type_=ChannelSeriesType.SEASON, 
                            id_=collection_id, 
                            credential=self.credential
                        )
                        # 尝试获取第一页视频数据来验证类型
                        test_videos = await test_collection.get_videos(
                            sort=ChannelOrder.DEFAULT, 
                            pn=1, 
                            ps=1
                        )
                        if test_videos and 'episodes' in test_videos:
                            meta = await test_collection.get_meta()
                            collection_name = meta.get('name', meta.get('title', f'Season_{collection_id}'))
                            detected_type = 'season'
                            self.logger.info(f"成功检测到 SEASON 类型合集")
                    except Exception as e:
                        self.logger.info(f"SEASON 类型检测失败: {e}")
                    
                    # 如果SEASON失败，尝试作为旧版合集(series)
                    if not detected_type:
                        try:
                            self.logger.info(f"尝试将合集 {collection_id} 作为 SERIES 类型检测...")
                            test_collection = ChannelSeries(
                                type_=ChannelSeriesType.SERIES, 
                                id_=collection_id, 
                                credential=self.credential
                            )
                            # 尝试获取第一页视频数据来验证类型
                            test_videos = await test_collection.get_videos(
                                sort=ChannelOrder.DEFAULT, 
                                pn=1, 
                                ps=1
                            )
                            if test_videos and 'archives' in test_videos:
                                meta = await test_collection.get_meta()
                                collection_name = meta.get('name', meta.get('title', f'Series_{collection_id}'))
                                detected_type = 'series'
                                self.logger.info(f"成功检测到 SERIES 类型合集")
                        except Exception as e:
                            self.logger.info(f"SERIES 类型检测失败: {e}")
                    
                    if not detected_type:
                        collection_name = f'Collection_{collection_id}'
                        # 默认使用series类型
                        detected_type = 'series'
                        self.logger.warning(f"无法自动检测合集类型，默认使用 SERIES 类型")
                    
                    collection_type = detected_type
                else:
                    series_type = ChannelSeriesType.SEASON if collection_type == 'season' else ChannelSeriesType.SERIES
                    collection = ChannelSeries(
                        type_=series_type, 
                        id_=collection_id, 
                        credential=self.credential
                    )
                    meta = await collection.get_meta()
                    collection_name = meta.get('name', meta.get('title', f'Collection_{collection_id}'))
            
            # 创建合集下载目录
            safe_collection_name = "".join(c for c in collection_name if c.isalnum() or c in (' ', '-', '_', '.')).strip()
            safe_collection_name = safe_collection_name[:50]  # 限制长度
            collection_folder = self.download_dir / f"{safe_collection_name}_{collection_id}"
            collection_folder.mkdir(parents=True, exist_ok=True)
            
            self.logger.info(f"开始下载合集: {collection_name} ({collection_type.upper()})")
            self.logger.info(f"下载目录: {collection_folder}")
            
            # 获取所有视频
            all_videos = await self.get_collection_videos(collection_id, collection_type)
            if not all_videos:
                print("❌ 未找到任何视频")
                return
            
            print(f"\n共找到 {len(all_videos)} 个视频，开始批量下载...")
            
            success_count = 0
            failed_count = 0
            
            # 检查ffmpeg
            if not self.downloader.check_ffmpeg():
                print("⚠️  警告: 未找到 ffmpeg，可能无法正确处理某些视频")
                print("请安装 ffmpeg: https://ffmpeg.org/")
            
            # 创建下载任务
            tasks = []
            for video_info in all_videos:
                if video_info.get('bvid'):
                    task = self.downloader.download_single_video(video_info['bvid'], collection_folder, self.semaphore)
                    tasks.append(task)
            
            # 执行下载
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"❌ 视频下载异常 {all_videos[i]['title']}: {result}")
                    failed_count += 1
                elif result:
                    success_count += 1
                else:
                    failed_count += 1
            
            print(f"\n📊 合集下载完成！成功: {success_count}, 失败: {failed_count}")
            
        except Exception as e:
            self.logger.error(f"下载合集失败: {e}")
            print(f"❌ 下载合集失败: {e}")
    
    async def list_user_collections(self, uid: int) -> None:
        """列出用户所有合集"""
        # 获取用户信息
        user_info = await self.get_user_info(uid)
        if not user_info:
            print(f"❌ 无法获取用户信息，请检查用户ID: {uid}")
            return
        
        username = user_info.get('name', 'Unknown')
        print(f"\n用户：{username} (UID: {uid})")
        
        # 获取合集列表
        collections = await self.get_user_collections_data(uid)
        if not collections:
            print("❌ 未找到任何合集")
            return
        
        print(f"总共 {len(collections)} 个合集\n")
        
        for i, collection in enumerate(collections, 1):
            collection_name = collection['name']
            collection_id = collection['id']
            collection_type = collection['type'].upper()
            total_videos = collection['total']
            created_time = datetime.fromtimestamp(collection.get('created_time', 0)).strftime('%Y-%m-%d')
            
            print(f"{i:3d}. {collection_name} [ID: {collection_id}]")
            print(f"     📺 类型: {collection_type} | 🎬 视频数: {total_videos} | 📅 创建: {created_time}")
            if collection.get('description'):
                description = collection['description'][:100]
                print(f"     📝 {description}{'...' if len(collection['description']) > 100 else ''}")
            print()
    
    async def list_collection_videos(self, collection_id: int, collection_type: str = 'auto') -> None:
        """列出合集中的所有视频"""
        try:
            # 获取视频列表
            videos = await self.get_collection_videos(collection_id, collection_type)
            if not videos:
                print(f"❌ 未找到任何视频 (合集ID: {collection_id}, 类型: {collection_type})")
                return
            
            print(f"\n合集 {collection_id} 中的视频 (类型: {collection_type.upper()})")
            print(f"总共 {len(videos)} 个视频\n")
            
            for i, video_info in enumerate(videos, 1):
                title = video_info['title']
                bvid = video_info['bvid']
                duration = video_info.get('duration', 0)
                view_count = video_info.get('view', 0)
                
                if duration > 0:
                    minutes = duration // 60
                    seconds = duration % 60
                    duration_str = f"{minutes:02d}:{seconds:02d}"
                else:
                    duration_str = "--:--"
                
                print(f"{i:3d}. {title} [{bvid}]")
                print(f"     ⏱️  {duration_str} | 👁️  {view_count:,} 播放")
                print()
                
        except Exception as e:
            self.logger.error(f"获取合集视频列表失败: {e}")
            print(f"❌ 获取合集视频列表失败: {e}")