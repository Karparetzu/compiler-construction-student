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
            return s
        
        # Go through instructions in reverse order and get 'before' of i
        afterCurrent = s
        beforeCurrent = s
        for i in reversed(range(0, len(bb.instrs))):
            # Compute L[after] and L[before] for current instruction
            afterCurrent = beforeCurrent
            beforeCurrent = (afterCurrent - instrDef(bb.instrs[i])) | instrUse(bb.instrs[i])
                
            # Update self.before and self.after
            self.before[(bb.index, i)] = beforeCurrent
            self.after[(bb.index, i)] = afterCurrent

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
                
        # As long as there's at least one vertex which is dirty (had a change during last cycle)
        while any(dirty == True for (_, dirty) in verticesIn.values()):
            # For each basic block
            for v in verticesIn.keys():
                # Get successors
                succs = g.succs(v)

                # Compute L[out]
                lOut: set[tac.ident] = set()
                for s in succs:
                    lIn = verticesIn[s][0]
                    lOut |= lIn
                
                # Compute L[start]
                lStart = self.liveStart(g.getData(v), lOut)

                # If lStart has changed: update and mark as dirty
                if verticesIn[v][0] != lStart:
                    verticesIn[v] = (lStart, True)
                else:
                    # Else keep previous value and not dirty anymore
                    verticesIn[v] = (verticesIn[v][0], False)

    def __addEdgesForInstr(self, instrId: InstrId, instr: tac.instr, interfG: InterfGraph):
        """
        Given an instruction and its ID, adds the edges resulting from the instruction
        to the interference graph.

        You should implement the algorithm specified on the slide
        "Computing the interference graph" (slide 50) here.
        """
        defs = instrDef(instr)
        after = self.after[instrId] - defs
        for tgt in after:
            for src in defs:
                if not isinstance(instr, tac.Assign) or src != tgt:
                    interfG.addEdge(src, tgt)

    def build(self, g: ControlFlowGraph) -> InterfGraph:
        """
        This method builds the interference graph. It performs three steps:

        - Use liveness to fill the sets self.before and self.after.
        - Setup the interference graph as an undirected graph containing all variables
          defined or used by any instruction of any basic block. Initially, theinstr
          graph does not have any edges.
        - Use __addEdgesForInstr to fill the edges of the interference graph.
        """
        # 1. Compute liveness for the CFG
        self.liveness(g)
        
        # 2. Setup interference graph (just add union of all defs and uses)
        # Note: can't use before and after because those don't contain defined but not used variables
        allVars: set[tac.ident] = set()
        for bb in g.values:
            for instr in bb.instrs:
                allVars |= instrDef(instr)
                allVars |= instrUse(instr)

        iGraph: InterfGraph = Graph('undirected')
        for var in allVars:
            iGraph.addVertex(var, None)

        # 3. Fill edges by going through each instruction in each block
        for bb in g.values:
            for i in range(0, len(bb.instrs)):
                self.__addEdgesForInstr((bb.index, i), bb.instrs[i], iGraph)

        return iGraph

def buildInterfGraph(g: ControlFlowGraph) -> InterfGraph:
    builder = InterfGraphBuilder()
    return builder.build(g)
