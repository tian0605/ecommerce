#!/usr/bin/env python3
"""统一日志记录器 - 写入 main_logs 表"""
import psycopg2
from datetime import datetime
from typing import Optional
import json

class Logger:
    DB_CONFIG = {
        'host': 'localhost',
        'database': 'ecommerce_data',
        'user': 'superuser',
        'password': 'Admin123!'
    }
    
    def __init__(self, log_type: str = "general"):
        self.log_type = log_type
        self.start_time = datetime.now()
        self.task_name: Optional[str] = None
        self.run_status = "running"
        self.run_message = ""
        self.run_content = ""
        self.log_level = "INFO"
    
    def set_task(self, task_name: str):
        """设置关联任务"""
        self.task_name = task_name
        return self
    
    def set_level(self, level: str):
        """设置日志级别 DEBUG, INFO, WARN, ERROR"""
        self.log_level = level
        return self
    
    def info(self, msg: str):
        print(f"[INFO] {msg}")
    
    def error(self, msg: str):
        print(f"[ERROR] {msg}")
        self.log_level = "ERROR"
    
    def warn(self, msg: str):
        print(f"[WARN] {msg}")
        self.log_level = "WARN"
    
    def debug(self, msg: str):
        print(f"[DEBUG] {msg}")
    
    def set_message(self, msg: str):
        """设置简要信息"""
        self.run_message = msg
        return self
    
    def set_content(self, content: str):
        """设置详细内容"""
        self.run_content = content[-10000:]  # 限制长度
        return self
    
    def finish(self, status: str = "success", message: str = ""):
        """完成日志记录
        
        Args:
            status: running/success/failed/skipped
            message: 简要信息
        """
        if message:
            self.run_message = message
        
        # 强制更新状态（允许从running更新，也允许后续更新）
        self.run_status = status
        
        end_time = datetime.now()
        duration_ms = int((end_time - self.start_time).total_seconds() * 1000)
        
        try:
            conn = psycopg2.connect(**self.DB_CONFIG)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO main_logs (
                    log_type, log_level, task_name,
                    run_start_time, run_end_time, duration_ms,
                    run_status, run_message, run_content
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                self.log_type,
                self.log_level,
                self.task_name,
                self.start_time,
                end_time,
                duration_ms,
                self.run_status,
                (self.run_message or "")[:500],
                (self.run_content or "")[-5000:]
            ))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"[ERROR] Failed to write log: {e}")
        
        return self


def get_logger(log_type: str = "general") -> Logger:
    """获取日志记录器"""
    return Logger(log_type)


if __name__ == '__main__':
    # 测试日志写入
    log = get_logger("test")
    log.set_task("TEST-001").info("测试日志")
    log.finish("success", "测试完成")
    print("✅ 日志记录器测试完成")
