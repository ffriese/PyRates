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

"""Wraps tensorflow such that it's low-level functions can be used by PyRates to create and simulate a compute graph.
"""

# external imports
from typing import Optional, Dict, Callable, List, Any, Union
import os
import sys
from shutil import rmtree
import numpy as np
from numpy import f2py

# pyrates internal imports
from .numpy_backend import NumpyBackend, PyRatesAssignOp, PyRatesIndexOp, PyRatesOp, CodeGen

# meta infos
__author__ = "Richard Gast"
__status__ = "development"

module_counter = 0


class FortranOp(PyRatesOp):

    def _generate_func(self):
        return generate_func(self)

    @classmethod
    def _process_args(cls, args, results, constants_to_num=False):
        """Parses arguments to function into argument names that are added to the function call and argument values
        that can used to set up the return line of the function.
        """
        return super()._process_args(args, results, constants_to_num=constants_to_num)


class FortranIndexOp(PyRatesIndexOp):
    def _generate_func(self):
        return generate_func(self)


class FortranAssignOp(PyRatesAssignOp):

    def _generate_func(self):
        idx = self._op_dict['arg_names'].index('y_delta')
        ndim = self._op_dict['args'][idx].shape
        return generate_func(self, return_key='y_delta', omit_assign=True, return_dim=ndim, return_intent='out')

    def eval(self):
        result = self._callable(*self.args[1:])
        self._check_numerics(result, self.name)
        return result


