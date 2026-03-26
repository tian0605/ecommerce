# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.

---

## 截图上传飞书文档流程

### 步骤

```python
# 1. 截图服务器桌面
DISPLAY=:10 python3 -c "
from PIL import Image, ImageGrab
img = ImageGrab.grab()
img.save('/tmp/desktop.png')
"

# 2. 缩小图片（可选，方便查看）
python3 -c "
from PIL import Image
img = Image.open('/tmp/desktop.png')
img_small = img.resize((1280, 800), Image.Resampling.LANCZOS)
img_small.save('/tmp/desktop_small.png', quality=85)
"

# 3. 创建飞书文档（如不存在）
feishu_doc(action="create", title="截图专用")

# 4. 上传图片到文档
feishu_doc(action="upload_image", doc_token="文档token", file_path="/tmp/desktop.png", filename="screenshot.png")

# 5. 发送消息到飞书群
message(action="send", channel="feishu", message="截图说明", media="/tmp/desktop_small.png")
```

### 关键点
- `DISPLAY=:10` 用于截取xrdp远程桌面的屏幕
- 图片先缩小再发送，原始图上传到飞书文档存档
- 飞书文档token从创建返回结果获取

