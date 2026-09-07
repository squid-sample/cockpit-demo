# 现代 C++ 深度笔记（原理+底层）

> **文档定位**：C++11/14/17 深度原理 + 编译器行为 + UB 与性能剖析
> **适用对象**：已读完 `ModernCpp_Basic.md`，想理解"为什么"的开发者
> **配套项目**：`d:\Android\Project\20260813\demo\service\`
> **学习目标**：理解编译器行为、ABI、内存模型，避免 UB、写出高性能代码

---

## 0. 文档说明

### 0.1 本文档与入门版的关系

| 维度 | Basic 版 | Deep 版（本文） |
|:---|:---|:---|
| 定位 | 用法 + 实例 | 原理 + 底层 |
| 风格 | "怎么写" | "为什么这么写" |
| 重点 | API 速查 + 项目对照 | 编译器行为 + ABI + 性能 + UB |
| 字数 | 约 1.5 万 | 约 3 万 |
| 学习周期 | 1 周 | 2-3 周 |

### 0.2 阅读建议

1. **先看 Basic 版**再读本版
2. 每章末尾有「**深度思考题**」——必做
3. 用 Compiler Explorer（https://godbolt.org/）验证汇编输出
4. 用 `-fsanitize=address,undefined` 抓 UB

### 0.3 标准与编译器版本对应

| 标准 | GCC 起始版本 | Clang 起始版本 | MSVC 起始版本 |
|:---:|:---:|:---:|:---:|
| C++11 | 4.7 | 3.1 | 2015 |
| C++14 | 5.1 | 3.5 | 2015 Update 2 |
| C++17 | 7.0 | 5.0 | 2017 15.7 |
| C++20 | 10.0 | 10.0 | 2019 16.3 |

---

## 1. auto 与类型推导：模板推导规则

### 1.1 auto 的本质

`auto` **不是新类型**，而是**让编译器用模板参数推导规则推导类型**。

```cpp
auto x = 42;
// 等价于：
template<typename T> void f(T x); 
f(42);   // T 推导为 int
```

### 1.2 模板参数推导规则

这是 C++ 最复杂的规则之一。核心三种情形：

```cpp
template<typename T> void f(T x);          // 情形1：按值
template<typename T> void f(T& x);          // 情形2：按引用
template<typename T> void f(T&& x);         // 情形3：转发引用
```

对 `auto` 来说：
```cpp
auto x = expr;           // 等价情形1
auto& x = expr;           // 等价情形2
auto&& x = expr;          // 等价情形3（转发引用）
```

### 1.3 array-to-pointer 和 function-to-pointer 衰变

```cpp
int arr[10];
auto a = arr;             // int* （数组衰变为指针）
auto& b = arr;             // int(&)[10] （引用保留数组类型）

void func();
auto f = func;            // void(*)() （函数衰变为函数指针）
auto& g = func;           // void(&)()  （保留函数引用）
```

### 1.4 const 和引用的剥离规则

**按值传递（auto x = ...）时：忽略 const 和引用**：

```cpp
int x = 42;
const int& ref = x;

auto a = ref;   // auto 推导为 int （丢弃 const 和 &）
a = 100;        // 合法，a 是副本
```

**按引用传递（auto& x = ...）时：保留 const**：

```cpp
auto& b = ref;   // auto 推导为 const int，b 是 const int&
b = 100;          // 编译错误
```

### 1.5 decltype 的不同

`decltype` 与 `auto` 的推导规则**不同**！

```cpp
int x = 42;
const int& ref = x;

auto a = ref;          // auto → int（丢 const 和 &）
decltype(ref) b = ref; // b 的类型是 const int& （保留完整类型）
```

**`decltype((x))` 与 `decltype(x)` 不同**：

```cpp
int x = 42;
decltype(x) a;       // int（裸变量名 → 直接类型）
decltype((x)) b = x; // int& （加括号 → 引用类型）
```

### 1.6 auto&& 的转发引用陷阱

```cpp
auto&& a = 42;        // 右值引用 int&&（绑定到临时值）
int x = 42;
auto&& b = x;         // 左值引用 int&（绑定到左值）

// 注意：模板里的 T&& 是转发引用，但 typedef/using 里的 && 是右值引用
template<typename T> void f(T&& x);   // 转发引用
using R = int&&; R&& r = ...;         // 右值引用（int&& && 折叠为 int&&）
```

### 1.7 项目实例深度分析

[LogExporter.cpp:36-37](../service/LogServer/LogExporter.cpp#L36-L37)：

```cpp
auto now = std::chrono::system_clock::now();
auto timeT = std::chrono::system_clock::to_time_t(now);
```

**为什么用 auto**：
- `system_clock::now()` 返回 `std::chrono::time_point<std::chrono::system_clock, std::chrono::duration<rep, period>>`，类型名 80+ 字符
- 写出来反而**影响可读性**
- `auto` 在这里让代码意图（取当前时间）更突出

### 1.8 ABI 视角

`auto` 是**编译期推导**，运行期零成本——编译后和手写完整类型完全一致。

```cpp
auto x = 42;        // 汇编：mov dword [rbp-4], 42
int x = 42;          // 汇编：mov dword [rbp-4], 42
```

完全相同。

### 1.9 深度思考题

**题**：解释以下代码每行 `auto` 的推导结果：

```cpp
int x = 1;
const int cx = x;
const int& rx = x;

auto a = x;           // ?
auto b = cx;          // ?
auto c = rx;          // ?
auto& d = cx;         // ?
auto&& e = x;          // ?
auto&& f = cx;         // ?
auto&& g = 42;         // ?
decltype(auto) h = x;  // ?
decltype(auto) i = rx; // ?
```

参考 cppreference `decltype` 规则推导。

---

## 2. 智能指针：控制块、内存布局与性能

### 2.1 控制块（Control Block）的本质

`shared_ptr` 内部不止一个指针，而是**对象指针 + 控制块指针**：

```cpp
// 简化的 shared_ptr 布局
template<typename T>
class shared_ptr {
    T* ptr_;                      // 指向实际对象
    control_block* control_;      // 指向控制块
};

struct control_block {
    atomic<long> strong_count_;  // 强引用计数
    atomic<long> weak_count_;    // 弱引用计数
    destructor_type deleter_;    // 自定义删除器
    allocator_type alloc_;        // 分配器（可选）
};
```

### 2.2 make_shared 的内存优化

**手写 `shared_ptr<T>(new T)`：两次分配**

```
堆：[T 对象]   [control_block]
      ↑           ↑
      │           │
ptr__│     control_│
```

**`make_shared<T>()`：一次分配（对象 + 控制块合并）**

```
堆：[T 对象 | control_block]
      ↑          ↑
      │          │
   ptr_     control_ (内部计算偏移)
