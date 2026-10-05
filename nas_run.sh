#!/bin/bash
# 在 DXP4800 上执行命令；凭证从 overview.json 读取，不写死在脚本里。
# 用法: ./nas_run.sh 'ls /volume1/Video'
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

exec sshpass -p "$NAS_PASS" ssh -o StrictHostKeyChecking=no -o LogLevel=ERROR -p "$NAS_PORT" "$NAS_USER@$NAS_IP" "$@"
