class TreeNode:
    def __init__(self, name=None):
        self.root = self
        self.father = None
        self.name = name
        self.son = []
        self.depth = 0
        self.index = [0]
        self.dirty = False

        self.former_section = []
        self.subsection = []

    def add_son(self, subsection):
        subsection.father = self
        subsection.root = self.root
        subsection.index = self.index + [len(self.son)]
        subsection.depth = self.depth + 1
        self.son.append(subsection)
        root = self
        while root.father:
            if not root.dirty:
                root.dirty = True
                root = root.father
            else:
                break
            
    def delete_son(self, subsection):
        if subsection in self.son:
            self._delete_subtree(subsection)
            self.son.remove(subsection)
            root = self
            while root.father:
                if not root.dirty:
                    root.dirty = True
                    root = root.father
                else:
                    break

    def _delete_subtree(self, node):
        for child in node.son:
            self._delete_subtree(child)
        del node

    def update_section(self):
        preorder_result = []

        def traverse(node):
            nonlocal preorder_result
            node.former_section = preorder_result.copy()
            preorder_result.append(node)
            for son in node.son:
                node.subsection.append(son)
                traverse(son)
                node.subsection.extend(son.subsection)

        traverse(self)

    @property
    def is_leaf(self):
        return len(self.son) == 0

    @property
    def all_section(self):
        result = [self]
        result.extend(self.subsection)
        return result
    
    @property
    def number_index(self):
        index = self.index.copy()
        index.pop(0)
        if len(index) == 0:
            index_str = "0."
        elif len(index) == 1:
            index_str = str(index[0]+1) + "."
        else:
            index_str = ".".join([str(i+1) for i in index])
        return index_str

