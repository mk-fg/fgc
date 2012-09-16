# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function


import itertools as it, operator as op, functools as ft
from collections import defaultdict
import types


default_enc = 'utf-8' # wanna get it from env? FUCK YOU!
element_uid = ft.partial(next, iter(xrange(int(2**31-1))))


class Element(object):
	_gv_base = 'id', '_style', '_attrs', 'graph'
	__slots__ = _gv_base

	# In case there'll be something more sophisticated (otherwise its a deprecation warning)
	def __new__(cls, *argz, **kwz): return super(Element, cls).__new__(cls)

	def _kwz_init(self, graph, gvstyle=None, id=None, **kwz):
		self.id = element_uid() if id is None else id
		if graph:
			self.graph = graph
			graph.elements[type(self)].add(self)
		self.style = 'base'
		if gvstyle is not None: self.style = gvstyle
		if kwz: self.attrs.update(kwz)

	@property
	def attrs(self):
		try: return self._attrs
		except AttributeError:
			self._attrs = dict()
			return self._attrs

	@property
	def style(self): # cow
		try: style = self._style.copy()
		except AttributeError: style = dict()
		self._style = style
		return style
	@style.setter
	def style(self, style):
		if isinstance(style, types.StringTypes):
			style = self.graph.styles.get(style, dict())
		if isinstance(style, dict): self.style.update(style)
		else:
			for style in style: self.style = style

	@property
	def properties(self):
		properties = self.style.copy()
		properties.update(self.attrs)
		return properties

	def __iter__(self): return iter(self.children)

	def __contains__(self, k): return k in self.attrs
	def __setitem__(self, k, v): self.attrs[k] = v
	def __getitem__(self, k): return self.attrs[k]
	def __delitem__(self, k): del self.attrs[k]
	def get(self, k, default=None):
		return default if not self._attrs else self.attrs.get(k, default)
	def update(self, *argz, **kwz): return self.attrs.update(*argz, **kwz)

	def __hash__(self): return hash(self.id)

	def remove(self): graph.elements[type(self)].discard(self)


class Node(Element):
	__slots__ = Element._gv_base\
		+ ('parent', 'children', 'children_idx', 'locked')

	def __init__(self, label=None, parent=None, **props):
		props['graph'] = props.get('graph', parent and parent.graph)
		if self._kwz_init(**props): raise TypeError
		elif parent and parent.locked: raise TypeError
		self.style = 'node'
		self.parent, self.locked = parent, False
		self.children, self.children_idx = set(), dict()
		if label: self.attrs['label'] = label
		if parent:
			parent.children.add(self)
			parent.children_idx[self.label] = self

	def add_child(self, *labels, **props):
		if 'parent' in props or self.locked: raise TypeError
		props['parent'] = self
		return self.graph.add_node(*labels, **props)
	add_node = add_child

	def get_child(self, *labels):
		result = list()
		for label in labels:
			if isinstance(label, types.StringTypes):
				result.append(self.children_idx[label])
			else:
				subtree = self
				for node in label: subtree = subtree.children_idx[node]
				result.append(subtree)
		return result[0] if len(labels) == 1 else result
	get_node = get_child

	@property
	def label(self):
		label = self['label']
		if label[0] != '<': return label.split('\\n', 1)[0]
		else:
			import re
			try: return re.match(r'.*?>\s*([^<\s]+)', label).group(1)
			except AttributeError: return label
	@property
	def name(self):
		return ('cluster{0}' if self.children else 'node{0}').format(self.id)\
			if isinstance(self.id, int) else '"{0}"'.format(self.id)
	def __unicode__(self): return self.name

	@property
	def _repr_short(self):
		return ''.join((
			'' if not self.parent else '{0}.'.format(self.parent._repr_short),
			'{0}[{1}]'.format(self.label, self.name) if 'label' in self else self.name ))
	def __repr__(self):
		return '<{0}: {1}>'.format(self.__class__.__name__, self._repr_short)

	def edge_from(self, *nodes, **props):
		edges = list(it.starmap(ft.partial(Edge, **props), self.product(nodes, self)))
		return edges[0] if len(edges) == 1 else edges
	def edge_to(self, *nodes, **props):
		edges = list(it.starmap(ft.partial(Edge, **props), self.product(self, nodes)))
		return edges[0] if len(edges) == 1 else edges

	def __sub__(self, node):
		return edge_to(node, op='--')
	def __lshift__(self, node):
		return edge_from(node, op='->')
	def __rshift__(self, node):
		return edge_to(node, op='->')

	def remove(self):
		super(Node, self).remove()
		if self.parent: self.parent.children.discard(self)
		self.locked = True

	@classmethod
	def product(cls, src, dst, graph=None, _final=False):
		if isinstance(src, Node):
			src, graph = src.children if src.children else [src], src.graph
		elif isinstance(src, types.StringTypes): src = graph.get_nodes_by_label(src)
		if isinstance(dst, Node):
			dst, graph = dst.children if dst.children else [dst], dst.graph
		elif isinstance(dst, types.StringTypes): dst = graph.get_nodes_by_label(dst)
		product = list(it.product(src, dst)) # can still yield [(node,cluster)], hence the _final kw
		return product if len(product) == 1 and _final else list(
			it.chain.from_iterable( cls.product(src, dst, graph=graph,
				_final=len(product) == 1) for src,dst in product ))


