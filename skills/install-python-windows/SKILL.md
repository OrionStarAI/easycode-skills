---
name: install-python-windows
description: >
  当用户在 Windows 上没有安装 Python 时，引导其从官网下载最新稳定版安装包，勾选 Add Python to PATH 完成安装，并验证环境变量已生效。
  触发词：安装 Python、没有 Python、python 不是内部命令、找不到 python。
---

# install-python-windows

帮助 Windows 新手完整安装 Python 并将其加入系统 PATH。

---

## 第一步：检查当前是否已安装 Python

在终端（CMD 或 PowerShell）运行：

```cmd
python --version
```

- 若输出版本号，则已安装，跳到第四步验证 PATH 是否正常。
- 若提示不是内部命令或跳转到 Microsoft Store，继续第二步。

---
## 第二步：下载 Python 安装包

1. 打开浏览器，访问 Python 官网下载页：
   https://www.python.org/downloads/windows/
2. 页面顶部点击 Download Python 3.x.x 下载 .exe 安装包。
   - 64 位系统下载 Windows installer (64-bit)
   - 32 位系统下载 Windows installer (32-bit)

> 提示：如不确定系统位数，在此电脑右键属性查看系统类型。

---
## 第三步：安装 Python （关键：必须勾选 Add to PATH）

1. 双击下载好的 .exe 文件，启动安装向导。
2. 安装向导第一页底部，务必勾选：
   - Add Python x.x to PATH。
   > WARNING: 这一步最重要！若忘记勾选，安装后需手动添加环境变量。
3. 点击 Install Now（推荐普通用户）。
4. 等待安装完成，看到 Setup was successful 界面后点击 Close。

---
## 第四步：验证安装成功 & PATH 已生效

必须打开一个新的终端窗口，然后运行：

```cmd
python --version
```

- 成功：输出 Python 3.x.x，安装完成。
- 失败：继续第五步手动修复。

同时验证 pip：

```cmd
pip --version
```

---
## 第五步（仅在 PATH 未生效时执行）：手动添加 Python 到系统 PATH

1. 按 Win+S 搜索「环境变量」，点击「编辑系统环境变量」。
2. 点击右下角的「环境变量」按鈕。
3. 在「系统变量」区域找到 Path，双击编辑。
4. 点击「新建」，加入两条路径（将 Python3x 替换为实际目录）：
   C:\\Users\\<用户名>\\AppData\\Local\\Programs\\Python\\Python3x\\
   C:\\Users\\<用户名>\\AppData\\Local\\Programs\\Python\\Python3x\\Scripts\\
5. 点击「确定」保存，关闭所有窗口。
6. 重新打开终端，再次执行 python --version 验证。

> 提示：实际安装路径可在文件管理器里搜索 python.exe 定位。

---
## 完成判定标准

满足以下条件视为安装成功：

- 新终端中 python --version 输出 Python 3.x.x（x >= 10）
- pip --version 正常输出版本信息
- 无需指定完整路径即可运行 python

---

## 注意事项

- Windows 11/10 的应用执行别名可能让 python 命令跳转到 Microsoft Store，需在设置 -> 应用 -> 高级应用设置 -> 应用执行别名中关闭 Python 相关条目。
- 安装时选 Install Now 会安装到用户目录，无需管理员权限。
- 企业或学校电脑可能有权限限制，遇到权限错误请联系 IT。
