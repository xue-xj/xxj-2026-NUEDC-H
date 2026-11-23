# 外部电机依赖

公开仓库保留应用层与电机接口的调用，但不附带尚未确认再分发许可的商家示例及电机集成文件。
因此 MCU 目录不是可直接构建的完整发行包，需先补齐依赖。

## 所需文件

将以下文件放到 `mspm0/`：

```text
Emm_V5.c / Emm_V5.h
usart.c / usart.h
fifo.c / fifo.h
delay.c / delay.h
gimbal.c / gimbal.h
```

前四组为张大头 Emm V5 驱动器示例相关文件。请通过商家官方支持渠道获取适用于 MSPM0G3507 的示例，并遵守附带使用条件。
示例文件署名渠道：https://zhangdatou.taobao.com ，https://blog.csdn.net/zhangdatou666 。
gimbal.c/.h 为本工程使用的电机集成依赖，不保证商家通用示例包含或可直接替代；应使用匹配本工程 API 的合法副本。
所有文件的接口、引脚、驱动器版本及遥测结构都需核对，不能假定任意下载版本可以直接构建。

补齐依赖后，运行 `python tools/check_source_integrity.py` 检查参考文件版本，再执行 CCS Clean/Rebuild。
不同合法版本可能导致哈希不一致，需审查接口与行为，而不是绕过检查直接认定兼容。
主机 Python 测试无需这些外部文件；真实运动控制仍需完整驱动、SDK 与硬件。

本地完整工程中的依赖并未删除；公开仓库不提供这些文件，也不授予其再分发权利。
