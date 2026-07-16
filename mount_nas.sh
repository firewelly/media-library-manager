#!/bin/bash
# 挂载 DXP4800 NAS 的 Video 共享
# 凭证从外部配置读取，不写死在脚本里
# 配置路径：~/Library/CloudStorage/OneDrive-Personal/bioinfo/MacMgt/config/nas/dxp4800/overview.json

CONF="$HOME/Library/CloudStorage/OneDrive-Personal/bioinfo/MacMgt/config/nas/dxp4800/overview.json"

if [ ! -f "$CONF" ]; then
    echo "未找到凭证配置: $CONF"
    exit 1
fi

# 用 python 从 json 取出 smb 用户名/密码/IP
CRED=$(python3 - "$CONF" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding='utf-8'))
user = d['ssh']['users'][0]['username']
pw = d['ssh']['users'][0]['password']
ip = d['ip']
print(f"{user}:{pw}:{ip}")
PY
)
SMB_USER="${CRED%%:*}"
REST="${CRED#*:}"
SMB_PASS="${REST%%:*}"
NAS_IP="${REST##*:}"

mnt="/Volumes/Video"
if [ ! -d "$mnt" ]; then
    sudo mkdir -p "$mnt"
fi

if ! mount | grep -q "$mnt"; then
    echo "挂载 $mnt (//$SMB_USER@$NAS_IP/Video) ..."
    sudo mount_smbfs "//${SMB_USER}:${SMB_PASS}@${NAS_IP}/Video" "$mnt"
    echo "✓ $mnt 已挂载"
else
    echo "✓ $mnt 已挂载"
fi

echo ""
echo "挂载状态:"
mount | grep "/Volumes/Video"
