#!/usr/bin/env python
"""Simple parsers for configuration files."""

import logging
import os
import re
import stat

from grr.lib import lexer
from grr.lib import parsers
from grr.lib import utils
from grr.lib.rdfvalues import anomaly as rdf_anomaly
from grr.lib.rdfvalues import client as rdf_client
from grr.lib.rdfvalues import protodict as rdf_protodict
from grr.parsers import config_file


class LSBInitLexer(lexer.Lexer):
  """Parse out upstart configurations from init scripts.

  Runlevels in /etc/init.d are defined in stanzas like:
  ### BEGIN INIT INFO
  # Provides:             sshd
  # Required-Start:       $remote_fs $syslog
  # Required-Stop:        $remote_fs $syslog
  # Default-Start:        2 3 4 5
  # Default-Stop:         1
  # Short-Description:    OpenBSD Secure Shell server
  ### END INIT INFO
  """

  tokens = [
      lexer.Token("INITIAL", r"### BEGIN INIT INFO", None, "UPSTART"),
      lexer.Token("UPSTART", r"### END INIT INFO", "Finish", "INITIAL"),
      lexer.Token("UPSTART", r"#\s+([-\w]+):\s+([^#\n]*)", "StoreEntry", None),
      lexer.Token("UPSTART", r"\n\s*\w+", "Finish", None),
      lexer.Token(".*", ".", None, None)
  ]

  required = {"provides", "default-start"}

  def __init__(self):
    super(LSBInitLexer, self).__init__()
    self.entries = {}

  def StoreEntry(self, match, **_):
    key, val = match.groups()
    setting = key.strip().lower()
    if setting:
      self.entries[setting] = val

  def Finish(self, **_):
    self.buffer = []

  def ParseEntries(self, data):
    self.entries = {}
    self.Reset()
    self.Feed(utils.SmartStr(data))
    self.Close()
    found = set(self.entries)
    if self.required.issubset(found):
      return self.entries


def _LogInvalidRunLevels(states, valid):
  """Log any invalid run states found."""
  invalid = set()
  for state in states:
    if state not in valid:
      invalid.add(state)
  if invalid:
    logging.warn("Invalid init runlevel(s) encountered: %s", ", ".join(invalid))


def GetRunlevelsLSB(states):
  """Accepts a string and returns a list of strings of numeric LSB runlevels."""
  if not states:
    return set()
  valid = set(["0", "1", "2", "3", "4", "5", "6"])
  _LogInvalidRunLevels(states, valid)
  return valid.intersection(set(states.split()))


def GetRunlevelsNonLSB(states):
  """Accepts a string and returns a list of strings of numeric LSB runlevels."""
  if not states:
    return set()
  convert_table = {
      "0": "0",
      "1": "1",
      "2": "2",
      "3": "3",
      "4": "4",
      "5": "5",
      "6": "6",
      # SysV, Gentoo, Solaris, HP-UX all allow an alpha variant
      # for single user. https://en.wikipedia.org/wiki/Runlevel
      "S": "1",
      "s": "1"
  }
  _LogInvalidRunLevels(states, convert_table)
  return set([convert_table[s] for s in states.split() if s in convert_table])


class LinuxLSBInitParser(parsers.FileParser):
  """Parses LSB style /etc/init.d entries."""

  output_types = ["LinuxServiceInformation"]
  supported_artifacts = ["LinuxLSBInit"]
  process_together = True

  def _Facilities(self, condition):
    results = []
    for facility in condition.split():
      for expanded in self.insserv.get(facility, []):
        if expanded not in results:
          results.append(expanded)
    return results

  def _ParseInit(self, init_files):
    init_lexer = LSBInitLexer()
    for path, file_obj in init_files:
      init = init_lexer.ParseEntries(file_obj.read(100000))
      if init:
        service = rdf_client.LinuxServiceInformation()
        service.name = init.get("provides")
        service.start_mode = "INIT"
        service.start_on = GetRunlevelsLSB(init.get("default-start"))
        if service.start_on:
          service.starts = True
        service.stop_on = GetRunlevelsLSB(init.get("default-stop"))
        service.description = init.get("short-description")
        service.start_after = self._Facilities(init.get("required-start", []))
        service.stop_after = self._Facilities(init.get("required-stop", []))
        yield service
      else:
        logging.debug("No runlevel information found in %s", path)

  def _InsservExpander(self, facilities, val):
    """Expand insserv variables."""
    expanded = []
    if val.startswith("$"):
      vals = facilities.get(val, [])
      for v in vals:
        expanded.extend(self._InsservExpander(facilities, v))
    elif val.startswith("+"):
      expanded.append(val[1:])
    else:
      expanded.append(val)
    return expanded

  def _ParseInsserv(self, data):
    """/etc/insserv.conf* entries define system facilities.

    Full format details are in man 8 insserv, but the basic structure is:
      $variable          facility1 facility2
      $second_variable   facility3 $variable

    Any init script that specifies Required-Start: $second_variable needs to be
    expanded to facility1 facility2 facility3.

    Args:
      data: A string of insserv definitions.
    """
    parser = config_file.FieldParser()
    entries = parser.ParseEntries(data)
    raw = {e[0]: e[1:] for e in entries}
    # Now expand out the facilities to services.
    facilities = {}
    for k, v in raw.iteritems():
      # Remove interactive tags.
      k = k.replace("<", "").replace(">", "")
      facilities[k] = v
    for k, vals in facilities.iteritems():
      self.insserv[k] = []
      for v in vals:
        self.insserv[k].extend(self._InsservExpander(facilities, v))

  def ParseMultiple(self, stats, file_objs, _):
    self.insserv = {}
    paths = [s.pathspec.path for s in stats]
    files = dict(zip(paths, file_objs))
    insserv_data = ""
    init_files = []
    for k, v in files.iteritems():
      if k.startswith("/etc/insserv.conf"):
        insserv_data += "%s\n" % v.read(100000)
      else:
        init_files.append((k, v))
    self._ParseInsserv(insserv_data)
    for rslt in self._ParseInit(init_files):
      yield rslt


