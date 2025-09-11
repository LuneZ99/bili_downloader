# Bili Downloader | B站视频下载工具

### 📝 项目介绍

Bili Downloader 是一个功能强大的 Bilibili 视频下载工具，支持高画质视频下载、批量下载、合集下载等多种功能。采用现代化的异步架构，提供高效稳定的下载体验。

### ✨ 功能特性

#### 视频下载功能
- 🎥 **单个视频下载** - 支持通过 BVID 下载任意视频
- 👤 **用户视频批量下载** - 下载指定用户的所有投稿视频
- 📚 **合集下载** - 支持下载完整的视频合集/系列
- 📋 **视频列表查看** - 浏览用户视频和合集信息
- 📝 **弹幕下载** - 默认同时下载视频弹幕，支持普通弹幕和特殊弹幕(BAS)
- 🔐 **登录支持** - 支持登录获取高画质视频
- ⚡ **并发下载** - 可调节的多线程并发下载
- 🎨 **自动画质选择** - 根据账号权限自动选择最佳画质
- 🔄 **自动格式处理** - 支持 FLV/MP4/DASH 格式自动转换
- 📁 **智能目录管理** - 自动创建分类下载目录

#### 动态爬取功能 🆕
- 📱 **用户动态获取** - 获取指定用户的全部动态
- 💬 **评论完整爬取** - 默认获取全部评论和楼中楼回复
- 📊 **数据结构化保存** - JSON 格式保存，便于后续分析
- 🚀 **并发处理** - 支持多线程并发爬取评论
- 🎯 **灵活配置** - 可选择性限制评论数量、并发数等
- 🔄 **增量更新** - 支持跳过已存在文件的断点续传

### 🛠️ 系统要求

- **Python**: 3.7 或更高版本
- **FFmpeg**: 用于视频格式转换（必需）
- **操作系统**: Windows / macOS / Linux

### 📦 安装说明

#### 1. 克隆项目
```bash
git clone https://github.com/LuneZ99/bili_downloader.git
cd bili_downloader
```

#### 2. 安装 Python 依赖
```bash
pip install -r requirements.txt
```

#### 3. 安装 FFmpeg
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# macOS (使用 Homebrew)
brew install ffmpeg

# Windows (使用 Chocolatey)
choco install ffmpeg

# 或从官网下载: https://ffmpeg.org/download.html
```

#### 4. 验证安装
```bash
python bili_cli.py --help
ffmpeg -version
```

### 🔑 配置说明

#### 登录凭据配置（可选但推荐）

为了获取高画质视频，建议配置 B站 登录凭据：

1. **复制配置模板**
```bash
cp credentials.json.example credentials.json
```

2. **获取登录凭据**
   > 📖 **详细教程**: [bilibili-api 官方获取凭证指南](https://nemo2011.github.io/bilibili-api/#/get-credential)
   
   - 登录 [bilibili.com](https://www.bilibili.com)
   - 按 F12 打开开发者工具
   - 在工具窗口上方找到 **Application** 选项卡
   - 在左侧找到 **Storage/Cookies**，并选中任一B站域名
   - 在右侧找到并复制以下 Cookie 值：
     - `SESSDATA`
     - `bili_jct`
     - `buvid3`
     - `DedeUserID`
     - `ac_time_value`（可选，用于增强认证）

3. **编辑配置文件**
```json
{
  "SESSDATA": "你的SESSDATA值",
  "bili_jct": "你的bili_jct值", 
  "buvid3": "你的buvid3值",
  "DedeUserID": "你的DedeUserID值",
  "ac_time_value": "你的ac_time_value值"
}
```

#### 环境变量配置（可选）
```bash
export BILI_SESSDATA="你的SESSDATA值"
export BILI_JCT="你的bili_jct值"
export BILI_BUVID3="你的buvid3值"
export BILI_DEDEUSERID="你的DedeUserID值"
export BILI_AC_TIME_VALUE="你的ac_time_value值"
```

### 🚀 使用方法

#### 基本命令

```bash
# 查看帮助
python bili_cli.py --help

# 查看支持的画质格式
python bili_cli.py --show-formats
```

#### 视频相关操作

```bash
# 列出用户所有视频
python bili_cli.py list-videos 477317922

# 下载单个视频（默认包含弹幕）
python bili_cli.py download-video BV1FQbPzKEA8

# 下载视频但不下载弹幕
python bili_cli.py download-video BV1FQbPzKEA8 --no-danmaku

# 下载单个视频到指定目录
python bili_cli.py download-video BV1FQbPzKEA8 --dir /path/to/download

