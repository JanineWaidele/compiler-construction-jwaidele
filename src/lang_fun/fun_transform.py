from lang_fun.fun_ast import *
import lang_fun.fun_astAtom as atom
from common.compilerSupport import *
import common.utils as utils

type Temporaries = list[tuple[atom.Ident, atom.exp]]

class Ctx:
    """
    Context for getting fresh variable names.
    """
    def __init__(self):
        self.freshVars: dict[ident, ty] = {}
    def newVar(self, t: ty) -> ident:
        """
        Get a fresh variabler of the given type.
        """
        nameId = len(self.freshVars)
        x = Ident(f'tmp_{nameId}')
        self.freshVars[x] = t
        return x

def transExpAtomic(e: exp, ctx: Ctx) -> tuple[atom.atomExp, Temporaries]:
    """
    Translates e to an atomic expression. Essentially a shortcut for transExp(e, True, ctx).
    """
    (res, ts) = transExp(e, True, ctx)
    #print(type(res))
    #iat: atom.atomExp = atom.IntConst(0,Int())
    #print(type(atom.AtomExp(iat,NotVoid(Int()))))
    match res:
        case atom.AtomExp(a):
            return (a, ts)
        # case atom.ArrayInitStatic(ely, eli_ty):
        #     for el in ely:

        case _:
            utils.abort(f'transExp with needAtom=True failed to return an atomic expression: {e}')

def assertExpNotVoid(e: exp | atom.exp) -> ty:
    """
    Asserts that e is an expression of a non-void type.
    """
    match e.ty:
        case None:
            raise ValueError(f'type still None after type-checking. Expression: {e}')
        case Void():
            raise ValueError(f'type of {e} is Void after type-checking.')
        case NotVoid(t):
            return t

def atomic(needAtomic: bool, e: atom.exp, tmps: Temporaries, ctx: Ctx) -> tuple[atom.exp, Temporaries]:
    """
    Converts e to an atomic expression if needAtomic is True.
    """
    if needAtomic:
        match e:
            case atom.AtomExp():
                return (e, tmps)
            case _:
                t = assertExpNotVoid(e)
                tmp = ctx.newVar(t)
                tmps.append((tmp, e))
                return (atom.AtomExp(atom.VarName(tmp, t),NotVoid(t)), tmps)
    else:
        return (e, tmps)

def restyOfResultTy(ty: optional[resultTy]) -> resultTy:
    match ty:
        case NotVoid(t):
            return NotVoid(t)
        case Void():
            return Void()
        case _:
            return Void()

def tyOfResultTy(ty: optional[resultTy]) -> ty:
    match ty:
        case NotVoid(t):
            return t
        case Void():
            return Int()
        case _:
            return Int()
        
def tyOfExp(ae: atom.exp)->ty:
    # AtomExp | Call | UnOp | BinOp | ArrayInitDyn | ArrayInitStatic | Subscript
    return tyOfResultTy(ae.ty)

def unpackTemporary(tempor: Temporaries)->tuple[atom.Ident,atom.exp]:
    (ati, ate) = tempor[0]
    return (ati, ate)
 