```

**优势**：
1. 一次 malloc，减少内存碎片
2. 缓存局部性好（对象和控制块挨着）
3. 异常安全（`foo(shared_ptr<T>(new T), bar())` 中 `bar()` 异常会泄漏）

### 2.3 make_shared 的隐藏陷阱

```cpp
auto p = std::make_shared<HugeObject>();
// 1. 内存立即释放延迟：weak_ptr 还活着时，对象内存不会释放！
std::weak_ptr<HugeObject> w = p;
p.reset();   // 对象析构，但内存不释放
// HugeObject 已析构，但 sizeof(HugeObject) + sizeof(control_block) 的内存仍占着
w.reset();   // 现在才真正释放
```

**原理**：`make_shared` 把对象和控制块放一块儿，**控制块活着时整块内存不能 free**。如果有 weak_ptr 长期持有，对象内存延迟释放。

### 2.4 unique_ptr 的零成本抽象

`unique_ptr` 设计目标：**和手写 new/delete 性能完全一致**。

```cpp
std::unique_ptr<int> p(new int(42));
// 编译后和裸指针一样（汇编里没有引用计数）
```

**原因**：
1. 没有 control_block（独占，不需要计数）
2. 析构内联 → 编译期确定调用 delete
3. 移动语义通过 move 实现，运行期零开销

### 2.5 自定义 deleter 的影响

```cpp
// 函数指针 deleter：unique_ptr 大小从 8 字节变 16 字节
std::unique_ptr<FILE, decltype(&fclose)> fp(fopen("a.txt", "r"), fclose);

// lambda deleter（无捕获）：unique_ptr 大小仍 8 字节
std::unique_ptr<FILE, decltype([](FILE* f){ fclose(f); })> fp(fopen(...));
```

**原理**：无捕获 lambda 是空类，EBO（Empty Base Optimization）让它零大小；函数指针必须存值。

### 2.6 循环引用的内存泄漏

```cpp
struct Node {
    std::shared_ptr<Node> next;
    std::shared_ptr<Node> prev;   // 循环引用！
};

auto a = std::make_shared<Node>();
auto b = std::make_shared<Node>();
a->next = b;   // b 引用计数 = 2
b->prev = a;   // a 引用计数 = 2

// 离开作用域：a 引用计数降到 1（b 还持着），b 引用计数降到 1（a 还持着）
// 结果：两个都不会释放 → 内存泄漏！
```

**修复**：把其中一个改成 `weak_ptr`：

```cpp
struct Node {
    std::shared_ptr<Node> next;
    std::weak_ptr<Node> prev;   // 弱引用，不增加计数
};
```

### 2.7 项目实例深度分析

[PowerManager.cpp:19](../service/PowerManagerService/src/PowerManager.cpp#L19)：

```cpp
mAdapter = std::make_unique<FdbusPowerAdapter>("com.cockpit.power.qnx.service",
                                                 POWER_FDBUS_SERVER_TCP_URL);
```

**为什么用 unique_ptr 而非 shared_ptr**：
1. **所有权语义**：`mAdapter` 是 PowerManager 的**专属成员**，生命周期与 PowerManager 绑定
2. **性能**：避免引用计数的原子操作开销
3. **意图清晰**：unique_ptr 表达"独占"，让代码读者立即理解设计
4. **可移动**：未来需要转移所有权时可用 `std::move`

[HelloWorldService.cpp:41](../service/HelloWorldServer/HelloWorldService.cpp#L41)：

```cpp
auto service = std::make_shared<HelloWorldServerImpl>();
runtime->registerService("local", "demo.HelloWorld", service);   // runtime 内部拷贝
std::thread t(simulatePowerStateChanges, service);               // 线程拷贝
```

**为什么用 shared_ptr**：
1. service 被**两个独立生命周期**的对象持有（runtime + 线程）
2. runtime 在 main 退出时析构，线程在结束时析构，时序不确定
3. shared_ptr 引用计数保证最后一个持有者析构时才释放 service

### 2.8 enable_shared_from_this 模式

```cpp
class Widget : public std::enable_shared_from_this<Widget> {
public:
    std::shared_ptr<Widget> getPtr() {
        return shared_from_this();   // 安全地从 this 拿 shared_ptr
    }
};

// 错误做法：return shared_ptr<Widget>(this); 会导致双重释放
```

**原理**：`enable_shared_from_this` 内部存了一个 `weak_ptr<Widget>`，被 `make_shared` 时填入，调用 `shared_from_this()` 时从 weak_ptr 升级为 shared_ptr，**共享同一控制块**。

### 2.9 性能对比表

| 操作 | unique_ptr | shared_ptr |
|:---|:---|:---|
| 构造 | 1 次 new（仅对象） | 1 次 new（对象+控制块，make_shared） |
| 拷贝 | 不支持 | 1 次原子 increment（lock 指令） |
| 移动 | 几个指针赋值 | 几个指针赋值 + 1 次原子 decrement |
| 析构 | 1 次 delete | 1 次 atomic decrement + 可能的 delete |
| 大小（64 位） | 8 字节（默认 deleter） | 16 字节 |

### 2.10 深度思考题

**题 1**：以下代码为何危险？如何修复？
```cpp
class Widget {
public:
    std::shared_ptr<Widget> getSelf() {
        return std::shared_ptr<Widget>(this);   // 危险！
    }
};
```

**题 2**：为什么 `std::make_shared` 比手写 `new` 更"异常安全"？
```cpp
func(std::shared_ptr<Widget>(new Widget), mayThrow());
```

---

## 3. 右值引用、移动语义与完美转发

### 3.1 值类别（Value Category）

C++11 重新定义了表达式类别：

| 类别 | 全称 | 例子 |
|:---|:---|:---|
| **lvalue** | 左值（有名字、可取地址） | `int x; x` |
| **prvalue** | 纯右值（字面量、临时值） | `42`, `x+1`, `T()` |
| **xvalue** | 将亡值（即将被移动） | `std::move(x)`, `std::forward<T>(x)` |
| rvalue | prvalue ∪ xvalue | — |
| glvalue | lvalue ∪ xvalue | — |

### 3.2 移动语义的本质

**移动 ≠ 复制 + 删除原对象**，而是**资源所有权转移**：

```cpp
// 拷贝 Buffer：分配新内存 + memcpy
Buffer b1(1000);
Buffer b2 = b1;   // 拷贝：new + memcpy，慢

// 移动 Buffer：偷走内部指针，原对象置空
Buffer b3 = std::move(b1);   // 移动：b3.data_ = b1.data_; b1.data_ = nullptr;
                             // 不分配内存，O(1) 操作
```

### 3.3 移动构造的正确实现

```cpp
class Buffer {
    int* data_;
    size_t size_;
public:
    // 移动构造（要点：noexcept + 置空源对象）
    Buffer(Buffer&& other) noexcept 
        : data_(other.data_), size_(other.size_) {
        other.data_ = nullptr;   // ← 必须置空，否则析构双重释放
        other.size_ = 0;
    }
    
    // 移动赋值
    Buffer& operator=(Buffer&& other) noexcept {
        if (this != &other) {
            delete[] data_;             // 释放自己原来的资源
            data_ = other.data_;
            size_ = other.size_;
            other.data_ = nullptr;
            other.size_ = 0;
        }
        return *this;
    }
};
```

### 3.4 noexcept 的重要性

**STL 容器在异常安全下退化**：如果元素的移动构造不是 `noexcept`，`std::vector` 扩容时会用拷贝而非移动，性能下降。

```cpp
// 不加 noexcept：vector 扩容时拷贝（怕移动抛异常后状态丢失）
Buffer(Buffer&& other);   

