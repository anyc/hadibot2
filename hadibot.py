#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
#	Author: Mario Kicherer (2009,2010) http://empanyc.net
#	License: GPL v2 (http://www.gnu.org/licenses/gpl-2.0.txt)
#
#	Requires http://python-irclib.sourceforge.net
#

import irclib
import sys
import socket
import os
import getopt
import re, threading,datetime,signal

from time import time,sleep
from ircbot import SingleServerIRCBot
from irclib import nm_to_n, nm_to_h, irc_lower, ip_numstr_to_quad, ip_quad_to_numstr

config={};
threads=[];

verbose_lvl = {"error":0, "info":3, "debug":6, "all":10}

def default_config(config):
	config["main"] = {
			"configfiles": ["hadibot.conf", "~/hadibot.conf", "/etc/hadibot.conf"],
			"plugin_path":"plugins/",
			"servers":"",
			"nickname":"HaDiBot2",
			"channels":"",
			"plugins_include":"",
			"plugins_exclude":"",
			"command_timeout":"120",
			"public_prefix":"!",
			"bot_handle":None,
			"ignore_unknown_cmds":0,
			}
	config["commands"] = {}
	config["plugins"] = {}
	config["users"] = {}
	config["reg_users"] = {}
	config["callbacks"] = {}
	

class Respond():
	def __init__(self):
		return
	
	def respond(text):
		return

# PrivMsgRespond - stores caller and discards a message after a timeout
class PrivMsgRespond(Respond):
	def __init__(self, c, target):
		Respond.__init__(self);
		self.c = c;
		self.target = target;
		self.start = time();
	
	def respond(self,text):
		if text == None:
			return
		if text.strip() == "":
			return
		
		if (self.start+float(config["main"]["command_timeout"])) > time():
			for line in text.split("\n"):
				self.c.privmsg(self.target, line);
		else:
			output("info", "Timeout for response to \"%s\": %s" %(self.target, text));

# execute a command in a separate thread
class runCommand ( threading.Thread ):
	def __init__ (self, bot, e, resp, cmd):
		threading.Thread.__init__(self)
		self.cmd = cmd;
		self.bot = bot;
		self.e = e;
		self.resp = resp;
		threads.append(self);
	
	def run ( self ):
		self.result = self.bot.do_command(self.e, self.cmd);
		self.resp.respond(self.result);
		threads.remove(self);


