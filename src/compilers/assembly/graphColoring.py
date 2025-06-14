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
    
    # Initialize forbidden colors for each variable
    for vertex in g.vertices:
        forbidden[vertex] = set()
    
    # Initialize priority queue with all variables
    # Priority is initially 0 since no neighbors are colored yet
    for vertex in g.vertices:
        q.push(vertex, 0)
    
    # Process variables in order of largest forbidden set
    while not q.isEmpty():
        # Get the variable with the largest forbidden set
        x = q.pop()
        
        # Choose the lowest available color for this variable
        color = chooseColor(x, forbidden)
        colors[x] = color
        
        # Update forbidden colors for all uncolored neighbors
        for neighbor in g.succs(x):
            if neighbor not in colors:  # Only update uncolored neighbors
                forbidden[neighbor].add(color)
                # Increase priority of neighbor since its forbidden set grew
                q.incPrio(neighbor, 1)
    
    # Create and return the register allocation map
    m = RegisterAllocMap(colors, maxRegs)
    return m
