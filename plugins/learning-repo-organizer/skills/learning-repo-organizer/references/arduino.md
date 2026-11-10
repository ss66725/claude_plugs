# Arduino 仓库

## 为什么不能用 run_tests.py

Arduino 程序依赖硬件（引脚、传感器、串口）。所以不做自动期望输出测试，改为在 README 里写清楚每个 sketch 的行为。

如果已安装 `arduino-cli`，可以编译检查语法：

```bash
arduino-cli compile --fqbn <开发板型号> <sketch文件夹>
```

开发板型号（`--fqbn`）需要问用户，例如 `arduino:avr:uno`。

## README 怎么写

每个 sketch 写清楚：

- 功能：程序做什么，结果是什么（例如“温度超过 30°C 时红灯闪烁”）。
- 硬件：用到的引脚和元件，例如“DS18B20 温度传感器（8 号引脚）”。
- 所需库：列出库名，并说明安装方法（库管理器或放进 libraries 文件夹）。

## 第三方库和驱动

- 用户保留在本地的第三方库（如 `libraries/`）和厂商驱动，不要删除。
- 这些文件不上传到仓库，README 里写明需要安装哪些库即可。
- 如果库的许可证文件缺失，在 README 里提醒。

## .gitignore

```
build/
*.hex
*.elf
*.bin
*.map
*.o
*.d
```

## 隐私（重点）

Arduino 代码里经常硬编码 WiFi 名称和密码、MQTT 账号、API 密钥。上传前必须搜索：

```bash
grep -n -i -E "ssid|password|passwd|wifi|token|secret|api[_-]?key" */*.ino
```

发现真实凭据时停止，告诉用户，改成占位符（如 `"YOUR_WIFI_SSID"`）后再提交。

## 文件夹命名

sketch 文件夹如果用 `sketch_nov3a` 这种命名，先问用户是否改为 YYMMDD 格式。用户要求保持原名时，就不改。
