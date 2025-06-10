from assembly.common import *
from assembly.graph import Graph
import assembly.tac_ast as tac

def instrDef(instr: tac.instr) -> set[tac.ident]:
    """
    Returns the set of identifiers defined by some instrucution.
    """
    match instr:
        case tac.Assign(var, _):
            return {var}
        case tac.Call(var, _, _):
            return {var} if (var is not None) else set()
        case tac.GotoIf() | tac.Goto() | tac.Label():
            return set()

def instrUse(instr: tac.instr) -> set[tac.ident]:
    """
    Returns the set of identifiers used by some instrucution.
    """
    match instr:
        case tac.Assign(_, right):
            return set(getIdentsOfExp(right))
        case tac.Call(_, _, args):
            ids: list[tac.ident] = []
            for a in args:
                id = getIdentOfPrim(a)
                if id is not None:
                    ids.append(id)
            return set(ids)
        case tac.GotoIf(test, _):
            id = getIdentOfPrim(test)
            return { id } if (id is not None) else set()
        case tac.Goto(_) | tac.Label(_):
            return set()

def getIdentOfPrim(p: tac.prim) -> Optional[tac.ident]:
    match p:
        case tac.Const():
            return None
        case tac.Name(var):
            return tac.Ident(var.name)
        
def getIdentsOfExp(exp: tac.exp) -> list[tac.ident]:
    match exp:
        case tac.Prim(p):
            id = getIdentOfPrim(p)
            return [id] if id is not None else []
        case tac.BinOp(l, _, r):
            ret: list[tac.ident] = []
            idL = getIdentOfPrim(l)
            idR = getIdentOfPrim(r)
            if idL is not None:
                ret.append(idL)
            if idR is not None:
                ret.append(idR)
            return ret

# Each individual instruction has an identifier. This identifier is the tuple
# (index of basic block, index of instruction inside the basic block)
type InstrId = tuple[int, int]

class InterfGraphBuilder:
    def __init__(self):
        # self.before holds, for each instruction I, to set of variables live before I.
        self.before: dict[InstrId, set[tac.ident]] = {}
        # self.after holds, for each instruction I, to set of variables live after I.
        self.after: dict[InstrId, set[tac.ident]] = {}

    def liveStart(self, bb: BasicBlock, s: set[tac.ident]) -> set[tac.ident]:
        """
        Given a set of variables s and a basic block bb, liveStart computes
        the set of variables live at the beginning of bb, assuming that s
        are the variables live at the end of the block.

        Essentially, you have to implement the subalgorithm "Computing L_start" from
        slide 46 here. You should update self.after and self.before while traversing
        the instructions of the basic block in reverse.
        """
        # No instructions: live before variables are the same as at the end
        if bb.last is None:
            self.before[(bb.index, 0)] = s
            self.after[(bb.index, 0)] = s
            return s
        
        # Go through instructions in reverse order and get 'before' of i
        afterCurrent = s
        beforeCurrent = s
        k = len(bb.instrs) - 1
        for instr in reversed(bb.instrs):
            # Compute L[after] and L[before] for current instruction
            afterCurrent = beforeCurrent
            beforeCurrent = (afterCurrent - instrDef(instr)).union(instrUse(instr))
            # Update self.before and self.after
            self.before[(bb.index, k)] = beforeCurrent
            self.after[(bb.index, k)] = afterCurrent
            # Update index of k
            k -= 1

        return beforeCurrent

    def liveness(self, g: ControlFlowGraph):
        """
        This method computes liveness information and fills the sets self.before and
        self.after.

        You have to implement the algorithm for computing liveness in a CFG from
        slide 46 here.
        """
        vertices = g.vertices

        # Dictionary for tracking changes of IN[B]: vertex-ID -> (IN[B], dirty)
        verticesIn: dict[int, Tuple[set[tac.ident], bool]] = {}
        for v in vertices:
            verticesIn[v] = (set(), True)
        
        # TODO: multiple cycles (idea: mark as dirty if changed in current cycle. Every v is dirty initially. If L[start] hasn't changed => dirty = false. We're finished if all vertices aren't dirty)
        
        # For each basic block
        for v in vertices:
            # Get successors
            succs = g.succs(v)

            # Compute L[out]
            lOut: set[tac.ident] = set()
            for s in succs:
                lIn = self.before.get((s, 0))
                if lIn is not None:
                    lOut.union(lIn)
            self.liveStart(g.getData(v), lOut)


    def __addEdgesForInstr(self, instrId: InstrId, instr: tac.instr, interfG: InterfGraph):
        """
        Given an instruction and its ID, adds the edges resulting from the instruction
        to the interference graph.

        You should implement the algorithm specified on the slide
        "Computing the interference graph" (slide 50) here.
        """
        raise ValueError('todo')

    def build(self, g: ControlFlowGraph) -> InterfGraph:
        """
        This method builds the interference graph. It performs three steps:

        - Use liveness to fill the sets self.before and self.after.
        - Setup the interference graph as an undirected graph containing all variables
          defined or used by any instruction of any basic block. Initially, the
          graph does not have any edges.
        - Use __addEdgesForInstr to fill the edges of the interference graph.
        """
        raise ValueError('todo')

def buildInterfGraph(g: ControlFlowGraph) -> InterfGraph:
    builder = InterfGraphBuilder()
    return builder.build(g)
