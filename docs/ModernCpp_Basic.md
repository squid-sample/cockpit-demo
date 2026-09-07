# 现代 C++ 学习笔记（入门+实用版）

> **文档定位**：C++11/14/17 实用速查 + 项目实例对照
> **适用对象**：有 Java/Python 基础、刚接触 C++ 的开发者
> **配套项目**：`d:\Android\Project\20260813\demo\service\`
> **学习目标**：1 周内能读懂项目代码，2 周内能仿写小模块

---

## 0. 文档说明

### 0.1 本文档的用法

1. **不要从头到尾读**：按需查阅，每章独立
2. **配合项目代码看**：每节末尾有「项目实例」，直接跳到对应文件
3. **动手验证**：每章末尾有「练习题」，至少做 1 道
4. **环境要求**：g++ ≥ 7.5 或 clang++ ≥ 6.0，C++17 标准

### 0.2 编译命令速查

```bash
# 单文件编译
g++ -std=c++17 -Wall -Wextra -g your_file.cpp -o your_app

# 严格模式（警告当错误）
g++ -std=c++17 -Wall -Wextra -Werror -pedantic your_file.cpp -o your_app

# 带地址消毒（抓内存错误）
g++ -std=c++17 -fsanitize=address,undefined -g your_file.cpp -o your_app

# C++ 标准速查
C++11 = -std=c++11
C++14 = -std=c++14
C++17 = -std=c++17
C++20 = -std=c++20
```

### 0.3 现代 C++ 时间线


| 标准 | 发布年份 | 重要特性                                               |
| :-----: | :--------: | :------------------------------------------------------- |
| C++11 |   2011   | auto、智能指针、lambda、右值引用、thread、chrono       |
| C++14 |   2014   | make_unique、泛型 lambda、binary literals              |
| C++17 |   2017   | filesystem、optional、string_view、structured bindings |
| C++20 |   2020   | concepts、ranges、coroutines、modules（本文档不涉及）  |

---

## 1. auto 与类型推导

### 1.1 是什么

`auto` 让编译器**自动推导变量类型**，省去写冗长类型名的麻烦。

### 1.2 解决什么问题

C++03 时代：

```cpp
std::map<std::string, std::vector<int>>::const_iterator it = myMap.cbegin();
// 类型名长达 40 个字符，写起来累，读起来也累
```

### 1.3 基本语法

```cpp
// 基础用法
auto x = 42;              // int
auto y = 3.14;            // double
auto s = "hello";         // const char* （注意：不是 std::string！）
auto str = std::string("hello");  // std::string

// 复杂类型
std::map<std::string, int> m;
auto it = m.begin();      // std::map<std::string, int>::iterator

// 函数返回值推导（C++14）
auto make_vector() {
    return std::vector<int>{1, 2, 3};   // 自动推导返回 vector<int>
}
```

### 1.4 auto 与 const/引用

```cpp
int x = 42;
int& ref = x;

auto a = ref;             // auto 推导为 int（丢弃引用和 const）
auto& b = ref;             // auto 推导为 int& （保留引用）
const auto& c = ref;       // auto 推导为 int，加 const &

// 推荐：用 auto& 遍历容器，避免拷贝
std::vector<std::string> names = {"alice", "bob"};
for (const auto& name : names) {   // 不拷贝
    std::cout << name << "\n";
}
```

### 1.5 项目实例

[LogExporter.cpp:36-37](../service/LogServer/LogExporter.cpp#L36-L37)：

```cpp
auto now = std::chrono::system_clock::now();     // 类型：std::chrono::time_point<...>
auto timeT = std::chrono::system_clock::to_time_t(now);  // 类型：std::time_t
```

**不用 auto 写法**：

```cpp
std::chrono::time_point<std::chrono::system_clock> now = std::chrono::system_clock::now();
std::time_t timeT = std::chrono::system_clock::to_time_t(now);
// 类型名太长，auto 更清晰
```

### 1.6 易错点


| 坑              | 示例                                               | 正确做法                                     |
| :---------------- | :--------------------------------------------------- | :--------------------------------------------- |
| `auto` 推成指针 | `auto s = "hello";` 是 `const char*` 不是 `string` | 想要 string 显式写`std::string s = "hello";` |
| `auto` 丢引用   | `auto x = ref;` 是值拷贝                           | 用`auto&` 保留引用                           |
| `auto` 丢 const | `auto x = const_obj;` 能修改                       | 用`const auto&`                              |
| `auto&&` 陷阱   | `auto&& x = ...;` 是转发引用                       | 不熟悉就别用                                 |

### 1.7 练习题

**题 1**：以下代码输出什么？为什么？

```cpp
std::vector<int> v = {1, 2, 3};
auto a = v[0];        // a 的类型？
auto& b = v[0];       // b 的类型？
a = 100;              // v 改变吗？
b = 100;              // v 改变吗？
```

**题 2**：用 `auto` 重写下面代码

```cpp
std::map<std::string, std::vector<int>>::iterator it = myMap.find("key");
```

---

## 2. 智能指针

### 2.1 是什么

C++11 引入的**自动管理内存的指针**，析构时自动 delete，告别手动 new/delete 内存泄漏。

### 2.2 解决什么问题

C++98 时代的噩梦：

```cpp
void foo() {
    int* p = new int(42);
    if (error) {
        delete p;        // 容易忘
        return;
    }
    bar();               // 如果 bar 抛异常 → p 泄漏！
    delete p;            // 最后还要 delete
}
```

### 2.3 四种智能指针速查


| 类型            | 头文件     | 所有权                 |     可拷贝     | 何时用                 |
| :---------------- | :----------- | :----------------------- | :---------------: | :----------------------- |
| `unique_ptr<T>` | `<memory>` | 独占                   | ❌（只能 move） | 默认首选               |
| `shared_ptr<T>` | `<memory>` | 共享（引用计数）       |       ✅       | 多处共享同一对象       |
| `weak_ptr<T>`   | `<memory>` | 弱引用，不增加引用计数 |       ✅       | 打破循环引用           |
| `auto_ptr<T>`   | —         | 转移所有权             |   ✅（有坑）   | **C++11 已废弃，别用** |

### 2.4 unique_ptr 基础

```cpp
#include <memory>