class FortranBackend(NumpyBackend):

    idx_l, idx_r = "(", ")"
    idx_start = 1

    def __init__(self,
                 ops: Optional[Dict[str, str]] = None,
                 dtypes: Optional[Dict[str, object]] = None,
                 name: str = 'net_0',
                 float_default_type: str = 'float32',
                 imports: Optional[List[str]] = None,
                 build_dir: Optional[str] = None,
                 pyauto_compat: bool = False
                 ) -> None:
        """Instantiates numpy backend, i.e. a compute graph with numpy operations.
        """

        # define operations and datatypes of the backend
        ################################################

        # base math operations
        ops_f = {"+": {'name': "fortran_add", 'call': "+"},
                 "-": {'name': "fortran_subtract", 'call': "-"},
                 "*": {'name': "fortran_multiply", 'call': "*"},
                 "/": {'name': "fortran_divide", 'call': "/"},
                 "%": {'name': "fortran_modulo", 'call': "MODULO"},
                 "^": {'name': "fortran_power", 'call': "**"},
                 "**": {'name': "fortran_power_float", 'call': "**"},
                 "@": {'name': "fortrandot", 'call': ""},
                 ".T": {'name': "fortrantranspose", 'call': ""},
                 ".I": {'name': "fortraninvert", 'call': ""},
                 ">": {'name': "fortrangreater", 'call': ">"},
                 "<": {'name': "fortranless", 'call': "<"},
                 "==": {'name': "fortranequal", 'call': "=="},
                 "!=": {'name': "fortran_not_equal", 'call': "!="},
                 ">=": {'name': "fortran_greater_equal", 'call': ">="},
                 "<=": {'name': "fortran_less_equal", 'call': "<="},
                 "=": {'name': "assign", 'call': "="},
                 "+=": {'name': "assign_add", 'call': ""},
                 "-=": {'name': "assign_subtract", 'call': ""},
                 "*=": {'name': "assign_multiply", 'call': ""},
                 "/=": {'name': "assign_divide", 'call': ""},
                 "neg": {'name': "negative", 'call': "-"},
                 "sin": {'name': "fortran_sin", 'call': "SIN"},
                 "cos": {'name': "fortran_cos", 'call': "COS"},
                 "tan": {'name': "fortran_tan", 'call': "TAN"},
                 "atan": {'name': "fortran_atan", 'call': "ATAN"},
                 "abs": {'name': "fortran_abs", 'call': "ABS"},
                 "sqrt": {'name': "fortran_sqrt", 'call': "SQRT"},
                 "sq": {'name': "fortran_square", 'call': ""},
                 "exp": {'name': "fortran_exp", 'call': "EXP"},
                 "max": {'name': "fortran_max", 'call': "MAX"},
                 "min": {'name': "fortran_min", 'call': "MIN"},
                 "argmax": {'name': "fortran_transpose", 'call': "ARGMAX"},
                 "argmin": {'name': "fortran_argmin", 'call': "ARGMIN"},
                 "round": {'name': "fortran_round", 'call': ""},
                 "sum": {'name': "fortran_sum", 'call': ""},
                 "mean": {'name': "fortran_mean", 'call': ""},
                 "concat": {'name': "fortran_concatenate", 'call': ""},
                 "reshape": {'name': "fortran_reshape", 'call': ""},
                 "append": {'name': "fortran_append", 'call': ""},
                 "shape": {'name': "fortran_shape", 'call': ""},
                 "dtype": {'name': "fortran_dtype", 'call': ""},
                 'squeeze': {'name': "fortran_squeeze", 'call': ""},
                 'expand': {'name': 'fortran_expand', 'call': ""},
                 "roll": {'name': "fortran_roll", 'call': ""},
                 "cast": {'name': "fortran_cast", 'call': ""},
                 "randn": {'name': "fortran_randn", 'call': ""},
                 "ones": {'name': "fortran_ones", 'call': ""},
                 "zeros": {'name': "fortran_zeros", 'call': ""},
                 "range": {'name': "fortran_arange", 'call': ""},
                 "softmax": {'name': "pyrates_softmax", 'call': ""},
                 "sigmoid": {'name': "pyrates_sigmoid", 'call': ""},
                 "tanh": {'name': "fortran_tanh", 'call': "TANH"},
                 "index": {'name': "pyrates_index", 'call': "pyrates_index"},
                 "mask": {'name': "pyrates_mask", 'call': ""},
                 "group": {'name': "pyrates_group", 'call': ""},
                 "asarray": {'name': "fortran_asarray", 'call': ""},
                 "no_op": {'name': "pyrates_identity", 'call': ""},
                 "interpolate": {'name': "pyrates_interpolate", 'call': ""},
                 "interpolate_1d": {'name': "pyrates_interpolate_1d", 'call': ""},
                 "interpolate_nd": {'name': "pyrates_interpolate_nd", 'call': ""},
                 }
        if ops:
            ops_f.update(ops)
        self.pyauto_compat = pyauto_compat
        super().__init__(ops=ops_f, dtypes=dtypes, name=name, float_default_type=float_default_type,
                         imports=imports, build_dir=build_dir)
        self._imports = []
        self.npar = 0
        self.ndim = 0
        self._auto_files_generated = False

    def compile(self, build_dir: Optional[str] = None, decorator: Optional[Callable] = None, **kwargs) -> tuple:
        """Compile the graph layers/operations. Creates python files containing the functions in each layer.

        Parameters
        ----------
        build_dir
            Directory in which to create the file structure for the simulation.
        decorator
            Decorator function that should be applied to the right-hand side evaluation function.
        kwargs
            decorator keyword arguments

        Returns
        -------
        tuple
            Contains tuples of layer run functions and their respective arguments.

        """

        # preparations
        ##############

        # remove empty layers and operators
        new_layer_idx = 0
        for layer_idx, layer in enumerate(self.layers.copy()):
            for op in layer.copy():
                if op is None:
                    layer.pop(layer.index(op))
            if len(layer) == 0:
                self.layers.pop(new_layer_idx)
            else:
                new_layer_idx += 1

        # create directory in which to store rhs function
        orig_path = os.getcwd()
        if build_dir:
            os.makedirs(build_dir, exist_ok=True)
        dir_name = f"{build_dir}/pyrates_build" if build_dir and "/pyrates_build" not in build_dir else "pyrates_build"
        try:
            os.mkdir(dir_name)
        except FileExistsError:
            pass
        os.chdir(dir_name)
        try:
            os.mkdir(self.name)
        except FileExistsError:
            rmtree(self.name)
            os.mkdir(self.name)
        for key in sys.modules.copy():
            if self.name in key:
                del sys.modules[key]
        os.chdir(self.name)
        net_dir = os.getcwd()
        self._build_dir = net_dir
        sys.path.append(net_dir)

        # remove previously imported rhs_funcs from system
        if 'rhs_func' in sys.modules:
            del sys.modules['rhs_func']

        # collect state variable and parameter vectors
        state_vars, params, var_map = self._process_vars()

        # create rhs evaluation function
        ################################

        # set up file header
        func_gen = FortranGen()
        for import_line in self._imports:
            func_gen.add_code_line(import_line)
            func_gen.add_linebreak()
        func_gen.add_linebreak()

        # define function head
        func_gen.add_indent()
        if self.pyauto_compat:
            func_gen.add_code_line("subroutine func(ndim,y,icp,args,ijac,y_delta,dfdu,dfdp)")
            func_gen.add_linebreak()
            func_gen.add_code_line("implicit none")
            func_gen.add_linebreak()
            func_gen.add_code_line("integer, intent(in) :: ndim, icp(*), ijac")
            func_gen.add_linebreak()
            func_gen.add_code_line("double precision, intent(in) :: y(ndim), args(*)")
            func_gen.add_linebreak()
            func_gen.add_code_line("double precision, intent(out) :: y_delta(ndim)")
            func_gen.add_linebreak()
            func_gen.add_code_line("double precision, intent(inout) :: dfdu(ndim,ndim), dfdp(ndim,*)")
            func_gen.add_linebreak()
        else:
            func_gen.add_code_line("subroutine func(ndim,t,y,args,y_delta)")
            func_gen.add_linebreak()
            func_gen.add_code_line("implicit none")
            func_gen.add_linebreak()
            func_gen.add_code_line("integer, intent(in) :: ndim")
            func_gen.add_linebreak()
            func_gen.add_code_line("double precision, intent(in) :: t, y(ndim)")
            func_gen.add_linebreak()
            func_gen.add_code_line("double precision, intent(in) :: args(*)")
            func_gen.add_linebreak()
            func_gen.add_code_line("double precision, intent(out) :: y_delta(ndim)")
            func_gen.add_linebreak()

        # declare variable types
        func_gen.add_code_line("double precision ")
        for key in var_map:
            var = self.get_var(key)
            if "float" in str(var.dtype) and var.short_name != 'y_delta':
                func_gen.add_code_line(f"{var.short_name},")
        if "," in func_gen.code[-1]:
            func_gen.code[-1] = func_gen.code[-1][:-1]
        else:
            func_gen.code.pop(-1)
        func_gen.add_linebreak()
        func_gen.add_code_line("integer ")
        for key in var_map:
            var = self.get_var(key)
            if "int" in str(var.dtype):
                func_gen.add_code_line(f"{var.short_name},")
        if "," in func_gen.code[-1]:
            func_gen.code[-1] = func_gen.code[-1][:-1]
        else:
            func_gen.code.pop(-1)
        func_gen.add_linebreak()

        # declare constants
        args = [None for _ in range(len(params))]
        func_gen.add_code_line("! declare constants")
        func_gen.add_linebreak()
        updates, indices = [], []
        i = 0
        for key, (vtype, idx) in var_map.items():
            if vtype == 'constant':
                var = params[idx][1]
                if var.short_name != 'y_delta':
                    func_gen.add_code_line(f"{var.short_name} = args({idx+1})")
                    func_gen.add_linebreak()
                    args[idx] = var
                    updates.append(f"{var.short_name}")
                    indices.append(i)
                    i += 1
        func_gen.add_linebreak()

        # extract state variables from input vector y
        func_gen.add_code_line("! extract state variables from input vector")
        func_gen.add_linebreak()
        for key, (vtype, idx) in var_map.items():
            var = self.get_var(key)
            if vtype == 'state_var':
                func_gen.add_code_line(f"{var.short_name} = {var.value}")
                func_gen.add_linebreak()
        func_gen.add_linebreak()

        # add equations
        func_gen.add_code_line("! calculate right-hand side update of equation system")
        func_gen.add_linebreak()
        arg_updates = []
        for i, layer in enumerate(self.layers):
            for j, op in enumerate(layer):
                lhs = op.value.split("=")[0]
                lhs = lhs.replace(" ", "")
                find_arg = [arg == lhs for arg in updates]
                if any(find_arg):
                    idx = find_arg.index(True)
                    arg_updates.append((updates[idx], indices[idx]))
                func_gen.add_code_line(op.value)
                func_gen.add_linebreak()
        func_gen.add_linebreak()

        # update parameters where necessary
        func_gen.add_code_line("! update system parameters")
        func_gen.add_linebreak()
        for upd, idx in arg_updates:
            update_str = f"args{self.idx_l}{idx}{self.idx_r} = {upd}"
            if f"    {update_str}" not in func_gen.code:
                func_gen.add_code_line(update_str)
                func_gen.add_linebreak()

        # end function
        func_gen.add_code_line(f"end subroutine func")
        func_gen.add_linebreak()
        func_gen.remove_indent()

        # save rhs function to file
        f2py.compile(func_gen.generate(), modulename='rhs_func', extension='.f', source_fn='rhs_func.f', verbose=False)

        # create additional subroutines in pyauto compatibility mode
        if self.pyauto_compat:
            self.generate_auto_file(net_dir)

        # import function from file
        exec("from rhs_func import func", globals())
        rhs_eval = globals().pop('func')
        os.chdir(orig_path)

        # apply function decorator
        if decorator:
            rhs_eval = decorator(rhs_eval, **kwargs)

        return rhs_eval, args, state_vars, var_map, net_dir

    def generate_auto_file(self, directory):
        """

        Parameters
        ----------
        directory

        Returns
        -------

        """

        if not self.pyauto_compat:
            raise ValueError('This method can only be called in pyauto compatible mode. Please set `pyauto_compat` to '
                             'True upon calling the `CircuitIR.compile` method.')

        # read file
        ###########

        try:

            # read file from excisting system compilation
            if not directory:
                directory = os.getcwd()
            directory = f"{directory}/pyrates_build/{self.name}" if "/pyrates_build" not in directory else directory
            fn = f"{directory}/rhs_func.f" if "rhs_func.f" not in directory else directory
            with open(fn, 'rt') as f:
                func_str = f.read()

        except FileNotFoundError:

            # compile system and then read the built files
            compile_results = self.compile(build_dir=directory)
            fn = f"{compile_results[-1]}/rhs_func.f"
            with open(fn, 'r') as f:
                func_str = f.read()

        # generate additional subroutines
        #################################

        func_gen = FortranGen()

        # generate subroutine header
        func_gen.add_linebreak()
        func_gen.add_indent()
        func_gen.add_code_line("subroutine stpnt(ndim, y, args, t)")
        func_gen.add_linebreak()
        func_gen.add_code_line("implicit None")
        func_gen.add_linebreak()
        func_gen.add_code_line("integer, intent(in) :: ndim")
        func_gen.add_linebreak()
        func_gen.add_code_line("double precision, intent(inout) :: y(ndim), args(*)")
        func_gen.add_linebreak()
        func_gen.add_code_line("double precision, intent(in) :: T")
        func_gen.add_linebreak()

        # declare variable types
        func_gen.add_code_line("double precision ")
        for key in self.vars:
            var = self.get_var(key)
            name = var.short_name
            if "float" in str(var.dtype) and name != 'y_delta' and name != 'y' and name != 't':
                func_gen.add_code_line(f"{var.short_name},")
        if "," in func_gen.code[-1]:
            func_gen.code[-1] = func_gen.code[-1][:-1]
        else:
            func_gen.code.pop(-1)
        func_gen.add_linebreak()
        func_gen.add_code_line("integer ")
        for key in self.vars:
            var = self.get_var(key)
            if "int" in str(var.dtype):
                func_gen.add_code_line(f"{var.short_name},")
        if "," in func_gen.code[-1]:
            func_gen.code[-1] = func_gen.code[-1][:-1]
        else:
            func_gen.code.pop(-1)
        func_gen.add_linebreak()

        # define parameter values
        func_gen.add_linebreak()
        for key in self.vars:
            var = self.get_var(key)
            if hasattr(var, 'vtype') and var.vtype == 'constant' and var.short_name != 'y_delta' and var.short_name != 'y':
                func_gen.add_code_line(f"{var.short_name} = {var}")
                func_gen.add_linebreak()
        func_gen.add_linebreak()

        # define initial state
        state_vars, params, var_map = self._process_vars()

        func_gen.add_linebreak()
        npar = 0
        for key, (vtype, idx) in var_map.items():
            if vtype == 'constant':
                var = params[idx][1]
                if var.short_name != 'y_delta':
                    func_gen.add_code_line(f"args({idx + 1}) = {var.short_name}")
                    func_gen.add_linebreak()
                    if idx+1 > npar:
                        npar = idx+1
        func_gen.add_linebreak()

        func_gen.add_linebreak()
        for key, (vtype, idx) in var_map.items():
            var = self.get_var(key)
            if vtype == 'state_var':
                func_gen.add_code_line(f"{var.value} = {var.eval()}")
                func_gen.add_linebreak()
        func_gen.add_linebreak()

        # end subroutine
        func_gen.add_linebreak()
        func_gen.add_code_line("end subroutine stpnt")
        func_gen.add_linebreak()

        # add dummy subroutines
        for routine in ['bcnd', 'icnd', 'fopt', 'pvls']:
            func_gen.add_linebreak()
            func_gen.add_code_line(f"subroutine {routine}")
            func_gen.add_linebreak()
            func_gen.add_code_line(f"end subroutine {routine}")
            func_gen.add_linebreak()
        func_gen.add_linebreak()
        func_gen.remove_indent()

        func_combined = f"{func_str} \n {func_gen.generate()}"
        f2py.compile(func_combined, source_fn=fn, modulename='rhs_func', extension='.f', verbose=False)

        self.npar = npar
        self.ndim = self.get_var('y').shape[0]

        # generate constants file
        #########################

        # declare auto constants and their values
        auto_constants = {'NDIM': self.ndim, 'NPAR': self.npar, 'IPS': -2, 'ILP': 0, 'ICP': 14, 'NTST': 1, 'NCOL': 4,
                          'IAD': 3, 'ISP': 0, 'ISW': 1, 'IPLT': 0, 'NBC': 0, 'NINT': 0, 'NMX': 10000, 'NPR': 10,
                          'MXBF': 10, 'IID': 2, 'ITMX': 8, 'ITNW': 5, 'NWTN': 3, 'JAC': 0, 'EPSL': 1e-7, 'EPSU': 1e-7,
                          'EPSS': 1e-5, 'IRS': 0}

        # write auto constants to string
        cgen = FortranGen()
        for key, val in auto_constants.items():
            cgen.add_code_line(f"{key} = {val}")
            cgen.add_linebreak()

        # write auto constants to file
        try:
            with open('c.ivp', 'wt') as cfile:
                cfile.write(cgen.generate())
        except FileNotFoundError:
            with open('c.ivp', 'xt') as cfile:
                cfile.write(cgen.generate())

        self._auto_files_generated = True

        return fn

    def _solve(self, rhs_func, func_args, T, dt, dts, t, solver, output_indices, **kwargs):
        """

        Parameters
        ----------
        rhs_func
        func_args
        state_vars
        T
        dt
        dts
        t
        solver
        output_indices
        kwargs

        Returns
        -------

        """

        if self.pyauto_compat:

            from pyrates.utility import PyAuto
            pyauto = PyAuto(auto_dir=self._build_dir)
            dsmin, dsmax = dt*1e-2, dt*1e2
            nmx = int(T/dsmin)
            npr = int(dts/dt)
            pyauto.run(e='rhs_func', c='ivp', DS=dt, DSMIN=dsmin, DSMAX=1.0, name='t', UZR={14: T}, STOP={'UZ1'},
                       NMX=nmx, NPR=npr, **kwargs)

            extract = [f'U({i[0]+self.idx_start if type(i) is list else i+self.idx_start})' for i in output_indices]
            extract.append('PAR(14)')
            results_tmp = pyauto.extract(keys=extract, cont='t')
            times = results_tmp.pop('PAR(14)')
            return times, [results_tmp[v] for v in extract[:-1]]

        return super()._solve(rhs_func, func_args, T, dt, dts, t, solver, output_indices, **kwargs)

    def _create_op(self, op, name, *args):
        if not self.ops[op]['call']:
            raise NotImplementedError(f"The operator `{op}` is not implemented for this backend ({self.name}). "
                                      f"Please consider passing the required operation to the backend initialization "
                                      f"or choose another backend.")
        if op in ["=", "+=", "-=", "*=", "/="]:
            if len(args) > 2 and hasattr(args[2], 'shape') and len(args[2].shape) > 1 and \
                    'bool' not in str(type(args[2])):
                args_tmp = list(args)
                if not hasattr(args_tmp[2], 'short_name'):
                    idx = self.add_var(vtype='state_var', name='idx', value=args_tmp[2])
                else:
                    idx = args_tmp[2]
                var, upd, idx = self._process_update_args_old(args[0], args[1], idx)
                idx_str = ",".join([f"{idx.short_name}[:,{i}]" for i in range(idx.shape[1])])
                args = (var, upd, idx_str, idx)
            return FortranAssignOp(self.ops[op]['call'], self.ops[op]['name'], name, *args, idx_l=self.idx_l,
                                   idx_r=self.idx_r)
        elif op is "index":
            return FortranIndexOp(self.ops[op]['call'], self.ops[op]['name'], name, *args, idx_l=self.idx_l,
                                  idx_r=self.idx_r)
        else:
            if op is "cast":
                args = list(args)
                for dtype in self.dtypes:
                    if dtype in str(args[1]):
                        args[1] = f"np.{dtype}"
                        break
                args = tuple(args)
            return FortranOp(self.ops[op]['call'], self.ops[op]['name'], name, *args)

    @staticmethod
    def _compare_shapes(op1: Any, op2: Any, index=False) -> bool:
        """Checks whether the shapes of op1 and op2 are compatible with each other.

        Parameters
        ----------
        op1
            First operator.
        op2
            Second operator.

        Returns
        -------
        bool
            If true, the shapes of op1 and op2 are compatible.

        """

        if hasattr(op1, 'shape') and hasattr(op2, 'shape'):
            if op1.shape == op2.shape:
                return True
            elif len(op1.shape) > 1 and len(op2.shape) > 1:
                return True
            elif len(op1.shape) == 0 and len(op2.shape) == 0:
                return True
            else:
                return False
        elif hasattr(op1, 'shape'):
            if sum(op1.shape) > 0:
                return False
            else:
                return True
        else:
            return True


