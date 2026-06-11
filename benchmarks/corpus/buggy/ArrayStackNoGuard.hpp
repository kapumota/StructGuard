#pragma once

class ArrayStackNoGuard {
public:
    ArrayStackNoGuard() : n(0) {}

    void push(int value) {
        data[n] = value;
        n += 1;
    }

    int pop() {
        return data[--n];
    }

private:
    int data[16];
    int n;
};
