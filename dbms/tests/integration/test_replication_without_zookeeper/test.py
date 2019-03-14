import time
import pytest

from helpers.cluster import ClickHouseCluster, CLICKHOUSE_START_COMMAND
from helpers.test_tools import assert_eq_with_retry

cluster = ClickHouseCluster(__file__)
node1 = cluster.add_instance('node1', main_configs=['configs/remote_servers.xml'], with_zookeeper=True, stay_alive=True)

@pytest.fixture(scope="module")
def start_cluster():
    try:
        cluster.start()

        node1.query(
        '''
            CREATE DATABASE test;
            CREATE TABLE test_table(date Date, id UInt32)
            ENGINE = ReplicatedMergeTree('/clickhouse/tables/test/replicated', 'node1') ORDER BY id PARTITION BY toYYYYMM(date);
        ''')

        yield cluster

    except Exception as ex:
        print ex

    finally:
        cluster.shutdown()

def drop_zk(zk):
    zk.delete(path="/clickhouse", recursive=True)

def test_startup_without_zookeeper(start_cluster):
    node1.query("INSERT INTO test_table VALUES ('2018-10-01', 1), ('2018-10-02', 2), ('2018-10-03', 3)")
    node1.query("SELECT COUNT(*) from test_table") == "3\n"
    node1.query("SELECT is_readonly from system.replicas where table='test_table'") == "0\n"

    cluster.run_kazoo_commands_with_retries(drop_zk)

    time.sleep(5)
    node1.query("SELECT COUNT(*) from test_table") == "3\n"
    node1.query("SELECT is_readonly from system.replicas where table='test_table'") == "1\n"

    node1.exec_in_container(["bash", "-c", "pkill clickhouse"], user='root')
    time.sleep(5)

    node1.exec_in_container(["bash", "-c", "{} --daemon".format(CLICKHOUSE_START_COMMAND)], user='root')
    time.sleep(5)

    node1.query("SELECT COUNT(*) from test_table") == "3\n"
    node1.query("SELECT is_readonly from system.replicas where table='test_table'") == "1\n"