// 加 noexcept：vector 扩容时移动（高效）
Buffer(Buffer&& other) noexcept;   
```

### 3.5 std::move 的真相

`std::move` **不做任何运行期操作**，只是**编译期类型转换**：

```cpp
template<typename T>
constexpr typename std::remove_reference<T>::type&& 
std::move(T&& t) noexcept {
    return static_cast<typename std::remove_reference<T>::type&&>(t);
}
```

作用：把任意类型转成**右值引用**，让重载解析选择移动构造/赋值。

### 3.6 完美转发与引用折叠

```cpp
template<typename T>
void wrapper(T&& arg) {                    // T&& 是转发引用
    target(std::forward<T>(arg));         // 完美转发：保留左值/右值属性
}
```

**引用折叠规则**（4 条规则）：

```
typedef T& &  → T&      （左值 + 左值 = 左值）
typedef T& && → T&      （左值 + 右值 = 左值）
typedef T&& & → T&      （右值 + 左值 = 左值）
typedef T&& && → T&&   （右值 + 右值 = 右值）
```

**规则**：**只有右值+右值才是右值，其他全是左值**。

### 3.7 std::forward 的实现

```cpp
template<typename T>
constexpr T&& std::forward(typename std::remove_reference<T>::type& t) noexcept {
    return static_cast<T&&>(t);
}
```

作用：根据模板参数 `T` 的推导结果，把 `arg` 转回它原本的值类别。

### 3.8 转发引用 vs 右值引用

```cpp
void foo(int&& x);          // 右值引用：只接右值

template<typename T>
void bar(T&& x);            // 转发引用：可接左值或右值（取决于 T 推导）

int x = 10;
foo(x);                     // ❌ 错误，x 是左值
foo(std::move(x));          // ✅ 显式转成右值

bar(x);                     // ✅ T 推导为 int&，x 折叠后是 int&（左值引用）
bar(10);                    // ✅ T 推导为 int，x 是 int&&（右值引用）
```

### 3.9 项目实例分析

[PowerManager.cpp:46-47](../service/PowerManagerService/src/PowerManager.cpp#L46-L47)：

```cpp
mEcdClient->setPowerModeHandler(
    std::bind(&PowerManager::handlePowerMode, this, std::placeholders::_1));
```

**为什么 `std::bind` 结果可以隐式转成 `std::function`**：

`std::bind` 返回一个未命名的函数对象类型（`_Bind<...>`），是**右值**（将亡值），通过移动构造到 `std::function` 内部，避免拷贝。

### 3.10 RVO（返回值优化）与 move 的交互

```cpp
Buffer makeBuffer() {
    Buffer local(1000);
    return local;   // NRVO：编译器直接在调用者的栈上构造，零拷贝
}

Buffer b = makeBuffer();   // 可能零拷贝（NRVO）
```

**陷阱**：加 `std::move` 反而破坏 RVO：

```cpp
return std::move(local);   // ❌ 禁用 NRVO，强制调用移动构造
```

**规则**：返回局部变量时**直接 return，不要加 `std::move`**，编译器会自动选择最优。

### 3.11 深度思考题

**题 1**：以下代码调用了几次构造？几次拷贝？几次移动？
```cpp
std::vector<std::string> v;
v.push_back(std::string("hello"));
v.push_back(std::string("world"));
```

**题 2**：解释为什么 `std::move` 加在 return 语句里反而更慢
```cpp
std::vector<int> makeVec() {
    std::vector<int> v = {1, 2, 3};
    return std::move(v);   // ❌ 为什么不好？
}
```

---

## 4. Lambda：闭包对象、捕获原理与性能

### 4.1 Lambda 的本质：编译器生成的闭包类

每个 lambda 在编译期生成一个**唯一的类**，operator() 是它的成员函数：

```cpp
int x = 10;
auto f = [x](int y) { return x + y; };
// 等价于：
struct __lambda_1 {
    int x;                              // 捕获的变量成为成员
    int operator()(int y) const {        // operator() 是 const 的
        return x + y;
    }
} f = {10};                             // 用捕获列表初始化成员
```

### 4.2 捕获的本质

| 捕获方式 | 等价成员类型 |
|:---|:---|
| `[x]` | `int x;` （按值，const 成员） |
| `[&x]` | `int& x;` （按引用，引用成员） |
| `[=]` | 所有使用到的外部变量按值捕获 |
| `[&]` | 所有使用到的外部变量按引用捕获 |
| `[this]` | `类名* this;`（捕获 this 指针） |

### 4.3 无捕获 lambda 可转函数指针

```cpp
int (*fp)(int) = [](int x) { return x * 2; };   // ✅
int (*fp2)(int) = [x](int y) { return x + y; }; // ❌ 有捕获不能转
```

**原理**：无捕获 lambda 的 operator() 是非成员函数等价物，可以转换成普通函数指针。

### 4.4 泛型 Lambda（C++14）

```cpp
auto f = [](auto x, auto y) { return x + y; };   // 等价于模板 operator()
// 等价于：
struct __lambda {
    template<typename T, typename U>
    auto operator()(T x, U y) const { return x + y; }
};
```

### 4.5 std::function 的开销

`std::function` 是**类型擦除**的容器，可以装任何可调用对象，但有代价：

| 开销 | 说明 |
|:---|:---|
| 内存 | 至少 32 字节（GCC 实现），超大对象会堆分配 |
| 调用 | 间接跳转（virtual 或函数指针），无法内联 |
| 异常 | 可能抛 `bad_function_call` |

**对比 lambda 直接调用**：

```cpp
auto f = [](int x) { return x * 2; };
f(10);   // ✅ 编译器可内联，零开销

std::function<int(int)> g = f;
g(10);   // ❌ 间接调用，无法内联，慢 3-5 倍
```

**性能敏感场景**：用 `auto` 而非 `std::function`。

### 4.6 项目实例分析

[PowerManager.cpp:59](../service/PowerManagerService/src/PowerManager.cpp#L59)：

```cpp
mRunCond.wait(lock, [this]{ return !mRunning; });
```

**为什么用 lambda 而非函数指针**：
1. 需要访问 `this->mRunning`，函数指针做不到
2. `std::condition_variable::wait` 接受任何可调用对象，但 lambda + `auto` 模板版本最优
3. 编译器内联 lambda，零开销

### 4.7 悬空引用陷阱

```cpp
std::function<int()> makeCounter() {
    int x = 0;
    return [&x]() { return ++x; };   // ❌ x 离开作用域销毁，悬空！
}

auto bad = makeCounter();
bad();   // UB：访问已销毁的 x
```

**修复**：按值捕获
```cpp
return [x]() mutable { return ++x; };   // ✅ x 是副本
```

### 4.8 [this] 的悬空陷阱

```cpp
class Widget {
public:
    std::function<void()> getCallback() {
        return [this]() { doSomething(); };   // this 可能悬空
    }
};

