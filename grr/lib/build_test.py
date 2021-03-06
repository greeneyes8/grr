#!/usr/bin/env python
"""Tests for building and repacking clients."""

import os
import StringIO

import mock
import yaml

from grr import config
from grr.lib import build
from grr.lib import config_lib
from grr.lib import flags
from grr.lib.rdfvalues import client as rdf_client
from grr.test_lib import test_lib


class BuildTests(test_lib.GRRBaseTest):
  """Tests for building functionality."""

  def testWriteBuildYaml(self):
    """Test build.yaml is output correctly."""
    context = [
        "Target:LinuxDeb", "Platform:Linux", "Target:Linux", "Arch:amd64"
    ]
    expected = {
        "Client.build_environment":
            "cp27-cp27mu-linux_x86_64",
        "Client.build_time":
            "2016-05-24 20:04:25",
        "Template.build_type":
            "Release",
        "Template.build_context": ["ClientBuilder Context"] + context,
        "Template.version_major":
            str(config.CONFIG.Get("Source.version_major")),
        "Template.version_minor":
            str(config.CONFIG.Get("Source.version_minor")),
        "Template.version_revision":
            str(config.CONFIG.Get("Source.version_revision")),
        "Template.version_release":
            str(config.CONFIG.Get("Source.version_release")),
        "Template.arch":
            u"amd64"
    }

    fd = StringIO.StringIO()
    builder = build.ClientBuilder(context=context)

    with mock.patch.object(rdf_client.Uname, "FromCurrentSystem") as fcs:
      fcs.return_value.signature.return_value = "cp27-cp27mu-linux_x86_64"
      with test_lib.FakeTime(1464120265):
        builder.WriteBuildYaml(fd)

    fd.seek(0)
    self.assertEqual(dict(yaml.load(fd)), expected)

  def testGenClientConfig(self):
    with test_lib.ConfigOverrider({"Client.build_environment": "test_env"}):

      deployer = build.ClientRepacker()
      data = deployer.GetClientConfig(["Client Context"], validate=True)

      parser = config_lib.YamlParser(data=data)
      raw_data = parser.RawData()

      self.assertIn("Client.deploy_time", raw_data)

  def testRepackerDummyClientConfig(self):
    """Ensure our dummy client config can pass validation.

    This config is used to exercise repacking code in integration testing, here
    we just make sure it will pass validation.
    """
    new_config = config.CONFIG.MakeNewConfig()
    new_config.Initialize()
    new_config.LoadSecondaryConfig(
        os.path.join(config.CONFIG["Test.data_dir"], "dummyconfig.yaml"))
    build.ClientRepacker().ValidateEndConfig(new_config)


def main(argv):
  test_lib.main(argv)


if __name__ == "__main__":
  flags.StartMain(main)
