#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Takes a base url from cli, walks all links under the same tree recursively, returns list of successfully fetched urls"""
from __future__ import with_statement
from __future__ import print_function
import urllib2
import yaml