# the main class
class HaDiBot(SingleServerIRCBot):
	run = False;
	
	def __init__(self):
		SingleServerIRCBot.__init__(self, self.get_serverlist(config["main"]["servers"]), config["main"]["nickname"], config["main"]["nickname"])
		self.run = True;
	
	# parse server list
	def get_serverlist(self, servers):
		lst = [];
		srvs = servers.split(" ");
		for srv in srvs:
			if len(srv.split(":")) > 1:
				tpl = (srv.split(":")[0], int(srv.split(":")[1]));
			else:
				tpl = (srv, 6667);
			lst.append(tpl);
		
		return lst
	
	# main loop
	def start(self):
		self._connect()
		while self.run:
			self.ircobj.process_once(0.2)
	
	# shutdown bot
	def shutdown(self):
		if (bot.run):
			bot.run = False;
			bot.connection.disconnect("Bye, cruel world!");
	
	#####################
	# callback handlers
	
	def on_all_raw_messages(self, c, e):
		# print all raw messages in debug mode except text messages
		for line in e.arguments():
			if (len(line.split(" ")) >= 2) and (not (line.split(" ")[1] == "PRIVMSG")):
				output("debug", "RAW: %s" % (line));
			else:
				output("all", "RAW: %s" % (line));
		
		if "raw" in config["callbacks"]:
			for cb in config["callbacks"]["raw"].values():
				cb["fct"](self, e);
	
	def on_join(self,c,e):
		if "join" in config["callbacks"]:
			for cb in config["callbacks"]["join"].values():
				cb["fct"](self, e);
	
	def on_part(self,c,e):
		if "part" in config["callbacks"]:
			for cb in config["callbacks"]["part"].values():
				cb["fct"](self, e);
	
	def on_quit(self,c,e):
		if "quit" in config["callbacks"]:
			for cb in config["callbacks"]["quit"].values():
				cb["fct"](self, e);
				
	def on_nick(self,c,e):
		if "nick" in config["callbacks"]:
			for cb in config["callbacks"]["nick"].values():
				cb["fct"](self, e);
	
	def on_nicknameinuse(self, c, e):
		c.nick(c.get_nickname() + "_")
	
	def on_welcome(self, c, e):
		if "welcome" in config["callbacks"]:
			for cb in config["callbacks"]["welcome"].values():
				cb["fct"](self, e);
		self.join_channels(c,e);
		return;
	
	def on_privmsg(self, c, e):
		resp = PrivMsgRespond(c, nm_to_n(e.source()));
		self.process_td(e, resp,  e.arguments()[0]);
		""" result = self.do_command(e, e.arguments()[0]);
		if result:
			result = result.split("\n");
			for r in result:
				#c.privmsg(e.source().split("!")[0],r);
				c.privmsg(nm_to_n(e.source()),r);
		"""
	
	def on_pubmsg(self, c, e):
		a = e.arguments()[0].split(":", 1)
		if len(a) > 1 and irc_lower(a[0]) == irc_lower(self.connection.get_nickname()):
			# been called directly "HaDibot2:"
			cmd = a[1].strip();
		else:
			cmd = e.arguments()[0];
			if (cmd[:len(config["main"]["public_prefix"])] != config["main"]["public_prefix"]) or (config["main"]["public_prefix"] == ""):
				# nothing to do
				return
			else:
				cmd = cmd[len(config["main"]["public_prefix"]):];
		
		resp = PrivMsgRespond(c, e.target());
		self.process_td(e, resp,  cmd);
		"""
		result = self.do_command(e, cmd);
		if result:
			result = result.split("\n");
			for r in result:
				c.privmsg(e.target(), r);
		"""

	#def on_dccmsg(self, c, e):
		#c.privmsg("You said: " + e.arguments()[0])

	#def on_dccchat(self, c, e):
		#if len(e.arguments()) != 2:
			#return
		#args = e.arguments()[1].split()
		#if len(args) == 4:
			#try:
				#address = ip_numstr_to_quad(args[2])
				#port = int(args[3])
			#except ValueError:
				#return
			#self.dcc_connect(address, port)
	
	# joins all required channels
	def join_channels(self, c, e):
		channels = [];
		channels.extend(config["main"]["channels"].split(" "));
		
		# collect channels required by plugins
		if "channels" in config["callbacks"]:
			for cb in config["callbacks"]["channels"].values():
				channels.extend(cb["fct"](self, e));
		
		chanh = {}
		for chan in channels:
			schan = chan.split(":");
			channel = schan[0];
			if len(schan) > 1:
				key = schan[1];
			else:
				key = ""
			
			# ignore duplicate entries
			if channel in chanh:
				continue;
			
			chanh[channel] = True;
			
			output("info", "Joining %s (K: %s)..." % (channel, key));
			c.join(channel, key);

	# spawns new thread for a command
	def process_td(self, e, resp, command):
		nt = runCommand(self, e, resp, command);
		nt.start()
		
	
	# find handler for specific command and pass arguments
	def do_command(self, e, cmd):
		nick = nm_to_n(e.source())
		c = self.connection
		found = 0;
		for comk in config["commands"].keys():
			res = re.match(comk, cmd);
			if res:
				found = 1;
				if is_cmd_allowed(config, self, e, cmd):
					output("debug", "CMD: \"%s\" from %s" % (cmd, e.source()));
					return config["commands"][comk]["pointer"](self, e, cmd);
				else:
					output("info", "CMD: \"%s\" from %s FORBIDDEN" % (cmd, e.source()));
		
		if (not found) and (not config["main"]["ignore_unknown_cmds"]):
			output("debug", "CMD: \"%s\" from %s not found." % (cmd, e.source()));
			return "Command not found."


# checks if command is executable by the calling user
def is_cmd_allowed(config, bot, e, cmd):
	ncmd = cmd.split(" ")[0];
	for recmd in config["commands"]:
		res = re.match(recmd, ncmd);
		if res:
			#if ("min_level" in config["commands"][recmd]) and ("auth" in config["callbacks"]):
			if ("auth" in config["callbacks"]):
				for cb in config["callbacks"]["auth"].values():
					if cb["fct"](config, bot, e, recmd, cmd):
						return 1;
	return 0;



