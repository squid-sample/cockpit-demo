# C++11 / 14 / 17 常用新特性（极简速查）

> 每个特性：**一句话作用 + 一段最小代码**。看代码就懂，不啰嗦。

---

## C++11

### 1. auto
让编译器自动推导变量类型，省得写又长又重复的类型名。

```cpp
auto it = m.begin();               // std::map<...>::iterator
auto p = std::make_shared<Foo>();  // std::shared_ptr<Foo>
auto x = 3.14;                     // double
```

### 2. decltype
取一个表达式/变量的类型，用来声明另一个同类型变量。

```cpp
int a = 1;
decltype(a) b = 2;   // b 也是 int
```

### 3. 右值引用与移动语义
`&&` 接住临时对象（右值），`std::move` 把对象转成右值，避免拷贝。

```cpp
std::string s = "hello";
std::string t = std::move(s);  // s 被掏空，t 直接接管内存，不拷贝
```

### 4. 智能指针
自动释放堆内存，不用手写 delete。`unique_ptr` 独占，`shared_ptr` 共享（带引用计数）。

```cpp
std::unique_ptr<Foo> u = std::make_unique<Foo>();
std::shared_ptr<Bar> s = std::make_shared<Bar>();
// 出作用域自动 delete
```

### 5. Lambda
在代码里直接写匿名函数，常配合 STL 算法或回调用。

```cpp
auto add = [](int a, int b) { return a + b; };
add(1, 2);  // 3

std::sort(v.begin(), v.end(), [](int a, int b) { return a > b; });
```

### 6. nullptr
替代 `NULL`/`0`，是真正的空指针（类型是 nullptr_t），避免"0 到底是 int 还是 指针"的歧义。

```cpp
void f(int);
void f(int*);
f(0);        // 调 f(int)
f(nullptr);  // 调 f(int*)
```

### 7. 范围 for
简化容器遍历，不用写迭代器。

```cpp
int arr[] = {1, 2, 3};
for (int x : arr) std::cout << x;
std::vector<int> v = {1, 2, 3};
for (int& x : v) x *= 2;  // 引用才能改原元素
```

### 8. 列表初始化
`{}` 统一初始化语法，还能防窄化转换。

```cpp
int a{5};
std::vector<int> v{1, 2, 3};
struct Foo { int x; double y; };
Foo f{1, 2.0};
int b = 3.14;     // 隐式截断，编译能过
int c{3.14};      // ❌ 报错，防窄化
```

### 9. emplace 与就地构造
`emplace_back` / `emplace` 直接用参数在容器内原地构造，省掉先构造再拷贝/移动。

```cpp
std::vector<std::pair<int,int>> v;
v.emplace_back(1, 2);   // 直接构造 pair
v.push_back({1, 2});    // 先构造 pair 临时对象再移动进去
```

### 10. enum class
强类型枚举，不会隐式转 int，名字不污染外层作用域。

```cpp
enum class Color { Red, Green, Blue };
Color c = Color::Red;
int x = c;            // ❌ 不能隐式转
int y = (int)c;       // OK，显式转
```

### 11. 委托构造与继承构造
- 委托构造：一个构造函数调用另一个构造函数，省重复代码
- 继承构造：派生类用 `using` 直接继承基类构造函数

```cpp
struct Foo {
    int a, b;
    Foo(int x, int y) : a(x), b(y) {}
    Foo(int x) : Foo(x, 0) {}        // 委托给上面那个
};
struct Bar : Foo {
    using Foo::Foo;                  // 继承基类构造函数
};
Bar b(1, 2);  // 直接用 Foo(int,int)
```

### 12. =default / =delete
显式控制特殊成员函数：要默认实现就 `=default`，禁用就 `=delete`。

```cpp
struct Foo {
    Foo() = default;                          // 用默认构造
    Foo(const Foo&) = delete;                 // 禁止拷贝
    Foo& operator=(const Foo&) = delete;      // 禁止赋值
};
```

### 13. override / final
- `override`：明确告诉编译器"我在重写虚函数"，写错了（签名不匹配）编译报错
- `final`：禁止派生类再重写

```cpp
struct Base { virtual void f(); };
struct Derived : Base {
    void f() override;        // 签名不对编译器会报错
};
struct Last final : Derived {};  // 不能再继承
```

### 14. constexpr
声明编译期常量表达式函数/变量，结果可在编译期算出来。

