#ifndef __SINGLETON_H__
#define __SINGLETON_H__

template<typename T>
class Singleton {
public:
    static T* instance() {
        static T inst;
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

#endif
