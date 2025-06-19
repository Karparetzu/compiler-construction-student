# import assembly.tac_ast as tac
import assembly.tacSpill_ast as tacSpill
import assembly.mips_ast as mips
from typing import *
from assembly.common import *
# import assembly.tacInterp as tacInterp
from assembly.mipsHelper import *
from common.compilerSupport import *

def assignToMips(i: tacSpill.Assign) -> list[mips.instr]:
    match i.right:
        case tacSpill.Prim(p):
            return [assignPrimToMips(i.var, p)]
        case tacSpill.BinOp():
            return assignBinOpToMips(i.var, i.right)
                
def assignPrimToMips(var: tacSpill.ident, p: tacSpill.prim) -> mips.instr:
    match p:
        case tacSpill.Const(value):
            return mips.LoadI(mips.Reg(var.name), mips.Imm(value))
        case tacSpill.Name(var):
            return mips.Move(mips.Reg(var.name), mips.Reg(var.name))
        
def assignBinOpToMips(var: tacSpill.Ident, binOp: tacSpill.BinOp) -> list[mips.instr]:
    ret: list[mips.instr] = []

    match binOp.op.name:
        case "ADD":
            ret.extend(assignAddToMips(var, binOp.left, binOp.right))
        case "LT_S":
            ret.extend(assignLessThanToMips(var, binOp.left, binOp.right))    
        case _:
            mipsBinOp = getMipsBinOp(binOp.op)
            ret.extend(assignOtherToMips(mipsBinOp, var, binOp.left, binOp.right))    
    
    return ret

def assignAddToMips(var: tacSpill.Ident, left: tacSpill.prim, right: tacSpill.prim) -> list[mips.instr]:
    ret: list[mips.instr] = []
    match (left, right):
        case (tacSpill.Name(lVar), tacSpill.Const(rValue)):
            # r1 = r2 + 1
            ret.append(mips.OpI(mips.AddI(), mips.Reg(var.name), mips.Reg(lVar.name), mips.Imm(rValue)))
        case (tacSpill.Name(lVar), tacSpill.Name(rVar)):
            # r1 = r2 + r3
            ret.append(mips.Op(mips.Add(), mips.Reg(var.name), mips.Reg(lVar.name), mips.Reg(rVar.name)))
        case (tacSpill.Const(lValue), tacSpill.Const(rValue)):
            # r1 = 1 + 2
            ret.append(mips.LoadI(mips.Reg(var.name), mips.Imm(lValue)))
            ret.append(mips.OpI(mips.AddI(), mips.Reg(var.name), mips.Reg(var.name), mips.Imm(rValue)))
        case (tacSpill.Const(lValue), tacSpill.Name(rVar)):
            # r1 = 1 + r2
            tmpName = getTmpRegName([var, rVar])                    
            ret.append(mips.LoadI(mips.Reg(tmpName), mips.Imm(lValue)))
            ret.append(mips.Op(mips.Add(), mips.Reg(var.name), mips.Reg(tmpName), mips.Reg(rVar.name)))
    return ret

def assignLessThanToMips(var: tacSpill.Ident, left: tacSpill.prim, right: tacSpill.prim) -> list[mips.instr]:
    ret: list[mips.instr] = []
    match (left, right):
        case (tacSpill.Name(lVar), tacSpill.Const(rValue)):
            # r1 = r2 < 1
            ret.append(mips.OpI(mips.LessI(), mips.Reg(var.name), mips.Reg(lVar.name), mips.Imm(rValue)))
        case (tacSpill.Name(lVar), tacSpill.Name(rVar)):
            # r1 = r2 < r3
            ret.append(mips.Op(mips.Less(), mips.Reg(var.name), mips.Reg(lVar.name), mips.Reg(rVar.name)))
        case (tacSpill.Const(lValue), tacSpill.Const(rValue)):
            # r1 = 1 < 2
            ret.append(mips.LoadI(mips.Reg(var.name), mips.Imm(lValue)))
            ret.append(mips.OpI(mips.LessI(), mips.Reg(var.name), mips.Reg(var.name), mips.Imm(rValue)))
        case (tacSpill.Const(lValue), tacSpill.Name(rVar)):
            # r1 = 1 < r2
            tmpName = getTmpRegName([var, rVar])
            ret.append(mips.LoadI(mips.Reg(tmpName), mips.Imm(lValue)))
            ret.append(mips.Op(mips.Less(), mips.Reg(var.name), mips.Reg(tmpName), mips.Reg(rVar.name)))
    return ret

