#!/bin/bash
# 等 ISO 批次结束 → rmvb → wmv 单文件 → wmv 合并组（全部无人值守）
cd /tmp
while pgrep -f "nas_transcode_iso.py" > /dev/null; do sleep 120; done
echo "[chain] ISO 批次结束 $(date '+%H:%M:%S')"

echo "[chain] 开始 rmvb $(date '+%H:%M:%S')"
python3 /tmp/nas_transcode.py /tmp/rmvb_list.txt --apply --workers 2

echo "[chain] 开始 wmv 单文件 $(date '+%H:%M:%S')"
python3 /tmp/nas_transcode.py /tmp/wmv_singles.txt --apply --workers 2

echo "[chain] 开始 wmv 合并组 $(date '+%H:%M:%S')"
python3 /tmp/nas_transcode_merge.py --apply --workers 1

echo "[chain] 全部结束 $(date '+%H:%M:%S')"
touch /tmp/transcode_chain.done
