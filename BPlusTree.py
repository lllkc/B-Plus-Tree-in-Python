# -*-coding:utf-8 -*-
import bisect

import math
import unittest
from random import shuffle

__all__ = ['BPlusTree']


class _IdxNode(object):
    __slots__ = ('type', 'key', 'idx')

    def __init__(self, t):
        self.type = t  # 0:next level is _IdxNode，1：next level is _DataNode
        self.key = []
        self.idx = []

    def __repr__(self):
        return str(self.key)


class _DataNode(object):
    __slots__ = 'record'

    def __init__(self):
        self.record = []

    def __repr__(self):
        return str(self.record)


class BPlusTree(object):
    __slots__ = ('order', 'dataBlkSize', '_root')

    def __init__(self, m, l):
        self.order = m
        self.dataBlkSize = l
        self._root = None

    def insert(self, x):
        if self._root is None:
            self._root = _IdxNode(1)
            d = _DataNode()
            d.record.append(x)
            self._root.idx.append(d)
            return

        p = self._insert(x, self._root)

        # tree grows
        if p is not None:
            t = self._root
            self._root = _IdxNode(0)
            self._root.idx.append(t)
            self._root.idx.append(p)
            while p.type == 0:
                p = p.idx[0]
            d = p.idx[0]
            self._root.key.append(d.record[0])

    def find(self, x):
        return self._find(x)

    def delete(self, x):
        route = self._trace(x)
        if not self._present(route, x):
            raise ValueError("%r not present!" % x)
        self._delete(route)

    def _insert(self, x, node):
        i = bisect.bisect_left(node.key, x)

        if node.type == 0:
            new_node = self._insert(x, node.idx[i])
        else:
            new_node = self._insert_data(x, node.idx[i])

        if new_node is None:
            return None
        else:
            if node.type == 0:
                return self._add_idx_blk(node, new_node)
            else:
                return self._add_data_blk(node, new_node)

    def _insert_data(self, x, t):
        if len(t.record) < self.dataBlkSize:
            index = bisect.bisect_left(t.record, x)
            t.record.insert(index, x)
            return

        index = bisect.bisect_left(t.record, x)
        t.record.insert(index, x)

        new_node = _DataNode()
        max_ = self.dataBlkSize // 2 + 1
        new_node.record = t.record[max_:]
        t.record = t.record[:max_]

        return new_node

    def _add_idx_blk(self, t, new_node):
        p = new_node
        while p.type == 0:
            p = p.idx[0]
        min_ = p.idx[0].record[0]

        if len(t.idx) < self.order:
            index = bisect.bisect_left(t.key, min_)
            t.idx.insert(index + 1, new_node)
            t.key.insert(index, min_)
            return

        # split
        index = bisect.bisect_left(t.key, min_)
        t.idx.insert(index + 1, new_node)
        t.key.insert(index, min_)

        new_idx = _IdxNode(0)
        max_ = self.order // 2
        new_idx.idx = t.idx[max_ + 1:]
        new_idx.key = t.key[max_ + 1:]
        t.idx = t.idx[:max_ + 1]
        t.key = t.key[:max_]

        return new_idx

    def _add_data_blk(self, t, new_node):
        if len(t.idx) < self.order:
            index = bisect.bisect_left(t.key, new_node.record[0])
            t.idx.insert(index + 1, new_node)
            t.key.insert(index, new_node.record[0])
            return

        # todo: lend child to siblings
        # split
        index = bisect.bisect_left(t.key, new_node.record[0])
        t.idx.insert(index + 1, new_node)
        t.key.insert(index, new_node.record[0])

        new_idx = _IdxNode(1)
        max_ = self.order // 2
        new_idx.idx = t.idx[max_ + 1:]
        new_idx.key = t.key[max_ + 1:]
        t.idx = t.idx[:max_ + 1]
        t.key = t.key[:max_]

        return new_idx

    def _find(self, x):
        ancestry = self._trace(x)
        return self._present(ancestry, x)

    def _present(self, ancestry, x):
        if not ancestry:
            return False
        node, index = ancestry[-1]
        if isinstance(node, _DataNode):
            return x == node.record[index]
        return False

    def _trace(self, x):
        current = self._root
        route = []

        if current is None:
            return route
        while current.type == 0:
            i = bisect.bisect_right(current.key, x)
            route.append((current, i))
            current = current.idx[i]
        i = bisect.bisect_right(current.key, x)
        route.append((current, i))
        current = current.idx[i]
        record = current.record
        i = bisect.bisect_left(record, x)
        if i < len(record) and record[i] == x:
            route.append((current, i))

        return route

    def _delete(self, route):
        current, index = route.pop()

        minimum = int(math.ceil(self.dataBlkSize * 1.0 / 2))
        current.record.pop(index)
        if len(current.record) >= minimum:
            return

        parent, parent_idx = route[-1]
        left_sib = right_sib = None

        # borrow from left sibling
        if parent_idx:
            left_sib = parent.idx[parent_idx - 1]
            if len(left_sib.record) > minimum:
                borrowed = left_sib.record.pop()
                parent.key[parent_idx - 1] = borrowed
                current.record.insert(0, borrowed)
                return

        # then try right
        if parent_idx + 1 < len(parent.idx):
            right_sib = parent.idx[parent_idx + 1]
            if len(right_sib.record) > minimum:
                borrowed = right_sib.record.pop(0)
                parent.key[parent_idx] = right_sib.record[0]
                current.record.append(borrowed)
                return

        # if borrowing failed, join
        if left_sib:
            left_sib.record.extend(current.record)
            parent.key.pop(parent_idx - 1)
            parent.idx.pop(parent_idx)
            self._merge(route)
            return

        if right_sib:
            current.record.extend(right_sib.record)
            parent.key.pop(parent_idx)
            parent.idx.pop(parent_idx + 1)
            self._merge(route)
            return

    def _merge(self, route):
        current, index = route.pop()
        if not route:
            return
        minimum = int(math.ceil(self.order * 1.0 / 2))
        if len(current.idx) >= minimum:
            return

        parent, parent_idx = route[-1]
        left_sib = right_sib = None

        # borrow from left sibling
        if parent_idx:
            left_sib = parent.idx[parent_idx - 1]
            if len(left_sib.idx) > minimum:
                idx_borrowed = left_sib.idx.pop()
                key_borrowed = left_sib.key.pop()
                key_parent = parent.key[parent_idx - 1]
                current.key.insert(0, key_parent)
                current.idx.insert(0, idx_borrowed)
                parent.key[parent_idx - 1] = key_borrowed
                return

        # then try right
        if parent_idx + 1 < len(parent.idx):
            right_sib = parent.idx[parent_idx + 1]
            if len(right_sib.idx) > minimum:
                idx_borrowed = right_sib.idx.pop(0)
                key_borrowed = right_sib.key.pop(0)
                key_parent = parent.key[parent_idx]
                current.key.append(key_parent)
                current.idx.append(idx_borrowed)
                parent.key[parent_idx] = key_borrowed
                return

        # if borrowing failed, join
        if left_sib:
            left_sib.idx.extend(current.idx)
            left_sib.key.append(parent.key.pop(parent_idx - 1))
            left_sib.key.extend(current.key)
            parent.idx.pop(parent_idx)
            # change root
            if len(route) == 1 and not len(parent.key):
                ori_root = self._root
                self._root = left_sib
                del ori_root
                return
            self._merge(route)
            return

        if right_sib:
            current.idx.extend(right_sib.idx)
            current.key.append(parent.key.pop(parent_idx))
            current.key.extend(right_sib.key)
            parent.idx.pop(parent_idx + 1)
            # change root
            if len(route) == 1 and not len(parent.key):
                ori_root = self._root
                self._root = current
                del ori_root
                return
            self._merge(route)
            return

    def __repr__(self):
        def level_traverse(node, accumulation, depth):
            accumulation.append(("\t" * depth) + repr(node))
            if isinstance(node, _IdxNode):
                for child in node.idx:
                    level_traverse(child, accumulation, depth + 1)

        a = []
        level_traverse(self._root, a, 0)
        return "\n".join(a)


class BPlusTreeTests(unittest.TestCase):
    def setUp(self):
        self.seq = range(1, 1000)

    def test_ordered(self):
        bpt = BPlusTree(4, 4)
        for i in self.seq:
            bpt.insert(i)
        for i in self.seq:
            self.assertTrue(bpt.find(i))
        for i in self.seq:
            bpt.delete(i)
            self.assertFalse(bpt.find(i))

    def test_random(self):
        bpt = BPlusTree(4, 4)

        shuffle(self.seq)

        for i in self.seq:
            bpt.insert(i)
        for i in self.seq:
            self.assertTrue(bpt.find(i))
        for i in self.seq:
            bpt.delete(i)
            self.assertFalse(bpt.find(i))


if __name__ == '__main__':
    BPlusTreeTests.main()