// 创建
std::unique_ptr<int> p1 = std::make_unique<int>(42);   // 推荐
std::unique_ptr<int> p2(new int(42));                   // 旧写法，不推荐

// 使用
*p1 = 100;
if (p1) { /* p1 非空 */ }
p1.reset();        // 立即释放
p1.release();      // 放弃所有权（返回裸指针，调用者负责 delete）

// 转移所有权（只能用 std::move）
std::unique_ptr<int> p3 = std::move(p1);  // p1 变 nullptr，p3 接管
```

### 2.5 shared_ptr 基础

```cpp
// 创建
auto p1 = std::make_shared<int>(42);   // 引用计数 = 1
auto p2 = p1;                          // 引用计数 = 2
auto p3 = p1;                          // 引用计数 = 3

// 当所有 shared_ptr 离开作用域，对象才被销毁
*p1 = 100;   // 修改后 p2、p3 看到的也是 100（指向同一对象）

// 引用计数查询
std::cout << p1.use_count();   // 3
```

### 2.6 make_unique vs make_shared

```cpp
// make_unique：1 次内存分配（对象）
auto p = std::make_unique<Widget>(args...);

// make_shared：1 次内存分配（对象 + 控制块合并）
auto p = std::make_shared<Widget>(args...);

// 手写 new shared_ptr：2 次分配（对象 + 控制块分开）
std::shared_ptr<Widget> p(new Widget(args...));   // 不推荐
```

**推荐**：永远用 `make_xxx`，不用 `new`。

### 2.7 项目实例

[PowerManager.cpp:19-44](../service/PowerManagerService/src/PowerManager.cpp#L19-L44)（unique_ptr）：

```cpp
// 独占所有权：PowerManager 专属管理 mAdapter
mAdapter = std::make_unique<FdbusPowerAdapter>("com.cockpit.power.qnx.service",
                                                 POWER_FDBUS_SERVER_TCP_URL);
mKeyHandler = std::make_unique<KeyEventHandler>();
mStrNotifier = std::make_unique<StrNotifier>();
mEcdClient = std::make_unique<EcdClient>();
```

[HelloWorldService.cpp:41](../service/HelloWorldServer/HelloWorldService.cpp#L41)（shared_ptr）：

```cpp
// 共享所有权：service 被 runtime 和线程同时持有
auto service = std::make_shared<HelloWorldServerImpl>();
runtime->registerService("local", "demo.HelloWorld", service);   // runtime 持有
std::thread t(simulatePowerStateChanges, service);                // 线程也持有
// 引用计数 = 2，最后两个持有者都销毁时，对象才释放
```

### 2.8 易错点


| 坑                         | 说明                                                                          | 正确做法                |
| :--------------------------- | :------------------------------------------------------------------------------ | :------------------------ |
| 循环引用                   | A 持 B，B 持 A，两者都用 shared_ptr → 永不释放                               | 其中一个改用 weak_ptr   |
| 裸指针构造多个 shared_ptr  | `int* p = new int; shared_ptr<int> s1(p); shared_ptr<int> s2(p);` → 双重释放 | 只用`make_shared`       |
| shared_ptr 误用 unique_ptr | 把 unique_ptr 当 shared_ptr 用，性能浪费                                      | 单拥有者就用 unique_ptr |
| 数组用错类型               | `unique_ptr<int> p(new int[10]);` → 析构调 delete 而非 delete[]              | 用`unique_ptr<int[]>`   |

### 2.9 练习题

**题 1**：以下代码有何问题？

```cpp
int* raw = new int(42);
std::shared_ptr<int> p1(raw);
std::shared_ptr<int> p2(raw);
```

**题 2**：用 `unique_ptr` 改写

```cpp
FILE* fp = fopen("test.txt", "r");
if (!fp) return;
// ... 读文件
fclose(fp);   // 忘记写就泄漏
```

提示：可以用自定义 deleter。

---

## 3. 右值引用与移动语义

### 3.1 是什么

C++11 引入的「**把资源搬走而不是拷贝**」的机制，大幅提升性能。

### 3.2 左值 vs 右值

```cpp
int a = 10;         // a 是左值（有名字、有地址）
int& lref = a;      // 左值引用

int b = a + 5;      // a + 5 是右值（临时值，没名字）
int&& rref = 10;    // 右值引用（绑定到临时值）
```


| 概念           | 简单判断                          |
| :--------------- | :---------------------------------- |
| 左值（lvalue） | 能取地址`&x`，有名字              |
| 右值（rvalue） | 临时值，如`42`、`a+b`、函数返回值 |

### 3.3 移动构造函数

```cpp
class Buffer {
    int* data_;
    size_t size_;
public:
    // 普通构造
    Buffer(size_t n) : data_(new int[n]), size_(n) {}
  
    // 拷贝构造（深拷贝，慢）
    Buffer(const Buffer& other) 
        : data_(new int[other.size_]), size_(other.size_) {
        std::copy(other.data_, other.data_ + size_, data_);
    }
  
    // 移动构造（资源转移，快）
    Buffer(Buffer&& other) noexcept 
        : data_(other.data_), size_(other.size_) {
        other.data_ = nullptr;    // 把原对象置空
        other.size_ = 0;
    }
  
