from lark import ParseTree
from lang_var.var_ast import *
from parsers.common import *
import common.log as log

grammarFile = "./src/parsers/lang_var/var_grammar.lark"

def parseTreeToExpAst(t: ParseTree) -> exp:
    match t.data:
        case 'int_exp':
            return IntConst(int(asToken(t.children[0])))
        case 'add_exp':
            e1, e2 = [asTree(c) for c in t.children]
            return BinOp(parseTreeToExpAst(e1), Add(), parseTreeToExpAst(e2))
        case 'sub_exp':
            e1, e2 = [asTree(c) for c in t.children]
            return BinOp(parseTreeToExpAst(e1), Sub(), parseTreeToExpAst(e2))
        case 'mul_exp':
            e1, e2 = [asTree(c) for c in t.children]
            return BinOp(parseTreeToExpAst(e1), Mul(), parseTreeToExpAst(e2))
        case 'usub_exp':
            return UnOp(USub(), parseTreeToExpAst(asTree(t.children[0])))
        case 'call_exp':
            # CNAME "(" args ")"
            args = asTree(t.children[1])
            return Call(Ident(str(asToken(t.children[0]))), parseTreeToArgsAst(args)) 
        case 'name_exp':
            return Name(Ident(str(asToken(t.children[0]))))
        case 'exp_1' | 'exp_2' | 'paren_exp':
            return parseTreeToExpAst(asTree(t.children[0]))
        case kind:
            raise Exception(f'unhandled parse tree of kind {kind} for exp: {t}')
        
def parseTreeToArgsAst(t: ParseTree) -> list[exp]:
    args: list[exp] = []
    for child in t.children:
        args.append(parseTreeToExpAst(asTree(child)))
    return args

def parseTreeToAssignAst(t: ParseTree) -> stmt:
    # CNAME "=" exp
    var = Ident(asToken(t.children[0]).value)
    right = parseTreeToExpAst(asTree(t.children[1]))

    return Assign(var, right)

def parseTreeToStmtAst(t: ParseTree) -> stmt:
    statement: stmt

    match t.data:
        case "stmt_exp":
                statement = StmtExp(parseTreeToExpAst(asTree(t.children[0])))
        case "stmt_assign":
                statement = parseTreeToAssignAst(asTree(t.children[0]))
        case kind:
            raise Exception(f'unhandled parse tree of kind {kind} for stmt: {t}')

    return statement

def parseTreeToStmtListAst(t: ParseTree) -> list[stmt]:
    stmts: list[stmt] = []

    match t.data:
        case "stmts":
            for child in t.children:
                statement = parseTreeToStmtAst(asTree(child))
                stmts.append(statement)
        case kind:
            raise Exception(f'unhandled parse tree of kind {kind} for stmts: {t}')

    return stmts

def parseTreeToModuleAst(t: ParseTree) -> mod:
    module: mod

    match t.data:
        case "mod":
            module = Module(parseTreeToStmtListAst(asTree(t.children[0])))
        case kind:
            raise Exception(f'unhandled parse tree of kind {kind} for module: {t}')

    return module

def parseModule(args: ParserArgs) -> mod:
    parseTree = parseAsTree(args, grammarFile, 'mod')
    ast = parseTreeToModuleAst(parseTree)
    log.debug(f'AST: {ast}')
    return ast