class LinuxXinetdParser(parsers.FileParser):
  """Parses xinetd entries."""

  output_types = ["LinuxServiceInformation"]
  supported_artifacts = ["LinuxXinetd"]
  process_together = True

  def _ParseSection(self, section, cfg):
    parser = config_file.KeyValueParser()
    # Skip includedir, we get this from the artifact.
    if section.startswith("includedir"):
      return
    elif section.startswith("default"):
      for val in parser.ParseEntries(cfg):
        self.default.update(val)
    elif section.startswith("service"):
      svc = section.replace("service", "").strip()
      if not svc:
        return
      self.entries[svc] = {}
      for val in parser.ParseEntries(cfg):
        self.entries[svc].update(val)

  def _ProcessEntries(self, fd):
    """Extract entries from the xinetd config files."""
    parser = config_file.KeyValueParser(kv_sep="{", term="}", sep=None)
    data = fd.read(100000)
    entries = parser.ParseEntries(data)
    for entry in entries:
      for section, cfg in entry.items():
        # The parser returns a list of configs. There will only be one.
        if cfg:
          cfg = cfg[0].strip()
        else:
          cfg = ""
        self._ParseSection(section, cfg)

  def _GenConfig(self, cfg):
    """Interpolate configurations with defaults to generate actual configs."""
    # Some setting names may have a + or - suffix. These indicate that the
    # settings modify the default values.
    merged = self.default.copy()
    for setting, vals in cfg.iteritems():
      option, operator = (setting.split(None, 1) + [None])[:2]
      vals = set(vals)
      default = set(self.default.get(option, []))
      # If there is an operator, updated values accordingly.
      if operator == "+":
        vals = default.union(vals)
      elif operator == "-":
        vals = default.difference(vals)
      merged[option] = list(vals)
    return rdf_protodict.AttributedDict(**merged)

  def _GenService(self, name, cfg):
    # Merge the config values.
    service = rdf_client.LinuxServiceInformation(name=name)
    service.config = self._GenConfig(cfg)
    if service.config.disable == ["no"]:
      service.starts = True
      service.start_mode = "XINETD"
      service.start_after = ["xinetd"]
    return service

  def ParseMultiple(self, stats, file_objs, _):
    self.entries = {}
    self.default = {}
    paths = [s.pathspec.path for s in stats]
    files = dict(zip(paths, file_objs))
    for v in files.values():
      self._ProcessEntries(v)
    for name, cfg in self.entries.iteritems():
      yield self._GenService(name, cfg)


class LinuxSysVInitParser(parsers.FileParser):
  """Parses SysV runlevel entries.

  Reads the stat entries for files under /etc/rc* runlevel scripts.
  Identifies start and stop levels for services.

  Yields:
    LinuxServiceInformation for each service with a runlevel entry.
    Anomalies if there are non-standard service startup definitions.
  """

  output_types = ["LinuxServiceInformation"]
  supported_artifacts = ["LinuxSysVInit"]
  process_together = True

  runlevel_re = re.compile(r"/etc/rc(?:\.)?([0-6S]|local$)(?:\.d)?")
  runscript_re = re.compile(r"(?P<action>[KS])(?P<prio>\d+)(?P<name>\S+)")

  def ParseMultiple(self, stats, unused_file_obj, unused_kb):
    """Identify the init scripts and the start/stop scripts at each runlevel.

    Evaluate all the stat entries collected from the system.
    If the path name matches a runlevel spec, and if the filename matches a
    sysv init symlink process the link as a service.

    Args:
      stats: An iterator of StatEntry rdfs.
      unused_file_obj: An iterator of file contents. Not needed as the parser
        only evaluates link attributes.
      unused_kb: Unused KnowledgeBase rdf.

    Yields:
      rdf_anomaly.Anomaly if the startup link seems wierd.
      rdf_client.LinuxServiceInformation for each detected service.
    """
    services = {}
    for stat_entry in stats:
      path = stat_entry.pathspec.path
      runlevel = self.runlevel_re.match(os.path.dirname(path))
      runscript = self.runscript_re.match(os.path.basename(path))
      if runlevel and runscript:
        svc = runscript.groupdict()
        service = services.setdefault(svc["name"],
                                      rdf_client.LinuxServiceInformation(
                                          name=svc["name"], start_mode="INIT"))
        runlvl = GetRunlevelsNonLSB(runlevel.group(1))
        if svc["action"] == "S" and runlvl:
          service.start_on.append(runlvl.pop())
          service.starts = True
        elif runlvl:
          service.stop_on.append(runlvl.pop())
        if not stat.S_ISLNK(int(stat_entry.st_mode)):
          yield rdf_anomaly.Anomaly(
              type="PARSER_ANOMALY",
              finding=[path],
              explanation="Startup script is not a symlink.")
    for svc in services.itervalues():
      yield svc
