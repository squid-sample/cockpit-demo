# cockpit-demo

座舱域开发练习项目：QNX / Android Automotive 环境下的服务间通信与电源/日志管理。

## 目录

- `service/` — 自研服务源码
  - `PowerManagerService/` — 电源管理（FDBus 适配、ECD 通信、STR 流程）
  - `LogServer/` — 日志服务（多源日志、文件轮转、USB 导出）
  - `FaultCollector/` — 故障采集与存储
  - `liblog/` — 日志库
  - `api/` — CommonAPI / SOME-IP 接口定义（fdepl 等）
- `docs/` — 技术笔记
  - `someip_notes.md` — SOME/IP 与 vsomeip 架构梳理
  - `ModernCpp_Basic.md` / `ModernCpp_Deep.md` — C++ 11/14/17 特性整理
  - `CarService公共控件库-架构总案V6.md`
- `.trae/skills/` — AI 技能
  - `crypto-swing-recommender/` — 加密货币短线推荐（15天/30天）
  - `stock-month-trader/` — A 股月度交易计划
- `countdown_timer/` — 下班倒计时小工具

## 第三方依赖（需单独 clone，未入库）

`tools/` 目录存放第三方源码，体积较大且自带 git 仓库，已在 `.gitignore` 中排除，需在本机单独获取：

- `tools/vsomeip` — SOME/IP 开源实现
- `tools/fdbus` — 进程间通信框架
- `tools/capicxx-core-runtime` / `capicxx-someip-runtime` — CommonAPI 运行时
- `tools/protobuf` — protobuf
- `tools/commonapi-generator` — CommonAPI 代码生成器

## 构建

```bat
build_qnx_x86_64.bat
```
