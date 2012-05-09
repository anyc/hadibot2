#! /usr/bin/python
# -*- coding: utf-8 -*-
#
#	Author: Mario Kicherer (http://empanyc.net)
#	License: GPL v2 (http://www.gnu.org/licenses/gpl-2.0.txt)
#
# Some common commands and user accounting
#
# Example config:
#
#	plugins.stdplugin.config.reg_users.myuser.passwd=mypasswd
#	plugins.stdplugin.config.reg_users.myuser.level=5


import irclib
import re
from hadibot import register_command,register_callback,is_cmd_allowed,output,register_plugin,reload_plugins,verbose_lvl,load_config;

plugin_name = "stdplugin";
plugin_description = "Common commands and user accounting";
plugin_version = "0.1";

def cmd_disconnect(bot, event, cmd):
	bot.disconnect();
	return "";

def cmd_quit(bot, event, cmd):
	bot.shutdown();
	return "";

def cmd_help(bot, event, cmd):
	global config;

	text = "Available commands:\n";
	for com in sorted(config["commands"].keys()):
		if is_cmd_allowed(config, bot, event, com):
			text = "%s  %s - %s\n" % (text, com, config["commands"][com]["desc"]);
	return text

def cmd_login(bot, event, cmd):
	global lconfig;
	
	res = re.match("\s*login\s*(\w+)\s*(\w+)\s*", cmd);
	if res:
		#print "-%s- -%s-" %(res.group(1), res.group(2));
		user = res.group(1);
		pw = res.group(2);
		
		found = 0;
		for c in bot.channels.values():
			for u in c.users():
				if u == irclib.nm_to_n(event.source()):
					found = 1;
		
		if not found:
			return "You're not in one of my channels. Access denied.";
		
		if (user in lconfig["reg_users"]) and ("passwd" in lconfig["reg_users"][user]) and (lconfig["reg_users"][user]["passwd"] == pw):
			if not event.source() in lconfig["users"]:
				lconfig["users"][event.source()] = {}
			lconfig["users"][event.source()]["username"] = user;
			lconfig["users"][event.source()]["level"] = lconfig["reg_users"][user]["level"];
			
			output("info", "Login: \"%s\" as %s successfull" % (event.source(), user));
			return "Login succesfull.";
		else:
			output("info", "Login: \"%s\" as %s failed" % (event.source(), user));
			return "Login failed.";
	
	return "";

def cmd_join(bot, event, cmd):
	global config;

	res = re.match("join\s*(.+)\s*(.+)\s*", cmd);
	if res:
		bot.connection.join(res.group(1), res.group(2));

	res = re.match("join\s*(.+)\s*", cmd);
	if res:
		bot.connection.join(res.group(1));
	return "";

def cmd_leave(bot, event, cmd):
	global config;

	res = re.match("leave\s*(.+)\s*", cmd);
	if res:
		bot.connection.part(res.group(1));
	return "";

def cmd_quote(bot, event, cmd):
	global config;

	res = re.match("quote\s*(.+)\s*", cmd);
	if res:
		bot.connection.send_raw(res.group(1));
	return "";

def cmd_reload_plugins(bot, event, cmd):
	global config;

	res = re.match("reload_plugins\s*(\w*)", cmd);
	if res:
		if res.group(1) == "config":
			reload_plugins(config, config["main"]["plugin_path"], 1);
			return "Plugins and config reloaded."
		else:
			reload_plugins(config, config["main"]["plugin_path"], 0);
			return "Plugins reloaded."
	return ""


def cmd_reload_config(bot, event, cmd):
	global config;

	res = re.match("reload_config\s*(.*)", cmd);
	if res:
		if res.group(1).strip() != "":
			load_config(config, config["main"]["configfiles"], res.group(1).split(" "));
		else:
			load_config(config, config["main"]["configfiles"]);
		return "Config reloaded."
	return ""

def cmd_browse_config(bot, event, cmd):
	#dire = cmd.split("browse_config")[1][1:];
	if len(cmd.split(" ")) > 1:
		dire = cmd.split(" ")[1];
	else:
		dire = "";
	
	dirs = dire.split("/");
	itr = config;
	i=0;
	
	for i in range(0,len(dirs)):
		if dirs[i].strip() == "":
			break;
		if dirs[i] in itr:
			itr = itr[dirs[i]];
			continue;
		else:
			return "%s is not a valid path" % dire
	
	if isinstance(itr, dict):
		text = "";
		for key in itr.keys():
			if isinstance(key,dict):
				key = key+"/"
			text = "%s %s " % (text,key);
		return text
	else:
		return "%s = %s" %(dire, itr);

