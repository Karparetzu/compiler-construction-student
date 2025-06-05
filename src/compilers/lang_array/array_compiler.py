from lang_array.array_astAtom import *
import lang_array.array_ast as plainAst
from common.wasm import *
import lang_array.array_tychecker as array_tychecker
import lang_array.array_transform as array_transform
from lang_array.array_compilerSupport import *
from common.compilerSupport import *
# import common.utils as utils

config: CompilerConfig

def compileModule(m: plainAst.mod, cfg: CompilerConfig) -> WasmModule:
    """
    Compiles the given module.
    """

    # # Set config as global (for max array size)
    global config
    config = cfg

    # Get array context
    ctx = array_transform.Ctx()

    vars = array_tychecker.tycheckModule(m)

    # Transform (atomic subexpressions)
    arr_stmts = array_transform.transStmts(m.stmts, ctx)

    instrs = compileStmts(arr_stmts)
    idMain = WasmId('$main')

    # Locals (tycheck-vars + tmp + ctx)
    locals: list[tuple[WasmId, WasmValtype]] = [(identToWasmId(x[0]), tyToWasmValtype(x[1].ty)) for x in vars.items()]
    locals.extend(Locals.decls())
    locals.extend([(identToWasmId(x[0]), tyToWasmValtype(x[1])) for x in ctx.freshVars.items()] )
    
    return WasmModule(imports=wasmImports(config.maxMemSize),
                        exports=[WasmExport("main", WasmExportFunc(idMain))],
                        globals=Globals.decls(),
                        data=Errors.data(),
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

def tyOfAtomExp(e: atomExp) -> ty:
    match e.ty:
        case Int() | Bool() | Array():
            return e.ty
        case None:
            raise Exception("Unknown type for atomExp")

def tyOfExp(e: exp) -> ty:
    match e.ty:
        case NotVoid(type):
            return type
        case None | Void():
            raise Exception("Type is None or Void for exp")

def tyToWasmValtype(ty: ty) -> Literal['i32', 'i64']:
    match ty:
        case Bool():
            return 'i32'
        case Int():
            return 'i64'
        case Array():
            return 'i32'

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
            case SubscriptAssign(left, index, right):
                # Get type and store instruction
                match left.ty:
                    case Array(ty):
                        arrType = ty
                        storeInstr = WasmInstrMem(tyToWasmValtype(ty), 'store')
                    case _:
                        raise TypeError
                instructions.extend(arrayOffsetInstrs(left, index, arrType))    # Get address of left side array item
                instructions.extend(compileExp(right))                          # Get right side
                instructions.append(storeInstr)                                 # Store right side into item

    return instructions

def compileAtomExp(atomExp: AtomExp) -> WasmInstr:
    match atomExp.e:
        case IntConst(num):
            return WasmInstrConst('i64', num)
        case BoolConst(val):
            return WasmInstrConst('i32', 1 if val else 0)
        case Name(name):
            return WasmInstrVarLocal('get', identToWasmId(name, tyToWasmValtype(tyOfAtomExp(atomExp.e))))

def compileExp(exp: exp) -> list[WasmInstr]:
    match exp:
        case AtomExp():
            return [compileAtomExp(exp)]
        case Call(name, args):
            return compileCall(name, args)
        case UnOp(op, arg):
            return compileUnOp(op, arg)
        case BinOp(left, op, right, ty):
            return compileBinOp(left, op, right, ty)
        case ArrayInitDyn(length, elemInit, ty):
            ret: list[WasmInstr] = []

            # Initialization of array, leaves array address on top of stack
            ret.extend(compileInitArray(length, tyOfAtomExp(elemInit)))
            ret.append(WasmInstrVarLocal('tee', identToWasmId(Ident('@tmp_i32'))))  # Set $@tmp_i32 to array address, leave it on top of stack
            ret.append(WasmInstrVarLocal('get', identToWasmId(Ident('@tmp_i32'))))
            ret.append(WasmInstrConst('i32', 4))
            ret.append(WasmInstrNumBinOp('i32', 'add'))
            ret.append(WasmInstrVarLocal('set', identToWasmId(Ident('@tmp_i32'))))  # Set $@tmp_i32 to array address, leave it on top of stack

            # Loop
            elemLen = 4 if ((elemInit.ty is None) or tyToWasmValtype(elemInit.ty) == 'i32') else 8  # Item length in bytes

            global whileCount
            currentWhileNo = whileCount
            whileCount += 1

            whileInstr: list[WasmInstr] = []
            
            whileInstr.append(WasmInstrVarLocal('get', identToWasmId(Ident('@tmp_i32'))))
            whileInstr.append(WasmInstrVarGlobal('get', identToWasmId(Ident('@free_ptr'))))
            whileInstr.append(WasmInstrIntRelOp('i32','lt_u'))

            branchToExit = WasmInstrBranch(identToWasmId(Ident(f'loop_{currentWhileNo}_exit')), False)
            whileInstr.append(WasmInstrIf(None, [], [branchToExit]))

            whileInstr.append(WasmInstrVarLocal('get', identToWasmId(Ident('@tmp_i32'))))
            whileInstr.append(compileAtomExp(AtomExp(elemInit)))
            whileInstr.append(WasmInstrMem(tyToWasmValtype(tyOfAtomExp(elemInit)), 'store'))
            whileInstr.append(WasmInstrVarLocal('get', identToWasmId(Ident('@tmp_i32'))))
            whileInstr.append(WasmInstrConst('i32', elemLen))
            whileInstr.append(WasmInstrNumBinOp('i32','add'))
            whileInstr.append(WasmInstrVarLocal('set', identToWasmId(Ident('@tmp_i32'))))

            branchToStart = WasmInstrBranch(identToWasmId(Ident(f'loop_{currentWhileNo}_start')), False)
            whileInstr.append(branchToStart)


            loop = WasmInstrLoop(
                identToWasmId(Ident(f'loop_{currentWhileNo}_start')),
                whileInstr
            )

            ret.append(WasmInstrBlock(
                identToWasmId(Ident(f'loop_{currentWhileNo}_exit')),
                None,
                [loop]
            ))

            return ret
        case ArrayInitStatic(elemInit, ty):
            ret: list[WasmInstr] = []
            ret.extend(compileInitArray(IntConst(len(elemInit)), tyOfAtomExp(elemInit[0])))

            match elemInit[0].ty:
                case Int(): 
                    elemType = 'i64' 
                    elemLen = 8
                case _:
                    elemType = 'i32'
                    elemLen = 4

            for i, e in enumerate(elemInit):
                # Read & write local var
                ret += [WasmInstrVarLocal('tee', identToWasmId(Ident('@tmp_i32')))]
                ret += [WasmInstrVarLocal('get', identToWasmId(Ident('@tmp_i32')))]

                # Add offset
                ret += [WasmInstrConst('i32', 4 + (elemLen*(i))), WasmInstrNumBinOp('i32','add')]

                # Evaluate expr and store it
                ret += compileExp(AtomExp(e))
                ret += [WasmInstrMem(elemType, 'store')]
            return ret
        case Subscript(array, index):
            ret = arrayOffsetInstrs(array, index, tyOfExp(exp))
            ret.append(WasmInstrMem(tyToWasmValtype(tyOfExp(exp)), 'load'))
            return ret

def checkLength(lenExp: atomExp, elemTy: ty) -> list[WasmInstr]:
    ret: list[WasmInstr] = []

    # 1.1. Check > 0
    ret.append(WasmInstrConst('i64', 0))                    # 0 to stack
    ret.append(compileAtomExp(AtomExp(lenExp)))             # Length to stack
    ret.append(WasmInstrIntRelOp('i64', 'gt_s'))            # Greater than
    ret.append(WasmInstrIf(
        None,
        [WasmInstrConst('i32',0),WasmInstrConst('i32',14),WasmInstrCall(identToWasmId(Ident("print_err"),'i32')),WasmInstrTrap()], # If
        [] # Else
    ))

    # 1.2. Check <= maxArraySize
    global config
    maxArraySize = config.maxArraySize                      # Max array size in bytes
    elemLen = 4 if tyToWasmValtype(elemTy) == 'i32' else 8  # Item length in bytes
    maxElemCount = maxArraySize // elemLen                  # Max number of elements
    ret.append(compileAtomExp(AtomExp(lenExp)))             # Length to stack
    ret.append(WasmInstrConst('i64', maxElemCount))         # maxElemCount to stack
    ret.append(WasmInstrIntRelOp('i64','ge_u'))             # Greater equals
    ret.append(WasmInstrIf(
        None,
        [WasmInstrConst('i32',0),WasmInstrConst('i32',14),WasmInstrCall(identToWasmId(Ident("print_err"))),WasmInstrTrap()], # If
        [] # Else
    ))

    return ret

def compileInitArray(lenExp: atomExp, elemTy: ty) -> list[WasmInstr]:
    ret: list[WasmInstr] = []

    # 1. Check length
    ret = checkLength(lenExp, elemTy)

    # 3.1. Read free_ptr (yes, step 3 begins before step 2)
    ret.append(WasmInstrVarGlobal('get', identToWasmId(Ident('@free_ptr'))))

    # 2. Compute header value
    # 2.1. Get value of M
    match elemTy:
        case Array():
            m = 3
        case _:
            m = 1

    # 2.2. Compute 
    ret.append(compileAtomExp(AtomExp(lenExp)))                                 # Length to stack
    ret.append(WasmInstrConvOp('i32.wrap_i64'))                                 # Convert length to i32
    ret.extend([WasmInstrConst('i32', 4), WasmInstrNumBinOp('i32','shl')])      # Shift length left by 4 bit
    ret.append(WasmInstrConst('i32', m))                                        # Value for bits 0-3
    ret.append(WasmInstrNumBinOp('i32', 'xor'))                                 # Integrate bits 0-3

    # 3.2. Store header at free_ptr
    ret.append(WasmInstrMem('i32', 'store'))

    elemLen = 4 if tyToWasmValtype(elemTy) == 'i32' else 8                      # Item length in bytes

    # 4. Move $@free_ptr and return array address
    ret.append(WasmInstrVarGlobal('get', identToWasmId(Ident('@free_ptr'))))
    ret.append(compileAtomExp(AtomExp(lenExp)))                                 # Length to stack
    ret.extend([                                                                # Multiply length with the size of each element
        WasmInstrConvOp('i32.wrap_i64'),
        WasmInstrConst('i32', elemLen),
        WasmInstrNumBinOp('i32', 'mul')]) 
    ret.extend([WasmInstrConst('i32', 4), WasmInstrNumBinOp('i32', 'add')])     # Add 4 for the header
    ret.append(WasmInstrVarGlobal('get', identToWasmId(Ident('@free_ptr'))))
    ret.append(WasmInstrNumBinOp('i32', 'add'))                                 # Add the space required by the array to $@free_ptr
    ret.append(WasmInstrVarGlobal('set', identToWasmId(Ident('@free_ptr'))))    # Set free_ptr

    return ret

def arrayLenInstrs() -> list[WasmInstr]:
    ret: list[WasmInstr] = []

    ret.append(WasmInstrMem('i32', 'load'))                                     # Load array header
    ret.extend([WasmInstrConst('i32', 4), WasmInstrNumBinOp('i32', 'shr_u')])   # Shift by 4 (location of the length info)
    ret.append(WasmInstrConvOp('i64.extend_i32_u'))                             # Convert to i64

    return ret

def checkBounds(arrayExp: atomExp, indexExp: atomExp) -> list[WasmInstr]:
    ret: list[WasmInstr] = []

    # 1.1. Check > 0
    ret.append(WasmInstrConst('i64', 0))                    # 0 to stack (left)
    ret.append(compileAtomExp(AtomExp(indexExp)))           # Index to stack (right)
    ret.append(WasmInstrIntRelOp('i64', 'gt_s'))            # Greater than
    ret.append(WasmInstrIf(
        None,
        [WasmInstrConst('i32', 14), WasmInstrConst('i32', 10), WasmInstrCall(identToWasmId(Ident("print_err"))),WasmInstrTrap()], # If (error)
        [] # Else
    ))

    # 1.2. Check <= length
    ret.append(compileAtomExp(AtomExp(indexExp)))           # Index to stack (left)
    ret.append(compileAtomExp(AtomExp(arrayExp)))           # Array address to stack
    ret.extend(arrayLenInstrs())                            # Length to stack (right)
    ret.append(WasmInstrIntRelOp('i64','ge_u'))             # Greater equals
    ret.append(WasmInstrIf(
        None,
        [WasmInstrConst('i32', 14), WasmInstrConst('i32', 10), WasmInstrCall(identToWasmId(Ident("print_err"))),WasmInstrTrap()], # If (error)
        [] # Else
    ))

    return ret

def arrayOffsetInstrs(arrayExp: atomExp, indexExp: atomExp, subTy: ty) -> list[WasmInstr]:
    ret: list[WasmInstr] = []

    # 1. Check bounds
    ret.extend(checkBounds(arrayExp, indexExp))

    # 2. Compute address
    elemLen = 4 if tyToWasmValtype(subTy) == 'i32' else 8   # Item length in bytes

    ret.append(compileAtomExp(AtomExp(arrayExp)))           # Array address to stack
    ret.append(compileAtomExp(AtomExp(indexExp)))           # Index to stack
    
    ret.append(WasmInstrConvOp('i32.wrap_i64'))
    ret.append(WasmInstrConst('i32', elemLen))
    ret.append(WasmInstrNumBinOp('i32', 'mul'))
    ret.append(WasmInstrConst('i32', 4))
    ret.append(WasmInstrNumBinOp('i32','add'))              # now on top of stack: offset of the element
    ret.append(WasmInstrNumBinOp('i32','add'))              # now on top of stack: address of the element

    return ret

def compileCall(name: ident, args: list[exp]):
    ret: list[WasmInstr] = []

    # If len is called
    if name.name == 'len':
        ret.extend(compileExp(args[0]))
        ret.extend(arrayLenInstrs())
    else:
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
        case Is():
            ret.extend(compileExp(left))
            ret.extend(compileExp(right))
            ret.append(WasmInstrIntRelOp('i32','eq')) 
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