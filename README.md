# Note Migrator

小米笔记 → Vivo 原子笔记 迁移工具

## 快速开始（推荐）

一键启动图形界面：

```bash
cd note-migrator
pip install -e .
playwright install chromium
python gui.py
```

然后在界面中：
1. **小米笔记** → 点击「连接小米账号」→ 浏览器中登录 → 自动捕获 cookies
2. **小米笔记** → 点击「导出全部笔记」→ 导出所有笔记到本地
3. **Vivo原子笔记** → 点击「登录 Vivo 账号」→ 浏览器中登录 → 自动保存 session
4. **Vivo原子笔记** → 点击「导入全部笔记」→ 自动逐条导入

也可用 `note-migrator gui` 启动。

---

## 命令行方式

### 1. 安装

```bash
cd note-migrator
pip install -e .
playwright install chromium
```

### 2. 配置

```bash
note-migrator config init
```

编辑 `config.yaml`，填入从小米笔记浏览器中提取的 cookies：

1. 在 Chrome 中登录 [i.mi.com](https://i.mi.com)
2. 按 F12 → Application → Cookies → `i.mi.com`
3. 复制 `serviceToken`, `userId`, `passToken`

### 3. 导出小米笔记

```bash
# 列出所有笔记
note-migrator export list

# 导出全部笔记
note-migrator export all
```

导出到 `output/export/notes/*.md`，图片在 `output/export/images/`。

### 4. 导入到 Vivo

```bash
note-migrator import all
```

Playwright 会打开浏览器窗口，你扫码/登录 Vivo 后回车继续，随后自动逐条导入。

### 5. 验证

```bash
note-migrator verify export
note-migrator import status
```

## 命令参考

| 命令 | 说明 |
|------|------|
| `gui` | 启动图形界面 |
| `config init` | 创建配置文件 |
| `config show` | 查看当前配置 |
| `config validate` | 验证认证信息 |
| `export list` | 列出小米笔记 |
| `export all` | 导出所有笔记 |
| `import all` | 导入所有笔记到 Vivo |
| `import status` | 查看导入状态 |
| `verify export` | 校验导出文件完整性 |