class FortranGen(CodeGen):

    def add_code_line(self, code_str):
        """Add code line string to code.
        """
        code_line = "\t" * self.lvl + code_str if self.code and self.code[-1] == '\n' else code_str
        n = 60
        if len(code_line) > n:
            idx = self._find_first_op(code_line, start=0, stop=n)
            self.code.append(f"{code_line[0:idx]}")
            while idx < n:
                self.add_linebreak()
                idx_new = self._find_first_op(code_line, start=idx, stop=idx+n)
                self.code.append("     " f"& {code_line[idx:idx+idx_new]}")
                idx += idx_new
        else:
            self.code.append(code_line)

    def _find_first_op(self, code, start, stop):
        if stop < len(code):
            code_tmp = code[start:stop]
            ops = ["+", "-", "*", "/", "**", "^", "%", "<", ">", "==", "!=", "<=", ">="]
            indices = [code_tmp.index(op) for op in ops if op in code_tmp]
            if indices and max(indices) > 0:
                return max(indices)
            return len(code_tmp) - 1 - code_tmp[::-1].index(' ')
        return stop


def generate_func(self, return_key='f', omit_assign=False, return_dim=None, return_intent='out'):
    """Generates a function from operator value and arguments"""

    global module_counter

    # function head
    func_dict = {}
    func = FortranGen()
    func.add_linebreak()
    func.add_indent()
    func.add_code_line(f"subroutine {self.short_name}({return_key}")
    for arg in self._op_dict['arg_names']:
        if arg != return_key:
            func.add_code_line(f",{arg}")
    func.add_code_line(")")
    func.add_linebreak()

    # argument type definition
    for arg, name in zip(self._op_dict['args'], self._op_dict['arg_names']):
        if name != return_key:
            dtype = "integer" if "int" in str(arg.vtype) else "double precision"
            dim = f"dimension({','.join([str(s) for s in arg.shape])}), " if arg.shape else ""
            func.add_code_line(f"{dtype}, {dim}intent(in) :: {name}")
            func.add_linebreak()
    out_dim = f"({','.join([str(s) for s in return_dim])})" if return_dim else ""
    func.add_code_line(f"double precision, intent({return_intent}) :: {return_key}{out_dim}")
    func.add_linebreak()

    func.add_code_line(f"{self._op_dict['value']}" if omit_assign else f"{return_key} = {self._op_dict['value']}")
    func.add_linebreak()
    func.add_code_line("end")
    func.add_linebreak()
    func.remove_indent()
    module_counter += 1
    f2py.compile(func.generate(), modulename=f"pyrates_func_{module_counter}", extension=".f",
                 source_fn=f"/tmp/pyrates_func_{module_counter}.f", verbose=False)
    exec(f"from pyrates_func_{module_counter} import {self.short_name}", globals(), func_dict)
    return func_dict