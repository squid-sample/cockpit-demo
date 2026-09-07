# SOME/IP 学习整理

## FDBus 与 SOME/IP 的区别

### 一句话区别

- **SOME/IP**：AUTOSAR 定义的车载以太网服务通信协议和标准。
- **vsomeip**：SOME/IP 的一个开源 C++ 实现。
- **FDBus**：偏向高性能 IPC/RPC 的消息总线框架，常用于同一设备内的进程通信。

### 核心对比

| 项目 | FDBus | SOME/IP |
|---|---|---|
| 定位 | IPC/RPC 通信框架 | 车载以太网服务通信协议 |
| 标准化 | 主要遵循自身框架接口 | AUTOSAR 标准 |
| 典型场景 | 同一 SoC 内的服务、进程间通信 | ECU 之间、域控制器之间通信 |
| 传输方式 | Unix Domain Socket、TCP 等 | TCP / UDP |
| 服务发现 | 使用 FDBus 自身机制 | SOME/IP-SD |
| 通信能力 | 请求/响应、广播、连接管理 | 方法调用、事件通知、字段订阅 |
| 互操作性 | 通常要求通信双方兼容 FDBus | 不同厂商遵循标准即可互通 |
| 常见实现 | FDBus | vsomeip、其他 SOME/IP 实现 |

### 如何理解

```text
SOME/IP = 通信协议标准
vsomeip = SOME/IP 的开源实现
FDBus   = 独立的服务通信/IPC 框架
```

类比：

```text
HTTP   = 协议标准
curl   = HTTP 的一种实现/使用库
```

### 选型建议

#### 适合使用 FDBus

- 同一设备内多个进程通信
- 需要低延迟 IPC
- 需要请求/响应和广播事件
- 系统服务之间传递状态，例如电源模式、显示状态
- 不要求 AUTOSAR SOME/IP 兼容

#### 适合使用 SOME/IP/vsomeip

- ECU 或域控制器之间通过车载以太网通信
- 需要 AUTOSAR 生态兼容
- 需要标准化服务发现
- 需要跨供应商、跨平台互通
- 需要方法调用、事件订阅和字段通知

## 典型系统组合

```text
同一 SoC 内部：
PowerManagerService -- FDBus --> AudioService / DisplayService

跨 ECU 通信：
座舱域 -- SOME/IP/vsomeip --> 车身域 / 智驾域
```

两者可以同时存在，具体选择取决于通信范围、标准兼容性和系统架构要求。

---

# vsomeip 整体架构

## 源码目录与模块对应

```text
vsomeip/
├── interface/vsomeip/          # 对外公开 API（纯虚接口）
│   ├── application.hpp         # 应用入口接口
│   ├── runtime.hpp             # 对象工厂
│   ├── message.hpp / payload.hpp
│   └── constants/types/handler
└── implementation/             # 内部实现
    ├── runtime/                # application_impl、runtime_impl
    ├── routing/                # 路由核心（最核心模块）
    ├── endpoints/              # 本机 UDS + 车载以太网 TCP/UDP 端点
    ├── service_discovery/      # SOME/IP-SD 协议实现
    ├── message/                # 报文头/序列化/反序列化
    ├── configuration/          # JSON 配置加载
    ├── protocol/               # proxy↔host 内部协议
    ├── e2e_protection/         # E2E 保护
    ├── security/               # 安全策略
    └── tracing/logger/plugin/thread_manager/utility
```

## 整体架构图（含类职责）