auto w = std::make_unique<Widget>();
auto cb = w->getCallback();
w.reset();   // Widget 销毁
cb();        // ❌ UB：访问已销毁的 this
```

**修复**：用 `shared_from_this` 或拷贝需要的成员。

### 4.9 深度思考题

**题 1**：以下代码哪里出错？
```cpp
std::vector<std::function<void()>> callbacks;

for (int i = 0; i < 3; ++i) {
    callbacks.push_back([&i]() { std::cout << i; });
}
for (auto& cb : callbacks) cb();
```

**题 2**：实现一个 mutable lambda，每次调用计数 +1
```cpp
auto counter = ???;
counter();   // 1
counter();   // 2
```

---

## 5. 并发：内存模型、fences 与 false sharing

### 5.1 C++11 内存模型

C++11 引入标准化的**内存模型**，定义多线程下何时可见对方的修改。

**默认顺序**：`memory_order_seq_cst`（顺序一致），最严格但最慢。

```cpp
std::atomic<int> x{0};
x.store(1);                       // 默认 seq_cst
int v = x.load();                 // 默认 seq_cst
```

### 5.2 6 种内存序

| 序 | 全称 | 含义 |
|:---|:---|:---|
| `seq_cst` | 顺序一致 | 全局总序，最强保证 |
| `acq_rel` | 获取-释放 | 当前操作 acq + rel |
| `release` | 释放 | 之前的写对其他 acq 可见 |
| `acquire` | 获取 | 看到其他 rel 之前的写 |
| `consume` | 依赖 | 弱化的 acquire（不推荐） |
| `relaxed` | 宽松 | 无同步，仅原子 |

**何时用 relaxed**：计数器、统计值，不参与同步
```cpp
std::atomic<int> count{0};
count.fetch_add(1, std::memory_order_relaxed);   // 不需要同步
```

### 5.3 happens-before 关系

C++ 内存模型用 **happens-before** 定义操作顺序：

```
A happens-before B
└─ B 一定看到 A 的修改
```

**关键关系**：
1. 同线程内：程序顺序（sequenced-before）
2. 跨线程：release-acquire 对（release 后的写对 acquire 可见）
3. 同步原语：mutex.lock/unlock、thread::join、condition_variable 等

### 5.4 condition_variable 的实现原理

```cpp
std::condition_variable cv;
std::mutex m;

// 等待方
std::unique_lock<std::mutex> lk(m);
cv.wait(lk, []{ return ready; });
// 内部：
// 1. while (!pred()) {
// 2.     m.unlock();              // 释放锁，让通知方能进入临界区
// 3.     futex_wait(...);          // 内核态阻塞
// 4.     m.lock();                 // 唤醒后重新加锁
// 5. }
```

### 5.5 虚假唤醒（Spurious Wakeup）

操作系统可能在没有 notify 的情况下唤醒 wait。**必须用谓词 wait**：

```cpp
cv.wait(lk, []{ return ready; });   // 内部循环检查谓词

// 等价于：
while (!ready) {
    cv.wait(lk);   // 旧式 wait，可能被虚假唤醒
}
```

### 5.6 死锁的必要条件与避免

** Coffman 4 条件**：
1. 互斥
2. 持有并等待
3. 不可剥夺
4. 循环等待

**避免死锁的实践**：
1. **统一锁序**：按指针地址排序加锁
2. **`std::lock(m1, m2)`**：一次性获取多个锁，避免死锁
3. **`std::scoped_lock`（C++17）**：RAII 包装多个锁
4. **避免持有锁时调用回调**：回调可能反过来加锁

### 5.7 项目实例深度分析

[PowerManager.cpp:57-67](../service/PowerManagerService/src/PowerManager.cpp#L57-L67)：

```cpp
void PowerManager::run() {
    std::unique_lock<std::mutex> lock(mRunMutex);
    mRunCond.wait(lock, [this]{ return !mRunning; });
}

void PowerManager::stop() {
    {
        std::lock_guard<std::mutex> lock(mRunMutex);
        mRunning = false;
    }   // ← 这里 lock 析构，unlock
    mRunCond.notify_one();   // 通知等待方
}
```

**happens-before 分析**：
1. stop 线程：`mRunning = false`（程序序）
2. stop 线程：`unlock`（release 操作）
3. stop 线程：`notify_one`（唤醒）
4. run 线程：从 futex 醒来
5. run 线程：`lock`（acquire 操作，看到 stop 的写）
6. run 线程：`!mRunning` 为 true，退出 wait

**关键**：必须在 notify 之前 unlock，否则 wait 方重新加锁会失败。

### 5.8 false sharing 性能陷阱

```cpp
struct Counters {
    int a = 0;   // 线程 1 写
    int b = 0;   // 线程 2 写
};
Counters c;   // a 和 b 在同一缓存行（64 字节）

// 线程 1: while (...) c.a++;
// 线程 2: while (...) c.b++;
// 结果：两个线程看似无冲突，但 CPU 缓存行频繁失效，性能下降 10 倍
```

**修复**：`alignas(64)` 强制独占缓存行

```cpp
struct Counters {
    alignas(64) int a = 0;
    alignas(64) int b = 0;
};
```

### 5.9 深度思考题

**题**：以下代码会出现什么问题？怎么修？
```cpp
std::atomic<bool> ready{false};

void waiter() {
    while (!ready.load()) { }   // 自旋等待
}

void notifier() {
    ready.store(true);
}
```

---

## 6. chrono：类型安全、duration 与时钟选择

### 6.1 duration 的类型安全设计

```cpp
std::chrono::seconds s1(10);
std::chrono::milliseconds ms1(500);

auto sum = s1 + ms1;   // ❌ 编译错误！seconds + milliseconds 类型不匹配
// 正确：显式转换
auto sum2 = s1 + std::chrono::duration_cast<std::chrono::seconds>(ms1);
```

**编译期防止单位混淆**：不会出现把毫秒当秒用。

### 6.2 三种时钟的本质区别

| 时钟 | 单调性 | 可调整 | 用途 |
|:---|:---:|:---:|:---|
| `system_clock` | ❌ 可回拨 | ✅ NTP 调整 | 墙上时间、日志时间戳 |
| `steady_clock` | ✅ 单调 | ❌ | 测耗时、定时器 |
| `high_resolution_clock` | 取决于实现 | — | 通常等于 steady_clock |

**陷阱**：
```cpp
auto start = std::chrono::system_clock::now();
foo();
auto end = std::chrono::system_clock::now();
auto elapsed = end - start;   // ❌ 可能是负数（NTP 调整时钟）！
```

**正确做法**：用 `steady_clock` 测耗时。

### 6.3 time_point 的 epoch

```cpp
auto now = std::chrono::system_clock::now();
auto since_epoch = now.time_since_epoch();
// since_epoch 是从 1970-01-01 到现在的 duration

