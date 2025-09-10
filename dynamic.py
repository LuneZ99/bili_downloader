#!/usr/bin/env python3
"""
Bilibili动态爬取器

提供用户动态和评论的完整爬取功能：
- 获取用户所有动态
- 获取动态评论和楼中楼
- 支持并发获取
- 数据保存为JSON格式
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from bilibili_api import user, comment, dynamic, Credential
from bilibili_api.comment import CommentResourceType
from bilibili_api.dynamic import Dynamic

from utils import get_logger


class DynamicsCrawler:
    """B站用户动态爬取器"""
    
    def __init__(self, credential: Optional[Credential] = None, max_concurrent: int = 3, 
                 max_comments_per_dynamic: int = -1):
        """
        初始化动态爬取器
        
        Args:
            credential: B站登录凭据
            max_concurrent: 最大并发数
            max_comments_per_dynamic: 每个动态最大评论数限制 (-1 表示无限制)
        """
        self.credential = credential or Credential()
        self.max_concurrent = max_concurrent
        self.max_comments_per_dynamic = max_comments_per_dynamic
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        # 使用统一的日志配置
        self.logger = get_logger('DynamicsCrawler')
        
        # 统计信息
        self.stats = {
            'total_dynamics': 0,
            'processed_dynamics': 0,
            'total_comments': 0,
            'failed_dynamics': 0,
            'start_time': None
        }
    
    async def get_user_info(self, uid: int) -> Dict:
        """获取用户信息"""
        try:
            user_obj = user.User(uid)
            info = await user_obj.get_user_info()
            return info
        except Exception as e:
            self.logger.error(f"获取用户信息失败: {e}")
            return {}
    
    async def get_user_all_dynamics(self, uid: int) -> List[Dict]:
        """
        获取用户所有动态
        
        Args:
            uid: 用户ID
            
        Returns:
            List[Dict]: 动态信息列表
        """
        user_obj = user.User(uid, credential=self.credential)
        all_dynamics = []
        offset = ""
        page = 1
        
        self.logger.info(f"开始获取用户 {uid} 的动态列表...")
        
        while True:
            try:
                dynamics_data = await user_obj.get_dynamics_new(offset=offset)
                
                if not dynamics_data.get('items'):
                    break
                
                dynamics_list = dynamics_data['items']
                all_dynamics.extend(dynamics_list)
                
                self.logger.info(f"获取第 {page} 页，{len(dynamics_list)} 条动态，累计 {len(all_dynamics)} 条")
                
                # 检查是否有下一页
                if not dynamics_data.get('offset') or len(dynamics_list) == 0:
                    break
                
                offset = dynamics_data['offset']
                page += 1
                
                # 避免请求过快
                await asyncio.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"获取第 {page} 页动态列表失败: {e}")
                break
        
        self.logger.info(f"共获取到 {len(all_dynamics)} 条动态")
        self.stats['total_dynamics'] = len(all_dynamics)
        return all_dynamics
    
    async def get_dynamic_comments(self, dynamic_obj: Dynamic, dynamic_type: CommentResourceType) -> Dict:
        """
        获取单个动态的所有评论和楼中楼
        
        Args:
            dynamic_obj: 动态对象
            dynamic_type: 评论资源类型
            
        Returns:
            Dict: 包含所有评论数据的字典
        """
        try:
            # 获取动态的rid作为评论区oid
            rid = await dynamic_obj.get_rid()
            
            comments_data = {
                'root_comments': [],
                'sub_comments': {},
                'total_count': 0
            }
            
            # 获取根评论
            offset = ""
            comment_count = 0
            
            while True:
                try:
                    # 获取评论列表
                    comments_resp = await comment.get_comments_lazy(
                        oid=rid,
                        type_=dynamic_type,
                        offset=offset,
                        credential=self.credential
                    )
                    
                    if not comments_resp.get('replies'):
                        break
                    
                    root_comments = comments_resp['replies']
                    
                    for root_comment in root_comments:
                        comment_count += 1
                        if self.max_comments_per_dynamic != -1 and comment_count > self.max_comments_per_dynamic:
                            self.logger.warning(f"动态 {dynamic_obj.get_dynamic_id()} 评论数超过限制 {self.max_comments_per_dynamic}")
                            break
                        
                        comments_data['root_comments'].append(root_comment)
                        
                        # 获取楼中楼评论
                        if root_comment.get('rcount', 0) > 0:
                            rpid = root_comment['rpid']
                            sub_comments = await self.get_sub_comments(rid, dynamic_type, rpid)
                            if sub_comments:
                                comments_data['sub_comments'][str(rpid)] = sub_comments
                    
                    # 检查是否有下一页
                    if not comments_resp.get('cursor') or not comments_resp['cursor'].get('next'):
                        break
                    
                    offset = str(comments_resp['cursor']['next'])
                    await asyncio.sleep(0.3)  # 避免请求过快
                    
                    if self.max_comments_per_dynamic != -1 and comment_count > self.max_comments_per_dynamic:
                        break
                        
                except Exception as e:
                    self.logger.error(f"获取评论失败: {e}")
                    break
            
            comments_data['total_count'] = comment_count
            self.stats['total_comments'] += comment_count
            
            return comments_data
            
        except Exception as e:
            self.logger.error(f"获取动态 {dynamic_obj.get_dynamic_id()} 评论失败: {e}")
            return {'root_comments': [], 'sub_comments': {}, 'total_count': 0}
    
    async def get_sub_comments(self, oid: int, type_: CommentResourceType, root_rpid: int) -> List[Dict]:
        """
        获取楼中楼评论
        
        Args:
            oid: 资源ID
            type_: 评论资源类型
            root_rpid: 根评论ID
            
        Returns:
            List[Dict]: 子评论列表
        """
        try:
            comment_obj = comment.Comment(oid, type_, root_rpid, credential=self.credential)
            
            sub_comments = []
            page = 1
            
            while True:
                try:
                    sub_resp = await comment_obj.get_sub_comments(page_index=page, page_size=20)
                    
                    if not sub_resp.get('replies'):
                        break
                    
                    page_comments = sub_resp['replies']
                    sub_comments.extend(page_comments)
                    
                    # 检查是否还有更多页
                    if len(page_comments) < 20:
                        break
                    
                    page += 1
                    await asyncio.sleep(0.2)  # 避免请求过快
                    
                except Exception as e:
                    self.logger.error(f"获取楼中楼评论第 {page} 页失败: {e}")
                    break
            
            return sub_comments
            
        except Exception as e:
            self.logger.error(f"获取楼中楼评论失败: {e}")
            return []
    
    def determine_comment_type(self, dynamic_info: Dict) -> CommentResourceType:
        """
        根据动态信息确定评论资源类型
        
        Args:
            dynamic_info: 动态信息
            
        Returns:
            CommentResourceType: 评论资源类型
        """
        # 根据动态类型确定评论区类型
        dynamic_type = dynamic_info.get('type')
        
        if dynamic_type == 'DYNAMIC_TYPE_AV':  # 视频动态
            return CommentResourceType.VIDEO
        elif dynamic_type == 'DYNAMIC_TYPE_DRAW':  # 图文动态
            return CommentResourceType.DYNAMIC_DRAW
        elif dynamic_type == 'DYNAMIC_TYPE_ARTICLE':  # 文章动态
            return CommentResourceType.ARTICLE
        elif dynamic_type == 'DYNAMIC_TYPE_WORD':  # 纯文本动态
            return CommentResourceType.DYNAMIC
        else:
            # 默认使用动态评论类型
            return CommentResourceType.DYNAMIC
    
    async def save_dynamic_data(self, dynamic_info: Dict, comments_data: Dict, save_dir: Path):
        """
        保存动态数据到JSON文件
        
        Args:
            dynamic_info: 动态信息
            comments_data: 评论数据
            save_dir: 保存目录
        """
        try:
            dynamic_id = dynamic_info['id_str']
            
            # 构建完整的数据结构
            full_data = {
                'dynamic_info': dynamic_info,
                'comments': comments_data,
                'metadata': {
                    'crawl_time': datetime.now().isoformat(),
                    'total_comments': comments_data['total_count'],
                    'dynamic_type': dynamic_info.get('type', 'UNKNOWN'),
                    'dynamic_id': dynamic_id
                }
            }
            
            # 生成安全的文件名
            filename = f"dynamic_{dynamic_id}.json"
            filepath = save_dir / filename
            
            # 保存到文件
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(full_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"保存动态数据: {filename} ({comments_data['total_count']} 条评论)")
            
        except Exception as e:
            self.logger.error(f"保存动态数据失败: {e}")
    
    async def process_single_dynamic(self, dynamic_info: Dict, save_dir: Path, 
                                   include_comments: bool = True) -> bool:
        """
        处理单个动态（包含评论获取和保存）
        
        Args:
            dynamic_info: 动态信息
            save_dir: 保存目录
            include_comments: 是否包含评论
            
        Returns:
            bool: 处理是否成功
        """
        if not self.semaphore:
            return await self._process_dynamic_impl(dynamic_info, save_dir, include_comments)
        
        async with self.semaphore:
            return await self._process_dynamic_impl(dynamic_info, save_dir, include_comments)
    
    async def _process_dynamic_impl(self, dynamic_info: Dict, save_dir: Path, 
                                  include_comments: bool) -> bool:
        """处理单个动态的具体实现"""
        try:
            dynamic_id = dynamic_info['id_str']
            
            # 检查文件是否已存在
            filename = f"dynamic_{dynamic_id}.json"
            filepath = save_dir / filename
            
            if filepath.exists():
                self.logger.info(f"跳过已存在的动态: {filename}")
                return True
            
            comments_data = {'root_comments': [], 'sub_comments': {}, 'total_count': 0}
            
            if include_comments:
                # 创建动态对象
                dynamic_obj = Dynamic(int(dynamic_id), credential=self.credential)
                
                # 确定评论类型
                comment_type = self.determine_comment_type(dynamic_info)
                
                # 获取评论
                comments_data = await self.get_dynamic_comments(dynamic_obj, comment_type)
            
            # 保存数据
            await self.save_dynamic_data(dynamic_info, comments_data, save_dir)
            
            self.stats['processed_dynamics'] += 1
            return True
            
        except Exception as e:
            self.logger.error(f"处理动态 {dynamic_info.get('id_str', 'unknown')} 失败: {e}")
            self.stats['failed_dynamics'] += 1
            return False
    
    async def crawl_user_dynamics(self, uid: int, save_dir: str = "dynamics", 
                                include_comments: bool = True) -> Dict:
        """
        爬取用户所有动态和评论
        
        Args:
            uid: 用户ID
            save_dir: 保存目录
            include_comments: 是否包含评论
            
        Returns:
            Dict: 爬取统计信息
        """
        self.stats['start_time'] = datetime.now()
        
        # 获取用户信息
        user_info = await self.get_user_info(uid)
        if not user_info:
            self.logger.error(f"无法获取用户 {uid} 的信息")
            return self.stats
        
        username = user_info.get('name', f'UID_{uid}')
        self.logger.info(f"开始爬取用户 {username} (UID: {uid}) 的动态")
        
        # 创建保存目录
        save_path = Path(save_dir) / f"{username}_{uid}" / "dynamics"
        save_path.mkdir(parents=True, exist_ok=True)
        
        # 获取所有动态
        all_dynamics = await self.get_user_all_dynamics(uid)
        if not all_dynamics:
            self.logger.warning("未找到任何动态")
            return self.stats
        
        self.logger.info(f"开始处理 {len(all_dynamics)} 条动态{'和评论' if include_comments else ''}...")
        
        # 创建处理任务
        tasks = []
        for dynamic_info in all_dynamics:
            task = self.process_single_dynamic(dynamic_info, save_path, include_comments)
            tasks.append(task)
        
        # 并发执行任务
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计结果
        success_count = sum(1 for result in results if result is True)
        
        # 保存爬取元信息
        metadata = {
            'user_info': user_info,
            'crawl_stats': self.stats,
            'crawl_time': datetime.now().isoformat(),
            'total_dynamics': len(all_dynamics),
            'processed_dynamics': success_count,
            'include_comments': include_comments
        }
        
        metadata_path = save_path.parent / "metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        # 输出统计结果
        duration = datetime.now() - self.stats['start_time']
        self.logger.info(f"爬取完成！")
        self.logger.info(f"总动态数: {len(all_dynamics)}")
        self.logger.info(f"成功处理: {success_count}")
        self.logger.info(f"失败数: {len(all_dynamics) - success_count}")
        if include_comments:
            self.logger.info(f"总评论数: {self.stats['total_comments']}")
        self.logger.info(f"耗时: {duration}")
        
        return self.stats


class BilibiliDynamicManager:
    """Bilibili动态管理器 - 整合动态相关功能"""
    
    def __init__(self, download_dir: str = "downloads", max_concurrent: int = 3, 
                 credential: Optional[Credential] = None, max_comments: int = -1):
        """
        初始化动态管理器
        
        Args:
            download_dir: 下载目录
            max_concurrent: 最大并发数
            credential: B站登录凭据
            max_comments: 每个动态最大评论数限制 (-1 表示无限制)
        """
        self.download_dir = Path(download_dir)
        self.credential = credential
        
        # 创建动态爬取器
        self.dynamics_crawler = DynamicsCrawler(
            credential=credential, 
            max_concurrent=max_concurrent,
            max_comments_per_dynamic=max_comments
        )
        # 使用统一的日志配置
        self.logger = get_logger('DynamicManager')
    
    async def get_user_info(self, uid: int) -> Dict:
        """获取用户信息"""
        return await self.dynamics_crawler.get_user_info(uid)
    
    async def list_user_dynamics(self, uid: int, limit: Optional[int] = None) -> None:
        """
        列出用户最近的动态
        
        Args:
            uid: 用户ID
            limit: 显示动态数量限制 (默认: 100)
        """
        # 设置默认限制为100条
        if limit is None:
            limit = 100
        
        # 获取用户信息
        user_info = await self.get_user_info(uid)
        if not user_info:
            print(f"❌ 无法获取用户信息，请检查用户ID: {uid}")
            return
        
        username = user_info.get('name', 'Unknown')
        print(f"\n用户：{username} (UID: {uid})")
        
        # 获取动态列表（支持多页获取）
        try:
            user_obj = user.User(uid, credential=self.credential)
            all_dynamics = []
            offset = ""
            page = 1
            
            print(f"📦 正在获取最近 {limit} 条动态...")
            
            while len(all_dynamics) < limit:
                dynamics_data = await user_obj.get_dynamics_new(offset=offset)
                
                if not dynamics_data.get('items'):
                    break
                
                dynamics_list = dynamics_data['items']
                all_dynamics.extend(dynamics_list)
                
                # 如果是第一页且已满足需求，直接跳出
                if page == 1 and len(dynamics_list) >= limit:
                    break
                
                # 检查是否有下一页
                if not dynamics_data.get('offset') or len(dynamics_list) == 0:
                    break
                
                # 显示进度（仅在需要多页时）
                if page == 1 and len(dynamics_list) < limit:
                    print(f"📄 第1页已获取 {len(dynamics_list)} 条，继续获取更多...")
                elif page > 1:
                    print(f"📄 第{page}页已获取，累计 {len(all_dynamics)} 条...")
                
                offset = dynamics_data['offset']
                page += 1
                
                # 避免请求过快
                await asyncio.sleep(0.3)
                
                # 安全限制：最多获取10页
                if page > 10:
                    self.logger.warning(f"已达到最大页数限制(10页)，停止获取")
                    break
            
            # 截取所需数量
            dynamics_list = all_dynamics[:limit]
            
            if not dynamics_list:
                print("❌ 未找到任何动态")
                return
            
            print(f"✅ 成功获取 {len(dynamics_list)} 条动态\n")
            
            for i, dynamic_info in enumerate(dynamics_list, 1):
                dynamic_type = dynamic_info.get('type', 'UNKNOWN')
                dynamic_id = dynamic_info['id_str']
                
                # 解析动态内容
                modules = dynamic_info.get('modules', {})
                desc_text = ""
                
                # 尝试获取动态描述文本
                if modules.get('module_dynamic', {}).get('desc'):
                    desc_text = modules['module_dynamic']['desc'].get('text', '')[:100]
                elif modules.get('module_dynamic', {}).get('major', {}).get('opus'):
                    # 图文动态
                    opus = modules['module_dynamic']['major']['opus']
                    if opus.get('summary', {}).get('text'):
                        desc_text = opus['summary']['text'][:100]
                    elif opus.get('title'):
                        desc_text = opus['title']
                
                # 发布时间
                pub_time = datetime.fromtimestamp(dynamic_info.get('modules', {}).get('module_author', {}).get('pub_ts', 0))
                pub_time_str = pub_time.strftime('%Y-%m-%d %H:%M')
                
                print(f"{i:3d}. [{dynamic_type}] {dynamic_id}")
                print(f"     📅 {pub_time_str}")
                if desc_text:
                    print(f"     📝 {desc_text}{'...' if len(desc_text) >= 100 else ''}")
                print()
                
        except Exception as e:
            self.logger.error(f"获取用户动态失败: {e}")
            print(f"❌ 获取用户动态失败: {e}")
    
    async def download_user_dynamics(self, uid: int, include_comments: bool = True, 
                                   max_comments: int = -1) -> None:
        """
        下载用户所有动态和评论
        
        Args:
            uid: 用户ID
            include_comments: 是否包含评论
            max_comments: 每个动态最大评论数限制 (-1 表示无限制)
        """
        # 获取用户信息
        user_info = await self.get_user_info(uid)
        if not user_info:
            print(f"❌ 无法获取用户信息，请检查用户ID: {uid}")
            return
        
        username = user_info.get('name', 'Unknown')
        print(f"\n开始下载用户 {username} (UID: {uid}) 的动态{'和评论' if include_comments else ''}")
        
        # 设置动态爬取器参数
        self.dynamics_crawler.max_comments_per_dynamic = max_comments
        
        try:
            # 执行爬取
            stats = await self.dynamics_crawler.crawl_user_dynamics(
                uid=uid,
                save_dir=str(self.download_dir),
                include_comments=include_comments
            )
            
            # 显示结果统计
            print(f"\n📊 动态下载完成！")
            print(f"总动态数: {stats['total_dynamics']}")
            print(f"成功处理: {stats['processed_dynamics']}")
            print(f"失败数: {stats['failed_dynamics']}")
            if include_comments:
                print(f"总评论数: {stats['total_comments']}")
            
        except Exception as e:
            self.logger.error(f"下载用户动态失败: {e}")
            print(f"❌ 下载用户动态失败: {e}")
    
    async def download_single_dynamic(self, dynamic_id: int, include_comments: bool = True) -> None:
        """
        下载单个动态和评论
        
        Args:
            dynamic_id: 动态ID
            include_comments: 是否包含评论
        """
        try:
            # 创建动态对象
            dynamic_obj = Dynamic(dynamic_id, credential=self.credential)
            
            # 获取动态详细信息
            dynamic_info = await dynamic_obj.get_info()
            
            if not dynamic_info:
                print(f"❌ 无法获取动态 {dynamic_id} 的信息")
                return
            
            # 创建保存目录
            save_path = self.download_dir / "single_dynamics"
            save_path.mkdir(parents=True, exist_ok=True)
            
            print(f"\n开始下载动态 {dynamic_id}{'和评论' if include_comments else ''}")
            
            # 处理动态
            success = await self.dynamics_crawler.process_single_dynamic(
                dynamic_info['item'], 
                save_path, 
                include_comments
            )
            
            if success:
                print(f"✅ 动态下载完成")
            else:
                print(f"❌ 动态下载失败")
                
        except Exception as e:
            self.logger.error(f"下载单个动态失败: {e}")
            print(f"❌ 下载单个动态失败: {e}")