
# -*- coding: utf-8 -*-
#
#
# PyRates software framework for flexible implementation of neural 
# network model_templates and simulations. See also:
# https://github.com/pyrates-neuroscience/PyRates
# 
# Copyright (C) 2017-2018 the original authors (Richard Gast and 
# Daniel Rose), the Max-Planck-Institute for Human Cognitive Brain 
# Sciences ("MPI CBS") and contributors
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>
# 
# CITATION:
# 
# Richard Gast and Daniel Rose et. al. in preparation
"""
"""
from copy import copy
from typing import Iterator

from pyrates.ir.abc import AbstractBaseIR
from pyrates.ir.operator_graph import OperatorGraph

__author__ = "Daniel Rose"
__status__ = "Development"


class NodeIR(AbstractBaseIR):

    __slots__ = ["_op_graph", "values"]

    def __init__(self, operators: list = None, values: dict = None, template: str=None):

        super().__init__(template)
        self._op_graph = OperatorGraph(operators)
        self.values = values

    @property
    def op_graph(self):
        return self._op_graph

    def getitem_from_iterator(self, key: str, key_iter: Iterator[str]):
        """Alias for self.op_graph.getitem_from_iterator"""

        return self.op_graph.getitem_from_iterator(key, key_iter)

    def __iter__(self):
        """Return an iterator containing all operator labels in the operator graph."""
        return iter(self.op_graph)

    @property
    def operators(self):
        return self.op_graph.operators

    def __hash__(self):
        raise NotImplementedError


class VectorizedNodeIR(AbstractBaseIR):
    """Alternate version of NodeIR that takes a full NodeIR as input and creates a vectorized form of it."""

    __slots__ = ["_op_graph", "values"]

    def __init__(self, node_ir: NodeIR):

        super().__init__(node_ir.template)
        self._op_graph = node_ir.op_graph.copy()
        values = {}
        # reformat all values to be lists of themselves (adding an outer vector dimension)
        for op_key, value_dict in node_ir.values.items():
            op_values = {}
            for var_key, value in value_dict.items():
                op_values[var_key] = [value]
            values[op_key] = copy(op_values)
        self.values = values

    @property
    def op_graph(self):
        return self._op_graph

    def getitem_from_iterator(self, key: str, key_iter: Iterator[str]):
        """Alias for self.op_graph.getitem_from_iterator"""

        return self.op_graph.getitem_from_iterator(key, key_iter)

    def __iter__(self):
        """Return an iterator containing all operator labels in the operator graph."""
        return iter(self.op_graph)

    @property
    def operators(self):
        return self.op_graph.operators

    def __hash__(self):
        raise NotImplementedError