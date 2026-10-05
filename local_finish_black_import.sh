#!/bin/bash
# 本机守望：等 DXP4800 上的搬运流水线结束，取回账本与探测结果，自动入库；
# 入库成功后再删除 U 盘上的源文件（只删目标存在且大小一致的）。
# 用 nohup 启动，日志见 black_import_watch.log。
cd /Users/firewell/bin/media || exit 1
LOG=black_import_watch.log

log() { echo "$(date '+%F %T') $*" >> "$LOG"; }

log "守望启动，等待 NAS 侧完成标记"
while true; do
    if ./nas_run.sh 'test -f /tmp/usb_pipeline.done' > /dev/null 2>&1; then
        log "检测到 NAS 流水线完成"
        break
    fi
    sleep 300
done

log "取回账本与探测结果"
python3 nas_get.py /tmp/usb_copy_ok.tsv usb_copy_ok.tsv >> "$LOG" 2>&1 || log "取回账本失败"
python3 nas_get.py /tmp/probe_result.tsv probe_result.tsv >> "$LOG" 2>&1 || log "取回探测结果失败"
log "账本 $(wc -l < usb_copy_ok.tsv 2>/dev/null) 行，探测 $(wc -l < probe_result.tsv 2>/dev/null) 行"

log "开始入库"
python3 db_import_usb_videos.py --ok-ledger usb_copy_ok.tsv --probe probe_result.tsv --apply >> "$LOG" 2>&1
rc=$?
log "入库结束，退出码 $rc"

if [ "$rc" -eq 0 ]; then
    log "开始删除 U 盘源文件（目标存在且大小一致才删）"
    ./nas_run.sh 'cd /tmp && python3 nas_move_usb_videos.py delete' >> "$LOG" 2>&1
    log "删源结束，U 盘剩余视频: $(./nas_run.sh 'find /mnt/@usb/sde2/JAV -type f \( -iname "*.mp4" -o -iname "*.mkv" \) | wc -l' 2>/dev/null)"
else
    log "入库未成功，跳过删源（源文件保留）"
fi
log "全部流程结束"
