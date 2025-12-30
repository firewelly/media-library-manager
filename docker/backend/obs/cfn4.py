## Whole Workflow


import os
import re
import hashlib
import send2trash
import cv2
from tkinter import Tk
from tkinter.filedialog import askdirectory

# 重命名文件名称，把路径中的斜线转换成一致的格式,防止send2trash报错
def convert_path(path):
    """
    根据当前操作系统类型转换路径分隔符。
    
    :param path: 输入的路径字符串
    :return: 转换后的路径字符串
    """
    
    if os.name == 'nt':  # Windows
        converted_path = path.replace('/', '\\')
    # macOS, Linux, or other Unix-like systems
    else:
        converted_path = path.replace('\\', '/')
    
    return converted_path


# 重命名可以遍历子文件夹的文件  
# calculate the MD5 value of the file
def get_md5(file_path):
    if not os.path.exists(file_path):
        print(f"警告: 文件不存在 - {file_path}")
        return ""
    md5_hash = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()

# 重命名文件名称，自动加后缀
def rename_file(old_name, new_name):  
    # 检查新文件名是否已经存在  
    if os.path.exists(new_name):  
        # 获取新文件名的后缀  
        extension = os.path.splitext(new_name)[1]  
        # 获取新文件名的前缀  
        prefix = os.path.splitext(new_name)[0]  
        # 遍历数字，直到找到一个不存在的文件名  
        i = 1  
        while os.path.exists(f"{prefix}_{i}{extension}"):  
            i += 1  
        # 重命名文件  
        os.rename(old_name, f"{prefix}_{i}{extension}")  
    else:  
        # 如果新文件名不存在，直接重命名文件  
        os.rename(old_name, new_name)  
        print("文件重命名成功.")  
  

# Sub function - Rename the files
def process_filenames(path):  
    filenames = os.listdir(path) 

    # 匹配"【"和"】"之间的内容 
    pattern = r"(【.*?】)" 
    # 第二轮匹配各种括号情形
    partern2 = r"[\[\【\(\（][^)）].*?[\）\)\】\]]"

    # 第三轮匹配各种括号没有括回而是.
    partern3 = r"[\[\【\(\（][^)）].*?\."

    for root, dirs, filenames in os.walk(path):
        for filename in filenames:
            file_path = os.path.join(root, filename)
            new_filename = filename  

            # 把文件名大写，后缀小写

            # 获取文件名和后缀  
            filename_no_ext, ext = os.path.splitext(filename)  

            # 将文件名转换为大写  
            filename_upper = filename_no_ext.upper()  

            # 将后缀转换为小写  
            ext_lower = ext.lower()  

            # 构建新的文件名  
            new_filename = filename_upper + ext_lower  

            # 去掉空格  
            if " " in filename:
                new_filename = new_filename.replace(" ", "")  
            
            # 去掉"Chinese homemade video"和"_CHINESE_HOMEMADE_VIDEO"  
            if "CHINESEHOMEMADEVIDEO" in new_filename:  
                new_filename = new_filename.replace("CHINESEHOMEMADEVIDEO", "") 
            if "_CHINESE_HOMEMADE_VIDEO" in new_filename:
                new_filename = new_filename.replace("_CHINESE_HOMEMADE_VIDEO", "")
    
            # 去掉“hhd800.com@”
            if "HHD800.COM@" in new_filename:  
                new_filename = new_filename.replace("HHD800.COM@", "")

            # 去掉“WoXav.Com@”
            if "WOXAV.COM@" in new_filename:  
                new_filename = new_filename.replace("WOXAV.COM@", "") 
            
            # 去掉"【"和"】"之间的内容  
            if "【" in new_filename and "】" in new_filename:  
                match = re.search(pattern, new_filename)  
                if match:  
                    new_filename = re.sub(pattern, "", new_filename) 
            
            # 去掉中文括号之间的内容
            
            match = re.search(partern2, new_filename)
            if match:
                new_filename = re.sub(partern2, "", new_filename)
            
            match = re.search(partern3, new_filename)
            if match:
                new_filename = re.sub(partern3, ".", new_filename)

            # 去掉直角单引号之间的内容
            if "「" in new_filename and "」" in new_filename:
                new_filename = re.sub(r"「.*?」", "", new_filename)

            # 去掉直角双引号之间的内容
            if "『" in new_filename and "』" in new_filename:
                new_filename = re.sub(r"『.*?』", "", new_filename)

            new_file_path = os.path.join(root, new_filename)
            
            # 新增：去掉网址名称格式
            url_pattern = r"(?:WWW\.)?[A-Z0-9]+\.(COM|NET|ORG|CN|CC|ME)"
            new_filename = re.sub(url_pattern, "", new_filename)

            # 重命名文件
            # 如果file_path和new_file_path不同，才重命名
            if file_path != new_file_path:
                print(f"重命名文件：{file_path} -> {new_file_path}")
                try:
                    # 重命名文件
                    rename_file(file_path, new_file_path)
                    
                except:
                    print("Error: %s" % new_filename)         

    return filenames  

