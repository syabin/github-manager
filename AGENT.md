# Agent Guide — GitHub 仓库管理工具

## 项目简介

批量管理 GitHub 仓库的 Python 桌面工具（Tkinter GUI），支持克隆、上传、更新、重命名、修改可见性等操作。

## 技术栈

- Python 3 + Tkinter（GUI）
- requests 库（GitHub API）
- subprocess 调用 Git 命令行
- 单文件部署：`github_manager.pyw`

## 文件结构

```
github-manager/
├── github_manager.pyw  # 主程序（全部代码）
├── requirements.txt    # Python 依赖（requests>=2.28.0）
├── .env               # 配置文件（token、用户名、仓库路径）
├── .gitignore
├── update.bat         # Windows 更新脚本
├── update.py          # 更新逻辑
└── README.md          # 项目文档
```

## 核心架构

### 类结构

| 类 | 职责 |
|----|------|
| `ConfigManager` | 管理 `.env` 配置文件的读写 |
| `GitManager` | 封装 git 命令（clone/pull/push/status/init） |
| `GitHubAPI` | 封装 GitHub REST API（创建仓库、修改可见性、重命名） |
| `GitHubManagerApp` | Tkinter 主界面和业务逻辑 |

### 关键方法

- `GitManager.run_git(path, args)` — 执行 git 命令，超时300秒
- `GitManager.clone_async()` / `push_async()` — 异步操作不阻塞 UI
- `GitHubManagerApp.pull_repos()` — 先检查状态再批量拉取
- `GitHubManagerApp.push_repos()` — 自动 commit + push

## 配置

`.env` 文件格式：
```
github_token=ghp_xxx
github_username=xxx
repos_path=D:\repos
default_branch=main
```

## 修改指南

- **Git 路径**：默认 `C:\Program Files\Git\cmd\git.exe`，在 `GitManager.run_git()` 中修改
- **超时设置**：clone 600秒，其他 300秒，在对应方法中调整
- **UI 布局**：在 `setup_ui()` 方法中，使用 ttk 组件
- **新增 GitHub API 功能**：在 `GitHubAPI` 类中添加方法
