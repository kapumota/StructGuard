#pragma once

class QueueWrongEnd {
public:
    QueueWrongEnd() : head(0), tail(0), n(0) {}

    void enqueue(int value) {
        data[tail] = value;
        tail += 1;
        n += 1;
    }

    int dequeue() {
        n -= 1;
        return data[--tail];
    }

private:
    int data[16];
    int head;
    int tail;
    int n;
};
