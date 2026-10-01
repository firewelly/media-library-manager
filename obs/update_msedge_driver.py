import os
import platform
import subprocess
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import zipfile

def get_edge_version():
    """获取已安装的Edge浏览器版本"""
    try:
        if platform.system() == "Windows":
            cmd = r'reg query "HKEY_CURRENT_USER\Software\Microsoft\Edge\BLBeacon" /v version'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            version = result.stdout.split()[-1]
        else:  # macOS
            cmd = '/Applications/Microsoft\ Edge.app/Contents/MacOS/Microsoft\ Edge --version'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            version = result.stdout.split()[2]
        return version  # 返回完整版本号
    except Exception as e:
        print(f"获取Edge版本失败: {e}")
        return None



def get_driver_download_url(version):
    """根据Edge版本获取对应的Driver下载URL"""
    base_urls = [
        "https://msedgedriver.microsoft.com",
        "https://msedgedriver.azureedge.net"
    ]
    
    # 配置重试机制
    retry_strategy = Retry(
        total=2,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    http = requests.Session()
    http.mount("https://", adapter)
    http.mount("http://", adapter)
    
    # 设置超时时间
    http.timeout = 10
    
    # 根据操作系统确定文件名
    def get_driver_filename():
        system = platform.system().lower()
        if system == "windows":
            return "edgedriver_win64.zip"
        elif system == "darwin":  # macOS
            # 检查是否为Apple Silicon (M1/M2)
            machine = platform.machine().lower()
            if machine in ['arm64', 'aarch64']:
                return "edgedriver_mac64_m1.zip"
            else:
                return "edgedriver_mac64.zip"
        elif system == "linux":
            return "edgedriver_linux64.zip"
        else:
            return "edgedriver_mac64.zip"  # 默认fallback
    
    driver_filename = get_driver_filename()
    
    # 尝试从当前版本开始，逐步降级查找可用版本
    major_version = version.split('.')[0]  # 提取主版本号用于降级查找
    
    for base_url in base_urls:
        try:
            # 首先尝试精确版本
            url = f"{base_url}/{version}/{driver_filename}"
            try:
                response = http.head(url, timeout=10)
                if response.status_code == 200:
                    return url
            except requests.exceptions.RequestException:
                pass
            
            # 如果精确版本不存在，尝试主版本号降级
            for v in range(int(major_version), int(major_version)-5, -1):
                try:
                    fallback_url = f"{base_url}/{v}.0.0.0/{driver_filename}"
                    fallback_response = http.head(fallback_url, timeout=10)
                    if fallback_response.status_code == 200:
                        return fallback_url
                except requests.exceptions.RequestException:
                    continue
                    
        except requests.exceptions.RequestException as e:
            print(f"无法连接到 {base_url}: {e}")
            continue
    
    return None

def download_and_install_driver(download_url, install_path):
    """下载并安装EdgeDriver"""
    if not download_url:
        print("错误: 找不到匹配的EdgeDriver版本")
        return False
        
    try:
        print(f"正在下载: {download_url}")
        response = requests.get(download_url, stream=True)
        response.raise_for_status()
        
        temp_file = "edgedriver_temp"
        with open(temp_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print("解压安装中...")
        system = platform.system().lower()
        
        with zipfile.ZipFile(temp_file, 'r') as zip_ref:
            if system == "windows":
                # Windows: 直接解压到目标目录
                zip_ref.extractall(os.path.dirname(install_path))
            else:
                # macOS/Linux: 解压到当前目录然后移动
                zip_ref.extractall()
                
                # 确定解压后的可执行文件名
                extracted_file = 'msedgedriver'
                if system == "windows":
                    extracted_file = 'msedgedriver.exe'
                
                # 移动文件到目标位置
                if install_path.startswith('/usr/local/'):
                    subprocess.run(['sudo', 'mv', extracted_file, install_path], check=True)
                    subprocess.run(['sudo', 'chmod', '755', install_path], check=True)
                else:
                    os.rename(extracted_file, install_path)
                    os.chmod(install_path, 0o755)
        
        os.remove(temp_file)
        print(f"安装完成: {install_path}")
        return True
    except Exception as e:
        print(f"下载或安装失败: {e}")
        return False

def check_existing_driver_version(install_path):
    """检查已安装Driver的版本"""
    if not os.path.exists(install_path):
        return None
    
    try:
        result = subprocess.run([install_path, "--version"], capture_output=True, text=True)
        output = result.stdout.strip()
        if output:
            # 尝试提取版本号，格式通常是 "Microsoft Edge WebDriver 138.0.3351.121"
            parts = output.split()
            for part in parts:
                if '.' in part and part.replace('.', '').isdigit():
                    return part  # 返回完整版本号
            # 如果找不到版本号格式，返回最后一个包含数字的部分
            for part in reversed(parts):
                if any(c.isdigit() for c in part):
                    return part
        return None
    except Exception as e:
        print(f"检查现有Driver版本失败: {e}")
        return None

def main():
    # 确定安装路径
    system = platform.system().lower()
    if system == "windows":
        install_path = r"C:\bin\edgedriver_win64\msedgedriver.exe"
    elif system == "darwin":  # macOS
        # 检查是否为Apple Silicon (M1/M2)
        machine = platform.machine().lower()
        if machine in ['arm64', 'aarch64']:
            install_path = "/usr/local/bin/edgedriver_mac64_m1/msedgedriver"
        else:
            install_path = "/usr/local/bin/edgedriver_mac64/msedgedriver"
    elif system == "linux":
        install_path = "/usr/local/bin/edgedriver_linux64/msedgedriver"
    else:
        install_path = "/usr/local/bin/edgedriver_mac64/msedgedriver"  # 默认fallback
    
    # 创建目录(如果不存在)
    try:
        os.makedirs(os.path.dirname(install_path), exist_ok=True)
    except PermissionError:
        print("\n需要管理员权限来创建系统目录")
        print(f"请手动运行以下命令创建目录并设置权限:")
        print(f"sudo mkdir -p {os.path.dirname(install_path)}")
        print(f"sudo chown -R $(whoami) {os.path.dirname(install_path)}")
        print("\n或者您可以选择安装到用户目录下:")
        user_path = os.path.expanduser("~/bin/edgedriver_mac64_m1/msedgedriver")
        choice = input(f"是否安装到用户目录 {user_path}? (y/n): ").lower()
        if choice == 'y':
            install_path = user_path
            os.makedirs(os.path.dirname(install_path), exist_ok=True)
        else:
            print("安装中止")
            return
    
    # 获取Edge浏览器版本
    edge_version = get_edge_version()
    if not edge_version:
        return
    
    print(f"当前Edge版本: {edge_version}")
    
    # 检查现有Driver版本
    driver_version = check_existing_driver_version(install_path)
    if driver_version:
        print(f"现有Driver版本: {driver_version}")
        if driver_version == edge_version:
            print("版本匹配，无需更新")
            return
        else:
            print("现有Driver版本与浏览器版本不匹配，尝试更新Driver")
    
    # 下载并安装匹配的Driver
    try:
        download_url = get_driver_download_url(edge_version)
        if download_url:
            if not download_and_install_driver(download_url, install_path):
                print("无法找到或安装匹配的EdgeDriver版本")
                return
        else:
             print("\n❌ 无法找到匹配的EdgeDriver版本")
             print("\n可能的解决方案:")
             print("1. 检查网络连接是否正常")
             print("2. 手动下载EdgeDriver:")
             print(f"   - 访问: https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/")
             print(f"   - 下载适合版本 {edge_version} 的驱动")
             print(f"   - 解压并放置到: {install_path}")
             print("3. 稍后重试，可能是临时网络问题")
             if driver_version:
                 print(f"\n💡 提示: 当前已有Driver版本 {driver_version}，虽然版本不完全匹配，但可能仍然可用")
             return
    except Exception as e:
        print(f"\n❌ 网络连接错误: {e}")
        print("\n可能的解决方案:")
        print("1. 检查网络连接")
        print("2. 检查防火墙设置")
        print("3. 尝试使用VPN或更换网络")
        print("4. 手动下载EdgeDriver:")
        print(f"   - 访问: https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/")
        print(f"   - 下载适合版本 {edge_version} 的驱动")
        print(f"   - 解压并放置到: {install_path}")
        return

if __name__ == "__main__":
    main()