auto ns = since_epoch.count();   // 纳秒数（long long）
```

### 6.4 项目实例分析

[LogReader.cpp:41](../service/LogServer/LogReader.cpp#L41)：

```cpp
info.createTime = std::filesystem::last_write_time(entry.path())
                    .time_since_epoch().count();
```

**原理**：
1. `last_write_time` 返回 `file_time_type`（高精度时间点）
2. `.time_since_epoch()` 取相对 epoch 的 duration
3. `.count()` 取出底层整数（纳秒或微秒，取决于实现）

### 6.5 高精度定时器

```cpp
auto start = std::chrono::steady_clock::now();
expensiveOp();
auto end = std::chrono::steady_clock::now();
auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
std::cout << "耗时 " << ns << " 纳秒\n";
```

### 6.6 深度思考题

**题**：为什么 steady_clock 比 system_clock 更适合测耗时？请从时钟调整、CPU 缓存、精度三个角度分析。

---

## 7. 字符串与流：SSO、流缓冲与性能

### 7.1 std::string 的 SSO（Small String Optimization）

短字符串直接存在对象内部，不分配堆内存：

```cpp
// GCC libstdc++ 实现（简化）
class string {
    union {
        struct { char* ptr; size_t len; size_t cap; };   // 长字符串模式
        char buf[16];                                     // 短字符串模式（SSO）
    };
    // 阈值：libstdc++ 15 字符，libc++ 22 字符
};
```

**性能影响**：
- 短字符串（< 16 字符）：零堆分配
- 长字符串：堆分配，append 可能触发扩容

### 7.2 std::string_view（C++17）

非拥有字符串视图，零拷贝：

```cpp
std::string_view sv = "hello world";   // 不分配内存
sv.substr(0, 5);                       // 仍指向原内存，O(1)
sv.length();                            // O(1)

// 陷阱：源字符串销毁后 view 悬空
std::string_view getBadView() {
    std::string s = "hello";
    return s;   // ❌ s 离开作用域销毁，view 悬空
}
```

### 7.3 stringstream 的性能瓶颈

```cpp
std::stringstream ss;
ss << "a" << 1 << "b" << 2;
// 每次操作涉及：格式化、虚拟函数调用、缓冲管理
```

**替代方案**：

```cpp
// 高性能：直接用 std::to_string + +=
std::string s = "a" + std::to_string(1) + "b" + std::to_string(2);

// 极致性能：fmtlib / std::format（C++20）
#include <fmt/format.h>
std::string s = fmt::format("a{}b{}", 1, 2);
```

### 7.4 流的状态机

```cpp
std::stringstream ss;
ss << "abc";
ss >> x;   // 失败：解析错误

if (ss.fail()) { /* 解析失败 */ }
ss.clear();   // 清错误标志
```

### 7.5 项目实例深度分析

[LogExporter.cpp:38-41](../service/LogServer/LogExporter.cpp#L38-L41)：

```cpp
std::stringstream ss;
ss << std::put_time(std::localtime(&timeT), "%Y%m%d_%H%M%S");
//                       ↑ put_time 返回 special stream manipulator
//                          operator<< 内部调用 tm::put
exportedFile = targetPath + "/log_export_" + ss.str() + ".zip";
//                            ↑ 取出字符串，可能涉及堆分配
```

**性能分析**：
1. `std::localtime` 不是线程安全！多线程同时调用会用同一静态 `struct tm`
2. 修复：用 `localtime_r`（POSIX）或 `localtime_s`（C11 Annex K）
3. `put_time` 内部多次 `<<`，比直接 sprintf 慢

### 7.6 线程安全的 localtime

```cpp
std::tm tm_local;
#ifdef _WIN32
    localtime_s(&tm_local, &timeT);
#else
    localtime_r(&timeT, &tm_local);
#endif
ss << std::put_time(&tm_local, "%Y%m%d_%H%M%S");
```

### 7.7 深度思考题

**题**：为什么 `std::stringstream ss; ss << "a" << 1;` 比 `sprintf(buf, "a%d", 1)` 慢？从虚函数调用、格式解析、缓冲管理三个角度分析。

---

## 8. filesystem：错误处理、UTF-8 与跨平台

### 8.1 path 的内部表示

```cpp
std::filesystem::path p = "C:/Users/admin/log.txt";
// path 内部用 std::basic_string<value_type>
//   - Windows: value_type = wchar_t (UTF-16)
//   - Linux/Mac: value_type = char (UTF-8)
```

### 8.2 跨平台路径分隔符

```cpp
namespace fs = std::filesystem;

// 推荐：用 / 拼接，path 自动处理
fs::path p = fs::path("a") / "b" / "c.txt";   // a/b/c.txt 或 a\b\c.txt
// 比手动拼 "/" 更安全（Windows 上可能需要反斜杠）

// 不推荐：手动拼字符串
std::string s = "a/b/c.txt";   // Windows 上某些 API 不认
```

### 8.3 错误处理：异常 vs error_code

```cpp
// 抛异常版本
try {
    auto size = fs::file_size("/not/exist");   // 抛 filesystem_error
} catch (const fs::filesystem_error& e) {
    std::cerr << e.what();
}

// 不抛异常版本（性能更好）
std::error_code ec;
auto size = fs::file_size("/not/exist", ec);
if (ec) {
    std::cerr << ec.message();
}
```

**性能场景**：遍历大量文件时用 `error_code` 版本，避免异常开销。

### 8.4 directory_iterator vs recursive_directory_iterator

```cpp
// 单层遍历
for (const auto& entry : fs::directory_iterator(dir)) {
    // dir 下直接子项（不递归）
}

// 递归遍历（深度优先）
for (const auto& entry : fs::recursive_directory_iterator(dir)) {
    // 所有子目录的文件
}

