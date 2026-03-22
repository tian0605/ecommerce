# ERRORS.md - 错误记录

---

## [ERR-20260320-001] feishu_image_send

**Logged**: 2026-03-20T20:37:00+08:00
**Priority**: high
**Status**: resolved
**Area**: infra

### Summary
飞书发送图片失败，message工具的media参数不工作

### Error
```
channel: "feishu"
mediaUrl: "/tmp/test_1688_weight.jpg"
result: { messageId: "om_xxx", mediaUrl: "/tmp/test_1688_weight.jpg" }
# 但用户收到的是空白图片或显示失败
```

### Context
- 尝试用 message 工具的 media 参数发送截图
- 图片文件存在且格式正确（32KB, 1280x720 JPEG）
- 飞书API返回成功但用户看不到图片

### Suggested Fix
使用飞书原生API上传图片：
```python
# 1. 获取token
POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal

# 2. 上传图片
POST https://open.feishu.cn/open-apis/im/v1/images
Headers: Authorization: Bearer {token}
Form: image_type=message, image=@/path/to/file.jpg
Response: { data: { image_key: "img_v3_xxx" } }

# 3. 发送图片消息
POST https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id
Body: { receive_id: "chat_id", msg_type: "image", content: "{\"image_key\": \"img_v3_xxx\"}" }
```

### Resolution
- **Resolved**: 2026-03-20T20:37:00+08:00
- **Commit**: scripts/feishu_send_image.py
- **Notes**: 创建专用脚本封装飞书图片发送流程

### Metadata
- Reproducible: yes
- Related Files: scripts/feishu_send_image.py
- See Also: LRN-20260320-001

---
## [ERR-20260320-002] browser_relay_token

**Logged**: 2026-03-20T22:10:00+08:00
**Priority**: high
**Status**: wont_fix
**Area**: infra

### Summary
Browser Relay连接失败：Gateway token rejected

### Error
```
Gateway token rejected. Check token and save again.
```

### Context
- Chrome扩展已安装
- Gateway token配置正确（6766d8bbfe9d6e5322b6c14a20505dab5340407c2097374e）
- 但连接失败

### Root Cause
Browser Relay架构要求Chrome和Gateway在同一机器，或需要本地运行relay服务。Gateway在远程服务器，Chrome在本地，不满足此架构。

### Suggested Fix
替代方案：用户本地运行Python脚本直接采集1688数据

### Resolution
- **Resolved**: 2026-03-20T22:10:00+08:00
- **Notes**: 改用本地脚本方案，需要用户本地Python环境

### Metadata
- Reproducible: yes (架构限制)
- Related Files: scripts/feishu_send_image.py
- See Also: LRN-20260320-003

---

---
## [ERR-20260322-001] cookie_expired

**Logged**: 2026-03-22T21:56:00+08:00
**Priority**: high
**Status**: monitoring
**Area**: infra

### Summary
妙手ERP Cookies超过24小时需要更新

### Context
HEARTBEAT.md中的前置条件检查显示：
- Cookies文件存在但超过24小时
- 可能导致采集/提取失败

### Suggested Fix
提醒用户定期更新Cookie，或实现自动刷新机制

### Resolution
- **Status**: monitoring
- **Notes**: 需要用户手动更新Cookie文件

### Metadata
- Related Files: /home/ubuntu/.openclaw/skills/miaoshou-collector/miaoshou_cookies.json
- Tags: cookie, miaoshou, session
