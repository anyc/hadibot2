#! /usr/bin/python
# -*- coding: utf-8 -*-
#
#	Author: Mario Kicherer (http://empanyc.net)
#	License: GPL v2 (http://www.gnu.org/licenses/gpl-2.0.txt)
#
# Features:
#
#	- diff: monitor LDAP objects and publish changes
#	- op: op people based on LDAP information
#		add ircGroup to a posixGroup and insert an ircChannel, add ircUser to every member of the
#		group and set ircUser (e.g. nick!user@myhost.com)
#
#
# LDAP schema for auto-op:
#
#	Add this to a group and specify their channel:
#	
#		objectclass ( $PATH NAME 'ircGroup'
#			DESC 'IRC Group'
#			SUP top AUXILIARY
#			MUST ( ircChannel ) )
#
#	Add this to every user
#
#		objectclass ( $PATH NAME 'ircUser'
#			DESC 'IRC User'                                
#			SUP top AUXILIARY                              
#			MAY ( ircOrigin ) )     
#
#	Corresponding attributes:
#	
#		attributetype ( $PATH NAME 'ircOrigin'
#			DESC 'ircOrigin'                                   
#			EQUALITY caseIgnoreMatch                           
#			SYNTAX 1.3.6.1.4.1.1466.115.121.1.15 )             
#
#		attributetype ( $PATH NAME 'ircChannel'
#			DESC 'ircChannel'                                   
#			EQUALITY caseIgnoreMatch                            
#			SYNTAX 1.3.6.1.4.1.1466.115.121.1.15 )   
#
# Example config:
#
#	plugins.ldap.config.ldap.server=ldap://ldap.mydomain.de
#	plugins.ldap.config.ldap.login=cn=readonly,dc=mydomain,dc=de
#	plugins.ldap.config.ldap.password=mypassword
#	
#	plugins.ldap.config.auth.people_base=ou=people,dc=mydomain,dc=de
#	plugins.ldap.config.auth.group_base=ou=groups,dc=mydomain,dc=de
#	
#	plugins.ldap.config.diff.interval=600
#	plugins.ldap.config.diff.server.announce=#myhadibot
#	plugins.ldap.config.diff.server.base=ou=server,dc=mydomain,dc=de
#	plugins.ldap.config.diff.server.filter=(objectClass=*)
#	plugins.ldap.config.diff.server.attributes=memberUid


import irclib
import ldap
import re,sys,datetime
import threading,thread,os

from hadibot import register_command,register_callback,is_cmd_allowed,output,register_plugin,reload_plugins,verbose_lvl;
from irclib import nm_to_n, nm_to_h
from time import sleep

plugin_name = "ldap";
plugin_description = "Some ldap tools";
plugin_version = "0.1";

def query_ldap(base, scope, filter, retrieve_attributes,rdn=False):
	try:
		ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT,0)
		l = ldap.initialize(lconfig["ldap"]["server"])
		l.start_tls_s()
		l.simple_bind_s(lconfig["ldap"]["login"], lconfig["ldap"]["password"])
		#print "Successfully bound to server.\n"
	except ldap.LDAPError, error_message:
		output("error", "LDAP Couldn't Connect. %s " % error_message);
		return None
	
	result_set = [];
	result = [];
	timeout = 0;
	
	try:
		result_id = l.search(base, scope, filter, retrieve_attributes)
		
		while 1:
			result_type, result_data = l.result(result_id, timeout)
			if (result_data == []):
				break
			else:
				if result_type == ldap.RES_SEARCH_ENTRY:
					result_set.extend(result_data)
		
		if len(result_set) == 0:
			output("info", "LDAP: No Results.")
		
		if rdn:
			result = result_set;
		else:
			for entry in result_set:
				result.append(entry[1]);
			#for i in range(len(result_set)):
			#	for entry in result_set[i]:  
					#print entry[1]["uid"][0], "logged in"
					#print entry[1]["ircOrigin"][0], " <-"
			#		result.append(entry[1]);
		
	except ldap.LDAPError, error_message:
		output("error", "LDAP Query error %s for %s %s %s" % (error_message,base,filter, retrieve_attributes) )
		return None
	
	return result;