```cpp
constexpr int square(int x) { return x * x; }
int arr[square(3)];   // 编译期就有 9，能当数组大小
```

### 15. thread / mutex / atomic
标准库的并发原语。

```cpp
std::thread t([]{ /* 子线程 */ });
t.join();

std::mutex m;
std::lock_guard<std::mutex> lk(m);  // RAII 加锁，出作用域自动解
shared_data++;

std::atomic<int> counter{0};
counter++;   // 原子操作，无线索安全
```

### 16. std::array / std::tuple
- `array`：固定大小的栈上数组，比原生数组多了 size() 和迭代器接口
- `tuple`：把不同类型打包在一起，函数想返多个值时用

```cpp
std::array<int, 3> a = {1, 2, 3};
for (int x : a) {}

std::tuple<int, std::string, double> t{1, "hi", 3.14};
auto [id, name, val] = t;  // C++17 才行
```

### 17. 模板别名 using
给长模板名起短别名，替代 typedef（typedef 不支持模板）。

```cpp
template<typename T> using Vec = std::vector<T>;
Vec<int> v = {1, 2, 3};  // 等价 std::vector<int>

using String = std::string;  // 也能给普通类型起别名
```

---

## C++14

### 1. 函数返回 auto
返回类型让编译器推导，不用手写返回类型。

```cpp
auto add(int a, int b) { return a + b; }   // 返回 int
```

### 2. 泛型 Lambda
Lambda 参数用 auto，相当于模板。

```cpp
auto add = [](auto a, auto b) { return a + b; };
add(1, 2);        // int
add(1.0, 2.0);    // double
add(std::string("a"), std::string("b"));
```

### 3. std::make_unique
和 make_shared 配对的工厂函数，安全地构造 unique_ptr。

```cpp
auto p = std::make_unique<Foo>(args...);
// 比 Foo* p = new Foo(args) 安全：不漏 delete，异常安全
```

### 4. 变量模板
模板化的变量，常给数学常数、配置值用。

```cpp
template<typename T>
constexpr T pi = T(3.14159265358979);
double d = pi<double>;     // 3.14159...
float  f = pi<float>;      // 3.14159f
```

### 5. 数字字面量分隔符与二进制字面量
`'` 给数字加分隔符让长数好读；`0b` 写二进制。

```cpp
int big = 1'000'000;      // 一百万，下划线只起视觉作用
int mask = 0b1010'1100;   // 二进制写法
```

### 6. decltype(auto)
保留表达式的精确类型（含引用和 const），普通 auto 会丢掉这些。

```cpp
int& f();
auto x = f();              // int（丢了引用）
decltype(auto) y = f();    // int&（保留引用）
```

### 7. constexpr 放宽
C++11 的 constexpr 函数只能一个 return，C++14 放开了——允许 if、循环、多语句。

```cpp
constexpr int factorial(int n) {
    int r = 1;
    for (int i = 2; i <= n; ++i) r *= i;   // C++14 才能在 constexpr 里写
    return r;
}
```

---

## C++17

### 1. 结构化绑定
把 pair / tuple / struct 的成员一次性拆给多个变量，省去手写 `std::get<>`。

```cpp
std::pair p = {1, std::string("hi")};
auto [id, name] = p;        // id=1, name="hi"

std::map<int, std::string> m = {{1, "a"}, {2, "b"}};
for (const auto& [k, v] : m) std::cout << k << ":" << v;
```

### 2. if / switch 带初始化器
在条件里写初始化语句，作用域限定在 if 内，少污染外层。

```cpp
if (auto it = m.find(key); it != m.end()) {
    use(it->second);   // it 只在这个 if 块里有效
}

switch (auto x = get(); x) {
    case 1: ...
}
```

### 3. std::optional
表示"可能没有值"，替代"用 -1 / nullptr / 哨兵值"这种约定。

```cpp
std::optional<int> find_id(const std::string& name) {
    if (name == "x") return 42;
    return std::nullopt;   // 没找到
}
auto r = find_id("x");
if (r) std::cout << *r;     // 42
```

### 4. std::variant
类型安全的 union，任一时刻只装一个类型，访问时必须正确匹配，不会越界。

```cpp
std::variant<int, std::string, double> v;
v = 42;                    // 装 int
v = "hi";                  // 现在装 string
std::cout << std::get<std::string>(v);
std::visit([](auto&& x) { std::cout << x; }, v);  // 通用访问
```

