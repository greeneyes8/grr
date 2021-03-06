#!/usr/bin/env python
"""This module contains regression tests for cron-related API handlers."""




from grr.gui import api_regression_test_lib
from grr.gui.api_plugins import cron as cron_plugin
from grr.gui.api_plugins import cron_test as cron_plugin_test

from grr.lib import flags
from grr.lib import rdfvalue
from grr.lib.rdfvalues import cronjobs as rdf_cronjobs
from grr.lib.rdfvalues import file_finder as rdf_file_finder
from grr.server import aff4
from grr.server import foreman as rdf_foreman
from grr.server.aff4_objects import cronjobs
from grr.server.flows.cron import system as cron_system
from grr.server.flows.general import file_finder
from grr.server.hunts import standard
from grr.test_lib import test_lib


class ApiListCronJobsHandlerRegressionTest(
    api_regression_test_lib.ApiRegressionTest,
    cron_plugin_test.CronJobsTestMixin):
  """Test cron jobs list handler."""

  api_method = "ListCronJobs"
  handler = cron_plugin.ApiListCronJobsHandler

  def Run(self):
    # Add one "normal" cron job...
    with test_lib.FakeTime(42):
      self.CreateCronJob(
          flow_name=cron_system.GRRVersionBreakDown.__name__,
          periodicity="1d",
          lifetime="2h",
          description="foo",
          disabled=True,
          token=self.token)

    # ...one disabled cron job,
    with test_lib.FakeTime(84):
      self.CreateCronJob(
          flow_name=cron_system.OSBreakDown.__name__,
          periodicity="7d",
          lifetime="1d",
          description="bar",
          token=self.token)

    # ...and one failing cron job.
    with test_lib.FakeTime(126):
      cron_urn = self.CreateCronJob(
          flow_name=cron_system.LastAccessStats.__name__,
          periodicity="7d",
          lifetime="1d",
          token=self.token)

      for i in range(4):
        with test_lib.FakeTime(200 + i * 10):
          with aff4.FACTORY.OpenWithLock(cron_urn, token=self.token) as job:
            job.Set(job.Schema.LAST_RUN_TIME(rdfvalue.RDFDatetime.Now()))
            job.Set(
                job.Schema.LAST_RUN_STATUS(
                    status=rdf_cronjobs.CronJobRunStatus.Status.ERROR))

    self.Check("ListCronJobs", args=cron_plugin.ApiListCronJobsArgs())


class ApiCreateCronJobHandlerRegressionTest(
    api_regression_test_lib.ApiRegressionTest):
  """Test handler that creates a new cron job."""

  api_method = "CreateCronJob"
  handler = cron_plugin.ApiCreateCronJobHandler

  # ApiCronJob references CreateAndRunGenericHuntFlow that contains
  # some legacy dynamic fields, that can't be serialized in JSON-proto3-friendly
  # way.
  uses_legacy_dynamic_protos = True

  def Run(self):

    def ReplaceCronJobUrn():
      jobs = list(cronjobs.CRON_MANAGER.ListJobs(token=self.token))
      return {jobs[0].Basename(): "CreateAndRunGeneicHuntFlow_1234"}

    flow_args = standard.CreateGenericHuntFlowArgs()
    flow_args.hunt_args.flow_args = rdf_file_finder.FileFinderArgs(
        paths=["c:\\windows\\system32\\notepad.*"])
    flow_args.hunt_args.flow_runner_args.flow_name = (
        file_finder.FileFinder.__name__)
    flow_args.hunt_runner_args.client_rule_set.rules = [
        rdf_foreman.ForemanClientRule(os=rdf_foreman.ForemanOsClientRule(
            os_windows=True))
    ]
    flow_args.hunt_runner_args.description = "Foobar! (cron)"

    self.Check(
        "CreateCronJob",
        args=cron_plugin.ApiCronJob(
            description="Foobar!",
            flow_name=standard.CreateAndRunGenericHuntFlow.__name__,
            periodicity=604800,
            lifetime=3600,
            flow_args=flow_args),
        replace=ReplaceCronJobUrn)


