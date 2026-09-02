#encoding:gbk
'''
重定向输出log目录
'''
import sys
import glob

class Tee:
	"""将输出同时写入终端和日志文件"""
	def __init__(self, log_file_path):
		#self.terminal = sys.__stdout__      # 保留原始控制台输出流
		self.log = open(log_file_path, 'a', encoding='utf-8')  # 追加模式

	def write(self, message):
		#self.terminal.write(message)                  # 打印到控制台
		self.log.write(message)                 # 写入日志文件
		self.log.flush()                        # 实时写入磁盘

	def flush(self):
		try:
			#self.terminal.flush()
			self.log.flush()
		except ValueError:
			pass

	def close(self):
		self.log.close()

def get_log_path():
	"""检查多个可能的logfiles路径，返回第一个存在的"""
	candidates = [
		'D:\\stock\\test_stock\\socket\\QMT\\code\\logfiles',
		'C:\\Users\\Administrator\\Desktop\\socket\\QMT\\code\\logfiles',
		'C:\\socket\\QMT\\code\\logfiles'
	]
	for p in candidates:
		if os.path.exists(p):
			#print(f'logfiles路径: {p}')
			return p
	#print('未找到logfiles路径，使用默认路径')
	return candidates[0]

def get_latest_txt_file(directory):
	"""获取当前目录下最新的txt文件"""
	txt_files = glob.glob(os.path.join(directory, '*.log'))
	if not txt_files:
		return None
	return max(txt_files, key=os.path.getmtime)

log_path = get_log_path()
log_name = get_latest_txt_file(log_path)
tee = Tee(f"{log_name}")
sys.stdout = tee