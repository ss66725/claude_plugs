# Python 仓库

## 测试

- 每个程序的 `tests/<程序名>.txt` 写用例，格式和 C 相同。
- 运行器用 `PYTHONIOENCODING=utf-8` 和 `PYTHONHASHSEED=0` 运行程序，保证输出稳定。
- 运行 `python run_tests.py`（全部）或 `python run_tests.py 261108`（某一天）。

不适合自动测试的 Python 程序：

- 使用 `random` 的程序：输出每次都不同。
- 使用 `turtle`、`matplotlib`、`wordcloud` 等图形库的程序：需要图形窗口或字体。
- 使用 `requests` 联网的爬虫：结果依赖网站内容，并且可能需要 Cookie。
- 输出里包含对象内存地址的程序（例如 `print(obj)` 没有定义 `__str__`），每次运行都不同。

在 README 里说明没有测试的原因。

## .gitignore

```
__pycache__/
*.pyc
.venv/
venv/
tempCodeRunnerFile.py
```

## 文件名

- 检查是否有 `.py.py` 这种重复后缀，改成 `.py`。
- 文件名避免 `%`、空格等特殊字符。

## 隐私

- 爬虫脚本：Cookie、token、账号密码不能提交。占位符（如 `YOUR_COOKIE_HERE`）可以。
- 抓取到的数据文件（如 `.xlsx`）：先检查是否包含个人信息，只有表头可以提交。
- 公开仓库前，确认抓取的数据和网站的使用条款是否允许。

## 依赖

如果项目用到第三方库，可以加 `requirements.txt`，比如 `requests`、`beautifulsoup4`、`pandas`。