class ApiListCronJobFlowsHandlerRegressionTest(
    api_regression_test_lib.ApiRegressionTest):
  """Test cron job flows list handler."""

  api_method = "ListCronJobFlows"
  handler = cron_plugin.ApiListCronJobFlowsHandler

  flow_name = cron_system.GRRVersionBreakDown.__name__

  def setUp(self):
    super(ApiListCronJobFlowsHandlerRegressionTest, self).setUp()

    with test_lib.FakeTime(44):
      cron_args = cronjobs.CreateCronJobFlowArgs(
          periodicity="7d", lifetime="1d")
      cron_args.flow_runner_args.flow_name = self.flow_name
      cronjobs.CRON_MANAGER.ScheduleFlow(
          cron_args, job_name=self.flow_name, token=self.token)

      cronjobs.CRON_MANAGER.RunOnce(token=self.token)

  def _GetFlowId(self):
    cron_job_urn = list(cronjobs.CRON_MANAGER.ListJobs(token=self.token))[0]
    cron_job = aff4.FACTORY.Open(cron_job_urn, token=self.token)

    cron_job_flow_urn = list(cron_job.ListChildren())[0]

    return cron_job_flow_urn.Basename()

  def Run(self):
    flow_id = self._GetFlowId()

    self.Check(
        "ListCronJobFlows",
        args=cron_plugin.ApiListCronJobFlowsArgs(cron_job_id=self.flow_name),
        replace={flow_id: "F:ABCDEF11"})


class ApiGetCronJobFlowHandlerRegressionTest(
    api_regression_test_lib.ApiRegressionTest):
  """Test cron job flow getter handler."""

  api_method = "GetCronJobFlow"
  handler = cron_plugin.ApiGetCronJobFlowHandler

  def setUp(self):
    super(ApiGetCronJobFlowHandlerRegressionTest, self).setUp()

    self.flow_name = cron_system.GRRVersionBreakDown.__name__

    with test_lib.FakeTime(44):
      cron_args = cronjobs.CreateCronJobFlowArgs(
          periodicity="7d", lifetime="1d")
      cron_args.flow_runner_args.flow_name = self.flow_name
      cronjobs.CRON_MANAGER.ScheduleFlow(
          cron_args, job_name=self.flow_name, token=self.token)

      cronjobs.CRON_MANAGER.RunOnce(token=self.token)

  def _GetFlowId(self):
    cron_job_urn = list(cronjobs.CRON_MANAGER.ListJobs(token=self.token))[0]
    cron_job = aff4.FACTORY.Open(cron_job_urn, token=self.token)

    cron_job_flow_urn = list(cron_job.ListChildren())[0]

    return cron_job_flow_urn.Basename()

  def Run(self):
    flow_id = self._GetFlowId()

    self.Check(
        "GetCronJobFlow",
        args=cron_plugin.ApiGetCronJobFlowArgs(
            cron_job_id=self.flow_name, flow_id=flow_id),
        replace={flow_id: "F:ABCDEF11"})


class ApiForceRunCronJobRegressionTest(
    api_regression_test_lib.ApiRegressionTest,
    cron_plugin_test.CronJobsTestMixin):
  """Test cron job flow getter handler."""

  api_method = "ForceRunCronJob"
  handler = cron_plugin.ApiForceRunCronJobHandler

  def Run(self):
    self.CreateCronJob(
        flow_name=cron_system.OSBreakDown.__name__, token=self.token)

    self.Check(
        "ForceRunCronJob",
        args=cron_plugin.ApiForceRunCronJobArgs(
            cron_job_id=cron_system.OSBreakDown.__name__))


class ApiModifyCronJobRegressionTest(api_regression_test_lib.ApiRegressionTest,
                                     cron_plugin_test.CronJobsTestMixin):
  """Test cron job flow getter handler."""

  api_method = "ModifyCronJob"
  handler = cron_plugin.ApiModifyCronJobHandler

  def Run(self):
    self.CreateCronJob(
        flow_name=cron_system.OSBreakDown.__name__, token=self.token)
    self.CreateCronJob(
        flow_name=cron_system.GRRVersionBreakDown.__name__, token=self.token)

    self.Check(
        "ModifyCronJob",
        args=cron_plugin.ApiModifyCronJobArgs(
            cron_job_id=cron_system.OSBreakDown.__name__, state="ENABLED"))
    self.Check(
        "ModifyCronJob",
        args=cron_plugin.ApiModifyCronJobArgs(
            cron_job_id=cron_system.GRRVersionBreakDown.__name__,
            state="DISABLED"))


def main(argv):
  api_regression_test_lib.main(argv)


if __name__ == "__main__":
  flags.StartMain(main)