#def check_users(bot,event,channel,group):
	
	#if not channel in bot.channels:
		#return "%s not found" % channel;
	
	#scope = ldap.SCOPE_SUBTREE
	#base = "dc=hadiko,dc=de";
	#retrieve_attributes = None;
	#filter = "(&(objectClass=ircUser)(objectClass=%s))" % (group);# %(event.source());
	#result = query_ldap(base,scope,filter,retrieve_attributes);
	#if result:
		#for entry in result:
			#if "ircOrigin" in entry:
				#for item in entry["ircOrigin"]:
					#for user in bot.channels[channel].users():
						#print user
						#res = re.match(item, user);
						#if res:
							#if entry["hadinetStatus"][0] == "tutor":
								#bot.connection.mode(channel, "+o %s" % nm_to_n(user))
							#if entry["hadinetStatus"][0] == "helfer":
								#bot.connection.mode(channel, "+v %s" % nm_to_n(user))
	#return ""

#def on_join(bot,event):
	#check_user(bot, event, event.target(), [event.source()]);
	#pass

#def cmd_auth_channel(bot, event, cmd):
	#global config;
	#text = "";
	
	#res = re.match("\s*auth_channel\s*(#*\w*)\s*", cmd);
	#if res:
		#if res.group(1).strip() != "":
			#text = check_users(bot, event, res.group(1).strip(), "hadikoAktiv");
		#else:
			#text = check_users(bot, event, event.target().strip(), "hadikoAktiv");
	
	#return text

def on_join(bot,event):
	channels = [];
	
	scope = ldap.SCOPE_SUBTREE
	base = lconfig["auth"]["group_base"];
	
	if base.strip() == "":
		return;
	
	retrieve_attributes = None;
	filter = "(objectClass=ircGroup)";
	result = query_ldap(base,scope,filter,retrieve_attributes);
	if result:
		for entry in result:
			if "ircChannel" in entry:
				channels.append(entry["ircChannel"][0]);
			
			if "memberUid" in entry:
				for member in entry["memberUid"]:
					scope = ldap.SCOPE_SUBTREE
					base = lconfig["auth"]["people_base"];
					retrieve_attributes = None;
					filter = "(&(cn=%s)(objectClass=ircUser))" % (member);# %(event.source());
					result = query_ldap(base,scope,filter,retrieve_attributes);
					if result:
						for entry in result:
							if "ircOrigin" in entry:
								for item in entry["ircOrigin"]:
									res = re.match(item, event.source());
									if res:
										bot.connection.mode(event.target(), "+o %s" % nm_to_n(event.source()))

def on_channels(bot,event):
	channels = [];
	scope = ldap.SCOPE_SUBTREE
	base = lconfig["auth"]["group_base"];
	
	if base.strip() == "":
		return [];
	
	retrieve_attributes = None;
	filter = "(objectClass=ircGroup)";
	result = query_ldap(base,scope,filter,retrieve_attributes);
	if result:
		for entry in result:
			if "ircChannel" in entry:
				channels.append(entry["ircChannel"][0]);
	
	for key,val in lconfig["diff"].items():
		if "announce" in val:
			channels.append(val["announce"]);
	
	return channels;

def sendMessage(bot, channel, text):
	bot.connection.privmsg(channel, text);