# 下载用户所有视频（默认包含弹幕）
python bili_cli.py download-user 477317922

# 下载用户视频但不含弹幕，指定并发数
python bili_cli.py download-user 477317922 --concurrent 3 --no-danmaku
```

#### 合集相关操作

```bash
# 列出用户所有合集
python bili_cli.py list-series 477317922

# 列出合集中的所有视频
python bili_cli.py list-series-videos 123456

# 下载整个合集（默认包含弹幕）
python bili_cli.py download-series 123456

# 下载合集但不含弹幕
python bili_cli.py download-series 123456 --no-danmaku

# 指定合集类型下载
python bili_cli.py download-series 123456 --type season
```

#### 动态相关操作 🆕

```bash
# 列出用户最近的动态
python bili_cli.py list-dynamics 477317922

# 列出用户最近10条动态
python bili_cli.py list-dynamics 477317922 --limit 10

# 下载用户所有动态和评论（默认包含全部评论）
python bili_cli.py download-dynamics 477317922

# 下载动态但不包含评论
python bili_cli.py download-dynamics 477317922 --no-comments

# 限制每个动态最多500条评论，使用3个并发
python bili_cli.py download-dynamics 477317922 --max-comments 500 --concurrent 3

# 获取完整楼中楼评论（更慢但更完整）
python bili_cli.py download-dynamics 477317922 --full-sub-comments

# 自定义请求间隔时间（秒），默认0.1秒
python bili_cli.py download-dynamics 477317922 --wait-time 0.5

# 分页下载：从第2页开始，只下载5页动态
python bili_cli.py download-dynamics 477317922 --start-page 2 --total-pages 5

# 下载单个动态和评论
python bili_cli.py download-single-dynamic 123456789

# 下载单个动态但不包含评论
python bili_cli.py download-single-dynamic 123456789 --no-comments

# 下载单个动态使用完整楼中楼评论
python bili_cli.py download-single-dynamic 123456789 --full-sub-comments
```

#### 高级选项

```bash
# 使用登录凭据下载高画质视频
python bili_cli.py download-video BV1FQbPzKEA8 --credentials credentials.json

# 指定画质偏好
python bili_cli.py download-video BV1FQbPzKEA8 --quality 1080p60

# 组合使用多个选项
python bili_cli.py download-user 477317922 --dir ./downloads --concurrent 2 --credentials credentials.json --quality 4k
```

### 📁 项目结构

```
bili_downloader/
├── bili_cli.py              # 主CLI入口点
├── video.py                 # 视频管理器和下载器
├── dynamic.py               # 动态管理器和爬取器 🆕
├── requirements.txt         # Python依赖列表
├── credentials.json.example # 登录凭据模板
├── credentials.json         # 登录凭据文件(需自行创建)
├── README.md               # 项目说明文档
├── CLAUDE.md               # 开发指南
└── downloads/              # 默认下载目录
    ├── single_videos/      # 单独下载的视频 🆕
    │   ├── 视频.mp4        # 视频文件
    │   └── 视频_弹幕.jsonl # 弹幕文件 🆕
    ├── 用户名_UID/         # 用户数据目录
    │   ├── dynamics/       # 动态和评论数据 🆕
    │   └── videos/         # 视频文件和弹幕
    │       ├── 视频.mp4    # 视频文件
    │       └── 视频_弹幕.jsonl # 弹幕文件 🆕
    └── single_dynamics/    # 单个动态下载 🆕