# handle output -> printf/log file
def output(typ, message):
	global config;
	
	m = "[%s] %s %s" %(typ, datetime.datetime.now().strftime("|%Y-%m-%d|%H:%M:%S|"), message);

	if "main" in config and "verbosity" in config["main"]:
		out_lvl = config["main"]["verbosity"];
	else:
		out_lvl = "error";
	
	if "main" in config and "log_verbosity" in config["main"]:
		log_lvl = config["main"]["log_verbosity"];
	else:
		log_lvl = out_lvl;
	
	# write to stdout/stderr
	if verbose_lvl[typ] <= verbose_lvl[out_lvl]:
		if typ == "error":
			sys.stderr.write("%s\n" % m);
		else:
			sys.stdout.write("%s\n" % m);
	
	# write to log file
	if verbose_lvl[typ] <= verbose_lvl[log_lvl]:
		logfile = "";
		if (("main" in config) and ("log_file" in config["main"]) and (config["main"]["log_file"].strip() != "")):
			logfile = config["main"]["log_file"];
		if (logfile.strip() != ""):
			f = open(logfile, 'a')
			f.write("%s\n" % (m))
			f.close();

# load config file
def load_config(config, configfiles, filter=[]):
	for configfile in configfiles:
		if os.path.exists(configfile):
			output("info", "Loading config file %s." % configfile);
			f = open(configfile)
			lines = f.readlines();
			for line in lines:
				res = re.match(r"\s*([\w\.]+)\s*=\s*(.*)\s*", line);
				if res:
					key = res.group(1);
					value = res.group(2);

					found = (len(filter) == 0);
					for fi in filter:
						res2 = re.match(fi, key);
						if res2:
							found = 1;
							break;
					
					if not found: 
						continue;

					#value = res.group(2).replace("%h", host);
					key = key.split(".");
					k = -1;
					itr = config;
					for k in range(0,len(key)-1):
						if not key[k] in itr:
							itr[key[k]] = {};
						itr = itr[key[k]];
					itr[key[k+1]] = value;
			f.close();
		else:
			output("error", "Configfile %s does not exist." % configfile);

# load plugins
def load_plugins(config, path):
	global bot;
	if not path in sys.path:
		sys.path.insert(0,path)
	for filename in os.listdir(path):
		if (filename.split(".")[1] == "py"):
			pluginname = filename.split(".")[0];
			if (pluginname in config["main"]["plugins_include"].split(",")) or ((config["main"]["plugins_include"] == "*") and (not pluginname in config["main"]["plugins_exclude"].split(","))):
				output("info", "Load plugin \"%s\"" % (pluginname));
				plugin = __import__(pluginname, globals(), locals(), [''])
				plugin.init(plugin,config);

# shutdown plugins
def shutdown_plugins(config):
	for plugin in config["plugins"].values():
		if "handle" in plugin:
			if "shutdown" in dir(plugin["handle"]):
				plugin["handle"].shutdown();

# reload plugins
def reload_plugins(config, path, re_config=0):
	plugins = []
	
	# save plugin handles for reload
	for plugin in config["plugins"].values():
		if "handle" in plugin:
			plugins.append(plugin["handle"]);
	
	#plugins.clear();
	#config["commands"].clear();
	#config["plugins"].clear();
	shutdown_plugins(config)
	if re_config:
		config["plugins"].clear();
		load_config(config, config["main"]["configfiles"], ["^plugins\..*"]);
	
#	for mod in sys.modules.keys():
#		if mod != "__main__":
#			print sys.modules[mod]
#			if sys.modules[mod] != None:
	
	for pl in plugins:
		reload(pl)
	#plugins.clear();
	load_plugins(config, path);

# register commands for plugins
def register_command(config,plugin, id, fct, desc=""):
	config["commands"][id] = {};
	config["commands"][id]["pointer"] = fct;
	config["commands"][id]["plugin"] = plugin;
	config["commands"][id]["desc"] = desc;

