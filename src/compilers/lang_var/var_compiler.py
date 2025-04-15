from lang_var.var_ast import *
from common.wasm import *
import lang_var.var_tychecker as var_tychecker
from common.compilerSupport import *
# import common.utils as utils

def compileModule(m: mod, cfg: CompilerConfig) -> WasmModule:
    """
    Compiles the given module.
    """
    vars = var_tychecker.tycheckModule(m)
    instrs = compileStmts(m.stmts)
    idMain = WasmId('$main')
    locals: list[tuple[WasmId, WasmValtype]] = [(identToWasmId(x), 'i64') for x in vars]
    return WasmModule(imports=wasmImports(cfg.maxMemSize),
                        exports=[WasmExport("main", WasmExportFunc(idMain))],
                        globals=[],
                        data=[],
                        funcTable=WasmFuncTable([]),
                        funcs=[WasmFunc(idMain, [], None, locals, instrs)])

def identToWasmId(x: ident) -> WasmId:
    name = x.name
    match name:
        case "print":
            name = "print_i64"
        case "input_int":
            name = "input_i64"
        case _:
            pass
    return WasmId(f'${name}')

def binaryOpToWasmBinOp(op: binaryop) -> WasmInstrNumBinOp:
    match op:
        case Add():
            return WasmInstrNumBinOp('i64', 'add')
        case Sub():
            return WasmInstrNumBinOp('i64', 'sub')
        case Mul():
            return WasmInstrNumBinOp('i64', 'mul')

def compileStmts(stmts: list[stmt]) -> list[WasmInstr]:
    instructions: list[WasmInstr] = []
    for statement in stmts:
        match statement:
            case StmtExp(e):
                instructions.extend(compileExp(e))
            case Assign(var, right):
                instructions.extend(compileExp(right))
                instructions.append(WasmInstrVarLocal('set', identToWasmId(var)))
    return instructions

def compileExp(exp: exp) -> list[WasmInstr]:
    ret: list[WasmInstr] = []
    match exp:
        case IntConst(num):
            ret = [WasmInstrConst('i64', num)]
        case Name(name):
            ret = [WasmInstrVarLocal('get', identToWasmId(name))]
        case Call(name, args):
            for arg in args:
                ret.extend(compileExp(arg))
            ret.append(WasmInstrCall(identToWasmId(name)))
        case UnOp(op, arg):
            ret.append(WasmInstrConst('i64', 0))
            ret.extend(compileExp(arg))
            ret.append(WasmInstrNumBinOp('i64', 'sub'))
        case BinOp(left, op, right):
            ret.extend(compileExp(left))
            ret.extend(compileExp(right))
            ret.append(binaryOpToWasmBinOp(op))
    return ret