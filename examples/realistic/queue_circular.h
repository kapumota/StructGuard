#pragma once

class CircularQueue {
private:
    int data_[8];
    int size_;
    int capacity_;
    int head_;
    int tail_;
public:
    // invariant: size_ >= 0
    // invariant: size_ <= capacity_
    // invariant: head_ >= 0
    // invariant: tail_ >= 0
    CircularQueue() : size_(0), capacity_(8), head_(0), tail_(0) {}

    // requires: size_ < capacity_
    // ensures: size_ == old(size_) + 1
    void enqueue(int value) {
        if (size_ < capacity_) {
            data_[tail_] = value;
            tail_ = (tail_ + 1) % capacity_;
            size_++;
        }
    }

    // requires: size_ > 0
    // ensures: size_ == old(size_) - 1
    void dequeue() {
        if (size_ > 0) {
            head_ = (head_ + 1) % capacity_;
            size_--;
        }
    }

    // requires: size_ > 0
    int front() const { return data_[head_]; }
};
