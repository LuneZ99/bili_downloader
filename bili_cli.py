#!/usr/bin/env python3
"""
Bilibili视频管理CLI工具

支持以下功能：
1. 列出用户所有视频 (list-videos)
2. 下载单个视频 (download-video)  
3. 下载用户全部视频 (download-user)
4. 列出用户所有合集 (list-series)
5. 列出合集中的视频 (list-series-videos)
6. 下载合集所有视频 (download-series)

使用方法:
python bili_cli.py list-videos <UID>
python bili_cli.py download-video <BVID> [--dir 目录]
python bili_cli.py download-user <UID> [--dir 目录] [--concurrent 并发数]
python bili_cli.py list-series <UID>
python bili_cli.py list-series-videos <合集ID> [--type series|season]
python bili_cli.py download-series <合集ID> [--type series|season] [--dir 目录]
"""

import asyncio
import argparse
import os
from video import BilibiliVideoManager, VideoDownloader
from dynamic import BilibiliDynamicManager


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Bilibili视频管理CLI工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 视频相关（默认下载弹幕）
  %(prog)s list-videos 477317922                         # 列出用户视频
  %(prog)s download-video BV1FQbPzKEA8                   # 下载单个视频和弹幕
  %(prog)s download-video BV1FQbPzKEA8 --no-danmaku      # 下载视频不含弹幕
  %(prog)s download-user 477317922                       # 下载用户所有视频和弹幕
  
  # 合集相关
  %(prog)s list-series 477317922                         # 列出用户所有合集
  %(prog)s list-series-videos 123456                     # 列出合集中的视频
  %(prog)s download-series 123456 --no-danmaku           # 下载整个合集不含弹幕
  
  # 动态相关
  %(prog)s list-dynamics 477317922                       # 列出用户最近100条动态
  %(prog)s list-dynamics 477317922 --limit 10            # 列出用户最近10条动态
  %(prog)s download-dynamics 477317922                   # 下载用户所有动态和评论
  %(prog)s download-dynamics 477317922 --no-comments     # 下载动态不含评论
  %(prog)s download-single-dynamic 123456789             # 下载单个动态和评论
        """
    )
    
    # 全局参数
    parser.add_argument('--credentials', '-auth', help='B站登录凭据配置文件路径 (JSON格式)')
    parser.add_argument('--quality', '-q', default='auto', 
                      help='画质偏好 (auto/1080p/1080p60/4k/8k等, 默认: auto)')
    parser.add_argument('--log-file', default='logs.txt',
                      help='日志文件路径 (默认: logs.txt)')
    parser.add_argument('--show-formats', action='store_true', 
                      help='显示可用的画质格式信息')
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # list-videos 子命令
    parser_list = subparsers.add_parser('list-videos', help='列出用户所有视频')
    parser_list.add_argument('uid', type=int, help='用户UID')
    
    # download-video 子命令  
    parser_download = subparsers.add_parser('download-video', help='下载单个视频')
    parser_download.add_argument('bvid', help='视频BVID')
    parser_download.add_argument('--dir', '-d', default='downloads', help='下载目录 (默认: downloads)')
    parser_download.add_argument('--no-danmaku', action='store_true', help='不下载弹幕 (默认下载弹幕)')
    
    # download-user 子命令
    parser_download_all = subparsers.add_parser('download-user', help='下载用户所有视频')
    parser_download_all.add_argument('uid', type=int, help='用户UID')
    parser_download_all.add_argument('--dir', '-d', default='downloads', help='下载目录 (默认: downloads)')
    parser_download_all.add_argument('--concurrent', '-c', type=int, default=1, help='最大并发下载数 (默认: 1)')
    parser_download_all.add_argument('--no-danmaku', action='store_true', help='不下载弹幕 (默认下载弹幕)')
    
    # list-series 子命令
    parser_list_collections = subparsers.add_parser('list-series', help='列出用户所有合集')
    parser_list_collections.add_argument('uid', type=int, help='用户UID')
    
    # list-series-videos 子命令
    parser_list_collection_videos = subparsers.add_parser('list-series-videos', help='列出合集中的所有视频')
    parser_list_collection_videos.add_argument('series_id', type=int, help='合集ID')
    parser_list_collection_videos.add_argument('--type', '-t', default='auto', choices=['auto', 'series', 'season'], help='合集类型 (默认: auto自动检测)')
    
    # download-series 子命令
    parser_download_collection = subparsers.add_parser('download-series', help='下载合集中的所有视频')
    parser_download_collection.add_argument('series_id', type=int, help='合集ID')
    parser_download_collection.add_argument('--type', '-t', default='auto', choices=['auto', 'series', 'season'], help='合集类型 (默认: auto自动检测)')
    parser_download_collection.add_argument('--dir', '-d', default='downloads', help='下载目录 (默认: downloads)')
    parser_download_collection.add_argument('--concurrent', '-c', type=int, default=1, help='最大并发下载数 (默认: 1)')
    parser_download_collection.add_argument('--no-danmaku', action='store_true', help='不下载弹幕 (默认下载弹幕)')
    
    # list-dynamics 子命令
    parser_list_dynamics = subparsers.add_parser('list-dynamics', help='列出用户最近的动态')
    parser_list_dynamics.add_argument('uid', type=int, help='用户UID')
    parser_list_dynamics.add_argument('--limit', '-l', type=int, help='显示动态数量限制 (默认: 100)')
    
    # download-dynamics 子命令
    parser_download_dynamics = subparsers.add_parser('download-dynamics', help='下载用户所有动态和评论')
    parser_download_dynamics.add_argument('uid', type=int, help='用户UID')
    parser_download_dynamics.add_argument('--dir', '-d', default='downloads', help='下载目录 (默认: downloads)')
    parser_download_dynamics.add_argument('--concurrent', '-c', type=int, default=1, help='最大并发下载数 (默认: 1)')
    parser_download_dynamics.add_argument('--no-comments', action='store_true', help='不包含评论 (默认包含)')
    parser_download_dynamics.add_argument('--max-comments', type=int, default=-1, help='每个动态最大评论数限制 (-1 表示无限制, 默认: -1)')
    parser_download_dynamics.add_argument('--wait-time', type=float, default=5.0, help='请求之间的基本等待时间（秒）')
    parser_download_dynamics.add_argument('--full-sub-comments', action='store_true', 
                                        help='获取完整楼中楼评论 (默认使用内嵌楼中楼，速度更快)')
    parser_download_dynamics.add_argument(
        "--start-page",
        type=int,
        default=0,
        help="起始页面 (0表示从最新动态开始)",
    )
    parser_download_dynamics.add_argument(
        "--total-pages",
        type=int,
        default=0,
        help="总共爬取页面数 (0表示爬取所有页面)",
    )
    
    # download-single-dynamic 子命令
    parser_download_single_dynamic = subparsers.add_parser('download-single-dynamic', help='下载单个动态和评论')
    parser_download_single_dynamic.add_argument('dynamic_id', type=int, help='动态ID')
    parser_download_single_dynamic.add_argument('--dir', '-d', default='downloads', help='下载目录 (默认: downloads)')
    parser_download_single_dynamic.add_argument('--no-comments', action='store_true', help='不包含评论 (默认包含)')
    parser_download_single_dynamic.add_argument('--full-sub-comments', action='store_true', 
                                              help='获取完整楼中楼评论 (默认使用内嵌楼中楼，速度更快)')
    
    args = parser.parse_args()
    
    # 显示画质格式信息
    if args.show_formats:
        print("📺 支持的画质格式:")
        formats = [
            ("360P", "流畅画质", "无需登录"),
            ("480P", "清晰画质", "无需登录"),
            ("720P", "高清画质", "无需登录"),
            ("1080P", "超清画质", "无需登录"),
            ("1080P+", "超清高码率", "需要登录"),
            ("1080P60", "超清60帧", "需要大会员"),
            ("4K", "4K超高清", "需要大会员"),
            ("HDR", "HDR真彩", "需要大会员"),
            ("杜比视界", "杜比视界", "需要大会员"),
            ("8K", "8K超高清", "需要大会员")
        ]
        for quality, desc, auth in formats:
            print(f"  {quality:12} - {desc:12} ({auth})")
        print()
        return
    
    if not args.command:
        parser.print_help()
        return
    
    # 加载登录凭据
    credential = None
    if args.credentials:
        credential = VideoDownloader.load_credentials(args.credentials, args.log_file)
        if not credential:
            print("❌ 凭据加载失败，将使用普通画质下载")
    
    print("🎬 Bilibili视频管理工具")
    print("-" * 40)
    
    try:
        # 创建视频管理器
        video_manager = BilibiliVideoManager(
            download_dir=getattr(args, 'dir', 'downloads'),
            max_concurrent=getattr(args, 'concurrent', 1),
            credential=credential,
            preferred_quality=getattr(args, 'quality', 'auto'),
            log_file=args.log_file
        )
        
        # 创建动态管理器
        dynamic_manager = BilibiliDynamicManager(
            download_dir=getattr(args, 'dir', 'downloads'),
            max_concurrent=getattr(args, 'concurrent', 1),
            credential=credential,
            max_comments=getattr(args, 'max_comments', -1),
            base_wait_time=getattr(args, 'wait_time', 5.0),
            full_sub_comments=getattr(args, 'full_sub_comments', False),
            log_file=args.log_file
        )
        
        # 执行命令
        if args.command == 'list-videos':
            asyncio.run(video_manager.list_user_videos(args.uid))
        elif args.command == 'download-video':
            download_danmaku = not args.no_danmaku
            asyncio.run(video_manager.download_single_video(args.bvid, download_danmaku=download_danmaku))
        elif args.command == 'download-user':
            download_danmaku = not args.no_danmaku
            asyncio.run(video_manager.download_user_videos(args.uid, download_danmaku=download_danmaku))
        elif args.command == 'list-series':
            asyncio.run(video_manager.list_user_collections(args.uid))
        elif args.command == 'list-series-videos':
            asyncio.run(video_manager.list_collection_videos(args.series_id, args.type))
        elif args.command == 'download-series':
            download_danmaku = not args.no_danmaku
            asyncio.run(video_manager.download_collection_videos(args.series_id, args.type, download_danmaku=download_danmaku))
        elif args.command == 'list-dynamics':
            asyncio.run(dynamic_manager.list_user_dynamics(args.uid, args.limit))
        elif args.command == 'download-dynamics':
            include_comments = not args.no_comments
            asyncio.run(dynamic_manager.download_user_dynamics(
                args.uid,
                include_comments=include_comments,
                max_comments=args.max_comments,
                start_page=args.start_page,
                total_pages=args.total_pages
            ))
        elif args.command == 'download-single-dynamic':
            include_comments = not args.no_comments
            asyncio.run(dynamic_manager.download_single_dynamic(
                args.dynamic_id, 
                include_comments=include_comments
            ))
            
    except KeyboardInterrupt:
        print("\n\n⏹️  操作已中断")
    except Exception as e:
        print(f"\n💥 程序出错: {e}")


if __name__ == "__main__":
    main()