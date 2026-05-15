#pragma once

class StackInitializerOk {
  int size_;
  int capacity_;
public:
  // invariant: size_ >= 0
  // invariant: size_ <= capacity_
  // invariant: capacity_ >= 1
  // ensures: size_ == 0
  // ensures: capacity_ == 10
  StackInitializerOk() : size_(0), capacity_(10) {}

  // ensures: result == (size_ == 0)
  bool empty() const { return size_ == 0; }
};
