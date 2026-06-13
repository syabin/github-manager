# GitHub 仓库管理工具

批量管理 GitHub 仓库的桌面工具，支持克隆、上传、更新操作。

## 功能

- 获取云端仓库列表
- 新建仓库（自动克隆到本地）
- 更新（Pull）- 检查本地vs云端谁更新
- 上传（Push）- 自动提交并推送
- 初始化Git

## 安装

```bash
pip install requests
```

## 运行

```bash
python github_manager.py
```

## 配置

首次运行需填写：
- GitHub 用户名
- Personal Access Token
- 仓库存放目录

配置自动保存到 `.env` 文件。
