#!/usr/bin/env python3
"""
Bilibili视频管理器

高级管理功能，使用VideoDownloader作为核心下载引擎
提供用户视频管理、合集管理等功能
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from bilibili_api import user, Credential
from bilibili_api.channel_series import ChannelSeries, ChannelSeriesType, ChannelOrder
from bili_downloader import VideoDownloader


class BilibiliManager:
    """Bilibili视频管理器"""
    
    def __init__(self, download_dir: str = "downloads", max_concurrent: int = 3, credential: Optional[Credential] = None, preferred_quality: str = "auto"):
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
        self.logger = self.downloader.logger
    
    
    async def get_user_info(self, uid: int) -> Dict:
        """获取用户信息"""
        try:
            user_obj = user.User(uid)
            info = await user_obj.get_user_info()
            return info
        except Exception as e:
            self.logger.error(f"获取用户信息失败: {e}")
            return {}
    
    async def list_user_videos(self, uid: int) -> List[Dict]:
        """列出用户所有视频"""
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
        
        # 按创建时间倒序排列（最新的在前面）
        collections.sort(key=lambda x: x.get('created_time', 0), reverse=True)
        
        for i, collection in enumerate(collections, 1):
            name = collection['name']
            collection_id = collection['id']
            collection_type = collection['type'].upper()
            video_count = collection.get('total', 0)
            description = collection.get('description', '')[:50]
            if len(collection.get('description', '')) > 50:
                description += '...'
            
            print(f"{i:3d}. {name} [ID: {collection_id}, {collection_type}]")
            print(f"     📹 {video_count} 个视频")
            if description:
                print(f"     📝 {description}")
            print()
    
    async def list_collection_videos(self, collection_id: int, collection_type: str = 'auto') -> None:
        """列出合集中的所有视频"""
        # 获取合集视频
        videos = await self.get_collection_videos(collection_id, collection_type)
        if not videos:
            print(f"❌ 未找到合集 {collection_id} 的视频")
            return
        
        print(f"\n合集 {collection_id} ({collection_type.upper()})")
        print(f"总共 {len(videos)} 个视频\n")
        
        # 按发布时间倒序排列（最新的在前面）
        videos.sort(key=lambda x: x.get('created', 0), reverse=True)
        
        for i, video_info in enumerate(videos, 1):
            title = video_info['title']
            bvid = video_info['bvid']
            duration = video_info.get('duration', 0)
            view_count = video_info.get('view', 0)
            
            # 格式化时长
            if duration > 0:
                minutes, seconds = divmod(duration, 60)
                duration_str = f"{minutes:02d}:{seconds:02d}"
            else:
                duration_str = "--:--"
            
            print(f"{i:3d}. {title} [{bvid}]")
            print(f"     ⏱️  {duration_str} | 👁️  {view_count:,} 播放")
            print()
