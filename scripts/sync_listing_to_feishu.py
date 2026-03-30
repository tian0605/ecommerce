#!/usr/bin/env python3
"""
sync_listing_to_feishu.py - 增量同步 product_listing_info 到飞书表格

功能：
- 查询数据库中 pending 状态的记录
- 根据 alibaba_product_id 判断：存在则更新，不存在则创建
- 同步到飞书 Bitable

用法：
    python3 sync_listing_to_feishu.py
"""
import sys
import os
import json
import requests
import psycopg2
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from load_env import get_db_config

# 飞书 Bitable 配置
FEISHU_APP_TOKEN = "Xc4pbqRqsaozGwssDpAcd8qGn5b"
FEISHU_TABLE_ID = "tblr24mcoxAoGeOb"

# 飞书API认证配置
FEISHU_APP_ID = os.environ.get('FEISHU_APP_ID', 'cli_a933f5b61d39dcb5')
FEISHU_APP_SECRET = os.environ.get('FEISHU_APP_SECRET', 'CFuYjJZtEOFVfIhXINopPe4haJUul0cY')

# 数据库配置
DB_CONFIG = get_db_config()


def get_feishu_token():
    """获取飞书访问令牌"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    data = {
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    }
    try:
        resp = requests.post(url, json=data, timeout=10)
        return resp.json().get("tenant_access_token", "")
    except Exception as e:
        print(f"获取token失败: {e}")
        return ""


def get_all_records(token):
    """获取飞书表格所有记录，返回 {货源ID: record_id} 映射"""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records"
    
    headers = {"Authorization": f"Bearer {token}"}
    
    records_map = {}
    page_token = None
    
    while True:
        params = {"page_size": 100}
        if page_token:
            params["page_token"] = page_token
        
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            result = resp.json()
            
            if result.get('code') != 0:
                print(f"获取记录失败: {result}")
                break
            
            data = result.get('data', {})
            records = data.get('items', [])
            
            for record in records:
                fields = record.get('fields', {})
                source_id = fields.get('货源ID', '')
                if source_id:
                    records_map[str(source_id)] = record.get('record_id')
            
            # 检查是否还有下一页
            if data.get('has_more'):
                page_token = data.get('page_token')
            else:
                break
                
        except Exception as e:
            print(f"获取记录异常: {e}")
            break
    
    return records_map


def build_fields(row):
    """构建飞书字段"""
    # 计算尺寸（长*宽*高）
    length = float(row[5]) if row[5] else 0
    width = float(row[6]) if row[6] else 0
    height = float(row[7]) if row[7] else 0
    dimension = f"{length}*{width}*{height}" if length and width and height else ""
    
    return {
        "货源ID": str(row[0]),
        "主货号": str(row[1]),
        "优化标题": str(row[2])[:500] if row[2] else "",
        "优化描述": str(row[3])[:2000] if row[3] else "",
        "重量kg": float(row[4]) if row[4] else 0,
        "长cm": length,
        "宽cm": width,
        "高cm": height,
        "尺寸": dimension,
        "一级类目": str(row[8]) if row[8] else "",
        "二级类目": str(row[9]) if row[9] else "",
        "三级类目": str(row[10]) if row[10] else "",
        "状态": str(row[11]) if row[11] else "pending",
    }


def create_record(token, fields):
    """创建新记录"""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    try:
        resp = requests.post(url, json={"fields": fields}, headers=headers, timeout=30)
        return resp.json()
    except Exception as e:
        print(f"创建记录失败: {e}")
        return None


def update_record(token, record_id, fields):
    """更新已有记录"""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records/{record_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    try:
        resp = requests.put(url, json={"fields": fields}, headers=headers, timeout=30)
        return resp.json()
    except Exception as e:
        print(f"更新记录失败: {e}")
        return None


def get_pending_records():
    """获取待同步的记录"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            alibaba_product_id,
            product_id_new,
            optimized_title,
            optimized_description,
            package_weight_kg,
            package_length,
            package_width,
            package_height,
            category_level1,
            category_level2,
            category_level3,
            status
        FROM product_listing_info
        WHERE status = 'pending'
        ORDER BY updated_at DESC
    """)
    
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    return rows


def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始同步 product_listing_info 到飞书...")
    
    # 获取 token
    token = get_feishu_token()
    if not token:
        print("❌ 无法获取飞书访问令牌")
        return
    
    # 获取飞书表格现有记录
    print("获取飞书表格现有记录...")
    feishu_records = get_all_records(token)
    print(f"飞书表格已有 {len(feishu_records)} 条记录")
    
    # 获取待同步记录
    rows = get_pending_records()
    print(f"待同步记录: {len(rows)} 条")
    
    if not rows:
        print("没有待同步记录")
        return
    
    created_count = 0
    updated_count = 0
    
    for row in rows:
        alibaba_id = str(row[0])
        fields = build_fields(row)
        
        try:
            if alibaba_id in feishu_records:
                # 记录存在，执行更新
                record_id = feishu_records[alibaba_id]
                result = update_record(token, record_id, fields)
                
                if result and result.get('code') == 0:
                    print(f"  🔄 {alibaba_id}: 更新成功 (record_id={record_id})")
                    updated_count += 1
                else:
                    print(f"  ❌ {alibaba_id}: 更新失败 - {result}")
            else:
                # 记录不存在，执行创建
                result = create_record(token, fields)
                
                if result and result.get('code') == 0:
                    new_record_id = result.get('data', {}).get('record', {}).get('record_id', '')
                    print(f"  ✅ {alibaba_id}: 创建成功 (record_id={new_record_id})")
                    created_count += 1
                else:
                    print(f"  ❌ {alibaba_id}: 创建失败 - {result}")
                
        except Exception as e:
            print(f"  ❌ {alibaba_id}: 异常 - {e}")
    
    print(f"\n同步完成: 创建 {created_count} 条, 更新 {updated_count} 条")


if __name__ == '__main__':
    main()
