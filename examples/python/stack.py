# invariant: self.n >= 0
class Stack:
    # ensures: self.n == 0
    def __init__(self):
        self.n = 0
    # ensures: self.n == old(self.n) + 1
    def push(self, x):
        self.n += 1
    # requires: self.n > 0
    # ensures: self.n == old(self.n) - 1
    def pop(self):
        self.n -= 1
        return 0