class DiffLoop ( threading.Thread ):
	stop = True;
	interval = 600;
	old_state = {};
	#pid = 0;
	
	def __init__ (self, interval=600):
		threading.Thread.__init__(self);
		self.interval = interval;
	
	def shutdown(self):
		self.stop=True;
		#os.popen("kill -9 "+str(self.pid));
	
	def run ( self ):
		#self.pid = os.getpid();
		self.stop = False;
		first = True;
		
		while (not self.stop):
			new_state = {};
			for key,rule in lconfig["diff"].items():
				if not type(rule) == type({}):
					continue;
				
				new_state[key] = {};
				
				if "base" in rule:
					base = rule["base"];
				else:
					base = "";
				
				if "filter" in rule:
					filter = rule["filter"];
				else:
					filter = "(objectClass=*)";
				
				if "attributes" in rule:
					attributes = rule["attributes"].split(",");
				else:
					attributes = None;
				
				#scope = ldap.SCOPE_SUBTREE
				scope = ldap.SCOPE_ONELEVEL
				
				result = query_ldap(base,scope,filter,attributes, True);
				if (result):
					for entry_tuple in result:
						entry = entry_tuple[1];
						rdn = entry_tuple[0];
						new_state[key][rdn] = entry;
						
						if first:
							continue
						
						if not rdn in self.old_state[key]:
							sendMessage(bot, rule["announce"], "%s: new object \"%s\"" % (key,rdn.split(",")[0]));
							self.old_state[key][rdn] = {}
						
						for ikey in entry.keys():
							if not ikey in self.old_state[key][rdn]:
								sendMessage(bot, rule["announce"], "%s: new attribute %s->%s->%s" % (key,rdn.split(",")[0], ikey, entry[ikey]));
							else:
								for item in entry[ikey]:
									if item not in self.old_state[key][rdn][ikey]:
										sendMessage(bot, rule["announce"], "%s: new value %s->%s->%s" % (key,rdn.split(",")[0], ikey, item));
						
						if rdn in self.old_state[key]:
							for ikey in self.old_state[key][rdn].keys():
								if not ikey in entry:
									sendMessage(bot, rule["announce"], "%s: removed attribute %s->%s" % (key,rdn.split(",")[0], ikey));
								else:
									for item in self.old_state[key][rdn][ikey]:
										if item not in entry[ikey]:
											sendMessage(bot, rule["announce"], "%s: removed value %s->%s->%s" % (key,rdn.split(",")[0], ikey, item));
				
				if key in self.old_state:
					for ikey in self.old_state[key].keys():
						if not ikey in new_state[key]:
							sendMessage(bot, rule["announce"], "%s: removed object \"%s\"" % (key,ikey.split(",")[0]));
			
			self.old_state = new_state;
			first = False;
			
			# the following delays shutdown. killing threads in python sucks
			#sleep(self.interval);
			
			# ugly but allows almost immediate shutdown
			for w in range(1,self.interval):
				sleep(1);
				if self.stop:
					break;

config = {};
lconfig = {};
bot = None;
dl = None;

def init(plugin,root_config):
	global config;
	global lconfig;
	global bot;
	global dl;
	
	config = root_config;
	
	bot = config["main"]["bot_handle"];

	lconfig = register_plugin(plugin, config, plugin_name, plugin_description, plugin_version);
	
	if (not "ldap" in lconfig):
		lconfig["ldap"] = {};
	if not "server" in lconfig["ldap"]:
		lconfig["ldap"]["server"] = "ldap://localhost"
	if not "login" in lconfig["ldap"]:
		lconfig["ldap"]["login"] = ""
	if not "password" in lconfig["ldap"]:
		lconfig["ldap"]["password"] = ""
	
	if (not "auth" in lconfig):
		lconfig["auth"] = {};
	if not "people_base" in lconfig["auth"]:
		lconfig["auth"]["people_base"] = ""
	if not "group_base" in lconfig["auth"]:
		lconfig["auth"]["group_base"] = ""
	
	if (not "diff" in lconfig):
		lconfig["diff"] = {};
	
	register_callback(config, plugin, "join", "ldapplugin", on_join);
	register_callback(config, plugin, "channels", "ldapplugin", on_channels);
	#register_command(config, plugin, "auth_channel", cmd_auth_channel, 5, "try to authenticate all users in #channel");
	#register_callback(config, plugin, "join", "hadinet", on_join);
	
	if "interval" in lconfig["diff"]:
		dl = DiffLoop(int(lconfig["diff"]["interval"]));
	else:
		dl = DiffLoop();
	dl.start();

def shutdown():
	global dl;
	
	dl.shutdown();