def assignOtherToMips(binOp: mips.op, var: tacSpill.Ident, left: tacSpill.prim, right: tacSpill.prim) -> list[mips.instr]:
    ret: list[mips.instr] = []
    match (left, right):
        case (tacSpill.Name(lVar), tacSpill.Const(rValue)):
            # r1 = r2 op 1
            tmpName = getTmpRegName([var, lVar])
            ret.append(mips.LoadI(mips.Reg(tmpName), mips.Imm(rValue)))
            ret.append(mips.Op(binOp, mips.Reg(var.name), mips.Reg(lVar.name), mips.Reg(tmpName)))
        case (tacSpill.Name(lVar), tacSpill.Name(rVar)):
            # r1 = r2 op r3
            ret.append(mips.Op(binOp, mips.Reg(var.name), mips.Reg(lVar.name), mips.Reg(rVar.name)))
        case (tacSpill.Const(lValue), tacSpill.Const(rValue)):
            # r1 = 1 op 2
            tmpName = getTmpRegName([var])
            ret.append(mips.LoadI(mips.Reg(var.name), mips.Imm(lValue)))    # Load left value into r1
            ret.append(mips.LoadI(mips.Reg(tmpName), mips.Imm(rValue)))     # Load right value into tmp register
            ret.append(mips.Op(binOp, mips.Reg(var.name), mips.Reg(var.name), mips.Reg(tmpName)))    # r1 = r1 + tmp
        case (tacSpill.Const(lValue), tacSpill.Name(rVar)):
            # r1 = 1 op r2
            tmpName = getTmpRegName([var, rVar])
            ret.append(mips.LoadI(mips.Reg(tmpName), mips.Imm(lValue)))
            ret.append(mips.Op(binOp, mips.Reg(var.name), mips.Reg(tmpName), mips.Reg(rVar.name)))
    return ret

def getMipsBinOp(binOp: tacSpill.op) -> mips.op:
    match binOp.name:
        case 'ADD': return mips.Add()
        case 'SUB': return mips.Sub()
        case 'MUL': return mips.Mul()
        case 'EQ': return mips.Eq()
        case 'NE': return mips.NotEq()
        case 'LT_S': return mips.Less()
        case 'GT_S': return mips.Greater()
        case 'LE_S': return mips.LessEq()
        case 'GE_S': return mips.GreaterEq()
        case _:
            raise ValueError(f'Unknown binary operator: {binOp.name}')

def primToMips(p: tacSpill.prim) -> mips.Imm | mips.Reg:
    match p:
        case tacSpill.Const(value):
            return mips.Imm(value)
        case tacSpill.Name(var):
            return mips.Reg(var.name)
        
def getTmpRegName(vars: list[tacSpill.Ident]) -> str:
    '''
    Gets the next possible free register based on a list of occupied registers
    '''
    maxRegLetter = 's'
    maxRegNum = 0
    for var in vars:
        varNameLetter = var.name[1]
        varNameNum = int(var.name[2])
        
        if maxRegLetter == varNameLetter and maxRegNum < varNameNum:
            # If register kind is the same, pick the higher one of that kind
            maxRegNum = varNameNum
        elif maxRegLetter == 's' and varNameLetter == 't':
            # If var is in t but max is in s, replace max
            maxRegLetter = varNameLetter
            maxRegNum = varNameNum
    
    if maxRegLetter == 't':
        # If max register is either in t, increment it
        newTmp = f'$t{maxRegNum + 1}'
    else:
        # Else the max register has to be in s, so we need $t0
        newTmp = f'$t0'
    
    return newTmp