def cmd_set_config(bot, event, cmd):
	if len(cmd.split(" ")) < 3:
		return "wrong syntax";
	
	dire = cmd.split(" ")[1];
	value = " ".join(cmd.split(" ")[2:]);
	
	dirs = dire.split("/");
	itr = config;
	i=0;
	
	for i in range(0,len(dirs)-1):
		if dirs[i].strip() == "":
			return "%s is not an item" %dire
		if dirs[i] in itr:
			itr = itr[dirs[i]];
			continue;
		else:
			return "%s is not a valid path" % dire
	
	i=i+1;
	if dirs[i].strip() == "":
			return "%s is not an item" %dire 
	if isinstance(itr[dirs[i]], dict):
		return "%s is not an item" %dire
	else:
		itr[dirs[i]] = value;
		return "%s = %s" %(dire, value);

def on_part(bot,event):
	found = 0;
	for c in bot.channels.values():
		for u in c.users():
			if u == irclib.nm_to_n(event.source()):
				found = found + 1;
	
	if found < 2:
		output("info", "Logout: %s" %(event.source()))
		if event.source() in lconfig["users"]:
			del lconfig["users"][event.source()]

def on_quit(bot,event):
	output("info", "Logout: %s" %(event.source()))
	if event.source() in lconfig["users"]:
		del lconfig["users"][event.source()]


def on_nick(bot,event):
	newhost = irclib.nm_to_uh(event.source());
	if event.source() in lconfig["users"]:
		lconfig["users"]["%s!%s" %(event.target(),newhost)] = lconfig["users"][event.source()];
		del lconfig["users"][event.source()];

def on_welcome(bot,event):
	for k in lconfig["on_welcome_send"].keys():
		output("info", "on_welcome_send \"%s\": %s" %(k,lconfig["on_welcome_send"][k]))
		bot.connection.send_raw(lconfig["on_welcome_send"][k]);
	pass

def is_allowed(config, bot, e, cmd_id, cmd):
	level = 0;

	if ("users" in lconfig) and (e.source() in lconfig["users"]):
		level = lconfig["users"][e.source()]["level"];
	
	if e.eventtype()== "console":
		return 1;
	else:
		if (cmd_id in lconfig["commands"]) and ("min_level" in lconfig["commands"][cmd_id]):
			return lconfig["commands"][cmd_id]["min_level"] <= level;
	return 0;

def set_level(command, min_level):
	lconfig["commands"][command] = {};
	lconfig["commands"][command]["min_level"] = min_level;

config = {};
lconfig = {};

def init(plugin,root_config):
	global config;
	global lconfig;
	
	config = root_config;

	lconfig = register_plugin(plugin, config, plugin_name, plugin_description, plugin_version);
	
	if not "reg_users" in lconfig:
		lconfig["reg_users"] = {}
	if not "users" in lconfig:
		lconfig["users"] = {}
	if not "commands" in lconfig:
		lconfig["commands"] = {}
	if not "on_welcome_send" in lconfig:
		lconfig["on_welcome_send"] = {}
	
	set_level("reload_plugins",5);
	set_level("reload_config", 5);
	set_level("browse_config", 5);
	set_level("set_config", 5);
	set_level("help", 0);
	set_level("disconnect", 5);
	set_level("quit", 5);
	set_level("login", 0);
	set_level("join", 3);
	set_level("leave", 3);
	set_level("quote", 5);
	
	register_command(config, plugin, "reload_plugins", cmd_reload_plugins, "Reload all plugins");
	register_command(config, plugin, "reload_config", cmd_reload_config, "Reload config");
	register_command(config, plugin, "browse_config", cmd_browse_config, "Browse config");
	register_command(config, plugin, "set_config", cmd_set_config, "Set config options");
	register_command(config, plugin, "help", cmd_help, "Print help");
	register_command(config, plugin, "disconnect", cmd_disconnect, "Disconnect from server");
	register_command(config, plugin, "quit", cmd_quit, "Shutdown");
	register_command(config, plugin, "login", cmd_login, "login <user> <pw>");
	register_command(config, plugin, "join", cmd_join, "join <channel> [<pw>]");
	register_command(config, plugin, "leave", cmd_leave, "leave <channel>");
	register_command(config, plugin, "quote", cmd_quote, "Send raw commands");
	register_callback(config, plugin, "part", "login", on_part);
	register_callback(config, plugin, "quit", "login", on_quit);
	register_callback(config, plugin, "nick", "login", on_nick);
	register_callback(config, plugin, "welcome", "login", on_welcome);
	register_callback(config, plugin, "auth", "login", is_allowed);
	






