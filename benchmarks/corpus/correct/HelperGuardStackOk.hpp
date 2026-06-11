#pragma once

#include <stdexcept>

class HelperGuardStackOk {
public:
    HelperGuardStackOk() : n(0) {}

    void push(int value) {
        ensure_has_room();
        data[n] = value;
        n += 1;
    }

    int top() const {
        ensure_not_empty();
        return data[n - 1];
    }

    int pop() {
        ensure_not_empty();
        n -= 1;
        return data[n];
    }

private:
    void ensure_has_room() const {
        if (n >= 16) {
            throw std::out_of_range("capacidad agotada");
        }
    }

    void ensure_not_empty() const {
        if (n <= 0) {
            throw std::out_of_range("pila vacía");
        }
    }

    int data[16];
    int n;
};