# Remove the duplicated files
def remove_duplicate_files(directory, num_workers=4):
    global delete_all
    delete_all = False
    cancel_all = False
    all_skip = False  # 新增标志，用于判断是否选择了 na
    skipped_files = []  # 新增列表，用于存储被略过的文件

    files_to_keep = {}
    for root, dirs, files in os.walk(directory):
        for file in files:
            if cancel_all:
                return files_to_keep
            
            file_path = os.path.join(root, file)
            # 检查文件是否存在
            if not os.path.exists(file_path):
                print(f"警告: 文件不存在 - {file_path}")
                continue
            
            file_md5 = get_md5(file_path)
            file_size = os.path.getsize(file_path)
            file_mtime = os.path.getmtime(file_path)  # 获取文件修改时间
            
            if file_md5 in files_to_keep:
                if file_size == files_to_keep[file_md5]['size']:
                    # 定义一个函数来获取文件叹号数量
                    def count_leading_exclamation(file_path):
                        filename = os.path.basename(file_path)
                        count = 0
                        for char in filename:
                            if char == '!':
                                count += 1
                            else:
                                break
                        return count

                    existing_file = files_to_keep[file_md5]['path']
                    existing_exclamation = count_leading_exclamation(existing_file)
                    current_exclamation = count_leading_exclamation(file_path)

                    # 比较叹号数量和文件修改时间
                    if current_exclamation > existing_exclamation:
                        # 当前文件叹号更多，保留当前文件，删除已存在文件
                        file_to_delete = existing_file
                        files_to_keep[file_md5] = {
                            'path': file_path,
                            'name': file,
                            'size': file_size,
                            'mtime': file_mtime
                        }
                    elif current_exclamation < existing_exclamation:
                        # 已存在文件叹号更多，删除当前文件
                        file_to_delete = file_path
                    else:
                        # 叹号数量相同，保留最老的文件
                        existing_mtime = files_to_keep[file_md5]['mtime']
                        if file_mtime < existing_mtime:
                            # 当前文件更老，保留当前文件，删除已存在文件
                            file_to_delete = existing_file
                            files_to_keep[file_md5] = {
                                'path': file_path,
                                'name': file,
                                'size': file_size,
                                'mtime': file_mtime
                            }
                        else:
                            # 已存在文件更老，删除当前文件
                            file_to_delete = file_path

                    print(f"发现重复文件: {file_to_delete}")
                    def get_user_confirmation(prompt):
                        while True:
                            print("请选择操作:")
                            print("Y/y - 删除当前文件")
                            print("N/n - 跳过当前文件")
                            print("A/a - 删除所有后续文件(不再询问)")
                            print("C/c - 取消所有操作")
                            print("Na/na - 跳过所有文件")  # 新增选项
                            choice = input(prompt).lower()
                            if choice in ('y', 'n', 'a', 'c', 'na'):
                                return choice
                            print("错误: 无效输入，请输入 Y/y, N/n, A/a, C/c 或 Na/na")
                    
                    if not delete_all and not all_skip:
                        choice = get_user_confirmation("删除此文件? (y/n/a/c/na): ")
                        if choice == 'a':
                            delete_all = True
                        elif choice == 'c':
                            cancel_all = True
                            continue
                        elif choice == 'na':
                            all_skip = True
                        elif choice != 'y':
                            skipped_files.append(file_to_delete)  # 记录被略过的文件

                    if delete_all or choice == 'y':
                        if os.path.isfile(file_to_delete):
                            try:
                                send2trash.send2trash(file_to_delete)
                                print(f"已将文件移至回收站: {file_to_delete}")
                            except Exception:
                                try:
                                    os.remove(file_to_delete)
                                    print(f"已删除文件: {file_to_delete}")
                                except Exception as e:
                                    print(f"删除文件 {file_to_delete} 时出错: {e}")
                        else:
                            print(f"文件不存在，跳过删除: {file_to_delete}")
            else:
                files_to_keep[file_md5] = {
                    'path': file_path,
                    'name': file,
                    'size': file_size,
                    'mtime': file_mtime
                }

    return files_to_keep

