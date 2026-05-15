#pragma once

class Queue {
private:
    int size_;
    int capacity_;
    int front_;
    int back_;

public:
    // invariant: size_ >= 0
    // invariant: size_ <= capacity_
    // invariant: front_ >= 0
    // invariant: back_ >= 0

    // ensures: size_ == 0
    // ensures: capacity_ == 100
    Queue() {
        size_ = 0;
        capacity_ = 100;
        front_ = 0;
        back_ = 0;
    }

    // requires: size_ < capacity_
    // ensures: size_ == old(size_) + 1
    void enqueue(int x) {
        size_ = size_ + 1;
        back_ = back_ + 1;
    }

    // requires: !empty()
    // ensures: size_ == old(size_) - 1
    int dequeue() {
        size_ = size_ - 1;
        front_ = front_ + 1;
        return 0;
    }

    // ensures: result == (size_ == 0)
    bool empty() const {
        return size_ == 0;
    }
};