// 控制递归
fs::recursive_directory_iterator it(dir, fs::directory_options::skip_permission_denied);
```

### 8.5 文件类型判断

```cpp
fs::file_status s = fs::status(p);
fs::is_regular_file(s);   // 普通文件
fs::is_directory(s);      // 目录
fs::is_symlink(p);        // 符号链接
fs::is_block_file(s);     // 块设备
fs::is_character_file(s); // 字符设备
fs::is_fifo(s);           // 管道
fs::is_socket(s);         // 套接字
```

### 8.6 项目实例深度分析

[LogReader.cpp:35-44](../service/LogServer/LogReader.cpp#L35-L44)：

```cpp
for (const auto& entry : std::filesystem::directory_iterator(dir)) {
    if (entry.is_regular_file() && entry.path().extension() == ".log") {
        info.fileSize = std::filesystem::file_size(entry.path());
        info.createTime = std::filesystem::last_write_time(entry.path())
                          .time_since_epoch().count();
    }
}
```

**改进点**：
1. **错误处理**：`file_size` 可能抛异常（文件被删/无权限），应该用 `error_code` 版本
2. **性能**：`entry.path()` 每次调用都构造新 path 对象，可以缓存
3. **稳定性**：遍历过程中文件被删除，迭代器可能失效

### 8.7 改进版

```cpp
std::error_code ec;
for (const auto& entry : fs::directory_iterator(dir, ec)) {
    if (ec) break;
    
    auto path = entry.path();
    if (entry.is_regular_file() && path.extension() == ".log") {
        LogFileInfo info;
        info.fileName = path.filename().string();
        info.fileSize = fs::file_size(path, ec);
        if (ec) continue;
        info.createTime = fs::last_write_time(path, ec).time_since_epoch().count();
        if (ec) continue;
        info.sourceType = sourceType;
        files.push_back(info);
    }
}
```

### 8.8 深度思考题

**题**：为什么 `fs::file_size(p)` 比 `stat()` 系统调用"慢"？从封装层、错误处理、跨平台兼容三个角度分析。

---

## 9. 类与对象：规则五、虚函数表与 ABI

### 9.1 Rule of Five

C++11 后，需要管理资源时定义以下五个：

```cpp
class Resource {
public:
    Resource();                              // 默认构造
    ~Resource();                             // 析构
    Resource(const Resource&);                // 拷贝构造
    Resource& operator=(const Resource&);     // 拷贝赋值
    Resource(Resource&&) noexcept;            // 移动构造
    Resource& operator=(Resource&&) noexcept; // 移动赋值
};
```

**Rule of Zero**：让编译器生成默认版本，用智能指针管理资源：

```cpp
class Widget {
    std::unique_ptr<Impl> p_;   // 编译器生成的 5 个函数都正确
    // 不需要手写任何构造/析构/拷贝/移动
};
```

### 9.2 虚函数表（vtable）

```cpp
class Base {
public:
    virtual void foo() {}       // 占一个 vtable 槽
    virtual void bar() {}       // 占一个 vtable 槽
};

class Derived : public Base {
public:
    void foo() override {}      // 覆盖 foo，bar 仍用 Base 的
};

// 内存布局：
// Base 对象：
//   [vptr] → [Base_vtable] = { &Base::foo, &Base::bar }
//
// Derived 对象：
//   [vptr] → [Derived_vtable] = { &Derived::foo, &Base::bar }
```

**调用过程**：
```cpp
Base* b = new Derived;
b->foo();
// 1. 取 b->vptr
// 2. 查 vptr[0]（foo 在 vtable 的位置）
// 3. 跳到 Derived::foo
```

**性能开销**：
1. 对象大小 +8 字节（vptr 指针）
2. 调用间接（无法内联）
3. 缓存不友好（vtable 在堆）

### 9.3 虚析构的必要性

```cpp
class Base {
public:
    virtual ~Base() = default;   // ✅ 虚析构，多态删除安全
};

class Derived : public Base {
    int* data_;
    ~Derived() { delete[] data_; }
};

Base* b = new Derived;
delete b;   // 调用 Derived::~Derived，再 ~Base
// 如果 ~Base 不是虚的：只调用 ~Base，data_ 泄漏
```

### 9.4 final 的优化

```cpp
class Derived final : public Base {
    void foo() override final {}   // 不允许子类（无子类）再覆盖
};

// 编译器优化：知道 Derived 不能再被继承
// b->foo() 如果 b 是 Derived*，可以 devirtualize
```

### 9.5 项目实例深度分析

[Singleton.h](../service/PowerManagerService/include/Singleton.h)：

```cpp
template<typename T>
class Singleton {
public:
    static T* instance() {
        static T inst;   // C++11 Magic Statics，线程安全
        return &inst;
    }

private:
    Singleton() = default;
    ~Singleton() = default;
    Singleton(const Singleton&) = delete;
    Singleton& operator=(const Singleton&) = delete;
};

#define DECLARE_SINGLETON_FRIEND(class_name) \
    friend class Singleton<class_name>;
```

**原理解析**：

1. **Magic Statics**：C++11 起静态局部变量初始化线程安全，编译器用 `__cxa_guard_acquire/release` 包裹
2. **友元**：让 `Singleton<T>` 能访问 `T` 的 private 构造函数
3. **delete 拷贝/赋值**：防止单例被复制
4. **default 构造/析构**：让编译器生成，但 private 限制访问

### 9.6 Rule of Zero 项目实例

[PowerManager.h](../service/PowerManagerService/include/PowerManager.h)：

```cpp
class PowerManager {
    std::unique_ptr<FdbusPowerAdapter> mAdapter;
    std::unique_ptr<KeyEventHandler> mKeyHandler;
    std::unique_ptr<StrNotifier> mStrNotifier;
    std::unique_ptr<EcdClient> mEcdClient;
    // 全是 unique_ptr 成员
    // → 默认生成的析构会调用每个 unique_ptr 的析构，自动 delete
    // → 默认生成的拷贝构造/赋值会失败（unique_ptr 不可拷贝）
    // → 默认生成的移动构造/赋值会 move 每个 unique_ptr
    // 不需要手写任何特殊成员函数！
};
```

### 9.7 深度思考题

**题**：为什么 `Singleton::instance()` 用 static 局部变量比用成员变量加锁更优雅？请从线程安全、初始化时机、内存布局分析。

---

## 10. 类型转换：底层行为与 ABI

### 10.1 static_cast 的底层行为

```cpp
double d = 3.14;
int i = static_cast<int>(d);
// 汇编：cvttsd2si（double 转 int 指令）

Base* b = new Derived;
Derived* d = static_cast<Derived*>(b);
// 汇编：mov（仅指针赋值，无运行时检查！）
```

**陷阱**：`static_cast` 向下转型不做运行时检查，转错类型是 UB。

### 10.2 dynamic_cast 的实现

```cpp
Base* b = new Derived;
Derived* d = dynamic_cast<Derived*>(b);
// 编译器生成：
// 1. 取 b 的 vptr
// 2. 查 RTTI（runtime_type_info）
// 3. 比较 Derived 的 RTTI 与 b 的实际 RTTI
// 4. 匹配则返回调整后的指针，否则 nullptr
```

**性能开销**：每次 `dynamic_cast` 调用 RTTI 查找，比 `static_cast` 慢 10-100 倍。

### 10.3 reinterpret_cast 的本质

```cpp
int x = 42;
char* p = reinterpret_cast<char*>(&x);
// 不生成任何指令，只是告诉编译器"把这块内存当 char 数组看"
// p[0] = 0;  修改了 x 的最低字节
```

**陷阱**：违反 strict aliasing 规则，编译器优化可能导致 UB。

### 10.4 严格别名（Strict Aliasing）

```cpp
int x = 0;
float* fp = reinterpret_cast<float*>(&x);   // ❌ 类型不兼容
*fp = 1.0f;
// 编译器假定 int 和 float 不别名，可能优化错误

