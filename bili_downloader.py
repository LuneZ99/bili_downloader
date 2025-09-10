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
from pathlib import Path
from typing import Dict, Optional

import aiohttp
import aiofiles
from bilibili_api import video, HEADERS, Credential
from bilibili_api.video import VideoQuality


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
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('bili_downloader.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
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