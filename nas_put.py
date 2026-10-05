#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把本地文件上传到 DXP4800：python3 nas_put.py <本地路径> <远端路径>"""
import json
import subprocess
import sys

CONF = '/Users/firewell/Library/CloudStorage/OneDrive-Personal/bioinfo/MacMgt/config/nas/dxp4800/overview.json'


def main():
    local, remote = sys.argv[1], sys.argv[2]
    d = json.load(open(CONF, encoding='utf-8'))
    u = d['ssh']['users'][0]
    cmd = ['sshpass', '-p', u['password'], 'ssh', '-o', 'StrictHostKeyChecking=no',
           '-o', 'LogLevel=ERROR', f"{u['username']}@{d['ip']}", f'cat > {remote}']
    with open(local, 'rb') as f:
        r = subprocess.run(cmd, stdin=f)
    sys.exit(r.returncode)


if __name__ == '__main__':
    main()
