import os
import subprocess

GIT = r"C:\Program Files\Git\cmd\git.exe"
REPO_DIR = os.path.dirname(os.path.abspath(__file__))

def run_git(args):
    cmd = [GIT] + args
    result = subprocess.run(cmd, cwd=REPO_DIR, capture_output=True, text=True, timeout=120)
    return result.returncode == 0, result.stdout + result.stderr

def main():
    print("=" * 50)
    print("GitHub Manager 更新工具")
    print("=" * 50)
    print(f"\n仓库目录: {REPO_DIR}")

    print("\n正在拉取最新版本...")
    ok, msg = run_git(["pull", "origin", "main"])
    if not ok:
        ok, msg = run_git(["pull", "origin", "master"])

    if ok:
        print("更新成功！")
        print(msg)
    else:
        print(f"更新失败: {msg}")

    input("\n按回车键退出...")
    return 0 if ok else 1

if __name__ == "__main__":
    exit(main())
