SCRIPT_PATH="test2.py"
INTERVAL_MINUTES=22
LOG_FILE="scheduler.log"

log() {
	echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

if [ ! -f "$SCRIPT_PATH" ]; then
	log "❌ 错误: 脚本文件 $SCRIPT_PATH 不存在"
	exit 1
fi

log "🕒 开始定时执行: $SCRIPT_PATH"
log "⏰ 执行间隔: $INTERVAL_MINUTES 分钟"

while true; do
	START_TIME=$(date +%s)
	log "🚀 开始执行脚本..."

	python3 "$SCRIPT_PATH" 2>&1 | tee -a "$LOG_FILE"
	EXIT_CODE=${PIPESTATUS[0]}

	END_TIME=$(date +%s)
	DURATION=$((END_TIME - START_TIME))
                                                     
	if [ $EXIT_CODE -eq 0 ]; then
		log "✅ 执行成功 (耗时: ${DURATION}秒)"
	else
		log "❌ 执行失败，退出码: $EXIT_CODE (耗时: ${DURATION}秒)"
	fi

	log "⏳ 等待 $INTERVAL_MINUTES 分钟..."
	sleep $((INTERVAL_MINUTES * 60))
done