### 5. std::any
装任意类型（C 风格 void* 的安全版），但访问要 any_cast 对类型。

```cpp
std::any a = 42;
a = std::string("hi");
std::cout << std::any_cast<std::string>(a);  // 必须类型对上
```

### 6. std::string_view
**不拥有字符串**，只引用别处的字符串片段。传参用它代替 `const string&` 零拷贝、还能接 C 字符串/字符数组。

```cpp
void print(std::string_view s);   // 不分配内存
print("hello");
print(std::string("hello"));
print(some_substr_of_another_string);

// 注意：被引用的字符串活着 string_view 才有效，否则悬空
```

### 7. std::filesystem
跨平台文件系统操作：路径、遍历目录、查大小/类型、复制/删除。

```cpp
namespace fs = std::filesystem;
for (const auto& e : fs::directory_iterator("/tmp")) {
    std::cout << e.path() << " size=" << fs::file_size(e) << "\n";
}
fs::create_directories("a/b/c");
auto sz = fs::file_size("/tmp/x.log");
```

### 8. 并行算法
STL 算法加执行策略参数，能并行/向量化跑。

```cpp
#include <execution>
std::vector<int> v(1'000'000);
std::sort(std::execution::par, v.begin(), v.end());   // 并行排序
std::for_each(std::execution::par_unseq, v.begin(), v.end(), f);
```

### 9. 折叠表达式
展开变参模板的参数包，不用再写递归模板。

```cpp
template<typename... Ts>
auto sum(Ts... args) {
    return (args + ...);   // 一元右折叠：((a1+a2)+a3)+...
}
sum(1, 2, 3, 4);   // 10
```

### 10. if constexpr
编译期分支，不满足的分支**直接丢弃不实例化**，模板内根据类型选代码用。

```cpp
template<typename T>
void f(T x) {
    if constexpr (std::is_integral_v<T>)
        std::cout << "整数:" << x;
    else
        std::cout << "其他:" << x;   // T 是 string 时这段代码不存在
}
```

### 11. 内联变量
头文件里定义的变量加 `inline`，多个 .cpp 包含不会重定义，便于写头文件库。

```cpp
// header.h
inline int g_count = 0;
inline struct Config { int x = 0; } g_cfg;
```

### 12. 类模板参数推导 CTAD
类模板构造时省略 `<类型参数>`，编译器从构造参数推导。

```cpp
std::pair p(1, 2.0);           // std::pair<int, double>
std::vector v = {1, 2, 3};     // std::vector<int>
std::lock_guard lk(m);         // std::lock_guard<std::mutex>
```

### 13. 标准属性
- `[[nodiscard]]`：返回值不能忽略
- `[[maybe_unused]]`：可能不用的变量/参数，别警告
- `[[fallthrough]]`：switch 故意穿透，别警告

```cpp
[[nodiscard]] int compute();
auto x = compute();   // OK
compute();            // ⚠️ 警告

void f(int x, [[maybe_unused]] int debug) {
    [[maybe_unused]] int y = 0;
}

switch (n) {
    case 1: prep();  [[fallthrough]];
    case 2: run();
}
```

### 14. 嵌套命名空间简写
多层命名空间一行写完。

```cpp
namespace A::B::C {
    void f();
}
// 等价
// namespace A { namespace B { namespace C { void f(); } } }
```

### 15. std::byte
类型安全的字节类型，不混淆整数运算。

```cpp
std::byte b{0xFF};
b |= std::byte{0x10};
int n = std::to_integer<int>(b);
```

### 16. std::invoke
统一调用可调用对象（函数、函数指针、成员函数、成员指针、lambda）。

```cpp
struct Foo { void f() { } int x = 0; };
Foo obj;
std::invoke(&Foo::f, obj);              // 调成员函数
int x = std::invoke(&Foo::x, obj);      // 访问成员
std::invoke([] { /*...*/ });            // 调 lambda
```

---

## 版本演进速查

| 版本 | 主线主题 | 必记 5 个 |
|---|---|---|
| C++11 | 现代 C++ 奠基 | auto / 智能指针 / Lambda / 移动语义 / 右值引用 |
| C++14 | C++11 补丁 | 函数返回 auto / 泛型 Lambda / make_unique |
| C++17 | 实用大版本 | 结构化绑定 / optional / variant / string_view / filesystem |
