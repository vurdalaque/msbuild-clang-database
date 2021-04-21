import sys, os, re
from pathlib import Path
import ply.lex as lex
import ply.yacc as yacc

class CMakeNode(object):
    def __init__(self, typ, value):
        self.type = typ
        self.value = value

    def __str__(self):
        if type(self.value) == type('str') or type(self.value) == CMakeNode:
            return f'{self.type}:{self.value}'
        return f'{self.type}: [{", ".join([str(x) for x in self.value])}]'

    def __eq__(self, l):
        return str(l) == self.__str__()

    def append(self, value):
        self.value.append(value)

    def toString(self):
        return ', '.join(self.value)

class CMakeListsFile(object):

    def __init__(self, url = None):
        self.url = url
        if url is None:
            self.valid = Path('./CMakeLists.txt').exists()
            self.path = str(Path('.').absolute()).replace('\\', '/')
            if self.valid is True:
                self.fullPath = str(Path('./CMakeLists.txt').absolute()).replace('\\', '/')
        else:
            from urllib import request as req
            try:
                d = req.urlopen(url)
                self.content = d.read().decode('utf-8')
                self.valid = True
            except:
                self.valid = False

    def __str__(self):
        if self.valid is False:
            return 'no CMakeLists.txt at {path}'.format(path = self.path if self.url is None else self.url)
        return self.fullPath if self.url is None else self.url

    def read(self):
        if self.valid is False:
            return ''
        if self.url is not None:
            return self.content
        with open(self.fullPath) as f:
            return f.read()


