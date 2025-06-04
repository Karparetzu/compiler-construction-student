from lang_array.array_astAtom import *
import lang_array.array_ast as plainAst
from common.wasm import *
import lang_array.array_tychecker as array_tychecker
import lang_array.array_transform as array_transform
from lang_array.array_compilerSupport import *
from common.compilerSupport import *
import common.utils as utils

def compileModule(m: plainAst.mod, cfg: CompilerConfig) -> WasmModule:
    """
    Compiles the given module.
    """
    vars = loop_tychecker.tycheckModule(m)
    instrs = compileStmts(m.stmts)
    idMain = WasmId('$main')
    locals: list[tuple[WasmId, WasmValtype]] = [(identToWasmId(x[0]), tyToWasmValtype(x[1].ty)) for x in vars.items()]
    return WasmModule(imports=wasmImports(cfg.maxMemSize),
                        exports=[WasmExport("main", WasmExportFunc(idMain))],
                        globals=[],
                        data=[],
                        funcTable=WasmFuncTable([]),
                        funcs=[WasmFunc(idMain, [], None, locals, instrs)])

def identToWasmId(x: ident, ty: Optional[Literal['i32', 'i64']] = None) -> WasmId:
    name = x.name
    match name:
        case "print":
            name = f"print_{'bool' if ty == 'i32' else 'i64'}"
        case "input_int":
            name = "input_i64"
        case _:
            pass
    return WasmId(f'${name}')

def tyOfExp(e: exp) -> ty:
    utils.assertType(e.ty, NotVoid)

    match e.ty:
        case None | Void():
            raise Exception("Type is None or Void")
        case NotVoid(type):
            return type

def tyToWasmValtype(ty: ty) -> Literal['i32', 'i64']:
    match ty:
        case Bool():
            return 'i32'
        case Int():
            return 'i64'

whileCount = 0

def compileStmts(stmts: list[stmt]) -> list[WasmInstr]:
    instructions: list[WasmInstr] = []
    for statement in stmts:
        match statement:
            case StmtExp(e):
                instructions.extend(compileExp(e))
            case Assign(var, right):
                instructions.extend(compileExp(right))
                instructions.append(WasmInstrVarLocal('set', identToWasmId(var)))
            case IfStmt(cond, thenBody, elseBody):
                instructions.extend(compileExp(cond))

                instructions.append(
                    WasmInstrIf(
                        None,
                        compileStmts(thenBody),
                        compileStmts(elseBody)
                    )
                )
            case WhileStmt(cond, body):
                global whileCount
                currentWhileNo = whileCount
                whileCount += 1

                whileInstr = compileExp(cond)
                
                whileExit = WasmInstrBranch(identToWasmId(Ident(f'loop_{currentWhileNo}_exit')), False)
                whileInstr.append(WasmInstrIf(None, [], [whileExit]))
                
                whileInstr.extend(compileStmts(body))
                
                whileStart = WasmInstrBranch(identToWasmId(Ident(f'loop_{currentWhileNo}_start')), False)
                whileInstr.append(whileStart)
                
                loop = WasmInstrLoop(
                    identToWasmId(Ident(f'loop_{currentWhileNo}_start')),
                    whileInstr
                )

                block = WasmInstrBlock(
                    identToWasmId(Ident(f'loop_{currentWhileNo}_exit')),
                    None,
                    [loop]
                )

                instructions.append(block)

    return instructions

def compileExp(exp: exp) -> list[WasmInstr]:
    match exp:
        case IntConst(num):
            return [WasmInstrConst('i64', num)]
        case BoolConst(val):
            return [WasmInstrConst('i32', 1 if val else 0)]
        case Name(name, ty):
            return [WasmInstrVarLocal('get', identToWasmId(name, tyToWasmValtype(tyOfExp(exp))))]
        case Call(name, args):
            return compileCall(name, args)
        case UnOp(op, arg):
            return compileUnOp(op, arg)
        case BinOp(left, op, right, ty):
            return compileBinOp(left, op, right, ty)

