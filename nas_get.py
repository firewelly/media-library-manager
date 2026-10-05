#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 DXP4800 取回文件：python3 nas_get.py <远端路径> <本地路径>"""
import json
import subprocess
import sys

CONF = '/Users/firewell/Library/CloudStorage/OneDrive-Personal/bioinfo/MacMgt/config/nas/dxp4800/overview.json'


def main():
    remote, local = sys.argv[1], sys.argv[2]
    d = json.load(open(CONF, encoding='utf-8'))
    u = d['ssh']['users'][0]
    cmd = ['sshpass', '-p', u['password'], 'ssh', '-o', 'StrictHostKeyChecking=no',
           '-o', 'LogLevel=ERROR', f"{u['username']}@{d['ip']}", f'cat {remote}']
    with open(local, 'wb') as f:
        r = subprocess.run(cmd, stdout=f)
    sys.exit(r.returncode)


if __name__ == '__main__':
    main()