# register callback procedures
def register_callback(config,plugin, typ, ident, fct):
	if not typ in config["callbacks"]:
		config["callbacks"][typ] = {};
	if not ident in config["callbacks"][typ]:
		config["callbacks"][typ][ident] = {};
	config["callbacks"][typ][ident]["fct"] = fct;
	config["callbacks"][typ][ident]["plugin"] = plugin;

# register plugins
def register_plugin(plugin, config, name, info, version):
	if not name in config["plugins"]:
		config["plugins"][name] = {};
	config["plugins"][name]["handle"] = plugin;
	config["plugins"][name]["info"] = info;
	config["plugins"][name]["version"] = version;
	if not "config" in config["plugins"][name]:
		config["plugins"][name]["config"] = {};
	return config["plugins"][name]["config"];
	

def reregister_config(global_config):
	global config;
	config = global_config;

# signal handler
def handler(signum, frame):
	output("info", "received SIGINT");
	shutdown(config["main"]["bot_handle"]);

# shutdown procedure
def shutdown(bot):
	bot.run = False;
	sleep(1);
	shutdown_plugins(config)
	bot.shutdown();
	output("info", "Shutdown.");
	sys.exit(0);

def usage():
	print "Arguments: "
	print "\t-h|--help"
	print "\t-n|--nickname"
	print "\t-s|--servers"
	print "\t-c|--channels"
	print "\t-d|--daemon"
	print "\t-i|--interactive"

def main():
	global bot;
	global config;
	global configfile;

	interactive = False;
	daemonize = False;

	#home = os.path.expanduser("~");
	#configfile = home+"/.hadibot";
	
	signal.signal(signal.SIGINT, handler)
	
	
	default_config(config);
	load_config(config, config["main"]["configfiles"]);
	
	try:
		opts, args = getopt.getopt(sys.argv[1:], "dhn:c:s:i", ["daemon", "help", "nickname=", "channels=", "servers=","interactive"])
	except getopt.GetoptError:          
		usage()                         
		sys.exit(2)
	
	for opt, arg in opts:
		if opt in ("-h", "--help"):
			usage()
			sys.exit()
		elif opt in ("-n", "--nickname"):
			config["main"]["nickname"] = arg;
		elif opt in ("-c", "--channels"):
			config["main"]["channels"] = arg;
		elif opt in ("-s", "--servers"):
			config["main"]["servers"] = arg;
		elif opt in ("-i", "--interactive"):
			interactive = True;
		elif opt in ("-d", "--daemon"):
			daemonize = True;
	
	message = "".join(args)
	
	if (daemonize) and (interactive):
		output("error", "-d and -i can't be used together, ignoring -i");
		interactive = False;
	
	if config["main"]["servers"].strip()=="":
		output("error", "no server address");
		sys.exit(0);
	
	if (daemonize):
		# fork and detach from tty
		
		pid = os.fork()
		if (pid != 0):
			 os._exit(0)
		
		os.setsid()
		
		dest = "/dev/null";
		
		sys.stdout.close();
		sys.stdin.close();
		sys.stderr.close();
		
		sys.stdout = open(dest, "w");
		sys.stdin = open(dest, "r");
		sys.stderr = open(dest, "w");

	bot = HaDiBot()
	config["main"]["bot_handle"] = bot;
	
	load_plugins(config, config["main"]["plugin_path"]);
	
	if not interactive:
		bot.start()
	else:
		# start interactive prompt
		
		import readline;
		threading._start_new_thread(bot.start,())
		
		readline.parse_and_bind('tab: complete')
		#readline.parse_and_bind('set editing-mode vi')
		line = "";
		while line != "quit":
			try:
				line = raw_input('%s: ' % (config["main"]["nickname"]))
			except KeyboardInterrupt:
				line = "exit";
			if (line == 'exit') or (not bot.run):
				bot.run = False;
				break
			if line.strip() == "":
				continue;
			
			found = 0;
			for comk in config["commands"].keys():
				res = re.match(comk, line);
				if res:
					found = 1;
					print config["commands"][comk]["pointer"](bot, irclib.Event("console", "console", "console"), line);
			if not found:
				print "Command not found."
	
	shutdown(bot);
	

if __name__ == "__main__":
	main()
