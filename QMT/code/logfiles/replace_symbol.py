import os
import glob

def get_latest_txt_file(directory):
    """获取当前目录下最新的txt文件"""
    txt_files = glob.glob(os.path.join(directory, '*.log'))
    if not txt_files:
        return None
    return max(txt_files, key=os.path.getmtime)

def read_file_content(file_path):
    """读取文件内容，自动检测编码"""
    encodings = ['utf-8', 'gbk', 'gb2312']
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read(), encoding
        except UnicodeDecodeError:
            continue
    return None, None

def write_file_content(file_path, content, encoding):
    """写入文件内容"""
    with open(file_path, 'w', encoding=encoding) as f:
        f.write(content)

def replace_symbols(content, replace_map):
    """
    替换文件中的符号
    replace_map: 字典，{旧字符: 新字符}
    返回替换后的内容和替换统计
    """
    result = content
    stats = {}
    for old_char, new_char in replace_map.items():
        count = content.count(old_char)
        if count > 0:
            result = result.replace(old_char, new_char)
            stats[old_char] = count
    return result, stats

def process_file(file_path, replace_map):
    """处理文件：读取 -> 替换 -> 写回"""
    content, encoding = read_file_content(file_path)
    if content is None:
        print(f"replace_symbol.py: 无法读取文件: {file_path}")
        return
    
    new_content, stats = replace_symbols(content, replace_map)
    
    if not stats:
        #print("文件中没有需要替换的字符")
        return
    
    write_file_content(file_path, new_content, encoding)
    
    for old_char, count in stats.items():
        new_char = replace_map[old_char]
        #print(f"✅ 替换了 {count} 个 '{old_char}' → '{new_char}'")

# 执行
def process_replace(directory='.'):
    latest = get_latest_txt_file(directory)
    if latest:
        #print(f"处理文件: {latest}")
        # 在这里添加需要替换的符号对
        replace_map = {
            '√': '✅',
            '○': '⚪',
            '×': '❌'
        }
        process_file(latest, replace_map)
    else:
        print("replace_symbol.py: 未找到log文件")

if __name__ == "__main__":
    process_replace()