#pragma once

class BuggyStack {
private:
    int size_;
    int capacity_;

public:
    // invariant: size_ >= 0
    // invariant: size_ <= capacity_

    // ensures: size_ == 0
    // ensures: capacity_ == 100
    BuggyStack() {
        size_ = 0;
        capacity_ = 100;
    }

    // ensures: size_ == old(size_) - 1
    int pop() {
        size_ = size_ - 1;
        return 0;
    }
};