    ~Buffer() { delete[] data_; }
};
```

### 3.4 std::move

`std::move` **不移动任何东西**，只是把左值**强制转成右值引用**，让编译器选择移动构造函数。

```cpp
Buffer a(1000);
Buffer b = std::move(a);   // 调用移动构造，a 变成空壳
// 此时 a.data_ == nullptr，a.size_ == 0
// 资源已经搬到 b 了
```

### 3.5 项目实例

[PowerManager.cpp:62-72](../service/PowerManagerService/src/PowerManager.cpp#L62-L72)：

```cpp
void PowerManager::stop() {
    // ...
    if (mEcdClient) {
        mEcdClient->destroy();
        mEcdClient.reset();   // 释放 unique_ptr 持有的对象
    }
}
```

[EcdClient.cpp](../service/PowerManagerService/src/EcdClient.cpp) 中 `setPowerModeHandler` 的 `std::bind` 参数传递：

```cpp
mEcdClient->setPowerModeHandler(
    std::bind(&PowerManager::handlePowerMode, this, std::placeholders::_1));
// std::bind 返回的函数对象是右值，被 move 进 setPowerModeHandler
```

### 3.6 易错点


| 坑                       | 说明                                                  |
| :------------------------- | :------------------------------------------------------ |
| 移动后使用原对象         | `auto p = std::move(old); old->foo();` ← old 已失效  |
| `std::move` 不一定真移动 | 如果类没有移动构造，退化为拷贝                        |
| 返回值用`std::move`      | `return std::move(local);` 反而阻止 RVO（返回值优化） |
| `&&` 不一定是右值引用    | 模板里的`T&&` 是转发引用                              |

### 3.7 练习题

**题 1**：以下代码执行后，v 的内容是？

```cpp
std::vector<int> v1 = {1, 2, 3};
std::vector<int> v2 = std::move(v1);
v1.push_back(99);   // 合法吗？v1 现在是什么状态？
```

**题 2**：为下面的 String 类写移动构造函数

```cpp
class String {
    char* data_;
public:
    String(const char* s);   // 普通构造
    String(const String& o); // 拷贝构造
    // 写一个移动构造
};
```

---

## 4. Lambda 表达式

### 4.1 是什么

C++11 引入的「**匿名函数**」，方便写回调、就地定义函数对象。

### 4.2 基本语法

```cpp
[捕获列表](参数列表) -> 返回类型 { 函数体 }
```

```cpp
// 最简单的 lambda
auto hello = []() { std::cout << "hello"; };
hello();   // 调用

// 带参数和返回值
auto add = [](int a, int b) -> int { return a + b; };
std::cout << add(1, 2);   // 3

// 返回类型可省略，让编译器推导
auto square = [](int x) { return x * x; };   // 推导返回 int
```

### 4.3 捕获方式

```cpp
int x = 10, y = 20;

[]           // 不捕获任何变量
[=]          // 按值捕获所有外部变量（拷贝）
[&]          // 按引用捕获所有外部变量
[x]          // 只按值捕获 x
[&x]         // 只按引用捕获 x
[=, &y]      // 默认按值，但 y 按引用
[&x, y]      // 默认按引用，但 x 按值
[this]       // 捕获当前对象指针（类成员中常用）
```

### 4.4 STL 算法配合

```cpp
std::vector<int> v = {3, 1, 4, 1, 5, 9, 2, 6};

// 排序
std::sort(v.begin(), v.end(), [](int a, int b) { return a > b; });
// v: {9, 6, 5, 4, 3, 2, 1, 1}

// 查找
auto it = std::find_if(v.begin(), v.end(), [](int x) { return x > 5; });

// 遍历
std::for_each(v.begin(), v.end(), [](int x) { std::cout << x << " "; });
```

### 4.5 项目实例

[PowerManager.cpp:46-47](../service/PowerManagerService/src/PowerManager.cpp#L46-L47)：

```cpp
mEcdClient->setPowerModeHandler(
    std::bind(&PowerManager::handlePowerMode, this, std::placeholders::_1));
// 用 std::bind 绑定成员函数和 this 指针，等价于：
mEcdClient->setPowerModeHandler(
    [this](const PowerModeInfo& info) { handlePowerMode(info); });
```

[PowerManager.cpp:59](../service/PowerManagerService/src/PowerManager.cpp#L59)：

```cpp
mRunCond.wait(lock, [this]{ return !mRunning; });
// 等待条件变量时的谓词 lambda，避免虚假唤醒
```

### 4.6 易错点


| 坑                           | 说明                                                    |
| :----------------------------- | :-------------------------------------------------------- |
| `[=]` 捕获引用悬空           | lambda 按值捕获，但捕获的是指针，对象已销毁 → 悬空指针 |
| `[&]` 捕获局部变量后异步使用 | 局部变量离开作用域销毁，lambda 中引用悬空               |
| `this` 捕获后异步使用        | this 对象可能已销毁                                     |
| C++14 泛型 lambda`auto` 参数 | 注意模板推导陷阱                                        |

### 4.7 练习题

**题 1**：写一个 lambda，将 `vector<int>` 中所有偶数筛到新 vector

```cpp
std::vector<int> v = {1, 2, 3, 4, 5, 6};
// 用 lambda + std::copy_if 筛出 {2, 4, 6}
```

**题 2**：解释下面 lambda 捕获方式

```cpp
int x = 1, y = 2;
auto f = [=, &y]() { /* ... */ };
```

---

## 5. 并发编程

### 5.1 是什么

C++11 内置的**多线程库**，告别 pthread 跨平台噩梦。

### 5.2 std::thread 基础

```cpp
#include <thread>