// 正确：用 memcpy
float f;
std::memcpy(&f, &x, sizeof(f));   // ✅ 安全的类型双关
```

### 10.5 项目实例分析

[EcdClient.cpp:100](../service/PowerManagerService/src/EcdClient.cpp#L100)：

```cpp
auto* data = (const PowerModeInfo*)msg->getPayloadBuffer();
```

**底层风险**：

1. **对齐问题**：`void*` 可能未对齐到 `alignof(PowerModeInfo)`，ARM/MIPS 上 unaligned access 是 UB
   - 修复：保证 fdbus 消息 buffer 对齐，或用 `memcpy` 读取

2. **strict aliasing**：`void*` 转 `PowerModeInfo*` 合法，但通过指针访问底层 buffer 可能违反 aliasing
   - 修复：先 `memcpy` 到本地变量

3. **padding 差异**：两端编译器 padding 可能不同
   - 修复：`#pragma pack(1)` 或显式序列化

**更安全的实现**：

```cpp
PowerModeInfo data;
std::memcpy(&data, msg->getPayloadBuffer(), sizeof(PowerModeInfo));
// 编译器保证对齐 + aliasing 安全
```

### 10.6 深度思考题

**题**：为什么 `(int*)float_ptr` 用 `reinterpret_cast` 会 UB？如何安全地以 int 视角读 float 的位？

---

## 11. STL 容器：迭代器失效、复杂度保证

### 11.1 vector 的增长策略

```cpp
std::vector<int> v;
for (int i = 0; i < 100; ++i) {
    v.push_back(i);   // 触发多次扩容：1 → 2 → 4 → 8 → 16 → 32 → 64 → 128
}
// 扩容因子通常 2（GCC）或 1.5（MSVC）
```

**复杂度保证**：
- `push_back` 均摊 O(1)
- 随机访问 O(1)
- 中间插入/删除 O(n)

### 11.2 迭代器失效规则

| 操作 | 失效规则 |
|:---|:---|
| `vector::push_back` 触发扩容 | 所有迭代器/指针/引用失效 |
| `vector::push_back` 不扩容 | 不失效 |
| `vector::insert/erase` | 该位置及之后失效 |
| `deque::insert` 中间 | 全部失效 |
| `list::insert/erase` | 仅被删元素失效 |
| `map/set::erase` | 仅被删元素失效 |
| `unordered_map::erase` | 仅被删元素失效（rehash 时全部失效） |

**典型坑**：
```cpp
std::vector<int> v = {1, 2, 3, 4};
for (auto it = v.begin(); it != v.end(); ++it) {
    if (*it == 2) v.erase(it);   // ❌ it 失效
}

// 正确：
for (auto it = v.begin(); it != v.end();) {
    if (*it == 2) it = v.erase(it);   // erase 返回下一个有效迭代器
    else ++it;
}
```

### 11.3 emplace vs push

```cpp
std::vector<std::string> v;

v.push_back(std::string("hello"));   // 1. 临时 string 构造 2. 移动到 vector
v.emplace_back("hello");              // 1. 直接在 vector 内存中构造 string("hello")
// emplace_back 省去一次移动构造
```

### 11.4 reserve 预分配

```cpp
std::vector<int> v;
v.reserve(1000);   // 预分配容量
for (int i = 0; i < 1000; ++i) {
    v.push_back(i);   // 不再扩容，O(1) 每次
}
```

### 11.5 项目实例分析