class CMakeListsParse(object):

    def __init__(self, debug = False):
        self.valid = False
        self.init_ply(module=self, debug = debug)
        self.__bracket_size = -1
        self.__parents = -1

    def init_ply(self, **kwargs):
        self.lex = lex.lex(**kwargs)
        self.parser = yacc.yacc(**kwargs, start='file')

    def parse_lex(self, data):
        result = []
        self.lex.input(data)
        while True:
            tok = self.lex.token()
            if not tok:
                break
            result.append(tok)

        return result

    def parse(self, data):
        if type(data) == CMakeListsFile:
            print(data.read())
            return self.parser.parse(data.read(), lexer = self.lex)
        return self.parser.parse(data, lexer = self.lex)

    ## lexer routines

    literals = '()'
    states = (
            ('bargument', 'exclusive'), #  bracket_argument [===[...]===]
            ('qargument', 'exclusive'), #  "any string\\n with carrying"
            ('parenthises', 'inclusive'),
            )
    tokens = (
            'identifier',
            'space',
            'escape_sequence',
            'quoted_argument',
            'bracket_argument',
            'line_comment',
            'bracket_comment',
            'newline',
            'unquoted_argument',
            )
    t_identifier = r'[A-Za-z_][A-Za-z0-9_]*'
    t_space = r'[ \t]+'
    t_escape_sequence = r'\\(([^A-Za-z0-9])|(\t|\r|\n|;))'
    t_line_comment = r'\#[^\[]?[^\n]*'
    t_newline = r'\n'
    t_bracket_comment = r'\#\[\[[^\]]*\]\]'

    ## watch for parethises and gather arguments

    @lex.TOKEN('\(')
    def t_parenthises(self, t):
        self.__parents += 1
        t.type = '('
        t.lexer.begin('parenthises')
        return t

    @lex.TOKEN('\)')
    def t_parenthises_end(self, t):
        self.__parents -= 1
        t.type = ')'
        if self.__parents < 0:
            t.lexer.begin('INITIAL')
        return t

    @lex.TOKEN('\[=*\[')  # somewhy, inclusive eats pattern
    def t_parenthises_bargument_starts(self, t):
        return self.t_bargument(t)

    @lex.TOKEN(r';')
    def t_parenthises_semicolon(self, t):
        pass

    @lex.TOKEN(r"(\\([ ;])|([^; \s\(\)\#\"\\\s]))+")
    def t_parenthises_unquoted(self, t):
        t.type = 'unquoted_argument'
        return t

    ## tokenize bracket_argument

    @lex.TOKEN('\[=*\[')
    def t_bargument(self, t):
        if self.__bracket_size >= 0:
            self.__bracket += t.value
            return
        self.__bracket = ''
        self.__bracket_size = len(t.value) - 2
        t.lexer.begin('bargument')

    @lex.TOKEN('\]=*\]')
    def t_bargument_ends(self, t):
        t.type = 'bracket_argument'
        if len(t.value) != self.__bracket_size + 2:
            if t.value == ']]':
                t.lexer.lexpos -= 1
                self.__bracket += t.value[:-1]
            else:
                self.__bracket += t.value
            return

        t.value = self.__bracket
        self.__bracket = ''
        self.__bracket_size = -1
        t.lexer.begin("INITIAL") if self.__parents < 0 else t.lexer.begin('parenthises')
        return t

    @lex.TOKEN(r'[\s\S\w\W\d\D]')
    def t_bargument_any(self, t):
        self.__bracket += t.value

    ## tokenize quoted_argument

    @lex.TOKEN('"')
    def t_qargument(self, t):
        #  t.lexer.code_start = t.lexer.lexpos
        t.lexer.begin('qargument')
        self.__quoted_arg = ''

    @lex.TOKEN('"')
    def t_qargument_ends(self, t):
        t.value = self.__quoted_arg  # t.lexer.lexdata[t.lexer.code_start:t.lexer.lexpos - 1]
        t.type = "quoted_argument"
        t.lexer.begin("INITIAL") if self.__parents < 0 else t.lexer.begin('parenthises')
        return t

    @lex.TOKEN(r'\\"')
    def t_qargument_escaped_quote(self, t):
        self.__quoted_arg += t.value

    @lex.TOKEN(r'\\\s*\n')
    def t_qargument_escaped_newline(self, t):
        pass

    @lex.TOKEN('[^"]')
    def t_qargument_any(self, t):
        self.__quoted_arg += t.value
        pass

    ## end quoted_argument

    def t_parenthises_error(self, t):
        pass

    def t_qargument_error(self, t):
        print('failed to parse quoted argument');

    def t_bargument_error(self, t):
        print('failed to parse bracket_argument')

    def t_error(self, t):
        print('lexer error')

    ## syntax routines

    #  def p_eps(self, p):
        #  '''eps : '''
        #  print('eps')
        #  pass

    def p_separation(self, p):
        '''separation : separation space
                      | separation newline
                      | space
                      | newline'''
        print('>> separation')
        pass

    def p_line_ending(self, p):
        '''line_ending : newline
                       | line_comment newline'''
        print('>> line ending', len(p))
        p[0] = CMakeNode('line_ending', '')

    def p_bracket_argument_rule(self, p):
        '''bracket_argument_rule : separation bracket_argument separation'''
        p[0] = CMakeNode('bracket_argument', p[2])
        print('>> bracket_argument')

    def p_quoted_argument_rule(self, p):
        '''quoted_argument_rule : separation quoted_argument separation'''
        p[0] = CMakeNode('quoted_argument', p[2])
        print('>> quoted_argument')

    def p_unquoted_argument_rule(self, p):
        '''unquoted_argument_rule : separation unquoted_argument separation'''
        p[0] = CMakeNode('unquoted_argument', p[2])
        print('>> unquoted_argument')

    def p_argument(self, p):
        '''argument : bracket_argument_rule
                    | quoted_argument_rule
                    | unquoted_argument_rule '''
        p[0] = p[1]
        print('>> argument')

    def p_arguments(self, p):
        '''arguments : arguments separation argument
                     | argument '''
        if p[0] is None and len(p) == 2:
            p[0] = CMakeNode('arguments', [])
        else:
            p[0] = p[1]

        print('>> arguments')
        p[0].append(p[len(p) - 1])

    def p_command_invocation(self, p):
        '''command_invocation : separation identifier separation '(' arguments ')'
        '''
        print('>> p_command_invocation')
        p[0] = CMakeNode('command_invocation', CMakeNode(p[2], p[5]))

    def p_file_element(self, p):
        '''file_element : command_invocation line_ending
                        | bracket_comment line_ending
                        | space line_ending
                        | line_ending '''
                        #  | file_element bracket_comment line_ending
                        #  | file_element space line_ending
        print('>> file element ', len(p))
        if type(p[1]) == CMakeNode:
            if p[1].type == 'command_invocation':
                p[0] = p[1]
        for x in p:
            print(x)

    def p_file(self, p):
        '''file : file file_element
                | file_element
                '''
        print('>> file')
        for x in p:
            print(x)

    def p_error(self, p):
        pass

import unittest