def compileCall(name: ident, args: list[exp]):
    '''
    type: str = ""
    for arg in args:
        wasm += getExp(arg)
        type = tyToWasmValtype(tyOfExp(arg))
    wasm.append(WasmInstrCall(identToWasmId(name, type)))
    return wasm
    '''
    ret: list[WasmInstr] = []

    # Firstly compile arguments of function call
    for arg in args:
        ret.extend(compileExp(arg))

    wasmType = tyToWasmValtype(tyOfExp(args[0])) if len(args) == 1 else None

    # Compile call to function name in the end
    ret.append(WasmInstrCall(identToWasmId(name, wasmType)))
    return ret

def compileUnOp(op: unaryop, arg: exp) -> list[WasmInstr]:
    ret: list[WasmInstr] = []

    # Get 
    condWasmType = tyToWasmValtype(tyOfExp(arg))

    match op:
        case USub():        
            ret.append(WasmInstrConst(condWasmType, 0))
            ret.extend(compileExp(arg))
            ret.append(WasmInstrNumBinOp(condWasmType, 'sub'))
        case Not():
            ret.extend(compileExp(arg))                 
            ret.append(WasmInstrConst(condWasmType, 0))        
            ret.append(WasmInstrIntRelOp(condWasmType, 'eq'))  
    return ret

def compileBinOp(left: exp, op: binaryop, right: exp, ty: optional[resultTy]) -> list[WasmInstr]:
    ret: list[WasmInstr] = []

    condWasmTypeLeft = tyToWasmValtype(tyOfExp(left))
    condWasmTypeRight = tyToWasmValtype(tyOfExp(right))

    if condWasmTypeLeft != condWasmTypeRight:
        raise Exception('Left and right side of binary operation has to be equal of type.')
    else:
        condWasmType = condWasmTypeLeft

    match op:
        case Add():
            ret.extend(compileExp(left))
            ret.extend(compileExp(right))
            ret.append(WasmInstrNumBinOp(condWasmType, 'add'))
        case Sub():
            ret.extend(compileExp(left))
            ret.extend(compileExp(right))
            ret.append(WasmInstrNumBinOp(condWasmType, 'sub'))
        case Mul():
            ret.extend(compileExp(left))
            ret.extend(compileExp(right))
            ret.append(WasmInstrNumBinOp(condWasmType, 'mul'))
        case Less():
            ret.extend(compileExp(left))
            ret.extend(compileExp(right))
            ret.append(WasmInstrIntRelOp(condWasmType, 'lt_s'))
        case LessEq():
            ret.extend(compileExp(left))
            ret.extend(compileExp(right))
            ret.append(WasmInstrIntRelOp(condWasmType, 'le_s'))
        case Greater():
            ret.extend(compileExp(left))
            ret.extend(compileExp(right))
            ret.append(WasmInstrIntRelOp(condWasmType, 'gt_s'))
        case GreaterEq():
            ret.extend(compileExp(left))
            ret.extend(compileExp(right))
            ret.append(WasmInstrIntRelOp(condWasmType, 'ge_s'))
        case Eq():     
            ret.extend(compileExp(left))
            ret.extend(compileExp(right))
            ret.append(WasmInstrIntRelOp(condWasmType, 'eq'))
        case NotEq():
            ret.extend(compileExp(left))
            ret.extend(compileExp(right))
            ret.append(WasmInstrIntRelOp(condWasmType, 'ne'))
        case And():
            # AND Evaluate left side. If true, then get result of right side (which determines outcome). Otherwise push 0 to stack.
            ret.extend(compileExp(left))
            ret.append(WasmInstrIf(
                'i32',
                thenInstrs=compileExp(right),
                elseInstrs=[WasmInstrConst(condWasmType, 0)]
            ))
        case Or():
            # OR Evaluate left side. If true, push 1 to stack. Otherwise get result of right side (which determines outcome).
            ret.extend(compileExp(left))
            ret.append(WasmInstrIf(
                'i32',
                thenInstrs=[WasmInstrConst(condWasmType, 1)],
                elseInstrs=compileExp(right)
            ))

    return ret