[LogExporter.cpp:64-69](../service/LogServer/LogExporter.cpp#L64-L69)：

```cpp
std::vector<std::string> filePaths;
for (const auto& file : files) {
    // ...
    filePaths.push_back(dir + "/" + file.fileName);
}
```

**性能改进**：

```cpp
std::vector<std::string> filePaths;
filePaths.reserve(files.size());   // ✅ 预分配
for (const auto& file : files) {
    filePaths.push_back(dir + "/" + file.fileName);
}
```

### 11.6 unordered_map 的 rehash 陷阱

```cpp
std::unordered_map<int, int> m;
m.reserve(1000);   // 预分配桶

// 在遍历时插入会导致迭代器失效！
for (auto it = m.begin(); it != m.end(); ++it) {
    m[it->first + 100] = 1;   // ❌ 可能 rehash，it 失效
}
```

### 11.7 深度思考题

**题**：为什么 `std::vector` 扩容因子是 2 而不是 1.5？为什么 MSVC 用 1.5？从内存复用、缓存友好性分析。

---

## 12. function 与 bind：类型擦除、分配器

### 12.1 std::function 的类型擦除

```cpp
std::function<int(int)> f = [](int x) { return x * 2; };
// function 内部：
//   - 小对象：存储 lambda 对象本身（SSO 类似）
//   - 大对象：堆分配 + 存指针
```

**实现原理**：用**虚函数 + 模板**实现类型擦除：

```cpp
// 简化的 function 内部
struct function_base {
    virtual ~function_base() {}
    virtual int invoke(int) = 0;
};

template<typename F>
struct function_impl : function_base {
    F f_;
    function_impl(F f) : f_(f) {}
    int invoke(int x) override { return f_(x); }
};

class function {
    function_base* impl_;
public:
    template<typename F>
    function(F f) : impl_(new function_impl<F>(f)) {}
    int operator()(int x) { return impl_->invoke(x); }
};
```

### 12.2 std::bind 的内部实现

```cpp
auto f = std::bind(add, 1, std::placeholders::_1);
// f 是一个未命名类型，存储了 add 的指针 + 1
f(2);   // 调用 add(1, 2)
```

**bind 的局限**：
1. 类型签名不直观
2. 重载函数难绑定
3. 性能不如 lambda（多一层间接）

### 12.3 现代 C++ 推荐：lambda 替代 bind

```cpp
// 旧式：bind
auto f1 = std::bind(&PowerManager::handlePowerMode, this, std::placeholders::_1);

// 现代式：lambda（更清晰、更易优化）
auto f2 = [this](const PowerModeInfo& info) { handlePowerMode(info); };
```

### 12.4 项目实例深度分析

[PowerManager.cpp:46-47](../service/PowerManagerService/src/PowerManager.cpp#L46-L47)：

```cpp
mEcdClient->setPowerModeHandler(
    std::bind(&PowerManager::handlePowerMode, this, std::placeholders::_1));
```

**改进建议**：

```cpp
mEcdClient->setPowerModeHandler(
    [this](const PowerModeInfo& info) { handlePowerMode(info); });
// 或：
mEcdClient->setPowerModeHandler(
    [this](const PowerModeInfo& info) { return handlePowerMode(info); });
```

**优势**：
1. 编译器内联 lambda 更容易
2. 可读性高
3. 无 placeholders 噪音

### 12.5 深度思考题

**题**：为什么 `std::function` 比直接 `auto f = [](...){...}` 慢？从虚函数调用、SSO、内联三个角度分析。

---

## 附录 A：汇编对比速查

### A.1 auto vs 手写类型

```cpp
// 汇编完全相同
auto x = 42;          // mov DWORD PTR [rbp-4], 42
int x = 42;            // mov DWORD PTR [rbp-4], 42
```

### A.2 unique_ptr vs 裸指针

```cpp
// 汇编完全相同
std::unique_ptr<int> p(new int(42));
int* p = new int(42);
// 都是 mov + call operator new
```

### A.3 shared_ptr 的额外开销

```cpp
// shared_ptr 拷贝
auto p2 = p1;
// 汇编：
//   mov rdi, [p1.control]
//   mov rax, [rdi]            ; load counter
//   add rax, 1                ; increment
//   mov [rdi], rax             ; store back
//   lock                     ; 原子指令，缓存锁定
```

### A.4 lambda 内联

```cpp
auto f = [](int x) { return x * 2; };
int y = f(21);
// 编译后：mov eax, 42 （lambda 内联，零调用开销）
```

### A.5 std::function 的间接调用

```cpp
std::function<int(int)> g = [](int x) { return x * 2; };
int y = g(21);
// 编译后：
//   mov rdi, g
//   call [g + offset]         ; 间接调用，无法内联
```

---

## 附录 B：UB（未定义行为）清单

### B.1 常见 UB

| UB | 例子 | 后果 |
|:---|:---|:---|
| 数组越界 | `int a[10]; a[20] = 1;` | 崩溃/任意写 |
| 使用未初始化变量 | `int x; if (x == 0) ...` | 任意分支 |
| 空指针解引用 | `*nullptr` | 段错误 |
| 整数溢出（有符号） | `INT_MAX + 1` | 任意值 |
| 多线程数据竞争 | 两线程同时写非 atomic | 任意结果 |
| 错误类型 reinterpret_cast | `int* p; float* f = (float*)p; *f = 1.0;` | 任意值 |
| 悬空引用 | 返回局部变量引用 | 任意值 |
| double free | 同一指针 delete 两次 | 崩溃 |
| 违反 strict aliasing | 用 `int*` 访问 float 内存 | 优化错误 |
| 违反 ODR | 同一符号两份定义 | 链接错误/任意行为 |

### B.2 检测工具

```bash
# Address Sanitizer：内存错误
g++ -fsanitize=address -g xxx.cpp

# Undefined Behavior Sanitizer
g++ -fsanitize=undefined -g xxx.cpp

# Thread Sanitizer：数据竞争
g++ -fsanitize=thread -g xxx.cpp

# Memory Sanitizer：未初始化读
clang++ -fsanitize=memory -g xxx.cpp

# Valgrind（运行时检测）
valgrind --tool=memcheck ./a.out
```

---

## 附录 C：性能优化原则

### C.1 不要过早优化

> "Premature optimization is the root of all evil" — Donald Knuth

1. 先写**正确**的代码
2. 用 profiler 找瓶颈（perf、VTune、gperftools）
3. 只优化热点

### C.2 编译器优化的边界

```cpp
// 编译器能优化
int sum = 0;
for (int i = 0; i < 100; ++i) sum += i;
// → 编译期算出 4950

// 编译器不能优化
for (int i = 0; i < n; ++i) v[i] = i;   // n 是运行期变量
```

### C.3 数据局部性

```cpp
// 缓存友好：行优先遍历
for (int i = 0; i < N; ++i)
    for (int j = 0; j < N; ++j)
        m[i][j] = 0;   // ✅ 连续内存访问

// 缓存不友好：列优先
for (int j = 0; j < N; ++j)
    for (int i = 0; i < N; ++i)
        m[i][j] = 0;   // ❌ 跳跃访问
```

### C.4 减少动态分配

```cpp
// ❌ 循环中分配
for (int i = 0; i < 1000; ++i) {
    std::string s = std::to_string(i);
    process(s);
}

// ✅ 复用缓冲
std::string s;
for (int i = 0; i < 1000; ++i) {
    s = std::to_string(i);
    process(s);
}
```

### C.5 移动优于拷贝

```cpp
std::vector<std::string> v;
std::string s = "hello";
v.push_back(std::move(s));   // ✅ 移动，O(1)
// vs
v.push_back(s);              // 拷贝，O(n)
```

---

## 附录 D：现代 C++ 推荐做法速查

### D.1 DO

```cpp
// 1. 用智能指针管理资源
auto p = std::make_unique<T>(args);

// 2. 用 auto 推导复杂类型
auto it = m.find(key);

// 3. 用 range-based for
for (const auto& x : container) { ... }

// 4. 用 nullptr 替代 NULL
int* p = nullptr;

// 5. 用 enum class 替代 enum
enum class Color { Red, Green, Blue };

// 6. 用 override 标记虚函数覆盖
void foo() override;

// 7. 用 noexcept 标记不抛异常的函数
void swap(T&, T&) noexcept;

// 8. 用 const 表达不可变
const auto& ref = getValue();

// 9. 用 lambda 替代 bind
auto f = [this](auto x) { return x * 2; };

// 10. 用 RAII 管理资源
std::lock_guard<std::mutex> lk(m);
```

### D.2 DON'T

```cpp
// 1. 不要用裸 new/delete
int* p = new int(42);   // ❌

// 2. 不要用 NULL
int* p = NULL;          // ❌

// 3. 不要用旧式 enum
enum Color { Red };      // ❌

// 4. 不要用 C 风格 cast
int* p = (int*)x;        // ❌

// 5. 不要用 std::bind（用 lambda）
auto f = std::bind(...); // ❌

// 6. 不要返回局部变量引用
int& foo() { int x; return x; }   // ❌

// 7. 不要用 std::endl（用 "\n"）
std::cout << "hi" << std::endl;   // ❌ 多一次 flush

// 8. 不要在范围 for 中修改容器
for (auto& x : v) v.push_back(1);   // ❌ UB

// 9. 不要用 auto&& 不熟悉
auto&& x = ...;   // ❌ 转发引用陷阱

// 10. 不要假设对象布局
memcpy(this, &other, sizeof(*this));   // ❌ padding 陷阱
```

---

## 附录 E：深度学习路径

### E.1 进阶书籍

| 阶段 | 书名 | 重点 |
|:---|:---|:---|
| 中级 | Effective Modern C++ | 55 条最佳实践 |
| 中级 | C++ Concurrency in Action | 内存模型、原子操作、fences |
| 高级 | Effective STL | STL 陷阱与优化 |
| 高级 | Exceptional C++ | 异常安全、RAII |
| 大师级 | C++ Templates (Vandevoorde) | 模板元编程 |
| 大师级 | Large-Scale C++ (Lakos) | 物理设计、模块化 |

### E.2 标准 proposal

- https://www.open-std.org/jtc1/sc22/wg21/
- 看 proposal 了解每个特性的**设计动机**

### E.3 大型项目源码

| 项目 | 学什么 |
|:---|:---|
| LLVM/Clang | 工程化、模块化 |
| Chromium | 跨平台、大规模 |
| Folly (Facebook) | 性能优化技巧 |
| Boost | 模板、元编程 |

### E.4 在线工具

- **Compiler Explorer**：https://godbolt.org/ — 看汇编、对比编译器
- **Quick Bench**：https://quick-bench.com/ — 性能对比
- **CppInsights**：https://cppinsights.io/ — 看 lambda、auto 等转换后的代码

---

**文档版本**：v1.0  
**最后更新**：2026-08-24  
**配套文档**：[ModernCpp_Basic.md](./ModernCpp_Basic.md) 入门+实用版  
**反馈建议**：读完每章后做深度思考题，用 sanitizer 验证
