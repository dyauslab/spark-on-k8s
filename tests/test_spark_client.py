from __future__ import annotations

import datetime
import importlib
import json
import os
from typing import Callable
from unittest import mock

import pytest
from freezegun import freeze_time
from spark_on_k8s import client as client_module
from spark_on_k8s.client import ExecutorInstances, PodResources, SparkOnK8S, default_app_id_suffix
from spark_on_k8s.utils import configuration as configuration_module

FAKE_TIME = datetime.datetime(2024, 1, 14, 12, 12, 31)


def empty_suffix() -> str:
    return ""


class TestSparkOnK8s:
    @pytest.mark.parametrize(
        "app_name, app_id_suffix, expected_app_name, expected_app_id",
        [
            pytest.param(
                "spark-app-name",
                empty_suffix,
                "spark-app-name",
                "spark-app-name",
                id="app_name_without_suffix",
            ),
            pytest.param(
                "spark-app-name",
                default_app_id_suffix,
                "spark-app-name",
                "spark-app-name-20240114121231",
                id="app_name_with_suffix",
            ),
            pytest.param(
                "some-very-long-name-which-is-not-allowed-by-k8s-which-is-why-we-need-to-truncate-it",
                empty_suffix,
                "some-very-long-name-which-is-not-allowed-by-k8s-which-is-why-we",
                "some-very-long-name-which-is-not-allowed-by-k8s-which-is-why-we",
                id="app_name_without_suffix_long",
            ),
            pytest.param(
                "some-very-long-name-which-is-not-allowed-by-k8s-which-is-why-we-need-to-truncate-it",
                default_app_id_suffix,
                "some-very-long-name-which-is-not-allowed-by-k8s-w",
                "some-very-long-name-which-is-not-allowed-by-k8s-w-20240114121231",
                id="app_name_with_suffix_long",
            ),
            pytest.param(
                "some-name-ends-with-invalid-character-",
                empty_suffix,
                "some-name-ends-with-invalid-character",
                "some-name-ends-with-invalid-character",
                id="app_name_without_suffix_invalid_character",
            ),
            pytest.param(
                "some-name-ends-with-invalid-character-",
                default_app_id_suffix,
                "some-name-ends-with-invalid-character",
                "some-name-ends-with-invalid-character-20240114121231",
                id="app_name_with_suffix_invalid_character",
            ),
            pytest.param(
                "some.invalid_characters-in/the-name",
                empty_suffix,
                "some-invalid-characters-in-the-name",
                "some-invalid-characters-in-the-name",
                id="app_name_without_suffix_invalid_characters",
            ),
            pytest.param(
                "some.invalid_characters-in/the-name",
                default_app_id_suffix,
                "some-invalid-characters-in-the-name",
                "some-invalid-characters-in-the-name-20240114121231",
                id="app_name_with_suffix_invalid_characters",
            ),
            pytest.param(
                "name.with_8.numerical-characters/12345678",
                empty_suffix,
                "name-with-8-numerical-characters-12345678",
                "name-with-8-numerical-characters-12345678",
                id="app_name_without_suffix_numerical_characters",
            ),
            pytest.param(
                "name.with_8.numerical-characters/12345678",
                default_app_id_suffix,
                "name-with-8-numerical-characters-12345678",
                "name-with-8-numerical-characters-12345678-20240114121231",
                id="app_name_with_suffix_numerical_characters",
            ),
            pytest.param(
                "./-_---name-with-trailing-and-leading-dashes-_-_-,;",
                empty_suffix,
                "name-with-trailing-and-leading-dashes",
                "name-with-trailing-and-leading-dashes",
                id="app_name_without_suffix_trailing_and_leading_dashes",
            ),
            pytest.param(
                "./-_---name-with-trailing-and-leading-dashes-_-_-,;",
                default_app_id_suffix,
                "name-with-trailing-and-leading-dashes",
                "name-with-trailing-and-leading-dashes-20240114121231",
                id="app_name_with_suffix_trailing_and_leading_dashes",
            ),
            pytest.param(
                "12345-name-starts-with-numbers",
                empty_suffix,
                "name-starts-with-numbers",
                "name-starts-with-numbers",
                id="app_name_without_suffix_starts_with_numbers",
            ),
            pytest.param(
                "12345-name-starts-with-numbers",
                default_app_id_suffix,
                "name-starts-with-numbers",
                "name-starts-with-numbers-20240114121231",
                id="app_name_with_suffix_starts_with_numbers",
            ),
            pytest.param(
                None,
                empty_suffix,
                "spark-app",
                "spark-app",
                id="none_app_name_without_suffix",
            ),
            pytest.param(
                None,
                default_app_id_suffix,
                "spark-app-20240114121231",
                "spark-app-20240114121231",
                id="none_app_name_with_suffix",
            ),
            pytest.param(
                "custom-app-id-suffix",
                lambda: "-custom-app-id-suffix",
                "custom-app-id-suffix",
                "custom-app-id-suffix-custom-app-id-suffix",
                id="custom_app_id_suffix",
            ),
            pytest.param(
                "custom-dynamic-app-id-suffix",
                lambda: f"-{int(datetime.datetime.now().timestamp())}",
                "custom-dynamic-app-id-suffix",
                "custom-dynamic-app-id-suffix-1705234351",
                id="custom_dynamic_app_id_suffix",
            ),
        ],
    )
    @freeze_time(FAKE_TIME)
    def test_parse_app_name_and_id(
        self, app_name: str, app_id_suffix: Callable[[], str], expected_app_name: str, expected_app_id: str
    ):
        """
        Test the method _parse_app_name_and_id
        """
        spark_client = SparkOnK8S()
        actual_app_name, actual_app_id = spark_client._parse_app_name_and_id(
            app_name=app_name, app_id_suffix=app_id_suffix
        )
        assert actual_app_name == expected_app_name, "The app name is not as expected"
        assert actual_app_id == expected_app_id, "The app id is not as expected"

    @mock.patch("kubernetes.config.kube_config.load_kube_config")
    @mock.patch("kubernetes.client.api.core_v1_api.CoreV1Api.create_namespaced_pod")
    @mock.patch("kubernetes.client.api.core_v1_api.CoreV1Api.create_namespaced_service")
    @freeze_time(FAKE_TIME)
    def test_submit_app(
        self, mock_create_namespaced_service, mock_create_namespaced_pod, mock_load_kube_config
    ):
        """Test the method submit_app"""

        spark_client = SparkOnK8S()
        spark_client.submit_app(
            image="pyspark-job",
            app_path="local:///opt/spark/work-dir/job.py",
            namespace="spark",
            service_account="spark",
            app_name="pyspark-job-example",
            app_arguments=["100000"],
            app_waiter="no_wait",
            image_pull_policy="Never",
            ui_reverse_proxy=True,
            driver_resources=PodResources(cpu=1, memory=2048, memory_overhead=1024),
            executor_instances=ExecutorInstances(min=2, max=5, initial=5),
        )

        expected_app_name = "pyspark-job-example"
        expected_app_id = f"{expected_app_name}-20240114121231"

        created_pod = mock_create_namespaced_pod.call_args[1]["body"]
        assert created_pod.metadata.name == f"{expected_app_id}-driver"
        assert created_pod.metadata.labels["spark-app-name"] == expected_app_name
        assert created_pod.metadata.labels["spark-app-id"] == expected_app_id
        assert created_pod.metadata.labels["spark-role"] == "driver"
        assert created_pod.spec.containers[0].image == "pyspark-job"
        assert created_pod.spec.containers[0].args == [
            "driver",
            "--master",
            "k8s://https://kubernetes.default.svc.cluster.local:443",
            "--conf",
            f"spark.app.name={expected_app_name}",
            "--conf",
            f"spark.app.id={expected_app_id}",
            "--conf",
            "spark.kubernetes.namespace=spark",
            "--conf",
            "spark.kubernetes.authenticate.driver.serviceAccountName=spark",
            "--conf",
            "spark.kubernetes.container.image=pyspark-job",
            "--conf",
            f"spark.driver.host={expected_app_id}",
            "--conf",
            "spark.driver.port=7077",
            "--conf",
            f"spark.kubernetes.driver.pod.name={expected_app_id}-driver",
            "--conf",
            f"spark.kubernetes.executor.podNamePrefix={expected_app_id}",
            "--conf",
            "spark.kubernetes.container.image.pullPolicy=Never",
            "--conf",
            "spark.driver.memory=2048m",
            "--conf",
            "spark.executor.cores=1",
            "--conf",
            "spark.executor.memory=1024m",
            "--conf",
            "spark.executor.memoryOverhead=512m",
            "--conf",
            f"spark.ui.proxyBase=/webserver/ui/spark/{expected_app_id}",
            "--conf",
            "spark.ui.proxyRedirectUri=/",
            "--conf",
            "spark.dynamicAllocation.enabled=true",
            "--conf",
            "spark.dynamicAllocation.shuffleTracking.enabled=true",
            "--conf",
            "spark.dynamicAllocation.minExecutors=2",
            "--conf",
            "spark.dynamicAllocation.maxExecutors=5",
            "--conf",
            "spark.dynamicAllocation.initialExecutors=5",
            "local:///opt/spark/work-dir/job.py",
            "100000",
        ]

    @mock.patch("kubernetes.config.kube_config.load_kube_config")
    @mock.patch("spark_on_k8s.utils.app_manager.SparkAppManager.stream_logs")
    @mock.patch("kubernetes.client.api.core_v1_api.CoreV1Api.create_namespaced_pod")
    @mock.patch("kubernetes.client.api.core_v1_api.CoreV1Api.create_namespaced_service")
    @freeze_time(FAKE_TIME)
    def test_submit_app_with_env_configurations(
        self,
        mock_create_namespaced_service,
        mock_create_namespaced_pod,
        mock_stream_logs,
        mock_load_kube_config,
    ):
        """Test the method submit_app with env configurations"""
        os.environ["SPARK_ON_K8S_DOCKER_IMAGE"] = "test-spark-on-k8s-docker-image"
        os.environ["SPARK_ON_K8S_APP_PATH"] = "/path/to/app.py"
        os.environ["SPARK_ON_K8S_NAMESPACE"] = "test-namespace"
        os.environ["SPARK_ON_K8S_SERVICE_ACCOUNT"] = "test-service-account"
        os.environ["SPARK_ON_K8S_APP_NAME"] = "test-spark-app"
        os.environ["SPARK_ON_K8S_APP_ARGUMENTS"] = '["arg1","arg2"]'
        os.environ["SPARK_ON_K8S_APP_WAITER"] = "log"
        os.environ["SPARK_ON_K8S_IMAGE_PULL_POLICY"] = "Always"
        os.environ["SPARK_ON_K8S_UI_REVERSE_PROXY"] = "true"
        os.environ["SPARK_ON_K8S_DRIVER_CPU"] = "1"
        os.environ["SPARK_ON_K8S_DRIVER_MEMORY"] = "1024"
        os.environ["SPARK_ON_K8S_DRIVER_MEMORY_OVERHEAD"] = "512"
        os.environ["SPARK_ON_K8S_EXECUTOR_CPU"] = "1"
        os.environ["SPARK_ON_K8S_EXECUTOR_MEMORY"] = "718"
        os.environ["SPARK_ON_K8S_EXECUTOR_MEMORY_OVERHEAD"] = "512"
        os.environ["SPARK_ON_K8S_EXECUTOR_MIN_INSTANCES"] = "2"
        os.environ["SPARK_ON_K8S_EXECUTOR_MAX_INSTANCES"] = "5"
        os.environ["SPARK_ON_K8S_EXECUTOR_INITIAL_INSTANCES"] = "5"
        os.environ["SPARK_ON_K8S_SPARK_CONF"] = json.dumps(
            {"spark.conf1.key": "spark.conf1.value", "spark.conf2.key": "spark.conf2.value"}
        )

        importlib.reload(configuration_module)
        importlib.reload(client_module)

        spark_client = SparkOnK8S()
        spark_client.submit_app()

        expected_app_name = "test-spark-app"
        expected_app_id = f"{expected_app_name}-20240114121231"

        created_pod = mock_create_namespaced_pod.call_args[1]["body"]
        assert created_pod.spec.containers[0].image == "test-spark-on-k8s-docker-image"
        assert created_pod.spec.containers[0].args == [
            "driver",
            "--master",
            "k8s://https://kubernetes.default.svc.cluster.local:443",
            "--conf",
            f"spark.app.name={expected_app_name}",
            "--conf",
            f"spark.app.id={expected_app_id}",
            "--conf",
            "spark.kubernetes.namespace=test-namespace",
            "--conf",
            "spark.kubernetes.authenticate.driver.serviceAccountName=test-service-account",
            "--conf",
            "spark.kubernetes.container.image=test-spark-on-k8s-docker-image",
            "--conf",
            f"spark.driver.host={expected_app_id}",
            "--conf",
            "spark.driver.port=7077",
            "--conf",
            f"spark.kubernetes.driver.pod.name={expected_app_id}-driver",
            "--conf",
            f"spark.kubernetes.executor.podNamePrefix={expected_app_id}",
            "--conf",
            "spark.kubernetes.container.image.pullPolicy=Always",
            "--conf",
            "spark.driver.memory=1024m",
            "--conf",
            "spark.executor.cores=1",
            "--conf",
            "spark.executor.memory=718m",
            "--conf",
            "spark.executor.memoryOverhead=512m",
            "--conf",
            f"spark.ui.proxyBase=/webserver/ui/test-namespace/{expected_app_id}",
            "--conf",
            "spark.ui.proxyRedirectUri=/",
            "--conf",
            "spark.dynamicAllocation.enabled=true",
            "--conf",
            "spark.dynamicAllocation.shuffleTracking.enabled=true",
            "--conf",
            "spark.dynamicAllocation.minExecutors=2",
            "--conf",
            "spark.dynamicAllocation.maxExecutors=5",
            "--conf",
            "spark.dynamicAllocation.initialExecutors=5",
            "--conf",
            "spark.conf1.key=spark.conf1.value",
            "--conf",
            "spark.conf2.key=spark.conf2.value",
            "/path/to/app.py",
            "arg1",
            "arg2",
        ]
