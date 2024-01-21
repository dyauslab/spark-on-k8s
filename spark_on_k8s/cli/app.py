from __future__ import annotations

from typing import Literal

import click

from spark_on_k8s.cli.options import (
    app_id_option,
    app_name_option,
    app_path_option,
    class_name_option,
    docker_image_option,
    force_option,
    image_pull_policy_option,
    logs_option,
    namespace_option,
    service_account_option,
    spark_conf_option,
    ui_reverse_proxy_option,
    wait_option,
)


@click.group(name="app")
def app_cli():
    pass


class SparkAppCommand(click.Command):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.params.insert(0, app_id_option)
        self.params.insert(1, namespace_option)


@app_cli.command(cls=SparkAppCommand)
def status(app_id: str, namespace: str):
    from spark_on_k8s.utils.app_manager import SparkAppManager

    app_manager = SparkAppManager()
    print(app_manager.app_status(namespace=namespace, app_id=app_id).value)


@app_cli.command(cls=SparkAppCommand)
def logs(app_id: str, namespace: str):
    from spark_on_k8s.utils.app_manager import SparkAppManager

    app_manager = SparkAppManager()
    app_manager.stream_logs(namespace=namespace, app_id=app_id, print_logs=True)


@app_cli.command(cls=SparkAppCommand)
def kill(app_id: str, namespace: str):
    from spark_on_k8s.utils.app_manager import SparkAppManager

    app_manager = SparkAppManager()
    app_manager.kill_app(namespace=namespace, app_id=app_id)


@app_cli.command(
    cls=SparkAppCommand,
    params=[force_option],
)
def delete(app_id: str, namespace: str, force: bool):
    from spark_on_k8s.utils.app_manager import SparkAppManager

    app_manager = SparkAppManager()
    app_manager.delete_app(namespace=namespace, app_id=app_id, force=force)


@app_cli.command(cls=SparkAppCommand)
def wait(app_id: str, namespace: str):
    from spark_on_k8s.utils.app_manager import SparkAppManager

    app_manager = SparkAppManager()
    app_manager.wait_for_app(namespace=namespace, app_id=app_id)
    app_status = app_manager.app_status(namespace=namespace, app_id=app_id)
    print(f"App {app_id} has terminated with status {app_status.value}")


@app_cli.command(
    params=[
        docker_image_option,
        app_path_option,
        namespace_option,
        service_account_option,
        app_name_option,
        spark_conf_option,
        class_name_option,
        wait_option,
        logs_option,
        image_pull_policy_option,
        ui_reverse_proxy_option,
    ]
)
@click.argument("app_arguments", nargs=-1, type=str)
def submit(
    image: str,
    path: str,
    namespace: str,
    service_account: str,
    name: str | None,
    spark_conf: dict[str, str],
    class_name: str | None,
    wait: bool,
    logs: bool,
    image_pull_policy: Literal["Always", "Never", "IfNotPresent"],
    ui_reverse_proxy: bool,
    app_arguments: tuple[str, ...],
):
    from spark_on_k8s.client.generic import SparkOnK8S

    spark_client = SparkOnK8S()
    spark_client.submit_app(
        image=image,
        app_path=path,
        namespace=namespace,
        service_account=service_account,
        app_name=name,
        spark_conf=spark_conf,
        class_name=class_name,
        app_waiter="print" if logs else "wait" if wait else "no_wait",
        image_pull_policy=image_pull_policy,
        ui_reverse_proxy=ui_reverse_proxy,
        app_arguments=list(app_arguments),
    )
