#! /usr/bin/python
# -*- coding: utf-8 -*-
#
#	Author: Mario Kicherer (http://empanyc.net)
#	License: GPL v2 (http://www.gnu.org/licenses/gpl-2.0.txt)
#
# Opens a tcp port and prints incoming information into a specific channel
#
# Config example:
#	plugins.irccat.config.distribution=*:-#myhadibot
#	plugins.irccat.config.password=mypassword
#	plugins.irccat.config.port=1685
#	plugins.irccat.config.keyfile=mykey.key
#	plugins.irccat.config.certfile=mycert.crt


import irclib
import re
import threading,thread
import os,time
from socket import * 
from hadibot import register_command,register_callback,is_cmd_allowed,output,register_plugin,reload_plugins,verbose_lvl,reregister_config;

config = {};
lconfig = {};
bot = None;
sl = None;

BUFSIZ = 1024

def int2bin(i, pad=8):
	return "".join( [str((i >> a) & 1) for a in range(pad-1,-1,-1)] )

def prefix2int(size, prefix):
	r=0;
	for i in range(size-prefix,size):
		r=r+2**i
	return r;

def expand(liste):
	for i in range(0,8):
		if liste[i] == "":
			liste[i] = "0";
			for x in range(0,8-len(liste)):
				liste.insert(i, "0");
	for i in range(0,8):
		if len(liste[i]) < 4:
			liste[i] = "%04X" % int(liste[i],16);
	newliste = [];
	for i in range(0,8):
		newliste.append(liste[i][0:2]);
		newliste.append(liste[i][2:4]);
	return newliste;

def ip_in_subnet(ip, subnet):
	if len(subnet.split("/")) > 1:
		netaddr=subnet.split("/")[0];
		prefix=int(subnet.split("/")[1]);
	else:
		netaddr=subnet;
		prefix=-1;
	
	if ip.find(":") > -1 and ip.find(".") > -1:
		ip = ip.split(":")[3];
	
	if ip.find(":") > -1:
		lip=ip.split(":");
		lnet=netaddr.split(":");
		nbytes = 16;
		base=16;
		if prefix == -1:
			prefix=128;
		lip=expand(lip);
		lnet=expand(lnet);
		
	if ip.find(".") > -1:
		lip=ip.split(".");
		lnet=netaddr.split(".");
		nbytes = 4;
		base=10;
		if prefix == -1:
			prefix=32;
	
	iip=0;
	inet=0;
	for i in range(0,nbytes):
		iip=iip+int(lip[3-i],base)*2**(i*8)
		inet=inet+int(lnet[3-i],base)*2**(i*8)
	
	return iip&prefix2int(32,prefix) == inet;



def process_msg(msg):
	res = re.match(r"([\w\-\_]+):(.*)", msg);
	if not res:
		output("info", "malformed msg: %s" % (msg));
		return

	typ = res.group(1);
	pay = res.group(2);
	
	out = "%s:%s" % (typ,pay);
	
	items = lconfig["distribution"].split(" ");
	for item in items:
		res = re.match(r"(\*|(?:,*\w+)+):((,*(?:[-#!]{1,2}\w+))*|\*)", item);
		if res:
			categories = res.group(1).split(",");
			channels = res.group(2).split(",");
			
			if (typ in categories) or (categories[0]=="*"):
				if channels[0] == "*":
					dest_channels = bot.channels.values();
				else:
					dest_channels = channels;
				for chan in dest_channels:
					#print chan
					if chan[0] == "-":
						bot.connection.privmsg(chan[1:], pay);
					else:
						bot.connection.privmsg(chan, out);
				break;

def process_head(parent, msg):
	res = re.match(r"(\w+):(.*)", msg);
	if res:
		key = res.group(1).strip();
		value = res.group(2).strip();
		
		if (key == "password") and value == lconfig["password"]:
			parent.allowed = True;
		else:
			output("info", "wrong password");

