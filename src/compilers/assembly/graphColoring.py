from assembly.common import *
import assembly.tac_ast as tac
import common.log as log
from common.prioQueue import PrioQueue

def chooseColor(x: tac.ident, forbidden: dict[tac.ident, set[int]]) -> int:
    """
    Returns the lowest possible color for variable x that is not forbidden for x.
    """
    forbiddenColors = forbidden[x]
    if not forbiddenColors:
        return 0
    
    freeColor = 0
    while freeColor in forbiddenColors:
        freeColor += 1
        
    return freeColor

def colorInterfGraph(g: InterfGraph, secondaryOrder: dict[tac.ident, int]={},
                     maxRegs: int=MAX_REGISTERS) -> RegisterMap:
    """
    Given an interference graph, computes a register map mapping a TAC variable
    to a TACspill variable. You have to implement the "simple graph coloring algorithm"
    from slide 58 here.

    - Parameter maxRegs is the maximum number of registers we are allowed to use.
    - Parameter secondaryOrder is used by the tests to get deterministic results even
      if two variables have the same number of forbidden colors.
    """
    log.debug(f"Coloring interference graph with maxRegs={maxRegs}")
    colors: dict[tac.ident, int] = {}
    forbidden: dict[tac.ident, set[int]] = {}
    q = PrioQueue(secondaryOrder)

    # 1. Get vertices of g -> w
    w = set(g.vertices)

    # Continue as long as w isn't empty
    while len(w) > 0:
        # 2. Get u with largest forbidden[u]
        maxForbiddenCount = 0
        canidates: list[tac.ident] = []
        for i in w:
            forbiddenCount = len(forbidden[i])
            if maxForbiddenCount < forbiddenCount:
                maxForbiddenCount = forbiddenCount
                canidates = [i]
            else:
                canidates.append(i)
           
            for canidate in canidates:
                q.push(canidate, secondaryOrder[canidate])
            
            u = q.pop()
            
            
        # TODO: Get ident with highest priority

    m = RegisterAllocMap(colors, maxRegs)
    return m
