# Bili Downloader | B站视频下载工具

### 📝 项目介绍

Bili Downloader 是一个功能强大的 Bilibili 视频下载工具，支持高画质视频下载、批量下载、合集下载等多种功能。采用现代化的异步架构，提供高效稳定的下载体验。

### ✨ 功能特性

- 🎥 **单个视频下载** - 支持通过 BVID 下载任意视频
- 👤 **用户视频批量下载** - 下载指定用户的所有投稿视频
- 📚 **合集下载** - 支持下载完整的视频合集/系列
- 📋 **视频列表查看** - 浏览用户视频和合集信息
- 🔐 **登录支持** - 支持登录获取高画质视频
- ⚡ **并发下载** - 可调节的多线程并发下载
- 🎨 **自动画质选择** - 根据账号权限自动选择最佳画质
- 🔄 **自动格式处理** - 支持 FLV/MP4/DASH 格式自动转换
- 📁 **智能目录管理** - 自动创建分类下载目录

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
   - 登录 [bilibili.com](https://www.bilibili.com)
   - 按 F12 打开开发者工具
   - 切换到 Network 选项卡
   - 刷新页面，找到任意请求
   - 在请求头中复制以下 Cookie 值：
     - `SESSDATA`
     - `bili_jct`
     - `buvid3`
     - `DedeUserID`

3. **编辑配置文件**
```json
{
  "SESSDATA": "你的SESSDATA值",
  "bili_jct": "你的bili_jct值", 
  "buvid3": "你的buvid3值",
  "DedeUserID": "你的DedeUserID值"
}
```

#### 环境变量配置（可选）
```bash
export BILI_SESSDATA="你的SESSDATA值"
export BILI_JCT="你的bili_jct值"
export BILI_BUVID3="你的buvid3值"
export BILI_DEDEUSERID="你的DedeUserID值"
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

# 下载单个视频
python bili_cli.py download-video BV1FQbPzKEA8

# 下载单个视频到指定目录
python bili_cli.py download-video BV1FQbPzKEA8 --dir /path/to/download

# 下载用户所有视频
python bili_cli.py download-user 477317922

# 指定并发数下载用户视频
python bili_cli.py download-user 477317922 --concurrent 5
```

#### 合集相关操作

```bash
# 列出用户所有合集
python bili_cli.py list-series 477317922

# 列出合集中的所有视频
python bili_cli.py list-series-videos 123456

# 下载整个合集
python bili_cli.py download-series 123456

# 指定合集类型下载
python bili_cli.py download-series 123456 --type season
```

#### 高级选项

```bash
# 使用登录凭据下载高画质视频
python bili_cli.py download-video BV1FQbPzKEA8 --credentials credentials.json

# 指定画质偏好
python bili_cli.py download-video BV1FQbPzKEA8 --quality 1080p60

# 组合使用多个选项
python bili_cli.py download-user 477317922 --dir ./downloads --concurrent 3 --credentials credentials.json --quality 4k
```

### 📁 项目结构

```
bili_downloader/
├── bili_cli.py              # 主CLI入口点
├── bili_downloader.py       # 核心视频下载器
├── bili_manager.py          # 高级管理功能
├── requirements.txt         # Python依赖列表
├── credentials.json.example # 登录凭据模板
├── credentials.json         # 登录凭据文件(需自行创建)
├── README.md               # 项目说明文档
└── downloads/              # 默认下载目录
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

### 📜 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

### 🤝 贡献

欢迎提交 Issue 和 Pull Request！