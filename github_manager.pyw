import os
import sys
import json
import subprocess
import threading
import traceback
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext, simpledialog
import requests
from datetime import datetime

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug.log")

def debug_log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[{timestamp}] {msg}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

APP_VERSION = "1.1.0"


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
        debug_log(f"run_git: cwd={repo_path} cmd={args}")
        try:
            result = subprocess.run(
                cmd, cwd=repo_path, capture_output=True, text=True, timeout=300,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            out = result.stdout + result.stderr
            debug_log(f"run_git: rc={result.returncode} out={out[:500]}")
            return result.returncode == 0, out
        except subprocess.TimeoutExpired:
            debug_log(f"run_git: TIMEOUT")
            return False, "命令超时"
        except Exception as e:
            debug_log(f"run_git: EXCEPTION {e}")
            return False, str(e)

    def run_git_async(self, repo_path, args, on_done, post=None):
        """异步执行 git 命令。on_done 在子线程触发，post(ok, out) 在主线程触发。"""
        import threading as _t

        def _worker():
            try:
                ok, out = self.run_git(repo_path, args)
            except Exception as e:
                err = f"{e}\n{traceback.format_exc()}"
                debug_log(f"run_git_async EXCEPTION: {args} err={err[:500]}")
                if post is not None:
                    post(False, err)
                elif on_done is not None:
                    on_done(False, err)
                return
            debug_log(f"run_git_async DONE: args={args} ok={ok} out={out[:300]}")
            if post is not None:
                post(ok, out)
            elif on_done is not None:
                on_done(ok, out)

        _t.Thread(target=_worker, daemon=True).start()

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

    def clone_async(self, repo_url, target_path, log_callback=None, on_done=None, post=None):
        """异步 clone，不阻塞 UI。on_done 在子线程触发，post(ok, out) 在主线程触发。"""
        import threading as _t

        def _worker():
            ok, out = self.clone(repo_url, target_path, log_callback=log_callback)
            if post is not None:
                post(ok, out)
            elif on_done is not None:
                on_done(ok, out)

        _t.Thread(target=_worker, daemon=True).start()

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

    def push_async(self, repo_path, on_done=None, post=None, log_callback=None):
        import threading as _t
        import traceback

        def _worker():
            try:
                ok, out = self.push(repo_path, log_callback=log_callback)
            except Exception as e:
                if log_callback:
                    log_callback(f"推送异常: {e}\n{traceback.format_exc()}")
                if post is not None:
                    post(False, str(e))
                elif on_done is not None:
                    on_done(False, str(e))
                return
            if post is not None:
                post(ok, out)
            elif on_done is not None:
                on_done(ok, out)

        _t.Thread(target=_worker, daemon=True).start()

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

    def get_local_repos(self, base_path, exclude_dirs=None, check_remote=False):
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
                    ok, local_status = self.status(item_path)
                    if not ok:
                        status = "未知"
                    elif local_status:
                        status = "有修改"
                    else:
                        status = "已同步"

                    # 检查云端是否有更新
                    if check_remote and status in ("已同步", "有修改"):
                        ok_fetch, _ = self.run_git(item_path, ["fetch", "origin"])
                        if ok_fetch:
                            ok_b, branch = self.run_git(item_path, ["branch", "--show-current"])
                            branch = branch.strip() if ok_b and branch.strip() else "main"
                            ok_l, local_time = self.run_git(item_path, ["log", "-1", "--format=%at"])
                            ok_r, remote_time = self.run_git(item_path, ["log", "-1", "--format=%at", f"origin/{branch}"])
                            if ok_l and ok_r and local_time.strip() and remote_time.strip():
                                if int(remote_time.strip()) > int(local_time.strip()):
                                    if status == "有修改":
                                        status = "有修改+有更新"
                                    else:
                                        status = "有更新"
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

    def rename_repo(self, old_name, new_name):
        try:
            url = f"{self.base_url}/repos/{self.username}/{old_name}"
            data = {"name": new_name}
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
        # 防止系统判定未响应：定时让 pump 跑一下
        self._heartbeat = None
        self.root.after(100, self._tick)

        self.config = ConfigManager()
        self.git = GitManager(self.config)
        self.github = None

        self.selected_repos = set()
        self._scanning = False
        self.setup_ui()
        self.load_settings()
        self.refresh_repo_list()
        if self.github:
            self.fetch_remote_repos()


    def setup_ui(self):
        style = ttk.Style()
        style.configure("Status.TLabel", foreground="gray")
        style.configure("Update.TLabel", foreground="red")
        style.configure("UpdateChange.TLabel", foreground="orange")
        style.configure("Modified.TLabel", foreground="dark orange")
        style.configure("Synced.TLabel", foreground="green")
        style.configure("Uninit.TLabel", foreground="gray")

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
        self.repo_tree.column("status", width=120)
        self.repo_tree.tag_configure("update", foreground="red")
        self.repo_tree.tag_configure("update_change", foreground="orange")
        self.repo_tree.tag_configure("modified", foreground="dark orange")
        self.repo_tree.tag_configure("synced", foreground="green")
        self.repo_tree.tag_configure("uninit", foreground="gray")
        self.repo_tree.tag_configure("unknown", foreground="purple")
        self.repo_tree.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.repo_tree.yview)
        self.repo_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.repo_tree.bind("<<TreeviewSelect>>", self.on_repo_select)
        self.repo_tree.bind("<Double-1>", self.on_repo_double_click)
        self.repo_tree.bind("<Button-1>", self.on_repo_click)

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

        ttk.Label(right_frame, text="刷新", font=("", 9, "bold")).pack(anchor=tk.W)
        self.refresh_btn = ttk.Button(right_frame, text="刷新", command=self.refresh_all)
        self.refresh_btn.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(right_frame, text="同步", font=("", 9, "bold")).pack(anchor=tk.W)
        self.pull_btn = ttk.Button(right_frame, text="下载 (Pull)", command=self.pull_repos)
        self.pull_btn.pack(fill=tk.X, pady=(0, 3))
        self.push_btn = ttk.Button(right_frame, text="上传 (Push)", command=self.push_repos)
        self.push_btn.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(right_frame, text="仓库操作", font=("", 9, "bold")).pack(anchor=tk.W)
        ttk.Button(right_frame, text="新建云端仓库", command=self.create_remote_repo).pack(
            fill=tk.X, pady=(0, 3)
        )
        ttk.Button(right_frame, text="重命名仓库", command=self.rename_repo).pack(
            fill=tk.X, pady=(0, 3)
        )
        ttk.Button(right_frame, text="修改可见性", command=self.toggle_visibility).pack(
            fill=tk.X, pady=(0, 3)
        )
        ttk.Button(right_frame, text="初始化Git", command=self.init_selected).pack(
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

    def refresh_all(self):
        self._set_buttons_state(tk.DISABLED)
        self.status_var.set("正在刷新...")

        def _do():
            if self.github:
                repos = self.github.list_user_repos()
                self.root.after(0, lambda: self._update_remote_tree(repos))
            self.root.after(0, self.refresh_repo_list)
            self.root.after(0, lambda: self._on_sync_done("刷新完成"))

        self.run_in_thread(_do)

    def refresh_repo_list(self):
        if self._scanning:
            debug_log("refresh_repo_list: skipped, already scanning")
            return
        self._scanning = True

        for item in self.repo_tree.get_children():
            self.repo_tree.delete(item)

        path = self.path_var.get()
        if not path or not os.path.exists(path):
            self.log("仓库目录不存在或未设置")
            self._scanning = False
            return

        self.status_var.set("正在扫描仓库...")

        def _worker():
            try:
                repos = self.git.get_local_repos(
                    path, self.config.config.get("exclude_dirs", []), check_remote=True
                )
                debug_log(f"refresh_repo_list: found {len(repos)} repos")
                self.root_after(self._finish_scan, repos)
            except Exception as e:
                debug_log(f"refresh_repo_list ERROR: {e}\n{traceback.format_exc()}")
                self.root_after(lambda: (self.status_var.set("扫描出错"), setattr(self, '_scanning', False)))

        self.run_in_thread(_worker)

    def _finish_scan(self, repos):
        for item in self.repo_tree.get_children():
            self.repo_tree.delete(item)

        status_tag_map = {
            "有更新": "update",
            "有修改+有更新": "update_change",
            "有修改": "modified",
            "已同步": "synced",
            "未初始化": "uninit",
            "未知": "unknown",
        }
        for repo in repos:
            tag = status_tag_map.get(repo["status"], "")
            self.repo_tree.insert(
                "", tk.END, values=(repo["name"], repo["status"]), tags=(repo["path"], tag)
            )
        self._scanning = False
        self.status_var.set("就绪")
        self.log(f"找到 {len(repos)} 个仓库")

    def on_repo_click(self, event):
        # 单击已选中的行 → 取消选中（不与 Ctrl/Shift 多选冲突）
        region = self.repo_tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        row_id = self.repo_tree.identify_row(event.y)
        if not row_id:
            return
        # 修饰键按下时不做取消，保持多选行为
        if event.state & (0x0004 | 0x0001):  # Ctrl or Shift
            return
        cur = self.repo_tree.selection()
        if row_id in cur and len(cur) == 1:
            self.repo_tree.selection_remove(row_id)
            self.selected_repos.clear()
            return "break"

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

    def _tick(self):
        try:
            self._heartbeat = self.root.after(100, self._tick)
        except Exception:
            self._heartbeat = None

    def root_after(self, callback, *args):
        try:
            debug_log(f"root_after: scheduling {callback.__name__} args_len={len(args)}")
            self.root.after(0, lambda: callback(*args))
        except Exception as e:
            debug_log(f"root_after FAILED: {e}")

    def _run_git_async(self, repo_path, args, on_done):
        """在子线程跑 git 命令，完成后用 root_after 把结果投回主线程。"""
        def _worker():
            try:
                ok, out = self.git.run_git(repo_path, args)
            except Exception as e:
                ok, out = False, f"{e}\n{traceback.format_exc()}"
            debug_log(f"_run_git_async DONE: args={args} ok={ok} out={out[:300] if out else ''}")
            self.root_after(on_done, ok, out)

        threading.Thread(target=_worker, daemon=True).start()

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
        base_path = self.path_var.get()
        if not base_path:
            messagebox.showwarning("警告", "请先设置仓库目录")
            return

        repos_to_pull = []
        repos_to_clone = []

        for path in self.selected_repos:
            if self.git.is_git_repo(path):
                repos_to_pull.append(path)

        remote_selection = self.remote_tree.selection()
        for item in remote_selection:
            tags = self.remote_tree.item(item, "tags")
            clone_url = tags[0]
            repo_name = tags[1]
            repo_path = os.path.join(base_path, repo_name)
            if os.path.exists(repo_path) and self.git.is_git_repo(repo_path):
                if repo_path not in repos_to_pull:
                    repos_to_pull.append(repo_path)
            else:
                repos_to_clone.append((repo_name, clone_url, repo_path))

        if not repos_to_pull and not repos_to_clone:
            messagebox.showwarning("警告", "请先选择要下载的仓库")
            return

        self._set_buttons_state(tk.DISABLED)
        self.status_var.set("正在检查仓库状态...")

        # 队列：每条 = (path, 已fetch?, 其它临时数据)
        queue = list(repos_to_pull)
        state = {
            "queue": queue,
            "idx": 0,
            "with_changes": [],
            "with_remote_updates": [],
        }

        def _check_one():
            debug_log(f"pull _check_one: idx={state['idx']}/{len(state['queue'])}")
            if state["idx"] >= len(state["queue"]):
                debug_log("pull _check_one: all done, calling _ask_confirm")
                self.root_after(_ask_confirm)
                return
            path = state["queue"][state["idx"]]
            name = os.path.basename(path)
            self.status_var.set(f"检查 {name} ({state['idx']+1}/{len(state['queue'])})...")

            def _on_status(ok, status):
                debug_log(f"pull _on_status: name={name} ok={ok} status={status[:100] if status else ''}")
                if ok and status.strip():
                    state["with_changes"].append(name)
                debug_log(f"pull _on_status: fetch origin for {name}")
                self._run_git_async(path, ["fetch", "origin"], _on_fetched)

            def _on_fetched(*_):
                debug_log(f"pull _on_fetched: {name}, getting branch")
                self._run_git_async(path, ["branch", "--show-current"], _on_branch)

            def _on_branch(ok_b, branch):
                br = branch.strip() if ok_b and branch.strip() else "main"
                debug_log(f"pull _on_branch: {name} branch={br} ok={ok_b}")
                self._run_git_async(path, ["log", "-1", "--format=%at"], lambda ok_l, local_time: _on_local(br, ok_l, local_time))

            def _on_local(branch, ok_l, local_time):
                debug_log(f"pull _on_local: {name} branch={branch} ok={ok_l} time={local_time[:30] if local_time else ''}")
                def _on_remote(ok_r, remote_time):
                    debug_log(f"pull _on_remote: {name} ok={ok_r} time={remote_time[:30] if remote_time else ''}")
                    if (ok_l and ok_r and local_time.strip()
                            and remote_time.strip()
                            and int(remote_time.strip()) > int(local_time.strip())):
                        state["with_remote_updates"].append(name)
                    state["idx"] += 1
                    debug_log(f"pull _on_remote: advancing idx to {state['idx']}")
                    self.root_after(_check_one)

                self._run_git_async(
                    path, ["log", "-1", "--format=%at", f"origin/{branch}"], _on_remote
                )

            debug_log(f"pull _check_one: starting fetch for {name}")
            self._run_git_async(path, ["fetch", "origin"], _on_fetched)

        def _ask_confirm():
            msg_parts = []
            if repos_to_clone:
                msg_parts.append("将克隆以下仓库:\n" + "\n".join([r[0] for r in repos_to_clone]))
            if state["with_changes"]:
                msg_parts.append("以下仓库有未保存的修改:\n" + "\n".join(state["with_changes"]))
            if state["with_remote_updates"]:
                msg_parts.append("以下仓库云端有更新:\n" + "\n".join(state["with_remote_updates"]))

            proceed = True
            if msg_parts:
                proceed = messagebox.askyesno("确认", "\n\n".join(msg_parts) + "\n\n是否继续下载?")

            if not proceed:
                self._on_sync_done("已取消")
                return

            self._do_pull(repos_to_pull, repos_to_clone)

        self.root_after(_check_one)

    def _do_pull(self, repos_to_pull, repos_to_clone):
        debug_log(f"_do_pull: clone={len(repos_to_clone)} pull={len(repos_to_pull)}")
        self.status_var.set("正在下载...")
        queue = list(repos_to_clone) + [("pull", p) for p in repos_to_pull]

        def _step(idx=0):
            debug_log(f"_do_pull _step: idx={idx}/{len(queue)}")
            if idx >= len(queue):
                debug_log("_do_pull: all done")
                self.root_after(lambda: self._on_sync_done("下载完成"))
                return
            item = queue[idx]
            if isinstance(item, tuple) and item[0] == "pull":
                name = os.path.basename(item[1])
                self.status_var.set(f"拉取 {name} ({idx+1}/{len(queue)})...")
            else:
                self.status_var.set(f"克隆 {item[0]} ({idx+1}/{len(queue)})...")

            def _done(ok, out):
                debug_log(f"_do_pull _done: ok={ok} out={out[:200] if out else ''}")
                self.root_after(lambda: _step(idx + 1))

            if isinstance(item, tuple) and item[0] == "pull":
                debug_log(f"_do_pull: pulling {item[1]}")
                self.git.run_git_async(
                    item[1], ["pull", "--no-rebase"], on_done=None, post=_done
                )
            else:
                _repo_name, clone_url, repo_path = item
                debug_log(f"_do_pull: cloning {clone_url} -> {repo_path}")
                self.git.clone_async(
                    clone_url, repo_path, self.log, on_done=None, post=_done
                )

        self.root_after(_step)

    def push_repos(self):
        debug_log(f"push_repos: selected={list(self.selected_repos)}")
        if not self.selected_repos:
            messagebox.showwarning("警告", "请先选择要上传的仓库")
            return

        self._set_buttons_state(tk.DISABLED)
        self.status_var.set("正在检查仓库状态...")

        selected = list(self.selected_repos)
        queue = [p for p in selected if self.git.is_git_repo(p)]
        debug_log(f"push_repos: queue={[os.path.basename(p) for p in queue]}")
        state = {
            "queue": queue,
            "idx": 0,
            "with_remote_updates": [],
            "has_changes": False,
        }

        def _check_one():
            debug_log(f"push _check_one: idx={state['idx']}/{len(state['queue'])}")
            if state["idx"] >= len(state["queue"]):
                debug_log("push _check_one: all done, calling _ask_or_push")
                self.root_after(_ask_or_push)
                return
            path = state["queue"][state["idx"]]
            name = os.path.basename(path)
            self.status_var.set(f"检查 {name} ({state['idx']+1}/{len(state['queue'])})...")

            def _on_fetched(*_):
                debug_log(f"push _on_fetched: {name}, getting branch")
                self._run_git_async(path, ["branch", "--show-current"], _on_branch)

            def _on_branch(ok_b, branch):
                br = branch.strip() if ok_b and branch.strip() else "main"
                debug_log(f"push _on_branch: {name} branch={br} ok={ok_b}")
                self._run_git_async(path, ["log", "-1", "--format=%at"], lambda ok_l, local_time: _on_local(br, ok_l, local_time))

            def _on_local(branch, ok_l, local_time):
                debug_log(f"push _on_local: {name} branch={branch} ok={ok_l} time={local_time[:30] if local_time else ''}")
                def _on_remote(ok_r, remote_time):
                    debug_log(f"push _on_remote: {name} ok={ok_r} time={remote_time[:30] if remote_time else ''}")
                    if (ok_l and ok_r and local_time.strip()
                            and remote_time.strip()
                            and int(remote_time.strip()) > int(local_time.strip())):
                        state["with_remote_updates"].append(name)
                    debug_log(f"push _on_remote: checking status for {name}")
                    self._run_git_async(path, ["status", "--porcelain"], _on_status)

                self._run_git_async(
                    path, ["log", "-1", "--format=%at", f"origin/{branch}"], _on_remote
                )

            def _on_status(ok_s, status):
                debug_log(f"push _on_status: {name} ok={ok_s} status={status[:100] if status else ''}")
                if ok_s and status.strip():
                    state["has_changes"] = True
                state["idx"] += 1
                debug_log(f"push _on_status: advancing idx to {state['idx']}")
                self.root_after(_check_one)

            debug_log(f"push _check_one: starting fetch for {name}")
            self._run_git_async(path, ["fetch", "origin"], _on_fetched)

        def _ask_or_push():
            if state["with_remote_updates"]:
                msg = "以下仓库云端有更新，建议先下载:\n" + "\n".join(
                    state["with_remote_updates"]
                ) + "\n\n是否继续上传?"
                if not messagebox.askyesno("确认", msg):
                    self._on_sync_done("已取消")
                    return

            if state["has_changes"]:
                commit_msg = self._ask_commit_message(selected)
                if commit_msg is None:
                    self._on_sync_done("已取消")
                    return
            else:
                commit_msg = ""

            self._do_push(selected, commit_msg)

        self.root_after(_check_one)

    def _ask_commit_message(self, selected):
        default_msg = f"update {os.path.basename(selected[0])}"
        result = {"msg": None}

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

        text_var = tk.StringVar(value=default_msg)
        text_entry = ttk.Entry(dialog, textvariable=text_var, width=50)
        text_entry.pack(pady=5, padx=10)
        text_entry.select_range(0, tk.END)
        text_entry.focus()

        def on_ok():
            result["msg"] = text_var.get()
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="确定", command=on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=on_cancel).pack(side=tk.LEFT, padx=5)

        self.root.wait_window(dialog)
        return result["msg"]

    def _do_push(self, selected, commit_msg):
        debug_log(f"_do_push: selected={[os.path.basename(p) for p in selected]} commit_msg={commit_msg}")
        self.status_var.set("正在上传...")
        queue = [p for p in selected if self.git.is_git_repo(p)]

        def _step(idx=0):
            debug_log(f"_do_push _step: idx={idx}/{len(queue)}")
            if idx >= len(queue):
                debug_log("_do_push: all done")
                self.root_after(lambda: self._on_sync_done("上传完成"))
                return
            path = queue[idx]
            name = os.path.basename(path)
            self.status_var.set(f"上传 {name} ({idx+1}/{len(queue)})...")

            def _on_status(ok_s, status):
                debug_log(f"_do_push _on_status: {name} ok={ok_s} status={status[:100] if status else ''}")
                if ok_s and status.strip():
                    debug_log(f"_do_push: committing {name}")
                    self.git.commit(
                        path,
                        commit_msg if commit_msg else f"update {name}",
                        log_callback=self.log,
                    )
                debug_log(f"_do_push: pushing {name}")
                self.git.push_async(path, on_done=None, post=_done, log_callback=self.log)

            def _done(ok, out):
                debug_log(f"_do_push _done: {name} ok={ok} out={out[:200] if out else ''}")
                self.root_after(lambda: _step(idx + 1))

            self._run_git_async(path, ["status", "--porcelain"], _on_status)

        self.root_after(_step)

    def _on_sync_done(self, msg):
        self.log(msg)
        self.status_var.set("就绪")
        self._set_buttons_state(tk.NORMAL)
        self.refresh_repo_list()

    def _set_buttons_state(self, state):
        # 同步/刷新类按钮，名称固定；找不到的忽略
        for btn in (self.refresh_btn, self.pull_btn, self.push_btn):
            try:
                btn.configure(state=state)
            except tk.TclError:
                pass

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

    def rename_repo(self):
        if not self.github:
            messagebox.showwarning("警告", "请先验证Token")
            return

        selection = self.remote_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择要重命名的仓库")
            return

        item = selection[0]
        tags = self.remote_tree.item(item, "tags")
        old_name = tags[1]

        new_name = simpledialog.askstring("重命名仓库", f"请输入新名称:\n当前: {old_name}")
        if not new_name or new_name == old_name:
            return

        base_path = self.path_var.get()
        old_path = os.path.join(base_path, old_name)
        new_path = os.path.join(base_path, new_name)

        def _rename():
            if self.github.rename_repo(old_name, new_name):
                self.log(f"云端重命名成功: {old_name} -> {new_name}")
                if os.path.exists(old_path):
                    os.rename(old_path, new_path)
                    self.log(f"本地重命名成功: {old_name} -> {new_name}")
                    git = GitManager(self.config)
                    git.add_remote(new_path, self.github.get_repo_url(new_name), log_callback=self.log)
                self.root.after(0, self.fetch_remote_repos)
                self.root.after(0, self.refresh_repo_list)
            else:
                self.log(f"重命名失败: {old_name}")

        self.run_in_thread(_rename)

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
