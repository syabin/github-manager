import os
import sys
import requests

REPO = "syabin/github-manager"
FILE = "github_manager.pyw"
URL = f"https://raw.githubusercontent.com/{REPO}/main/{FILE}"

def main():
    print("=" * 50)
    print("GitHub Manager 强制更新工具")
    print("=" * 50)

    current_dir = os.path.dirname(os.path.abspath(__file__))
    target_file = os.path.join(current_dir, FILE)
    backup_file = target_file + ".bak"

    print(f"\n目标文件: {target_file}")
    print(f"下载地址: {URL}")

    print("\n正在下载最新版本...")
    try:
        resp = requests.get(URL, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"\n下载失败: {e}")
        input("\n按回车键退出...")
        return 1

    content = resp.text
    if not content or "APP_VERSION" not in content:
        print("\n下载内容无效")
        input("\n按回车键退出...")
        return 1

    print("下载成功")

    if os.path.exists(backup_file):
        os.remove(backup_file)
        print("已删除旧备份")

    if os.path.exists(target_file):
        os.rename(target_file, backup_file)
        print("已备份当前文件")

    with open(target_file, 'w', encoding='utf-8') as f:
        f.write(content)

    print("\n更新完成！")
    print(f"新文件: {target_file}")
    print(f"备份文件: {backup_file}")
    input("\n按回车键退出...")
    return 0

if __name__ == "__main__":
    sys.exit(main())
