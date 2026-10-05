#!/bin/bash
# 在 DXP4800 上：等 copy 结束 -> 探测时长/分辨率 -> 落完成标记
# 按用户要求：不做 MD5 校验（verify 步骤已去掉），也不删 U 盘源文件。
# 若之后想补校验：python3 /tmp/nas_move_usb_videos.py verify --workers 4
cd /tmp
rm -f /tmp/usb_pipeline.done
while pgrep -f "nas_move_usb_videos.py copy" > /dev/null; do
    sleep 120
done
echo "[watch] copy 结束 $(date '+%H:%M:%S')"

# 不做校验，直接把拷贝账本当作可用清单（含 源/目标/大小/预算MD5）
cp /tmp/usb_copy_ledger.tsv /tmp/usb_copy_ok.tsv
echo "[watch] 已生成可用清单（未校验）: $(wc -l < /tmp/usb_copy_ok.tsv) 条"

cut -f2 /tmp/usb_copy_ok.tsv > /tmp/probe_list.txt
echo "[watch] 待探测 $(wc -l < /tmp/probe_list.txt) 个"
python3 nas_probe_videos.py
echo "[watch] 探测结束 $(date '+%H:%M:%S')"

echo "[watch] 未删源；源文件保留在 U 盘"
touch /tmp/usb_pipeline.done
echo "[watch] 全部结束 $(date '+%H:%M:%S')"
