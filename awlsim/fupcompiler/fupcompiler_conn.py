# -*- coding: utf-8 -*-
#
# AWL simulator - FUP compiler - Connection
#
# Copyright 2016-2017 Michael Buesch <m@bues.ch>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

from __future__ import division, absolute_import, print_function, unicode_literals
from awlsim.common.compat import *

from awlsim.common.xmlfactory import *

from awlsim.core.instructions.all_insns import * #+cimport

from awlsim.fupcompiler.fupcompiler_base import *


class FupCompiler_ConnFactory(XmlFactory):
	def parser_open(self, tag=None):
		self.inConn = False
		XmlFactory.parser_open(self, tag)

	def parser_beginTag(self, tag):
		if not self.inConn:
			if tag.name == "connection":
				self.inConn = True
				pos = tag.getAttrInt("pos")
				dirIn = tag.getAttrInt("dir_in")
				dirOut = tag.getAttrInt("dir_out")
				wireId = tag.getAttrInt("wire")
				text = tag.getAttr("text", "")
				conn = FupCompiler_Conn(self.elem,
					pos, dirIn, dirOut, wireId, text)
				if not self.elem.addConn(conn):
					raise self.Error("Invalid connection")
				return
		XmlFactory.parser_beginTag(self, tag)

	def parser_endTag(self, tag):
		if self.inConn:
			if tag.name == "connection":
				self.inConn = False
				return
		else:
			if tag.name == "connections":
				self.parser_finish()
				return
		XmlFactory.parser_endTag(self, tag)

