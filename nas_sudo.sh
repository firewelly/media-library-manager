#!/bin/bash
# 在 DXP4800 上以 sudo 执行命令。
# 密码经 ssh 的 stdin 传给远端 sudo -S，不出现在命令行/进程表里。
# 用法: ./nas_sudo.sh 'umount /mnt/@usb/sde2'
CONF="$HOME/Library/CloudStorage/OneDrive-Personal/bioinfo/MacMgt/config/nas/dxp4800/overview.json"
if [ ! -f "$CONF" ]; then echo "未找到凭证配置: $CONF" >&2; exit 1; fi

CRED=$(python3 - "$CONF" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding='utf-8'))
u = d['ssh']['users'][0]
print(u['username'], u['password'], d['ip'], d.get('ssh', {}).get('port', 22), sep='\t')
PY
)
IFS=$'\t' read -r NAS_USER NAS_PASS NAS_IP NAS_PORT <<< "$CRED"

printf '%s\n' "$NAS_PASS" | sshpass -p "$NAS_PASS" ssh -o StrictHostKeyChecking=no -o LogLevel=ERROR -p "$NAS_PORT" \
    "$NAS_USER@$NAS_IP" "sudo -S -p '' $*"
