#!/bin/bash
# 在NAS上计算md5的脚本
# 用法: bash md5_calc_nas.sh <tasks_file> <results_file>
# 支持断点续传、容错（单文件失败不影响整体）

# 注意：不使用 set -e，确保单个文件失败不会中断整个任务

TASKS_FILE="$1"
RESULTS_FILE="$2"
PROGRESS_FILE="${RESULTS_FILE}.progress"
FAIL_LOG="${RESULTS_FILE}.fail_log"

if [ -z "$TASKS_FILE" ] || [ -z "$RESULTS_FILE" ]; then
    echo "用法: $0 <tasks_file> <results_file>"
    echo "  tasks_file: 格式为 id,file_path"
    echo "  results_file: 输出格式为 id,md5"
    exit 1
fi

if [ ! -f "$TASKS_FILE" ]; then
    echo "任务文件不存在: $TASKS_FILE"
    exit 1
fi

# 路径映射函数 (macOS SMB挂载路径 -> NAS本地路径)
# 已验证的正确映射（2026-07-16 确认）：
#   /Volumes/国产_DX4600/ -> /volume4/国产_DX4600/
#   /Volumes/app/usr/     -> /volume1/app/usr/
#   /Volumes/HC530_1/     -> /volume2/HC530_1/
#   /Volumes/Jav_HDD4/    -> /volume4/Jav_HDD4/
convert_path() {
    local mac_path="$1"
    echo "$mac_path" | sed -E '
        s|^/Volumes/国产_DX4600/|/volume4/国产_DX4600/|
        s|^/Volumes/app/usr/|/volume1/app/usr/|
        s|^/Volumes/HC530_1/|/volume2/HC530_1/|
        s|^/Volumes/Jav_HDD4/|/volume4/Jav_HDD4/|
    '
}

# 加载已处理的ID（断点续传）
declare -A processed
if [ -f "$PROGRESS_FILE" ]; then
    while IFS=, read -r id md5; do
        processed[$id]=1
    done < "$PROGRESS_FILE"
fi

total=$(wc -l < "$TASKS_FILE" | tr -d ' ')
processed_count=${#processed[@]}
remaining=$((total - processed_count))

echo "========================================"
echo "MD5 计算任务启动"
echo "========================================"
echo "总任务: $total"
echo "已处理: $processed_count"
echo "待处理: $remaining"
echo "结果文件: $RESULTS_FILE"
echo "进度文件: $PROGRESS_FILE"
echo "失败日志: $FAIL_LOG"
echo "========================================"
echo ""

# 统计计数器
count=0
success=0
not_found=0
errors=0
start_time=$(date +%s)

# 处理任务
while IFS=, read -r id file_path; do
    count=$((count + 1))

    # 去掉末尾换行符/回车符
    file_path="${file_path%$'\n'}"
    file_path="${file_path%$'\r'}"

    # 跳过已处理的
    if [ -n "${processed[$id]}" ]; then
        continue
    fi

    # 转换路径
    nas_path=$(convert_path "$file_path")

    # 检查文件是否存在
    if [ ! -f "$nas_path" ]; then
        not_found=$((not_found + 1))
        echo "$id," >> "$RESULTS_FILE"
        echo "$id," >> "$PROGRESS_FILE"
        echo "[$count/$total] 文件不存在: $nas_path" >> "$FAIL_LOG"
        # 每200条或最后一条打印进度
        if [ $((count % 200)) -eq 0 ] || [ $count -eq $total ]; then
            elapsed=$(( $(date +%s) - start_time ))
            echo "[$count/$total] 进度: $((count * 100 / total))% | 成功:$success 未找到:$not_found 错误:$errors | 耗时:${elapsed}s"
        fi
        continue
    fi

    # 计算md5，设置超时（单个文件最多2小时，防止卡死）
    # timeout 命令在大多数 Linux 上可用，超时后返回124
    timeout 7200 md5sum "$nas_path" > /tmp/md5_tmp_$$ 2>/tmp/md5_err_$$
    exit_code=$?

    if [ $exit_code -eq 0 ]; then
        md5=$(cut -d' ' -f1 < /tmp/md5_tmp_$$)
        echo "$id,$md5" >> "$RESULTS_FILE"
        echo "$id,$md5" >> "$PROGRESS_FILE"
        success=$((success + 1))
    elif [ $exit_code -eq 124 ]; then
        errors=$((errors + 1))
        echo "$id," >> "$RESULTS_FILE"
        echo "$id," >> "$PROGRESS_FILE"
        echo "[$count/$total] 超时(>2h): $nas_path" >> "$FAIL_LOG"
    else
        errors=$((errors + 1))
        echo "$id," >> "$RESULTS_FILE"
        echo "$id," >> "$PROGRESS_FILE"
        err_msg=$(cat /tmp/md5_err_$$)
        echo "[$count/$total] 错误(exit=$exit_code): $nas_path - $err_msg" >> "$FAIL_LOG"
    fi

    rm -f /tmp/md5_tmp_$$ /tmp/md5_err_$$

    # 每200条显示进度
    if [ $((count % 200)) -eq 0 ] || [ $count -eq $total ]; then
        elapsed=$(( $(date +%s) - start_time ))
        speed=$(echo "scale=1; $success / ($elapsed / 60 + 0.01)" 2>/dev/null | bc)
        remain_count=$((total - count))
        eta=$(echo "scale=0; $remain_count / ($speed + 0.01)" 2>/dev/null | bc)
        echo "[$count/$total] 进度: $((count * 100 / total))% | 成功:$success 未找到:$not_found 错误:$errors | 速度:${speed}条/分 | 预计剩余:${eta}分钟"
    fi

done < "$TASKS_FILE"

# 最终统计
end_time=$(date +%s)
total_elapsed=$((end_time - start_time))

echo ""
echo "========================================"
echo "任务完成！"
echo "========================================"
echo "总处理: $count / $total"
echo "成功: $success"
echo "文件不存在: $not_found"
echo "错误: $errors"
echo "总耗时: ${total_elapsed}s ($(( total_elapsed / 3600 ))h $(( (total_elapsed % 3600) / 60 ))m)"
echo "结果保存在: $RESULTS_FILE"
echo "失败详情见: $FAIL_LOG"
echo "========================================"