void task(int n) {
    std::cout << "task " << n << "\n";
}

// 创建线程
std::thread t1(task, 42);
std::thread t2([]() { std::cout << "lambda thread\n"; });

// 等待线程结束
t1.join();
t2.join();

// 分离（后台运行，不能 join）
std::thread t3(task, 100);
t3.detach();
```

### 5.3 std::mutex 与锁

```cpp
#include <mutex>

std::mutex mtx;
int counter = 0;

void increment() {
    // 推荐用法：lock_guard，RAII 自动解锁
    std::lock_guard<std::mutex> lock(mtx);
    counter++;
  
    // 作用域结束自动 unlock
}

// unique_lock：可以手动 unlock/lock，配合 condition_variable
std::unique_lock<std::mutex> lk(mtx);
lk.unlock();   // 手动解锁
lk.lock();     // 重新加锁
```

### 5.4 std::condition_variable

```cpp
std::mutex mtx;
std::condition_variable cv;
bool ready = false;

// 等待线程
void waiter() {
    std::unique_lock<std::mutex> lk(mtx);
    cv.wait(lk, [&]{ return ready; });   // 不满足则释放锁并阻塞
    // 被唤醒后重新持有锁，继续执行
}

// 通知线程
void notifier() {
    {
        std::lock_guard<std::mutex> lk(mtx);
        ready = true;
    }
    cv.notify_one();   // 唤醒一个等待者
    // cv.notify_all();  唤醒所有
}
```

**关键点**：

- `wait` 会自动释放 mutex → 阻塞 → 被唤醒时重新加锁
- 必须用 `unique_lock`（可加解锁），不能用 `lock_guard`
- `wait(pred)` 形式防止**虚假唤醒**

### 5.5 std::atomic

```cpp
#include <atomic>

std::atomic<int> counter{0};

void increment() {
    counter++;       // 原子操作，无需 mutex
    counter.fetch_add(1);
}

// 适合简单类型（int、bool、指针）
// 复杂结构还是用 mutex
```

### 5.6 项目实例

[PowerManager.h:59-61](../service/PowerManagerService/include/PowerManager.h#L59-L61)：

```cpp
std::mutex mRunMutex;
std::condition_variable mRunCond;
bool mRunning;
```

[PowerManager.cpp:57-67](../service/PowerManagerService/src/PowerManager.cpp#L57-L67)：

```cpp
void PowerManager::run() {
    std::unique_lock<std::mutex> lock(mRunMutex);
    mRunCond.wait(lock, [this]{ return !mRunning; });
    // 阻塞直到 mRunning 变 false
}

void PowerManager::stop() {
    {
        std::lock_guard<std::mutex> lock(mRunMutex);
        mRunning = false;
    }
    mRunCond.notify_one();   // 唤醒 run() 中等待的线程
}
```

[PowerManager.cpp:89-92](../service/PowerManagerService/src/PowerManager.cpp#L89-L92)：

```cpp
{
    std::lock_guard<std::mutex> lock(mStateMutex);
    mCurrentMode = power_info;   // 保护状态变量的读写
}
```

### 5.7 易错点


| 坑                          | 说明                                                   |
| :---------------------------- | :------------------------------------------------------- |
| 死锁                        | 线程 A 持锁 1 求锁 2，线程 B 持锁 2 求锁 1 → 永久等待 |
| 忘记 join/detach            | `std::thread` 析构时若 joinable 会 std::terminate      |
| condition_variable 虚假唤醒 | 不用`wait(pred)` 形式可能被意外唤醒                    |
| atomic 假原子               | `std::atomic<BigStruct>` 可能退化为锁                  |
| 共享数据竞争                | 多线程同时写非 atomic 变量 → UB                       |

### 5.8 练习题

**题 1**：用 `std::thread` + `std::mutex` 写一个线程安全的计数器类

```cpp
class SafeCounter {
    // 实现：inc()、get()
};
```

**题 2**：用 `condition_variable` 实现生产者-消费者

```cpp
// 队列里 < 5 时生产者生产，队列非空时消费者消费
```

---

## 6. 时间库 chrono

### 6.1 是什么

C++11 内置的**时间处理库**，跨平台、类型安全，替代 `gettimeofday`/`clock`。

### 6.2 三个核心概念

```cpp
#include <chrono>

// 1. 时钟（clock）：三种
std::chrono::system_clock;       // 系统时钟（墙上时间，可调整）
std::chrono::steady_clock;       // 稳定时钟（单调递增，测耗时最佳）
std::chrono::high_resolution_clock;  // 高精度（通常等于 steady_clock）

// 2. 时长（duration）
std::chrono::seconds s(10);          // 10 秒
std::chrono::milliseconds ms(500);   // 500 毫秒
std::chrono::hours h(1);             // 1 小时

// 3. 时间点（time_point）
auto now = std::chrono::system_clock::now();
auto later = now + std::chrono::hours(1);   // 1 小时后
```

### 6.3 常用操作

```cpp
// 当前时间
auto now = std::chrono::system_clock::now();
auto time_t_val = std::chrono::system_clock::to_time_t(now);
std::cout << std::ctime(&time_t_val);   // Mon Aug 19 14:30:00 2026

// 计时
auto start = std::chrono::steady_clock::now();
// ... 要计时的代码
auto end = std::chrono::steady_clock::now();
auto elapsed = end - start;
auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(elapsed).count();
std::cout << "耗时: " << ms << " ms\n";

// 休眠
std::this_thread::sleep_for(std::chrono::seconds(2));     // 睡 2 秒
std::this_thread::sleep_for(std::chrono::milliseconds(500));
std::this_thread::sleep_until(now + std::chrono::hours(1));
```

### 6.4 字面量（C++14）

```cpp
using namespace std::chrono_literals;

