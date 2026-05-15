#pragma once

class Stack {
private:
    int data_[100];
    int size_;
    int capacity_;

public:
    // invariant: size_ >= 0
    // invariant: size_ <= capacity_

    // ensures: size_ == 0
    // ensures: capacity_ == 100
    Stack() {
        size_ = 0;
        capacity_ = 100;
    }

    // ensures: result == size_
    int size() const {
        return size_;
    }

    // ensures: result == (size_ == 0)
    bool empty() const {
        return size_ == 0;
    }

    // requires: size_ < capacity_
    // ensures: size_ == old(size_) + 1
    void push(int x) {
        size_ = size_ + 1;
    }

    // requires: !empty()
    // ensures: size_ == old(size_) - 1
    int pop() {
        size_ = size_ - 1;
        return 0;
    }
};
