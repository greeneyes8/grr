#!/usr/bin/env python
"""Configuration parameters for the data stores."""

from grr.lib import config_lib
from grr.lib import rdfvalue

config_lib.DEFINE_integer("Datastore.maximum_blob_size", 15 * 1024 * 1024,
                          "Maximum blob size we may store in the datastore.")

config_lib.DEFINE_string("Datastore.implementation", "FakeDataStore",
                         "Storage subsystem to use.")

config_lib.DEFINE_string("Blobstore.implementation", "MemoryStreamBlobstore",
                         "Blob storage subsystem to use.")

DATASTORE_PATHING = [
    r"%{(?P<path>files/hash/generic/sha256/...).*}",
    r"%{(?P<path>files/hash/generic/sha1/...).*}",
    r"%{(?P<path>files/hash/generic/md5/...).*}",
    r"%{(?P<path>files/hash/pecoff/md5/...).*}",
    r"%{(?P<path>files/hash/pecoff/sha1/...).*}",
    r"%{(?P<path>files/nsrl/...).*}", r"%{(?P<path>W/[^/]+).*}",
    r"%{(?P<path>CA/[^/]+).*}", r"%{(?P<path>C\..\{1,16\}?)($|/.*)}",
    r"%{(?P<path>hunts/[^/]+).*}", r"%{(?P<path>blobs/[^/]+).*}",
    r"%{(?P<path>[^/]+).*}"
]

config_lib.DEFINE_list("Datastore.pathing", DATASTORE_PATHING,
                       ("Path selection for subjects in the file-based data "
                        "stores (by priority)."))

config_lib.DEFINE_string(
    "Datastore.location",
    default="%(Config.prefix)/var/grr-datastore",
    help=("Location of the data store (usually a "
          "filesystem directory)"))

# SQLite data store.
config_lib.DEFINE_integer(
    "SqliteDatastore.vacuum_check",
    default=10,
    help=("Number of rows that need to be deleted before "
          "checking if the sqlite file may need to be "
          "vacuumed."))

config_lib.DEFINE_integer(
    "SqliteDatastore.vacuum_frequency",
    default=60,
    help=("Minimum interval (in seconds) between vacuum"
          "operations on the same sqlite file."))

config_lib.DEFINE_integer(
    "SqliteDatastore.vacuum_minsize",
    default=10 * 1024,
    help=("Minimum size of sqlite file in bytes required"
          " for vacuuming"))

config_lib.DEFINE_integer(
    "SqliteDatastore.vacuum_ratio",
    default=50,
    help=("Percentage of pages that are free before "
          "vacuuming a sqlite file."))

config_lib.DEFINE_integer(
    "SqliteDatastore.connection_cache_size",
    default=1000,
    help=("Number of file handles kept in the SQLite "
          "data_store cache."))

# MySQLAdvanced data store.
config_lib.DEFINE_string("Mysql.host", "localhost",
                         "The MySQL server hostname.")

config_lib.DEFINE_integer("Mysql.port", 0, "The MySQL server port.")

config_lib.DEFINE_string(
    "Mysql.database_name", default="grr", help="Name of the database to use.")

config_lib.DEFINE_string(
    "Mysql.table_name", default="aff4", help="Name of the table to use.")

config_lib.DEFINE_string(
    "Mysql.database_username",
    default="root",
    help="The user to connect to the database.")

config_lib.DEFINE_string(
    "Mysql.database_password",
    default="",
    help="The password to connect to the database.")

config_lib.DEFINE_integer(
    "Mysql.conn_pool_max",
    10,
    help=("The maximum number of open connections to keep"
          " available in the pool."))

config_lib.DEFINE_integer(
    "Mysql.conn_pool_min",
    5,
    help=("The minimum number of open connections to keep"
          " available in the pool."))

config_lib.DEFINE_integer(
    "Mysql.max_connect_wait",
    0,
    help=("Total number of seconds we wait for a "
          "connection before failing (0 means we wait "
          "forever)."))

# HTTP data store.
config_lib.DEFINE_string(
    "HTTPDataStore.username",
    default="httpuser",
    help="The username to connect to the http data store.")

config_lib.DEFINE_string(
    "HTTPDataStore.password",
    default="httppass",
    help="The password to connect to the http data store.")

config_lib.DEFINE_integer(
    "HTTPDataStore.read_timeout",
    5,
    help="HTTP socket read timeout in seconds.")

config_lib.DEFINE_integer(
    "HTTPDataStore.replay_timeout",
    5,
    help=("HTTP socket read timeout when replaying "
          "requests, in seconds."))

config_lib.DEFINE_integer(
    "HTTPDataStore.send_timeout",
    5,
    help="HTTP socket send timeout in seconds.")

config_lib.DEFINE_integer(
    "HTTPDataStore.login_timeout",
    5,
    help=("HTTP socket timeout when remote servers are "
          "logging in."))

config_lib.DEFINE_integer(
    "HTTPDataStore.reconnect_timeout",
    10 * 60,
    help=("Number of seconds to spend attempting to "
          "reconnect to the database. Attempt every "
          "retry_timeout seconds."))

config_lib.DEFINE_integer(
    "HTTPDataStore.retry_time",
    5,
    help=("Number of seconds to wait in-between attempts"
          "to reconnect to the database."))

config_lib.DEFINE_string(
    "CloudBigtable.project_id",
    default=None,
    help="The Google cloud project ID which will hold the bigtable.")

config_lib.DEFINE_string(
    "CloudBigtable.instance_location",
    default="us-central1-c",
    help="The google cloud zone for the instance. This needs to be in "
    "a zone that has bigtable available and ideally the same zone (or at "
    "least the same region) as the server for performance and billing "
    "reasons.")

config_lib.DEFINE_string(
    "CloudBigtable.instance_id",
    default="grrbigtable",
    help="The cloud bigtable instance ID.")

config_lib.DEFINE_string(
    "CloudBigtable.test_project_id",
    default=None,
    help="Set this to run the cloud bigtable tests. Note that billing applies! "
    "Always check your project has deleted the test instances correctly after "
    "running these tests.")

config_lib.DEFINE_string(
    "CloudBigtable.instance_name",
    default="grrbigtable",
    help="The cloud bigtable instance ID.")

config_lib.DEFINE_semantic(rdfvalue.Duration, "CloudBigtable.retry_interval",
                           "1s", "Time to wait before first retry.")

config_lib.DEFINE_integer(
    "CloudBigtable.retry_max_attempts",
    default=5,
    help="Maximum number of retries on RPC before we give up.")

config_lib.DEFINE_integer("CloudBigtable.retry_multiplier", 2,
                          "For each retry, multiply last delay by this value.")

config_lib.DEFINE_string(
    "CloudBigtable.table_name",
    default="grrbigtable",
    help="The cloud bigtable table name.")

config_lib.DEFINE_integer("CloudBigtable.threadpool_size", 100,
                          "The threadpool size for making"
                          "parallel RPC calls.")

config_lib.DEFINE_integer(
    "CloudBigtable.serve_nodes", 3, help=("Number of bigtable serve nodes."))