auto t1 = 1h;        // 1 小时
auto t2 = 30min;     // 30 分钟
auto t3 = 500ms;     // 500 毫秒
auto t4 = 1000us;    // 1000 微秒
auto t5 = 1s;        // 1 秒
```

### 6.5 项目实例

[LogExporter.cpp:36-39](../service/LogServer/LogExporter.cpp#L36-L39)：

```cpp
auto now = std::chrono::system_clock::now();
auto timeT = std::chrono::system_clock::to_time_t(now);
std::stringstream ss;
ss << std::put_time(std::localtime(&timeT), "%Y%m%d_%H%M%S");
// 生成 "20260819_143025" 这样的时间戳字符串
```

[UsbMonitor.cpp:48](../service/LogServer/UsbMonitor.cpp#L48)：

```cpp
std::this_thread::sleep_for(std::chrono::seconds(2));
// 每 2 秒轮询一次 U 盘挂载状态
```

### 6.6 易错点


| 坑                      | 说明                                            |
| :------------------------ | :------------------------------------------------ |
| 用 system_clock 测耗时  | 系统时间可能被 NTP 调回拨 → 测出负数           |
| duration 类型转换       | `duration_cast<seconds>(ms)` 会截断，不四舍五入 |
| chrono 字面量需要 C++14 | C++11 只能用`std::chrono::seconds(1)`           |

### 6.7 练习题

**题 1**：写一个简单的计时器类，记录函数执行耗时

```cpp
class Timer {
    // start()、stop()、elapsed_ms()
};

// 用法：
Timer t;
t.start();
foo();
t.stop();
std::cout << t.elapsed_ms() << " ms\n";
```

**题 2**：生成格式为 `"2026-08-19 14:30:25"` 的时间字符串

---

## 7. 字符串与流

### 7.1 std::string 常用操作

```cpp
std::string s = "hello world";

// 查找
s.find("world");           // 返回位置 6，找不到返回 std::string::npos
s.find("xyz");             // npos

// 子串
s.substr(0, 5);            // "hello"
s.substr(6);               // "world"

// 拼接
std::string s2 = s + " !";
s += " !";

// 长度
s.length();
s.size();                  // 等价

// 比较
s == "hello world";
s.compare("hello");        // 负数/0/正数

// 转换
std::stoi("42");           // string → int
std::stoul("100");         // string → unsigned long
std::stod("3.14");         // string → double
std::to_string(42);        // int → string
```

### 7.2 std::stringstream

```cpp
#include <sstream>

std::stringstream ss;

// 写入
ss << "name=" << "alice" << ", age=" << 30 << ", score=" << 95.5;
// 等价 Python: "name={}, age={}, score={}".format("alice", 30, 95.5)

// 取出
std::string result = ss.str();
// "name=alice, age=30, score=95.5"

// 解析
std::stringstream parser("10 20 30");
int a, b, c;
parser >> a >> b >> c;   // a=10, b=20, c=30
```

### 7.3 流插入运算符 <<

```cpp
std::cout << "hello" << 42;    // 控制台输出
std::stringstream ss; ss << "hello" << 42;   // 写入字符串流
std::ofstream file("a.txt"); file << "hello" << 42;  // 写入文件
```

`<<` 在 C++ 里是**重载的流插入运算符**，含义「把右边的东西塞进左边的流里」。

### 7.4 项目实例

[LogExporter.cpp:38-41](../service/LogServer/LogExporter.cpp#L38-L41)：

```cpp
std::stringstream ss;
ss << std::put_time(std::localtime(&timeT), "%Y%m%d_%H%M%S");
// 把格式化后的时间字符串塞进 stringstream

exportedFile = targetPath + "/log_export_" + ss.str() + ".zip";
// 用 std::string 的 + 拼接出完整路径
// 结果: "/tmp/log_export_20260819_143025.zip"
```

[LogConfig.cpp:92-100](../service/LogServer/LogConfig.cpp#L92-L100)：

```cpp
settings.rollPeriod = std::stoul(value);                  // string → unsigned long
settings.minLogLevel = static_cast<LogLevel>(std::stoi(value));  // string → int → 枚举
settings.enabledSources = std::stoul(value, nullptr, 16);  // 16 进制解析
```

### 7.5 易错点


| 坑                   | 说明                                            |
| :--------------------- | :------------------------------------------------ |
| `std::stoi` 抛异常   | 空字符串、非数字 →`std::invalid_argument`      |
| `std::stoul` 越界    | `"99999999999999999999"` → `std::out_of_range` |
| `<<` 用于整数        | `int x = 1 << 4;` 是位移，不是流插入！          |
| `+` 拼接 const char* | `const char* a = "a" + "b";` ❌ 不能这样拼接    |

### 7.6 练习题

**题 1**：把 `"rollPeriod=3600"` 解析成 key="rollPeriod"，value=3600
**题 2**：用 stringstream 把 `int x = 42` 转成字符串

---

## 8. 文件系统 filesystem

### 8.1 是什么

C++17 引入的**跨平台文件系统库**，替代 `opendir`/`stat`/`mkdir` 等平台相关 API。

### 8.2 常用 API

```cpp
#include <filesystem>
namespace fs = std::filesystem;

// 路径操作
fs::path p = "/data/log/app.log";
p.parent_path();        // "/data/log"
p.filename();           // "app.log"
p.stem();               // "app" (去扩展名)
p.extension();          // ".log"

// 判断
fs::exists(p);          // 文件/目录是否存在
fs::is_regular_file(p); // 是否是普通文件
fs::is_directory(p);    // 是否是目录

// 文件信息
fs::file_size(p);                    // 字节数
fs::last_write_time(p);              // 最后修改时间

