# -*- coding: utf-8 -*-
"""
统一密钥读取（项目内不保存任何明文密钥）
==========================================

密钥集中存放在 OneDrive 的 MacMgt 配置目录，本模块只负责**读取**：
    <配置目录>/media-library.env      # 本项目专用
    <配置目录>/skills-api-keys.env    # 各 skill 共用的密钥

配置目录解析顺序:
    1. 环境变量 ``MACMGT_CONFIG_DIR``
    2. ~/Library/CloudStorage/OneDrive-个人/bioinfo/MacMgt/config
    3. ~/Library/CloudStorage/OneDrive-Personal/bioinfo/MacMgt/config
    4. ~/OneDrive/bioinfo/MacMgt/config

用法:
    from utils.secrets import load_keys, get_key
    load_keys()                       # 注入 os.environ（不覆盖已有环境变量）
    key = get_key("BAIDU_API_KEY")    # 取单个密钥
"""

import os
import glob

_ENV_FILES = ("media-library.env", "skills-api-keys.env")
_CANDIDATE_DIRS = (
    os.path.expanduser("~/Library/CloudStorage/OneDrive-个人/bioinfo/MacMgt/config"),
    os.path.expanduser("~/Library/CloudStorage/OneDrive-Personal/bioinfo/MacMgt/config"),
    os.path.expanduser("~/OneDrive/bioinfo/MacMgt/config"),
)

_loaded = False


def config_dir():
    """返回密钥配置目录（不存在返回 None）"""
    env_dir = os.getenv("MACMGT_CONFIG_DIR")
    if env_dir and os.path.isdir(env_dir):
        return env_dir
    for d in _CANDIDATE_DIRS:
        if os.path.isdir(d):
            return d
    # 兜底：通配 OneDrive-* 目录
    for d in glob.glob(os.path.expanduser(
            "~/Library/CloudStorage/OneDrive-*/bioinfo/MacMgt/config")):
        return d
    return None


def _parse_env_file(path):
    pairs = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                pairs[k.strip()] = v.strip().strip("'\"")
    except Exception:
        pass
    return pairs


def load_keys(verbose=False):
    """把配置目录中的密钥注入 os.environ（不覆盖已存在的环境变量）。

    返回成功加载的密钥名列表（不含值）。
    """
    global _loaded
    d = config_dir()
    if not d:
        if verbose:
            print("[secrets] 未找到 MacMgt 配置目录，跳过密钥加载")
        return []
    loaded = []
    for fname in _ENV_FILES:
        path = os.path.join(d, fname)
        if not os.path.isfile(path):
            continue
        for k, v in _parse_env_file(path).items():
            if v and not os.getenv(k):
                os.environ[k] = v
                loaded.append(k)
    _loaded = True
    if verbose:
        print(f"[secrets] 已从 {d} 加载: {', '.join(sorted(loaded)) or '（无新增）'}")
    return loaded


def get_key(name, default=None):
    """读取单个密钥：环境变量优先，其次 OneDrive 配置文件"""
    val = os.getenv(name)
    if val:
        return val
    if not _loaded:
        load_keys()
    return os.getenv(name, default)
