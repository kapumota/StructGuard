#pragma once

#include <stdexcept>

class CircularQueueOk {
public:
    CircularQueueOk() : head(0), tail(0), n(0) {}

    bool empty() const {
        return n == 0;
    }

    int size() const {
        return n;
    }

    void enqueue(int value) {
        if (n >= 16) {
            throw std::out_of_range("capacidad agotada");
        }
        data[tail] = value;
        tail = (tail + 1) % 16;
        n += 1;
    }

    int dequeue() {
        if (n <= 0) {
            throw std::out_of_range("cola vacía");
        }
        int value = data[head];
        head = (head + 1) % 16;
        n -= 1;
        return value;
    }

private:
    int data[16];
    int head;
    int tail;
    int n;
};
