import os
import sys
import json
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext, simpledialog
import requests
from datetime import datetime

APP_VERSION = "1.1.0"
UPDATE_REPO = "syabin/github-manager"


class ConfigManager:
    def __init__(self):
        self.config_file = os.path.join(os.path.dirname(__file__), ".env")
        self.config = self.load_config()

    def load_config(self):
        config = {
            "github_token": "",
            "github_username": "",
            "repos_path": "",
            "default_branch": "main",
        }
        if os.path.exists(self.config_file):
            with open(self.config_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        config[key.strip()] = value.strip()
        return config

    def save_config(self):
        with open(self.config_file, "w", encoding="utf-8") as f:
            f.write("# GitHub Manager 配置文件\n")
            for key, value in self.config.items():
                f.write(f"{key}={value}\n")


class GitManager:
    def __init__(self, config: ConfigManager):
        self.config = config

    def run_git(self, repo_path, args):
        cmd = [r"C:\Program Files\Git\cmd\git.exe"] + args
        try:
            result = subprocess.run(
                cmd, cwd=repo_path, capture_output=True, text=True, timeout=300,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "命令超时"
        except Exception as e:
            return False, str(e)

    def is_git_repo(self, path):
        return os.path.exists(os.path.join(path, ".git"))

    def clone(self, repo_url, target_path, log_callback=None):
        def _log(msg):
            if log_callback:
                log_callback(msg)

        _log(f"正在克隆: {repo_url}")
        cmd = ["git", "clone", repo_url, target_path]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                _log("克隆成功")
                return True, "克隆成功"
            else:
                _log(f"克隆失败: {result.stderr}")
                return False, result.stderr
        except Exception as e:
            _log(f"克隆错误: {str(e)}")
            return False, str(e)

    def pull(self, repo_path, log_callback=None):
        def _log(msg):
            if log_callback:
                log_callback(msg)

        _log("正在同步...")

        ok, _ = self.run_git(repo_path, ["fetch", "origin"])
        if not ok:
            _log("fetch 失败")
            return False, "fetch失败"

        ok, branch = self.run_git(repo_path, ["branch", "--show-current"])
        branch = branch.strip() if ok and branch.strip() else "main"

        ok, local_time = self.run_git(repo_path, ["log", "-1", "--format=%at"])
        ok2, remote_time = self.run_git(repo_path, ["log", "-1", "--format=%at", f"origin/{branch}"])

        if ok and ok2 and local_time.strip() and remote_time.strip():
            local_ts = int(local_time.strip())
            remote_ts = int(remote_time.strip())
            if remote_ts > local_ts:
                _log("发现云端有更新")
            elif local_ts > remote_ts:
                _log("本地比云端更新")
            else:
                _log("已是最新")

        ok, msg = self.run_git(repo_path, ["pull", "origin", branch])
        if not ok:
            ok, msg = self.run_git(repo_path, ["pull", "origin", "main"])
        if not ok:
            ok, msg = self.run_git(repo_path, ["pull", "origin", "master"])

        if ok:
            _log("拉取成功")
        else:
            _log(f"拉取失败: {msg}")
        return ok, msg

    def push(self, repo_path, log_callback=None):
        def _log(msg):
            if log_callback:
                log_callback(msg)

        _log("正在同步...")

        ok, _ = self.run_git(repo_path, ["fetch", "origin"])
        if not ok:
            _log("fetch 失败")
            return False, "fetch失败"

        ok, branch = self.run_git(repo_path, ["branch", "--show-current"])
        branch = branch.strip() if ok and branch.strip() else "main"

        ok, local_time = self.run_git(repo_path, ["log", "-1", "--format=%at"])
        ok2, remote_time = self.run_git(repo_path, ["log", "-1", "--format=%at", f"origin/{branch}"])

        if ok and ok2 and local_time and remote_time and local_time.strip() and remote_time.strip():
            local_ts = int(local_time.strip())
            remote_ts = int(remote_time.strip())
            if remote_ts > local_ts:
                _log("警告: 云端有更新，建议先下载")
            elif local_ts > remote_ts:
                _log("本地有更新")
            else:
                _log("已是最新")

        _log("正在推送...")
        ok, msg = self.run_git(repo_path, ["push", "-u", "origin", branch])
        if ok:
            _log("推送成功")
        else:
            _log(f"推送失败: {msg}")
        return ok, msg

    def status(self, repo_path):
        ok, msg = self.run_git(repo_path, ["status", "--porcelain"])
        return ok, msg.strip()

    def init_repo(self, repo_path, log_callback=None):
        def _log(msg):
            if log_callback:
                log_callback(msg)

        _log("正在初始化仓库...")
        ok, msg = self.run_git(repo_path, ["init"])
        if ok:
            _log("初始化成功")
        return ok, msg

    def add_remote(self, repo_path, remote_url, log_callback=None):
        def _log(msg):
            if log_callback:
                log_callback(msg)

        _log("正在添加远程仓库...")
        ok, _ = self.run_git(repo_path, ["remote", "remove", "origin"])
        ok, msg = self.run_git(repo_path, ["remote", "add", "origin", remote_url])
        if ok:
            _log("远程仓库添加成功")
        return ok, msg

    def commit(self, repo_path, message, log_callback=None):
        def _log(msg):
            if log_callback:
                log_callback(msg)

        _log("正在提交...")
        ok, _ = self.run_git(repo_path, ["add", "-A"])
        ok, msg = self.run_git(repo_path, ["commit", "-m", message])
        if ok:
            _log("提交成功")
        else:
            _log(f"提交: {msg}")
        return ok, msg

    def get_current_branch(self, repo_path):
        ok, msg = self.run_git(repo_path, ["branch", "--show-current"])
        return msg.strip() if ok else "main"

    def get_local_repos(self, base_path, exclude_dirs=None):
        repos = []
        if not os.path.exists(base_path):
            return repos
        if exclude_dirs is None:
            exclude_dirs = []
        for item in os.listdir(base_path):
            if item in exclude_dirs:
                continue
            item_path = os.path.join(base_path, item)
            if os.path.isdir(item_path):
                is_git = self.is_git_repo(item_path)
                status = ""
                if is_git:
                    ok, status = self.status(item_path)
                    if not ok:
                        status = "未知"
                    elif status:
                        status = "有修改"
                    else:
                        status = "已同步"
                else:
                    status = "未初始化"
                repos.append(
                    {"name": item, "path": item_path, "is_git": is_git, "status": status}
                )
        return repos


class GitHubAPI:
    def __init__(self, token, username):
        self.token = token
        self.username = username
        self.headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        self.base_url = "https://api.github.com"

    def validate_token(self):
        try:
            resp = requests.get(f"{self.base_url}/user", headers=self.headers, timeout=10)
            return resp.status_code == 200
        except:
            return False

    def repo_exists(self, repo_name):
        try:
            url = f"{self.base_url}/repos/{self.username}/{repo_name}"
            resp = requests.get(url, headers=self.headers, timeout=10)
            return resp.status_code == 200
        except:
            return False

    def create_repo(self, repo_name, private=False):
        try:
            url = f"{self.base_url}/user/repos"
            data = {"name": repo_name, "private": private}
            resp = requests.post(url, headers=self.headers, json=data, timeout=30)
            return resp.status_code == 201
        except:
            return False

    def update_repo_visibility(self, repo_name, private):
        try:
            url = f"{self.base_url}/repos/{self.username}/{repo_name}"
            data = {"private": private}
            resp = requests.patch(url, headers=self.headers, json=data, timeout=30)
            return resp.status_code == 200
        except:
            return False

    def get_repo_url(self, repo_name):
        return f"https://github.com/{self.username}/{repo_name}.git"

    def list_user_repos(self):
        repos = []
        page = 1
        while True:
            try:
                url = f"{self.base_url}/user/repos?page={page}&per_page=100&sort=updated"
                resp = requests.get(url, headers=self.headers, timeout=10)
                if resp.status_code != 200:
                    break
                data = resp.json()
                if not data:
                    break
                for repo in data:
                    repos.append({
                        "name": repo["name"],
                        "full_name": repo["full_name"],
                        "private": repo["private"],
                        "description": repo.get("description", ""),
                        "updated_at": repo.get("updated_at", ""),
                        "clone_url": repo["clone_url"],
                        "html_url": repo["html_url"],
                    })
                page += 1
            except:
                break
        return repos

    def list_org_repos(self, org):
        repos = []
        page = 1
        while True:
            try:
                url = f"{self.base_url}/orgs/{org}/repos?page={page}&per_page=100&sort=updated"
                resp = requests.get(url, headers=self.headers, timeout=10)
                if resp.status_code != 200:
                    break
                data = resp.json()
                if not data:
                    break
                for repo in data:
                    repos.append({
                        "name": repo["name"],
                        "full_name": repo["full_name"],
                        "private": repo["private"],
                        "description": repo.get("description", ""),
                        "updated_at": repo.get("updated_at", ""),
                        "clone_url": repo["clone_url"],
                        "html_url": repo["html_url"],
                    })
                page += 1
            except:
                break
        return repos


class GitHubManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"GitHub 仓库管理工具 v{APP_VERSION}")
        self.root.geometry("900x600")

        self.config = ConfigManager()
        self.git = GitManager(self.config)
        self.github = None

        self.selected_repos = set()
        self.setup_ui()
        self.load_settings()
        self.refresh_repo_list()
        if self.github:
            self.fetch_remote_repos()


    def setup_ui(self):
        style = ttk.Style()
        style.configure("Status.TLabel", foreground="gray")

        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        settings_frame = ttk.LabelFrame(main_frame, text="设置", padding=5)
        settings_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(settings_frame, text="仓库目录:").grid(row=0, column=0, sticky=tk.W)
        self.path_var = tk.StringVar()
        path_entry = ttk.Entry(settings_frame, textvariable=self.path_var, width=50)
        path_entry.grid(row=0, column=1, padx=5)
        path_entry.bind("<FocusOut>", lambda e: self.save_path())
        ttk.Button(settings_frame, text="浏览", command=self.browse_path).grid(row=0, column=2)

        ttk.Label(settings_frame, text="GitHub用户:").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.user_var = tk.StringVar()
        ttk.Entry(settings_frame, textvariable=self.user_var, width=30).grid(
            row=1, column=1, padx=5, sticky=tk.W, pady=(5, 0)
        )

        ttk.Label(settings_frame, text="Token:").grid(row=2, column=0, sticky=tk.W, pady=(5, 0))
        self.token_var = tk.StringVar()
        token_entry = ttk.Entry(settings_frame, textvariable=self.token_var, width=50, show="*")
        token_entry.grid(row=2, column=1, padx=5, sticky=tk.W, pady=(5, 0))
        ttk.Button(settings_frame, text="验证", command=self.validate_token).grid(
            row=2, column=2, pady=(5, 0)
        )

        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.LabelFrame(content_frame, text="本地仓库", padding=5)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.repo_tree = ttk.Treeview(
            left_frame, columns=("name", "status"), show="headings", selectmode="extended"
        )
        self.repo_tree.heading("name", text="仓库名称")
        self.repo_tree.heading("status", text="状态")
        self.repo_tree.column("name", width=200)
        self.repo_tree.column("status", width=100)
        self.repo_tree.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.repo_tree.yview)
        self.repo_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.repo_tree.bind("<<TreeviewSelect>>", self.on_repo_select)
        self.repo_tree.bind("<Double-1>", self.on_repo_double_click)

        remote_frame = ttk.LabelFrame(content_frame, text="云端仓库", padding=5)
        remote_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))

        self.remote_tree = ttk.Treeview(
            remote_frame, columns=("name", "private", "updated"), show="headings", selectmode="browse"
        )
        self.remote_tree.heading("name", text="仓库名称")
        self.remote_tree.heading("private", text="私有")
        self.remote_tree.heading("updated", text="更新时间")
        self.remote_tree.column("name", width=200)
        self.remote_tree.column("private", width=50)
        self.remote_tree.column("updated", width=120)
        self.remote_tree.pack(fill=tk.BOTH, expand=True)

        remote_scrollbar = ttk.Scrollbar(remote_frame, orient=tk.VERTICAL, command=self.remote_tree.yview)
        self.remote_tree.configure(yscrollcommand=remote_scrollbar.set)
        remote_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.remote_tree.bind("<Double-1>", self.on_remote_double_click)

        right_frame = ttk.Frame(content_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        ttk.Button(right_frame, text="刷新本地", command=self.refresh_repo_list).pack(
            fill=tk.X, pady=(0, 5)
        )
        ttk.Button(right_frame, text="获取云端列表", command=self.fetch_remote_repos).pack(
            fill=tk.X, pady=(0, 5)
        )
        ttk.Button(right_frame, text="下载", command=self.pull_repos).pack(
            fill=tk.X, pady=(0, 5)
        )
        ttk.Button(right_frame, text="上传(Push)", command=self.push_repos).pack(
            fill=tk.X, pady=(0, 5)
        )
        ttk.Separator(right_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        ttk.Button(right_frame, text="新建仓库", command=self.create_new_repo).pack(
            fill=tk.X, pady=(0, 5)
        )
        ttk.Button(right_frame, text="初始化Git", command=self.init_selected).pack(
            fill=tk.X, pady=(0, 5)
        )
        ttk.Button(right_frame, text="新建云端仓库", command=self.create_remote_repo).pack(
            fill=tk.X, pady=(0, 5)
        )
        ttk.Button(right_frame, text="修改可见性", command=self.toggle_visibility).pack(
            fill=tk.X, pady=(0, 5)
        )
        ttk.Separator(right_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        ttk.Button(right_frame, text="强制更新", command=self.force_update).pack(
            fill=tk.X, pady=(0, 5)
        )

        log_frame = ttk.LabelFrame(main_frame, text="日志", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(main_frame, textvariable=self.status_var, style="Status.TLabel").pack(
            anchor=tk.W, pady=(5, 0)
        )

    def save_path(self):
        path = self.path_var.get().strip()
        if path:
            self.config.config["repos_path"] = path
            self.config.save_config()
            self.refresh_repo_list()

    def browse_path(self):
        path = filedialog.askdirectory(title="选择仓库目录")
        if path:
            self.path_var.set(path)
            self.config.config["repos_path"] = path
            self.config.save_config()
            self.refresh_repo_list()

    def load_settings(self):
        cfg = self.config.config
        self.path_var.set(cfg.get("repos_path", ""))
        self.user_var.set(cfg.get("github_username", ""))
        self.token_var.set(cfg.get("github_token", ""))

        if cfg.get("github_token") and cfg.get("github_username"):
            self.github = GitHubAPI(cfg["github_token"], cfg["github_username"])

    def validate_token(self):
        token = self.token_var.get().strip()
        user = self.user_var.get().strip()
        if not token or not user:
            messagebox.showwarning("警告", "请输入用户名和Token")
            return
        self.config.config["github_token"] = token
        self.config.config["github_username"] = user
        self.config.save_config()
        self.github = GitHubAPI(token, user)
        if self.github.validate_token():
            self.log("Token验证成功")
            messagebox.showinfo("成功", "Token验证成功")
        else:
            self.log("Token验证失败")
            messagebox.showerror("错误", "Token验证失败，请检查用户名和Token")

    def force_update(self):
        def _force():
            try:
                self.log("正在强制下载最新版本...")
                url = f"https://raw.githubusercontent.com/{UPDATE_REPO}/master/github_manager.pyw"
                resp = requests.get(url, timeout=30)
                if resp.status_code != 200:
                    self.log("下载失败")
                    return

                content = resp.text
                if not content or "APP_VERSION" not in content:
                    self.log("下载内容无效")
                    return

                if messagebox.askyesno("强制更新", "将从云端下载最新版本并覆盖当前文件\n\n是否继续？"):
                    self._do_update(content)
            except Exception as e:
                self.log(f"强制更新出错: {e}")

        self.run_in_thread(_force)

    def _do_update(self, new_content):
        try:
            current_file = os.path.abspath(__file__)
            backup_file = current_file + ".bak"

            if os.path.exists(backup_file):
                os.remove(backup_file)
            os.rename(current_file, backup_file)

            with open(current_file, 'w', encoding='utf-8') as f:
                f.write(new_content)

            self.log("更新完成，正在重启...")
            messagebox.showinfo("更新成功", "更新完成，程序即将重启")

            self.root.destroy()
            python = sys.executable
            os.execl(python, python, *sys.argv)
        except Exception as e:
            self.log(f"更新失败: {e}")
            if os.path.exists(backup_file):
                os.rename(backup_file, current_file)
            messagebox.showerror("更新失败", f"更新出错: {e}")

    def log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{timestamp}] {msg}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def clear_log(self):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def refresh_repo_list(self):
        for item in self.repo_tree.get_children():
            self.repo_tree.delete(item)

        path = self.path_var.get()
        if not path or not os.path.exists(path):
            self.log("仓库目录不存在或未设置")
            return

        repos = self.git.get_local_repos(path, self.config.config.get("exclude_dirs", []))
        for repo in repos:
            self.repo_tree.insert(
                "", tk.END, values=(repo["name"], repo["status"]), tags=(repo["path"],)
            )
        self.log(f"找到 {len(repos)} 个仓库")

    def on_repo_select(self, event):
        self.selected_repos.clear()
        for item in self.repo_tree.selection():
            tags = self.repo_tree.item(item, "tags")
            if tags:
                self.selected_repos.add(tags[0])

    def on_repo_double_click(self, event):
        item = self.repo_tree.selection()
        if item:
            tags = self.repo_tree.item(item[0], "tags")
            if tags:
                path = tags[0]
                if os.path.exists(path):
                    os.startfile(path)

    def on_remote_double_click(self, event):
        item = self.remote_tree.selection()
        if item:
            tags = self.remote_tree.item(item[0], "tags")
            if tags:
                html_url = tags[0].replace(".git", "")
                os.startfile(html_url)

    def run_in_thread(self, func):
        thread = threading.Thread(target=func, daemon=True)
        thread.start()

    def fetch_remote_repos(self):
        if not self.github:
            messagebox.showwarning("警告", "请先验证Token")
            return

        def _fetch():
            self.log("正在获取云端仓库列表...")
            repos = self.github.list_user_repos()
            self.root.after(0, lambda: self._update_remote_tree(repos))

        self.run_in_thread(_fetch)

    def _update_remote_tree(self, repos):
        for item in self.remote_tree.get_children():
            self.remote_tree.delete(item)
        for repo in repos:
            private = "是" if repo["private"] else "否"
            updated = repo["updated_at"][:10] if repo["updated_at"] else ""
            self.remote_tree.insert(
                "", tk.END, values=(repo["name"], private, updated),
                tags=(repo["clone_url"], repo["name"])
            )
        self.log(f"找到 {len(repos)} 个云端仓库")

    def pull_repos(self):
        if not self.selected_repos:
            messagebox.showwarning("警告", "请先选择要更新的仓库")
            return

        repos_with_changes = []
        repos_with_remote_updates = []

        for path in self.selected_repos:
            if self.git.is_git_repo(path):
                ok, status = self.git.status(path)
                if ok and status.strip():
                    repos_with_changes.append(os.path.basename(path))

                self.git.run_git(path, ["fetch", "origin"])
                ok, branch = self.git.run_git(path, ["branch", "--show-current"])
                branch = branch.strip() if ok and branch.strip() else "main"
                ok, local_time = self.git.run_git(path, ["log", "-1", "--format=%at"])
                ok2, remote_time = self.git.run_git(path, ["log", "-1", "--format=%at", f"origin/{branch}"])
                if ok and ok2 and local_time.strip() and remote_time.strip():
                    if int(remote_time.strip()) > int(local_time.strip()):
                        repos_with_remote_updates.append(os.path.basename(path))

        msg_parts = []
        if repos_with_changes:
            msg_parts.append("以下仓库有未保存的修改:\n" + "\n".join(repos_with_changes))
        if repos_with_remote_updates:
            msg_parts.append("以下仓库云端有更新:\n" + "\n".join(repos_with_remote_updates))

        if msg_parts:
            msg = "\n\n".join(msg_parts) + "\n\n是否继续下载?"
            if not messagebox.askyesno("确认", msg):
                return

        def _pull():
            for path in self.selected_repos:
                if self.git.is_git_repo(path):
                    self.git.pull(path, log_callback=self.log)
            self.root.after(0, self.refresh_repo_list)

        self.run_in_thread(_pull)

    def push_repos(self):
        if not self.selected_repos:
            messagebox.showwarning("警告", "请先选择要上传的仓库")
            return

        repos_with_remote_updates = []

        for path in self.selected_repos:
            if self.git.is_git_repo(path):
                self.git.run_git(path, ["fetch", "origin"])
                ok, branch = self.git.run_git(path, ["branch", "--show-current"])
                branch = branch.strip() if ok and branch.strip() else "main"
                ok, local_time = self.git.run_git(path, ["log", "-1", "--format=%at"])
                ok2, remote_time = self.git.run_git(path, ["log", "-1", "--format=%at", f"origin/{branch}"])
                if ok and ok2 and local_time and remote_time and local_time.strip() and remote_time.strip():
                    if int(remote_time.strip()) > int(local_time.strip()):
                        repos_with_remote_updates.append(os.path.basename(path))

        if repos_with_remote_updates:
            msg = "以下仓库云端有更新，建议先下载:\n" + "\n".join(repos_with_remote_updates) + "\n\n是否继续上传?"
            if not messagebox.askyesno("确认", msg):
                return

        has_changes = False
        for path in self.selected_repos:
            if self.git.is_git_repo(path):
                ok, status = self.git.status(path)
                if ok and status.strip():
                    has_changes = True
                    break

        commit_msg = ""
        if has_changes:
            dialog = tk.Toplevel(self.root)
            dialog.title("提交信息")
            dialog.geometry("400x150")
            dialog.transient(self.root)
            dialog.grab_set()
            dialog.update_idletasks()
            x = self.root.winfo_rootx() + (self.root.winfo_width() - 400) // 2
            y = self.root.winfo_rooty() + (self.root.winfo_height() - 150) // 2
            dialog.geometry(f"+{x}+{y}")

            ttk.Label(dialog, text="请输入提交信息:").pack(pady=(10, 5))

            text_var = tk.StringVar(value=f"update {os.path.basename(list(self.selected_repos)[0])}")
            text_entry = ttk.Entry(dialog, textvariable=text_var, width=50)
            text_entry.pack(pady=5, padx=10)
            text_entry.select_range(0, tk.END)
            text_entry.focus()

            result = [None]

            def on_ok():
                result[0] = text_var.get()
                dialog.destroy()

            def on_cancel():
                dialog.destroy()

            btn_frame = ttk.Frame(dialog)
            btn_frame.pack(pady=10)
            ttk.Button(btn_frame, text="确定", command=on_ok).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text="取消", command=on_cancel).pack(side=tk.LEFT, padx=5)

            self.root.wait_window(dialog)

            commit_msg = result[0]
            if commit_msg is None:
                return
            if not commit_msg:
                commit_msg = f"update {os.path.basename(list(self.selected_repos)[0])}"

        def _push():
            for path in self.selected_repos:
                if self.git.is_git_repo(path):
                    ok, status = self.git.status(path)
                    if ok and status.strip():
                        msg = commit_msg if commit_msg else f"update {os.path.basename(path)}"
                        self.git.commit(path, msg, log_callback=self.log)
                    self.git.push(path, log_callback=self.log)
            self.root.after(1000, self.refresh_repo_list)

        self.run_in_thread(_push)

    def create_remote_repo(self):
        if not self.github:
            messagebox.showwarning("警告", "请先验证Token")
            return

        repo_name = simpledialog.askstring("创建仓库", "请输入新仓库名称:")
        if not repo_name:
            return

        if self.github.create_repo(repo_name):
            self.log(f"远程仓库创建成功: {repo_name}")
            messagebox.showinfo("成功", f"远程仓库创建成功: {repo_name}")
        else:
            messagebox.showerror("错误", "创建仓库失败")

    def toggle_visibility(self):
        if not self.github:
            messagebox.showwarning("警告", "请先验证Token")
            return

        selection = self.remote_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择要修改的仓库")
            return

        item = selection[0]
        tags = self.remote_tree.item(item, "tags")
        repo_name = tags[1]

        values = self.remote_tree.item(item, "values")
        current_private = values[1]

        new_private = current_private == "否"
        new_text = "是" if new_private else "否"

        def _toggle():
            if self.github.update_repo_visibility(repo_name, new_private):
                self.log(f"仓库 {repo_name} 已改为{'私有' if new_private else '公开'}")
                self.root.after(0, self.fetch_remote_repos)
            else:
                self.log(f"修改失败: {repo_name}")

        self.run_in_thread(_toggle)

    def create_new_repo(self):
        selection = self.remote_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先在云端仓库列表中选择一个仓库")
            return

        item = selection[0]
        tags = self.remote_tree.item(item, "tags")
        clone_url = tags[0]
        repo_name = tags[1]

        base_path = self.path_var.get()
        if not base_path:
            messagebox.showwarning("警告", "请先设置仓库目录")
            return

        repo_path = os.path.join(base_path, repo_name)
        if os.path.exists(repo_path):
            messagebox.showwarning("警告", f"目录已存在: {repo_path}")
            return

        def _clone():
            ok, msg = self.git.clone(clone_url, repo_path, log_callback=self.log)
            self.root.after(0, self.refresh_repo_list)

        self.run_in_thread(_clone)

    def init_selected(self):
        if not self.selected_repos:
            messagebox.showwarning("警告", "请先选择要初始化的仓库")
            return

        for path in self.selected_repos:
            if not self.git.is_git_repo(path):
                self.git.init_repo(path, log_callback=self.log)
        self.refresh_repo_list()


def main():
    root = tk.Tk()
    app = GitHubManagerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