class FupCompiler_Conn(FupCompiler_BaseObj):
	factory = FupCompiler_ConnFactory

	# Connection types
	EnumGen.start
	TYPE_UNKNOWN	= EnumGen.item
	TYPE_VKE	= EnumGen.item # Bit operation
	TYPE_ACCU	= EnumGen.item # Byte/word/dword operation
	EnumGen.end

	# The target instruction to be used for TYPE_VKE/TYPE_ACCU compilation
	EnumGen.start
	TARGET_VKE_U	= EnumGen.item
	TARGET_VKE_O	= EnumGen.item
	TARGET_VKE_X	= EnumGen.item
	TARGET_ACCU1	= EnumGen.item
	EnumGen.end

	target2LoadInsnClass = {
		TARGET_VKE_U	: AwlInsn_U,
		TARGET_VKE_O	: AwlInsn_O,
		TARGET_VKE_X	: AwlInsn_X,
		TARGET_ACCU1	: AwlInsn_L,
	}
	loadInsnClass2Target = pivotDict(target2LoadInsnClass)

	target2StoreInsnClass = {
		TARGET_VKE_U	: AwlInsn_ASSIGN,
		TARGET_VKE_O	: AwlInsn_ASSIGN,
		TARGET_VKE_X	: AwlInsn_ASSIGN,
		TARGET_ACCU1	: AwlInsn_T,
	}

	# Wire-ID used for unconnected connections
	WIREID_NONE	= -1

	__slots__ = (
		"elem",
		"pos",
		"dirIn",
		"dirOut",
		"wireId",
		"text",
		"virtual",
		"wire",
	)

	@classmethod
	def targetIsVKE(cls, target):
		"""Returns True, if a target ID is a VKE target.
		"""
		return target in {cls.TARGET_VKE_U,
				  cls.TARGET_VKE_O,
				  cls.TARGET_VKE_X}

	@classmethod
	def targetToInsnClass(cls, target, toLoad=True):
		"""Convert a target ID to its corresponding instruction class.
		If 'toLoad' is True, the load instruction is returned.
		If 'toLoad' is False, the store instruction is returned.
		"""
		if toLoad:
			return cls.target2LoadInsnClass[target]
		return cls.target2StoreInsnClass[target]

	def __init__(self, elem, pos, dirIn, dirOut, wireId, text, virtual=False):
		FupCompiler_BaseObj.__init__(self)
		self.elem = elem		# FupCompiler_Elem
		self.pos = pos			# Position index
		self.dirIn = bool(dirIn)	# Input
		self.dirOut = bool(dirOut)	# Output
		self.wireId = wireId		# Wire ID number
		self.text = text or ""		# Connection text (optional)
		self.virtual = virtual		# True, if this is a virtual connection

		self.wire = None

	@property
	def compiler(self):
		if self.elem:
			return self.elem.compiler
		return None

	def hasText(self, text):
		"""Returns True, if the connection text matches.
		This does a case insensitive compare.
		"""
		return strEqual(self.text, text, caseSensitive=False)

	@property
	def isOptional(self):
		"""Returns True, if this connection is optional.
		An optional connection does not have to be connected.
		"""
		return self.elem.connIsOptional(self)

	@property
	def connType(self):
		"""Get the connection type.
		This returns whether this connection is VKE based (TYPE_VKE)
		or accu based (TYPE_ACCU).
		If the type is unknown TYPE_UNKNOWN is returned.
		"""
		return self.elem.getConnType(self)

	@property
	def isConnected(self):
		"""Returns True, if this connection is connected to a wire.
		"""
		return self.wire is not None

	def getConnectedConns(self, getOutputs=False, getInputs=False):
		"""Get all other connections that are connected
		via self.wire to this connection.
		This excludes self.
		If 'getOutputs' is True, connections with dirOut=True are returned.
		If 'getInputs' is True, connections with dirIn=True are returned.
		"""
		if self.wire:
			for conn in self.wire.connections:
				if conn is not self and\
				   ((conn.dirOut and getOutputs) or\
				    (conn.dirIn and getInputs)):
					yield conn

	def getConnectedConn(self, getOutput=False, getInput=False):
		"""Get the single connection that is connected to this connection.
		If 'getOutput' is True, elements connected to the wire via OUT
		connection are returned.
		If 'getInput' is True, elements connected to the wire via OUT
		connection are returned.
		If neither 'getOutput' nor 'getInput' is True, None is returned.
		If there is no matching element or more that one matching
		element, an exception is raised.
		"""
		if not getOutput and not getInput:
			return None
		dirText = "%s%s%s" % (
			"IN" if getInput else "",
			"/" if getInput and getOutput else "",
			"OUT" if getOutput else "")
		selfText = (" \"%s\"" % self.text) if self.text else ""
		connections = list(self.getConnectedConns(getOutputs=getOutput,
							  getInputs=getInput))
		if len(connections) > 0:
			if len(connections) > 1:
				raise AwlSimError("The connection%s of element '%s' does "
					"only support a single %s-wire, "
					"but has %d %s-connections." % (
					selfText,
					str(self.elem),
					dirText,
					len(connections),
					dirText))
			return connections[0]
		raise AwlSimError("The connection%s of element '%s' does "
			"does not have a valid %s-connected element." % (
			selfText,
			str(self.elem),
			dirText))

	def getConnectedElems(self, viaOut=False, viaIn=False):
		"""Get all elements that are connected to this connection.
		If 'viaOut' is True, elements connected to the wire via OUT
		connection are returned.
		If 'viaIn' is True, elements connected to the wire via OUT
		connection are returned.
		If neither 'viaOut' nor 'viaIn' is True, no element is returned.
		The element that belongs to 'self' is not returned.
		"""
		for conn in self.getConnectedConns(getOutputs=viaOut, getInputs=viaIn):
			yield conn.elem

	def getConnectedElem(self, viaOut=False, viaIn=False):
		"""Get the single element that is connected to this connection.
		If 'viaOut' is True, elements connected to the wire via OUT
		connection are returned.
		If 'viaIn' is True, elements connected to the wire via OUT
		connection are returned.
		If neither 'viaOut' nor 'viaIn' is True, None is returned.
		If there is no matching element or more that one matching
		element, an exception is raised.
		"""
		conn = self.getConnectedConn(getOutput=viaOut, getInput=viaIn)
		if not conn:
			return None
		return conn.elem

	def connectTo(self, otherConn):
		if self.isConnected:
			raise AwlSimError("Connection %s is already connected" % (
				str(self)))
		if otherConn.isConnected:
			wire = otherConn.wire
		else:
			wire = self.elem.grid.newWire(virtual=True)
			wire.addConn(otherConn)
		wire.addConn(self)

	def compileConn(self, target=None, targetInsnClass=None):
		"""Compile the element that owns this connection.
		A compile target has to be specified. That is either a VKE
		instruction target, or an ACCU1 load target.
		target: one of TARGET_xxx,
		targetInsnClass: An AwlInsn_xxx class.
		Either target or targetInsnClass must be specified, but not both.
		"""
		assert(self.elem)
		assert(bool(target) ^ bool(targetInsnClass))
		if targetInsnClass:
			target = self.loadInsnClass2Target[targetInsnClass]
		return self.elem.compileConn(self, target)

	def __repr__(self):
		return "FupCompiler_Conn(elem, pos=%d, dirIn=%s, dirOut=%s, "\
					"wireId=%d, text=\"%s\", virtual=%s)" % (
			self.pos, self.dirIn, self.dirOut, self.wireId,
			self.text, self.virtual)

	def __str__(self):
		fields = []
		if self.text:
			fields.append('"%s"' % self.text)
		else:
			fields.append("pos=%s" % self.pos)
		if self.elem:
			fields.append(str(self.elem))
		if self.virtual:
			fields.append("VIRTUAL")
		return "CONNECTION(%s)" % (", ".join(fields))
