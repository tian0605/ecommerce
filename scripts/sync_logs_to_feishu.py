#!/usr/bin/env python3
"""
sync_logs_to_feishu.py - 同步main_logs到飞书电子表格

功能：
- 每10分钟增量同步新增日志到飞书电子表格
- 记录最后同步时间到本地文件
- 方便远程办公时查看任务执行情况

用法：
- 手动执行: python3 sync_logs_to_feishu.py
- 定时任务: */10 * * * * python3 sync_logs_to_feishu.py
"""
import sys
import os
import json
import psycopg2
from datetime import datetime, timedelta
from pathlib import Path

# 添加路径
WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
sys.path.insert(0, str(WORKSPACE / 'scripts'))

# 飞书表格配置
FEISHU_APP_TOKEN = "CcahbCiYLaaFlgsMzs5cmbc6nId"
FEISHU_TABLE_ID = "tblZGXbXvQ8Qr0vS"

# 最后同步时间文件
LAST_SYNC_FILE = WORKSPACE / "logs" / ".last_feishu_sync.json"

# 飞书API配置
FEISHU_APP_ID = os.environ.get('FEISHU_APP_ID', 'cli_a933f5b61d39dcb5')
FEISHU_APP_SECRET = os.environ.get('FEISHU_APP_SECRET', 'CFuYjJZtEOFVfIhXINopPe4haJUul0cY')

def get_feishu_token():
    """获取飞书访问令牌"""
    import requests
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    data = {
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    }
    resp = requests.post(url, json=data)
    return resp.json().get("tenant_access_token", "")

def get_last_sync_time():
    """获取上次同步时间"""
    if LAST_SYNC_FILE.exists():
        with open(LAST_SYNC_FILE, 'r') as f:
            data = json.load(f)
            return data.get('last_sync_time')
    return None

def save_last_sync_time(sync_time):
    """保存本次同步时间"""
    LAST_SYNC_FILE.parent.mkdir(exist_ok=True)
    with open(LAST_SYNC_FILE, 'w') as f:
        json.dump({'last_sync_time': sync_time}, f)

def get_new_logs(since_time):
    """获取指定时间后的新日志"""
    conn = psycopg2.connect(
        host='localhost',
        database='ecommerce_data',
        user='superuser',
        password='Admin123!'
    )
    cur = conn.cursor()
    
    if since_time:
        cur.execute("""
            SELECT 
                id, task_name, log_type, log_level,
                run_status, run_message, run_content,
                run_start_time, run_end_time, duration_ms,
                created_at
            FROM main_logs
            WHERE created_at > %s
            ORDER BY created_at ASC
            LIMIT 500
        """, (since_time,))
    else:
        # 首次同步，获取最近24小时的日志
        cur.execute("""
            SELECT 
                id, task_name, log_type, log_level,
                run_status, run_message, run_content,
                run_start_time, run_end_time, duration_ms,
                created_at
            FROM main_logs
            WHERE created_at > NOW() - INTERVAL '24 hours'
            ORDER BY created_at ASC
            LIMIT 500
        """)
    
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def sync_to_feishu(logs):
    """同步日志到飞书表格"""
    if not logs:
        print("[INFO] 没有新日志需要同步")
        return 0
    
    import requests
    
    # 获取token
    token = get_feishu_token()
    if not token:
        print("[ERROR] 获取飞书token失败")
        return 0
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # 批量创建记录（每批100条）
    batch_size = 100
    total_synced = 0
    
    for i in range(0, len(logs), batch_size):
        batch = logs[i:i+batch_size]
        records = []
        
        for row in batch:
            (log_id, task_name, log_type, log_level,
             run_status, run_message, run_content,
             run_start, run_end, duration_ms, created_at) = row
            
            # 截断过长内容
            message = (run_message or "")[:200]
            content = (run_content or "")[:1000] if run_content else ""
            
            # 转换时间戳
            if created_at:
                if isinstance(created_at, str):
                    created_at_str = created_at
                else:
                    created_at_str = created_at.isoformat()
            else:
                created_at_str = None
            
            record = {
                "fields": {
                    "任务名": task_name or "",
                    "运行状态": run_status or "",
                    "简要消息": message,
                    "详细内容": content,
                    "耗时(毫秒)": duration_ms if duration_ms else 0
                }
            }
            
            # 添加执行时间（需要转时间戳毫秒）
            if created_at:
                if isinstance(created_at, datetime):
                    ts_ms = int(created_at.timestamp() * 1000)
                else:
                    ts_ms = None
                if ts_ms:
                    record["fields"]["执行时间"] = ts_ms
            
            records.append(record)
        
        # 调用飞书API批量创建
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records/batch_create"
        
        resp = requests.post(url, headers=headers, json={"records": records})
        
        if resp.status_code == 200:
            result = resp.json()
            if result.get("code") == 0:
                total_synced += len(records)
                print(f"[INFO] 成功同步 {len(records)} 条记录")
            else:
                print(f"[ERROR] 飞书API错误: {result}")
        else:
            print(f"[ERROR] HTTP错误: {resp.status_code} - {resp.text[:200]}")
    
    return total_synced

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] sync_logs_to_feishu 启动")
    
    # 获取上次同步时间
    last_sync = get_last_sync_time()
    if last_sync:
        print(f"[INFO] 上次同步时间: {last_sync}")
        since_time = datetime.fromisoformat(last_sync)
    else:
        print(f"[INFO] 首次同步，将获取最近24小时数据")
        since_time = None
    
    # 获取新日志
    logs = get_new_logs(since_time)
    print(f"[INFO] 发现 {len(logs)} 条新日志")
    
    if not logs:
        print("[INFO] 没有需要同步的日志")
        return
    
    # 同步到飞书
    synced = sync_to_feishu(logs)
    print(f"[INFO] 共同步 {synced} 条记录到飞书")
    
    # 更新同步时间
    current_time = datetime.now().isoformat()
    save_last_sync_time(current_time)
    print(f"[INFO] 已更新同步时间: {current_time}")

if __name__ == '__main__':
    main()