def transExp(e: exp, needAtomic: bool, ctx: Ctx) -> tuple[atom.exp, Temporaries]:
    """
    Translates expression e (of type array_ast.exp) to an expression of type
    array_astAtom.exp, together with a list of temporary variables used by
    the translated expression.

    If the flag needAtomic is True, then the translated expression is an atomic expression,
    that is something of the form array_astAtom.AtomExp(...).
    """
    t = restyOfResultTy(e.ty)
    match e:
        case IntConst(v):
            return (atom.AtomExp(atom.IntConst(v, Int()), t), [])
        case BoolConst(v):
            return (atom.AtomExp(atom.BoolConst(v, Bool()), t), [])
        case Call(funExp, args):
                    # help in call case from Anton Kesy
                    (atomArgs, tmps) = utils.unzip([transExp(a, False, ctx) for a in args])
                    match funExp:
                        case Name(var, scope, nameTy):
                            match scope:
                                case Var():  
                                    match tyOfResultTy(nameTy):     
                                        case Fun(fp):
                                            call_target = atom.Call(atom.CallTargetIndirect(var, fp, t), atomArgs, restyOfResultTy(nameTy))
                                        case _:
                                            call_target = atom.Call(atom.CallTargetIndirect(var, [], t), atomArgs, restyOfResultTy(nameTy))
                                case UserFun():
                                    call_target = atom.Call(atom.CallTargetDirect(var), atomArgs, t)
                                case BuiltinFun():
                                    call_target = atom.Call(atom.CallTargetBuiltin(var), atomArgs, t)
                                case None:
                                    raise RuntimeError("Scope is none")
                            return atomic(needAtomic, call_target, utils.flatten(tmps), ctx)
                        
                        case Subscript(_,_,scTy): 
                            (atomCall, tmps1) = transExpAtomic(funExp, ctx)
                            if isinstance(atomCall,atom.VarName):
                                atvarname = atomCall.var.name
                                match tyOfResultTy(scTy):
                                    case Fun(fpams):
                                        return atomic(needAtomic, atom.Call(atom.CallTargetIndirect(atom.Ident(atvarname), fpams, t), atomArgs, restyOfResultTy(scTy)), tmps1, ctx)
                                    case _:
                                        return atomic(needAtomic, atom.Call(atom.CallTargetIndirect(atom.Ident(atvarname), [], t), atomArgs, restyOfResultTy(scTy)), tmps1, ctx)
                            else:
                                raise RuntimeError('atomcall not varname')

                        case Call(_,_,cTy):
                            
                            (atomCall, tmps1) = transExpAtomic(funExp, ctx)
                            if isinstance(atomCall,atom.VarName):
                                atvarname = atomCall.var.name
                                match tyOfResultTy(cTy):
                                    case Fun(params):
                                        return atomic(needAtomic, atom.Call(atom.CallTargetIndirect(atom.Ident(atomCall.var.name), params, t), atomArgs, restyOfResultTy(t)), tmps1, ctx)
                                    case _:
                                        return atomic(needAtomic, atom.Call(atom.CallTargetIndirect(atom.Ident(atomCall.var.name), [], t), atomArgs, restyOfResultTy(t)), tmps1, ctx)
                            else:
                                raise ValueError("Call exp not valid")
                        case _:
                            raise ValueError("No valid exp")
                                
        case UnOp(op, sub):
            (atomSub, tmps) = transExp(sub, False, ctx)
            return atomic(needAtomic, atom.UnOp(op, atomSub, t), tmps, ctx)
        case BinOp(left, op, right):
            (l, tmps1) = transExp(left, needAtomic, ctx)
            (r, tmps2) = transExp(right, needAtomic, ctx)
            return atomic(needAtomic, atom.BinOp(l, op, r, t), tmps1 + tmps2, ctx)
        case Name(x, scop):
            xt = assertExpNotVoid(e)
            match scop:
                case Var():
                    return (atom.AtomExp(atom.VarName(x, xt), t), [])
                case UserFun() | BuiltinFun():
                    return (atom.AtomExp(atom.FunName(x, xt), t), [])
                case _:
                    raise RuntimeError('wrong call type')
        case ArrayInitDyn(lenExp, elemInit):
            (atomLen, tmps1) = transExpAtomic(lenExp, ctx)
            (atomElem, tmps2) = transExpAtomic(elemInit, ctx)
            return atomic(needAtomic, atom.ArrayInitDyn(atomLen, atomElem, t), tmps1 + tmps2, ctx)
        case ArrayInitStatic(initExps):
            (args, tmp) = utils.unzip([transExpAtomic(i, ctx) for i in initExps])
            return atomic(needAtomic, atom.ArrayInitStatic(args, t), utils.flatten(tmp), ctx)
        case Subscript(arrExp, indexExp):
            (atomArr, tmps1) = transExpAtomic(arrExp, ctx)
            (atomIndex, tmps2) = transExpAtomic(indexExp, ctx)
            return atomic(needAtomic, atom.Subscript(atomArr, atomIndex, t), tmps1 + tmps2, ctx)

def mkAssigns(tmps: Temporaries) -> list[atom.stmt]:
    """
    Turns a list of temporary variables into a list of statements.
    """
    return [atom.Assign(x, e) for (x, e) in tmps]

def transStmt(s:stmt, ctx: Ctx) -> list[atom.stmt]:
    """
    Translates statement s (of type array_ast.stmt) to a statement of type
    array_astAtom.stmt.
    """
    #print(s)
    match s:
        case StmtExp(e):
            (a, tmps) = transExp(e, False, ctx)
            return mkAssigns(tmps) + [atom.StmtExp(a)]
        case Assign(x, e):
            (a, tmps) = transExp(e, False, ctx)
            return mkAssigns(tmps) + [atom.Assign(x, a)]
        case IfStmt(cond, thenBody, elseBody):
            (a, tmps1) = transExp(cond, False, ctx)
            stmts1 = transStmts(thenBody, ctx)
            stmts2 = transStmts(elseBody, ctx)
            return mkAssigns(tmps1) + [atom.IfStmt(a, stmts1, stmts2)]
        case WhileStmt(cond, body):
            (a, tmps1) = transExp(cond, False, ctx)
            stmts = transStmts(body, ctx)
            return mkAssigns(tmps1) + [atom.WhileStmt(a, stmts)]
        case SubscriptAssign(leftExp, indexExp, rightExp):
            (l, tmps1) = transExpAtomic(leftExp, ctx)
            (i, tmps2) = transExpAtomic(indexExp, ctx)
            (r, tmps3) = transExp(rightExp, False, ctx)
            return mkAssigns(tmps1 + tmps2 + tmps3) + [atom.SubscriptAssign(l, i, r)]
        case Return(oe):
            if oe == None:
                return [atom.Return(None)]
            else:
                (ea, tmps) = transExp(oe,False,ctx)
                return mkAssigns(tmps) + [atom.Return(ea)] 

def transStmts(stmts: list[stmt], ctx: Ctx) -> list[atom.stmt]:
    """
    Main entry point, transforming a list of statements.
    This function is called from compilers.array_compiler.compileModule.
    """
    result: list[atom.stmt] = []
    for s in stmts:
        result.extend(transStmt(s, ctx))
    return result