class ClientLoop ( threading.Thread ):
	rawsocket = None;
	socket6 = None;
	parent = None;
	running = False;
	allowed = False;
	stop = False;
	
	def __init__ (self, parent, rawsocket, socket):
		threading.Thread.__init__(self)
		self.socket6 = socket;
		self.rawsocket = rawsocket;
		self.parent = parent;
		
	
	def run ( self ):
		head = True;
		self.running = True;
		self.stop = False;
		
		while not self.stop:
			try:
				rdata = self.socket6.recv(BUFSIZ)
			except:
				break;
			if not rdata: break
			
			for data in rdata.split("\n"):
				if data.strip() == "":
					head=False;
					continue;
				if data.strip() == "exit":
					self.stop = True;
					break;
				if head:
					process_head(self,data);
				else:
					if "password" in lconfig and not self.allowed:
						self.socket6.send("401 Unauthorized\n");
						self.stop = True;
						break;
					process_msg(data);
			
		self.shutdown();
	
	def shutdown(self):
		if not self.running:
			return;
		self.stop = True;
		self.running = False;
		output("debug", "irccat: connection from %s closed." % str(self.rawsocket.getpeername()));
		
		self.socket6.shutdown(SHUT_RDWR);
		self.socket6.close();
		if (self.socket6 != self.rawsocket):
			self.rawsocket.shutdown(SHUT_RDWR);
			self.rawsocket.close();
		del self.socket6;
		del self.rawsocket;
		self.parent.clients.remove(self);

#
class ServerLoop ( threading.Thread ):
	socket = None;
	clients = [];
	stop = False;
	socket_up = False;
	
	def __init__ (self):
		threading.Thread.__init__(self)
		
	
	def run ( self ):
		ssl_available = False
		self.stop = False;
		self.socket_up = False;
		
		while not self.stop:
			while not self.stop and not self.socket_up:
				try:
					if has_ipv6:
						self.socket=socket(AF_INET6,SOCK_STREAM)
					else:
						self.socket=socket(AF_INET,SOCK_STREAM)
					self.socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
					self.socket.bind(("",int(lconfig["port"])))
					self.socket.listen(3);
					self.socket_up = True;
				except error, st:
					output("error", "ERROR ServerSocketInitialization %s %s" % (error, st))
					self.socket_up = False;
					for i in range(5):
						if self.stop:
							break;
						time.sleep(1);
			
			if (not self.stop) and (lconfig["certfile"] != "") and (lconfig["keyfile"] != ""):
				try:
					import ssl
					ssl_available = True;
				except:
					output("info", "SSL module not available. Continue unencrypted...");
					ssl_available = False;
			
			while not self.stop:
				try:
					clientsock, addr = self.socket.accept()
				except error, st:
					if not self.stop:
						output("error", "ERROR Serverloop %s %s" % (error, st))
					break
				
				found = False;
				if lconfig["ips_allowed"].strip() == "*":
					found = True;
				else:
					for subnet in lconfig["ips_allowed"].split():
						if ip_in_subnet(addr[0], subnet):
							found=True;
							break;
				
				if not found:
					output("info", "irccat: incoming connection from: %s - denied" % str(addr));
					clientsock.close();
					continue;
				
				output("debug", "irccat: incoming connection from: %s" % str(addr));
				
				if ssl_available:
					try:
						secsock = ssl.wrap_socket(clientsock,
							server_side=True,
							certfile=lconfig["certfile"],
							keyfile=lconfig["keyfile"],
							ssl_version=ssl.PROTOCOL_TLSv1)
					except error, st:
						output("error", "ERROR %s %s" % (error, st))
						clientsock.shutdown(SHUT_RDWR);
						clientsock.close()
						continue;
				
					cl = ClientLoop(self,clientsock,secsock);
				else:
					cl = ClientLoop(self,clientsock,clientsock);
				self.clients.append(cl);
				cl.start();
		self.shutdown();
	
	def shutdown(self):
		self.stop = True;
		for client in self.clients:
			client.shutdown();
		if self.socket and self.socket_up:
			try:
				self.socket.shutdown(SHUT_RDWR);
			except:
				pass
			self.socket.close();
			self.socket_up = False;

def init(plugin,root_config):
	global config;
	global lconfig;
	global bot;
	global sl;
	
	reregister_config(root_config);
	config = root_config;
	bot = config["main"]["bot_handle"];
	
	lconfig = register_plugin(plugin, config, "irccat", "IRCCat", "0.1");

	if not "port" in lconfig:
		lconfig["port"] = "1685"
	if not "distribution" in lconfig:
		lconfig["distribution"] = "*:*"
	if not "ips_allowed" in lconfig:
		lconfig["ips_allowed"] = "*"
	if not "keyfile" in lconfig:
		lconfig["keyfile"] = ""
	if not "certfile" in lconfig:
		lconfig["certfile"] = ""

	sl = ServerLoop();
	sl.start()

def shutdown():
	global sl;
	sl.shutdown();







 