class TestCMakeListsParse(unittest.TestCase):

    def eq(self, token, type, value):
        return token.value == value and token.type == type

    def list_eq(self, tokens, lst):
        if len(tokens) != len(lst):
            print('length mismatched', len(tokens), len(lst))
            return False
        for i in range(0, len(lst)):
            if self.eq(tokens[i], lst[i][0], lst[i][1]) == False:
                print('tokens not equal: ', tokens[i], lst[i][0], lst[i][1])
                return False
        return True

    #  @unittest.skip('sample')
    def testLexerIdentifiers(self):
        c = CMakeListsParse()
        r = c.parse_lex('this0 i1_s O0nly IDs')
        self.assertTrue(self.list_eq(r, [
            ['identifier', 'this0'], ['space', ' '],
            ['identifier', 'i1_s'], ['space', ' '],
            ['identifier', 'O0nly'], ['space', ' '],
            ['identifier', 'IDs'], ]))

    def testLexerIdentifiersString(self):
        c = CMakeListsParse()
        r = c.parse_lex('\\;hello "st\\"ring multi" world')
        self.assertTrue(self.list_eq(r, [
            ['escape_sequence', r'\;'], ['identifier', 'hello'], ['space', ' '],
            ['quoted_argument', r'st\"ring multi'], ['space', ' '], ['identifier', 'world'], ]))

    def testLexerStringCarry(self):
        c = CMakeListsParse()
        r = c.parse_lex('this "string has\\\n new lined ending"')
        self.assertTrue(self.list_eq(r, [
            ['identifier', 'this'], ['space', ' '],
            ['quoted_argument', 'string has new lined ending'], ]))
        r = c.parse_lex('this "string has\\ \t\n new lined ending"')
        self.assertTrue(self.list_eq(r, [
            ['identifier', 'this'], ['space', ' '],
            ['quoted_argument', 'string has new lined ending'], ]))

    def testLexerComments(self):
        c = CMakeListsParse()
        r = c.parse_lex('comments# this is line comment\nnext_line')
        self.assertTrue(self.list_eq(r, [
            ['identifier', 'comments'], ['line_comment', '# this is line comment'],
            ['newline', '\n'], ['identifier', 'next_line'], ]))
        r = c.parse_lex('comments#[[this is bracket comment\nnext line]]next_line')
        self.assertTrue(self.list_eq(r, [
            ['identifier', 'comments'], ['bracket_comment', '#[[this is bracket comment\nnext line]]'], ['identifier', 'next_line'], ]))
        r = c.parse_lex('comments#[[]]next_line')
        self.assertTrue(self.list_eq(r, [
            ['identifier', 'comments'], ['bracket_comment', '#[[]]'], ['identifier', 'next_line'], ]))

    def testLexerBracketArgument(self):
        c = CMakeListsParse()
        r = c.parse_lex('comments \t[[this is bracket ]=]argument next line]] next_id')
        self.assertTrue(self.list_eq(r, [
            ['identifier', 'comments'], ['space', ' \t'], ['bracket_argument', 'this is bracket ]=]argument next line'], ['space', ' '], ['identifier', 'next_id'], ]))
        r = c.parse_lex('comments [===[this [[is]] bracket]=] argument]==]\nnext line]===] next_id')
        self.assertTrue(self.list_eq(r, [
            ['identifier', 'comments'], ['space', ' '], ['bracket_argument', 'this [[is]] bracket]=] argument]==]\nnext line'], ['space', ' '], ['identifier', 'next_id'], ]))
        r = c.parse_lex('[====[arg=[1]]]====]')
        self.assertTrue(self.list_eq(r, [
            ['bracket_argument', 'arg=[1]]'], ]))

    def testLexerUnquotedArgument(self):
        c = CMakeListsParse()
        r = c.parse_lex('\nset(escaped\\;\\ space)')
        self.assertTrue(self.list_eq(r, [
            [ 'newline', '\n'], ['identifier', 'set'], ['(', '('], ['unquoted_argument', 'escaped\\;\\ space'], [')', ')'], ]))
        r = c.parse_lex('\nset(Th\\;is;Divides;Into;Five;Arguments)')
        self.assertTrue(self.list_eq(r, [
            [ 'newline', '\n'], ['identifier', 'set'], ['(', '('],
            ['unquoted_argument', 'Th\\;is'], ['unquoted_argument', 'Divides'], ['unquoted_argument', 'Into'],
            ['unquoted_argument', 'Five'], ['unquoted_argument', 'Arguments'], [')', ')'], ]))

    def testSyntaxFuncTest(self):
        self.assertEqual(
                CMakeListsParse().parse('func(arg0 arg1 arg2)'),
                CMakeNode('command_invocation',
                    CMakeNode('func', CMakeNode('arguments', [
                        CMakeNode('unquoted_argument', 'arg0'),
                        CMakeNode('unquoted_argument', 'arg1'),
                        CMakeNode('unquoted_argument', 'arg2'), ]))))
        self.assertEqual(
                CMakeListsParse().parse('  func   (arg0;arg1;arg2 )'),
                CMakeNode('command_invocation',
                    CMakeNode('func', CMakeNode('arguments', [
                        CMakeNode('unquoted_argument', 'arg0'),
                        CMakeNode('unquoted_argument', 'arg1'),
                        CMakeNode('unquoted_argument', 'arg2'), ]))))
        self.assertEqual(
                CMakeListsParse().parse('  func  (  "arg0" ;  [====[arg[=1=]]====] arg2 )'),
                CMakeNode('command_invocation',
                    CMakeNode('func', CMakeNode('arguments', [
                        CMakeNode('quoted_argument', 'arg0'),
                        CMakeNode('bracket_argument', 'arg[=1=]'),
                        CMakeNode('unquoted_argument', 'arg2'), ]))))


    def testLast(self):
        print(CMakeListsParse().parse('func(arg0 arg1 arg2)\n'))
        #  f = CMakeListsFile('https://raw.githubusercontent.com/Kitware/CMake/master/Tests/EmptyProperty/CMakeLists.txt')
        #  print(CMakeListsParse(debug = True).parse(f))

if __name__ == '__main__':
    unittest.main()