```text
┌─────────────────────────────────────────────────────────────────┐
│ 用户业务代码                                                     │
├─────────────────────────────────────────────────────────────────┤
│ 公开 API 层 (interface/vsomeip)                                  │
│ ┌────────────┐ ┌────────────┐ ┌──────────────────────────┐      │
│ │  runtime   │→│ application│→│ message / payload        │      │
│ │ (对象工厂) │ │(应用入口)  │ │ (报文抽象)               │      │
│ └────────────┘ └─────┬──────┘ └──────────────────────────┘      │
├──────────────────────┼──────────────────────────────────────────┤
│ runtime 层           ▼                                          │
│   application_impl ── 持有 routing manager，init/start/stop，    │
│                         注册回调、offer/request/subscribe 封装   │
├─────────────────────────────────────────────────────────────────┤
│ 路由核心层 (implementation/routing)                              │
│                                                                  │
│  ★ 本进程是 routing host 时（配置 routing="host"）：             │
│  ┌───────────────────────┐                                      │
│  │ routing_manager_impl  │ 继承 routing_manager_base，          │
│  │  (总控)               │ 同时实现 4 个 host 接口：            │
│  └────┬──────┬─────┬──────┘  - boardnet_routing_host(收发外网)   │
│       │      │     │         - routing_manager_stub_host         │
│       │      │     │         - sd::service_discovery_host        │
│       │      │     │         - event_dispatcher                  │
│       │      │     │                                             │
│  ┌────▼──┐ ┌─▼───────────┐ ┌▼──────────────────┐                │
│  │routing│ │routing_mgr_ │ │sd::service_       │                │
│  │_base  │ │stub         │ │discovery_impl     │                │
│  │本机client│管理本机其他│ │SOME/IP-SD 报文、  │                │
│  │表/event│ │app 的 UDS   │ │Offer/Find/Subscribe│               │
│  │表/订阅 │ │连接(server) │ │                   │                │
│  └───────┘ └─────────────┘ └───────────────────┘                │
│                                                                  │
│  ★ 本进程是普通应用时：                                          │
│  ┌───────────────────────┐                                      │
│  │routing_manager_client │ 作为 proxy，通过 UDS 把本地请求      │
│  │ (proxy)               │ 转发给 host 进程的 stub              │
│  └───────────────────────┘                                      │
├─────────────────────────────────────────────────────────────────┤
│ 端点层 (implementation/endpoints)                                │
│ ┌──────────────────────┐  ┌────────────────────────────┐         │
│ │endpoint_manager_impl │  │本机: local_endpoint        │         │
│ │创建/管理所有端点，    │  │      UDS (Unix Domain      │         │
│ │绑定 io_context       │  │      Socket)               │         │
│ └──────────┬───────────┘  ├────────────────────────────┤         │
│            │              │外网(boardnet):             │         │
│            ▼              │  udp_client_endpoint       │         │
│ ┌──────────────────────┐  │  tcp_client_endpoint       │         │
│ │abstract_socket_factory│ │  udp_server_endpoint      │         │
│ │(asio 实现)           │  │  tcp_server_endpoint      │         │
│ └──────────────────────┘  │  tp_reassembler(TP 分片)  │         │
│                           └────────────────────────────┘         │
├─────────────────────────────────────────────────────────────────┤
│ 报文层 (message)          配置层 (configuration)                │
│  message_header_impl      configuration_impl                    │
│  serializer/deserializer  加载 JSON，提供服务/端口/SD 参数      │
│  (SOME/IP 报文格式)                                             │
├─────────────────────────────────────────────────────────────────┤
│ 支撑模块: e2e_protection(端到端保护) security(策略)             │
│          tracing(DLT) logger plugin thread_manager              │
└─────────────────────────────────────────────────────────────────┘
              │ UDS(本机) / UDP+TCP(车载以太网)
              ▼
        其他 ECU 的 vsomeip / AUTOSAR 栈
```

## 关键类职责表

| 类 | 位置 | 职责 |
|---|---|---|
| `runtime_impl` | runtime | 工厂，创建 application 对象 |
| `application_impl` | runtime | 实现 `application` 接口；init 时加载配置、创建 routing manager；持有所有用户回调 |
| `routing_manager_impl` | routing | **host 进程总控**：服务发布/订阅的最终处理者，串起 SD、stub、boardnet 端点 |
| `routing_manager_base` | routing | host 与 client 共用的基础逻辑：本机 client 表、event/eventgroup 表、remote_subscription |
| `routing_manager_client` | routing | **非 host 进程的 proxy**：把本进程请求经 UDS 发给 host 的 stub |
| `routing_manager_stub` | routing | host 侧接收本机其他 app 的 UDS 连接，转发请求给 impl |
| `sd::service_discovery_impl` | service_discovery | SOME/IP-SD：Offer/FindService/Subscribe 报文收发与解析 |
| `endpoint_manager_impl` | endpoints | 按 service/instance 创建并缓存端点对象 |
| `tcp/udp_client_endpoint_impl` | endpoints | 向远端 ECU 发送报文（client 端） |
| `tcp/udp_server_endpoint_impl` | endpoints | 接收远端 ECU 报文并分发（server 端） |
| `local_endpoint` / `local_server` | endpoints | 本机进程间 UDS 通道（app ↔ host） |
| `serializer` / `deserializer` | message | SOME/IP 头 + payload 的字节流编解码 |
| `configuration_impl` | configuration | 解析 JSON：client id、端口、SD 周期、event 配置 |

## 一次跨 ECU 请求的完整流转

```text
普通进程 App(client)
  application_impl.send()
    → routing_manager_client (proxy)
      → UDS local_endpoint
        → host 进程 routing_manager_stub
          → routing_manager_impl
            → serializer 打包 SOME/IP 头
            → udp/tcp_client_endpoint
              → 车载以太网 → 对端 ECU

对端 ECU (host 进程)
  udp/tcp_server_endpoint 收包
    → routing_manager_impl 反序列化、按 service/instance/method 分发
    → 应用注册的 message_handler 被回调
```

核心设计要点：每个 SoC 上只有一个进程承担 routing host（真实对外收发），同机其他进程都是 proxy，通过 UDS 汇聚到 host，由 host 统一做 SOME/IP-SD 和以太网收发。因此系统中通常有一个"通信进程"，业务进程只连本地。
