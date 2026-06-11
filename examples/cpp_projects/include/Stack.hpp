#pragma once

#include <cstddef>

namespace demo {

template <class T>
class Stack {
public:
    Stack();

    // ensures n == old(n) + 1
    void push(const T& value);

    // requires n > 0
    // ensures n == old(n) - 1
    T pop();

    // requires n > 0
    T top() const;

    // requires n > 0
    T peek() const;

    int size() const;

private:
    T data[16];
    int n;
};

}  // namespace demo
