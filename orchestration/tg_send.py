#!/usr/bin/env python3
"""
Telegram 消息/文件发送工具 — A-Share RawData Multi-Agent 系统的通知组件

Usage:
    python orchestration/tg_send.py --text "研究员完成了一个周期"
    python orchestration/tg_send.py --file report.md --caption "初筛报告"
    python orchestration/tg_send.py --photo curve.png --caption "PnL curve"
    python orchestration/tg_send.py --summary-file .claude-output/reports/report.md

注意: 从项目根目录运行 (cd /home/gkh/claude_tasks/ashare_rawdata)
"""

import argparse
import json
import os
import subprocess
import sys
import time
import yaml

# === 配置加载 ===

def load_config():
    """从 orchestration/config.yaml 加载 TG 配置"""
    config_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.yaml'),
        os.path.join(os.getcwd(), 'orchestration', 'config.yaml'),
    ]
    for path in config_paths:
        if os.path.exists(path):
            with open(path, 'r') as f:
                config = yaml.safe_load(f)
            return config['telegram']
    raise FileNotFoundError(
        f"找不到 config.yaml，尝试过的路径: {config_paths}"
    )


# === TG API: 本地优先，SSH relay 兜底 ===

TG_MSG_LIMIT = 4096
SSH_RELAY = "aws-proxy"


def _tg_api_call(bot_token: str, method: str, data: dict = None,
                 files: dict = None) -> dict:
    """调用 Telegram Bot API。先尝试本地 curl，失败后回退 SSH relay。"""
    if files:
        return _tg_api_call_with_file(bot_token, method, data or {}, files)

    url = f"https://api.telegram.org/bot{bot_token}/{method}"
    json_str = json.dumps(data or {}, ensure_ascii=False)

    # --- 尝试 1: 本地直连 ---
    result = _call_local(url, json_str)
    if result.get('ok'):
        return result

    local_err = result.get('description', 'unknown')
    print(f"  [local] failed: {local_err}, trying SSH relay...", file=sys.stderr)

    # --- 尝试 2: SSH relay 兜底 ---
    return _call_ssh(url, json_str)


