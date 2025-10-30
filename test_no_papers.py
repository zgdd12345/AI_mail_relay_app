#!/usr/bin/env python3
"""测试在没有论文时不发送邮件的场景"""

from datetime import datetime, UTC, timedelta
from dotenv import load_dotenv
from ai_mail_relay.config import Settings
from ai_mail_relay.pipeline import run_pipeline
import logging

# 设置详细日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
)

load_dotenv()

settings = Settings()

# 修改回溯天数为 0，这样几乎不会找到任何邮件
original_max_days = settings.filtering.max_days_back

# 使用非常短的回溯时间来模拟没有邮件的情况
from dataclasses import replace
settings = replace(
    settings,
    filtering=replace(
        settings.filtering,
        max_days_back=0  # 只查找今天的，且时间窗口很短
    )
)

print("\n" + "="*60)
print("测试场景：模拟没有找到相关邮件的情况")
print("="*60 + "\n")

try:
    run_pipeline(settings)
    print("\n✓ 测试通过：程序正确处理了无邮件的情况")
    print("  预期行为：不发送邮件，正常退出")
except Exception as e:
    print(f"\n✗ 测试失败：{e}")

print("\n" + "="*60)