// 创建/删除
fs::create_directory(p);             // 创建目录
fs::create_directories(p);           // 递归创建
fs::remove(p);                       // 删除文件
fs::remove_all(p);                   // 递归删除

// 遍历目录
for (const auto& entry : fs::directory_iterator("/data/log")) {
    std::cout << entry.path() << "\n";
}
```

### 8.3 项目实例

[LogReader.cpp:35-44](../service/LogServer/LogReader.cpp#L35-L44)：

```cpp
for (const auto& entry : std::filesystem::directory_iterator(dir)) {
    if (entry.is_regular_file() && entry.path().extension() == ".log") {
        LogFileInfo info;
        info.fileName = entry.path().filename().string();
        info.fileSize = std::filesystem::file_size(entry.path());
        info.createTime = std::filesystem::last_write_time(entry.path())
                          .time_since_epoch().count();
        info.sourceType = sourceType;
        files.push_back(info);
    }
}
```

[UsbMonitor.cpp:52-58](../service/LogServer/UsbMonitor.cpp#L52-L58)：

```cpp
bool UsbMonitor::checkUsbMounted() {
    std::filesystem::path mountPath(settings.usbMountPoint);
    return std::filesystem::exists(mountPath) 
        && std::filesystem::is_directory(mountPath);
}
```

### 8.4 易错点


| 坑                       | 说明                                             |
| :------------------------- | :------------------------------------------------- |
| 路径分隔符跨平台         | Windows 用`\`，Linux 用 `/`，`fs::path` 自动处理 |
| 遍历过程中修改目录       | 迭代器失效，可能崩溃                             |
| 中文路径                 | Windows 下 GBK 编码可能乱码，建议 UTF-8          |
| 不存在的路径取 file_size | 抛`filesystem_error` 异常                        |

### 8.5 练习题

**题 1**：写一个函数，统计某目录下所有 `.log` 文件的总大小

```cpp
uint64_t totalLogSize(const std::string& dir);
```

**题 2**：列出 `/tmp` 下所有子目录名

---

## 9. 类与对象的新特性

### 9.1 = default / = delete

```cpp
class Widget {
public:
    Widget() = default;                              // 让编译器生成默认构造
    ~Widget() = default;                             // 让编译器生成默认析构
    Widget(const Widget&) = delete;                  // 禁止拷贝
    Widget& operator=(const Widget&) = delete;       // 禁止赋值
};
```


| 写法        | 含义                                     |
| :------------ | :----------------------------------------- |
| `= default` | 让编译器生成默认实现（仍受访问权限约束） |
| `= delete`  | 禁止使用此函数（编译期报错）             |

### 9.2 override / final

```cpp
class Base {
public:
    virtual void foo() {}
    virtual void bar() final {}   // 不允许子类再覆盖 bar
};

class Derived : public Base {
public:
    void foo() override {}        // 明确告诉编译器"我在覆盖虚函数"
    // void foo(int) override;   // 编译错误！签名不匹配
};
```

### 9.3 nullptr

```cpp
// C++03
int* p = NULL;        // 二义性：0 还是 (void*)0？

// C++11
int* p = nullptr;     // 明确是空指针，类型安全
```

### 9.4 委托构造

```cpp
class Widget {
    int x_, y_;
public:
    Widget(int x, int y) : x_(x), y_(y) {}
    Widget() : Widget(0, 0) {}      // 委托给上面的构造函数
    Widget(int x) : Widget(x, 0) {} // 委托
};
```

### 9.5 enum class

```cpp
// 旧式 enum（C 风格，会污染命名空间）
enum Color { RED, GREEN, BLUE };
int x = RED;   // 合法，隐式转换

// 新式 enum class（C++11，类型安全）
enum class Color { Red, Green, Blue };
Color c = Color::Red;    // 必须加作用域
int x = c;               // ❌ 编译错误，不能隐式转 int
int x = static_cast<int>(c);   // 显式转换才行
```

### 9.6 项目实例

[Singleton.h:13-16](../service/PowerManagerService/include/Singleton.h#L13-L16)：

```cpp
private:
    Singleton() = default;                            // private + default
    ~Singleton() = default;
    Singleton(const Singleton&) = delete;            // 禁拷贝
    Singleton& operator=(const Singleton&) = delete;  // 禁赋值
```

[PowerManagerCommon.h:16-23](../service/PowerManagerService/include/PowerManagerCommon.h#L16-L23)：

```cpp
enum PowerMode {
    POWER_MODE_OFF        = 0,
    POWER_MODE_STR        = 1,
    POWER_MODE_ACTIVE     = 2,
    POWER_MODE_SHUTDOWN   = 3,
    POWER_MODE_RESTART    = 4,
    POWER_MODE_DEEP_SLEEP = 5
};
```

### 9.7 练习题

**题 1**：写一个不可拷贝、不可赋值的类 `NonCopyable`
**题 2**：把下面的旧 enum 改成 enum class

```cpp
enum LogLevel { VERBOSE, DEBUG, INFO, WARN, ERROR };
```

---

## 10. 强制类型转换

### 10.1 四种 cast

```cpp
// 1. static_cast：相关类型转换（数值、子类→父类）
double d = 3.14;
int i = static_cast<int>(d);    // 3

// 2. dynamic_cast：多态向下转型（带运行时检查）
class Base { virtual ~Base() {} };
class Derived : public Base {};
Base* b = new Derived;
Derived* d = dynamic_cast<Derived*>(b);   // 成功则非空，失败返回 nullptr

// 3. const_cast：增删 const
const int* cp = &x;
int* p = const_cast<int*>(cp);   // 去掉 const（慎用！）

