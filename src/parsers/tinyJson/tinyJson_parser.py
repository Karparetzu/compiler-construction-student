from parsers.common import *

type Json = str | int | dict[str, Json]

def ruleJson(toks: TokenStream) -> Json:
    return alternatives("json", toks, [ruleObject, ruleString, ruleInt])

# object: "{", entryList, "}"
def ruleObject(toks: TokenStream) -> dict[str, Json]:
    toks.ensureNext("LBRACE")
    entryList = ruleEntryList(toks)
    toks.ensureNext("RBRACE")

    return entryList

# entryList: | entryListNotEmpty
def ruleEntryList(toks: TokenStream) -> dict[str, Json]:
    if toks.lookahead().type == "STRING":
        return ruleEntryListNotEmpty(toks)
    else:
        return {}

# entryListNotEmpty: entry | entry, ",", entryListNotEmpty
def ruleEntryListNotEmpty(toks: TokenStream) -> dict[str, Json]:
    key, value = ruleEntry(toks)
    entryDict = {key: value}

    if toks.lookahead().type == "COMMA":
       toks.next()
       rest = ruleEntryListNotEmpty(toks)
       entryDict.update(rest)
       return entryDict
    else:
        return entryDict

# entry: string, ":", json
def ruleEntry(toks: TokenStream) -> tuple[str, Json]:
    key = ruleString(toks)
    toks.ensureNext("COLON")
    value = ruleJson(toks)
    return (key, value)

def ruleString(toks: TokenStream) -> str:
    return toks.ensureNext("STRING").value[1:-1]

def ruleInt(toks: TokenStream) -> int:
    return (int)(toks.ensureNext("INT").value)

def parse(code: str) -> Json:
    parser = mkLexer("./src/parsers/tinyJson/tinyJson_grammar.lark")
    tokens = list(parser.lex(code))
    log.info(f'Tokens: {tokens}')
    toks = TokenStream(tokens)
    res = ruleJson(toks)
    toks.ensureEof(code)
    return res
