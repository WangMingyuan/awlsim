# -*- coding: utf-8 -*-
#
# AWL simulator - FUP compiler - Wire
#
# Copyright 2016 Michael Buesch <m@bues.ch>
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

from awlsim.fupcompiler.fupcompiler_base import *


class FupCompiler_WireFactory(XmlFactory):
	def parser_open(self):
		self.inWire = False
		XmlFactory.parser_open(self)

	def parser_beginTag(self, tag):
		if not self.inWire:
			if tag.name == "wire":
				self.inWire = True
				idNum = tag.getAttrInt("id")
				wire = FupCompiler_Wire(self.grid, idNum)
				if not self.grid.addWire(wire):
					raise self.Error("Invalid wire")
				return
		XmlFactory.parser_beginTag(self, tag)

	def parser_endTag(self, tag):
		if self.inWire:
			if tag.name == "wire":
				self.inWire = False
				return
		else:
			if tag.name == "wires":
				self.parser_finish()
				return
		XmlFactory.parser_endTag(self, tag)

class FupCompiler_Wire(FupCompiler_BaseObj):
	factory = FupCompiler_WireFactory

	def __init__(self, grid, idNum):
		FupCompiler_BaseObj.__init__(self)
		self.grid = grid		# FupCompiler_Grid
		self.idNum = idNum		# Wire ID

		self.connections = set()
