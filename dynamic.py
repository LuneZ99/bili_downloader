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
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from bilibili_api import user, comment, dynamic, Credential
from bilibili_api.comment import CommentResourceType
from bilibili_api.dynamic import Dynamic

from utils import get_logger, api_retry_decorator


class DynamicsCrawler:
    """B站用户动态爬取器"""
    
    def __init__(self, credential: Optional[Credential] = None, max_concurrent: int = 1, 
                 max_comments_per_dynamic: int = -1, base_wait_time: float = 0.1, 
                 full_sub_comments: bool = False):
        """
        初始化动态爬取器
        
        Args:
            credential: B站登录凭据
            max_concurrent: 最大并发数
            max_comments_per_dynamic: 每个动态最大评论数限制 (-1 表示无限制)
            base_wait_time: 请求之间的基本等待时间（秒，默认0.1秒）
            full_sub_comments: 是否获取完整楼中楼评论 (False=仅使用内嵌楼中楼, True=单独获取完整楼中楼)
        """
        self.credential = credential or Credential()
        self.max_concurrent = max_concurrent
        self.max_comments_per_dynamic = max_comments_per_dynamic
        self.full_sub_comments = full_sub_comments
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.base_wait_time = base_wait_time
        self.current_wait_time = base_wait_time
        
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
    
    @api_retry_decorator()
    async def get_user_info(self, uid: int) -> Dict:
        """获取用户信息"""
        try:
            user_obj = user.User(uid, credential=self.credential)
            info = await user_obj.get_user_info()
            return info
        except Exception as e:
            self.logger.error(f"获取用户信息失败: {e}")
            return {}
    
    @api_retry_decorator()
    async def _get_dynamics_page(self, user_obj: user.User, offset: str) -> Dict:
        """获取一页动态"""
        return await user_obj.get_dynamics_new(offset=offset)

    async def get_user_all_dynamics(self, uid: int, start_page: int = 1, max_pages: Optional[int] = None) -> List[Dict]:
        """
        获取用户所有动态
        
        Args:
            uid: 用户ID
            start_page: 起始页码
            max_pages: 最大爬取页数

        Returns:
            List[Dict]: 动态信息列表
        """
        user_obj = user.User(uid, credential=self.credential)
        all_dynamics = []
        offset = ""
        page = 1
        pages_crawled = 0
        
        self.logger.info(f"开始获取用户 {uid} 的动态列表...")
        
        while True:
            if max_pages is not None and pages_crawled >= max_pages:
                self.logger.info(f"已达到最大爬取页数限制 ({max_pages}页)，停止获取。")
                break

            try:
                dynamics_data = await self._get_dynamics_page(user_obj, offset)
                
                if not dynamics_data or not dynamics_data.get('items'):
                    break
                
                if page >= start_page:
                    dynamics_list = dynamics_data['items']
                    all_dynamics.extend(dynamics_list)
                    pages_crawled += 1
                    self.logger.info(f"获取第 {page} 页，{len(dynamics_list)} 条动态，累计 {len(all_dynamics)} 条 (已爬取 {pages_crawled} 页)")
                else:
                    self.logger.info(f"跳过第 {page} 页 (起始页: {start_page})")

                # 检查是否有下一页
                if not dynamics_data.get('offset') or len(dynamics_data['items']) == 0:
                    break
                
                offset = dynamics_data['offset']
                page += 1
                
                # 避免请求过快
                await asyncio.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"获取第 {page} 页动态列表失败: {e}")
                break
        
        self.logger.info(f"共获取到 {len(all_dynamics)} 条动态")
        self.stats['total_dynamics'] = len(all_dynamics)
        return all_dynamics
    
    @api_retry_decorator()
    async def _get_comments_page(self, oid: int, type_: CommentResourceType, offset: str) -> Dict:
        """获取一页根评论"""
        return await comment.get_comments_lazy(
            oid=oid,
            type_=type_,
            offset=offset,
            credential=self.credential
        )

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
            dynamic_id = dynamic_obj.get_dynamic_id()
            
            comments_data = {
                'root_comments': [],
                'sub_comments': {},
                'total_count': 0
            }
            
            # 获取根评论
            offset = ""
            comment_count = 0
            page_count = 0
            sub_comments_to_process = []
            
            self.logger.info(f"动态 {dynamic_id}: 开始获取根评论...")
            
            while True:
                comments_resp = await self._get_comments_page(rid, dynamic_type, offset)

                if not comments_resp or not comments_resp.get('replies'):
                    break
                
                page_count += 1
                root_comments = comments_resp['replies']
                
                self.logger.info(f"动态 {dynamic_id}: 获取第 {page_count} 页根评论，{len(root_comments)} 条")
                
                for root_comment in root_comments:
                    comment_count += 1
                    if self.max_comments_per_dynamic != -1 and comment_count > self.max_comments_per_dynamic:
                        self.logger.warning(f"动态 {dynamic_id} 评论数超过限制 {self.max_comments_per_dynamic}")
                        break
                    
                    # 根据策略处理楼中楼
                    if self.full_sub_comments:
                        # 方案B: 清空内嵌楼中楼，单独获取完整楼中楼
                        if root_comment.get('rcount', 0) > 0:
                            sub_comments_to_process.append({
                                'rpid': root_comment['rpid'],
                                'rcount': root_comment['rcount']
                            })
                        # 清空内嵌的replies避免重复
                        root_comment['replies'] = []
                    else:
                        # 方案A: 保留内嵌楼中楼，不单独获取
                        pass  # 保持原有的replies字段
                    
                    comments_data['root_comments'].append(root_comment)
                
                # 检查是否有下一页 - 使用正确的API字段路径
                cursor = comments_resp.get('cursor', {})
                pagination_reply = cursor.get('pagination_reply', {})
                next_offset = pagination_reply.get('next_offset', '')
                
                if not next_offset:
                    self.logger.info(f"动态 {dynamic_id}: 没有更多页面")
                    break
                
                offset = next_offset
                await asyncio.sleep(self.base_wait_time)
                
                if self.max_comments_per_dynamic != -1 and comment_count > self.max_comments_per_dynamic:
                    break

            # 统计楼中楼信息
            total_sub_comments_expected = sum(item['rcount'] for item in sub_comments_to_process)
            
            if sub_comments_to_process and self.full_sub_comments:
                # 方案B: 单独获取完整楼中楼
                self.logger.info(f"动态 {dynamic_id}: 根评论获取完成，共 {comment_count} 条根评论，"
                               f"发现 {len(sub_comments_to_process)} 个楼中楼，预计 {total_sub_comments_expected} 条子评论")
                
                # 获取楼中楼评论
                processed_sub_count = 0
                for i, sub_info in enumerate(sub_comments_to_process, 1):
                    rpid = sub_info['rpid']
                    expected_count = sub_info['rcount']
                    
                    self.logger.info(f"动态 {dynamic_id}: 获取楼中楼 {i}/{len(sub_comments_to_process)} "
                                   f"(rpid: {rpid}, 预计: {expected_count} 条)")
                    
                    sub_comments = await self.get_sub_comments(rid, dynamic_type, rpid)
                    if sub_comments:
                        comments_data['sub_comments'][str(rpid)] = sub_comments
                        processed_sub_count += len(sub_comments)
                        
                        self.logger.info(f"动态 {dynamic_id}: 楼中楼 {i}/{len(sub_comments_to_process)} 完成，"
                                       f"实际获取 {len(sub_comments)} 条，累计子评论: {processed_sub_count}")
                
                self.logger.info(f"动态 {dynamic_id}: 楼中楼获取完成，实际获取 {processed_sub_count} 条子评论")
            else:
                # 方案A: 使用内嵌楼中楼或无楼中楼
                if self.full_sub_comments:
                    self.logger.info(f"动态 {dynamic_id}: 根评论获取完成，共 {comment_count} 条，无楼中楼")
                else:
                    self.logger.info(f"动态 {dynamic_id}: 根评论获取完成，共 {comment_count} 条，使用内嵌楼中楼")

            comments_data['total_count'] = comment_count
            self.stats['total_comments'] += comment_count
            
            return comments_data
            
        except Exception as e:
            self.logger.error(f"获取动态 {dynamic_obj.get_dynamic_id()} 评论失败: {e}")
            return {'root_comments': [], 'sub_comments': {}, 'total_count': 0}
    
    @api_retry_decorator()
    async def _get_sub_comments_page(self, comment_obj: comment.Comment, page: int) -> Dict:
        """获取一页楼中楼评论"""
        return await comment_obj.get_sub_comments(page_index=page, page_size=20)

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
                self.logger.debug(f"获取楼中楼 {root_rpid} 第 {page} 页...")
                sub_resp = await self._get_sub_comments_page(comment_obj, page)

                if not sub_resp or not sub_resp.get('replies'):
                    break
                
                page_comments = sub_resp['replies']
                sub_comments.extend(page_comments)
                
                if page == 1:
                    self.logger.debug(f"楼中楼 {root_rpid}: 第 {page} 页获取 {len(page_comments)} 条")
                elif page % 5 == 0 or len(page_comments) < 20:  # 每5页或最后一页打印进度
                    self.logger.debug(f"楼中楼 {root_rpid}: 第 {page} 页获取 {len(page_comments)} 条，累计 {len(sub_comments)} 条")
                
                # 检查是否还有更多页
                if len(page_comments) < 20:
                    break
                
                page += 1
                await asyncio.sleep(self.base_wait_time)
            
            if page > 1:
                self.logger.debug(f"楼中楼 {root_rpid} 获取完成: 共 {page} 页，{len(sub_comments)} 条子评论")
            
            return sub_comments
            
        except Exception as e:
            self.logger.error(f"获取楼中楼评论失败 (rpid: {root_rpid}): {e}")
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
        dynamic_id = dynamic_info['id_str']
        start_time = datetime.now()
        
        self.logger.info(f"开始处理动态: {dynamic_id}")
        try:
            
            # 检查文件是否已存在
            filename = f"dynamic_{dynamic_id}.json"
            filepath = save_dir / filename
            
            if filepath.exists():
                self.logger.info(f"跳过已存在的动态: {filename}")
                return True
            
            comments_data = {'root_comments': [], 'sub_comments': {}, 'total_count': 0}
            
            if include_comments:
                self.logger.info(f"正在获取动态 {dynamic_id} 的评论...")
                # 创建动态对象
                dynamic_obj = Dynamic(int(dynamic_id), credential=self.credential)
                
                # 确定评论类型
                comment_type = self.determine_comment_type(dynamic_info)
                
                # 获取评论
                comments_data = await self.get_dynamic_comments(dynamic_obj, comment_type)
                
                # 计算处理时间
                processing_time = datetime.now() - start_time
                
                self.logger.info(f"动态 {dynamic_id} 评论获取完成，共 {comments_data['total_count']} 条评论，"
                               f"耗时 {processing_time.total_seconds():.1f}秒")
            
            # 保存数据
            await self.save_dynamic_data(dynamic_info, comments_data, save_dir)
            
            # 总处理时间
            total_time = datetime.now() - start_time
            self.logger.info(f"动态 {dynamic_id} 处理完成，总耗时 {total_time.total_seconds():.1f}秒")
            
            self.stats['processed_dynamics'] += 1
            return True
            
        except Exception as e:
            self.logger.error(f"处理动态 {dynamic_info.get('id_str', 'unknown')} 失败: {e}")
            self.stats['failed_dynamics'] += 1
            return False
    
    async def crawl_user_dynamics(self, uid: int, save_dir: str = "dynamics", 
                                include_comments: bool = True, 
                                start_page: int = 1, max_pages: Optional[int] = None) -> Dict:
        """
        爬取用户所有动态和评论
        
        Args:
            uid: 用户ID
            save_dir: 保存目录
            include_comments: 是否包含评论
            start_page: 起始页码
            max_pages: 最大爬取页数
            
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
        
        # 逐页获取和处理动态
        user_obj = user.User(uid, credential=self.credential)
        offset = ""
        page = 1
        pages_crawled = 0
        total_dynamics_processed = 0
        
        self.logger.info(f"开始逐页获取和处理动态...")
        
        while True:
            if max_pages is not None and pages_crawled >= max_pages:
                self.logger.info(f"已达到最大爬取页数限制 ({max_pages}页)，停止获取。")
                break

            try:
                # 获取当前页动态
                dynamics_data = await self._get_dynamics_page(user_obj, offset)
                
                if not dynamics_data or not dynamics_data.get('items'):
                    break
                
                if page >= start_page:
                    dynamics_list = dynamics_data['items']
                    pages_crawled += 1
                    
                    self.logger.info(f"获取第 {page} 页，{len(dynamics_list)} 条动态，开始处理...")
                    
                    # 立即处理这页的动态
                    tasks = []
                    for dynamic_info in dynamics_list:
                        task = self.process_single_dynamic(dynamic_info, save_path, include_comments)
                        tasks.append(task)
                    
                    # 并发执行当前页的任务
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # 统计当前页结果
                    page_success_count = sum(1 for result in results if result is True)
                    total_dynamics_processed += len(dynamics_list)
                    
                    self.logger.info(f"第 {page} 页处理完成: {page_success_count}/{len(dynamics_list)} 成功, "
                                   f"累计处理 {total_dynamics_processed} 条动态")
                    
                else:
                    self.logger.info(f"跳过第 {page} 页 (起始页: {start_page})")

                # 检查是否有下一页
                if not dynamics_data.get('offset') or len(dynamics_data['items']) == 0:
                    break
                
                offset = dynamics_data['offset']
                page += 1
                
                # 避免请求过快
                await asyncio.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"处理第 {page} 页动态失败: {e}")
                break
        
        if total_dynamics_processed == 0:
            self.logger.warning("未找到任何动态")
            return self.stats
        
        # 更新统计信息
        self.stats['total_dynamics'] = total_dynamics_processed
        
        # 保存爬取元信息
        # 处理 stats 中的 datetime 对象，避免 JSON 序列化错误
        stats_copy = self.stats.copy()
        if 'start_time' in stats_copy and isinstance(stats_copy['start_time'], datetime):
            stats_copy['start_time'] = stats_copy['start_time'].isoformat()
            
        metadata = {
            'user_info': user_info,
            'crawl_stats': stats_copy,
            'crawl_time': datetime.now().isoformat(),
            'total_dynamics': total_dynamics_processed,
            'processed_dynamics': self.stats['processed_dynamics'],
            'include_comments': include_comments
        }
        
        metadata_path = save_path.parent / "metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        # 输出统计结果
        duration = datetime.now() - self.stats['start_time']
        self.logger.info(f"爬取完成！")
        self.logger.info(f"总动态数: {total_dynamics_processed}")
        self.logger.info(f"成功处理: {self.stats['processed_dynamics']}")
        self.logger.info(f"失败数: {self.stats['failed_dynamics']}")
        if include_comments:
            self.logger.info(f"总评论数: {self.stats['total_comments']}")
        self.logger.info(f"耗时: {duration}")
        
        return self.stats


class BilibiliDynamicManager:
    """Bilibili动态管理器 - 整合动态相关功能"""
    
    def __init__(self, download_dir: str = "downloads", max_concurrent: int = 1, 
                 credential: Optional[Credential] = None, max_comments: int = -1,
                 base_wait_time: float = 0.1, full_sub_comments: bool = False):
        """
        初始化动态管理器
        
        Args:
            download_dir: 下载目录
            max_concurrent: 最大并发数
            credential: B站登录凭据
            max_comments: 每个动态最大评论数限制 (-1 表示无限制)
            base_wait_time: 请求之间的基本等待时间（秒，默认0.1秒）
            full_sub_comments: 是否获取完整楼中楼评论 (False=仅使用内嵌楼中楼, True=单独获取完整楼中楼)
        """
        self.download_dir = Path(download_dir)
        self.credential = credential
        
        # 创建动态爬取器
        self.dynamics_crawler = DynamicsCrawler(
            credential=credential, 
            max_concurrent=max_concurrent,
            max_comments_per_dynamic=max_comments,
            base_wait_time=base_wait_time,
            full_sub_comments=full_sub_comments
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
                dynamics_data = await self.dynamics_crawler._get_dynamics_page(user_obj, offset)
                
                if not dynamics_data or not dynamics_data.get('items'):
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
                await asyncio.sleep(0.1)
                
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
                                   max_comments: int = -1, start_page: int = 0, total_pages: int = 0) -> None:
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
                include_comments=include_comments,
                start_page=start_page,
                max_pages=total_pages if total_pages > 0 else None
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
    
    @api_retry_decorator()
    async def _get_dynamic_info(self, dynamic_obj: Dynamic) -> Dict:
        """获取单个动态的详细信息"""
        return await dynamic_obj.get_info()

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
            dynamic_info = await self._get_dynamic_info(dynamic_obj)
            
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