class Edge(Element):
	__slots__ = Element._gv_base + ('node_from', 'node_to', 'op')

	def __new__(cls, src, dst, op=None, **props):
		edges = Node.product(src, dst, graph=props.pop('graph', None))
		# print(props, edges)
		# exit()
		if len(edges) == 1:
			src, dst = edges[0]
			self = super(Edge, cls).__new__(cls, src, dst, **props)
			if isinstance(src, types.StringTypes) or isinstance(dst, types.StringTypes)\
				or 'graph' in props: raise TypeError(repr([src, dst, op, props]))
			style = props.get('gvstyle', list())
			if isinstance(style, types.StringTypes): style = [style]
			style.insert(0, 'edge')
			props['gvstyle'] = style
			self._kwz_init(graph=src.graph, **props)
			self.op = '->' if self.graph.directed else '--'
			if src.graph is not dst.graph or src.locked or dst.locked:
				raise TypeError(repr([src, dst, op, props]))
			if op is not None and op != self.op: raise TypeError
			self.node_from, self.node_to = src, dst
			return self
		else: list(it.starmap(ft.partial(cls, **props), edges))

	@classmethod
	def batch(cls, *edgespecs, **props):
		return list(it.starmap(ft.partial(cls, **props), edgespecs))



class Graph(object):

	def __init__( self, directed=True, strict=True,
			flat=False, subgroup_nodes=False, styles=dict(), **props ):
		# TODO: flat_prefix option, flat=int to specify level after which it's flat
		self.elements, self.properties, self.styles = defaultdict(set), props, styles
		self.directed, self.strict, self.flat = directed, strict, flat
		self.subgroup_nodes = subgroup_nodes

	@property
	def type(self):
		return '{0}{1}'.format( 'strict ' if self.strict else '',
			'digraph' if self.directed else 'graph' )


	def add_node(self, *labels, **props):
		if len(labels) < 2:
			if labels: props['label'] = labels[0]
			return Node(graph=self, **props)
		else:
			nodes = list()
			for label in labels:
				props['label'] = label
				nodes.append(Node(graph=self, **props))
			return nodes

	def get_nodes_by_label(self, label):
		return filter(lambda el: 'label' in el and el.label == label, self.elements[Node])


	def add_edge(self, *nodes, **props): return Edge(*nodes, **props)

	def add_style(self, name, **props):
		self.styles[name] = props
		return props


	def _format_val(self, val):
		if isinstance(val, Node): val = unicode(val)
		if isinstance(val, types.StringTypes):
			return val if val[0] == '<' else '"{0}"'.format(unicode(val).replace('"', r'\"'))
		elif isinstance(val, bool): return unicode(val).lower()
		elif val is None: raise ValueError
		else: return unicode(val)

	def _tree_abstract(self, nodes=None):
		'(header, (props, [(header, (props, [...])), (header, props), ...]))'
		if not nodes: # root
			nodes = self._tree_abstract(it.ifilterfalse(
				op.attrgetter('parent'), self.elements[Node] ))
			edges = list(( '{0.node_from}{0.op}{0.node_to}'\
					.format(edge), edge.properties ) for edge in self.elements[Edge]
				if edge.node_from in self.elements[Node] and edge.node_to in self.elements[Node] )
			return '{0} "{1}"'.format(
					self.type, self.properties.get('name', 'root') ),\
				(self.properties, nodes + edges)
		else:
			return list(( ( 'subgraph {0}'.format(node) if not self.flat else '',
						(node.properties, self._tree_abstract(node.children)) )
					if node.children else (node, node.properties) )
				for node in sorted( nodes,
					key=lambda node: len(node.children), reverse=True ))

	def _format_tree(self, write, node=None, level=0, indent='  ', append=''):
		header, content = node
		if isinstance(content, tuple):
			props, nodes = content
			if header:
				write('{0}{1} {{'.format(indent*level, header))
				for k,v in props.iteritems():
					write('\n{0}{1}={2};'.format(
						indent*(level+1), k, self._format_val(v) ))
			for node in nodes:
				write('\n')
				self._format_tree(write, node, level+1, indent)
			if header:
				if append: write(append)
				write(' }')
		else:
			content = '' if not content else\
				' [{0}]'.format(','.join('{0}={1}'.format( k,
					self._format_val(v) ) for k,v in content.iteritems()))
			write('{0}{1}{2};'.format(indent*level, header, content))


	def dot(self, write, append='', encode=default_enc):
		if isinstance(write, file): write = write.write
		if encode: write = lambda data,write=write: write(data.encode(encode))
		if self.subgroup_nodes: # add "group hierarchy nodes" and their links
			def recurse(node):
				gnode = self.add_node(node['label'], **node.properties)
				for node in node.children:
					if not node.children: gnode.edge_to(node, gvstyle='cluster')
					else: gnode.edge_to(recurse(node), gvstyle='cluster')
				return gnode
			for node in filter(lambda node:\
				not node.parent, self.elements[Node]): recurse(node)
		self._format_tree(write, self._tree_abstract(), append=append)



if __name__ == '__main__':
	import sys

	graph = Graph(compound=True, label='Sample graph')

	graph.add_style('ssh', color='darkgreen')
	graph.add_style('hack', color='red', arrowhead='halfopen')
	graph.add_style('fail', color='olive', arrowhead='tee')

	group1 = graph.add_node('Home')
	bob = group1.add_node('Bob')
	alice = group1.add_node('Alice')
	alice.update(color='green', shape='octagon')

	group2 = graph.add_node('Corporate')
	carol = group2.add_node('Carol')
	eve = group2.add_node('Eve')
	isaac = group2.add_node('Isaac')

	tp = graph.add_node('Third party')

	bob.edge_to(alice, eve, carol, style='ssh')
	isaac.edge_to(alice, eve)
	eve.edge_to(bob)
	eve.edge_to(carol, style='ssh')
	tp.edge_to(alice, carol, style='hack')
	tp.edge_to(eve, lhead=group2, style='fail')

	graph.dot(sys.stdout)
