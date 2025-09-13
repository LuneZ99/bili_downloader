# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Essential Commands

### Installation and Setup
```bash
pip install -r requirements.txt
ffmpeg -version  # Verify FFmpeg is installed
```

### Main CLI Usage
```bash
python bili_cli.py --help                              # Show all commands
python bili_cli.py --show-formats                      # List available quality formats

# Single video operations
python bili_cli.py download-video BV1FQbPzKEA8          # Download single video
python bili_cli.py download-video BV1FQbPzKEA8 --dir /path/to/download

# User operations
python bili_cli.py list-videos 477317922               # List user's videos
python bili_cli.py download-user 477317922 --concurrent 5

# Series/collection operations  
python bili_cli.py list-series 477317922               # List user's collections
python bili_cli.py list-series-videos 123456 --type season
python bili_cli.py download-series 123456 --type auto

# Dynamics operations (NEW)
python bili_cli.py list-dynamics 477317922 --limit 10  # List user's recent dynamics
python bili_cli.py download-dynamics 477317922         # Download all dynamics and ALL comments
python bili_cli.py download-dynamics 477317922 --no-comments --max-comments 500
python bili_cli.py download-single-dynamic 123456789   # Download single dynamic
```

### Credential Configuration (for high-quality downloads)
```bash
cp credentials.json.example credentials.json
# Then edit credentials.json with SESSDATA, bili_jct, buvid3, DedeUserID from browser
```

## Architecture Overview

### Three-Layer Design
- **`bili_cli.py`**: CLI interface using argparse, handles command routing and argument parsing
- **`video.py`**: Video management (`BilibiliVideoManager` class) and core download engine (`VideoDownloader` class)
- **`dynamic.py`**: Dynamics management (`BilibiliDynamicManager` class) and crawler (`DynamicsCrawler` class)

### Key Architectural Patterns
- **Async/await throughout**: All I/O operations use asyncio for concurrent execution
- **Semaphore-controlled concurrency**: Uses `asyncio.Semaphore(max_concurrent)` for download throttling
- **Bilibili API integration**: Built on `bilibili-api-python` library for official API access
- **Stream detection and processing**: Handles FLV/MP4 direct streams and DASH audio/video separation

## Core Workflows

### Video Download Flow (Restructured)
1. **Video info retrieval**: `get_video_info()` fetches complete metadata via bilibili-api
2. **Folder creation**: Creates dedicated folder for each video using safe filename processing
3. **Metadata saving**: Saves complete video info + pages data to `metadata.json`
4. **Multi-page processing**: Downloads each part (P01, P02, ...) separately with proper naming
5. **Stream detection**: `VideoDownloadURLDataDetecter` identifies best available quality per page
6. **Download strategy per page**:
   - **FLV/MP4 streams**: Direct download + FFmpeg format conversion
   - **DASH streams**: Separate audio/video download + FFmpeg merging
7. **Danmaku integration**: Automatic per-page danmaku download alongside videos
8. **File organization**: Clean structure with videos, danmaku, and metadata in dedicated folders

### Dynamics Crawling Flow (NEW)
1. **User dynamics retrieval**: `get_user_all_dynamics()` paginated fetching via `user.get_dynamics_new()`
2. **Comment extraction**: `get_dynamic_comments()` for each dynamic using `comment.get_comments_lazy()`
3. **Sub-comment traversal**: `get_sub_comments()` for nested replies (楼中楼)
4. **Data structure**: JSON format with dynamic info, comments hierarchy, and metadata
5. **Concurrent processing**: Semaphore-controlled parallel comment fetching

## Configuration and Dependencies

### Required Dependencies
- **FFmpeg**: Essential for video format conversion and audio/video merging
- **bilibili-api-python>=16.0.0**: Official API wrapper
- **aiohttp>=3.8.0**: Async HTTP client for downloads
- **aiofiles>=23.0.0**: Async file I/O

### Authentication System
- **credentials.json**: Primary auth method with SESSDATA, bili_jct, buvid3, DedeUserID
- **Environment variables**: Alternative using BILI_SESSDATA, BILI_JCT, etc.
- **Quality impact**: Unauthenticated = basic quality, authenticated = high quality + member-exclusive formats

## Key Implementation Details

### Concurrent Download Management
```python
semaphore = asyncio.Semaphore(max_concurrent)
tasks = [downloader.download_single_video(bvid, folder, semaphore) for bvid in bvids]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

### Quality Selection Logic
- Automatic best quality detection based on user credentials and membership status
- Quality mapping: 360P(16) → 480P(32) → 720P(64) → 1080P(80) → 1080P+(112) → 1080P60(116) → 4K(120) → HDR(125) → 8K(127)

### Error Handling Patterns
- Comprehensive logging via Python logging module to `logs.txt` (configurable via `--log-file`)
- Exception handling with graceful degradation
- Progress reporting during downloads with percentage completion

### File Safety and Filename Processing
- **Smart character mapping**: Converts problematic characters to full-width equivalents for cross-platform compatibility
  - `/` → `／` (full-width slash)
  - `?` → `？` (Chinese question mark)  
  - `:` → `：` (Chinese colon)
  - `<>` → `〈〉` (full-width angle brackets)
  - `|` → `｜` (full-width vertical bar)
  - `"` → `"` (Chinese quotation mark)
  - `*` → `＊` (full-width asterisk)
  - `\` → `＼` (full-width backslash)
- **Extended length support**: 255 characters for main titles, 50 characters for multi-part video segments
- **Unicode preservation**: Fully preserves Chinese, Japanese, and other Unicode characters
- **Automatic directory creation** with proper permissions

## Dynamics Feature Details (NEW)

### Data Structure
```json
{
  "dynamic_info": { /* Complete dynamic metadata */ },
  "comments": {
    "root_comments": [ /* First-level comments */ ],
    "sub_comments": { 
      "rpid_123": [ /* Nested replies for comment 123 */ ]
    },
    "total_count": 456
  },
  "metadata": {
    "crawl_time": "2024-01-01T12:00:00",
    "dynamic_type": "DYNAMIC_TYPE_DRAW",
    "dynamic_id": "789"
  }
}
```

### Comment Type Detection
- **DYNAMIC_TYPE_AV**: Video dynamics → `CommentResourceType.VIDEO`
- **DYNAMIC_TYPE_DRAW**: Image/text dynamics → `CommentResourceType.DYNAMIC_DRAW`
- **DYNAMIC_TYPE_ARTICLE**: Article dynamics → `CommentResourceType.ARTICLE`
- **DYNAMIC_TYPE_WORD**: Text-only dynamics → `CommentResourceType.DYNAMIC`

### Rate Limiting and Error Handling
- Built-in delays between requests (0.1-0.5s, configurable via --wait-time)
- Automatic retry logic for network failures
- **Default: Download ALL comments** (max_comments_per_dynamic = -1)
- Optional comment limits can be set via --max-comments parameter
- Skip-existing functionality for incremental updates