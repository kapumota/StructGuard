#pragma once

#include <stdexcept>

class ArrayStackOk {
public:
    ArrayStackOk() : n(0) {}

    bool empty() const {
        return n == 0;
    }

    int size() const {
        return n;
    }

    void push(int value) {
        if (n >= 16) {
            throw std::out_of_range("capacidad agotada");
        }
        data[n] = value;
        n += 1;
    }

    int top() const {
        if (n <= 0) {
            throw std::out_of_range("pila vacía");
        }
        return data[n - 1];
    }

    int pop() {
        if (n <= 0) {
            throw std::out_of_range("pila vacía");
        }
        n -= 1;
        return data[n];
    }

private:
    int data[16];
    int n;
};