def delete_small_files(directory, min_size=1024*1024):
    global delete_all
    global cancel_all
    delete_all = False
    cancel_all = False
    all_skip = False  # 新增标志，用于判断是否选择了 na
    skipped_files = []  # 新增列表，用于存储被略过的文件
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if cancel_all:
                return
                
            file_path = os.path.join(root, file)
            file_size = os.path.getsize(file_path)
            
            if file_size < min_size:
                print(f"发现小文件: {file_path} ({file_size} bytes)")
                if not delete_all and not all_skip:
                    choice = input("删除此文件? (y/n/a/c/na): ").lower()
                    if choice == 'a':
                        delete_all = True
                    elif choice == 'c':
                        cancel_all = True
                        continue
                    elif choice == 'na':
                        all_skip = True
                    elif choice != 'y':
                        skipped_files.append(file_path)  # 记录被略过的文件
                        continue
                if all_skip:
                    skipped_files.append(file_path)  # 记录被略过的文件
                    continue
                try:
                    send2trash.send2trash(convert_path(file_path))
                except:
                    os.remove(file_path)

    if skipped_files:
        print("以下文件被略过:")
        for file in skipped_files:
            print(file)

# Sub function - Remove the unwanted numbers
def remove_underscore_number(path):  
    for foldername, subfolders, filenames in os.walk(path):  
        for filename in filenames:  
            # 如果文件名中有 _\d+  
            if re.search(r'_\d+', filename):  
                new_filename = re.sub(r'_\d+', '', filename)  
                # 检查新文件名是否已存在  
                if os.path.exists(os.path.join(foldername, new_filename)):  
                    print(f'File {new_filename} already exists in {foldername}. Skipping...')  
                else:  
                    # 如果新文件名不存在，则重命名文件  
                    os.rename(os.path.join(foldername, filename), os.path.join(foldername, new_filename))  
                    print(f'Renamed file {filename} to {new_filename} in {foldername}.')  


#查找特定文件夹下面所有的视频文件（包括子文件夹）；使用cv2检查每个视频文件是否可以播放是否完整；如果不能播放或者不完整，将其移动到回收站


def can_play_video(file_path):
    try:
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            print(f"Video {file_path} cannot be opened")
            return False
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            print(f"Video {file_path} is incomplete")
            return False
        cap.release()
        return True
    except Exception as e:
        print(f"Error playing video {file_path}: {e}")
        return False
    
def check_videos_in_directory(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(('.mp4', '.avi', '.mov', 'mkv')):
                file_path = os.path.join(root, file)
                playable = can_play_video(file_path)
                if not playable:
                    # remove the files which is not playable
                    send2trash.send2trash(convert_path(file_path))
                    print(f"Video {file_path} is playable: {playable}")
def select_directory():
    """打开文件浏览器让用户选择目录。"""
    root = Tk()
    root.withdraw()  # 隐藏主窗口
    directory = askdirectory(title="Select Directory To Process")
    if directory:
        return directory
    else:
        print("No directory selected.")
        exit(1)

# set the path as "D:\Video"
if __name__ == "__main__":
    
    # set for laptop thinkbook T14p
    path = select_directory()

    # Remove the duplicated files
    remove_duplicate_files(path)
    
    # Check the videos and remove the bad videos
    check_videos_in_directory(path)

    # Delete the files which size is less than 1MB
    delete_small_files(path, min_size=1024 * 1024)
    
    # Rename the files
    process_filenames(path)  

    # Remove the unwanted numbers
    remove_underscore_number(path)

 