def _call_local(url: str, json_str: str) -> dict:
    """本地 curl 直连 Telegram API。"""
    cmd = [
        'curl', '-s', '--max-time', '15',
        '-H', 'Content-Type: application/json',
        '-d', json_str,
        url,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if result.returncode != 0:
            return {'ok': False, 'description': f'local curl error (rc={result.returncode}): {result.stderr.strip()}'}
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {'ok': False, 'description': 'local curl timeout'}
    except json.JSONDecodeError:
        return {'ok': False, 'description': f'local invalid JSON: {result.stdout[:200]}'}


def _call_ssh(url: str, json_str: str) -> dict:
    """通过 SSH relay 调用 Telegram API。"""
    remote_cmd = (
        f"curl -s --max-time 30 "
        f"-H 'Content-Type: application/json' "
        f"-d '{json_str}' "
        f"'{url}'"
    )
    cmd = ['ssh', '-o', 'ConnectTimeout=10', SSH_RELAY, remote_cmd]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            print(f"  [ssh] error: {result.stderr.strip()}", file=sys.stderr)
            return {'ok': False, 'description': f'SSH error: {result.stderr.strip()}'}
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {'ok': False, 'description': 'SSH relay timeout'}
    except json.JSONDecodeError:
        return {'ok': False, 'description': f'SSH invalid JSON: {result.stdout[:200]}'}


def _tg_api_call_with_file(bot_token: str, method: str, data: dict,
                           files: dict) -> dict:
    """发送文件到 Telegram。先尝试本地，失败后回退 SSH relay。"""
    url = f"https://api.telegram.org/bot{bot_token}/{method}"

    result = _call_local_with_file(url, data, files)
    if result.get('ok'):
        return result

    local_err = result.get('description', 'unknown')
    print(f"  [local file] failed: {local_err}, trying SSH relay...", file=sys.stderr)

    return _call_ssh_with_file(url, data, files)


def _call_local_with_file(url: str, data: dict, files: dict) -> dict:
    """本地 curl 直连发送文件。"""
    curl_parts = ['curl', '-s', '--max-time', '60']
    for key, value in data.items():
        curl_parts.extend(['-F', f'{key}={value}'])
    for field_name, (filename, filepath) in files.items():
        curl_parts.extend(['-F', f'{field_name}=@{filepath};filename={filename}'])
    curl_parts.append(url)

    try:
        result = subprocess.run(curl_parts, capture_output=True, text=True, timeout=90)
        if result.returncode != 0:
            return {'ok': False, 'description': f'local curl file error (rc={result.returncode}): {result.stderr.strip()}'}
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {'ok': False, 'description': 'local curl file timeout'}
    except json.JSONDecodeError:
        return {'ok': False, 'description': f'local file invalid JSON: {result.stdout[:200]}'}


def _call_ssh_with_file(url: str, data: dict, files: dict) -> dict:
    """通过 SSH relay 发送文件到 Telegram。"""
    remote_files = {}
    try:
        for field_name, (filename, filepath) in files.items():
            remote_path = f"/tmp/tg_upload_{os.getpid()}_{filename}"
            scp_cmd = ['scp', '-o', 'ConnectTimeout=10', filepath,
                       f'{SSH_RELAY}:{remote_path}']
            result = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                return {'ok': False, 'description': f'SCP error: {result.stderr.strip()}'}
            remote_files[field_name] = (filename, remote_path)

        curl_parts = ['curl', '-s', '--max-time', '60']
        for key, value in data.items():
            curl_parts.extend(['-F', f'{key}={value}'])
        for field_name, (filename, remote_path) in remote_files.items():
            curl_parts.extend(['-F', f'{field_name}=@{remote_path};filename={filename}'])
        curl_parts.append(url)

        curl_cmd_str = ' '.join(f"'{p}'" if ' ' in p or '=' in p or '@' in p or ';' in p else p
                                for p in curl_parts)
        ssh_cmd = ['ssh', '-o', 'ConnectTimeout=10', SSH_RELAY, curl_cmd_str]

        result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            return {'ok': False, 'description': f'SSH curl error: {result.stderr.strip()}'}
        return json.loads(result.stdout)

    except subprocess.TimeoutExpired:
        return {'ok': False, 'description': 'SSH relay timeout (file upload)'}
    except json.JSONDecodeError:
        return {'ok': False, 'description': f'SSH invalid JSON: {result.stdout[:200]}'}
    finally:
        for field_name, (filename, remote_path) in remote_files.items():
            try:
                subprocess.run(
                    ['ssh', SSH_RELAY, f'rm -f {remote_path}'],
                    capture_output=True, timeout=10
                )
            except Exception:
                pass


# === TG 高层接口 ===

def send_text(bot_token, chat_id, text, message_thread_id=None):
    results = []
    chunks = _split_text(text, TG_MSG_LIMIT)
    for i, chunk in enumerate(chunks):
        payload = {'chat_id': chat_id, 'text': chunk, 'parse_mode': 'Markdown'}
        if message_thread_id is not None:
            payload['message_thread_id'] = message_thread_id
        result = _tg_api_call(bot_token, 'sendMessage', payload)
        if result.get('ok'):
            msg_id = result['result']['message_id']
            print(f"  [text {i+1}/{len(chunks)}] sent (msg_id={msg_id})")
            results.append(result)
        else:
            payload2 = {'chat_id': chat_id, 'text': chunk}
            if message_thread_id is not None:
                payload2['message_thread_id'] = message_thread_id
            result2 = _tg_api_call(bot_token, 'sendMessage', payload2)
            if result2.get('ok'):
                msg_id = result2['result']['message_id']
                print(f"  [text {i+1}/{len(chunks)}] sent plain (msg_id={msg_id})")
                results.append(result2)
            else:
                desc = result2.get('description', 'unknown')
                print(f"  [text {i+1}/{len(chunks)}] FAILED: {desc}", file=sys.stderr)
        if i < len(chunks) - 1:
            time.sleep(0.5)
    return results


def send_document(bot_token, chat_id, filepath, caption='', message_thread_id=None):
    filename = os.path.basename(filepath)
    if len(caption) > 1024:
        caption = caption[:1020] + '...'
    data = {'chat_id': str(chat_id), 'caption': caption}
    if message_thread_id is not None:
        data['message_thread_id'] = str(message_thread_id)
    result = _tg_api_call(bot_token, 'sendDocument',
                          data=data, files={'document': (filename, filepath)})
    if result.get('ok'):
        print(f"  [file] {filename} sent (msg_id={result['result']['message_id']})")
    else:
        print(f"  [file] {filename} FAILED: {result.get('description', 'unknown')}", file=sys.stderr)
    return result


def send_photo(bot_token, chat_id, filepath, caption='', message_thread_id=None):
    if len(caption) > 1024:
        caption = caption[:1020] + '...'
    filename = os.path.basename(filepath)
    data = {'chat_id': str(chat_id), 'caption': caption}
    if message_thread_id is not None:
        data['message_thread_id'] = str(message_thread_id)
    result = _tg_api_call(bot_token, 'sendPhoto',
                          data=data, files={'photo': (filename, filepath)})
    if result.get('ok'):
        print(f"  [photo] sent (msg_id={result['result']['message_id']})")
    else:
        print(f"  [photo] FAILED: {result.get('description', 'unknown')}", file=sys.stderr)
    return result


def send_summary_file(bot_token, chat_id, filepath, message_thread_id=None):
    results = []
    with open(filepath, 'r') as f:
        content = f.read()
    summary = _extract_report_summary(content, filepath)
    results.extend(send_text(bot_token, chat_id, summary, message_thread_id))
    time.sleep(0.5)
    result = send_document(bot_token, chat_id, filepath, caption="详细报告",
                           message_thread_id=message_thread_id)
    results.append(result)
    return results


# === 辅助函数 ===

def _split_text(text, limit):
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split_pos = text.rfind('\n', 0, limit)
        if split_pos == -1:
            split_pos = limit
        chunks.append(text[:split_pos])
        text = text[split_pos:].lstrip('\n')
    return chunks


def _extract_report_summary(content, filepath):
    import re
    filename = os.path.basename(filepath)

    frontmatter = {}
    if content.startswith('---'):
        end_idx = content.find('---', 3)
        if end_idx != -1:
            try:
                frontmatter = yaml.safe_load(content[3:end_idx]) or {}
            except yaml.YAMLError:
                pass

    if frontmatter:
        direction = frontmatter.get('direction', '—')
        agent = frontmatter.get('agent_id') or frontmatter.get('agent', '—')
        status = frontmatter.get('status', '—')
        feature = frontmatter.get('feature_name', '—')
        avg_sharpe = frontmatter.get('net_sharpe', frontmatter.get('avg_net_sharpe', '—'))
        mono = frontmatter.get('mono_score', '—')

        emoji = {
            'screening_passed': '✅',
            'screening_failed': '❌',
            'screening_borderline': '⚠️',
        }.get(status, '📋')

        lines = [f"{emoji} A股RawData初筛报告: {filename}"]
        lines.append(f"方向: {direction}")
        lines.append(f"Agent: {agent} | 状态: {status}")
        if feature != '—':
            lines.append(f"特征: {feature}")
        if avg_sharpe != '—':
            lines.append(f"Net Sharpe: {avg_sharpe}")
        if mono != '—':
            lines.append(f"Mono: {mono}")
        lines.append("")
        lines.append("详细报告见附件")

        summary = '\n'.join(lines)
    else:
        lines = content.strip().split('\n')[:10]
        summary = f"📋 新报告: {filename}\n\n" + '\n'.join(lines) + "\n\n详细报告见附件"

    return summary


# === CLI 入口 ===

def main():
    parser = argparse.ArgumentParser(description='TG 消息/文件发送工具')
    parser.add_argument('--text', type=str, help='发送文本消息')
    parser.add_argument('--file', type=str, help='发送文件附件')
    parser.add_argument('--photo', type=str, help='发送图片')
    parser.add_argument('--caption', type=str, default='', help='文件/图片的标题')
    parser.add_argument('--summary-file', type=str, help='发送报告摘要 + 完整文件')
    parser.add_argument('--bot-token', type=str, help='覆盖 config 中的 bot token')
    parser.add_argument('--chat-id', type=int, help='覆盖 config 中的 chat id')
    parser.add_argument('--thread-id', type=int, help='覆盖 config 中的 message_thread_id')

    args = parser.parse_args()

    if not any([args.text, args.file, args.photo, args.summary_file]):
        parser.error('至少指定一个: --text, --file, --photo, --summary-file')

    tg_config = load_config()
    bot_token = args.bot_token or tg_config['bot_token']
    chat_id = args.chat_id or tg_config['chat_id']
    thread_id = args.thread_id or tg_config.get('message_thread_id')

    all_ok = True

    if args.text:
        results = send_text(bot_token, chat_id, args.text, thread_id)
        if not all(r.get('ok') for r in results):
            all_ok = False

    if args.file:
        if not os.path.exists(args.file):
            print(f"ERROR: 文件不存在: {args.file}", file=sys.stderr)
            sys.exit(1)
        result = send_document(bot_token, chat_id, args.file, args.caption, thread_id)
        if not result.get('ok'):
            all_ok = False

    if args.photo:
        if not os.path.exists(args.photo):
            print(f"ERROR: 图片不存在: {args.photo}", file=sys.stderr)
            sys.exit(1)
        result = send_photo(bot_token, chat_id, args.photo, args.caption, thread_id)
        if not result.get('ok'):
            all_ok = False

    if args.summary_file:
        if not os.path.exists(args.summary_file):
            print(f"ERROR: 报告文件不存在: {args.summary_file}", file=sys.stderr)
            sys.exit(1)
        results = send_summary_file(bot_token, chat_id, args.summary_file, thread_id)
        if not all(r.get('ok') for r in results if isinstance(r, dict)):
            all_ok = False

    sys.exit(0 if all_ok else 1)


if __name__ == '__main__':
    main()