// 4. reinterpret_cast：重解释内存（指针类型间互转）
void* raw = malloc(100);
int* pi = reinterpret_cast<int*>(raw);
```

### 10.2 项目实例

[EcdClient.cpp:100](../service/PowerManagerService/src/EcdClient.cpp#L100)：

```cpp
auto* data = (const PowerModeInfo*)msg->getPayloadBuffer();
// C 风格转换，等价于：
const PowerModeInfo* data = 
    reinterpret_cast<const PowerModeInfo*>(msg->getPayloadBuffer());
```

[LogConfig.cpp:98](../service/LogServer/LogConfig.cpp#L98)：

```cpp
settings.minLogLevel = static_cast<LogLevel>(std::stoi(value));
// int → enum，用 static_cast
```

### 10.3 选型决策树

```
要转的类型之间有关系吗？
│
├─ 有关（数值↔数值、子类→父类）
│   └─ static_cast
│
├─ 多态向下转型（父类→子类）
│   └─ dynamic_cast
│
├─ 要去 const 或加 const
│   └─ const_cast
│
└─ 完全不相关（指针↔指针、指针↔整数）
    └─ reinterpret_cast
```

### 10.4 易错点


| 坑                    | 说明                                                |
| :---------------------- | :---------------------------------------------------- |
| C 风格 cast 隐藏意图  | `(T*)x` 可能是 const_cast 也可能是 reinterpret_cast |
| dynamic_cast 性能     | 比 static_cast 慢（运行时 RTTI 查询）               |
| reinterpret_cast 误用 | 类型布局不兼容 → 访问未定义内存                    |

### 10.5 练习题

**题 1**：以下转换该用哪种 cast？

```cpp
void* buf = allocator();
MyStruct* p = ???(buf);              // ???
int x = 42;
double d = ???(x);                  // ???
const char* s = getStr();
char* m = ???(s);                   // ???
```

---

## 11. STL 容器与算法

### 11.1 常用容器

```cpp
// 顺序容器
std::vector<int> v = {1, 2, 3};        // 动态数组
std::list<int> l;                       // 双链表
std::deque<int> dq;                     // 双端队列
std::array<int, 5> arr;                 // 固定大小数组

// 关联容器（有序）
std::map<std::string, int> m;           // 红黑树，key 有序
std::multimap<int, int> mm;             // 允许重复 key
std::set<int> s;                        //有序集合

// 关联容器（无序，C++11）
std::unordered_map<std::string, int> um; // 哈希表，查找 O(1)
std::unordered_set<int> us;
```

### 11.2 选用建议


| 需求                   | 推荐                                    |
| :----------------------- | :---------------------------------------- |
| 频繁尾部增删、随机访问 | vector                                  |
| 频繁中间插入删除       | list                                    |
| key→value 查找        | unordered_map（默认）或 map（需有序时） |
| 去重                   | unordered_set                           |
| 固定大小数组           | array（替代 C 数组）                    |

### 11.3 vector 常用操作

```cpp
std::vector<int> v;

v.push_back(1);          // 末尾添加元素
v.emplace_back(42);      // 末尾原地构造（C++11，比 push_back 高效）
v.pop_back();            // 末尾删除
v.size();                // 元素个数
v.empty();               // 是否为空
v[0];                    // 访问（不检查越界）
v.at(0);                 // 访问（越界抛异常）
v.clear();               // 清空
v.resize(10);            // 改变大小

// 遍历
for (int x : v) { ... }              // C++11 range-based for
for (const auto& x : v) { ... }      // 不拷贝
```

### 11.4 range-based for

```cpp
std::vector<int> v = {1, 2, 3};

// 等价于：
// for (auto it = v.begin(); it != v.end(); ++it) { int x = *it; ... }
for (int x : v) {
    std::cout << x << "\n";
}

// 修改元素
for (int& x : v) {
    x *= 2;
}
```

### 11.5 STL 算法

```cpp
#include <algorithm>

std::vector<int> v = {3, 1, 4, 1, 5, 9, 2, 6};

// 排序
std::sort(v.begin(), v.end());

// 查找
std::find(v.begin(), v.end(), 4);
std::find_if(v.begin(), v.end(), [](int x){ return x > 5; });

// 遍历
std::for_each(v.begin(), v.end(), [](int x){ std::cout << x; });

// 计数
std::count(v.begin(), v.end(), 1);   // 1 出现的次数

// 拷贝筛选
std::vector<int> evens;
std::copy_if(v.begin(), v.end(), std::back_inserter(evens),
             [](int x){ return x % 2 == 0; });
```

### 11.6 项目实例

[LogExporter.cpp:68](../service/LogServer/LogExporter.cpp#L68)：

```cpp
filePaths.push_back(dir + "/" + file.fileName);
// 往 vector 末尾追加完整路径
```

### 11.7 练习题

**题 1**：用 `std::unordered_map` 统计一段字符串中每个单词出现的次数
**题 2**：用 `std::sort` + lambda 对 `vector<Student>` 按成绩降序排序

---

## 12. 函数对象与 bind

### 12.1 std::function

```cpp
#include <functional>

// 可以装任何可调用对象：函数指针、lambda、函数对象、bind 结果
std::function<int(int, int)> op;

op = [](int a, int b) { return a + b; };   // lambda
op = std::plus<int>();                      // 函数对象
op = [](int a, int b) { return a * b; };    // 改成乘法

std::cout << op(3, 4);   // 12
```

### 12.2 std::bind

```cpp
// 绑定参数、调整参数顺序
void foo(int a, int b, int c) { /* ... */ }

auto f1 = std::bind(foo, 1, 2, 3);          // 固定所有参数
auto f2 = std::bind(foo, std::placeholders::_1, 2, 3);  // 第 1 个参数待定
auto f3 = std::bind(foo, _2, _1, 3);        // 调换顺序