```

### 🎨 支持的画质格式

| 画质 | 描述 | 要求 |
|------|------|------|
| 360P | 流畅画质 | 无需登录 |
| 480P | 清晰画质 | 无需登录 |
| 720P | 高清画质 | 无需登录 |
| 1080P | 超清画质 | 无需登录 |
| 1080P+ | 超清高码率 | 需要登录 |
| 1080P60 | 超清60帧 | 需要大会员 |
| 4K | 4K超高清 | 需要大会员 |
| HDR | HDR真彩 | 需要大会员 |
| 杜比视界 | 杜比视界 | 需要大会员 |
| 8K | 8K超高清 | 需要大会员 |

### ⚙️ 动态爬取参数说明

#### 楼中楼评论获取策略

本工具提供两种楼中楼评论获取策略：

- **默认策略（推荐）**: 使用根评论响应中内嵌的楼中楼数据
  - ✅ **速度快**: 无需额外API请求
  - ✅ **效率高**: 减少服务器负载
  - ⚠️ **部分楼中楼**: 通常只包含前几条楼中楼回复

- **完整策略**: 使用 `--full-sub-comments` 参数单独获取每个根评论的所有楼中楼
  - ✅ **数据完整**: 获取所有楼中楼回复
  - ✅ **无遗漏**: 确保评论数据的完整性
  - ⚠️ **速度较慢**: 需要大量额外API请求
  - ⚠️ **易被限流**: 频繁请求可能触发反爬机制

#### 其他重要参数

- `--wait-time`: 控制请求间隔（默认0.1秒），可适当增加避免被限流
- `--start-page` / `--total-pages`: 支持分页下载，便于增量更新或测试
- `--max-comments`: 限制每个动态的评论数量，避免超大动态消耗过多时间

### 📊 动态数据格式

动态和评论数据以 JSON 格式保存，每个动态一个文件，包含完整的元数据：

```json
{
  "dynamic_info": {
    "id_str": "123456789",
    "type": "DYNAMIC_TYPE_DRAW",
    "modules": {
      "module_author": { "name": "用户名", "pub_ts": 1234567890 },
      "module_dynamic": { /* 动态内容 */ }
    }
  },
  "comments": {
    "root_comments": [
      {
        "rpid": 1001,
        "content": { "message": "评论内容" },
        "member": { "uname": "评论者", "avatar": "头像URL" },
        "rcount": 5,  // 楼中楼数量
        "like": 10    // 点赞数
      }
    ],
    "sub_comments": {
      "1001": [
        { "rpid": 2001, "content": { "message": "楼中楼回复" } }
      ]
    },
    "total_count": 15
  },
  "metadata": {
    "crawl_time": "2024-01-01T12:00:00",
    "dynamic_type": "DYNAMIC_TYPE_DRAW",
    "total_comments": 15
  }
}
```

### 📝 弹幕数据格式

视频弹幕以 JSONL 格式保存（每行一个 JSON 对象），包含完整的原始弹幕数据：

```jsonl
{"type": "regular", "text": "弹幕内容", "dm_time": 123.45, "send_time": 1640995200, "crc32_id": "abc123", "color": "ffffff", "weight": 5, "id_": 12345, "id_str": "12345", "action": "", "mode": 1, "font_size": 25, "is_sub": false, "pool": 0, "attr": 0, "uid": 123456}
{"type": "regular", "text": "另一条弹幕", "dm_time": 150.20, "send_time": 1640995230, "crc32_id": "def456", "color": "ff6699", "weight": 3, "id_": 12346, "id_str": "12346", "action": "", "mode": 1, "font_size": 25, "is_sub": false, "pool": 0, "attr": 0, "uid": -1}
{"type": "special", "content": "BAS特殊弹幕内容", "id_": 54321, "id_str": "54321", "mode": 9, "pool": 2}
```

#### 弹幕字段说明

**普通弹幕 (type: "regular")**:
- `text`: 弹幕文本内容
- `dm_time`: 弹幕在视频中的时间位置（秒）
- `send_time`: 弹幕发送的时间戳
- `crc32_id`: 发送者UID的CRC32哈希值
- `color`: 弹幕颜色（十六进制，"special"表示大会员专属颜色）
- `weight`: 弹幕在弹幕列表显示的权重
- `id_`: 弹幕ID（数字）
- `id_str`: 弹幕ID（字符串）
- `action`: 弹幕动作（用途待明确）
- `mode`: 弹幕类型 (1=滚动, 4=底部, 5=顶部, 6=逆向, 7=高级, 8=代码, 9=BAS)
- `font_size`: 字体大小 (12/16/18/25/36/45/64)
- `is_sub`: 是否为字幕弹幕
- `pool`: 弹幕池 (0=普通, 1=字幕, 2=特殊)
- `attr`: 弹幕属性（用途待明确）
- `uid`: 发送者真实UID（当可获取时，否则为-1）

**特殊弹幕 (type: "special")**:
- `content`: 特殊弹幕内容
- `id_`: 弹幕ID（数字）
- `id_str`: 弹幕ID（字符串）
- `mode`: 弹幕模式（通常为9=BAS弹幕）
- `pool`: 弹幕池（通常为2=特殊池）

> **注意**: 本工具保存弹幕对象的所有可用属性，确保数据完整性。如B站API增加新字段，也会自动包含在内。

#### 文件命名规则

- **单P视频**: `视频标题_弹幕.jsonl`
- **多P视频**: `视频标题_P01_分P标题_弹幕.jsonl`, `视频标题_P02_分P标题_弹幕.jsonl` ...

### 📜 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

### 🤝 贡献

欢迎提交 Issue 和 Pull Request！