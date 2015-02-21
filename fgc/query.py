#-*- coding: utf-8 -*-
from __future__ import print_function

import itertools as it, operator as op, functools as ft
import re, math

import pyparsing as pp
pp.ParserElement.enablePackrat()


class Grammar(object):

	# https://docs.python.org/2/library/operator.html#mapping-operators-to-functions
	ops_add = {'+': op.add,'-': op.sub}
	ops_mult = {'*': op.mul, '/': op.truediv, '//': op.div, '%': op.mod}
	ops_pow = {} # {'**': op.pow, log} - not used here
	ops_math = dict(it.chain.from_iterable(v.viewitems() for v in [ops_add, ops_mult, ops_pow]))

	_op_c, _op_nc = lambda a,b: a in b, lambda a,b: a not in b # op.contains is backwards
	ops_sets = {'in': _op_c, '∈': _op_c, 'not_in': _op_nc}
	ops_func = {'abs': abs, 'ceil': math.ceil, 'floor': math.floor, 'round': lambda n: int(round(n))}
	ops_comparison = {
		'<': op.lt, '<=': op.le, '>': op.gt, '>=': op.ge,
		'is': op.is_, 'is_not': op.is_not,
		'==': op.eq, '=': op.eq,
		'!=': op.ne, '<>': op.ne, '/=': op.ne, '=/=': op.ne }
	# ops_string = 're', 'rx'

	symbol = pp.Regex(ur'[\w_]*[^\W\d_][\w_]*', re.U).setName('symbol').setResultsName('name')

	int_ = pp.Regex(ur'[+-]?\d+').setParseAction(lambda t: int(t[0])).setName('integer')
	float_ = pp.Regex(ur'[+-]?\d+\.\d*').setParseAction(lambda t: float(t[0])).setName('float')
	number = (float_ | int_).setName('number')

	string = (pp.QuotedString('"') | pp.QuotedString("'"))\
		.setParseAction(pp.removeQuotes).setName('string')

	true = (pp.CaselessKeyword('true') | pp.CaselessKeyword('t')).setParseAction(lambda: True)
	false = (pp.CaselessKeyword('false') | pp.CaselessKeyword('f')).setParseAction(lambda: False)
	boolean = (true | false).setName('boolean')

	value = number | string | boolean

	_one_of = lambda vals,**k: pp.oneOf(' '.join(vals), caseless=True, **k)

	logic_not = _one_of(['not', '~', '!'])
	logic_and = _one_of(['and', '&', '&&'])
	logic_or = _one_of(['or', '|', '||'])
	logic_sets = _one_of(ops_sets)
	logic_comparison = _one_of(ops_comparison)
	logic_func = _one_of(ops_func)

	math_mult, math_add = _one_of(ops_mult), _one_of(ops_add)


class Query(object):

	grammar_cls = Grammar

	def __init__(self, expr, **kws):
		self.expr, self.params = expr, kws
		self.g = g = self.grammar_cls()
		atom = g.value | g.symbol.copy().setParseAction(lambda s,l,t: self.params[t[0].lower()])
		self.syntax = pp.operatorPrecedence(atom, [
			(g.logic_func, 1, pp.opAssoc.RIGHT, lambda s,l,t: g.ops_func[t[0][0]](t[0][1])),
			(g.math_mult, 2, pp.opAssoc.LEFT, self.eval_math),
			(g.math_add, 2, pp.opAssoc.LEFT, self.eval_math),
			(g.logic_sets, 2, pp.opAssoc.LEFT, lambda s,l,t: g.ops_sets[t[0][1]](t[0][0], t[0][2])),
			(g.logic_comparison, 2, pp.opAssoc.LEFT, self.eval_comparison),
			(g.logic_not, 1, pp.opAssoc.RIGHT, lambda s,l,t: not t[0][1]),
			(g.logic_and, 2, pp.opAssoc.LEFT, lambda s,l,t: t[0][0] and t[0][2]),
			(g.logic_or, 2, pp.opAssoc.LEFT, lambda s,l,t: t[0][0] or t[0][2]) ])

	@property
	def params(self): return self._params
	@params.setter
	def params(self, vals): self._params = dict((k.lower(), v) for k,v in vals.viewitems())

	def it_ngrams(self, seq, n):
		z = (it.islice(seq, i, None) for i in range(n))
		return zip(*z)

	def eval_math(self, s, l, t):
		res = t[0][0]
		for o, v in self.it_ngrams(t[0][1:], 2):
			res = self.g.ops_math[o](res, v)
		return res

	def eval_comparison(self, s, l, t):
		res = t[0][0]
		for o, v in self.it_ngrams(t[0][1:], 2):
			res = self.g.ops_comparison[o](res, v)
			if not res: break
			res = v
		else: res = True
		return res

	def eval(self, **kws):
		params_old = self.params.copy()
		self.params.update(kws)
		try: return self.syntax.parseString(self.expr, parseAll=True)[0]
		finally: self.params = params_old


if __name__ == "__main__":
	params = {
		'FRP': 100,
		'satellite': 'A',
		'letters': 'abcde',
	}
	tests = [
		("199 / 2 > FRP", False),
		("5 + 45 * 2 > FRP", False),
		("-5+5 < FRP", True),
		("99.9 < FRP", True),
		("satellite is 'N'", False),
		("FRP - 100 == 0", True),
		("FRP = 1 and satellite = 'T'", False),
		("FRP <> 1 and not satellite = 'T'", True),
		("1 is_not 1", False),
		("'a' not_in letters", False),
		("'c' in letters", True),
		("letters ∈ letters", True),
		("not(1 <> 2) is true", False),
		("abs((2-6)/2) * 3", 6),
		("not abs(2-3) is false", True),
		("round(3.6)", 4),
		("(1 <> 2) is true", True),
		("(FRP = 1) and ( (satellite = 'T') or (satellite iS 'A' ))", False),
	]
	q = Query(**params)
	for expr, res0 in tests:
		print('Processing:', expr)
		res = q.eval(expr)
		assert res == res0, [expr, res, res0]