f2(10);     // 调用 foo(10, 2, 3)
f3(10, 20); // 调用 foo(20, 10, 3)

// 绑定成员函数
class Widget {
public:
    void method(int x) { /* ... */ }
};

Widget w;
auto m = std::bind(&Widget::method, &w, std::placeholders::_1);
m(42);   // 调用 w.method(42)
```

### 12.3 项目实例

[PowerManager.cpp:46-47](../service/PowerManagerService/src/PowerManager.cpp#L46-L47)：

```cpp
mEcdClient->setPowerModeHandler(
    std::bind(&PowerManager::handlePowerMode, this, std::placeholders::_1));
// 把成员函数 handlePowerMode 绑定到 this 对象上
// 等价于：
mEcdClient->setPowerModeHandler(
    [this](const PowerModeInfo& info) { handlePowerMode(info); });
```

**建议**：现代 C++ 优先用 lambda 替代 `std::bind`，更易读。

### 12.4 练习题

**题 1**：用 `std::function` 写一个简单的回调机制

```cpp
class Button {
    std::function<void()> onClick;
    // setOnClick()、click()
};
```

---

## 附录 A：现代 C++ 速查表

### A.1 头文件速查


| 特性                       | 头文件                                        |
| :--------------------------- | :---------------------------------------------- |
| `auto`、`decltype`         | `<decltype.hpp>` 内置，无需 include           |
| 智能指针                   | `<memory>`                                    |
| `std::move`/`std::forward` | `<utility>`                                   |
| lambda                     | 内置，无需 include                            |
| thread/mutex/condvar       | `<thread>`, `<mutex>`, `<condition_variable>` |
| chrono                     | `<chrono>`                                    |
| stringstream               | `<sstream>`                                   |
| stoi/stoul                 | `<string>`                                    |
| filesystem                 | `<filesystem>`                                |
| atomic                     | `<atomic>`                                    |
| function/bind              | `<functional>`                                |
| STL 算法                   | `<algorithm>`                                 |

### A.2 常用 API 一行速查

```cpp
// 智能指针
std::make_unique<T>(args)
std::make_shared<T>(args)
p.reset(), p.get(), p.use_count()
std::move(p)

// 并发
std::thread(func, args...)
std::mutex, std::lock_guard, std::unique_lock
std::condition_variable, cv.wait(lk, pred), cv.notify_one/all
std::atomic<T>, x.fetch_add(1)

// 时间
std::chrono::system_clock::now()
std::this_thread::sleep_for(std::chrono::seconds(1))
std::chrono::duration_cast<ms>(d).count()

// 文件系统
std::filesystem::exists(p), file_size(p), is_directory(p)
std::filesystem::directory_iterator(dir)

// 字符串
std::stoi(s), stoul(s), stod(s), to_string(x)
std::stringstream ss; ss << x; ss.str()

// 容器
v.push_back(x), emplace_back(args)
v.size(), empty(), clear()
m[key], m.find(key), m.insert({k, v})
```

---

## 附录 B：项目代码索引

### B.1 按特性索引


| 特性                   | 文件                  |      行号      |
| :----------------------- | :---------------------- | :--------------: |
| `auto`                 | LogExporter.cpp       |     36-37     |
| `make_unique`          | PowerManager.cpp      | 19, 27, 33, 39 |
| `make_shared`          | HelloWorldService.cpp |       41       |
| `std::move`            | PowerManager.cpp      |   71, 75, 79   |
| lambda                 | PowerManager.cpp      |       59       |
| `std::thread`          | UsbMonitor.cpp        |       21       |
| `std::mutex`           | PowerManager.cpp      |   58, 64, 90   |
| `condition_variable`   | PowerManager.cpp      |     59, 67     |
| `chrono`               | LogExporter.cpp       |     36-37     |
| `sleep_for`            | UsbMonitor.cpp        |       48       |
| `stringstream`         | LogExporter.cpp       |     38-39     |
| `put_time`             | LogExporter.cpp       |       39       |
| `std::stoi`/`stoul`    | LogConfig.cpp         |     92-100     |
| `filesystem`           | LogReader.cpp         |     35-44     |
| `push_back`            | LogExporter.cpp       |       68       |
| `= default`/`= delete` | Singleton.h           |     13-16     |
| `enum`                 | PowerManagerCommon.h  |     16-23     |
| `static_cast`          | LogConfig.cpp         |       98       |
| C 风格 cast            | EcdClient.cpp         |      100      |
| `std::bind`            | PowerManager.cpp      |     46-47     |

---

## 附录 C：推荐资源

### C.1 在线参考

- **cppreference.com**：https://zh.cppreference.com/w/cpp （最权威）
- **cpppatterns.com**：常见模式速查
- **compiler explorer**：https://godbolt.org/ （在线看汇编）

### C.2 书籍推荐


| 书名                      | 作者             | 适合阶段             |
| :-------------------------- | :----------------- | :--------------------- |
| C++ Primer 第五版         | Lippman          | 入门                 |
| Effective Modern C++      | Scott Meyers     | 进阶（**强烈推荐**） |
| C++ Concurrency in Action | Anthony Williams | 并发深入             |
| Effective STL             | Scott Meyers     | STL 专项             |

### C.3 项目实战

参考本项目目录：

- `service/PowerManagerService/`：智能指针 + 并发 + bind
- `service/LogServer/`：filesystem + chrono + stringstream
- `service/HelloWorldServer/`：shared_ptr + thread

---

**文档版本**：v1.0
**最后更新**：2026-08-24
**配套文档**：[ModernCpp_Deep.md](./ModernCpp_Deep.md) 深度+原理版
