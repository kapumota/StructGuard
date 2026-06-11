#pragma once

class VectorMemoryLeak {
public:
    explicit VectorMemoryLeak(int capacity) : data(new int[capacity]), n(0), cap(capacity) {}

    void push(int value) {
        data[n] = value;
        n += 1;
    }

private:
    int* data;
    int n;
    int cap;
};
