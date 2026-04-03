#!/usr/bin/env python3
"""
Approve/Reject 脚本 — 取代 lead Agent 的审批功能

Usage:
    # 批量通过
    python orchestration/v2/scripts/approve.py feat1 feat2 feat3

    # 批量拒绝
    python orchestration/v2/scripts/approve.py --reject feat1 --reason WEAK_SIGNAL --note "Sharpe 太低"

    # 列出待审核
    python orchestration/v2/scripts/approve.py --list

    # 查看详情
    python orchestration/v2/scripts/approve.py --show feat1
"""

import argparse
import os
import shutil
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PENDING_DIR = os.path.join(PROJECT_DIR, 'research', 'pending-rawdata')
WAITING_DIR = os.path.join(PROJECT_DIR, 'research', 'waiting-rawdata')
REJECTED_DIR = os.path.join(PROJECT_DIR, 'research', 'rejected-rawdata')
FEEDBACK_DIR = os.path.join(PROJECT_DIR, 'research', 'agent_reports', 'feedback')
TG_SEND = os.path.join(PROJECT_DIR, 'orchestration', 'tg_send.py')

REJECT_REASONS = {
    'WEAK_SIGNAL': '信号太弱',
    'HIGH_CORR': '与已有特征太像',
    'UNSTABLE': '跨窗口不稳健',
    'NO_MONOTONICITY': '分组单调性差',
    'DIRECTION_EXHAUSTED': '方向已充分探索',
    'REVISIT_LATER': '有潜力但优先级低',
}


def list_pending():
    """列出所有待审核特征"""
    if not os.path.isdir(PENDING_DIR):
        print("无待审核特征。")
        return

    features = sorted(os.listdir(PENDING_DIR))
    if not features:
        print("无待审核特征。")
        return

    print(f"\n{'特征名':<40} {'Net Sharpe':<12} {'Mono':<8} {'Status'}")
    print("-" * 80)

    for feat in features:
        feat_dir = os.path.join(PENDING_DIR, feat)
        if not os.path.isdir(feat_dir):
            continue

        report_path = os.path.join(feat_dir, 'report.md')
        net_sharpe = '?'
        mono = '?'
        status = '?'

        if os.path.exists(report_path):
            with open(report_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('net_sharpe:'):
                        net_sharpe = line.split(':', 1)[1].strip()
                    elif line.startswith('mono_score:'):
                        mono = line.split(':', 1)[1].strip()
                    elif line.startswith('status:'):
                        status = line.split(':', 1)[1].strip()

        print(f"  {feat:<38} {net_sharpe:<12} {mono:<8} {status}")

    print(f"\n共 {len(features)} 个待审核。")


def show_feature(feat_name: str):
    """查看特征详情"""
    feat_dir = os.path.join(PENDING_DIR, feat_name)
    if not os.path.isdir(feat_dir):
        print(f"未找到: {feat_name}")
        return

    report_path = os.path.join(feat_dir, 'report.md')
    if os.path.exists(report_path):
        with open(report_path, 'r', encoding='utf-8') as f:
            print(f.read())
    else:
        print(f"无报告文件: {report_path}")
        print(f"\n目录内容:")
        for f in os.listdir(feat_dir):
            print(f"  {f}")


def approve_features(feat_names: list):
    """批量通过特征"""
    os.makedirs(WAITING_DIR, exist_ok=True)
    os.makedirs(FEEDBACK_DIR, exist_ok=True)

    approved = []
    for feat in feat_names:
        src = os.path.join(PENDING_DIR, feat)
        if not os.path.isdir(src):
            print(f"跳过（未找到）: {feat}")
            continue

        dst = os.path.join(WAITING_DIR, feat)
        shutil.move(src, dst)

        # 写 APPROVED feedback
        date_str = datetime.now().strftime('%Y-%m-%d')
        feedback_path = os.path.join(FEEDBACK_DIR, f"{date_str}_{feat}_APPROVED.md")
        with open(feedback_path, 'w', encoding='utf-8') as f:
            f.write(f"---\nfeature: {feat}\nstatus: APPROVED\ndate: {date_str}\n---\n\n")
            f.write(f"特征 `{feat}` 已通过审批，等待入库。\n")

        approved.append(feat)
        print(f"✅ {feat} → waiting-rawdata/")

    if approved:
        # TG 通知
        msg = f"✅ 已通过审批: {', '.join(approved)}"
        os.system(f'python {TG_SEND} --text "{msg}" 2>/dev/null')

    return approved


def reject_features(feat_names: list, reason: str, note: str = ''):
    """批量拒绝特征"""
    os.makedirs(REJECTED_DIR, exist_ok=True)
    os.makedirs(FEEDBACK_DIR, exist_ok=True)

    if reason not in REJECT_REASONS:
        print(f"无效原因码: {reason}")
        print(f"可用: {', '.join(REJECT_REASONS.keys())}")
        return []

    rejected = []
    for feat in feat_names:
        src = os.path.join(PENDING_DIR, feat)
        if not os.path.isdir(src):
            print(f"跳过（未找到）: {feat}")
            continue

        dst = os.path.join(REJECTED_DIR, feat)
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.move(src, dst)

        # 写 REJECTED feedback
        date_str = datetime.now().strftime('%Y-%m-%d')
        feedback_path = os.path.join(FEEDBACK_DIR, f"{date_str}_{feat}_REJECTED.md")
        with open(feedback_path, 'w', encoding='utf-8') as f:
            f.write(f"---\nfeature: {feat}\nstatus: REJECTED\nreason: {reason}\ndate: {date_str}\n---\n\n")
            f.write(f"## 拒绝原因\n\n")
            f.write(f"- **原因码**: {reason} — {REJECT_REASONS[reason]}\n")
            if note:
                f.write(f"- **说明**: {note}\n")
            f.write(f"\n研究员应在下个 cycle 读取此 feedback 并调整方向。\n")

        rejected.append(feat)
        print(f"❌ {feat} → rejected-rawdata/ (reason: {reason})")

    if rejected:
        msg = f"❌ 已拒绝: {', '.join(rejected)} | 原因: {reason}"
        os.system(f'python {TG_SEND} --text "{msg}" 2>/dev/null')

    # 如果是 DIRECTION_EXHAUSTED，标记方向池
    if reason == 'DIRECTION_EXHAUSTED':
        print("\n⚠️ 建议手动更新方向池中对应方向的 status 为 exhausted")

    return rejected


def main():
    parser = argparse.ArgumentParser(description='Approve/Reject pending rawdata features')
    parser.add_argument('features', nargs='*', help='特征名列表')
    parser.add_argument('--list', action='store_true', help='列出待审核特征')
    parser.add_argument('--show', metavar='FEAT', help='查看特征详情')
    parser.add_argument('--reject', action='store_true', help='拒绝模式')
    parser.add_argument('--reason', default='WEAK_SIGNAL',
                        choices=REJECT_REASONS.keys(), help='拒绝原因码')
    parser.add_argument('--note', default='', help='附加说明')

    args = parser.parse_args()

    if args.list:
        list_pending()
        return

    if args.show:
        show_feature(args.show)
        return

    if not args.features:
        parser.print_help()
        return

    if args.reject:
        reject_features(args.features, args.reason, args.note)
    else:
        approve_features(args.features)


if __name__ == '__main__':
    main()
